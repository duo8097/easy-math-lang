"""Central text editor: monospace QPlainTextEdit with line numbers."""

from PySide6 import QtCore, QtGui, QtWidgets

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
        palette = self.palette()
        palette.setColor(QtGui.QPalette.Base,
                         QtGui.QColor(self._theme_colors['editor_bg']))
        palette.setColor(QtGui.QPalette.Text,
                         QtGui.QColor(self._theme_colors['editor_fg']))
        self.setPalette(palette)
        self._highlighter.set_theme(theme)
        self._line_numbers.update()
        self._highlight_current_line(refresh=True)

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

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        # Auto-show autocompletion right after a trigger character, like
        # Ctrl+Space but without asking. Programmatic edits (completion
        # insertion, paste handling) never produce key events, so this
        # cannot loop back on itself.
        modifiers = event.modifiers() & (
            QtCore.Qt.KeyboardModifier.ControlModifier
            | QtCore.Qt.KeyboardModifier.AltModifier
            | QtCore.Qt.KeyboardModifier.MetaModifier)
        if event.text() in self.COMPLETION_TRIGGERS and not modifiers:
            self.completionRequested.emit()

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

    def _on_hover_timeout(self):
        if self._hover_pos is not None:
            self.hoverRequested.emit(self._hover_pos)
