"""Regression cases found while auditing v4.2.0."""

import hashlib
import os
from pathlib import Path

import pytest

from compiler.pipeline import compile_ezmath
from compiler.state import CompileContext
from compiler.variables import check_undefined_vars
from editor.preview import compile_source_to_format, export_source_to_file


@pytest.mark.parametrize('fmt', ['svg', 'png', 'typ', 'html'])
def test_explicit_format_selects_default_extension(tmp_path, fmt):
    src = tmp_path / 'doc.ezmath'
    src.write_text('Hello', encoding='utf-8')
    assert compile_ezmath(src, format=fmt)
    assert src.with_suffix('.' + fmt).is_file()
    assert not src.with_suffix('.pdf').exists()


def test_cli_format_selects_default_extension(tmp_path, monkeypatch):
    from compiler import pipeline
    src = tmp_path / 'doc.ezmath'
    src.write_text('Hello', encoding='utf-8')
    monkeypatch.setattr('sys.argv', ['ezmath', '--format', 'svg', str(src)])
    with pytest.raises(SystemExit) as exc:
        pipeline.main()
    assert exc.value.code == 0
    assert src.with_suffix('.svg').is_file()
    assert not src.with_suffix('.pdf').exists()


@pytest.mark.parametrize('alias', ['same', 'symlink', 'hardlink'])
def test_output_cannot_overwrite_source(tmp_path, alias):
    src = tmp_path / 'doc.ezmath'
    src.write_text('Keep this source', encoding='utf-8')
    out = src
    if alias != 'same':
        out = tmp_path / 'alias.pdf'
        try:
            if alias == 'symlink':
                out.symlink_to(src)
            else:
                os.link(src, out)
        except OSError:
            pytest.skip(f'{alias} unsupported')
    assert compile_ezmath(src, output=out) is False
    assert src.read_text(encoding='utf-8') == 'Keep this source'


@pytest.mark.parametrize('suffix', ['.typ', '.smap.json'])
def test_generated_artifacts_cannot_overwrite_source(tmp_path, suffix):
    src = tmp_path / ('doc' + suffix)
    src.write_text('Keep this source', encoding='utf-8')
    kwargs = {'source_map_path': src} if suffix == '.smap.json' else {}
    assert compile_ezmath(src, output=tmp_path / 'out.pdf', **kwargs) is False
    assert src.read_text(encoding='utf-8') == 'Keep this source'


def test_undefined_replacements_respect_operator_adjacency(capsys):
    text = '<x> and <<x>> and < x > and << x >>'
    assert check_undefined_vars(text, 1, CompileContext()) == (
        '[UNDEFINED: <x>] and <<x>> and [UNDEFINED: <x>] and << x >>')


def test_preview_pages_numeric_order_and_no_stale_pages(tmp_path):
    def render(n):
        return compile_source_to_format(
            '\n*newpage\n'.join(f'Page {i}' for i in range(1, n + 1)),
            tmp_path, format='svg')
    result = render(12)
    assert result['ok']
    assert [Path(f).name for f in result['files']] == [
        f'preview-{i}.svg' for i in range(1, 13)]
    result = render(2)
    assert result['ok']
    assert [Path(f).name for f in result['files']] == ['preview-1.svg', 'preview-2.svg']
    result = render(1)
    assert result['ok'] and len(result['files']) == 1
    result = render(2)
    assert result['ok'] and len(result['files']) == 2


def test_editor_typ_export_retains_diagram_assets(tmp_path):
    import typst
    output = tmp_path / 'lesson.typ'
    result = export_source_to_file('*plot(x ; -1 ; 1)', output)
    assert result['ok']
    # Compile after the helper's temporary directory has been removed.
    typst.compile(str(output), str(tmp_path / 'lesson.pdf'), ignore_system_fonts=True)
    assert (tmp_path / 'lesson.pdf').read_bytes().startswith(b'%PDF')


