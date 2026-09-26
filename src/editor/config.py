"""Config location: ``~/.config/ezmath`` (INI file, all platforms).

Previously the editor used default-constructed ``QSettings`` (Windows
registry on Windows, ``~/.config/<org>/<app>`` on Linux). Everything now
lives in one explicit file — ``~/.config/ezmath/config.ini`` — holding
the recent-files list, the theme choice, and any future settings.

On first run the previous store (if any) is migrated once so existing
users keep their recent files and theme.
"""

import os

from PySide6 import QtCore

CONFIG_DIR_NAME = 'ezmath'
CONFIG_FILE_NAME = 'config.ini'

_MIGRATED = False


def _home():
    """User home directory (separate helper so tests can stub it)."""
    return os.path.expanduser('~')


def config_dir():
    """Absolute path of the ``~/.config/ezmath`` directory."""
    return os.path.join(_home(), '.config', CONFIG_DIR_NAME)


def config_file():
    """Absolute path of the INI file holding all editor settings."""
    return os.path.join(config_dir(), CONFIG_FILE_NAME)


def default_settings():
    """QSettings backed by ``~/.config/ezmath/config.ini``."""
    path = config_file()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except OSError:
        pass
    settings = QtCore.QSettings(path, QtCore.QSettings.IniFormat)
    _migrate_legacy_once(settings)
    return settings


def _migrate_legacy_once(settings, legacy=None):
    """Copy keys from the old org/app store once (existing users)."""
    global _MIGRATED
    if _MIGRATED:
        return
    _MIGRATED = True
    try:
        if settings.allKeys():
            return  # fresh settings already in use; nothing to migrate
        if legacy is None:
            legacy = QtCore.QSettings()
        keys = legacy.allKeys() or []
        if not keys:
            return
        for key in keys:
            settings.setValue(key, legacy.value(key))
        settings.sync()
    except Exception:
        pass
