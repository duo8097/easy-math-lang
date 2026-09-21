"""Main window: menus, docks, file handling and LSP wiring."""

import html
import os
import re
import sys

from PySide6 import QtCore, QtGui, QtWidgets

from .command_palette import CommandPalette
from .editor_widget import EditorWidget
from .find_bar import FindBar
from .lsp_client import LspClient, default_server_command
from .outline_panel import OutlinePanel
from .problems_panel import ProblemsPanel
from .recent import RecentFiles, default_settings

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
    def __init__(self, start_lsp=True, parent=None, no_save_prompt=False):
        super().__init__(parent)
        self.setWindowTitle('Easy-Math-Lang Editor')
        self.resize(1100, 750)
        self._no_save_prompt = no_save_prompt

        self._file_path = None
        self._untitled_count = 0
        self._doc_uri = None
        self._doc_version = 0
        self._lsp_open = False  # didOpen acknowledged for current doc
        self._lsp_starting = False  # launch attempted, init not done yet
        self._closing = False  # closeEvent deferred until LSP shutdown done
        self._restart_pending = False  # restart once the old server exits
        self._reopen_after_connect = False  # re-didOpen after a restart

        self.editor = EditorWidget(self)
        self._default_font_size = self.editor.font().pointSizeF() or 12.0

        self._find_bar = FindBar()
        self._find_bar.findRequested.connect(self._on_find_requested)
        central = QtWidgets.QWidget(self)
        central_layout = QtWidgets.QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self._find_bar)
        central_layout.addWidget(self.editor, 1)
        self.setCentralWidget(central)

        self.outline = OutlinePanel(self)
        self._outline_dock = QtWidgets.QDockWidget('Outline', self)
        self._outline_dock.setWidget(self.outline)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self._outline_dock)

        self.problems = ProblemsPanel(self)
        self._problems_dock = QtWidgets.QDockWidget('Problems', self)
        self._problems_dock.setWidget(self.problems)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self._problems_dock)

        self._cursor_label = QtWidgets.QLabel('Ln 1  Col 1', self)
        self._problems_button = QtWidgets.QPushButton('', self)
        self._problems_button.setFlat(True)
        self._problems_button.setCursor(QtCore.Qt.PointingHandCursor)
        self._problems_button.setToolTip('Show Problems panel')
        self._problems_button.clicked.connect(self._focus_problems)
        self._lsp_label = QtWidgets.QLabel('LSP: Disconnected', self)
        self.statusBar().addPermanentWidget(self._cursor_label)
        self.statusBar().addPermanentWidget(self._problems_button)
        self.statusBar().addPermanentWidget(self._lsp_label)

        self._recent = RecentFiles(default_settings())

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
        self._completer.highlighted[str].connect(self._show_completion_detail)
        self._completion_model = QtCore.QStringListModel(self._completer)
        self._completer.setModel(self._completion_model)
        self._completion_info = {}  # label -> (kind_name, detail)

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
            # Reset the client out of its stuck 'starting' state so a
            # later _start_lsp() actually launches a new process.
            try:
                self.lsp.abort()
            except Exception:
                pass
            self._set_lsp_status('LSP: Disconnected')
            if isinstance(error, dict):
                detail = error.get('message') or repr(error)
            else:
                detail = str(error)
            self.statusBar().showMessage(
                f'LSP initialization failed: {detail}', 8000)
            return
        if not self._lsp_open:
            # A restart already reopened the document from _on_lsp_connected.
            self._open_current_in_lsp()

    def _on_lsp_connected(self):
        self._lsp_starting = False
        self._set_lsp_status('LSP: Connected')
        if self._reopen_after_connect:
            self._reopen_after_connect = False
            self._open_current_in_lsp()

    def _restart_lsp(self):
        """Restart the server (e.g. after a crash); reopens the document."""
        if self._restart_pending or self._closing:
            return
        if self.lsp.state == 'stopped':
            self._start_lsp()
            return
        self._restart_pending = True
        self._close_current_in_lsp()
        self.statusBar().showMessage('Restarting language server…', 3000)
        self.lsp.stop()

    def _on_lsp_disconnected(self, _code):
        self._lsp_starting = False
        self._set_lsp_status('LSP: Disconnected')
        self._lsp_open = False
        if self._closing:
            # Deferred close from closeEvent: the server process is gone,
            # so the window may now be destroyed safely.
            self.close()
            return
        if self._restart_pending:
            self._restart_pending = False
            self._reopen_after_connect = True
            self._start_lsp()

    def _on_lsp_error(self, message):
        if not self.lsp.is_connected():
            self._lsp_starting = False
            # A FailedToStart while state=='starting' would otherwise
            # deadlock future restarts (start() early-returns True).
            if self.lsp.state == 'starting':
                try:
                    self.lsp.abort()
                except Exception:
                    pass
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
        version = self._doc_version

        def _done(result, error):
            if error is not None or not isinstance(result, list):
                return
            symbols = []
            for item in result:
                if not isinstance(item, dict):
                    continue
                loc = item.get('location')
                if not isinstance(loc, dict):
                    loc = {}
                # Accept DocumentSymbol-style `range` as well as
                # SymbolInformation-style `location.range`.
                rng = item.get('range') or loc.get('range') or {}
                if not isinstance(rng, dict):
                    rng = {}
                start = rng.get('start') or {}
                if not isinstance(start, dict):
                    start = {}
                kind = item.get('kind', '')
                try:
                    line = int(start.get('line', 0))
                except (TypeError, ValueError):
                    line = 0
                try:
                    char = int(start.get('character', 0))
                except (TypeError, ValueError):
                    char = 0
                symbols.append({
                    'name': item.get('name', '?') if isinstance(item.get('name'), str) else '?',
                    'kind': _SYMBOL_KIND_NAMES.get(kind, str(kind)),
                    'line': line,
                    'start': char,
                })
            # Ignore stale responses from a previous document or version.
            if uri == self._doc_uri and version == self._doc_version:
                self.outline.set_symbols(symbols)

        self.lsp.request_symbols(uri, _done)

    def _on_diagnostics(self, uri, diagnostics, version=None):
        if uri != self._doc_uri:
            return
        # Drop stale diagnostics from an older document version.
        if version is not None:
            try:
                if int(version) < int(self._doc_version):
                    return
            except (TypeError, ValueError):
                pass
        if not isinstance(diagnostics, list):
            diagnostics = []
        rows = []
        for diag in diagnostics:
            if not isinstance(diag, dict):
                continue
            rng = diag.get('range')
            if not isinstance(rng, dict):
                rng = {}
            start = rng.get('start')
            if not isinstance(start, dict):
                start = {}
            end = rng.get('end')
            if not isinstance(end, dict):
                end = {}
            sev = diag.get('severity', 1)
            try:
                line = int(start.get('line', 0))
            except (TypeError, ValueError):
                line = 0
            try:
                s_char = int(start.get('character', 0))
            except (TypeError, ValueError):
                s_char = 0
            try:
                e_char = int(end.get('character', s_char))
            except (TypeError, ValueError):
                e_char = s_char
            msg = diag.get('message', '')
            if not isinstance(msg, str):
                msg = str(msg)
            rows.append({
                'line': line,
                'start': s_char,
                'end': e_char,
                'severity': 'error' if sev == 1 else 'warning',
                'message': msg,
            })
        self.problems.set_diagnostics(rows)
        count = len(rows)
        self._problems_button.setText(f'Problems: {count}' if count else '')

    # ------------------------------------------------------------------
    # Navigation (LSP positions are UTF-16; QTextCursor is natively UTF-16)
    # ------------------------------------------------------------------
    def _goto(self, line, character):
        try:
            line, character = int(line), int(character)
        except (TypeError, ValueError):
            return
        self.editor.goto_position(line, character)

    def _goto_range(self, line, start, end):
        try:
            line, start, end = int(line), int(start), int(end)
        except (TypeError, ValueError):
            return
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
    # LSP CompletionItemKind values we care about (the rest need no
    # argument handling).
    _COMPLETION_KIND_NAMES = {3: 'function', 14: 'keyword',
                              6: 'variable', 21: 'constant'}

    def _on_completion_requested(self):
        if not self.lsp.is_connected() or not self._lsp_open:
            return
        line, col = self.editor.cursor_line_col()
        uri = self._doc_uri
        version = self._doc_version
        self.lsp.request_completion(
            uri, line, col,
            lambda result, error: self._handle_completion_response(
                uri, result, error, version=version))

    def _handle_completion_response(self, uri, result, error, version=None):
        if error is not None or uri != self._doc_uri:
            return
        if version is not None and version != self._doc_version:
            return
        items = result.get('items') if isinstance(result, dict) else result
        if not isinstance(items, list):
            return
        info = {}
        for item in items:
            if not isinstance(item, dict) or not item.get('label'):
                continue
            kind = self._COMPLETION_KIND_NAMES.get(item.get('kind'), '')
            info[item['label']] = (kind, item.get('detail', ''))
        if not info:
            return
        self._completion_info = info
        self._completion_model.setStringList(sorted(info))
        self._completer.setCompletionPrefix(self.editor.word_under_cursor())
        self._completer.complete()

    def _show_completion_detail(self, text):
        """Show the highlighted candidate's signature in the status bar."""
        _kind, detail = self._completion_info.get(text, ('', ''))
        if detail:
            self.statusBar().showMessage(detail)

    def _char_after(self, pos):
        """Document character at absolute offset ('' when out of range)."""
        text = self.editor.toPlainText()
        return text[pos] if 0 <= pos < len(text) else ''

    def _insert_completion(self, text):
        kind, detail = self._completion_info.get(text, ('', ''))
        cursor = self.editor.textCursor()
        cursor.select(QtGui.QTextCursor.WordUnderCursor)
        start, end = cursor.selectionStart(), cursor.selectionEnd()
        if text.startswith('*') and start > 0 \
                and self._char_after(start - 1) == '*':
            # Swallow the trigger '*' the user already typed so '*pi'
            # does not become '**pi'.
            start -= 1
        add_parens = (kind in ('function', 'keyword')
                      and '(' in (detail or '')
                      and self._char_after(end) != '('
                      and not (start == end
                               and self._char_after(start - 1) == '('))
        cursor.setPosition(start)
        cursor.setPosition(end, QtGui.QTextCursor.KeepAnchor)
        cursor.insertText(text + ('()' if add_parens else ''))
        if add_parens:
            # Leave the cursor inside the parens, ready for arguments.
            cursor.setPosition(cursor.position() - 1)
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
        version = self._doc_version

        def _done(result, error):
            if error is not None or not result or uri != self._doc_uri or version != self._doc_version:
                return
            if not isinstance(result, dict):
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
    # Friendly extras: palette, find, go-to-line, recent files
    # ------------------------------------------------------------------
    _FIND_ALL_COLOR = QtGui.QColor('#ffe082')
    _FIND_CURRENT_COLOR = QtGui.QColor('#ffab40')
    _MAX_FIND_MATCHES = 1000

    def _focus_problems(self):
        self._problems_dock.show()
        self._problems_dock.raise_()

    def _palette_commands(self):
        toggle_outline = self._outline_dock.toggleViewAction()
        toggle_problems = self._problems_dock.toggleViewAction()
        return [
            ('file.new', 'File: New', '', self._new_document),
            ('file.open', 'File: Open…', 'Ctrl+O', self._open_file),
            ('file.save', 'File: Save', 'Ctrl+S', lambda: self._save()),
            ('file.saveAs', 'File: Save As…', '', lambda: self._save_as()),
            ('file.exit', 'File: Exit', '', self.close),
            ('edit.find', 'Find in File…', 'Ctrl+F', self._toggle_find),
            ('edit.gotoLine', 'Go to Line…', 'Ctrl+G', self._go_to_line),
            ('view.toggleOutline', 'View: Toggle Outline', '',
             toggle_outline.trigger),
            ('view.toggleProblems', 'View: Toggle Problems', '',
             toggle_problems.trigger),
            ('view.zoomIn', 'View: Zoom In', 'Ctrl+=',
             lambda: self._zoom(1)),
            ('view.zoomOut', 'View: Zoom Out', 'Ctrl+-',
             lambda: self._zoom(-1)),
            ('view.zoomReset', 'View: Reset Zoom', 'Ctrl+0',
             self._zoom_reset),
            ('build.compile', 'Build: Compile to PDF', 'Ctrl+B',
             self._compile),
            ('build.restartLSP', 'Build: Restart Language Server', '',
             self._restart_lsp),
        ]

    def _show_palette(self):
        dialog = CommandPalette(self)
        dialog.set_commands(
            [(cmd_id, title, hint)
             for cmd_id, title, hint, _ in self._palette_commands()])
        dialog.commandChosen.connect(self._run_palette_command)
        dialog.exec()

    def _run_palette_command(self, cmd_id):
        for item_id, _title, _hint, action in self._palette_commands():
            if item_id == cmd_id:
                action()
                return

    def _toggle_find(self):
        if self._find_bar.isVisible():
            self._find_bar.hide_bar()
            self.editor.setFocus()
            return
        selected = self.editor.textCursor().selectedText()
        self._find_bar.show_bar(selected or self.editor.word_under_cursor())

    def _find_again(self, direction):
        if not self._find_bar.isVisible():
            self._toggle_find()
            return
        self._do_find(self._find_bar._input.text(), direction)

    def _on_find_requested(self, text, direction):
        self._do_find(text, direction)

    def _find_all_ranges(self, text):
        """Absolute (start, end) offsets of every case-insensitive match."""
        if not text:
            return []
        import re as _re
        doc = self.editor.toPlainText()
        ranges = []
        for m in _re.finditer(_re.escape(text), doc, flags=_re.IGNORECASE):
            ranges.append((m.start(), m.end()))
            if len(ranges) >= self._MAX_FIND_MATCHES:
                break
        return ranges

    def _do_find(self, text, direction):
        self._clear_find_highlights()
        ranges = self._find_all_ranges(text)
        self._find_ranges = ranges
        if not ranges:
            self._find_bar.set_match_count(0, 0)
            return
        pos = self.editor.textCursor().position()
        inside = next((i for i, (s, e) in enumerate(ranges) if s <= pos < e), None)
        if direction == 0:
            index = inside if inside is not None else next(
                (i for i, (s, _e) in enumerate(ranges) if s >= pos), 0)
        elif direction > 0:
            if inside is not None:
                # Cursor inside a match: advance to the next one
                # (previously stayed on the same match).
                index = (inside + 1) % len(ranges)
            else:
                at_or_before = [i for i, (_s, e) in enumerate(ranges) if e <= pos]
                index = 0 if not at_or_before else (at_or_before[-1] + 1) % len(ranges)
        else:
            if inside is not None:
                index = (inside - 1) % len(ranges)
                # When the cursor sits inside a match, at_or_before
                # excludes it, so the generic formula would skip one.
            else:
                at_or_before = [i for i, (_s, e) in enumerate(ranges) if e <= pos]
                index = len(ranges) - 1 if not at_or_before else (at_or_before[-1] - 1) % len(ranges)
                # NOTE: after _show_find_match the cursor sits at the end
                # of the shown match (e == pos), so at_or_before includes
                # the current match and -1 steps to the previous one,
                # which is what the Prev button expects.
        self._show_find_match(index)

    def _show_find_match(self, index):
        ranges = self._find_ranges
        self._highlight_find_ranges(ranges, index)
        self._find_bar.set_match_count(index + 1, len(ranges))
        start, end = ranges[index]
        cursor = self.editor.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QtGui.QTextCursor.KeepAnchor)
        self.editor.setTextCursor(cursor)

    def _highlight_find_ranges(self, ranges, current):
        document = self.editor.document()
        selections = []
        for i, (start, end) in enumerate(ranges):
            selection = QtWidgets.QTextEdit.ExtraSelection()
            color = self._FIND_CURRENT_COLOR if i == current \
                else self._FIND_ALL_COLOR
            selection.format.setBackground(color)
            cursor = QtGui.QTextCursor(document)
            cursor.setPosition(start)
            cursor.setPosition(end, QtGui.QTextCursor.KeepAnchor)
            selection.cursor = cursor
            selections.append(selection)
        self.editor.setExtraSelections(
            self._current_extra_selections() + selections)

    def _current_extra_selections(self):
        """Selections not owned by find (e.g. the current-line highlight)."""
        keep = []
        for selection in self.editor.extraSelections():
            background = selection.format.background()
            if background != self._FIND_ALL_COLOR \
                    and background != self._FIND_CURRENT_COLOR:
                keep.append(selection)
        return keep

    def _clear_find_highlights(self):
        self.editor.setExtraSelections(self._current_extra_selections())

    def _go_to_line(self):
        current = self.editor.textCursor().blockNumber() + 1
        total = max(1, self.editor.blockCount())
        line, ok = QtWidgets.QInputDialog.getInt(
            self, 'Go to Line', f'Line number (1–{total}):',
            current, 1, total, 1)
        if ok:
            self._goto(line - 1, 0)
            self.editor.setFocus()

    def _refresh_recent_menu(self):
        self._recent_menu.clear()
        paths = [p for p in self._recent.list() if p]
        if not paths:
            empty = self._recent_menu.addAction('(No recent files)')
            empty.setEnabled(False)
            return
        for path in paths:
            if not os.path.exists(path):
                continue
            action = self._recent_menu.addAction(
                os.path.basename(path) or path)
            action.setStatusTip(path)
            action.setData(path)
            action.triggered.connect(
                lambda _checked=False, p=path: self._open_recent(p))
        self._recent_menu.addSeparator()
        clear_action = self._recent_menu.addAction('Clear Menu')
        clear_action.triggered.connect(self._recent.clear)

    def _open_recent(self, path):
        if not os.path.exists(path):
            self.statusBar().showMessage(f'File not found: {path}', 5000)
            return
        if not self._maybe_save():
            return
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                text = handle.read()
        except OSError as e:
            QtWidgets.QMessageBox.critical(self, 'Open failed', str(e))
            return
        self._recent.add(path)
        self._switch_document(path, text)

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------
    def _display_name(self):
        if self._file_path:
            return os.path.basename(self._file_path) or self._file_path
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
        if self._no_save_prompt:
            return True
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
        self._problems_button.setText('')
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
        self._recent.add(path)
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
        self._recent.add(path)
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
                ']; from compiler.pipeline import main; main()')
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
            pdf_base, _ = os.path.splitext(self._file_path or '')
            pdf = pdf_base + '.pdf' if pdf_base else '.pdf'
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
        new_action.setStatusTip('Start a new document')
        new_action.triggered.connect(self._new_document)
        open_action = file_menu.addAction('&Open…')
        open_action.setShortcut(QtGui.QKeySequence.Open)
        open_action.setStatusTip('Open an existing .ezmath file')
        open_action.triggered.connect(self._open_file)
        self._recent_menu = file_menu.addMenu('Open R&ecent')
        file_menu.aboutToShow.connect(self._refresh_recent_menu)
        save_action = file_menu.addAction('&Save')
        save_action.setShortcut(QtGui.QKeySequence.Save)
        save_action.setStatusTip('Save the current document')
        save_action.triggered.connect(self._save)
        save_as_action = file_menu.addAction('Save &As…')
        save_as_action.setShortcut(QtGui.QKeySequence.SaveAs)
        save_as_action.setStatusTip('Save under a new name')
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
        edit_menu.addSeparator()
        find_action = edit_menu.addAction('&Find…')
        find_action.setShortcut('Ctrl+F')
        find_action.setStatusTip('Find text in the document')
        find_action.triggered.connect(self._toggle_find)
        goto_action = edit_menu.addAction('Go to &Line…')
        goto_action.setShortcut('Ctrl+G')
        goto_action.setStatusTip('Jump to a line number')
        goto_action.triggered.connect(self._go_to_line)

        view_menu = self.menuBar().addMenu('&View')
        view_menu.addAction(self._outline_dock.toggleViewAction())
        view_menu.addAction(self._problems_dock.toggleViewAction())
        view_menu.addSeparator()
        palette_action = view_menu.addAction('Command &Palette…')
        palette_action.setShortcut('Ctrl+Shift+P')
        palette_action.setStatusTip('Run any command by name')
        palette_action.triggered.connect(self._show_palette)
        view_menu.addSeparator()
        zoom_in_action = view_menu.addAction('Zoom &In')
        zoom_in_action.setShortcuts(['Ctrl+=', 'Ctrl++'])
        zoom_in_action.setStatusTip('Make the editor text bigger')
        zoom_in_action.triggered.connect(lambda: self._zoom(1))
        zoom_out_action = view_menu.addAction('Zoom &Out')
        zoom_out_action.setShortcut('Ctrl+-')
        zoom_out_action.setStatusTip('Make the editor text smaller')
        zoom_out_action.triggered.connect(lambda: self._zoom(-1))
        zoom_reset_action = view_menu.addAction('&Reset Zoom')
        zoom_reset_action.setShortcut('Ctrl+0')
        zoom_reset_action.setStatusTip('Restore the default text size')
        zoom_reset_action.triggered.connect(self._zoom_reset)

        build_menu = self.menuBar().addMenu('&Build')
        compile_action = build_menu.addAction('&Compile')
        compile_action.setShortcut('Ctrl+B')
        compile_action.setStatusTip('Compile the document to PDF')
        compile_action.triggered.connect(self._compile)
        build_menu.addSeparator()
        restart_action = build_menu.addAction('&Restart Language Server')
        restart_action.setStatusTip(
            'Restart the language server (fixes stale errors)')
        restart_action.triggered.connect(self._restart_lsp)

        toolbar = self.addToolBar('Main Toolbar')
        toolbar.addAction(new_action)
        toolbar.addAction(open_action)
        toolbar.addAction(save_action)
        toolbar.addSeparator()
        toolbar.addAction(compile_action)

        find_next_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence.StandardKey.FindNext, self)
        find_next_shortcut.activated.connect(lambda: self._find_again(1))
        find_prev_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence.StandardKey.FindPrevious, self)
        find_prev_shortcut.activated.connect(lambda: self._find_again(-1))

    # ------------------------------------------------------------------
    # Editor text size
    # ------------------------------------------------------------------
    _MIN_FONT_SIZE = 6.0
    _MAX_FONT_SIZE = 48.0

    def _set_editor_font_size(self, size):
        clamped = max(self._MIN_FONT_SIZE, min(self._MAX_FONT_SIZE, size))
        font = self.editor.font()
        font.setPointSizeF(clamped)
        self.editor.setFont(font)

    def _zoom(self, step):
        self._set_editor_font_size(self.editor.font().pointSizeF() + step)

    def _zoom_reset(self):
        self._set_editor_font_size(self._default_font_size)

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
        self._recent.add(path)
        self._switch_document(path, text)

    def closeEvent(self, event):
        if self._closing:
            # Second pass: shutdown completed (or was forced).
            event.accept()
            return
        if not self._maybe_save():
            event.ignore()
            return
        self._restart_pending = False
        self._reopen_after_connect = False
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
        try:
            self.lsp.abort()
        except RuntimeError:
            pass  # Qt objects already destroyed during teardown
        try:
            self.close()
        except RuntimeError:
            pass