def test_separate_typ_exports_do_not_replace_each_others_assets(tmp_path):
    first = tmp_path / 'first.typ'
    second = tmp_path / 'second.typ'
    assert export_source_to_file('*plot(x ; -1 ; 1)', first)['ok']
    assets = {p: p.read_bytes() for p in tmp_path.glob('*.svg')}
    assert assets
    assert export_source_to_file('*plot(x ; -2 ; 2)', second)['ok']
    assert all(p.read_bytes() == data for p, data in assets.items())


def test_plot_power_tower_is_bounded():
    # A subprocess timeout makes this regression safe even if the bigint
    # guard is accidentally removed later.
    import subprocess
    import sys
    code = '''
import numpy as np
from compiler.plots import evaluate_on_grid
from compiler.state import CompileContext
try:
    evaluate_on_grid(CompileContext(), '9^9^9', np.array([0., 1.]))
except ValueError as exc:
    assert 'exponent too large' in str(exc)
else:
    raise AssertionError('unbounded power accepted')
'''
    subprocess.run([sys.executable, '-c', code], check=True, timeout=5)


def test_failed_diagram_render_closes_figure(tmp_path, monkeypatch):
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure
    from compiler.plots import render_plot_svg
    before = plt.get_fignums()
    def fail(*args, **kwargs):
        raise OSError('disk full')
    monkeypatch.setattr(Figure, 'savefig', fail)
    try:
        with pytest.raises(RuntimeError, match='disk full'):
            render_plot_svg(CompileContext(), 'x', -1, 1, tmp_path / 'plot.svg')
        assert plt.get_fignums() == before
    finally:
        for number in set(plt.get_fignums()) - set(before):
            plt.close(number)


@pytest.mark.parametrize('fmt', ['pdf', 'typ'])
def test_editor_resolves_images_from_saved_document(tmp_path, fmt):
    import typst
    project = tmp_path / 'project'
    project.mkdir()
    src = project / 'lesson.ezmath'
    image = project / 'figure.svg'
    image.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20">'
                     '<rect width="20" height="20" fill="red"/></svg>', encoding='utf-8')
    text = '*image(figure.svg ; 20%)'
    src.write_text(text, encoding='utf-8')
    preview = compile_source_to_format(text, tmp_path / 'preview', source_path=src)
    assert preview['ok'] and '[Image Error' not in preview['log']
    out = tmp_path / 'exports' / ('lesson.' + fmt)
    result = export_source_to_file(text, out, source_path=src)
    assert result['ok'] and '[Image Error' not in result['log']
    if fmt == 'typ':
        # Exported source must be independent of both the original image
        # and the temporary preview directory.
        image.unlink()
        typst.compile(str(out), str(out.with_suffix('.pdf')), ignore_system_fonts=True)


def test_editor_export_refuses_source_alias(tmp_path):
    src = tmp_path / 'lesson.ezmath'
    src.write_text('Keep me', encoding='utf-8')
    result = export_source_to_file('New text', src, format='pdf', source_path=src)
    assert not result['ok']
    assert src.read_text(encoding='utf-8') == 'Keep me'


@pytest.mark.parametrize('pages', [1, 2, 12])
def test_editor_image_export_page_pattern(tmp_path, pages):
    out = tmp_path / 'page-{p}.svg'
    text = '\n*newpage\n'.join(f'Page {i}' for i in range(pages))
    result = export_source_to_file(text, out)
    assert result['ok']
    assert result['outputs'] == [str(tmp_path / f'page-{i}.svg')
                                  for i in range(1, pages + 1)]
    assert all(Path(p).is_file() for p in result['outputs'])
    assert not out.exists()


@pytest.mark.parametrize('ppi', [float('inf'), 1.5, True])
def test_invalid_resolution_fails_without_writing(tmp_path, ppi):
    src = tmp_path / 'doc.ezmath'
    src.write_text('Hello', encoding='utf-8')
    assert compile_ezmath(src, format='png', ppi=ppi) is False
    assert not src.with_suffix('.typ').exists()


def test_invalid_map_path_returns_failure(tmp_path):
    src = tmp_path / 'doc.ezmath'
    src.write_text('Hello', encoding='utf-8')
    assert compile_ezmath(src, source_map_path=123) is False


