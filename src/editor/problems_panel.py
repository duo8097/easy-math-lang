"""Problems panel: LSP diagnostics list with click-to-navigate."""

from PySide6 import QtCore, QtWidgets

from . import friendly_errors, i18n, positions
from .icons import SIZE_PANEL, apply_icon


class ProblemsPanel(QtWidgets.QWidget):
    """Shows ``❌ line:col message`` rows; click navigates to the range."""

    diagnosticActivated = QtCore.Signal(int, int, int)  # line, start, end

    def __init__(self, parent=None):
        super().__init__(parent)
        self._diagnostics = []
        self._filter = 'all'
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setSpacing(4)
        self._count_label = QtWidgets.QLabel('', self)
        self._count_label.setObjectName('problems-count')
        toolbar.addWidget(self._count_label)
        toolbar.addStretch(1)
        self._filter_combo = QtWidgets.QComboBox(self)
        self._filter_combo.setObjectName('problems-filter')
        self._filter_combo.addItem(i18n.tr('problems.filter_all'), 'all')
        self._filter_combo.addItem(i18n.tr('problems.filter_errors'), 'error')
        self._filter_combo.addItem(i18n.tr('problems.filter_warnings'),
                                   'warning')
        self._filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self._filter_combo)
        self._clear_button = QtWidgets.QPushButton(
            i18n.tr('problems.clear'), self)
        self._clear_button.setObjectName('problems-clear')
        self._clear_button.setToolTip(i18n.tr('problems.clear_tip'))
        self._clear_button.setAccessibleName(i18n.tr('problems.clear'))
        apply_icon(self._clear_button, 'clear', SIZE_PANEL)
        self._clear_button.clicked.connect(self.clear)
        toolbar.addWidget(self._clear_button)
        layout.addLayout(toolbar)

        self._list = QtWidgets.QListWidget(self)
        layout.addWidget(self._list)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.itemActivated.connect(self._on_item_clicked)
        self._refresh_count()

    def _on_filter_changed(self, _index=0):
        data = self._filter_combo.currentData()
        self._filter = data if data in ('all', 'error', 'warning') else 'all'
        self._rebuild_rows()

    def set_diagnostics(self, diagnostics):
        """Replace rows. Each diagnostic is a dict with line/start/end/message.

        ``severity`` is ``'error'`` or anything else (shown as warning).
        Every row shows a plain-language explanation plus the raw
        message, which is also kept in the item tooltip.
        """
        safe = []
        for diag in (diagnostics or []):
            if isinstance(diag, dict):
                safe.append(diag)
        self._diagnostics = safe
        self._rebuild_rows()
        self._refresh_count()

    def _rebuild_rows(self):
        self._list.clear()
        for index, diag in enumerate(self._diagnostics):
            severity = diag.get('severity', 'error')
            if self._filter != 'all' and severity != self._filter:
                continue
            line = diag.get('line', 0)
            start = diag.get('start', 0)
            message = diag.get('message', '')
            # Keep the position prefix + raw message (tests and muscle
            # memory rely on it); the friendly sentence follows.
            friendly = friendly_errors.format_friendly(message)
            text = positions.format_diagnostic(
                severity, line, start, message)
            if friendly:
                text = f'{text}  —  {friendly}'
            item = QtWidgets.QListWidgetItem(text, self._list)
            item.setData(QtCore.Qt.UserRole, index)
            icon_name = 'error' if severity == 'error' else 'warning'
            from .icons import icon as _icon
            item.setIcon(_icon(icon_name, SIZE_PANEL))
            if message:
                item.setToolTip(
                    f'{i18n.tr("friendly.technical_details")}\n{message}')

    def _refresh_count(self):
        count = len(self._diagnostics)
        self._count_label.setText(
            i18n.tr('problems.count_badge', count=count))
        self._count_label.setToolTip(
            i18n.tr('problems.count_badge', count=count))

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
        if not isinstance(diag, dict):
            return
        self.diagnosticActivated.emit(diag.get('line', 0),
                                      diag.get('start', 0),
                                      diag.get('end', diag.get('start', 0)))
