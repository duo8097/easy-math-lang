"""Easy-Math-Lang desktop editor (PySide6 + easy-math-lsp)."""

import argparse
import sys

from PySide6 import QtWidgets

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
    return '1.1.1'


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
    args = parse_args(sys.argv[1:] if argv is None else argv)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(
        sys.argv if argv is None else ['easy-math-editor'])
    app.setOrganizationName('easy-math-lang')
    app.setApplicationName('easy-math-editor')
    window = MainWindow(no_save_prompt=args.no_save_prompt)
    if args.path:
        window.open_path(args.path)
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
