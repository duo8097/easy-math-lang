"""Offscreen GUI smoke tests (no display, no LSP process)."""

import os

import pytest

PySide6 = pytest.importorskip('PySide6')

import sys  # noqa: E402

from PySide6 import QtGui, QtWidgets  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from editor.main_window import (  # noqa: E402
    MainWindow,
    markdown_to_html,
)


@pytest.fixture()
def window(qapp):
    # no_save_prompt: tests must never block on the modal save dialog.
    win = MainWindow(start_lsp=False, no_save_prompt=True)
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
    from editor import syntax_highlighter as hl
    assert hl.comment_pattern().search('// note')
    assert not hl.comment_pattern().search('<a> = 1')
    assert hl.variable_pattern().search('<width>').group(0) == '<width>'
    assert hl.variable_pattern().search('  < width >').group(0) == '< width >'
    assert not hl.variable_pattern().search('a <-> b')
    assert hl.command_pattern().search('*frac(2 ; 3)').group(0) == '*frac'
    assert hl.number_pattern().search('100 000')
    assert hl.operator_pattern().search('x => y')
    assert hl.operator_pattern().search('a <-> b').group(0) == '<->'
    assert hl.operator_pattern().search('a << b').group(0) == '<<'
    assert hl.operator_pattern().search('a === b').group(0) == '==='
    assert hl.operator_pattern().search('a <== b').group(0) == '<=='


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
    from editor.app import parse_args
    assert parse_args([]).path is None
    assert parse_args(['doc.ezmath']).path == 'doc.ezmath'
    assert parse_args([]).no_save_prompt is False
    assert parse_args(['--no-save-prompt']).no_save_prompt is True
    with pytest.raises(SystemExit) as exc:
        parse_args(['--help'])
    assert exc.value.code == 0
    with pytest.raises(SystemExit):
        parse_args(['--nope'])


def test_no_save_prompt_closes_dirty_doc_without_dialog(qapp):
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        win.editor.moveCursor(QtGui.QTextCursor.End)
        win.editor.insertPlainText('<a> = undefined-symbol\n')
        assert win.editor.document().isModified()
        assert win._maybe_save() is True
        event = QtGui.QCloseEvent()
        win.closeEvent(event)
        assert event.isAccepted()
    finally:
        win.close()


def test_save_prompt_asked_by_default_but_skipped_with_flag(qapp, monkeypatch):
    calls = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, 'question',
        lambda *a, **k: calls.append(True) or QtWidgets.QMessageBox.Discard,
    )
    plain = MainWindow(start_lsp=False)
    try:
        plain.show()
        plain.editor.insertPlainText('dirty\n')
        assert plain._maybe_save() is True
        assert calls, 'expected the save dialog without the flag'
    finally:
        plain.close()
    calls.clear()
    flagged = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        flagged.show()
        flagged.editor.insertPlainText('dirty\n')
        assert flagged._maybe_save() is True
        assert not calls, 'no save dialog expected with the flag'
    finally:
        flagged.close()


