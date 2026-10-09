"""Shared Qt application for editor tests (single instance per session)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pytest.fixture(scope='session')
def qapp():
    pytest.importorskip('PySide6')
    if not os.environ.get('DISPLAY'):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6 import QtWidgets
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


@pytest.fixture(scope='session', autouse=True)
def _isolated_user_config(tmp_path_factory):
    """Redirect ~/.config/ezmath to a temp dir for the test session.

    MainWindow reads/writes real user settings (recent files, theme);
    without this the suite would clobber the developer's config file.

    Qt-independent: non-editor (compiler/geometry/LSP) tests must run
    without PySide6, so this fixture never requires ``qapp`` and only
    patches ``editor.config`` when it imports cleanly. Editor tests
    that need Qt still request ``qapp`` (which skips without PySide6).
    """
    try:
        from editor import config as config_module
    except ImportError:
        yield None
        return
    home = str(tmp_path_factory.mktemp('fake-home'))
    original_home = config_module._home
    config_module._home = lambda: home
    config_module._MIGRATED = True  # never migrate the real legacy store
    try:
        yield home
    finally:
        config_module._home = original_home
