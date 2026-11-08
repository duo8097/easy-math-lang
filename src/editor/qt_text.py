"""Translated Qt-generated texts (context menus, standard buttons).

Qt ships no Vietnamese catalog, so its built-in texts (text-edit
context menus, QMessageBox standard buttons, file dialog labels)
stay English unless set explicitly. The helpers here build those
texts from the i18n catalog at show time, so a language switch
needs no restart. They never touch IME composition: menus are only
built when the user opens one.
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from . import i18n


def _standard_button_texts():
    return {
        QtWidgets.QDialogButtonBox.Ok: 'btn.ok',
        QtWidgets.QDialogButtonBox.Cancel: 'btn.cancel',
        QtWidgets.QDialogButtonBox.Yes: 'btn.yes',
        QtWidgets.QDialogButtonBox.No: 'btn.no',
        QtWidgets.QDialogButtonBox.Save: 'btn.save',
        QtWidgets.QDialogButtonBox.Discard: 'btn.discard',
        QtWidgets.QDialogButtonBox.Close: 'btn.close',
        QtWidgets.QDialogButtonBox.Apply: 'btn.apply',
    }


def translate_button_box(box):
    """Set every standard button in *box* from the catalog."""
    if box is None:
        return box
    for standard, key in _standard_button_texts().items():
        try:
            button = box.button(standard)
        except Exception:
            button = None
        if button is not None:
            button.setText(i18n.tr(key))
    return box


def translate_message_box(box):
    """Set every standard button in a QMessageBox from the catalog."""
    if box is None:
        return box
    for standard, key in _standard_button_texts().items():
        try:
            button = box.button(standard)
        except Exception:
            button = None
        if button is not None:
            button.setText(i18n.tr(key))
    return box


def question(parent, title, text, buttons):
    """QMessageBox.question with translated buttons.

    *buttons* is a list of ``(catalog_key, role)`` pairs. Returns
    the clicked button's role, or ``None`` when cancelled/closed.
    """
    box = QtWidgets.QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QtWidgets.QMessageBox.Question)
    chosen = {}
    for key, role in buttons:
        button = box.addButton(i18n.tr(key), role)
        chosen[button] = role
    if chosen:
        box.setDefaultButton(next(iter(chosen)))
    translate_message_box(box)
    box.exec()
    clicked = box.clickedButton()
    return chosen.get(clicked)


def critical(parent, title, text):
    """QMessageBox.critical with a translated Close button."""
    box = QtWidgets.QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QtWidgets.QMessageBox.Critical)
    box.addButton(i18n.tr('btn.close'), QtWidgets.QMessageBox.RejectRole)
    translate_message_box(box)
    box.exec()
    return box


def translate_file_dialog(dialog):
    """Set translated labels/buttons on a non-native QFileDialog."""
    if dialog is None:
        return dialog
    labels = {
        QtWidgets.QFileDialog.LookIn: 'filedialog.lookin',
        QtWidgets.QFileDialog.FileName: 'filedialog.filename',
        QtWidgets.QFileDialog.FileType: 'filedialog.filetype',
        QtWidgets.QFileDialog.Accept: 'filedialog.accept_open',
        QtWidgets.QFileDialog.Reject: 'filedialog.reject',
    }
    for label, key in labels.items():
        try:
            dialog.setLabelText(label, i18n.tr(key))
        except Exception:
            pass
    # The accept button text follows the dialog mode.
    try:
        accept_key = ('filedialog.accept_save'
                      if dialog.acceptMode() == QtWidgets.QFileDialog.AcceptSave
                      else 'filedialog.accept_open')
        dialog.setLabelText(QtWidgets.QFileDialog.Accept,
                            i18n.tr(accept_key))
    except Exception:
        pass
    return dialog


def translate_input_dialog(dialog):
    """Set translated buttons on a QInputDialog instance."""
    if dialog is None:
        return dialog
    for box in dialog.findChildren(QtWidgets.QDialogButtonBox):
        translate_button_box(box)
    return dialog


def install_text_context_menu(widget):
    """Replace the Qt text-edit context menu with a translated one.

    Works for QPlainTextEdit and QLineEdit. The menu is built on
    demand from the current locale, so it always shows the active
    language. IME composition is untouched (this only runs when the
    user right-clicks).
    """
    widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

    def _show(position):
        menu = QtWidgets.QMenu(widget)
        actions = (
            ('ctx.undo', widget.undo, QtGui_QKeySequence('Undo')),
            ('ctx.redo', widget.redo, QtGui_QKeySequence('Redo')),
            None,
            ('ctx.cut', widget.cut, QtGui_QKeySequence('Cut')),
            ('ctx.copy', widget.copy, QtGui_QKeySequence('Copy')),
            ('ctx.paste', widget.paste, QtGui_QKeySequence('Paste')),
            ('ctx.delete',
             getattr(widget, 'deleteSelected', widget.cut), None),
            None,
            ('ctx.select_all', widget.selectAll,
             QtGui_QKeySequence('SelectAll')),
        )
        for item in actions:
            if item is None:
                menu.addSeparator()
                continue
            key, slot, shortcut = item
            action = menu.addAction(i18n.tr(key), slot)
            if shortcut is not None:
                action.setShortcut(shortcut)
            # Enablement mirrors the widget's own state.
            try:
                if key == 'ctx.cut' or key == 'ctx.copy':
                    action.setEnabled(widget.textCursor().hasSelection()
                                      if hasattr(widget, 'textCursor')
                                      else True)
                if key == 'ctx.paste':
                    action.setEnabled(True)
            except Exception:
                pass
        menu.exec(widget.mapToGlobal(position))

    widget.customContextMenuRequested.connect(_show)
    return widget


def QtGui_QKeySequence(name):
    from PySide6 import QtGui
    return getattr(QtGui.QKeySequence, name)
