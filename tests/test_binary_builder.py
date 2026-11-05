"""Scheduling and failure handling for independent frozen entry points."""
import importlib.util
import os
from pathlib import Path
import sys
import threading
import types

import pytest

SPEC = importlib.util.spec_from_file_location(
    'binary_builder', Path(__file__).resolve().parents[1] / 'scripts/build_binaries.py')
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def test_parallel_builds_finish_before_alias(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, 'PyInstaller', types.ModuleType('PyInstaller'))
    monkeypatch.setattr(builder, 'DIST', tmp_path)
    started = threading.Barrier(2, timeout=10)
    finished = set()
    lock = threading.Lock()

    def build(name, import_line, full_pyside6, strip_binaries):
        # The first pair must overlap; a serial implementation times out.
        if name != 'easy-math-editor':
            started.wait()
        with lock:
            finished.add(name)

    assembled = []
    aliased = []

    def assemble():
        assembled.append(True)

    def alias():
        assert finished == set(builder.ENTRIES)
        aliased.append(True)

    monkeypatch.setattr(builder, '_build', build)
    monkeypatch.setattr(builder, '_assemble', assemble)
    monkeypatch.setattr(builder, '_alias', alias)
    assert builder.main(['builder', '--jobs', '2']) == 0
    assert assembled == [True]
    assert aliased == [True]


def test_failed_worker_never_creates_alias(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, 'PyInstaller', types.ModuleType('PyInstaller'))
    monkeypatch.setattr(builder, 'DIST', tmp_path)

    def fail(*args):
        raise RuntimeError('freeze failed')

    called = []
    monkeypatch.setattr(builder, '_build', fail)
    monkeypatch.setattr(builder, '_assemble', lambda: called.append('assemble'))
    monkeypatch.setattr(builder, '_alias', lambda: called.append('alias'))
    with pytest.raises(RuntimeError, match='freeze failed'):
        builder.main(['builder', '--jobs', '2'])
    assert called == []


def test_rejects_invalid_worker_count():
    with pytest.raises(SystemExit) as exc:
        builder.main(['builder', '--jobs', '0'])
    assert exc.value.code == 2


def test_entrypoint_is_stable_until_contents_change(monkeypatch, tmp_path):
    monkeypatch.setattr(builder, 'ROOT', tmp_path)
    commands = []
    monkeypatch.setattr(builder, '_run', lambda cmd, cache: commands.append(cmd))
    builder._build('easy-math-lsp', builder.ENTRIES['easy-math-lsp'], False)
    shim = Path(commands[0][3])
    stamp = shim.stat().st_mtime_ns
    builder._build('easy-math-lsp', builder.ENTRIES['easy-math-lsp'], False)
    assert commands[0] == commands[1]
    assert shim.stat().st_mtime_ns == stamp
    builder._build('easy-math-lsp', 'from other_module import main', False)
    assert 'other_module' in shim.read_text()


@pytest.mark.parametrize('value', ['0', '-1', 'invalid'])
def test_rejects_invalid_environment_jobs(monkeypatch, value):
    monkeypatch.setenv('EASYMATH_BUILD_JOBS', value)
    with pytest.raises(SystemExit) as exc:
        builder.main(['builder'])
    assert exc.value.code == 2


def test_explicit_jobs_override_environment(monkeypatch, tmp_path):
    monkeypatch.setenv('EASYMATH_BUILD_JOBS', 'invalid')
    monkeypatch.setitem(sys.modules, 'PyInstaller', types.ModuleType('PyInstaller'))
    monkeypatch.setattr(builder, 'DIST', tmp_path)
    monkeypatch.setattr(builder, '_build', lambda *args: None)
    monkeypatch.setattr(builder, '_assemble', lambda: None)
    monkeypatch.setattr(builder, '_alias', lambda: None)
    assert builder.main(['builder', '--jobs', '1']) == 0


def test_posix_alias_survives_relocation_and_rebuild(monkeypatch, tmp_path):
    if sys.platform == 'win32':
        pytest.skip('POSIX symlink alias')
    dist = tmp_path / 'dist'
    shared = dist / 'easy-math-lang'
    shared.mkdir(parents=True)
    compiler = shared / 'easy-math-lang'
    compiler.write_text('#!/bin/sh\necho alias-ok\n')
    compiler.chmod(0o755)
    monkeypatch.setattr(builder, 'DIST', dist)
    builder._alias()
    builder._alias()
    alias = shared / 'ezmath'
    assert alias.is_symlink()
    relocated = tmp_path / 'relocated'
    dist.rename(relocated)
    import subprocess
    assert subprocess.check_output([str(relocated / 'easy-math-lang' / 'ezmath')], text=True).strip() == 'alias-ok'


def test_windows_alias_replaces_old_symlink_without_overwriting_target(monkeypatch, tmp_path):
    shared = tmp_path / 'easy-math-lang'
    shared.mkdir()
    monkeypatch.setattr(builder, 'DIST', tmp_path)
    monkeypatch.setattr(builder, 'os', types.SimpleNamespace(name='nt'))
    source = shared / builder._executable('easy-math-lang')
    source.write_bytes(b'compiler')
    unrelated = tmp_path / 'unrelated'
    unrelated.write_bytes(b'preserve')
    alias = shared / builder._executable('ezmath')
    try:
        alias.symlink_to(unrelated.name)
    except OSError:
        pytest.skip('symlink privilege unavailable')
    builder._alias()
    assert not alias.is_symlink()
    assert alias.read_bytes() == source.read_bytes()
    assert unrelated.read_bytes() == b'preserve'