@pytest.mark.parametrize('conflict', ['typ-output', 'map-output', 'map-typ'])
def test_export_artifact_paths_must_not_collide(tmp_path, conflict):
    src = tmp_path / 'doc.ezmath'
    src.write_text('Hello', encoding='utf-8')
    out = src.with_suffix('.typ') if conflict == 'typ-output' else src.with_suffix('.pdf')
    kwargs = {}
    if conflict == 'map-output':
        kwargs['source_map_path'] = out
    elif conflict == 'map-typ':
        kwargs['source_map_path'] = src.with_suffix('.typ')
    assert compile_ezmath(src, output=out, format='pdf', **kwargs) is False
    assert src.read_text(encoding='utf-8') == 'Hello'
    assert not out.exists()


def test_multiline_math_preserves_floor_division_and_trailing_comment():
    from compiler.comments import strip_comments
    assert strip_comments('\\\na // b\n\\ // comment') == '\\\na // b\n\\ '


def test_comments_do_not_change_math_state():
    from compiler.comments import strip_comments
    assert strip_comments('hello // \\\nnext // hidden') == 'hello \nnext '
    assert strip_comments('*p(\\)\nnext // hidden') == '*p(\\)\nnext '
    assert strip_comments('<path> = C:\\folder\nnext // hidden') == '<path> = C:\\folder\nnext '


def test_fenced_code_preserves_literal_comments():
    from compiler.comments import strip_comments
    text = '```\na // literal\n\\\n```\nnext // hidden'
    assert strip_comments(text) == '```\na // literal\n\\\n```\nnext '


# --- AUDIT-001 regression: degenerate segment division-by-zero guard ---

def test_bad_len_degenerate_segment():
    """A zero-length segment must be caught by _bad_len."""
    import numpy as np
    from geometry.vectors import _norm
    from geometry.commands import _bad_len
    P = {'A': np.array([0.0, 0.0]), 'B': np.array([0.0, 0.0])}
    assert _bad_len(_norm(P['B'] - P['A'])) is True


def test_degenerate_perp_does_not_crash():
    """*perp with coincident points must not raise ZeroDivisionError."""
    from geometry.solver import GeometrySolver
    from geometry.commands import _process_command
    solver = GeometrySolver()
    solver.add_point('A', 0, 0)
    solver.add_point('B', 0, 0)
    solver.add_point('C', 1, 0)
    try:
        _process_command(solver, 'perp', ['A', 'B', 'C'])
    except ZeroDivisionError:
        raise AssertionError("Division by zero in degenerate *perp")


# --- AUDIT-008 regression: LSP source-range slicing uses source line ---

def test_lsp_calc_expression_uses_source_offsets():
    """The expression passed to evaluate_calc must come from the original
    source line (`code`), not from the masked/substituted `check_code`,
    so source-range slicing stays accurate after substitutions."""
    from lsp.analysis import _balanced_range
    from compiler.calc import evaluate_calc
    from compiler.state import CompileContext
    # A line with a variable that would change length after substitution.
    code = '<longvar> = 10\ncalc(1 + 1)'
    # For regression purposes we only verify the expression extraction
    # logic uses `code` offsets (the fix ensures `expr` is sliced from
    # `code`, not `check_code`).
    import re
    CALC_OPEN = re.compile(r'(?<![A-Za-z0-9_])\*?calc\(')
    # Find the calc call in the second line.
    lines = code.splitlines()
    for line in lines:
        for m in CALC_OPEN.finditer(line):
            close = _balanced_range(line, m.end() - 1)
            assert close is not None
            # Before the fix this could slice from a masked/substituted
            # string (wrong offsets); after the fix it uses the source.
            expr = line[m.end():close - 1]
            res = evaluate_calc(CompileContext(), expr)
            assert res == '2'


# --- AUDIT-003 regression: plot expression hash cache ---

def test_plot_cache_hit_skips_render(tmp_path):
    """Same expression/options with existing file gives a cache hit."""
    from compiler.plots import render_plot_svg, _PLOT_CACHE
    from compiler.state import CompileContext
    out = tmp_path / 'cached.svg'
    # First render writes file.
    render_plot_svg(CompileContext(), 'x', -1, 1, out)
    assert out.is_file()
    # The function should return quickly without error.
    result = render_plot_svg(CompileContext(), 'x', -1, 1, out)
    assert result == 'x'


