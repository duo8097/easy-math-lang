"""Light/dark theme for the desktop editor (app palette + editor colors).

All theme-dependent colors live here so the editor, the syntax
highlighter, and the find highlights switch together. The choice is
persisted in QSettings under ``theme`` (``'light'``/``'dark'``).
"""

from PySide6 import QtGui

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
    return palette