def test_editor_build_ships_gallery_previews_and_qtsvg(monkeypatch):
    """The frozen editor must bundle the *draw gallery assets + QtSvg."""
    import os
    commands = []
    monkeypatch.setattr(builder, '_run',
                        lambda cmd, cache: commands.append(cmd))
    builder._build('easy-math-editor', builder.ENTRIES['easy-math-editor'],
                   False)
    cmd = commands[0]
    assert 'PySide6.QtSvg' in cmd
    assert 'editor.draw_gallery' in cmd
    assert 'editor.draw_template' in cmd
    add_data = [cmd[i + 1] for i, flag in enumerate(cmd)
                if flag == '--add-data']
    assert add_data, 'editor build passes no --add-data'
    source = add_data[0].split(';' if os.name == 'nt' else ':', 1)[0]
    assert source.endswith(os.path.join('assets', 'draw_previews'))
    assert os.path.isdir(source), source
    assert any(name.endswith('.svg') for name in os.listdir(source))


# ---------------------------------------------------------------- fcitx5 bundle

def _fake_plugin(tmp_path, name='libfcitx5platforminputcontextplugin.so'):
    plugin = tmp_path / 'platforminputcontexts' / name
    plugin.parent.mkdir(parents=True, exist_ok=True)
    plugin.write_bytes(b'\x7fELF fake')
    return plugin


def _patch_linux_ime(monkeypatch, plugin, system_version, pyside6_version):
    from editor import linux_ime
    monkeypatch.setattr(linux_ime, '_find_system_plugin', lambda: plugin)
    monkeypatch.setattr(linux_ime, '_get_system_qt_version', lambda: system_version)
    monkeypatch.setattr(linux_ime, '_get_pyside6_qt_version', lambda: pyside6_version)


def test_system_fcitx5_plugin_disabled_by_default(monkeypatch, tmp_path):
    plugin = _fake_plugin(tmp_path)
    _patch_linux_ime(monkeypatch, plugin, '6.12.0', '6.12.0')
    monkeypatch.setattr(builder, '_system_fcitx5_enabled', lambda: False)
    assert builder._system_fcitx5_plugin_adddata() == []


def test_system_fcitx5_plugin_bundled_when_qt_matches(monkeypatch, tmp_path):
    plugin = _fake_plugin(tmp_path)
    _patch_linux_ime(monkeypatch, plugin, '6.12.0', '6.12.0')
    monkeypatch.setattr(builder, '_system_fcitx5_enabled', lambda: True)
    args = builder._system_fcitx5_plugin_adddata()
    assert args[0] == '--add-data'
    sep = ';' if os.name == 'nt' else ':'
    src, dest = args[1].split(sep, 1)
    assert src == str(plugin)
    assert dest == 'PySide6/Qt/plugins/platforminputcontexts'


def test_system_fcitx5_plugin_skipped_on_qt_mismatch(monkeypatch, tmp_path):
    """Rolling distro with a stale plugin: skip silently, never fail."""
    plugin = _fake_plugin(tmp_path)
    _patch_linux_ime(monkeypatch, plugin, '6.11.0', '6.12.0')
    monkeypatch.setattr(builder, '_system_fcitx5_enabled', lambda: True)
    assert builder._system_fcitx5_plugin_adddata() == []


def test_system_fcitx5_plugin_skipped_when_missing(monkeypatch, tmp_path):
    _patch_linux_ime(monkeypatch, None, '6.12.0', '6.12.0')
    monkeypatch.setattr(builder, '_system_fcitx5_enabled', lambda: True)
    assert builder._system_fcitx5_plugin_adddata() == []


def test_system_fcitx5_plugin_skipped_on_unknown_versions(monkeypatch, tmp_path):
    plugin = _fake_plugin(tmp_path)
    _patch_linux_ime(monkeypatch, plugin, None, '6.12.0')
    monkeypatch.setattr(builder, '_system_fcitx5_enabled', lambda: True)
    assert builder._system_fcitx5_plugin_adddata() == []


@pytest.mark.skipif(not sys.platform.startswith('linux'),
                    reason='the CI-built plugin path is Linux-only')
def test_ci_plugin_preferred_over_system(monkeypatch, tmp_path):
    """With EASYMATH_FCITX5_PLUGIN set, the CI-built plugin wins."""
    commands = []
    ci_plugin = _fake_plugin(tmp_path / 'ci')
    system_plugin = _fake_plugin(tmp_path / 'sys')
    monkeypatch.setenv('EASYMATH_FCITX5_PLUGIN', str(ci_plugin))
    monkeypatch.setattr(builder, '_system_fcitx5_enabled', lambda: True)
    _patch_linux_ime(monkeypatch, system_plugin, '6.12.0', '6.12.0')
    monkeypatch.setattr(builder, '_run',
                        lambda cmd, cache: commands.append(cmd))
    builder._build('easy-math-editor', builder.ENTRIES['easy-math-editor'],
                   False)
    cmd = commands[0]
    add_data = [cmd[i + 1] for i, flag in enumerate(cmd)
                if flag == '--add-data']
    sep = ';' if os.name == 'nt' else ':'
    sources = [a.split(sep, 1)[0] for a in add_data]
    assert str(ci_plugin) in sources
    assert str(system_plugin) not in sources
