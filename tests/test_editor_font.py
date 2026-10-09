"""Tests for the editor font picker (family + size, persisted)."""

import os
import sys

import pytest

PySide6 = pytest.importorskip('PySide6')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402

from editor import main_window as main_window_module  # noqa: E402
from editor.main_window import MainWindow  # noqa: E402


def _isolated_settings(tmp_path, monkeypatch):
    from PySide6 import QtCore as _QC
    settings = _QC.QSettings(
        str(tmp_path / 'font-test.ini'), _QC.QSettings.IniFormat)
    settings.clear()
    monkeypatch.setattr(main_window_module, 'default_settings',
                        lambda: settings)
    return settings


def _other_family(current):
    families = QtGui.QFontDatabase.families()
    for name in families:
        if name and name != current:
            return name
    return current


@pytest.fixture()
def window(qapp):
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    win.show()
    yield win
    win.close()


def test_palette_lists_choose_font(window):
    ids = [c[0] for c in window._palette_commands()]
    assert 'view.chooseFont' in ids


def test_choose_font_accept_applies_and_persists(window, tmp_path, monkeypatch, qapp):
    settings = _isolated_settings(tmp_path, monkeypatch)
    window._settings = settings
    family = _other_family(window.editor.font().family())
    picked = QtGui.QFont(family, 20)
    monkeypatch.setattr(
        QtWidgets.QFontDialog, 'getFont',
        staticmethod(lambda *args, **kwargs: (QtGui.QFont(picked), True)))
    window._choose_editor_font()
    assert window.editor.font().family() == family
    assert window.editor.font().pointSizeF() == 20
    assert window._default_font_size == 20
    assert settings.value('editor/fontFamily') == family
    assert float(settings.value('editor/fontSize')) == 20
    # Reset Zoom now returns to the chosen size.
    window._zoom(-5)
    window._zoom_reset()
    assert window.editor.font().pointSizeF() == 20


def test_choose_font_cancel_changes_nothing(window, monkeypatch, qapp):
    before_family = window.editor.font().family()
    before_size = window.editor.font().pointSizeF()
    monkeypatch.setattr(
        QtWidgets.QFontDialog, 'getFont',
        staticmethod(lambda *args, **kwargs: (QtGui.QFont(), False)))
    window._choose_editor_font()
    assert window.editor.font().family() == before_family
    assert window.editor.font().pointSizeF() == before_size


def test_set_editor_font_rejects_garbage(window, qapp):
    before_family = window.editor.font().family()
    before_size = window.editor.font().pointSizeF()
    assert window._set_editor_font('   ', 'not-a-size') is False
    assert window._set_editor_font('', None) is False
    assert window.editor.font().family() == before_family
    assert window.editor.font().pointSizeF() == before_size


def test_set_editor_font_clamps_size(window, tmp_path, monkeypatch, qapp):
    window._settings = _isolated_settings(tmp_path, monkeypatch)
    assert window._set_editor_font('', 1000) is True
    assert window.editor.font().pointSizeF() == 48.0
    assert window._set_editor_font('', 1) is True
    assert window.editor.font().pointSizeF() == 6.0


def test_stored_font_restores_on_startup(tmp_path, monkeypatch, qapp):
    settings = _isolated_settings(tmp_path, monkeypatch)
    family = QtGui.QFontDatabase.systemFont(
        QtGui.QFontDatabase.FixedFont).family()
    settings.setValue('editor/fontFamily', family)
    settings.setValue('editor/fontSize', 18)
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        assert win.editor.font().pointSizeF() == 18
        assert win._default_font_size == 18
    finally:
        win.close()


def test_garbage_stored_font_ignored(tmp_path, monkeypatch, qapp):
    settings = _isolated_settings(tmp_path, monkeypatch)
    settings.setValue('editor/fontFamily', '   ')
    settings.setValue('editor/fontSize', 'huge')
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        assert win.editor.font().pointSizeF() == win._default_font_size
        assert win.editor.font().family() != ''
    finally:
        win.close()
