"""Non-modal *draw gallery window (presentational only).

Opened from the Symbol Bar's ``*draw`` button. Lists every geometry
command as a card — thumbnail, syntax, description — with a search box
and group filter. Like ``SymbolBar`` it emits signals and lets the
host window (MainWindow) own insertion:

- ``exampleRequested(str)`` — a full ``*draw(...)`` example block to
  insert (also used for the "empty block" action).
- ``commandRequested(str symbol_name)`` — a ``geo-*`` palette id; the
  host runs the existing ``SymbolDialog`` parameter dialog.

Thumbnails come from ``assets/draw_previews/<id>.svg`` rendered with
``QSvgRenderer`` (pre-rendered by ``scripts/build_draw_previews.py`` —
never fetched at runtime). A missing/unreadable file degrades to a
neutral placeholder tile, so the dialog works with zero SVGs present.
Every thumbnail sits on a fixed light tile so it stays legible in dark
mode; the rest of the window follows the app theme like any dialog.

This module is imported lazily on first click (keeps PySide6.QtSvg
and the catalog out of editor startup — see tests/test_lazy_imports).
"""

from __future__ import annotations

import os

from PySide6 import QtCore, QtGui, QtSvg, QtWidgets

from .draw_catalog import CATALOG, GROUPS, CatalogEntry, catalog_entries

#: Source-tree location of the pre-rendered thumbnails.
PREVIEW_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'assets', 'draw_previews')

#: Fixed thumbnail tile: light in BOTH themes so figures read on dark.
THUMB_W, THUMB_H = 168, 112
TILE_BG = '#ffffff'
PLACEHOLDER_BG = '#f2f2f2'
PLACEHOLDER_FG = '#b8b8b8'
PLACEHOLDER_BORDER = '#c8c8c8'
CARD_WIDTH = 244
GRID_COLUMNS = 3


def preview_dir() -> str:
    """Directory holding ``<id>.svg`` previews.

    Source tree first (``editor/assets/draw_previews`` next to this
    module), then the PyInstaller bundle layout (``--add-data`` puts
    the files under the bundle root). Returns the first existing
    candidate — none may exist, in which case every card shows the
    placeholder tile.
    """
    candidates = [PREVIEW_DIR]
    try:
        from . import paths
        candidates.append(
            paths.resource_path('editor', 'assets', 'draw_previews'))
    except Exception:  # pragma: no cover - defensive
        pass
    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    return PREVIEW_DIR


def preview_path(entry_id: str) -> str:
    """Absolute path of one thumbnail (may not exist)."""
    return os.path.join(preview_dir(), f'{entry_id}.svg')


# ----------------------------------------------------------------------
# Thumbnail rendering
# ----------------------------------------------------------------------

def _placeholder_pixmap() -> QtGui.QPixmap:
    """Neutral tile used when an SVG is missing or unreadable."""
    pix = QtGui.QPixmap(THUMB_W, THUMB_H)
    pix.fill(QtGui.QColor(PLACEHOLDER_BG))
    painter = QtGui.QPainter(pix)
    try:
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        pen = QtGui.QPen(QtGui.QColor(PLACEHOLDER_BORDER))
        pen.setStyle(QtCore.Qt.DashLine)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRect(4, 4, THUMB_W - 9, THUMB_H - 9)
        painter.drawLine(6, 6, THUMB_W - 7, THUMB_H - 7)
        painter.drawLine(THUMB_W - 7, 6, 6, THUMB_H - 7)
    finally:
        painter.end()
    return pix


def render_thumbnail(entry_id: str) -> tuple[QtGui.QPixmap, bool]:
    """Render ``<entry_id>.svg`` on a fixed light tile.

    Returns ``(pixmap, has_preview)``; ``has_preview`` is False when
    the file is missing/invalid (a placeholder tile is returned then).
    """
    path = preview_path(entry_id)
    try:
        renderer = QtSvg.QSvgRenderer(path)
    except Exception:  # unreadable/corrupt file — fall back
        renderer = None
    if renderer is None or not renderer.isValid():
        return _placeholder_pixmap(), False
    pix = QtGui.QPixmap(THUMB_W, THUMB_H)
    pix.fill(QtGui.QColor(TILE_BG))
    painter = QtGui.QPainter(pix)
    try:
        # Letterbox: previews vary in aspect (auto-sized pages), the
        # tile is fixed — scale to fit without distortion.
        view = renderer.viewBoxF()
        if view.isValid() and view.width() > 0 and view.height() > 0:
            scale = min(THUMB_W / view.width(), THUMB_H / view.height())
            w, h = view.width() * scale, view.height() * scale
            target = QtCore.QRectF((THUMB_W - w) / 2.0,
                                    (THUMB_H - h) / 2.0, w, h)
        else:
            target = QtCore.QRectF(0, 0, THUMB_W, THUMB_H)
        renderer.render(painter, target)
    finally:
        painter.end()
    return pix, True


