"""End-to-end Linux integration tests for the fcitx5 IME setup.

Each test drives the real ``editor.linux_ime`` code path in a fresh
subprocess (not in-process mocks), with Qt's plugin debug output enabled
and the platform set to ``offscreen``. Nothing here needs a display, a
running fcitx5, or root; filesystem effects are confined to ``tmp_path``
(via ``XDG_CACHE_HOME`` and ``HOME``).

Depending on the host, the fcitx5 assertions either verify the real
plugin load or verify the graceful skip path (and then skip with the
reason). The ibus test is deterministic everywhere.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith('linux'), reason='Linux-only integration tests')

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = 'libfcitx5platforminputcontextplugin.so'

_PROBE = r"""
import os
import sys
from editor import linux_ime
print('SETUP_OK=%s' % linux_ime.setup_fcitx5_ime())
print('QT_PLUGIN_PATH=%s' % os.environ.get('QT_PLUGIN_PATH', ''))
print('QT_IM_MODULE=%s' % os.environ.get('QT_IM_MODULE', ''))
from PySide6 import QtWidgets
app = QtWidgets.QApplication(sys.argv)
print('APP_OK=1')
"""


def _base_env(tmp_path):
    return {
        'PATH': os.environ.get('PATH', '/usr/bin:/bin'),
        'HOME': str(tmp_path),
        'XDG_CACHE_HOME': str(tmp_path / 'xdg-cache'),
        'PYTHONPATH': str(REPO_ROOT / 'src'),
        'PYTHONDONTWRITEBYTECODE': '1',
        'QT_QPA_PLATFORM': 'offscreen',
        'QT_DEBUG_PLUGINS': '1',
    }


def _run_probe(tmp_path, **env_overrides):
    env = _base_env(tmp_path)
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, '-c', _PROBE],
        env=env, capture_output=True, text=True, timeout=300)


def _marker(stdout, name):
    for line in stdout.splitlines():
        if line.startswith(name + '='):
            return line[len(name) + 1:]
    return None


def _system_plugin_decision(monkeypatch):
    """Mirror the subprocess decision on this host (fresh env, no QT_PLUGIN_PATH).

    Returns (plugin, system_version, pyside6_version, usable) where usable
    means "the plugin will be selected and used".
    """
    from editor import linux_ime
    monkeypatch.delenv('QT_PLUGIN_PATH', raising=False)
    plugin = linux_ime._find_system_plugin()
    system_version = linux_ime._get_system_qt_version()
    pyside6_version = linux_ime._get_pyside6_qt_version()
    usable = (
        plugin is not None
        and system_version is not None
        and pyside6_version is not None
        and linux_ime._major_minor(system_version)
        == linux_ime._major_minor(pyside6_version)
    )
    return plugin, system_version, pyside6_version, usable


def test_fcitx_probe_loads_plugin_or_skips(tmp_path, monkeypatch):
    plugin, system_version, pyside6_version, usable = _system_plugin_decision(monkeypatch)
    proc = _run_probe(
        tmp_path,
        QT_IM_MODULE='fcitx',
        XMODIFIERS='@im=fcitx',
        GTK_IM_MODULE='fcitx',
    )
    output = proc.stdout + proc.stderr
    assert 'APP_OK=1' in proc.stdout, (
        f'editor probe did not start (rc={proc.returncode}):\n{output}')
    assert 'Traceback' not in proc.stderr

    if usable:
        loaded = [line for line in proc.stderr.splitlines()
                  if PLUGIN_NAME in line and 'loaded library' in line]
        assert loaded, (
            'expected Qt to load the matching system fcitx5 plugin, '
            f'but no load line was logged:\n{proc.stderr}')
        return

    # Skip path: a clear warning (or none at all), never a crash.
    assert ('does not match' in proc.stderr
            or 'Could not find' in proc.stderr
            or 'Could not verify' in proc.stderr
            or 'Could not determine' in proc.stderr
            or 'not match' in proc.stderr), (
        f'expected a clear skip warning, got:\n{proc.stderr}')
    pytest.skip(
        f'no fcitx5 plugin usable with PySide6 here '
        f'(system={system_version}, pyside6={pyside6_version}, plugin={plugin}); '
        'verified the skip path instead (warning + no crash)')


def test_ibus_environment_is_untouched(tmp_path):
    proc = _run_probe(
        tmp_path,
        QT_IM_MODULE='ibus',
        XMODIFIERS='@im=ibus',
        GTK_IM_MODULE='ibus',
    )
    assert 'APP_OK=1' in proc.stdout, (
        f'editor probe did not start:\n{proc.stdout}\n{proc.stderr}')
    assert _marker(proc.stdout, 'QT_IM_MODULE') == 'ibus'
    assert _marker(proc.stdout, 'QT_PLUGIN_PATH') == ''
    assert 'fcitx5 IME setup completed' not in proc.stderr


def test_fcitx_environment_untouched_when_opted_out(tmp_path):
    proc = _run_probe(
        tmp_path,
        QT_IM_MODULE='fcitx',
        XMODIFIERS='@im=fcitx',
        EZMATH_NO_IME_FIX='1',
    )
    assert 'APP_OK=1' in proc.stdout
    assert _marker(proc.stdout, 'QT_PLUGIN_PATH') == ''
    assert _marker(proc.stdout, 'QT_IM_MODULE') == 'fcitx'
