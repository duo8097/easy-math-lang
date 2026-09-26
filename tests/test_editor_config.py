"""Config location tests (~/.config/ezmath)."""

import os
import sys

import pytest

PySide6 = pytest.importorskip('PySide6')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from editor import config as config_module  # noqa: E402
from editor.config import (  # noqa: E402
    config_dir,
    config_file,
    default_settings,
)


@pytest.fixture()
def home_dir(tmp_path, monkeypatch):
    """Point ~/.config at a temp dir."""
    monkeypatch.setattr(config_module, '_home', lambda: str(tmp_path))
    monkeypatch.setattr(config_module, '_MIGRATED', True)  # skip migration
    return tmp_path


def test_config_paths_live_under_home_config(home_dir):
    assert config_dir() == os.path.join(str(home_dir), '.config', 'ezmath')
    assert config_file() == os.path.join(
        str(home_dir), '.config', 'ezmath', 'config.ini')


def test_default_settings_roundtrip(home_dir, qapp):
    from PySide6 import QtCore
    settings = default_settings()
    assert os.path.normcase(settings.fileName()) == \
        os.path.normcase(config_file())
    settings.setValue('theme', 'dark')
    settings.setValue('recentFiles', ['/a.ezmath', '/b.ezmath'])
    settings.sync()
    assert os.path.isfile(config_file())

    fresh = QtCore.QSettings(config_file(), QtCore.QSettings.IniFormat)
    assert fresh.value('theme') == 'dark'
    assert list(fresh.value('recentFiles')) == ['/a.ezmath', '/b.ezmath']


def test_migrate_legacy_once_copies_keys(home_dir, qapp, monkeypatch):
    from PySide6 import QtCore

    class FakeLegacy:
        def __init__(self, data):
            self._data = data

        def allKeys(self):
            return list(self._data)

        def value(self, key, default=None):
            return self._data.get(key, default)

    monkeypatch.setattr(config_module, '_MIGRATED', False)
    settings = QtCore.QSettings(config_file(), QtCore.QSettings.IniFormat)
    assert settings.allKeys() == []
    legacy = FakeLegacy({'theme': 'dark',
                         'recentFiles': ['/old.ezmath']})
    config_module._migrate_legacy_once(settings, legacy=legacy)
    assert settings.value('theme') == 'dark'
    assert list(settings.value('recentFiles')) == ['/old.ezmath']
    # Second call is a no-op even with different legacy content.
    config_module._migrate_legacy_once(
        settings, legacy=FakeLegacy({'theme': 'light'}))
    assert settings.value('theme') == 'dark'


def test_migrate_skipped_when_store_not_empty(home_dir, qapp, monkeypatch):
    from PySide6 import QtCore

    class FakeLegacy:
        def allKeys(self):
            return ['theme']

        def value(self, key, default=None):
            return 'dark'

    monkeypatch.setattr(config_module, '_MIGRATED', False)
    settings = QtCore.QSettings(config_file(), QtCore.QSettings.IniFormat)
    settings.setValue('theme', 'light')
    config_module._migrate_legacy_once(settings, legacy=FakeLegacy())
    assert settings.value('theme') == 'light'


def test_recent_reexports_default_settings():
    from editor import recent
    assert recent.default_settings is default_settings
