"""Regression tests for audit fixes (editor/LSP/geometry)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_point_thousands_coordinates():
    from geometry.parsing import parse_draw_block
    import io
    import contextlib
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        out = parse_draw_block('*point(A = 1,000, 0)')
    assert 'invalid coordinates' not in err.getvalue()
    assert out is not None


def test_labels_circle_thousands_radius_no_crash():
    from geometry.solver import GeometrySolver
    from geometry.labels import _label_anchors
    from geometry.commands import _process_command
    from geometry.parsing import split_args_for
    solver = GeometrySolver()
    for cmd_text in ('*point(A = 0, 0)', '*point(B = 3, 0)', '*circle(A ; 1,000)'):
        name = cmd_text[1:cmd_text.index('(')]
        argstr = cmd_text[cmd_text.index('(') + 1:-1]
        _process_command(solver, name, split_args_for(name, argstr))
    solver.solve()
    assert isinstance(_label_anchors(solver), dict)


def test_draw_completion_suggested():
    from lsp.analysis import complete
    labels = [i['label'] for i in complete('*draw(*point(A = 0, 0))', 0, 1)]
    assert 'draw' in labels


def test_find_emoji_offsets_qt_native(qapp):
    from PySide6 import QtGui
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        win.editor.setPlainText('😀 foo 😀 foo\n')
        ranges = win._find_all_ranges('foo')
        assert len(ranges) == 2
        for s, e in ranges:
            cursor = win.editor.textCursor()
            cursor.setPosition(s)
            cursor.setPosition(e, QtGui.QTextCursor.KeepAnchor)
            assert cursor.selectedText() == 'foo'
    finally:
        win.close()


def test_goto_focuses_editor(qapp):
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        win.editor.setPlainText('a\nb\n')
        calls = []
        orig = win.editor.setFocus
        win.editor.setFocus = lambda *a, **k: (calls.append(1), orig(*a, **k))
        try:
            win._goto(1, 0)
        finally:
            win.editor.setFocus = orig
        assert win.editor.textCursor().blockNumber() == 1
        assert calls, 'expected _goto to request editor focus'
    finally:
        win.close()


def test_toggle_find_clears_highlights(qapp):
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        win.editor.setPlainText('foo foo\n')
        win._toggle_find()
        win._find_bar._input.setText('foo')
        assert win._find_bar.isVisible()
        assert win._find_ranges
        win._toggle_find()
        assert not win._find_bar.isVisible()
        assert win.editor.extraSelections() is not None
        from editor.main_window import MainWindow as MW
        leftover = [s for s in win.editor.extraSelections()
                    if s.format.property(MW._FIND_PROP)]
        assert leftover == []
    finally:
        win.close()


def test_save_as_preserves_cursor(qapp, tmp_path):
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        win.editor.setPlainText('hello world\n')
        cursor = win.editor.textCursor()
        cursor.setPosition(5)
        win.editor.setTextCursor(cursor)
        target = str(tmp_path / 'out.ezmath')
        win._file_dialog = lambda save, title: (target, '')
        assert win._save_as() is True
        assert win.editor.textCursor().position() == 5
    finally:
        win.close()


def test_atomic_write_preserves_mode(tmp_path):
    import stat
    from editor.main_window import MainWindow
    target = tmp_path / 'doc.ezmath'
    target.write_text('old', encoding='utf-8')
    try:
        os.chmod(target, 0o644)
    except OSError:
        pytest.skip('chmod not supported')
    MainWindow._atomic_write(str(target), 'new')
    assert target.read_text(encoding='utf-8') == 'new'
    if os.name != 'nt':
        assert stat.S_IMODE(os.stat(target).st_mode) == 0o644


def test_paths_no_macos_dirs_off_darwin(monkeypatch):
    import sys as _sys
    from editor import paths
    if _sys.platform == 'darwin':
        pytest.skip('darwin-only behavior')
    monkeypatch.setattr(_sys, 'platform', 'win32')
    dirs = paths.candidate_directories()
    assert '/Applications/EasyMath/bin' not in dirs
    assert '/Applications/EasyMathLang/bin' not in dirs
