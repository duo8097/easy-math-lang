"""Regression cases found while auditing v4.2.0."""

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
