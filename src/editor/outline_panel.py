"""Outline panel: document symbols with click-to-navigate."""

from PySide6 import QtCore, QtWidgets

from . import i18n


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
            kind = symbol.get('kind', '')
            # Symbol kinds are LSP identifiers; their display names
            # are translated, the identifiers themselves stay English.
            translator = i18n.current_translator()
            kind_text = (translator.tr(f'kind.{kind}')
                         if kind and translator.has(f'kind.{kind}')
                         else str(kind))
            label = f"{symbol.get('name', '?')}  [{kind_text}]"
            item = QtWidgets.QListWidgetItem(label, self._list)
            item.setData(QtCore.Qt.UserRole, (symbol.get('line', 0),
                                              symbol.get('start', 0)))

    def clear(self):
        self.set_symbols([])

    def _on_item_clicked(self, item):
        data = item.data(QtCore.Qt.UserRole)
        try:
            line, start = (tuple(data) if isinstance(data, (list, tuple)) else (None, None))
            if line is None or start is None:
                return
            line, start = int(line), int(start)
        except (TypeError, ValueError):
            return
        self.symbolActivated.emit(line, start)
