"""Backslash auto-pair tests (pure + GUI, offscreen)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from editor import auto_pairs  # noqa: E402


def test_should_pair_backslash():
    assert auto_pairs.should_pair_backslash('') is True
    assert auto_pairs.should_pair_backslash(' ') is True
    assert auto_pairs.should_pair_backslash(')') is True
    assert auto_pairs.should_pair_backslash('a') is False
    assert auto_pairs.should_pair_backslash('1') is False
    assert auto_pairs.should_pair_backslash('\\') is False
    assert auto_pairs.should_pair_backslash('(') is False
    assert auto_pairs.should_pair_backslash('"') is False


def test_backslash_pair_and_rollback_helpers():
    assert auto_pairs.is_backslash_pair('\\', '\\') is True
    assert auto_pairs.is_backslash_pair('a', '\\') is False
    assert auto_pairs.is_rollback_char('a') is True
    assert auto_pairs.is_rollback_char('9') is True
    assert auto_pairs.is_rollback_char('(') is True
    assert auto_pairs.is_rollback_char('"') is True
    assert auto_pairs.is_rollback_char(' ') is False
    assert auto_pairs.is_rollback_char(')') is False
    assert auto_pairs.is_rollback_char('\\') is False


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


def _window(qapp):
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    win.show()
    return win


def test_backslash_pairs_and_cursor_between(qapp):
    from PySide6.QtCore import Qt
    win = _window(qapp)
    try:
        _set_text(win, '')
        _press(win.editor, Qt.Key_Backslash, '\\')
        assert win.editor.toPlainText() == '\\\\'
        assert win.editor.textCursor().position() == 1
    finally:
        win.close()


def test_backslash_twice_overtype(qapp):
    from PySide6.QtCore import Qt
    win = _window(qapp)
    try:
        _set_text(win, '')
        _press(win.editor, Qt.Key_Backslash, '\\')
        _press(win.editor, Qt.Key_Backslash, '\\')
        assert win.editor.toPlainText() == '\\\\'
        assert win.editor.textCursor().position() == 2
    finally:
        win.close()


def test_backslash_then_letter_rollback(qapp):
    from PySide6.QtCore import Qt
    win = _window(qapp)
    try:
        _set_text(win, '')
        _press(win.editor, Qt.Key_Backslash, '\\')
        _press(win.editor, Qt.Key_A, 'a')
        assert win.editor.toPlainText() == '\\a'
        assert win.editor.textCursor().position() == 2
        _press(win.editor, Qt.Key_L, 'l')
        assert win.editor.toPlainText() == '\\al'
    finally:
        win.close()


def test_backslash_then_bracket_rollback(qapp):
    from PySide6.QtCore import Qt
    win = _window(qapp)
    try:
        _set_text(win, '')
        _press(win.editor, Qt.Key_Backslash, '\\')
        _press(win.editor, Qt.Key_ParenLeft, '(')
        # Rollback plus escaped-opener rule: single backslash, no closer.
        assert win.editor.toPlainText() == '\\('
        assert win.editor.textCursor().position() == 2
    finally:
        win.close()


def test_backslash_backspace_deletes_both(qapp):
    from PySide6.QtCore import Qt
    win = _window(qapp)
    try:
        _set_text(win, '')
        _press(win.editor, Qt.Key_Backslash, '\\')
        _press(win.editor, Qt.Key_Backspace, '')
        assert win.editor.toPlainText() == ''
    finally:
        win.close()


def test_backslash_before_backslash_no_pair(qapp):
    from PySide6.QtCore import Qt
    win = _window(qapp)
    try:
        _set_text(win, '\\x', cursor_pos=0)
        win.editor.textCursor()
        cursor = win.editor.textCursor()
        cursor.setPosition(0)
        win.editor.setTextCursor(cursor)
        _press(win.editor, Qt.Key_Backslash, '\\')
        assert win.editor.toPlainText() == '\\\\x'
    finally:
        win.close()


def test_backslash_middle_of_word_no_pair(qapp):
    from PySide6.QtCore import Qt
    win = _window(qapp)
    try:
        _set_text(win, 'ab', cursor_pos=1)
        _press(win.editor, Qt.Key_Backslash, '\\')
        assert win.editor.toPlainText() == 'a\\b'
    finally:
        win.close()


def test_backslash_after_existing_pair_no_new_pair(qapp):
    from PySide6.QtCore import Qt
    win = _window(qapp)
    try:
        _set_text(win, '\\\\')
        _press(win.editor, Qt.Key_Backslash, '\\')
        assert win.editor.toPlainText() == '\\\\\\'
        assert win.editor.textCursor().position() == 3
    finally:
        win.close()


def test_backslash_selection_single_insert(qapp):
    from PySide6 import QtGui
    from PySide6.QtCore import Qt
    win = _window(qapp)
    try:
        _set_text(win, 'hello')
        cursor = win.editor.textCursor()
        cursor.setPosition(0)
        cursor.movePosition(QtGui.QTextCursor.Right,
                            QtGui.QTextCursor.KeepAnchor, 5)
        win.editor.setTextCursor(cursor)
        _press(win.editor, Qt.Key_Backslash, '\\')
        # No auto-pair wrap for backslash: single backslash replaces.
        assert win.editor.toPlainText() == '\\'
    finally:
        win.close()


def test_backslash_paste_does_not_pair(qapp):
    win = _window(qapp)
    try:
        _set_text(win, '')
        win.editor.insertPlainText('\\')
        assert win.editor.toPlainText() == '\\'
    finally:
        win.close()


def test_backslash_undo_one_step(qapp):
    from PySide6.QtCore import Qt
    win = _window(qapp)
    try:
        _set_text(win, '')
        _press(win.editor, Qt.Key_Backslash, '\\')
        assert win.editor.toPlainText() == '\\\\'
        win.editor.undo()
        assert win.editor.toPlainText() == ''
        win.editor.redo()
        assert win.editor.toPlainText() == '\\\\'
    finally:
        win.close()


def test_backslash_triple_via_overtype_then_single(qapp):
    from PySide6.QtCore import Qt
    win = _window(qapp)
    try:
        _set_text(win, '')
        for _ in range(3):
            _press(win.editor, Qt.Key_Backslash, '\\')
        assert win.editor.toPlainText() == '\\\\\\'
        assert win.editor.textCursor().position() == 3
    finally:
        win.close()


def test_backslash_ime_vietnamese_not_paired(qapp):
    """Vietnamese diacritic commits must not create a pair."""
    from PySide6.QtCore import Qt
    win = _window(qapp)
    try:
        _set_text(win, 'đã xong')
        for char in ('đ', 'ă', 'ê'):
            _press(win.editor, 0, char)
        assert win.editor.toPlainText() == 'đã xongđăê'
        assert '\\\\' not in win.editor.toPlainText()
    finally:
        win.close()


def test_existing_bracket_escape_rules_unchanged(qapp):
    from PySide6.QtCore import Qt
    win = _window(qapp)
    try:
        _set_text(win, '\\')
        _press(win.editor, Qt.Key_ParenLeft, '(')
        assert win.editor.toPlainText() == '\\('
        _set_text(win, '\\\\')
        _press(win.editor, Qt.Key_ParenLeft, '(')
        assert win.editor.toPlainText() == '\\\\()'
    finally:
        win.close()
