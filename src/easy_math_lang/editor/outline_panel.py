"""Outline panel: document symbols with click-to-navigate."""

from PySide6 import QtCore, QtWidgets


class OutlinePanel(QtWidgets.QWidget):
    """Lists document symbols; click moves the cursor to the symbol."""

    symbolActivated = QtCore.Signal(int, int)  # line, start char

    def __init__(self, parent=None):
        super().__init__(parent)
        self._symbols = []
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._list = QtWidgets.QListWidget(self)
        layout.addWidget(self._list)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.itemActivated.connect(self._on_item_clicked)

    def set_symbols(self, symbols):
        """Replace rows. Each symbol is a dict with name/kind/line/start."""
        self._symbols = list(symbols or [])
        self._list.clear()
        for symbol in self._symbols:
            label = f"{symbol.get('name', '?')}  [{symbol.get('kind', '')}]"
            item = QtWidgets.QListWidgetItem(label, self._list)
            item.setData(QtCore.Qt.UserRole, (symbol.get('line', 0),
                                              symbol.get('start', 0)))

    def clear(self):
        self.set_symbols([])

    def _on_item_clicked(self, item):
        line, start = item.data(QtCore.Qt.UserRole) or (0, 0)
        self.symbolActivated.emit(line, start)
