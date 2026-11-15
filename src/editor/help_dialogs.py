"""Newcomer-friendly help: welcome panel, examples, shortcut list.

Presentational only, like the draw gallery: the host window owns
insertion. The welcome panel is a dismissible banner (not a modal
dialog) so first-run help never blocks the editor or the test suite;
the host shows it once at startup via ``maybe_show_welcome``.
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from . import i18n
from .icons import SIZE_DIALOG, apply_icon

# Ready-to-run samples (English source, like every other sample in the
# repo). Short on purpose: each one compiles on its own.
EXAMPLES = (
    ('basic-math', 'examples.basic_math',
     '<width> = 5\n'
     '<area> = calc(<width> * 2)\n'
     '\n'
     'Area: <area>\n'),
    ('fraction-equation', 'examples.fraction_equation',
     '*frac(2 ; 3)\n'
     '\n'
     '*frac(x + 1 ; x - 1)\n'
     '\n'
     'Solve: *frac(x ; 2) + *frac(1 ; 3) = *frac(5 ; 6)\n'),
    ('vector', 'examples.vector',
     'Vector: *vec(3 ; 4)\n'
     '\n'
     'Length: *root(2 ; *pow(3 ; 2) + *pow(4 ; 2))\n'),
    ('simple-draw', 'examples.simple_draw',
     '*draw(\n'
     '    *point(A = 0, 0)\n'
     '    *point(B = 3, 0)\n'
     '    *point(C = 0, 4)\n'
     '    *triangle(A ; B ; C)\n'
     ')\n'),
)

# (shortcut, catalog key for the action name) transcribed from
# main_window._create_menus and editor_widget (Ctrl+Space).
SHORTCUTS = (
    ('Ctrl+N', 'shortcuts.action.new'),
    ('Ctrl+O', 'shortcuts.action.open'),
    ('Ctrl+S', 'shortcuts.action.save'),
    ('Ctrl+Shift+S', 'shortcuts.action.save_as'),
    ('Ctrl+Q', 'shortcuts.action.quit'),
    ('Ctrl+Z', 'shortcuts.action.undo'),
    ('Ctrl+Shift+Z / Ctrl+Y', 'shortcuts.action.redo'),
    ('Ctrl+X', 'shortcuts.action.cut'),
    ('Ctrl+C', 'shortcuts.action.copy'),
    ('Ctrl+V', 'shortcuts.action.paste'),
    ('Ctrl+A', 'shortcuts.action.select_all'),
    ('Ctrl+F', 'shortcuts.action.find'),
    ('F3', 'shortcuts.action.find_next'),
    ('Shift+F3', 'shortcuts.action.find_previous'),
    ('Esc', 'shortcuts.action.close_find_bar'),
    ('Ctrl+G', 'shortcuts.action.go_to_line'),
    ('Ctrl+Space', 'shortcuts.action.show_completions'),
    ('Ctrl+B', 'shortcuts.action.compile_to_pdf'),
    ('F5', 'shortcuts.action.refresh_preview'),
    ('Ctrl+Shift+V', 'shortcuts.action.toggle_live_preview'),
    ('Ctrl+Shift+D', 'shortcuts.action.toggle_dark_mode'),
    ('Ctrl+Shift+B', 'shortcuts.action.toggle_auto-close_brackets'),
    ('Ctrl+Shift+P', 'shortcuts.action.command_palette'),
    ('Ctrl+Shift+G', 'shortcuts.action.geometry_gallery'),
    ('Ctrl+= / Ctrl++', 'shortcuts.action.zoom_in'),
    ('Ctrl+-', 'shortcuts.action.zoom_out'),
    ('Ctrl+0', 'shortcuts.action.reset_zoom'),
)


def examples():
    """``(id, translated name, source)`` for every sample."""
    return [(key, i18n.tr(name_key), source)
            for key, name_key, source in EXAMPLES]


def example_source(key):
    for entry_id, _name_key, source in EXAMPLES:
        if entry_id == key:
            return source
    return ''


class WelcomePanel(QtWidgets.QFrame):
    """Dismissible first-run banner with a 3-step quick start."""

    openExampleRequested = QtCore.Signal(str)
    dismissed = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('welcomePanel')
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        self.title = QtWidgets.QLabel(self)
        self.title.setObjectName('welcome-title')
        font = self.title.font()
        font.setBold(True)
        self.title.setFont(font)
        layout.addWidget(self.title)

        self.steps = []
        for _ in range(3):
            label = QtWidgets.QLabel(self)
            label.setObjectName('welcome-step')
            label.setWordWrap(True)
            self.steps.append(label)
            layout.addWidget(label)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(6)
        self.example_btn = QtWidgets.QPushButton(self)
        self.example_btn.setObjectName('welcome-example')
        apply_icon(self.example_btn, 'examples', SIZE_DIALOG)
        self.example_btn.setMinimumHeight(32)
        self.example_btn.clicked.connect(
            lambda: self.openExampleRequested.emit('basic-math'))
        row.addWidget(self.example_btn)
        row.addStretch(1)
        self.dont_show = QtWidgets.QCheckBox(self)
        self.dont_show.setObjectName('welcome-dont-show')
        row.addWidget(self.dont_show)
        self.close_btn = QtWidgets.QPushButton(self)
        self.close_btn.setObjectName('welcome-close')
        apply_icon(self.close_btn, 'close', SIZE_DIALOG)
        self.close_btn.clicked.connect(self._on_close)
        row.addWidget(self.close_btn)
        layout.addLayout(row)
        self.retranslate_ui()

    def retranslate_ui(self):
        self.title.setText(i18n.tr('welcome.title'))
        self.steps[0].setText(i18n.tr('welcome.step1'))
        self.steps[1].setText(i18n.tr('welcome.step2'))
        self.steps[2].setText(i18n.tr('welcome.step3'))
        self.example_btn.setText(i18n.tr('welcome.open_example'))
        self.dont_show.setText(i18n.tr('welcome.dont_show'))
        self.close_btn.setText(i18n.tr('welcome.close'))

    def _on_close(self):
        if self.dont_show.isChecked():
            self.setProperty('dont-show-again', True)
        self.hide()
        self.dismissed.emit()


class ShortcutsDialog(QtWidgets.QDialog):
    """Read-only cheat sheet listing the real editor shortcuts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('shortcutsDialog')
        self.setWindowTitle(i18n.tr('shortcuts.title'))
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        heading = QtWidgets.QLabel(i18n.tr('shortcuts.heading'), self)
        font = heading.font()
        font.setBold(True)
        heading.setFont(font)
        layout.addWidget(heading)
        table = QtWidgets.QTableWidget(len(SHORTCUTS), 2, self)
        table.setHorizontalHeaderLabels([
            i18n.tr('shortcuts.header_shortcut'),
            i18n.tr('shortcuts.header_action')])
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        table.verticalHeader().setVisible(False)
        for row, (shortcut, action_key) in enumerate(SHORTCUTS):
            table.setItem(row, 0,
                          QtWidgets.QTableWidgetItem(shortcut))
            table.setItem(row, 1,
                          QtWidgets.QTableWidgetItem(i18n.tr(action_key)))
        table.horizontalHeader().setStretchLastSection(True)
        table.resizeColumnsToContents()
        layout.addWidget(table, 1)
        self.resize(520, 480)
        self.setMinimumSize(480, 360)


