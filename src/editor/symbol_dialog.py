"""Small focused dialog for parameterized symbol insertion."""

from __future__ import annotations

from dataclasses import replace as _dc_replace

from PySide6 import QtCore, QtWidgets

from .symbol_registry import (
    Symbol,
    build_source,
    grid_shape_of_fields,
    is_grid_symbol,
    make_grid_fields,
    validate_fields,
)


def _shape_text(rows: int, cols: int) -> str:
    """Human-readable grid size, e.g. ``3 rows × 2 columns``."""
    row_word = 'row' if rows == 1 else 'rows'
    col_word = 'column' if cols == 1 else 'columns'
    return f'{rows} {row_word} × {cols} {col_word}'


class SymbolDialog(QtWidgets.QDialog):
    """Generic ``Insert <symbol>`` dialog built from :class:`Symbol.fields`.

    - Clear labels, placeholders/defaults, first-field autofocus.
    - Enter confirms (default button), Escape cancels.
    - Required-field + pattern validation; nothing is inserted on Cancel.
    - Table/matrix grids additionally offer Add row / Add cell, growing
      from the default 2x2 (values already typed are preserved).
    """

    def __init__(self, symbol: Symbol, parent=None,
                 initial: dict | None = None):
        super().__init__(parent)
        self._symbol = symbol
        # Local field list: grid dialogs extend it via Add row/cell
        # without mutating the shared registry entry.
        self._fields = list(symbol.fields)
        self.setWindowTitle(f'Insert {symbol.display}')
        self.setModal(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        # Keep the window fitted to its contents: grid dialogs grow via
        # Add row/cell, and without this the top-level keeps the stale
        # smaller geometry while the layout minimum has grown — the
        # Windows platform plugin then spams
        # "QWindowsWindow::setGeometry: Unable to set geometry" warnings.
        layout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)

        info = QtWidgets.QLabel(symbol.tooltip, self)
        info.setWordWrap(True)
        info.setObjectName('symbol-info')
        layout.addWidget(info)

        self._form = QtWidgets.QFormLayout()
        self._form.setSpacing(6)
        layout.addLayout(self._form)

        self._edits: dict[str, QtWidgets.QLineEdit] = {}
        self._populate_form(dict(initial or {}))

        self._shape_label: QtWidgets.QLabel | None = None
        if is_grid_symbol(symbol):
            grid_row = QtWidgets.QHBoxLayout()
            grid_row.setSpacing(6)
            self._shape_label = QtWidgets.QLabel(self)
            self._shape_label.setObjectName('symbol-grid-shape')
            self._shape_label.setAccessibleName('Grid dimensions')
            grid_row.addWidget(self._shape_label)
            grid_row.addStretch(1)
            add_row = QtWidgets.QPushButton('Add row', self)
            add_row.setObjectName('symbol-add-row')
            add_row.setAccessibleName('Add row')
            add_row.setToolTip('Add another row to the grid')
            add_row.clicked.connect(self._on_add_row)
            grid_row.addWidget(add_row)
            add_cell = QtWidgets.QPushButton('Add cell', self)
            add_cell.setObjectName('symbol-add-cell')
            add_cell.setAccessibleName('Add cell')
            add_cell.setToolTip('Add another column to the grid')
            add_cell.clicked.connect(self._on_add_cell)
            grid_row.addWidget(add_cell)
            layout.addLayout(grid_row)
            self._update_shape_label()

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
        self._focus_first_empty()

    def _populate_form(self, prefill: dict):
        """Build form rows from ``self._fields`` (construction only).

        The form is empty at this point; grid growth later appends /
        inserts rows incrementally (see ``_on_add_row`` / ``_on_add_cell``)
        so live edits — and their typed values — are never destroyed.
        """
        for f in self._fields:
            edit = self._field_edit(f, prefill.get(f.key, ''))
            self._form.addRow(f.label + ':', edit)
            self._edits[f.key] = edit

    def _field_edit(self, field, text: str = ''):
        """Configured line edit for one field (prefill > default)."""
        edit = QtWidgets.QLineEdit(self)
        pre = text
        if not str(pre).strip() and field.default:
            pre = field.default
        edit.setText(str(pre))
        edit.setAccessibleName(field.label)
        if field.placeholder:
            edit.setPlaceholderText(field.placeholder)
        if field.help:
            edit.setToolTip(field.help)
            edit.setAccessibleDescription(field.help)
        edit.returnPressed.connect(self._on_accept)
        return edit

    def _focus_first_empty(self):
        first = None
        for f in self._fields:
            edit = self._edits.get(f.key)
            if edit is None:
                continue
            if f.required and not edit.text().strip():
                first = edit
                break
        if first is None and self._fields:
            first = self._edits.get(self._fields[0].key)
        if first is not None:
            QtCore.QTimer.singleShot(0, first.setFocus)
            try:
                first.selectAll()
            except Exception:
                pass

    def _update_shape_label(self):
        if self._shape_label is None:
            return
        rows, cols = grid_shape_of_fields(self._fields)
        self._shape_label.setText(_shape_text(rows, cols))

    def _sync_geometry(self):
        """Resize the window to its (possibly grown) contents.

        Grid dialogs grow via Add row/cell while the top-level would
        otherwise keep its stale smaller geometry — the condition the
        Windows platform plugin reports as
        "QWindowsWindow::setGeometry: Unable to set geometry" warnings.
        """
        self._form.invalidate()
        if self.layout() is not None:
            self.layout().activate()
        self.adjustSize()

    def _focus_edit(self, key: str):
        target = self._edits.get(key)
        if target is not None:
            target.setFocus()
            try:
                target.selectAll()
            except Exception:
                pass

    def _extend_grid(self, add_rows: int, add_cols: int,
                     focus_key: str | None = None):
        """Grow the grid, preserving already-typed values.

        Existing edits stay in place (only new rows are appended /
        inserted), so typed values and focus targets are never destroyed.
        """
        rows, cols = grid_shape_of_fields(self._fields)
        new_rows, new_cols = rows + add_rows, cols + add_cols
        full = make_grid_fields(self._symbol.name, new_rows, new_cols)
        known = set(self._edits)
        if add_cols:
            # One new cell per row, inserted at the end of its row group
            # (earlier inserts shift later indices by one each).
            for r in range(1, rows + 1):
                key = f'r{r}c{new_cols}'
                field = next(f for f in full if f.key == key)
                edit = self._field_edit(field)
                self._form.insertRow(r * new_cols - 1,
                                     field.label + ':', edit)
                self._edits[key] = edit
        else:
            for f in full:
                if f.key not in known:
                    edit = self._field_edit(f)
                    self._form.addRow(f.label + ':', edit)
                    self._edits[f.key] = edit
        self._fields = full
        self._update_shape_label()
        self._sync_geometry()
        if focus_key:
            self._focus_edit(focus_key)

    def _on_add_row(self):
        rows, cols = grid_shape_of_fields(self._fields)
        self._extend_grid(1, 0, focus_key=f'r{rows + 1}c1')

    def _on_add_cell(self):
        rows, cols = grid_shape_of_fields(self._fields)
        self._extend_grid(0, 1, focus_key=f'r1c{cols + 1}')

    def _active_symbol(self) -> Symbol:
        """Symbol copy carrying the current (possibly extended) fields."""
        if is_grid_symbol(self._symbol):
            return _dc_replace(self._symbol, fields=list(self._fields))
        return self._symbol

    def values(self) -> dict:
        return {k: e.text() for k, e in self._edits.items()}

    def _on_accept(self):
        symbol = self._active_symbol()
        errors = validate_fields(symbol, self.values())
        if errors:
            self._error.setText(errors[0])
            self._error.show()
            return
        # Defensive: generation must never crash the dialog.
        try:
            build_source(symbol, self.values())
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
