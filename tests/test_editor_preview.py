"""Live preview tests (headless compile + offscreen panel/window)."""

import os
import sys

import pytest

PySide6 = pytest.importorskip('PySide6')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from compiler import pipeline as _pipeline  # noqa: E402
from editor.preview import compile_source_to_pdf  # noqa: E402


def test_compile_source_to_pdf_ok(tmp_path, monkeypatch):
    _stub = type('_TypstStub', (),
                 {'compile': staticmethod(lambda *a, **k: None)})()
    monkeypatch.setattr(_pipeline, 'typst', _stub)
    result = compile_source_to_pdf('<a> = 5\nValue: <a>\n', str(tmp_path))
    assert result['ok'] is False  # no real PDF backend under the stub
    assert result['pdf'] is None
    typ = open(result['typ'], encoding='utf-8').read()
    assert 'Value: 5' in typ


def test_compile_source_to_pdf_real_backend(tmp_path):
    pytest.importorskip('typst')
    result = compile_source_to_pdf('Hello preview\n', str(tmp_path))
    assert result['ok'] is True
    assert result['pdf'] and os.path.isfile(result['pdf'])


def test_compile_source_failure_returns_log(tmp_path, monkeypatch):
    _stub = type('_TypstStub', (),
                 {'compile': staticmethod(lambda *a, **k: None)})()
    monkeypatch.setattr(_pipeline, 'typst', _stub)
    result = compile_source_to_pdf('Hello\n*(\n<a> = 1\n', str(tmp_path))
    assert result['ok'] is False
    assert 'Unclosed block' in result['log']


@pytest.fixture()
def window(qapp):
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    win.show()
    yield win
    win.close()


def test_preview_dock_hidden_by_default(window):
    assert window._preview_dock.windowTitle() == 'Preview'
    assert not window._preview_dock.isVisible()
    ids = [c[0] for c in window._palette_commands()]
    assert 'view.togglePreview' in ids
    assert 'build.refreshPreview' in ids


def test_schedule_preview_bumps_version_and_starts_timer(window, qapp):
    from PySide6 import QtCore
    window._preview_dock.show()
    qapp.processEvents()
    before = window._preview_version
    window.editor.setPlainText('hello\n')
    assert window._preview_version > before
    assert window._preview_timer.isActive()
    # Auto-off cancels pending work.
    window.preview.set_auto_enabled(False)
    qapp.processEvents()
    assert window._preview_timer.isActive() is False
    window.preview.set_auto_enabled(True)


def test_stale_preview_results_dropped(window):
    window._preview_version = 5
    window._on_preview_finished(4, {'ok': True,
                                    'pdf': 'nope.pdf', 'log': ''})
    assert window.preview.pdf_path is None
    window._on_preview_finished(5, {'ok': False, 'pdf': None,
                                    'log': 'boom'})
    assert 'error' in window.preview.status_label.text().lower()


def test_preview_panel_states(qapp):
    from editor.preview_panel import PreviewPanel
    panel = PreviewPanel()
    panel.show()
    panel.show_empty()
    assert 'idle' in panel.status_label.text().lower()
    panel.show_loading()
    assert 'updating' in panel.status_label.text().lower()
    panel.show_error('something broke')
    assert 'error' in panel.status_label.text().lower()
    panel.close()


def test_preview_shows_all_pages_continuously(window, qapp):
    from editor.preview_panel import pdf_available
    if not pdf_available():
        pytest.skip('Qt PDF modules unavailable')
    from PySide6.QtPdfWidgets import QPdfView
    assert window.preview._view.pageMode() == QPdfView.PageMode.MultiPage
    assert window.preview._view.zoomMode() == QPdfView.ZoomMode.FitToWidth


def test_refresh_preview_end_to_end(window, qapp):
    pytest.importorskip('typst')
    from PySide6 import QtCore

    window.editor.setPlainText('<a> = 5\nValue: <a>\n')
    window._refresh_preview_now()
    assert window._preview_dock.isVisible()

    loop = QtCore.QEventLoop()
    finished = {}

    def _done(version, result):
        finished['v'] = version

    window._preview_worker.finished.connect(_done)
    timer = QtCore.QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(15000)
    poll = QtCore.QTimer()
    poll.timeout.connect(
        lambda: loop.quit() if window.preview.pdf_path else None)
    poll.start(50)
    loop.exec()
    poll.stop()
    timer.stop()
    assert window.preview.pdf_path is not None
    assert 'up to date' in window.preview.status_label.text().lower()


def test_refresh_preview_multi_page(window, qapp):
    pytest.importorskip('typst')
    from PySide6 import QtCore
    from PySide6.QtPdfWidgets import QPdfView

    lines = [f'Line {i}: filler text to fill the page' for i in range(1, 120)]
    window.editor.setPlainText('<a> = 5\n' + '\n'.join(lines) + '\n')
    window._refresh_preview_now()

    loop = QtCore.QEventLoop()
    timer = QtCore.QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(15000)
    poll = QtCore.QTimer()
    poll.timeout.connect(
        lambda: loop.quit() if window.preview.pdf_path else None)
    poll.start(50)
    loop.exec()
    poll.stop()
    timer.stop()
    assert window.preview.pdf_path is not None
    assert int(window.preview._document.pageCount()) > 1
    assert 'pages' in window.preview.status_label.text().lower()
    # Whole document stays scrollable after reload (not single-page).
    assert window.preview._view.pageMode() == QPdfView.PageMode.MultiPage