class AboutDialog(QtWidgets.QDialog):
    """Simple About box (version + one-line description)."""

    checkUpdatesRequested = QtCore.Signal()

    def __init__(self, version=None, parent=None):
        super().__init__(parent)
        if version is None:
            from compiler.update import get_current_version

            version = get_current_version()
        self.setObjectName('aboutDialog')
        self.setWindowTitle(i18n.tr('about.title'))
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        label = QtWidgets.QLabel(
            i18n.tr('about.text', version=version), self)
        label.setWordWrap(True)
        label.setMinimumWidth(420)
        layout.addWidget(label)
        # "Check for updates" link-style button (opens the update flow).
        self.check_button = QtWidgets.QPushButton(
            i18n.tr('about.check_updates'), self)
        self.check_button.setObjectName('about-check-updates')
        self.check_button.setFlat(True)
        self.check_button.clicked.connect(self._on_check_updates)
        layout.addWidget(self.check_button)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok, self)
        buttons.button(QtWidgets.QDialogButtonBox.Ok).setText(
            i18n.tr('about.ok'))
        apply_icon(buttons.button(QtWidgets.QDialogButtonBox.Ok),
                   'ok', SIZE_DIALOG)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _on_check_updates(self):
        self.checkUpdatesRequested.emit()
        self.accept()
