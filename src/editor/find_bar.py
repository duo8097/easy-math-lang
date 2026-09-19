"""Minimal VS Code-style find bar (Ctrl+F): next/previous, Esc closes."""

from PySide6 import QtCore, QtWidgets


class FindBar(QtWidgets.QWidget):
    """Thin search strip. Search itself lives in MainWindow."""

    findRequested = QtCore.Signal(str, int)  # (text, direction +1/-1)
    closed = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)

        self._input = QtWidgets.QLineEdit(self)
        self._input.setPlaceholderText('Find')
        self._input.setClearButtonEnabled(True)
        layout.addWidget(self._input, 1)

        self._count = QtWidgets.QLabel('', self)
        layout.addWidget(self._count)

        prev_button = QtWidgets.QPushButton('↑', self)
        prev_button.setFlat(True)
        prev_button.setToolTip('Previous match (Shift+F3)')
        prev_button.clicked.connect(lambda: self._emit(-1))
        layout.addWidget(prev_button)

        next_button = QtWidgets.QPushButton('↓', self)
        next_button.setFlat(True)
        next_button.setToolTip('Next match (F3 / Enter)')
        next_button.clicked.connect(lambda: self._emit(1))
        layout.addWidget(next_button)

        close_button = QtWidgets.QPushButton('✕', self)
        close_button.setFlat(True)
        close_button.setToolTip('Close (Esc)')
        close_button.clicked.connect(self.hide_bar)
        layout.addWidget(close_button)

        self._input.textChanged.connect(lambda: self._emit(0))
        self._input.returnPressed.connect(lambda: self._emit(1))
        self.setVisible(False)

    def show_bar(self, initial_text=''):
        if initial_text and not self._input.text():
            self._input.setText(initial_text)
        self.setVisible(True)
        self._input.setFocus()
        self._input.selectAll()

    def hide_bar(self):
        self.setVisible(False)
        self.closed.emit()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.hide_bar()
            event.accept()
            return
        super().keyPressEvent(event)

    def set_match_count(self, index, total):
        """Update the 'i of n' label (either may be 0)."""
        self._count.setText(f'{index} of {total}' if total else '0 of 0')

    def _emit(self, direction):
        self.findRequested.emit(self._input.text(), direction)
