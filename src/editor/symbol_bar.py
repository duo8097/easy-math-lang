"""Horizontal Smart Symbol Palette toolbar for Easy Math Lang."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from .symbol_registry import list_categories, list_symbols, symbols_in_category


class SymbolBar(QtWidgets.QWidget):
    """Compact horizontal symbol bar with a category filter.

    Emits ``symbolChosen(str)`` with the internal symbol name; the host
    window (MainWindow) owns insertion + dialogs so this widget stays
    purely presentational and easy to test offscreen.
    """

    symbolChosen = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._symbols = list_symbols()

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        self._category = QtWidgets.QComboBox(self)
        self._category.setToolTip('Filter symbols by category')
        self._category.addItem('All')
        for cat in list_categories():
            self._category.addItem(cat)
        self._category.currentTextChanged.connect(self._rebuild)
        layout.addWidget(self._category)

        self._scroll = QtWidgets.QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        # Compact single-row height; still readable on high-DPI (layout
        # scales, no fixed pixel fonts).
        self._scroll.setMaximumHeight(40)
        layout.addWidget(self._scroll, 1)

        self._container = QtWidgets.QWidget(self._scroll)
        self._buttons_layout = QtWidgets.QHBoxLayout(self._container)
        self._buttons_layout.setContentsMargins(0, 0, 0, 0)
        self._buttons_layout.setSpacing(2)
        self._scroll.setWidget(self._container)

        self._rebuild('All')
        self.setToolTip('Easy Math Lang symbols — click to insert at the cursor')

    @property
    def categoryCombo(self):
        return self._category

    def visible_symbols(self) -> list:
        return symbols_in_category(self._category.currentText())

    def _clear_buttons(self):
        while self._buttons_layout.count():
            item = self._buttons_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _rebuild(self, _category: str = 'All'):
        self._clear_buttons()
        for sym in symbols_in_category(self._category.currentText()):
            btn = QtWidgets.QToolButton(self._container)
            btn.setText(sym.display)
            btn.setToolTip(sym.tooltip)
            btn.setStatusTip(sym.tooltip)
            btn.setAccessibleName(f'{sym.display} {sym.syntax}')
            btn.setAccessibleDescription(f'{sym.description} ({sym.category})')
            btn.setAutoRaise(True)
            btn.setFocusPolicy(QtCore.Qt.StrongFocus)
            # Keep buttons compact but touchable; sizeHint still scales
            # with DPI/font.
            btn.setMinimumHeight(26)
            btn.setProperty('symbol-name', sym.name)
            btn.clicked.connect(
                lambda _checked=False, n=sym.name: self.symbolChosen.emit(n))
            self._buttons_layout.addWidget(btn)
        spacer = QtWidgets.QWidget(self._container)
        spacer.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                             QtWidgets.QSizePolicy.Preferred)
        self._buttons_layout.addWidget(spacer)

    def button_for(self, name: str):
        """Return the QToolButton for *name*, or None."""
        for i in range(self._buttons_layout.count()):
            w = self._buttons_layout.itemAt(i).widget()
            if w is not None and w.property('symbol-name') == name:
                return w
        return None
