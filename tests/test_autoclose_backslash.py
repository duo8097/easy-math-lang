"""Backslash-aware auto-close tests (pure + GUI, offscreen)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from editor import auto_pairs  # noqa: E402


def test_count_preceding_backslashes():
    assert auto_pairs.count_preceding_backslashes('') == 0
    assert auto_pairs.count_preceding_backslashes('a') == 0
    assert auto_pairs.count_preceding_backslashes('\\') == 1
    assert auto_pairs.count_preceding_backslashes('\\\\') == 2
    assert auto_pairs.count_preceding_backslashes('a\\\\') == 2
    assert auto_pairs.count_preceding_backslashes('\\\\\\') == 3
    assert auto_pairs.count_preceding_backslashes('a\\b') == 0


def test_is_escaped_odd_even():
    assert auto_pairs.is_escaped('\\') is True
    assert auto_pairs.is_escaped('\\\\') is False
    assert auto_pairs.is_escaped('\\\\\\') is True
    assert auto_pairs.is_escaped('x') is False
    assert auto_pairs.is_escaped('') is False


def test_escaped_closer_and_pair_ahead():
    assert auto_pairs.escaped_closer('(') == '\\)'
    assert auto_pairs.escaped_closer('[') == '\\]'
    assert auto_pairs.escaped_closer('{') == '\\}'
    assert auto_pairs.escaped_closer('"') == '\\"'
    assert auto_pairs.escaped_closer('\\') is None
    assert auto_pairs.escaped_pair_ahead('\\)') == ')'
    assert auto_pairs.escaped_pair_ahead(')') is None
    assert auto_pairs.escaped_pair_ahead('\\x') is None
    assert auto_pairs.matching_escaped_pair('(', '\\)') == ')'
    assert auto_pairs.matching_escaped_pair('(', ')') is None
    assert auto_pairs.matching_escaped_pair('[', '\\)') is None


def _press(widget, key, text):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    widget.keyPressEvent(QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier, text))


def _set_text(window, text, cursor_pos=None):
    from PySide6 import QtGui
    window.editor.setPlainText(text)
    cursor = window.editor.textCursor()
    cursor.movePosition(QtGui.QTextCursor.End)
    if cursor_pos is not None:
        cursor.setPosition(cursor_pos)
    window.editor.setTextCursor(cursor)


def test_backslash_alone_inserts_pair(qapp):
    from PySide6.QtCore import Qt
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        _set_text(win, '')
        _press(win.editor, Qt.Key_Backslash, '\\')
        assert win.editor.toPlainText() == '\\\\'
        assert win.editor.textCursor().position() == 1
    finally:
        win.close()


def test_escaped_opener_inserts_no_closer(qapp):
    from PySide6.QtCore import Qt
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        _set_text(win, '\\')
        _press(win.editor, Qt.Key_ParenLeft, '(')
        assert win.editor.toPlainText() == '\\('
        assert win.editor.textCursor().position() == 2
    finally:
        win.close()


def test_double_backslash_opener_auto_closes(qapp):
    from PySide6.QtCore import Qt
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        # ``\\`` is a literal backslash, so ( is not escaped.
        _set_text(win, '\\\\')
        _press(win.editor, Qt.Key_ParenLeft, '(')
        assert win.editor.toPlainText() == '\\\\()'
        assert win.editor.textCursor().position() == 3
    finally:
        win.close()


def test_triple_backslash_opener_is_escaped(qapp):
    from PySide6.QtCore import Qt
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        _set_text(win, '\\\\\\')
        _press(win.editor, Qt.Key_ParenLeft, '(')
        assert win.editor.toPlainText() == '\\\\\\('
    finally:
        win.close()


def test_escaped_quote_no_pair(qapp):
    from PySide6.QtCore import Qt
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        _set_text(win, '\\')
        _press(win.editor, Qt.Key_QuoteLeft, '"')
        assert win.editor.toPlainText() == '\\"'
    finally:
        win.close()


def test_escaped_selection_wrap_no_closer(qapp):
    from PySide6 import QtGui
    from PySide6.QtCore import Qt
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        _set_text(win, '\\hello')
        cursor = win.editor.textCursor()
        cursor.setPosition(1)
        cursor.movePosition(QtGui.QTextCursor.Right,
                            QtGui.QTextCursor.KeepAnchor, 5)
        win.editor.setTextCursor(cursor)
        _press(win.editor, Qt.Key_ParenLeft, '(')
        assert win.editor.toPlainText() == '\\(hello'
        assert win.editor.textCursor().selectedText() == 'hello'
    finally:
        win.close()


def test_overtype_escaped_closer_skips_both(qapp):
    from PySide6.QtCore import Qt
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        _set_text(win, '(' + chr(92) + ')', cursor_pos=1)
        _press(win.editor, Qt.Key_ParenRight, ')')
        # Cursor stepped over both '\' and ')'.
        assert win.editor.toPlainText() == '(' + chr(92) + ')'
        assert win.editor.textCursor().position() == 3
    finally:
        win.close()


def test_backspace_deletes_escaped_pair(qapp):
    from PySide6.QtCore import Qt
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        _set_text(win, '(' + chr(92) + ')', cursor_pos=1)
        _press(win.editor, Qt.Key_Backspace, '')
        assert win.editor.toPlainText() == ''
    finally:
        win.close()


def test_backspace_between_backslash_and_closer(qapp):
    from PySide6.QtCore import Qt
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        _set_text(win, '(' + chr(92) + ')', cursor_pos=2)
        _press(win.editor, Qt.Key_Backspace, '')
        assert win.editor.toPlainText() == ''
    finally:
        win.close()


def test_enter_expands_escaped_pair(qapp):
    from PySide6.QtCore import Qt
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        _set_text(win, '(' + chr(92) + ')', cursor_pos=1)
        _press(win.editor, Qt.Key_Return, '')
        lines = win.editor.toPlainText().split('\n')
        assert lines[0] == '('
        assert lines[2] == '\\)'
        assert len(lines) == 3
    finally:
        win.close()


def test_escaped_opener_undo_one_step(qapp):
    from PySide6.QtCore import Qt
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        _set_text(win, '\\')
        win.editor.document().setModified(False)
        _press(win.editor, Qt.Key_ParenLeft, '(')
        assert win.editor.toPlainText() == '\\('
        win.editor.undo()
        assert win.editor.toPlainText() == '\\'
    finally:
        win.close()


def test_plain_pair_undo_still_one_step(qapp):
    from PySide6.QtCore import Qt
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        _set_text(win, '')
        _press(win.editor, Qt.Key_ParenLeft, '(')
        assert win.editor.toPlainText() == '()'
        win.editor.undo()
        assert win.editor.toPlainText() == ''
    finally:
        win.close()


def test_vietnamese_ime_text_does_not_pair(qapp):
    """Vietnamese diacritic commits (single-char events) never pair."""
    from PySide6.QtCore import Qt
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        _set_text(win, 'đã xong')
        for char in ('đ', 'ă', 'ê'):
            _press(win.editor, 0, char)
        assert win.editor.toPlainText() == 'đã xongđăê'
        assert '()' not in win.editor.toPlainText()
    finally:
        win.close()