# ----------------------------------------------------------------------
# Card
# ----------------------------------------------------------------------

class DrawCard(QtWidgets.QFrame):
    """One command: thumbnail, syntax, description, two insert buttons."""

    def __init__(self, entry: CatalogEntry, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.setObjectName('draw-card')
        self.setProperty('entry-id', entry.id)
        self.setProperty('group', entry.group)
        self.setFixedWidth(CARD_WIDTH)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.thumb = QtWidgets.QLabel(self)
        self.thumb.setObjectName('draw-thumbnail')
        self.thumb.setFixedSize(THUMB_W, THUMB_H)
        self.thumb.setAlignment(QtCore.Qt.AlignCenter)
        # Fixed light tile in both themes: previews stay legible in
        # dark mode without inverting the rendered figure.
        self.thumb.setStyleSheet(
            f'QLabel {{ background-color: {TILE_BG}; '
            f'border: 1px solid {PLACEHOLDER_BORDER}; }}')
        pixmap, has_preview = render_thumbnail(entry.id)
        self.thumb.setPixmap(pixmap)
        self.thumb.setProperty('has-preview', has_preview)
        self.thumb.setAccessibleName(
            f'Preview of *{entry.command}' if has_preview
            else f'No preview for *{entry.command}')
        layout.addWidget(self.thumb, 0, QtCore.Qt.AlignHCenter)

        title = QtWidgets.QLabel(entry.title, self)
        title.setObjectName('draw-card-title')
        title_font = QtGui.QFont(title.font())
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        syntax = QtWidgets.QLabel(entry.syntax, self)
        syntax.setObjectName('draw-card-syntax')
        syntax.setWordWrap(True)
        mono = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
        syntax.setFont(mono)
        syntax.setToolTip(entry.syntax)
        layout.addWidget(syntax)

        description = QtWidgets.QLabel(entry.description, self)
        description.setObjectName('draw-card-description')
        description.setWordWrap(True)
        description.setToolTip(f'{entry.syntax}\n{entry.description}')
        layout.addWidget(description)

        buttons = QtWidgets.QHBoxLayout()
        buttons.setSpacing(6)
        self.example_btn = QtWidgets.QPushButton('Insert example', self)
        self.example_btn.setObjectName('insert-example')
        self.example_btn.setAccessibleName(f'Insert {entry.title} example')
        self.example_btn.setToolTip(f'Insert the example *draw block for *{entry.command}')
        buttons.addWidget(self.example_btn)

        self.command_btn = QtWidgets.QPushButton('Insert command…', self)
        self.command_btn.setObjectName('insert-command')
        self.command_btn.setAccessibleName(f'Insert *{entry.command} command')
        if entry.symbol:
            self.command_btn.setToolTip(
                f'Open the parameter dialog for *{entry.command}')
        else:
            # No geo-* dialog in the registry (e.g. equal-angle).
            self.command_btn.setEnabled(False)
            self.command_btn.setToolTip(
                f'No parameter dialog for *{entry.command} yet — '
                'use Insert example')
        buttons.addWidget(self.command_btn)
        layout.addLayout(buttons)
        layout.addStretch(1)


# ----------------------------------------------------------------------
# Dialog
# ----------------------------------------------------------------------

class DrawGalleryDialog(QtWidgets.QDialog):
    """Non-modal browser for every geometry command.

    One instance is reused per MainWindow; presentational only — the
    host window connects the signals to its own insertion code.
    """

    exampleRequested = QtCore.Signal(str)
    commandRequested = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(False)
        self.setObjectName('drawGalleryDialog')
        self.setWindowTitle('*draw — Geometry Gallery')
        self.resize(820, 560)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(6)

        self.search = QtWidgets.QLineEdit(self)
        self.search.setObjectName('draw-gallery-search')
        self.search.setPlaceholderText('Search commands…')
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName('Search geometry commands')
        self.search.setToolTip(
            'Filter by command, title or description (e.g. "perp")')
        header.addWidget(self.search, 1)

        self.group_combo = QtWidgets.QComboBox(self)
        self.group_combo.setObjectName('draw-gallery-group')
        self.group_combo.setAccessibleName('Filter by group')
        self.group_combo.addItem('All')
        for group in GROUPS:
            self.group_combo.addItem(group)
        header.addWidget(self.group_combo)

        self.empty_btn = QtWidgets.QPushButton('Insert empty block', self)
        self.empty_btn.setObjectName('draw-gallery-empty')
        self.empty_btn.setAccessibleName('Insert empty draw block')
        self.empty_btn.setToolTip(
            'Insert a minimal *draw block (the old *draw button behavior)')
        self.empty_btn.clicked.connect(self._emit_empty_block)
        header.addWidget(self.empty_btn)
        layout.addLayout(header)

        self.status = QtWidgets.QLabel('', self)
        self.status.setObjectName('draw-gallery-status')
        self.status.setAccessibleName('Visible command count')
        layout.addWidget(self.status)

        self.scroll = QtWidgets.QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarAsNeeded)
        layout.addWidget(self.scroll, 1)

        self._container = QtWidgets.QWidget(self.scroll)
        self._grid = QtWidgets.QGridLayout(self._container)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(8)
        self._grid.setVerticalSpacing(8)
        self._grid.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        self.scroll.setWidget(self._container)

        self._cards: dict[str, DrawCard] = {}
        self.search.textChanged.connect(self._rebuild)
        self.group_combo.currentTextChanged.connect(self._rebuild)
        self._rebuild()

    # -- public helpers (used by tests) --------------------------------

    @property
    def cards(self) -> dict[str, DrawCard]:
        return dict(self._cards)

    def visible_ids(self) -> list[str]:
        """Entry ids currently shown, in catalog order."""
        return [entry.id for entry in catalog_entries()
                if entry.id in self._cards]

    def card_for(self, entry_id: str) -> DrawCard | None:
        return self._cards.get(entry_id)

    def matches(self, entry: CatalogEntry) -> bool:
        """True when *entry* passes the current search + group filter."""
        group = self.group_combo.currentText()
        if group not in ('', 'All') and entry.group != group:
            return False
        query = self.search.text().strip().lower()
        if not query:
            return True
        return query in entry.search_text

    # -- internals ----------------------------------------------------

    def _clear_grid(self):
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

    def _rebuild(self, *_args):
        self._clear_grid()
        self._cards = {}
        row = col = 0
        for entry in CATALOG:
            if not self.matches(entry):
                continue
            card = DrawCard(entry, self._container)
            card.example_btn.clicked.connect(
                lambda _checked=False, e=entry: self.exampleRequested.emit(
                    e.example))
            if entry.symbol:
                card.command_btn.clicked.connect(
                    lambda _checked=False, s=entry.symbol:
                    self.commandRequested.emit(s))
            self._grid.addWidget(card, row, col)
            self._cards[entry.id] = card
            col += 1
            if col >= GRID_COLUMNS:
                col = 0
                row += 1
        # Push any leftover row against the left edge.
        if self._cards and col > 0:
            spacer = QtWidgets.QWidget(self._container)
            spacer.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                 QtWidgets.QSizePolicy.Preferred)
            self._grid.addWidget(spacer, row, col, 1,
                                 GRID_COLUMNS - col)
        shown = len(self._cards)
        total = len(CATALOG)
        self.status.setText(
            f'{shown} of {total} commands' if shown != total
            else f'{total} commands')
        if shown == 0:
            empty = QtWidgets.QLabel(
                'No command matches your search.', self._container)
            empty.setObjectName('draw-gallery-no-match')
            self._grid.addWidget(empty, 0, 0)

    def _emit_empty_block(self):
        """The old *draw button's insert, offered inside the gallery."""
        from .symbol_registry import get_symbol
        try:
            text = get_symbol('draw-skeleton').insert_text or ''
        except KeyError:  # pragma: no cover - registry always has it
            text = ''
        if text:
            self.exampleRequested.emit(text)

    def raise_and_activate(self):
        """Bring an already-open instance to the front."""
        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()
