"""Main window: menus, docks, file handling and LSP wiring."""

import html
import re
import sys

from PySide6 import QtCore, QtGui, QtWidgets

from .editor_widget import EditorWidget
from .lsp_client import LspClient, default_server_command
from .outline_panel import OutlinePanel
from .problems_panel import ProblemsPanel

SUPPORTED_SUFFIXES = ('.ezmath', '.eml')

# LSP SymbolKind values occasionally arrive as ints; show readable names.
_SYMBOL_KIND_NAMES = {
    1: 'File', 2: 'Module', 3: 'Namespace', 4: 'Package', 5: 'Class',
    6: 'Method', 7: 'Property', 8: 'Field', 9: 'Constructor', 10: 'Enum',
    11: 'Interface', 12: 'Function', 13: 'Variable', 14: 'Constant',
    15: 'String', 16: 'Number', 17: 'Boolean', 18: 'Array', 19: 'Object',
    20: 'Key', 21: 'Null', 22: 'EnumMember', 23: 'Struct', 24: 'Event',
    25: 'Operator', 26: 'TypeParameter',
}


def markdown_to_html(text):
    """Tiny Markdown subset (bold, code, newlines) for tooltips."""
    escaped = html.escape(text)
    escaped = re.sub(r'\*\*(.+?)\*\*', r'<b>\g<1></b>', escaped)
    escaped = re.sub(r'`(.+?)`', r'<code>\g<1></code>', escaped)
    return escaped.replace('\n', '<br>')


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, start_lsp=True, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Easy-Math-Lang Editor')
        self.resize(1100, 750)

        self._file_path = None
        self._untitled_count = 0
        self._doc_uri = None
        self._doc_version = 0
        self._lsp_open = False  # didOpen acknowledged for current doc
        self._lsp_starting = False  # launch attempted, init not done yet
        self._closing = False  # closeEvent deferred until LSP shutdown done

        self.editor = EditorWidget(self)
        self.setCentralWidget(self.editor)

        self.outline = OutlinePanel(self)
        self._outline_dock = QtWidgets.QDockWidget('Outline', self)
        self._outline_dock.setWidget(self.outline)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self._outline_dock)

        self.problems = ProblemsPanel(self)
        self._problems_dock = QtWidgets.QDockWidget('Problems', self)
        self._problems_dock.setWidget(self.problems)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self._problems_dock)

        self._cursor_label = QtWidgets.QLabel('Ln 1  Col 1', self)
        self._problems_label = QtWidgets.QLabel('', self)
        self._lsp_label = QtWidgets.QLabel('LSP: Disconnected', self)
        self.statusBar().addPermanentWidget(self._cursor_label)
        self.statusBar().addPermanentWidget(self._problems_label)
        self.statusBar().addPermanentWidget(self._lsp_label)

        self._change_timer = QtCore.QTimer(self)
        self._change_timer.setSingleShot(True)
        self._change_timer.setInterval(300)
        self._change_timer.timeout.connect(self._on_change_timeout)

        self._completer = QtWidgets.QCompleter(self)
        self._completer.setWidget(self.editor)
        self._completer.setCompletionMode(
            QtWidgets.QCompleter.PopupCompletion)
        self._completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self._completer.activated[str].connect(self._insert_completion)
        self._completion_model = QtCore.QStringListModel(self._completer)
        self._completer.setModel(self._completion_model)

        self._build_process = None

        self._create_menus()
        self._connect_editor()

        self.lsp = LspClient(default_server_command(), self)
        self.lsp.server_started.connect(self._request_initialize)
        self.lsp.connected.connect(self._on_lsp_connected)
        self.lsp.disconnected.connect(self._on_lsp_disconnected)
        self.lsp.process_error.connect(self._on_lsp_error)
        self.lsp.diagnostics_received.connect(self._on_diagnostics)
        if start_lsp:
            self._start_lsp()

        self._new_document()
        self._update_title()

    # ------------------------------------------------------------------
    # LSP lifecycle
    # ------------------------------------------------------------------
    def _start_lsp(self):
        if self.lsp.is_connected() or self._lsp_starting:
            return
        self._lsp_starting = True
        # start() never blocks; failure arrives via process_error and no
        # server_started signal, which resets the flag below.
        if not self.lsp.start():
            self._lsp_starting = False
            self._set_lsp_status('LSP: Disconnected')

    def _request_initialize(self):
        if self.lsp.is_connected():
            return
        self.lsp.initialize(callback=self._on_initialize)

    def _on_initialize(self, result, error):
        if error is not None:
            self._lsp_starting = False
            self._set_lsp_status('LSP: Disconnected')
            if isinstance(error, dict):
                detail = error.get('message') or repr(error)
            else:
                detail = str(error)
            self.statusBar().showMessage(
                f'LSP initialization failed: {detail}', 8000)
            return
        self._open_current_in_lsp()

    def _on_lsp_connected(self):
        self._lsp_starting = False
        self._set_lsp_status('LSP: Connected')

    def _on_lsp_disconnected(self, _code):
        self._lsp_starting = False
        self._set_lsp_status('LSP: Disconnected')
        self._lsp_open = False
        if self._closing:
            # Deferred close from closeEvent: the server process is gone,
            # so the window may now be destroyed safely.
            self.close()

    def _on_lsp_error(self, message):
        if not self.lsp.is_connected():
            self._lsp_starting = False
        self.statusBar().showMessage(message, 8000)
        sys.stderr.write(f'[easy-math-editor] {message}\n')

    def _set_lsp_status(self, text):
        self._lsp_label.setText(text)

    def _is_lsp_document(self):
        if self._file_path is not None:
            return self._file_path.endswith(SUPPORTED_SUFFIXES)
        return self._doc_uri is not None and \
            self._doc_uri.endswith(SUPPORTED_SUFFIXES)

    def _open_current_in_lsp(self):
        if not self.lsp.is_connected() or not self._is_lsp_document():
            return
        self._doc_version += 1
        self.lsp.did_open(self._doc_uri, 'easymath', self._doc_version,
                          self.editor.toPlainText())
        self._lsp_open = True
        self._request_symbols()

    def _close_current_in_lsp(self):
        if self._lsp_open and self._doc_uri is not None:
            self.lsp.did_close(self._doc_uri)
        self._lsp_open = False

    def _on_change_timeout(self):
        if not self.lsp.is_connected() or not self._lsp_open:
            return
        self._doc_version += 1
        self.lsp.did_change(self._doc_uri, self._doc_version,
                            self.editor.toPlainText())
        self._request_symbols()

    def _request_symbols(self):
        if not self.lsp.is_connected() or not self._lsp_open:
            return
        uri = self._doc_uri

        def _done(result, error):
            if error is not None or not isinstance(result, list):
                return
            symbols = []
            for item in result:
                if not isinstance(item, dict):
                    continue
                loc = item.get('location') or {}
                # Accept DocumentSymbol-style `range` as well as
                # SymbolInformation-style `location.range`.
                rng = item.get('range', loc.get('range') or {})
                start = rng.get('start') or {}
                kind = item.get('kind', '')
                symbols.append({
                    'name': item.get('name', '?'),
                    'kind': _SYMBOL_KIND_NAMES.get(kind, str(kind)),
                    'line': (start.get('line') or 0),
                    'start': (start.get('character') or 0),
                })
            # Ignore stale responses from a previous document.
            if uri == self._doc_uri:
                self.outline.set_symbols(symbols)

        self.lsp.request_symbols(uri, _done)

    def _on_diagnostics(self, uri, diagnostics):
        if uri != self._doc_uri:
            return
        rows = []
        for diag in diagnostics or []:
            rng = diag.get('range') or {}
            start = rng.get('start') or {}
            end = rng.get('end') or {}
            sev = diag.get('severity', 1)
            rows.append({
                'line': start.get('line', 0),
                'start': start.get('character', 0),
                'end': end.get('character', start.get('character', 0)),
                'severity': 'error' if sev == 1 else 'warning',
                'message': diag.get('message', ''),
            })
        self.problems.set_diagnostics(rows)
        count = len(rows)
        self._problems_label.setText(f'Problems: {count}' if count else '')

    # ------------------------------------------------------------------
    # Navigation (LSP positions are UTF-16; QTextCursor is natively UTF-16)
    # ------------------------------------------------------------------
    def _goto(self, line, character):
        self.editor.goto_position(line, character)

    def _goto_range(self, line, start, end):
        block = self.editor.document().findBlockByNumber(max(0, line))
        if not block.isValid():
            return
        length = max(0, block.length() - 1)
        cursor = QtGui.QTextCursor(block)
        cursor.setPosition(block.position() + max(0, min(start, length)))
        cursor.setPosition(block.position() + max(0, min(end, length)),
                           QtGui.QTextCursor.KeepAnchor)
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()
        self.editor.setFocus()

    # ------------------------------------------------------------------
    # Completion + hover
    # ------------------------------------------------------------------
    def _on_completion_requested(self):
        if not self.lsp.is_connected() or not self._lsp_open:
            return
        line, col = self.editor.cursor_line_col()
        uri = self._doc_uri

        def _done(result, error):
            if error is not None or uri != self._doc_uri:
                return
            items = result.get('items') if isinstance(result, dict) else result
            if not isinstance(items, list):
                return
            labels = [i.get('label', '') for i in items
                      if isinstance(i, dict) and i.get('label')]
            if not labels:
                return
            self._completion_model.setStringList(sorted(set(labels)))
            self._completer.setCompletionPrefix(self.editor.word_under_cursor())
            self._completer.complete()

        self.lsp.request_completion(uri, line, col, _done)

    def _insert_completion(self, text):
        cursor = self.editor.textCursor()
        cursor.select(QtGui.QTextCursor.WordUnderCursor)
        cursor.insertText(text)
        self.editor.setTextCursor(cursor)

    def _on_hover_requested(self, global_pos):
        if not self.lsp.is_connected() or not self._lsp_open:
            return
        cursor = self.editor.cursorForPosition(
            self.editor.mapFromGlobal(global_pos))
        if cursor.isNull():
            return
        line, col = cursor.blockNumber(), cursor.positionInBlock()
        uri = self._doc_uri

        def _done(result, error):
            if error is not None or not result or uri != self._doc_uri:
                return
            contents = result.get('contents')
            if isinstance(contents, dict):
                value = contents.get('value', '')
            elif isinstance(contents, list):
                parts = []
                for part in contents:
                    if isinstance(part, dict):
                        parts.append(part.get('value', ''))
                    else:
                        parts.append(str(part))
                value = '\n\n'.join(p for p in parts if p)
            else:
                value = str(contents or '')
            if value:
                QtWidgets.QToolTip.showText(global_pos, markdown_to_html(value),
                                            self.editor)

        self.lsp.request_hover(uri, line, col, _done)

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------
    def _display_name(self):
        if self._file_path:
            return self._file_path.rsplit('/', 1)[-1]
        return 'Untitled'

    def _update_title(self):
        dirty = '*' if self.editor.document().isModified() else ''
        self.setWindowTitle(f'{dirty}{self._display_name()} — Easy-Math-Lang Editor')

    def _doc_uri_for_path(self, path):
        if path is None:
            self._untitled_count += 1
            return f'untitled:///untitled-{self._untitled_count}.ezmath'
        return QtCore.QUrl.fromLocalFile(path).toString()

    def _maybe_save(self):
        if not self.editor.document().isModified():
            return True
        answer = QtWidgets.QMessageBox.question(
            self, 'Unsaved changes',
            f'Save changes to {self._display_name()}?',
            QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard |
            QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Save)
        if answer == QtWidgets.QMessageBox.Save:
            return self._save()
        return answer == QtWidgets.QMessageBox.Discard

    def _switch_document(self, path, text):
        self._close_current_in_lsp()
        self._change_timer.stop()
        self._file_path = path
        self._doc_uri = self._doc_uri_for_path(path)
        self.editor.setPlainText(text)
        self.editor.document().setModified(False)
        self.editor.moveCursor(QtGui.QTextCursor.Start)
        self.problems.clear()
        self.outline.clear()
        self._problems_label.setText('')
        self._open_current_in_lsp()
        self._update_title()

    def _new_document(self):
        if not self._maybe_save():
            return
        self._switch_document(None, '')

    def _open_file(self):
        if not self._maybe_save():
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Open', '',
            'Easy-Math-Lang (*.ezmath *.eml);;All files (*)')
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                text = handle.read()
        except OSError as e:
            QtWidgets.QMessageBox.critical(self, 'Open failed', str(e))
            return
        self._switch_document(path, text)

    def _save(self):
        if self._file_path is None:
            return self._save_as()
        try:
            with open(self._file_path, 'w', encoding='utf-8') as handle:
                handle.write(self.editor.toPlainText())
        except OSError as e:
            QtWidgets.QMessageBox.critical(self, 'Save failed', str(e))
            return False
        self.editor.document().setModified(False)
        self._update_title()
        return True

    def _save_as(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Save As', '',
            'Easy-Math-Lang (*.ezmath *.eml);;All files (*)')
        if not path:
            return False
        try:
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write(self.editor.toPlainText())
        except OSError as e:
            QtWidgets.QMessageBox.critical(self, 'Save failed', str(e))
            return False
        self._switch_document(path, self.editor.toPlainText())
        return True

    # ------------------------------------------------------------------
    # Build: compile current file with the existing compiler CLI logic
    # ------------------------------------------------------------------
    def _compile(self):
        if self.editor.document().isModified():
            answer = QtWidgets.QMessageBox.question(
                self, 'Unsaved changes', 'Save before compiling?',
                QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard |
                QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Save)
            if answer == QtWidgets.QMessageBox.Cancel:
                return
            if answer == QtWidgets.QMessageBox.Save and not self._save():
                return
        if self._file_path is None:
            self.statusBar().showMessage('Save the file before compiling', 5000)
            return
        if self._build_process is not None:
            self.statusBar().showMessage('A build is already running', 5000)
            return
        import sys as _sys
        code = ('import sys; sys.argv = ["easy-math-lang", '
                + repr(self._file_path) +
                ']; from easy_math_lang.compiler.pipeline import main; main()')
        process = QtCore.QProcess(self)
        process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        process.finished.connect(self._on_build_finished)
        process.errorOccurred.connect(self._on_build_error)
        process.start(_sys.executable, ['-c', code])
        self._build_process = process
        self.statusBar().showMessage('Compiling…')

    def _on_build_error(self, error):
        if error == QtCore.QProcess.ProcessError.FailedToStart:
            self._build_process = None
            self.statusBar().showMessage('Could not start compiler', 8000)

    def _on_build_finished(self, exit_code, _status):
        process, self._build_process = self._build_process, None
        output = ''
        if process is not None:
            output = bytes(process.readAllStandardOutput()).decode(
                'utf-8', errors='replace')
            process.deleteLater()
        if exit_code == 0:
            pdf = (self._file_path or '').rsplit('.', 1)[0] + '.pdf'
            self.statusBar().showMessage(f'Compiled to {pdf}', 8000)
        else:
            QtWidgets.QMessageBox.critical(
                self, 'Compilation failed', output.strip()[-2000:] or
                f'Compiler exited with code {exit_code}')

    # ------------------------------------------------------------------
    # Wiring: menus, editor signals, close
    # ------------------------------------------------------------------
    def _create_menus(self):
        file_menu = self.menuBar().addMenu('&File')
        new_action = file_menu.addAction('&New')
        new_action.setShortcut(QtGui.QKeySequence.New)
        new_action.triggered.connect(self._new_document)
        open_action = file_menu.addAction('&Open…')
        open_action.setShortcut(QtGui.QKeySequence.Open)
        open_action.triggered.connect(self._open_file)
        save_action = file_menu.addAction('&Save')
        save_action.setShortcut(QtGui.QKeySequence.Save)
        save_action.triggered.connect(self._save)
        save_as_action = file_menu.addAction('Save &As…')
        save_as_action.setShortcut(QtGui.QKeySequence.SaveAs)
        save_as_action.triggered.connect(self._save_as)
        file_menu.addSeparator()
        exit_action = file_menu.addAction('E&xit')
        exit_action.setShortcut(QtGui.QKeySequence.Quit)
        exit_action.triggered.connect(self.close)

        edit_menu = self.menuBar().addMenu('&Edit')
        undo_action = edit_menu.addAction('&Undo')
        undo_action.setShortcut(QtGui.QKeySequence.Undo)
        undo_action.triggered.connect(self.editor.undo)
        redo_action = edit_menu.addAction('&Redo')
        redo_action.setShortcut(QtGui.QKeySequence.Redo)
        redo_action.triggered.connect(self.editor.redo)
        edit_menu.addSeparator()
        cut_action = edit_menu.addAction('Cu&t')
        cut_action.setShortcut(QtGui.QKeySequence.Cut)
        cut_action.triggered.connect(self.editor.cut)
        copy_action = edit_menu.addAction('&Copy')
        copy_action.setShortcut(QtGui.QKeySequence.Copy)
        copy_action.triggered.connect(self.editor.copy)
        paste_action = edit_menu.addAction('&Paste')
        paste_action.setShortcut(QtGui.QKeySequence.Paste)
        paste_action.triggered.connect(self.editor.paste)
        edit_menu.addSeparator()
        select_all_action = edit_menu.addAction('Select &All')
        select_all_action.setShortcut(QtGui.QKeySequence.SelectAll)
        select_all_action.triggered.connect(self.editor.selectAll)

        view_menu = self.menuBar().addMenu('&View')
        view_menu.addAction(self._outline_dock.toggleViewAction())
        view_menu.addAction(self._problems_dock.toggleViewAction())

        build_menu = self.menuBar().addMenu('&Build')
        compile_action = build_menu.addAction('&Compile')
        compile_action.setShortcut('Ctrl+B')
        compile_action.triggered.connect(self._compile)

    def _connect_editor(self):
        self.editor.cursorMoved.connect(self._on_cursor_moved)
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.document().modificationChanged.connect(self._update_title)
        self.editor.completionRequested.connect(self._on_completion_requested)
        self.editor.hoverRequested.connect(self._on_hover_requested)
        self.problems.diagnosticActivated.connect(self._goto_range)
        self.outline.symbolActivated.connect(self._goto)

    def _on_cursor_moved(self, line, col):
        self._cursor_label.setText(f'Ln {line + 1}  Col {col + 1}')

    def _on_text_changed(self):
        if self.lsp.is_connected() and self._lsp_open:
            self._change_timer.start()

    def open_path(self, path):
        """Open a file (used for a launch argument)."""
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                text = handle.read()
        except OSError as e:
            QtWidgets.QMessageBox.critical(self, 'Open failed', str(e))
            return
        self._switch_document(path, text)

    def closeEvent(self, event):
        if self._closing:
            # Second pass: shutdown completed (or was forced).
            event.accept()
            return
        if not self._maybe_save():
            event.ignore()
            return
        self._change_timer.stop()
        self._close_current_in_lsp()
        if self._build_process is not None:
            self._build_process.kill()
            self._build_process = None
        if self.lsp.state == 'stopped':
            event.accept()
            return
        # The LSP shutdown handshake (shutdown -> response -> exit ->
        # process exit) is asynchronous: defer the close until the process
        # is gone so Qt never destroys a live QProcess.  A watchdog
        # forces the close if shutdown hangs.
        self._closing = True
        self.statusBar().showMessage('Shutting down language server…')
        QtCore.QTimer.singleShot(5000, self._force_close)
        self.lsp.stop()
        event.ignore()

    def _force_close(self):
        """Last-resort close when LSP shutdown hangs."""
        if not self._closing:
            return
        self.lsp.abort()
        self.close()
