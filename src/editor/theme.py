"""Light/dark theme for the desktop editor (app palette + editor colors).

All theme-dependent colors live here so the editor, the syntax
highlighter, and the find highlights switch together. The choice is
persisted in QSettings under ``theme`` (``'light'``/``'dark'``).
"""

import os

from PySide6 import QtCore, QtGui, QtWidgets

THEME_KEY = 'theme'
LIGHT = 'light'
DARK = 'dark'


def normalize(name):
    """Canonical theme name; anything but ``'dark'`` means light."""
    return DARK if str(name or '').strip().lower() == DARK else LIGHT


def available_themes():
    return (LIGHT, DARK)


def load_theme_name(settings):
    """Read the saved theme from *settings* (defaults to light)."""
    try:
        return normalize(settings.value(THEME_KEY, LIGHT))
    except Exception:
        return LIGHT


def save_theme_name(settings, name):
    settings.setValue(THEME_KEY, normalize(name))


# Editor chrome + selection colors per theme.
EDITOR_COLORS = {
    LIGHT: {
        'editor_bg': '#ffffff',
        'editor_fg': '#000000',
        'line_bg': '#f0f0f0',
        'line_fg': '#808080',
        'current_line': '#fff9c4',
        'find_all': '#ffe082',
        'find_current': '#ffab40',
    },
    DARK: {
        'editor_bg': '#1e1e1e',
        'editor_fg': '#d4d4d4',
        'line_bg': '#252526',
        'line_fg': '#858585',
        'current_line': '#2a2d2e',
        'find_all': '#6b5e00',
        'find_current': '#d18616',
    },
}

# Syntax roles mirror EmlHighlighter's rule set (light keeps the
# existing Solarized-ish colors; dark uses VS Code-inspired ones).
SYNTAX_COLORS = {
    LIGHT: {
        'math': '#2aa198',
        'comment': '#93a1a1',
        'number': '#b58900',
        'operator': '#cb4b16',
        'variable': '#268bd2',
        'command': '#6c71c4',
    },
    DARK: {
        'math': '#4ec9b0',
        'comment': '#6a9955',
        'number': '#b5cea8',
        'operator': '#d7ba7d',
        'variable': '#9cdcfe',
        'command': '#c586c0',
    },
}


def editor_colors(name):
    return EDITOR_COLORS[normalize(name)]


def syntax_colors(name):
    return SYNTAX_COLORS[normalize(name)]


def build_palette(name):
    """App-wide QPalette for *name*; None for light (system default)."""
    if normalize(name) != DARK:
        return None
    dark_bg = QtGui.QColor('#353535')
    dark_base = QtGui.QColor('#1e1e1e')
    dark_text = QtGui.QColor('#d4d4d4')
    disabled = QtGui.QColor('#808080')
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Window, dark_bg)
    palette.setColor(QtGui.QPalette.WindowText, dark_text)
    palette.setColor(QtGui.QPalette.Base, dark_base)
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor('#252526'))
    palette.setColor(QtGui.QPalette.Text, dark_text)
    palette.setColor(QtGui.QPalette.Button, dark_bg)
    palette.setColor(QtGui.QPalette.ButtonText, dark_text)
    palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor('#264f78'))
    palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor('#ffffff'))
    palette.setColor(QtGui.QPalette.ToolTipBase, dark_base)
    palette.setColor(QtGui.QPalette.ToolTipText, dark_text)
    for role in (QtGui.QPalette.WindowText, QtGui.QPalette.Text,
                 QtGui.QPalette.ButtonText):
        palette.setColor(QtGui.QPalette.Disabled, role, disabled)
    # Placeholder ("Find", "Type a command…", editor hint text) defaults
    # to black — invisible on dark backgrounds. Set for both Active and
    # Inactive groups (Inactive does not reliably inherit Active).
    placeholder = QtGui.QColor('#a0a0a0')
    for group in (QtGui.QPalette.Active, QtGui.QPalette.Inactive,
                  QtGui.QPalette.Disabled):
        palette.setColor(group, QtGui.QPalette.PlaceholderText, placeholder)
    # Unfocused selections default to a light-gray wash that flashes
    # bright whenever focus leaves a list/editor. Keep them dark.
    palette.setColor(QtGui.QPalette.Inactive, QtGui.QPalette.Highlight,
                     QtGui.QColor('#1e3a52'))
    palette.setColor(QtGui.QPalette.Inactive,
                     QtGui.QPalette.HighlightedText, dark_text)
    return palette


