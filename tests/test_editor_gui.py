"""Offscreen GUI smoke tests (no display, no LSP process)."""

import os

import pytest

PySide6 = pytest.importorskip('PySide6')

import sys  # noqa: E402

from PySide6 import QtGui, QtWidgets  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from easy_math_lang.editor.main_window import (  # noqa: E402
    MainWindow,
    markdown_to_html,
)


@pytest.fixture()
def window(qapp):
    win = MainWindow(start_lsp=False)
    win.show()
    yield win
    win.close()


def test_window_structure(window):
    menus = [a.text() for a in window.menuBar().actions()]
    assert menus == ['&File', '&Edit', '&View', '&Build']
    assert window.editor is not None
    assert window.problems is not None
    assert window.outline is not None
    assert window.editor.font().fixedPitch() or \
        window.editor.font().family() != ''
    assert 'Ln 1  Col 1' in window._cursor_label.text()
    assert 'Disconnected' in window._lsp_label.text()


def test_open_save_and_dirty(window, tmp_path):
    target = tmp_path / 'doc.ezmath'
    target.write_text('<a> = 1\n', encoding='utf-8')
    window.open_path(str(target))
    assert window._file_path == str(target)
    assert not window.editor.document().isModified()
    window.editor.moveCursor(QtGui.QTextCursor.End)
    window.editor.insertPlainText('// note\n')
    assert window.editor.document().isModified()
    assert window._update_title() is None
    assert window.windowTitle().startswith('*')
    assert window._save() is True
    assert target.read_text(encoding='utf-8') == '<a> = 1\n// note\n'
    assert not window.editor.document().isModified()


def test_problems_navigate_to_range(window):
    window.editor.setPlainText('😀 <oops>\nsecond\n')
    window.problems.set_diagnostics([{
        'line': 0, 'start': 3, 'end': 9,
        'severity': 'error', 'message': 'Undefined variable <oops>'}])
    item = window.problems._list.item(0)
    assert '❌ 1:4' in item.text()
    window.problems._on_item_clicked(item)
    cursor = window.editor.textCursor()
    # UTF-16 native: '<' of <oops> sits at offset 3 (emoji = 2 units);
    # the diagnostic range 3..9 is selected.
    assert cursor.blockNumber() == 0
    assert cursor.anchor() == cursor.block().position() + 3
    assert cursor.position() == cursor.block().position() + 9
    assert cursor.selectedText() == '<oops>'


def test_outline_navigates_to_symbol(window):
    window.editor.setPlainText('<a> = 1\n')
    window.outline.set_symbols([{'name': 'a', 'kind': 'variable',
                                 'line': 0, 'start': 0}])
    window.outline._on_item_clicked(window.outline._list.item(0))
    assert window.editor.textCursor().blockNumber() == 0


def test_goto_position_uses_utf16(window):
    window.editor.setPlainText('😀 <oops>\n')
    window.editor.goto_position(0, 3)
    assert window.editor.textCursor().positionInBlock() == 3


def test_markdown_to_html():
    html = markdown_to_html('**width**\n\nValue: `10`')
    assert '<b>width</b>' in html
    assert '<code>10</code>' in html
    assert '<br>' in html


def test_highlighter_patterns():
    from easy_math_lang.editor import syntax_highlighter as hl
    assert hl.comment_pattern().search('// note')
    assert not hl.comment_pattern().search('<a> = 1')
    assert hl.variable_pattern().search('<width>').group(0) == '<width>'
    assert hl.variable_pattern().search('  < width >').group(0) == '< width >'
    assert not hl.variable_pattern().search('a <-> b')
    assert hl.command_pattern().search('*frac(2 ; 3)').group(0) == '*frac'
    assert hl.number_pattern().search('100 000')
    assert hl.operator_pattern().search('x => y')
    assert hl.operator_pattern().search('a <-> b').group(0) == '<->'


def test_close_kills_running_build(window):
    from unittest import mock
    assert not window.editor.document().isModified()
    fake_build = mock.Mock()
    window._build_process = fake_build
    event = QtGui.QCloseEvent()
    window.closeEvent(event)
    assert event.isAccepted()
    fake_build.kill.assert_called_once_with()


def test_parse_args():
    from easy_math_lang.editor.app import parse_args
    assert parse_args([]).path is None
    assert parse_args(['doc.ezmath']).path == 'doc.ezmath'
    with pytest.raises(SystemExit) as exc:
        parse_args(['--help'])
    assert exc.value.code == 0
    with pytest.raises(SystemExit):
        parse_args(['--nope'])


def test_editor_main_module_import_has_no_side_effects():
    import subprocess
    code = ('import sys;'
            'from PySide6 import QtWidgets;'
            'import easy_math_lang.editor.__main__ as m;'
            'print("import-ok", QtWidgets.QApplication.instance() is None)')
    proc = subprocess.run(
        [sys.executable, '-c', code], capture_output=True, text=True,
        timeout=120, cwd=os.path.join(os.path.dirname(__file__), '..'))
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert 'import-ok True' in proc.stdout


def _pump_until(predicate, what, timeout_ms=20000):
    from PySide6 import QtCore
    loop = QtCore.QEventLoop()
    timer = QtCore.QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(timeout_ms)
    poll = QtCore.QTimer()
    poll.timeout.connect(lambda: predicate() and loop.quit())
    poll.start(25)
    loop.exec()
    poll.stop()
    timer.stop()
    assert predicate(), f'timed out waiting for {what}'


def test_close_waits_for_real_lsp_shutdown(window, qapp):
    """Closing defers until shutdown->exit->termination (real QProcess).

    Regression test: close() used to accept immediately while the LSP
    handshake was still running, so Qt destroyed a live QProcess
    ("QProcess: Destroyed while process ... is still running").
    """
    from PySide6 import QtCore
    qt_warnings = []

    def _handler(mode, context, message):
        if 'Destroyed while process' in message:
            qt_warnings.append(message)

    previous = QtCore.qInstallMessageHandler(_handler)
    try:
        connected = {}
        window.lsp.connected.connect(lambda: connected.update(yes=True))
        window._start_lsp()
        _pump_until(lambda: 'yes' in connected, 'LSP connect')
        assert window.isVisible()

        window.close()
        # Deferred close: window stays up while the handshake runs and
        # the process must still be alive (not yet reaped).
        assert window.isVisible()
        assert window.lsp.state != 'stopped'
        assert window.lsp._process is not None

        # Eventually the handshake completes, the window closes and the
        # process is reaped before anything is destroyed.
        _pump_until(
            lambda: (not window.isVisible()
                     and window.lsp.state == 'stopped'
                     and window.lsp._process is None),
            'deferred close after LSP shutdown')
    finally:
        QtCore.qInstallMessageHandler(previous)
    assert qt_warnings == []
