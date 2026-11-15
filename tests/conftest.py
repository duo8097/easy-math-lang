"""Shared Qt application for editor tests (single instance per session)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pytest.fixture(scope='session')
def qapp():
    pytest.importorskip('PySide6')
    # Force the offscreen platform for the test session. Desktop sessions
    # often export QT_QPA_PLATFORM=wayland;xcb (this machine does), which is
    # not a deliberate testing choice: under a real WM the Escape/cancel-
    # close assertions for dialogs cannot behave like offscreen. Qt reads
    # the platform at QApplication creation, so it must be forced here, not
    # merely defaulted. Set EZMATH_TEST_QPA_PLATFORM=xcb (etc.) to override.
    os.environ['QT_QPA_PLATFORM'] = os.environ.get(
        'EZMATH_TEST_QPA_PLATFORM', 'offscreen')
    from PySide6 import QtWidgets
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


@pytest.fixture(scope='session', autouse=True)
def _ensure_manifest(tmp_path_factory):
    import subprocess, sys
    manifest = os.path.join('src', 'editor', 'assets', 'draw_previews', 'manifest.json')
    if not os.path.isfile(manifest):
        result = subprocess.run(
            [sys.executable, 'scripts/build_draw_previews.py'],
            capture_output=True, text=True)
        # If it fails, fail loudly instead of skipping.
        assert result.returncode == 0, (
            f"build_draw_previews.py failed (manifest missing): {result.stderr}")


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
    os.environ.setdefault('EZMATH_NO_AUTO_UPDATE', '1')
    try:
        from editor import config as config_module
    except ImportError:
        config_module = None
    home = str(tmp_path_factory.mktemp('fake-home'))
    config_dir = os.path.join(home, '.config', 'ezmath')
    if config_module is not None:
        original_home = config_module._home
        config_module._home = lambda: home
        config_module._MIGRATED = True  # never migrate the real legacy store

    # The compiler's update-state file must never touch the real home
    # either (it is separate from the editor's config module path).
    try:
        from compiler import update as _update
    except ImportError:
        _update = None
    if _update is not None:
        original_default_config_dir = _update.default_config_dir
        _update.default_config_dir = lambda: config_dir

    yield config_dir if config_module is not None else None

    if config_module is not None:
        config_module._home = original_home
    if _update is not None:
        _update.default_config_dir = original_default_config_dir
