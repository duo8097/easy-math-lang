"""VS Code-style command palette (Ctrl+Shift+P): fuzzy command picker."""

from PySide6 import QtCore, QtWidgets

from . import i18n
from .icons import SIZE_MENU, icon as _icon

# Command id -> icon (reuses the menu icons).
COMMAND_ICONS = {
    'file.new': 'file-new', 'file.open': 'file-open',
    'file.save': 'file-save', 'file.saveAs': 'file-save-as',
    'file.exit': 'exit', 'edit.find': 'find', 'edit.gotoLine': 'goto-line',
    'view.toggleOutline': 'outline', 'view.toggleProblems': 'problems',
    'view.togglePreview': 'preview', 'view.toggleTheme': 'theme',
    'view.zoomIn': 'zoom-in', 'view.zoomOut': 'zoom-out',
    'view.zoomReset': 'zoom-reset', 'view.chooseFont': 'font',
    'draw.gallery': 'gallery', 'build.compile': 'compile',
    'build.refreshPreview': 'refresh', 'build.restartLSP': 'refresh',
    'file.exportPdf': 'export', 'file.exportPng': 'export',
    'file.exportSvg': 'export', 'file.exportHtml': 'export',
    'file.exportTyp': 'export',
}


def fuzzy_score(query, text):
    """Subsequence match score (lower is better), or None for no match.

    Pure helper, independent of Qt: matches when every character of
    ``query`` appears in ``text`` in order (case-insensitive). Prefers
    compact matches, word starts, and shorter candidates.
    """
    query, text = query.lower(), text.lower()
    if not query:
        return 0
    pos, total_gap, first = 0, 0, None
    for char in query:
        found = text.find(char, pos)
        if found == -1:
            return None
        if first is None:
            first = found
        total_gap += found - pos
        pos = found + 1
    return first * 2 + total_gap + len(text) * 0.01


class CommandPalette(QtWidgets.QDialog):
    """Filterable command list. Emits ``commandChosen(command_id)``."""

    commandChosen = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr('palette_window.title'))
        self.setModal(True)
        self._commands = []  # (id, title, hint)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self._input = QtWidgets.QLineEdit(self)
        self._input.setPlaceholderText(
            i18n.tr('palette_window.placeholder'))
        self._input.setClearButtonEnabled(True)
        layout.addWidget(self._input)
        self._list = QtWidgets.QListWidget(self)
        layout.addWidget(self._list)

        self._input.textChanged.connect(self._refilter)
        self._input.returnPressed.connect(self._accept_current)
        self._list.itemActivated.connect(self._accept_item)
        self.resize(560, 340)
        self.setMinimumWidth(420)

    def set_commands(self, commands):
        """Set available ``(id, title, shortcut_hint)`` commands."""
        self._commands = list(commands)
        self._refilter()

    def _refilter(self):
        query = self._input.text().strip()
        scored = []
        for cmd_id, title, hint in self._commands:
            score = fuzzy_score(query, f'{title} {cmd_id}')
            if score is not None:
                scored.append((score, cmd_id, title, hint))
        scored.sort(key=lambda row: (row[0], row[2]))
        self._list.clear()
        for _, cmd_id, title, hint in scored:
            label = f'{title}\t{hint}' if hint else title
            item = QtWidgets.QListWidgetItem(label, self._list)
            item.setData(QtCore.Qt.UserRole, cmd_id)
            icon_name = COMMAND_ICONS.get(cmd_id)
            if icon_name:
                item.setIcon(_icon(icon_name, SIZE_MENU))
        if self._list.count():
            self._list.setCurrentRow(0)

    def _accept_current(self):
        item = self._list.currentItem()
        if item is not None:
            self._accept_item(item)

    def _accept_item(self, item):
        cmd_id = item.data(QtCore.Qt.UserRole)
        if not cmd_id or not isinstance(cmd_id, str):
            return
        self.accept()
        self.commandChosen.emit(cmd_id)

    def open_with(self, initial_text=''):
        self._input.setText(initial_text)
        self._input.setFocus()
        self.open()
