"""Dark mode tests (theme module + editor/main-window wiring)."""

import os
import sys

import pytest

PySide6 = pytest.importorskip('PySide6')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from editor import theme as app_theme  # noqa: E402


def test_normalize_and_color_tables():
    assert app_theme.normalize('dark') == 'dark'
    assert app_theme.normalize('DARK') == 'dark'
    assert app_theme.normalize('light') == 'light'
    assert app_theme.normalize('nope') == 'light'
    assert app_theme.normalize(None) == 'light'
    assert set(app_theme.editor_colors('dark')) == \
        set(app_theme.editor_colors('light'))
    assert set(app_theme.syntax_colors('dark')) == \
        set(app_theme.syntax_colors('light'))
    assert app_theme.editor_colors('dark')['editor_bg'] != \
        app_theme.editor_colors('light')['editor_bg']


def test_settings_roundtrip(qapp):
    from PySide6 import QtCore
    settings = QtCore.QSettings(
        os.path.join(os.environ.get('RUNNER_TEMP',
                                    os.path.expandvars('%TEMP%')),
                     'easymath-theme-test.ini'),
        QtCore.QSettings.IniFormat)
    settings.clear()
    assert app_theme.load_theme_name(settings) == 'light'
    app_theme.save_theme_name(settings, 'dark')
    assert app_theme.load_theme_name(settings) == 'dark'
    settings.clear()


def test_build_palette(qapp):
    from PySide6 import QtGui
    assert app_theme.build_palette('light') is None
    dark = app_theme.build_palette('dark')
    assert isinstance(dark, QtGui.QPalette)
    assert dark.color(QtGui.QPalette.Window).name() == '#353535'
    assert dark.color(QtGui.QPalette.Base).name() == '#1e1e1e'


def test_highlighter_theme_switch(qapp):
    from PySide6 import QtGui
    doc = QtGui.QTextDocument()
    from editor.syntax_highlighter import EmlHighlighter
    hl = EmlHighlighter(doc)
    assert hl.theme == 'light'
    light_comment = hl._comment_format.foreground().color().name()
    hl.set_theme('dark')
    assert hl.theme == 'dark'
    assert hl._comment_format.foreground().color().name() != light_comment
    assert hl._comment_format.foreground().color().name() == \
        app_theme.syntax_colors('dark')['comment']
    hl.set_theme('light')
    assert hl._comment_format.foreground().color().name() == light_comment


@pytest.fixture()
def window(qapp):
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    win.show()
    # Isolate from whatever theme a previous test persisted.
    win._apply_theme('light')
    yield win
    win._apply_theme('light')
    win.close()


def test_toggle_switches_editor_and_persists(window, qapp, tmp_path):
    from PySide6 import QtCore, QtGui
    # Default-constructed QSettings has no org/app in tests, so point the
    # window at an isolated store to check persistence.
    window._settings = QtCore.QSettings(
        str(tmp_path / 'theme.ini'), QtCore.QSettings.IniFormat)
    window._apply_theme('light')
    assert window._theme_name == 'light'
    assert window.editor.theme == 'light'
    assert window._theme_action.isChecked() is False

    window._toggle_theme()
    assert window._theme_name == 'dark'
    assert window.editor.theme == 'dark'
    assert window._theme_action.isChecked() is True
    pal = window.editor.palette()
    assert pal.color(QtGui.QPalette.Base).name() == '#1e1e1e'
    assert pal.color(QtGui.QPalette.Text).name() == '#d4d4d4'
    assert app_theme.load_theme_name(window._settings) == 'dark'

    window._toggle_theme()
    assert window._theme_name == 'light'
    pal = window.editor.palette()
    assert pal.color(QtGui.QPalette.Base).name() == '#ffffff'


def test_find_highlights_follow_theme_without_moving_cursor(window):
    from PySide6 import QtGui
    window.editor.setPlainText('width <width> width\n')
    window.editor.moveCursor(QtGui.QTextCursor.Start)
    window._do_find('width', 0)
    before = window.editor.textCursor().position()
    sel_bg = lambda: next(
        s.format.background().color().name()
        for s in window.editor.extraSelections()
        if s.format.property(window._FIND_PROP))

    assert sel_bg() == '#ffab40'
    window._apply_theme('dark')
    assert sel_bg() == '#d18616'
    assert window.editor.textCursor().position() == before
    window._apply_theme('light')
    assert sel_bg() == '#ffab40'


def test_palette_lists_theme_command(window):
    ids = [c[0] for c in window._palette_commands()]
    assert 'view.toggleTheme' in ids


def test_startup_with_saved_dark_theme(qapp, monkeypatch):
    """Rehighlight during init emits textChanged before lsp exists.

    Regression test: starting with ``theme=dark`` saved used to crash in
    ``_on_text_changed`` with ``AttributeError: ... no attribute 'lsp'``
    because QSyntaxHighlighter.rehighlight() emits textChanged.
    """
    from editor import main_window as main_window_module
    from editor.main_window import MainWindow
    monkeypatch.setattr(main_window_module.app_theme, 'load_theme_name',
                        lambda settings: 'dark')
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        assert win._theme_name == 'dark'
        assert win.editor.theme == 'dark'
    finally:
        win._apply_theme('light')
        win.close()
