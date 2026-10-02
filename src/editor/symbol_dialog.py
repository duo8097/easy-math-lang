"""Small focused dialog for parameterized symbol insertion."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from .symbol_registry import Symbol, build_source, validate_fields


class SymbolDialog(QtWidgets.QDialog):
    """Generic ``Insert <symbol>`` dialog built from :class:`Symbol.fields`.

    - Clear labels, placeholders/defaults, first-field autofocus.
    - Enter confirms (default button), Escape cancels.
    - Required-field + pattern validation; nothing is inserted on Cancel.
    """

    def __init__(self, symbol: Symbol, parent=None,
                 initial: dict | None = None):
        super().__init__(parent)
        self._symbol = symbol
        self.setWindowTitle(f'Insert {symbol.display}')
        self.setModal(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        info = QtWidgets.QLabel(symbol.tooltip, self)
        info.setWordWrap(True)
        info.setObjectName('symbol-info')
        layout.addWidget(info)

        form = QtWidgets.QFormLayout()
        form.setSpacing(6)
        layout.addLayout(form)

        self._edits: dict[str, QtWidgets.QLineEdit] = {}
        initial = dict(initial or {})
        for f in symbol.fields:
            edit = QtWidgets.QLineEdit(self)
            # Prefill: explicit initial > field default > empty.
            pre = initial.get(f.key, '')
            if not str(pre).strip() and f.default:
                pre = f.default
            edit.setText(str(pre))
            edit.setAccessibleName(f.label)
            if f.placeholder:
                edit.setPlaceholderText(f.placeholder)
            if f.help:
                edit.setToolTip(f.help)
                edit.setAccessibleDescription(f.help)
            edit.returnPressed.connect(self._on_accept)
            form.addRow(f.label + ':', edit)
            self._edits[f.key] = edit

        self._error = QtWidgets.QLabel('', self)
        self._error.setWordWrap(True)
        self._error.setAccessibleName('Symbol dialog error')
        self._error.setProperty('isErrorLabel', True)
        self._error.hide()
        layout.addWidget(self._error)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Cancel | QtWidgets.QDialogButtonBox.Ok,
            self,
        )
        buttons.button(QtWidgets.QDialogButtonBox.Ok).setText('Insert')
        buttons.button(QtWidgets.QDialogButtonBox.Ok).setDefault(True)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Focus the first empty required field, else the first field.
        first = None
        for f in symbol.fields:
            if f.required and not self._edits[f.key].text().strip():
                first = self._edits[f.key]
                break
        if first is None and symbol.fields:
            first = self._edits[symbol.fields[0].key]
        if first is not None:
            QtCore.QTimer.singleShot(0, first.setFocus)
            try:
                first.selectAll()
            except Exception:
                pass

    def values(self) -> dict:
        return {k: e.text() for k, e in self._edits.items()}

    def _on_accept(self):
        errors = validate_fields(self._symbol, self.values())
        if errors:
            self._error.setText(errors[0])
            self._error.show()
            return
        # Defensive: generation must never crash the dialog.
        try:
            build_source(self._symbol, self.values())
        except ValueError as exc:
            self._error.setText(str(exc))
            self._error.show()
            return
        self._error.hide()
        self.accept()

    @classmethod
    def get_values(cls, symbol: Symbol, parent=None,
                   initial: dict | None = None) -> tuple[bool, dict]:
        """Show the dialog; return (accepted, values)."""
        dlg = cls(symbol, parent, initial=initial)
        ok = dlg.exec() == QtWidgets.QDialog.Accepted
        return ok, dlg.values() if ok else {}
