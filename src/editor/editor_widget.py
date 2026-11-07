"""Central text editor: monospace QPlainTextEdit with line numbers."""

from PySide6 import QtCore, QtGui, QtWidgets

from . import auto_pairs
from .positions import utf16_units
from .syntax_highlighter import EmlHighlighter


class _LineNumberArea(QtWidgets.QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        return QtCore.QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self._editor.line_number_area_paint_event(event)


class EditorWidget(QtWidgets.QPlainTextEdit):
    """QPlainTextEdit tuned for `.ezmath` editing.

    Emits ``cursorMoved(line, column)`` (0-based, UTF-16 columns, matching
    LSP), ``completionRequested()`` on Ctrl+Space, and ``hoverRequested``
    with the global mouse position after the pointer rests on text.
    """

    cursorMoved = QtCore.Signal(int, int)
    completionRequested = QtCore.Signal()
    hoverRequested = QtCore.Signal(QtCore.QPoint)

    HOVER_DELAY_MS = 600
    COMPLETION_TRIGGERS = ('*', '<')
    
    _auto_close_brackets = True

    def __init__(self, parent=None):
        super().__init__(parent)
        font = QtGui.QFontDatabase.systemFont(
            QtGui.QFontDatabase.FixedFont)
        self.setFont(font)
        self.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        self.setMouseTracking(True)
        self.setTabStopDistance(
            4 * self.fontMetrics().horizontalAdvance(' '))
        self.setPlaceholderText(
            'Start typing Easy-Math-Lang here…\n'
            '\n'
            '<width> = 5\n'
            '<area> = calc(<width> * 2)\n'
            'Area: <area>\n'
            '\n'
            'Tip: File → Open → examples/example.ezmath')

        self._line_numbers = _LineNumberArea(self)
        self._highlighter = EmlHighlighter(self.document())
        self._theme = 'light'
        self._theme_colors = None
        self.set_theme('light')

        self._hover_timer = QtCore.QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(self.HOVER_DELAY_MS)
        self._hover_timer.timeout.connect(self._on_hover_timeout)
        self._hover_pos = None

        self.blockCountChanged.connect(self._update_line_number_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._emit_cursor_moved)
        self._update_line_number_width(0)
        self._highlight_current_line()
        self.cursorPositionChanged.connect(self._highlight_current_line)

        self._completion_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence('Ctrl+Space'), self)
        self._completion_shortcut.setContext(
            QtCore.Qt.WidgetWithChildrenShortcut)
        self._completion_shortcut.activated.connect(
            self.completionRequested.emit)

    def set_theme(self, theme):
        """Apply a light/dark color set (see :mod:`editor.theme`)."""
        from .theme import editor_colors, normalize
        theme = normalize(theme)
        self._theme = theme
        self._theme_colors = editor_colors(theme)
        bg = self._theme_colors['editor_bg']
        fg = self._theme_colors['editor_fg']
        # 1) Widget palette (standard mechanism).
        palette = self.palette()
        palette.setColor(QtGui.QPalette.Base, QtGui.QColor(bg))
        palette.setColor(QtGui.QPalette.Text, QtGui.QColor(fg))
        self.setPalette(palette)
        # 2) Viewport palette: the viewport paints the text background and
        # does not always follow the parent widget palette on every style.
        viewport_palette = self.viewport().palette()
        viewport_palette.setColor(QtGui.QPalette.Base, QtGui.QColor(bg))
        viewport_palette.setColor(QtGui.QPalette.Text, QtGui.QColor(fg))
        self.viewport().setPalette(viewport_palette)
        # 3) Widget stylesheet as the final authority: stylesheets beat
        # palettes at paint time on every QStyle, so the editor background
        # cannot get stuck on either theme. It must be set explicitly in
        # BOTH directions — clearing it with '' leaves a stale
        # stylesheet-resolved palette that swallows later setPalette calls.
        self.setStyleSheet(
            f'QPlainTextEdit {{ background-color: {bg}; color: {fg}; }}'
        )
        self._highlighter.set_theme(theme)
        self._line_numbers.update()
        self._highlight_current_line(refresh=True)
        self.viewport().update()
        self.update()

    @property
    def theme(self):
        return self._theme

    # ------------------------------------------------------------------
    # Cursor position (0-based line, UTF-16 column — same units as LSP)
    # ------------------------------------------------------------------
    def cursor_line_col(self):
        cursor = self.textCursor()
        return cursor.blockNumber(), cursor.positionInBlock()

    def _emit_cursor_moved(self):
        line, col = self.cursor_line_col()
        self.cursorMoved.emit(line, col)

    def keyPressEvent(self, event):  # noqa: C901
        # IME composition must never be touched (Telex/VNI, fcitx5/ibus, CJK IMEs).
        # Programmatic edits never arrive here, so this is a pure key-event path.
        modifiers = event.modifiers()
        has_shortcut_modifier = bool(
            modifiers & (
                QtCore.Qt.KeyboardModifier.ControlModifier
                | QtCore.Qt.KeyboardModifier.AltModifier
                | QtCore.Qt.KeyboardModifier.MetaModifier))

        auto_on = getattr(self, '_auto_close_brackets', True)
        text = event.text()

        if auto_on and not has_shortcut_modifier and len(text) == 1:
            # ---- Openers: insert pair / wrap selection --------------------
            if text in auto_pairs.OPENERS_FOR:
                if self._handle_opener(text):
                    return
            # ---- Closers: overtype ----------------------------------------
            elif text in auto_pairs.CLOSERS:
                if self._handle_closer(text):
                    return

        # ---- Backspace: delete empty pair in one stroke -------------------
        if (auto_on and not has_shortcut_modifier
                and event.key() == QtCore.Qt.Key.Key_Backspace
                and self._handle_backspace()):
            return

        # ---- Enter: expand empty pair to three lines ----------------------
        if (auto_on and not has_shortcut_modifier
                and (event.key() == QtCore.Qt.Key.Key_Return
                     or event.key() == QtCore.Qt.Key.Key_Enter)
                and self._handle_enter()):
            return

        super().keyPressEvent(event)

        # Auto-show autocompletion right after a trigger character, like
        # Ctrl+Space but without asking. Programmatic edits (completion
        # insertion, paste handling) never produce key events, so this
        # cannot loop back on itself.
        if text in self.COMPLETION_TRIGGERS and not has_shortcut_modifier:
            self.completionRequested.emit()

    # -- auto-close helpers (each returns True when the event is consumed) --

    def _char_at_offset(self, offset):
        """Character at document offset ('' when out of range)."""
        doc = self.document()
        try:
            if offset < 0 or offset >= doc.characterCount():
                return ''
            ch = doc.characterAt(int(offset))
        except (TypeError, ValueError):
            return ''
        return '' if not ch or ch == '\x00' else ch

    def _handle_opener(self, char):
        cursor = self.textCursor()
        closer = auto_pairs.OPENERS_FOR.get(char)
        if closer is None:
            return False

        # Selection: wrap it, keep it selected (UTF-16 offsets use Qt cursor).
        if cursor.hasSelection():
            selected = cursor.selectedText()
            start, end = cursor.selectionStart(), cursor.selectionEnd()
            cursor.beginEditBlock()
            try:
                cursor.insertText(char + selected + closer)
                cursor.setPosition(start + utf16_units(char))
                cursor.setPosition(end + utf16_units(char),
                                   QtGui.QTextCursor.KeepAnchor)
            finally:
                cursor.endEditBlock()
            self.setTextCursor(cursor)
            self.ensureCursorVisible()
            return True

        # No selection: respect next-char / prev-char rules.
        pos = cursor.position()
        next_ch = self._char_at_offset(pos)
        prev_ch = self._char_at_offset(pos - 1)
        if not auto_pairs.should_pair(char, next_ch, prev_ch):
            return False

        cursor.beginEditBlock()
        try:
            cursor.insertText(char + closer)
            # Cursor should sit between opener and closer.
            cursor.setPosition(pos + utf16_units(char))
        finally:
            cursor.endEditBlock()
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
        return True

    def _handle_closer(self, char):
        cursor = self.textCursor()
        pos = cursor.position()
        next_ch = self._char_at_offset(pos)
        if not auto_pairs.should_overtype(char, next_ch):
            return False
        cursor.movePosition(QtGui.QTextCursor.NextCharacter)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
        return True

    def _handle_backspace(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            return False
        pos = cursor.position()
        prev_ch = self._char_at_offset(pos - 1)
        next_ch = self._char_at_offset(pos)
        if not auto_pairs.matching_pair(prev_ch, next_ch):
            return False
        cursor.beginEditBlock()
        try:
            cursor.deletePreviousChar()
            cursor.deleteChar()
        finally:
            cursor.endEditBlock()
        self.setTextCursor(cursor)
        return True

    def _handle_enter(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            return False
        pos = cursor.position()
        prev_ch = self._char_at_offset(pos - 1)
        next_ch = self._char_at_offset(pos)
        closer = auto_pairs.matching_pair(prev_ch, next_ch)
        if not closer:
            return False
        block = cursor.block()
        # Refuse to expand across a line break or with content between
        # opener and closer: the pair must be the whole block content.
        if prev_ch not in auto_pairs.OPENERS_FOR or \
                auto_pairs.OPENERS_FOR.get(prev_ch) != closer:
            return False
        block_text = block.text()
        if cursor.positionInBlock() not in (utf16_units(prev_ch), 1) \
                or block_text.strip() != f'{prev_ch}{closer}':
            # Still allow simple cases where the block is exactly the pair
            if block_text.strip() != f'{prev_ch}{closer}':
                return False

        cursor.beginEditBlock()
        try:
            start = block.position()
            # Split the block at the cursor (positionInBlock is UTF-16).
            pos_in_block = cursor.positionInBlock()
            # For ASCII blocks the UTF-16 index is also the Python index;
            # for non-ASCII use the positions helper for correctness.
            try:
                from .positions import to_code_point_offset

                cp_pos = to_code_point_offset(block_text, pos_in_block)
            except Exception:
                cp_pos = pos_in_block
            line_before = block_text[:cp_pos]
            line_after = block_text[cp_pos:]
            # Delete the whole block and re-insert three lines.
            cursor.setPosition(start)
            cursor.movePosition(
                QtGui.QTextCursor.NextCharacter,
                QtGui.QTextCursor.KeepAnchor,
                utf16_units(block_text))
            opener_line, _middle, closer_line = auto_pairs.expansion_lines(
                line_before, line_after)
            cursor.insertText(opener_line + '\n' + _middle + '\n' + closer_line)
            cursor.setPosition(start + utf16_units(opener_line) + 1
                               + utf16_units(_middle))
        finally:
            cursor.endEditBlock()
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
        return True

    def goto_position(self, line, character):
        """Move the cursor; character is a UTF-16 offset like LSP sends."""
        block = self.document().findBlockByNumber(max(0, line))
        if not block.isValid():
            block = self.document().lastBlock()
        pos = block.position() + max(0, min(character, block.length() - 1))
        cursor = QtGui.QTextCursor(block)
        cursor.setPosition(pos)
        self.setTextCursor(cursor)
        self.centerCursor()

    def word_under_cursor(self):
        cursor = self.textCursor()
        cursor.select(QtGui.QTextCursor.WordUnderCursor)
        return cursor.selectedText()

    # ------------------------------------------------------------------
    # Line numbers + current line
    # ------------------------------------------------------------------
    def line_number_area_width(self):
        digits = len(str(max(1, self.blockCount())))
        return 8 + self.fontMetrics().horizontalAdvance('9') * digits

    def _update_line_number_width(self, _count):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect, dy):
        if dy:
            self._line_numbers.scroll(0, dy)
        else:
            self._line_numbers.update(
                0, rect.y(), self._line_numbers.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_number_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        rect = self.contentsRect()
        self._line_numbers.setGeometry(
            QtCore.QRect(rect.left(), rect.top(),
                         self.line_number_area_width(), rect.height()))

    def line_number_area_paint_event(self, event):
        from .theme import editor_colors
        colors = self._theme_colors or editor_colors('light')
        painter = QtGui.QPainter(self._line_numbers)
        painter.fillRect(event.rect(), QtGui.QColor(colors['line_bg']))
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(
            self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(QtGui.QColor(colors['line_fg']))
                painter.drawText(0, int(top),
                                 self._line_numbers.width() - 4,
                                 self.fontMetrics().height(),
                                 QtCore.Qt.AlignRight, str(block_number + 1))
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    def _highlight_current_line(self, refresh=False):
        from .theme import editor_colors
        colors = self._theme_colors or editor_colors('light')
        line_color = QtGui.QColor(colors['current_line'])
        # The current-line marker is the only FullWidthSelection, so it
        # is found (and replaced on theme switches) regardless of color.
        others = [s for s in self.extraSelections()
                  if not s.format.property(
                      QtGui.QTextFormat.FullWidthSelection)]
        selection = QtWidgets.QTextEdit.ExtraSelection()
        selection.format.setBackground(line_color)
        selection.format.setProperty(QtGui.QTextFormat.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self.setExtraSelections(others + [selection])

    # ------------------------------------------------------------------
    # Hover detection (resting mouse triggers a tooltip request)
    # ------------------------------------------------------------------
    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self._hover_pos = event.globalPosition().toPoint()
        self._hover_timer.start()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._hover_timer.stop()
        self._hover_pos = None
        try:
            QtWidgets.QToolTip.hideText()
        except (RuntimeError, AttributeError):
            pass

    def _on_hover_timeout(self):
        if self._hover_pos is not None:
            self.hoverRequested.emit(self._hover_pos)
