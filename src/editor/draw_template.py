"""Non-modal *draw template window: preview + editable code + palette.

Opened by a gallery card's ``Insert example…`` button
(``DrawGalleryDialog.templateRequested``) — one instance per
MainWindow, re-loaded when another card is picked.  Layout:

- **left**: the template's pre-rendered SVG on a fixed light tile,
  and under it the bare ``*draw(...)`` code that will be inserted —
  editable, so the document gets exactly what this window shows;
- **right**: a command palette of **every** geometry command — the
  ones already used in the code are pinned to the top in first-
  appearance order and shown bold, and the whole list fuzzy-filters
  as you type.  Picking one runs its ``geo-*`` parameter dialog
  through the host window and splices the built command into the
  *code area* — before the closing ``)`` of the shown block — never
  into the document.

Presentational only, like the gallery it comes from: it emits
``insertRequested(str)`` (the final code) and ``commandRequested(str)``
(a ``geo-*`` palette id); the host window (MainWindow) owns both
insertions.  Thumbnails come from the same ``assets/draw_previews``
SVGs as the gallery cards — never compiled at runtime.  Imported
lazily with the gallery (see tests/test_lazy_imports).
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from .command_palette import fuzzy_score
from .draw_catalog import (CatalogEntry, build_insert_text, catalog_entries,
                           commands_in, get_entry, symbol_for_command)
from .draw_gallery import PLACEHOLDER_BORDER, TILE_BG, render_thumbnail

#: Preview tile: the SVG re-rendered at this size (crisp — not a
#: upscale of the 168×112 gallery thumbnail).
PREVIEW_W, PREVIEW_H = 480, 320


class DrawTemplateDialog(QtWidgets.QDialog):
    """Preview one template, tweak its code, then insert it.

    Non-modal so the document stays visible behind it; presentational
    only — the host window connects the signals to its insertion code.
    """

    insertRequested = QtCore.Signal(str)
    commandRequested = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(False)
        self.setObjectName('drawTemplateDialog')
        self.setWindowTitle('*draw — Template')
        self.resize(980, 640)
        self.entry: CatalogEntry | None = None

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(6)
        self.title = QtWidgets.QLabel('', self)
        self.title.setObjectName('draw-template-title')
        title_font = QtGui.QFont(self.title.font())
        title_font.setBold(True)
        self.title.setFont(title_font)
        header.addWidget(self.title)
        self.syntax = QtWidgets.QLabel('', self)
        self.syntax.setObjectName('draw-template-syntax')
        mono = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
        self.syntax.setFont(mono)
        self.syntax.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        header.addWidget(self.syntax, 1)
        root.addLayout(header)

        body = QtWidgets.QHBoxLayout()
        body.setSpacing(10)

        # -- left: preview over the editable code --------------------
        left = QtWidgets.QVBoxLayout()
        left.setSpacing(6)
        self.preview = QtWidgets.QLabel(self)
        self.preview.setObjectName('draw-template-preview')
        self.preview.setFixedSize(PREVIEW_W, PREVIEW_H)
        self.preview.setAlignment(QtCore.Qt.AlignCenter)
        # Fixed light tile in both themes, like the gallery cards:
        # previews stay legible in dark mode without inversion.
        self.preview.setStyleSheet(
            f'QLabel {{ background-color: {TILE_BG}; '
            f'border: 1px solid {PLACEHOLDER_BORDER}; }}')
        left.addWidget(self.preview, 0, QtCore.Qt.AlignHCenter)

        code_label = QtWidgets.QLabel('Code to insert', self)
        code_label.setObjectName('draw-template-code-label')
        left.addWidget(code_label)

        self.code = QtWidgets.QPlainTextEdit(self)
        self.code.setObjectName('draw-template-code')
        self.code.setFont(mono)
        self.code.setAccessibleName('Code to insert')
        code_label.setBuddy(self.code)
        self.code.setTabStopDistance(
            4 * self.code.fontMetrics().horizontalAdvance(' '))
        self.code.setPlaceholderText(
            'The *draw(...) block that Insert puts in the document…')
        left.addWidget(self.code, 1)
        body.addLayout(left, 3)

        # -- right: palette of every geometry command ---------------
        right = QtWidgets.QVBoxLayout()
        right.setSpacing(6)
        palette_label = QtWidgets.QLabel('Geometry commands', self)
        palette_label.setObjectName('draw-template-palette-label')
        palette_label.setToolTip(
            'All geometry commands — the ones already used in the code '
            'are pinned to the top in bold. Double-click one (or press '
            'Enter in the filter) to add it via its parameter dialog.')
        right.addWidget(palette_label)

        self.search = QtWidgets.QLineEdit(self)
        self.search.setObjectName('draw-template-search')
        self.search.setPlaceholderText('Filter commands…')
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName('Filter template commands')
        palette_label.setBuddy(self.search)
        right.addWidget(self.search)

        self.commands = QtWidgets.QListWidget(self)
        self.commands.setObjectName('draw-template-commands')
        self.commands.setAccessibleName('Geometry commands')
        right.addWidget(self.commands, 1)
        body.addLayout(right, 2)

        root.addLayout(body, 1)

        # -- bottom: commit / discard --------------------------------
        buttons = QtWidgets.QHBoxLayout()
        buttons.setSpacing(6)
        buttons.addStretch(1)
        self.cancel_btn = QtWidgets.QPushButton('Cancel', self)
        self.cancel_btn.setObjectName('draw-template-cancel')
        self.cancel_btn.setAccessibleName('Close without inserting')
        self.cancel_btn.clicked.connect(self.close)
        buttons.addWidget(self.cancel_btn)
        self.insert_btn = QtWidgets.QPushButton('Insert', self)
        self.insert_btn.setObjectName('draw-template-insert')
        self.insert_btn.setAccessibleName('Insert the code into the document')
        self.insert_btn.setToolTip(
            'Insert the code above at the cursor (one undo step)')
        self.insert_btn.setDefault(True)
        self.insert_btn.clicked.connect(self._emit_insert)
        buttons.addWidget(self.insert_btn)
        root.addLayout(buttons)

        self.search.textChanged.connect(self._rebuild_commands)
        self.search.returnPressed.connect(self._activate_current)
        self.code.textChanged.connect(self._on_code_changed)
        self.commands.itemActivated.connect(self._on_command_chosen)
        # Enter/Return must run ONLY the command pick — see eventFilter.
        self.search.installEventFilter(self)
        self.commands.installEventFilter(self)
        self._update_insert_enabled()

    # -- public helpers ---------------------------------------------

    def open_template(self, key) -> None:
        """Load *key* (a ``CatalogEntry``, id or command) into the window.

        Re-clicking the card that is already shown keeps any in-
        progress edits — only a different card reloads the example.
        """
        entry = key if isinstance(key, CatalogEntry) else get_entry(str(key))
        if entry == self.entry and self.isVisible():
            return
        self.entry = entry
        self.setWindowTitle(f'*draw — {entry.title} template')
        self.title.setText(entry.title)
        self.syntax.setText(entry.syntax)
        self.syntax.setToolTip(entry.syntax)
        pixmap, has_preview = render_thumbnail(
            entry.id, PREVIEW_W, PREVIEW_H)
        self.preview.setPixmap(pixmap)
        self.preview.setProperty('has-preview', has_preview)
        self.preview.setAccessibleName(
            f'Preview of *{entry.command}' if has_preview
            else f'No preview for *{entry.command}')
        self.code.setPlainText(entry.example)
        cursor = self.code.textCursor()
        cursor.setPosition(0)
        self.code.setTextCursor(cursor)
        self.search.clear()
        self._rebuild_commands()
        self._update_insert_enabled()

    def code_text(self) -> str:
        """The bare code Insert would put in the document."""
        return self.code.toPlainText()

    def insert_code(self, text: str) -> None:
        """Splice *text* (a built ``*command(...)`` line) into the code area.

        Uses the same block-aware insertion math as the document
        inserter: inside the shown ``*draw(...)`` block the command
        lands before the closing ``)``, otherwise it becomes its own
        block.  An active selection in the code area is replaced (as
        in the document).  The caret moves with the insertion; the
        document stays untouched until Insert.
        """
        doc = self.code.toPlainText()
        cursor = self.code.textCursor()
        sel_start = min(cursor.selectionStart(), cursor.selectionEnd())
        sel_end = max(cursor.selectionStart(), cursor.selectionEnd())
        # Positions below are relative to the code *without* the
        # selection — removing it first inside the edit block makes
        # the two line up exactly (as in the document inserter).
        base = doc[:sel_start] + doc[sel_end:]
        try:
            change = build_insert_text(text, base, sel_start)
        except ValueError:
            return
        cursor.beginEditBlock()
        try:
            cursor.setPosition(sel_start)
            if sel_end > sel_start:
                cursor.setPosition(sel_end, QtGui.QTextCursor.KeepAnchor)
                cursor.insertText('')
            cursor.setPosition(change.start)
            cursor.setPosition(change.end, QtGui.QTextCursor.KeepAnchor)
            cursor.insertText(change.insert)
            cursor.setPosition(change.cursor)
        finally:
            cursor.endEditBlock()
        self.code.setTextCursor(cursor)
        self.code.setFocus()

    def raise_and_activate(self):
        """Bring an already-open instance to the front."""
        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()

    # -- internals ---------------------------------------------------

    def _on_code_changed(self):
        self._rebuild_commands()
        self._update_insert_enabled()

    def _update_insert_enabled(self):
        """Grey Insert out unless the code would actually be accepted.

        Empty code and a code area the inserter rejects (an
        unterminated ``*draw(`` block) both leave the button inert —
        what it says is exactly what it can do.
        """
        text = self.code_text()
        if not text.strip():
            self.insert_btn.setEnabled(False)
            return
        try:
            build_insert_text(text, text, 0)
        except ValueError:
            self.insert_btn.setEnabled(False)
        else:
            self.insert_btn.setEnabled(True)

    def _emit_insert(self):
        text = self.code_text()
        if not text.strip():
            return
        # Same validation the host's inserter does — a code area the
        # inserter would reject (e.g. an unterminated *draw( block)
        # must not be committed AND silently discarded: keep the
        # window open so the edits survive to be fixed.
        try:
            build_insert_text(text, text, 0)
        except ValueError:
            return
        self.insertRequested.emit(text)
        self.close()

    def _rebuild_commands(self, *_args):
        """Refresh the palette: every geometry command, in-code first.

        The palette is also a launcher for commands the code does not
        use yet, so all catalog entries are listed; commands found in
        the code are pinned to the top (first-appearance order) and
        shown bold.  The filter fuzzy-matches over the whole list.
        """
        self.commands.clear()
        query = self.search.text().strip().lower()
        related = commands_in(self.code_text())
        related_set = set(related)
        entries = catalog_entries()
        by_command = {e.command: e for e in entries}
        ordered = [by_command[command] for command in related]
        ordered.extend(e for e in entries if e.command not in related_set)
        rows = []
        for order, entry in enumerate(ordered):
            score = 0.0
            if query:
                score = fuzzy_score(
                    query, f'{entry.title} {entry.command}')
                if score is None:
                    continue
            rows.append((score, order, entry))
        # In-code commands stay on top even while filtering (the
        # tooltip/docstring promise); fuzzy order only breaks ties
        # inside each band.
        rows.sort(key=lambda row: (
            0 if row[2].command in related_set else 1, row[0], row[1]))
        # Titles are padded to a common pixel width so the *command
        # column lines up (a plain '\t' collapses when one title is
        # within a space of the next tab stop).
        metrics = self.commands.fontMetrics()
        space = max(1, metrics.horizontalAdvance(' '))
        title_w = max((metrics.horizontalAdvance(row[2].title)
                       for row in rows), default=0)
        for _score, _order, entry in rows:
            pad = 2 + max(
                0, (title_w - metrics.horizontalAdvance(entry.title))
                // space)
            item = QtWidgets.QListWidgetItem(
                f'{entry.title}{" " * pad}*{entry.command}', self.commands)
            item.setData(QtCore.Qt.UserRole, entry.command)
            if entry.command in related_set:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            if entry.symbol:
                item.setToolTip(
                    f'Add *{entry.command} to the code via its parameter '
                    'dialog (double-click or press Enter)')
            else:
                # No geo-* dialog in the registry (e.g. equal-angle).
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEnabled)
                item.setToolTip(
                    f'No parameter dialog for *{entry.command} yet')
        if not rows:
            placeholder = QtWidgets.QListWidgetItem(
                'No matching command.' if query else 'No geometry commands.',
                self.commands)
            placeholder.setFlags(
                placeholder.flags() & ~QtCore.Qt.ItemIsEnabled)
            return
        for row in range(self.commands.count()):
            if self.commands.item(row).flags() & QtCore.Qt.ItemIsEnabled:
                self.commands.setCurrentRow(row)
                break

    def eventFilter(self, obj, event):
        """Enter in the palette runs only the command pick.

        Qt's dialog default-button handling also fires ``insert_btn``
        on the same key (verified with ``QTest.keyClick``): the whole
        code area would be committed and the window closed right after
        the pick.  The key press performs the activation, and press
        *and* release are swallowed so neither bubbles up to the
        dialog.  Double-click activation (``itemActivated``) is
        unaffected — mouse events pass through.
        """
        kind = event.type()
        if kind not in (QtCore.QEvent.KeyPress, QtCore.QEvent.KeyRelease):
            # Every other event (Show, Hide, Paint…) reaches this
            # filter too — and only QKeyEvent has key().
            return super().eventFilter(obj, event)
        if event.key() not in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            return super().eventFilter(obj, event)
        if kind == QtCore.QEvent.KeyPress:
            self._activate_current()
        return True

    def _activate_current(self):
        """Enter in the filter or on the palette picks the current row."""
        item = self.commands.currentItem()
        if item is not None and item.flags() & QtCore.Qt.ItemIsEnabled:
            self._on_command_chosen(item)

    def _on_command_chosen(self, item):
        command = item.data(QtCore.Qt.UserRole)
        if not isinstance(command, str) or not command:
            return
        symbol = symbol_for_command(command)
        if symbol:
            self.commandRequested.emit(symbol)