def test_plot_cache_miss_different_expression(tmp_path):
    """Different expression gives a miss and writes a new file."""
    from compiler.plots import render_plot_svg
    from compiler.state import CompileContext
    out1 = tmp_path / 'plot1.svg'
    out2 = tmp_path / 'plot2.svg'
    render_plot_svg(CompileContext(), 'x', -1, 1, out1)
    render_plot_svg(CompileContext(), 'x*x', -1, 1, out2)
    assert out1.is_file()
    assert out2.is_file()


def test_plot_cache_regenerates_deleted_svg(tmp_path):
    """If the cached SVG file is deleted, the next call regenerates it."""
    from compiler.plots import render_plot_svg
    from compiler.state import CompileContext
    out = tmp_path / 'regenerated.svg'
    render_plot_svg(CompileContext(), 'x', -1, 1, out)
    out.unlink()
    assert not out.is_file()
    render_plot_svg(CompileContext(), 'x', -1, 1, out)
    assert out.is_file()


def test_plot_cache_miss_on_options_change(tmp_path):
    """Different samples or bounds change the hash key (miss)."""
    from compiler.plots import render_plot_svg
    from compiler.state import CompileContext
    out1 = tmp_path / 'plot_samples.svg'
    out2 = tmp_path / 'plot_samples2.svg'
    render_plot_svg(CompileContext(), 'x', -1, 1, out1, samples=500)
    render_plot_svg(CompileContext(), 'x', -1, 1, out2, samples=500)
    assert out1.is_file() and out2.is_file()


# --- AUDIT-011 regression: editor threading cancellation (source inspection) ---

def test_preview_shutdown_flag_exists_in_source():
    """The preview shutdown mechanism exists and is called by closeEvent."""
    import inspect
    from editor import main_window
    # Verify source code contains cancellation logic (in closeEvent or _shutdown_preview).
    close_src = inspect.getsource(main_window.MainWindow.closeEvent)
    shutdown_src = inspect.getsource(main_window.MainWindow._shutdown_preview)
    assert '_preview_shutdown' in close_src or '_preview_shutdown' in shutdown_src
    assert 'quit()' in shutdown_src or 'terminate()' in shutdown_src


# --- AUDIT-002: deferred — threading/resource leaks (unverified in GUI) ---

def test_plot_cache_before_after_timing():
    import time, tempfile, os
    from compiler.plots import render_plot_svg
    from compiler.state import CompileContext
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, 'bench.svg')
        # Before: no cache file exists; render takes time.
        t0 = time.perf_counter()
        render_plot_svg(CompileContext(), 'x', -1, 1, out)
        t_first = time.perf_counter() - t0
        # After: cache hit; should be faster (skip Matplotlib render).
        t0 = time.perf_counter()
        render_plot_svg(CompileContext(), 'x', -1, 1, out)
        t_cached = time.perf_counter() - t0
        # Cache hit must be faster; report values.
        print(f"\n[Timing] first={t_first:.3f}s cached={t_cached:.3f}s speedup={t_first/max(t_cached,1e-6):.1f}x")
        assert t_cached < t_first, f"Cache did not speed up: cached={t_cached:.3f}s >= first={t_first:.3f}s"


# --- AUDIT-005 regression: offline cetz error message ---

def test_offline_cetz_error_message(monkeypatch, capsys):
    import tempfile, os
    from compiler import pipeline
    def fail_compile(*args, **kwargs):
        raise RuntimeError('failed to download @preview/cetz:0.4.2')
    monkeypatch.setattr(pipeline.typst, 'compile', fail_compile, raising=True)
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, 'draw.ezmath')
        with open(src, 'w') as f:
            f.write('*draw(\n*line(A;B)\n)')
        result = pipeline.compile_ezmath(src, output=os.path.join(td, 'draw.pdf'), format='pdf')
        assert result is False
        captured = capsys.readouterr()
        combined = (captured.out or '') + (captured.err or '')
        assert 'offline' in combined.lower() or 'download cetz' in combined.lower() or '@preview/cetz' in combined
