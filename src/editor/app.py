"""Easy-Math-Lang desktop editor (PySide6 + easy-math-lsp)."""

import argparse
import sys

from PySide6 import QtGui, QtWidgets

from .main_window import MainWindow


def _app_version():
    """Installed EasyMath version; literal is frozen-build fallback only."""
    try:
        from importlib.metadata import version as _dist_version

        found = _dist_version('easy-math-lang')
        if isinstance(found, str) and found.strip():
            return found.strip()
    except Exception:
        pass
    return '7.0.0'


def _set_application_icon(app):
    """Set the window/taskbar icon on the application (never raises)."""
    try:
        from .paths import icon_path

        path = icon_path()
        if path:
            icon = QtGui.QIcon(path)
            if not icon.isNull():
                app.setWindowIcon(icon)
    except Exception:
        # A missing icon must never prevent the editor from launching;
        # the default Qt icon is used instead.
        pass


# UI fonts, in preference order. Noto Sans and DejaVu Sans both cover
# Vietnamese diacritics (including stacking tone marks) on every
# platform; Qt falls back per glyph when a chosen family lacks one,
# so frozen builds need no bundled fonts — they use the system fonts
# via fontconfig (Linux), DirectWrite (Windows) or CoreText (macOS).
UI_FONT_FAMILIES = ('Noto Sans', 'DejaVu Sans', 'Segoe UI',
                    'SF Pro Text', 'Arial')


def _set_application_font(app):
    """Use a Vietnamese-capable UI font when one is installed."""
    try:
        available = set(QtGui.QFontDatabase.families())
        for family in UI_FONT_FAMILIES:
            if family in available:
                font = QtGui.QFont(family)
                app.setFont(font)
                return family
    except Exception:
        pass
    return None


def parse_args(argv=None):
    """Parse command-line arguments (``argv`` excludes the program name)."""
    parser = argparse.ArgumentParser(
        prog='easy-math-editor',
        description='Desktop editor for Easy-Math-Lang (.ezmath) files.')
    parser.add_argument('--version', action='version',
                        version=f'%(prog)s {_app_version()}')
    parser.add_argument('path', nargs='?',
                        help='optional .ezmath file to open at launch')
    parser.add_argument('--no-save-prompt', action='store_true',
                        help='close without asking to save (unsaved changes '
                             'are discarded; useful for automated tests)')
    return parser.parse_args(argv)


def main(argv=None):
    # Set up fcitx5 IME support for Linux (if applicable). This must
    # stay before QApplication creation and must not touch key
    # handling: Vietnamese typing via fcitx5 (fcitx5-lotus) depends on
    # the plugin path being set here, before any window exists.
    try:
        from .linux_ime import setup_fcitx5_ime
        setup_fcitx5_ime()
    except ImportError:
        # linux_ime.py not available (e.g., in a bundled build)
        pass

    args = parse_args(sys.argv[1:] if argv is None else argv)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(
        sys.argv if argv is None else ['easy-math-editor'])
    app.setOrganizationName('easy-math-lang')
    app.setApplicationName('easy-math-editor')
    _set_application_icon(app)
    _set_application_font(app)
    window = MainWindow(no_save_prompt=args.no_save_prompt)
    if args.path:
        window.open_path(args.path)
    window.show()
    window.maybe_show_welcome()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
