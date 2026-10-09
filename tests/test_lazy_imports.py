"""Startup-cost regression tests: heavy deps must stay lazy.

numpy (~11MB), the typst native backend, and matplotlib must not load
merely by importing the editor, the compiler pipeline, or geometry —
only by actually compiling/drawing/plotting. Subprocess isolation keeps
these assertions independent of test ordering.
"""

import os
import subprocess
import sys

import pytest

SRC = os.path.join(os.path.dirname(__file__), '..', 'src')
PY = sys.executable


def _run_isolated(code, extra_env=None):
    env = dict(os.environ)
    env['QT_QPA_PLATFORM'] = 'offscreen'
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        [PY, '-c', code], capture_output=True, text=True,
        cwd=os.path.join(os.path.dirname(__file__), '..'), env=env)
    return proc


def _check_absent(code):
    proc = _run_isolated(code)
    assert proc.returncode == 0, proc.stderr[-2000:]
    return proc.stdout.strip()


def test_geometry_import_without_numpy():
    out = _check_absent(
        "import sys; sys.path.insert(0, 'src');"
        "import geometry;"
        "from geometry.commands import KNOWN_GEOMETRY_COMMANDS;"
        "mods = {m.split('.')[0] for m in sys.modules};"
        "print('numpy' in mods, 'matplotlib' in mods);"
        "assert len(KNOWN_GEOMETRY_COMMANDS) > 0")
    assert out == 'False False'


def test_pipeline_import_without_typst():
    out = _check_absent(
        "import sys; sys.path.insert(0, 'src');"
        "import compiler.pipeline as p;"
        "mods = {m.split('.')[0] for m in sys.modules};"
        "print('typst' in mods, 'numpy' in mods, 'matplotlib' in mods);"
        "assert p.typst is None")
    assert out == 'False False False'


def test_mainwindow_import_without_heavy_deps():
    pytest.importorskip('PySide6')
    out = _check_absent(
        "import sys; sys.path.insert(0, 'src');"
        "import editor.main_window;"
        "mods = {m.split('.')[0] for m in sys.modules};"
        "print('numpy' in mods, 'typst' in mods, 'matplotlib' in mods)")
    assert out == 'False False False'


def test_geometry_still_uses_numpy_when_solving(tmp_path):
    """Lazy import must not change solver behavior."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
    from geometry.parsing import parse_draw_block
    out = parse_draw_block('*point(A = 0, 0)\n*point(B = 4, 0)\n*line(A ; B)\n')
    assert 'cetz' in out
    assert 'numpy' in {m.split('.')[0] for m in sys.modules}


def test_linecache_stays_bounded_over_repeated_compiles(tmp_path, monkeypatch, capsys):
    """Repeated identical compiles must not grow the source-line cache."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
    import linecache
    from compiler import compile_ezmath
    from compiler import pipeline as _pipeline
    stub = type('_TypstStub', (), {'compile': staticmethod(lambda *a, **k: None)})()
    monkeypatch.setattr(_pipeline, 'typst', stub)
    src = tmp_path / 'case.ezmath'
    src.write_text('<a> = 5\nValue: <a>\n', encoding='utf-8')
    out = tmp_path / 'case.pdf'

    def cache_bytes():
        return sum(sum(len(str(line)) for line in (entry[2] or []))
                   for entry in linecache.cache.values())

    compile_ezmath(str(src), str(out))  # warmup (fills + clears the cache)
    capsys.readouterr()
    before = cache_bytes()
    for _ in range(5):
        compile_ezmath(str(src), str(out))
    capsys.readouterr()
    after = cache_bytes()
    assert after - before < 256 * 1024, (before, after)


def test_preview_skips_identical_text(qapp):
    """Same text twice submits only one worker compile."""
    pytest.importorskip('PySide6')
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        win._preview_dock.show()
        emitted = []
        win._preview_request.connect(lambda *args: emitted.append(args))
        win.editor.setPlainText('hello\n')
        win._on_preview_timeout(force=True)
        assert len(emitted) == 1
        win._on_preview_timeout()  # same text: skipped
        assert len(emitted) == 1
        win.editor.setPlainText('hello world\n')
        win._on_preview_timeout()  # changed: submitted
        assert len(emitted) == 2
    finally:
        win.close()
