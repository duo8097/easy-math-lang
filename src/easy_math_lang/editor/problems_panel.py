"""Problems panel: LSP diagnostics list with click-to-navigate."""

from PySide6 import QtCore, QtWidgets

from . import positions


class ProblemsPanel(QtWidgets.QWidget):
    """Shows ``❌ line:col message`` rows; click navigates to the range."""

    diagnosticActivated = QtCore.Signal(int, int, int)  # line, start, end

    def __init__(self, parent=None):
        super().__init__(parent)
        self._diagnostics = []
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._list = QtWidgets.QListWidget(self)
        layout.addWidget(self._list)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.itemActivated.connect(self._on_item_clicked)

    def set_diagnostics(self, diagnostics):
        """Replace rows. Each diagnostic is a dict with line/start/end/message.

        ``severity`` is ``'error'`` or anything else (shown as warning).
        """
        self._diagnostics = list(diagnostics or [])
        self._list.clear()
        for index, diag in enumerate(self._diagnostics):
            line = diag.get('line', 0)
            start = diag.get('start', 0)
            severity = diag.get('severity', 'error')
            text = positions.format_diagnostic(
                severity, line, start, diag.get('message', ''))
            item = QtWidgets.QListWidgetItem(text, self._list)
            item.setData(QtCore.Qt.UserRole, index)

    def clear(self):
        self.set_diagnostics([])

    def count(self):
        return len(self._diagnostics)

    def _on_item_clicked(self, item):
        index = item.data(QtCore.Qt.UserRole)
        try:
            diag = self._diagnostics[index]
        except (IndexError, TypeError):
            return
        self.diagnosticActivated.emit(diag.get('line', 0),
                                      diag.get('start', 0),
                                      diag.get('end', diag.get('start', 0)))