def test_editor_main_module_import_has_no_side_effects():
    import subprocess
    code = ('import sys;'
            'from PySide6 import QtWidgets;'
            'import editor.__main__ as m;'
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


def test_fuzzy_score():
    from editor.command_palette import fuzzy_score
    assert fuzzy_score('', 'Anything') == 0
    assert fuzzy_score('fop', 'File: Open…') is not None
    assert fuzzy_score('xyz', 'File: Open…') is None
    assert fuzzy_score('file', 'File: Open') < fuzzy_score('file', 'XfXiXlXe')
    assert fuzzy_score('FILE', 'file: save') is not None


def test_command_palette_filters_and_chooses(window, qapp):
    from editor.command_palette import CommandPalette
    chosen = {}
    dialog = CommandPalette(window)
    dialog.commandChosen.connect(lambda cmd_id: chosen.setdefault('id', cmd_id))
    dialog.set_commands([
        ('file.open', 'File: Open…', 'Ctrl+O'),
        ('file.save', 'File: Save', 'Ctrl+S'),
        ('build.compile', 'Build: Compile to PDF', 'Ctrl+B'),
    ])
    assert dialog._list.count() == 3
    dialog._input.setText('comp')
    assert dialog._list.count() == 1
    dialog._accept_current()
    assert chosen == {'id': 'build.compile'}


def test_recent_files_roundtrip(tmp_path, qapp):
    from PySide6 import QtCore
    from editor.recent import RecentFiles
    settings = QtCore.QSettings(str(tmp_path / 'recent.ini'),
                                QtCore.QSettings.IniFormat)
    recent = RecentFiles(settings, max_items=3)
    assert recent.list() == []
    recent.add('/a.ezmath')
    recent.add('/b.ezmath')
    recent.add('/a.ezmath')  # duplicate moves to front, no copy
    recent.add('/c.ezmath')
    recent.add('/d.ezmath')  # over capacity trims oldest
    assert recent.list() == ['/d.ezmath', '/c.ezmath', '/a.ezmath']
    assert RecentFiles(settings, max_items=3).list() == recent.list()  # persisted
    recent.clear()
    assert recent.list() == []


def test_find_next_prev_and_count(window):
    window.editor.setPlainText('foo bar foo\nfoo\n')
    window.editor.moveCursor(QtGui.QTextCursor.Start)
    window._do_find('foo', 0)
    cursor = window.editor.textCursor()
    assert (cursor.selectionStart(), cursor.selectionEnd()) == (0, 3)
    assert window._find_bar._count.text() == '1 of 3'
    window._do_find('foo', 1)
    cursor = window.editor.textCursor()
    assert (cursor.selectionStart(), cursor.selectionEnd()) == (8, 11)
    assert window._find_bar._count.text() == '2 of 3'
    window._do_find('foo', -1)
    cursor = window.editor.textCursor()
    assert (cursor.selectionStart(), cursor.selectionEnd()) == (0, 3)
    assert window._find_bar._count.text() == '1 of 3'
    window._do_find('', 0)
    assert window._find_bar._count.text() == '0 of 0'
    window._do_find('zzz', 0)
    assert window._find_bar._count.text() == '0 of 0'


def test_find_bar_toggle_prefills_word(window):
    window.editor.setPlainText('<width> = 5\n')
    window.editor.moveCursor(QtGui.QTextCursor.Start)
    window.editor.moveCursor(QtGui.QTextCursor.Right,
                             QtGui.QTextCursor.KeepAnchor)
    window._toggle_find()
    assert window._find_bar.isVisible()
    assert window._find_bar._input.text() != ''
    window._toggle_find()
    assert not window._find_bar.isVisible()


def test_go_to_line(window, monkeypatch):
    window.editor.setPlainText('a\nb\nc\n')
    monkeypatch.setattr(QtWidgets.QInputDialog, 'getInt',
                        lambda *a, **k: (2, True))
    window._go_to_line()
    assert window.editor.textCursor().blockNumber() == 1


def test_problems_button_focuses_panel(window):
    window._doc_uri = 'file:///t.ezmath'
    window._on_diagnostics('file:///t.ezmath', [{
        'range': {'start': {'line': 0, 'character': 0},
                  'end': {'line': 0, 'character': 1}},
        'severity': 1, 'message': 'boom'}])
    assert 'Problems: 1' in window._problems_button.text()
    window._problems_dock.hide()
    window._problems_button.click()
    assert window._problems_dock.isVisible()


def test_recent_menu_lists_files(window, tmp_path, qapp):
    from PySide6 import QtCore
    from editor.recent import RecentFiles
    window._recent = RecentFiles(
        QtCore.QSettings(str(tmp_path / 'r.ini'), QtCore.QSettings.IniFormat))
    target = tmp_path / 'notes.ezmath'
    target.write_text('<a> = 1\n', encoding='utf-8')
    window._recent.add(str(target))
    window._recent.add(str(tmp_path / 'gone.ezmath'))  # missing: hidden
    window._refresh_recent_menu()
    texts = [a.text() for a in window._recent_menu.actions() if a.isEnabled()]
    assert 'notes.ezmath' in texts
    assert not any('gone' in t for t in texts)


def test_toolbar_has_main_actions(window):
    toolbars = window.findChildren(QtWidgets.QToolBar)
    assert len(toolbars) == 1
    texts = [a.text() for a in toolbars[0].actions() if a.text()]
    for expected in ('&New', '&Open…', '&Save', '&Compile'):
        assert expected in texts


def test_zoom_in_out_reset_and_clamp(window):
    original = window.editor.font().pointSizeF()
    window._zoom(1)
    assert window.editor.font().pointSizeF() == original + 1
    window._zoom(-1)
    assert window.editor.font().pointSizeF() == original
    for _ in range(100):
        window._zoom(1)
    assert window.editor.font().pointSizeF() == 48.0
    for _ in range(100):
        window._zoom(-1)
    assert window.editor.font().pointSizeF() == 6.0
    window._zoom_reset()
    assert window.editor.font().pointSizeF() == original


def test_placeholder_guides_new_users(window):
    placeholder = window.editor.placeholderText()
    assert placeholder != ''
    assert 'example.ezmath' in placeholder


def test_tab_width_is_four_spaces(window):
    expected = 4 * window.editor.fontMetrics().horizontalAdvance(' ')
    assert window.editor.tabStopDistance() == expected


def test_restart_lsp_reconnects_and_reopens(window, qapp):
    connects = {}
    window.lsp.connected.connect(
        lambda: connects.update(n=connects.get('n', 0) + 1))
    window._restart_lsp()  # stopped -> starts directly
    _pump_until(lambda: connects.get('n', 0) >= 1, 'first LSP connect')
    assert 'Connected' in window._lsp_label.text()
    assert window._lsp_open  # untitled .ezmath doc was (re)opened

    window._restart_lsp()  # connected -> stop, then start on disconnect
    _pump_until(lambda: connects.get('n', 0) >= 2, 'second LSP connect')
    assert 'Connected' in window._lsp_label.text()
    assert window._lsp_open

    window.lsp.stop()
    _pump_until(lambda: window.lsp.state == 'stopped', 'final LSP stop')


def _press_key(widget, key, text, modifiers=None):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    mods = Qt.NoModifier if modifiers is None else modifiers
    widget.keyPressEvent(QKeyEvent(QEvent.KeyPress, key, mods, text))


def test_star_keypress_requests_completion(window):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtCore import QEvent
    requested = []
    window.editor.completionRequested.connect(lambda: requested.append(1))
    _press_key(window.editor, Qt.Key_Asterisk, '*')
    assert window.editor.toPlainText() == '*'
    assert len(requested) == 1


def test_less_than_keypress_requests_completion(window):
    from PySide6.QtCore import Qt
    requested = []
    window.editor.completionRequested.connect(lambda: requested.append(1))
    _press_key(window.editor, Qt.Key_Less, '<')
    assert window.editor.toPlainText() == '<'
    assert len(requested) == 1


def test_plain_keypress_does_not_request_completion(window):
    from PySide6.QtCore import Qt
    requested = []
    window.editor.completionRequested.connect(lambda: requested.append(1))
    _press_key(window.editor, Qt.Key_A, 'a')
    assert window.editor.toPlainText() == 'a'
    assert requested == []


def test_ctrl_star_does_not_request_completion(window):
    from PySide6.QtCore import Qt
    requested = []
    window.editor.completionRequested.connect(lambda: requested.append(1))
    _press_key(window.editor, Qt.Key_Asterisk, '*', Qt.ControlModifier)
    assert requested == []


def test_completion_response_stores_details(window):
    result = {'items': [
        {'label': 'frac', 'kind': 3, 'detail': '*frac(numerator ; denominator)'},
        {'label': 'width', 'kind': 6, 'detail': '= 10'},
        {'label': 'pi', 'kind': 21, 'detail': ''},
        {'no-label': True},
    ]}
    window._handle_completion_response(window._doc_uri, result, None)
    assert window._completion_info == {
        'frac': ('function', '*frac(numerator ; denominator)'),
        'width': ('variable', '= 10'),
        'pi': ('constant', ''),
    }
    assert sorted(window._completion_model.stringList()) == ['frac', 'pi', 'width']


def test_completion_response_ignores_stale_or_bad(window):
    window._completion_info = {'old': ('variable', '')}
    window._handle_completion_response('file:///other.ezmath', {'items': []}, None)
    assert window._completion_info == {'old': ('variable', '')}
    window._handle_completion_response(window._doc_uri, {'items': None}, None)
    assert window._completion_info == {'old': ('variable', '')}
    window._handle_completion_response(window._doc_uri, {'items': []}, 'boom')
    assert window._completion_info == {'old': ('variable', '')}


def test_insert_function_adds_parens_with_cursor_inside(window):
    window._completion_info = {'frac': ('function', '*frac(numerator ; denominator)')}
    window.editor.setPlainText('*fr')
    window.editor.moveCursor(QtGui.QTextCursor.End)
    window._insert_completion('frac')
    assert window.editor.toPlainText() == '*frac()'
    assert window.editor.textCursor().position() == len('*frac(')


def test_insert_variable_has_no_parens(window):
    window._completion_info = {'width': ('variable', '= calc(2 + 3)')}
    window.editor.setPlainText('<wid')
    window.editor.moveCursor(QtGui.QTextCursor.End)
    window._insert_completion('width')
    assert window.editor.toPlainText() == '<width'


def test_insert_starred_label_swallows_trigger_star(window):
    window._completion_info = {}
    window.editor.setPlainText('*')
    window.editor.moveCursor(QtGui.QTextCursor.End)
    window._insert_completion('*pi')
    assert window.editor.toPlainText() == '*pi'


def test_insert_does_not_duplicate_open_paren(window):
    window._completion_info = {'frac': ('function', '*frac(numerator ; denominator)')}
    window.editor.setPlainText('*frac(')
    window.editor.moveCursor(QtGui.QTextCursor.End)
    window._insert_completion('frac')
    assert window.editor.toPlainText() == '*frac(frac'


def test_show_completion_detail_in_status_bar(window):
    window._completion_info = {'frac': ('function', '*frac(numerator ; denominator)')}
    window._show_completion_detail('frac')
    assert '*frac(numerator ; denominator)' in window.statusBar().currentMessage()
    window._show_completion_detail('unknown-label')  # no crash, message kept


def test_programmatic_insert_does_not_retrigger_completion(window):
    requested = []
    window.editor.completionRequested.connect(lambda: requested.append(1))
    window._completion_info = {'frac': ('function', '*frac(a ; b)')}
    window.editor.setPlainText('*fr')
    window.editor.moveCursor(QtGui.QTextCursor.End)
    window._insert_completion('frac')
    assert requested == []