# Qt draws the native Windows menu bar with the OS theme, ignoring
# QPalette — so without this the top bar stays light in dark mode.
# Applied on top of the palette when dark is active.
DARK_STYLESHEET = """
QMenuBar { background-color: #353535; color: #d4d4d4; }
QMenuBar::item { background: transparent; color: #d4d4d4; }
QMenuBar::item:selected { background-color: #264f78; color: #ffffff; }
QMenuBar::item:pressed { background-color: #264f78; color: #ffffff; }
QMenu { background-color: #353535; color: #d4d4d4; border: 1px solid #555555; }
QMenu::item:selected { background-color: #264f78; color: #ffffff; }
QMenu::item:disabled { color: #808080; background: transparent; }
QMenu::separator { background-color: #555555; height: 1px; }
QToolBar { background-color: #353535; color: #d4d4d4; border: none; }
QStatusBar { background-color: #353535; color: #d4d4d4; }
QStatusBar::item { border: none; }
QDockWidget::title { background-color: #353535; color: #d4d4d4; }
QMainWindow::separator { background-color: #555555; }
/* Scrollbars are drawn by the OS style (light on Windows) and ignore
   QPalette, so they need explicit styling or they glow white. */
QScrollBar:vertical { background: #2d2d2d; width: 12px; margin: 0px; }
QScrollBar::handle:vertical { background: #5a5a5a; min-height: 24px; border-radius: 3px; }
QScrollBar::handle:vertical:hover { background: #6e6e6e; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { background: #2d2d2d; height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: #2d2d2d; }
QScrollBar:horizontal { background: #2d2d2d; height: 12px; margin: 0px; }
QScrollBar::handle:horizontal { background: #5a5a5a; min-width: 24px; border-radius: 3px; }
QScrollBar::handle:horizontal:hover { background: #6e6e6e; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { background: #2d2d2d; width: 0px; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: #2d2d2d; }
/* PDF pages stay white (they are documents); darken the margin around them. */
QPdfView { background-color: #252526; }
QToolTip { background-color: #1e1e1e; color: #d4d4d4; border: 1px solid #555555; }
QPushButton { background-color: #444444; color: #d4d4d4; border: 1px solid #5a5a5a; padding: 4px 12px; }
QPushButton:hover { background-color: #505050; border: 1px solid #264f78; }
QPushButton:pressed { background-color: #264f78; }
QPushButton:disabled { color: #808080; background-color: #353535; }
QLineEdit, QComboBox { background-color: #1e1e1e; color: #d4d4d4; border: 1px solid #5a5a5a; selection-background-color: #264f78; selection-color: #ffffff; }
QComboBox QAbstractItemView { background-color: #1e1e1e; color: #d4d4d4; selection-background-color: #264f78; selection-color: #ffffff; }
QListView, QTreeView { background-color: #1e1e1e; color: #d4d4d4; border: 1px solid #5a5a5a; }
QListView::item:selected, QTreeView::item:selected { background-color: #264f78; color: #ffffff; }
QHeaderView::section { background-color: #353535; color: #d4d4d4; border: 1px solid #555555; padding: 2px 4px; }
QToolButton { background-color: transparent; color: #d4d4d4; border: 1px solid transparent; }
QToolButton:hover { background-color: #444444; border: 1px solid #5a5a5a; }
QToolButton:pressed { background-color: #264f78; }
QDialog, QMessageBox { background-color: #353535; color: #d4d4d4; }
QLabel { color: #d4d4d4; }
QCheckBox { color: #d4d4d4; }
"""


def stylesheet(name):
    """App-wide QSS for *name*; empty string for light (system default)."""
    return DARK_STYLESHEET if normalize(name) == DARK else ""


def set_title_bar_dark(widget, dark):
    """Switch the Windows OS title bar of *widget* (a top-level window).

    Qt cannot paint the outer title bar; on Windows 10 20H1+ the
    DWMWA_USE_IMMERSIVE_DARK_MODE attribute does. No-op on other
    platforms and never raises (headless tests just skip it).
    """
    try:
        if os.name != 'nt':
            return
        import ctypes
        hwnd = int(widget.winId())
        if not hwnd:
            return
        dwmapi = ctypes.windll.dwmapi
        value = ctypes.c_int(1 if dark else 0)
        # 20 = DWMWA_USE_IMMERSIVE_DARK_MODE (19 on older builds).
        for attr in (20, 19):
            try:
                if dwmapi.DwmSetWindowAttribute(
                        hwnd, attr, ctypes.byref(value),
                        ctypes.sizeof(value)) == 0:
                    break
            except Exception:
                continue
    except Exception:
        pass


class TitleBarThemer(QtCore.QObject):
    """App-wide event filter: dark title bar for EVERY top-level window.

    Each dialog (QMessageBox, QInputDialog, QFileDialog, SymbolDialog,
    CommandPalette...) owns its own HWND, so styling only the main
    window leaves all dialogs with a bright Windows title bar.
    """

    def __init__(self, dark=False, parent=None):
        super().__init__(parent)
        self._dark = bool(dark)

    def set_dark(self, dark):
        self._dark = bool(dark)
        app = QtWidgets.QApplication.instance()
        if app is not None:
            for w in app.topLevelWidgets():
                if w.isVisible():
                    set_title_bar_dark(w, self._dark)

    def eventFilter(self, obj, event):
        if (event.type() == QtCore.QEvent.Show
                and isinstance(obj, QtWidgets.QWidget)
                and obj.isWindow()):
            set_title_bar_dark(obj, self._dark)
        return False
