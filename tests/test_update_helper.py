"""Tests for the per-platform installers and the update helper.

No real network, installers, pkexec or system access: ``run_cmd``,
``wait_pid_exit``, ``relaunch`` and the macOS ``rename`` are fakes.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from compiler import updater as _updater  # noqa: E402
from compiler.updater import (  # noqa: E402
    METHOD_ARCH,
    METHOD_DEBIAN,
    METHOD_FEDORA,
    METHOD_MACOS,
    METHOD_WINDOWS,
    DownloadError,
    apply_update,
    arch_install_command,
    build_update_plan,
    debian_fallback_command,
    debian_install_command,
    fedora_fallback_command,
    fedora_install_command,
    load_plan,
    prepare_macos_update,
    wait_pid_exit,
    windows_setup_command,
    write_plan,
)


@pytest.fixture
def state_path(tmp_path):
    return str(tmp_path / 'update-state.json')


@pytest.fixture
def log_path(tmp_path):
    return str(tmp_path / 'update.log')


def _make_plan(tmp_path, *, method=METHOD_WINDOWS, asset_name='setup.exe',
               relaunch=None, macos=None, state_path=None, log_path=None):
    asset = tmp_path / (asset_name + '.bin')
    payload = b'installer'
    asset.write_bytes(payload)
    # mkdtemp yields a 0700 directory, exactly like production.
    import tempfile

    temp_dir = tempfile.mkdtemp(prefix='easymath-test-')
    import hashlib

    plan = build_update_plan(
        version='7.1.0', method=method, asset_path=str(asset),
        temp_dir=str(temp_dir),
        relaunch_argv=relaunch if relaunch is not None else ['/opt/app/app'],
        pid=4242, wait_timeout=30, macos=macos,
        state_path=state_path or str(tmp_path / 'state.json'),
        log_path=log_path or str(tmp_path / 'update.log'),
        install_log_path=str(tmp_path / 'installer.log'),
        asset_sha256=hashlib.sha256(payload).hexdigest(),
        asset_size=len(payload))
    return plan


def _read_log(path):
    if not os.path.isfile(path):
        return ''
    with open(path, encoding='utf-8') as handle:
        return handle.read()


# --------------------------------------------------------------------------
# Command construction (exact argv lists, paths with spaces)
# --------------------------------------------------------------------------

def test_windows_setup_command_exact_argv():
    argv = windows_setup_command('/tmp/My Dir/Setup.exe', '/tmp/log dir/i.log')
    assert argv[0] == '/tmp/My Dir/Setup.exe'
    assert argv[1:] == ['/SILENT', '/SP-', '/NORESTART', '/UPDATE=1',
                        '/LOG=/tmp/log dir/i.log']
    # Nothing from the install directory is running at install time, so
    # these flags are intentionally absent (silent force-close could
    # kill an unrelated editor instance with unsaved work).
    assert '/CLOSEAPPLICATIONS' not in argv
    assert '/RESTARTAPPLICATIONS' not in argv
    assert '/VERYSILENT' not in argv


def test_debian_commands_exact_argv():
    assert debian_install_command('/tmp/a b/f.deb') == \
        ['pkexec', 'apt-get', 'install', '-y', '/tmp/a b/f.deb']
    assert debian_fallback_command('/tmp/a b/f.deb') == \
        ['pkexec', 'dpkg', '-i', '/tmp/a b/f.deb']


def test_fedora_commands_exact_argv():
    assert fedora_install_command('/tmp/a b/f.rpm') == \
        ['pkexec', 'dnf', 'install', '-y', '/tmp/a b/f.rpm']
    assert fedora_fallback_command('/tmp/a b/f.rpm') == \
        ['pkexec', 'rpm', '-U', '/tmp/a b/f.rpm']


def test_arch_command_exact_argv():
    assert arch_install_command('/tmp/a b/f.pkg.tar.zst') == \
        ['pkexec', 'pacman', '-U', '--noconfirm', '/tmp/a b/f.pkg.tar.zst']
    # Never -Sy, never a full system upgrade.
    assert '-Sy' not in arch_install_command('/x.pkg.tar.zst')


def test_plan_default_install_log_lives_in_config_dir(monkeypatch, tmp_path):
    monkeypatch.setattr('compiler.update.default_config_dir',
                        lambda: str(tmp_path / 'cfg'))
    plan = build_update_plan(version='7.1.0', method=METHOD_WINDOWS,
                             asset_path='/x/setup.exe', temp_dir='/x',
                             relaunch_argv=[], pid=1)
    assert plan['install_log_path'] == str(tmp_path / 'cfg' / 'update-install.log')


def test_plan_roundtrip(tmp_path):
    plan = _make_plan(tmp_path)
    path = tmp_path / 'plan.json'
    write_plan(plan, str(path))
    loaded = load_plan(str(path))
    assert loaded['version'] == '7.1.0'
    assert loaded['pid'] == 4242
    assert loaded['installer'].startswith(str(tmp_path))


def test_load_plan_rejects_garbage(tmp_path):
    path = tmp_path / 'plan.json'
    path.write_text('{"foo": 1}', encoding='utf-8')
    with pytest.raises(ValueError):
        load_plan(str(path))
    path.write_text('[1, 2]', encoding='utf-8')
    with pytest.raises(ValueError):
        load_plan(str(path))


# --------------------------------------------------------------------------
# wait_pid_exit
# --------------------------------------------------------------------------

def test_wait_pid_exit_success():
    checks = iter([False, False, True])
    assert wait_pid_exit(4242, 10, _poll=lambda pid: next(checks),
                         _sleep=lambda s: None) is True


def test_wait_pid_exit_timeout():
    assert wait_pid_exit(4242, 0, _poll=lambda pid: False,
                         _sleep=lambda s: None) is False


@pytest.mark.skipif(os.name != 'posix', reason='POSIX pid semantics')
def test_default_pid_gone_posix():
    assert _updater._default_pid_gone(os.getpid()) is False
    assert _updater._default_pid_gone(2**22 + 12345) is True


# --------------------------------------------------------------------------
# Helper: PID wait gate
# --------------------------------------------------------------------------

def test_helper_aborts_when_app_never_exits(tmp_path):
    plan = _make_plan(tmp_path)
    state_path = plan['state_path']
    calls = []

    def run_cmd(argv):
        calls.append(argv)
        return 0

    result = apply_update(plan, wait_pid_exit_fn=lambda pid, timeout: False,
                          run_cmd=run_cmd, relaunch=lambda argv: None)
    assert result == 1
    assert calls == []  # installer never ran
    log = _read_log(plan['log_path'])
    assert 'did not exit' in log
    # The failure is persisted for the next editor start.
    from compiler.update import last_update_error

    err = last_update_error(state_path)
    assert err is not None
    assert 'did not exit' in err['reason']
    # The temp dir was cleaned up.
    assert not os.path.isdir(plan['temp_dir'])


# --------------------------------------------------------------------------
# Helper: success / failure per platform
# --------------------------------------------------------------------------

def _run_of(mapping):
    def run_cmd(argv):
        return mapping.get(tuple(argv), 1)
    return run_cmd


def test_windows_helper_hands_off_and_exits(tmp_path):
    plan = _make_plan(tmp_path, relaunch=['C:\\App\\easy-math-editor.exe'])
    spawned = []
    relaunched = []

    def fake_spawn(argv):
        spawned.append(list(argv))

    result = apply_update(plan, wait_pid_exit_fn=lambda p, t: True,
                          run_cmd=lambda argv: pytest.fail(
                              'the installer must not run inline'),
                          spawn_fn=fake_spawn,
                          relaunch=lambda argv: relaunched.append(argv))
    assert result == 0
    # The installer was launched detached, with /UPDATE=1 and a /LOG.
    assert len(spawned) == 1
    assert spawned[0][0] == plan['installer']
    assert '/UPDATE=1' in spawned[0]
    assert any(a.startswith('/LOG=') for a in spawned[0])
    # Relaunch happens via the Inno [Run] entry, not the helper.
    assert relaunched == []
    # The downloaded installer + plan are left in place for the
    # detached installer; the pending marker is recorded instead.
    assert os.path.isdir(plan['temp_dir'])
    from compiler.update import get_pending_update

    pending = get_pending_update(plan['state_path'])
    assert pending is not None
    assert pending['version'] == '7.1.0'
    assert pending['install_log_path'] == plan['install_log_path']
    assert pending['temp_dir'] == plan['temp_dir']


def test_windows_helper_waits_for_pid_before_spawning(tmp_path):
    plan = _make_plan(tmp_path)
    spawned = []

    result = apply_update(plan, wait_pid_exit_fn=lambda p, t: False,
                          spawn_fn=lambda argv: spawned.append(argv))
    assert result == 1
    assert spawned == []  # never launched
    from compiler.update import get_pending_update, last_update_error

    assert get_pending_update(plan['state_path']) is None
    assert 'did not exit' in last_update_error(plan['state_path'])['reason']
    assert not os.path.isdir(plan['temp_dir'])  # cleaned up


def test_windows_helper_spawn_failure_keeps_old_and_relaunches(tmp_path):
    plan = _make_plan(tmp_path, relaunch=['C:\\App\\easy-math-editor.exe'])

    def boom(argv):
        raise OSError('cannot start process')

    relaunched = []
    result = apply_update(plan, wait_pid_exit_fn=lambda p, t: True,
                          spawn_fn=boom,
                          relaunch=lambda argv: relaunched.append(argv))
    assert result == 1
    assert relaunched == [['C:\\App\\easy-math-editor.exe']]
    assert not os.path.isdir(plan['temp_dir'])  # nothing is running; clean up
    from compiler.update import get_pending_update, last_update_error

    # The installer never started, so no pending marker; the failure is
    # recorded for the next start instead.
    assert get_pending_update(plan['state_path']) is None
    assert 'could not launch' in last_update_error(plan['state_path'])['reason']


# ----------------------------------------------------------------------
# resolve_pending_update (the outcome detection on the next start)
# ----------------------------------------------------------------------

def test_resolve_pending_update_no_marker(tmp_path):
    from compiler.updater import resolve_pending_update

    assert resolve_pending_update(str(tmp_path / 'state.json')) is None


def test_resolve_pending_update_success(tmp_path):
    from compiler.update import (record_pending_update, get_pending_update,
                                 last_update_error)
    from compiler.updater import resolve_pending_update

    temp_dir = tmp_path / 'easymath-update-x'
    temp_dir.mkdir()
    state_path = str(tmp_path / 'state.json')
    record_pending_update('7.1.0', str(tmp_path / 'update-install.log'),
                          str(temp_dir), state_path)
    result = resolve_pending_update(state_path, current_version='7.1.0')
    assert result == {'ok': True, 'version': '7.1.0'}
    assert get_pending_update(state_path) is None
    assert last_update_error(state_path) is None  # success records nothing
    assert not temp_dir.exists()  # installer temp dir removed


def test_resolve_pending_update_success_with_newer_current(tmp_path):
    from compiler.update import record_pending_update
    from compiler.updater import resolve_pending_update

    state_path = str(tmp_path / 'state.json')
    record_pending_update('7.1.0', '', '', state_path)
    assert resolve_pending_update(state_path, current_version='7.2.0')['ok'] \
        is True


def test_resolve_pending_update_failure_records_error(tmp_path):
    from compiler.update import (record_pending_update,
                                 get_pending_update,
                                 last_update_error)
    from compiler.updater import resolve_pending_update

    log_path = tmp_path / 'update-install.log'
    log_path.write_text(
        'Inno Setup Log (x64)\n'
        'Attempted to use feature: ;\n'
        'Error 5: Access is denied\n', encoding='utf-8')
    temp_dir = tmp_path / 'easymath-update-y'
    temp_dir.mkdir()
    state_path = str(tmp_path / 'state.json')
    record_pending_update('7.1.0', str(log_path), str(temp_dir), state_path)
    result = resolve_pending_update(state_path, current_version='7.0.0')
    assert result['ok'] is False
    assert result['version'] == '7.1.0'
    assert 'Access is denied' in result['reason']
    assert result['log_path'] == str(log_path)
    err = last_update_error(state_path)
    assert err is not None
    assert 'Access is denied' in err['reason']
    assert err['log_path'] == str(log_path)
    assert get_pending_update(state_path) is None
    assert not temp_dir.exists()


def test_resolve_pending_update_failure_without_log(tmp_path):
    from compiler.update import record_pending_update, last_update_error
    from compiler.updater import resolve_pending_update

    state_path = str(tmp_path / 'state.json')
    missing_log = str(tmp_path / 'no-such.log')
    record_pending_update('7.1.0', missing_log, '', state_path)
    result = resolve_pending_update(state_path, current_version='7.0.0')
    assert result['ok'] is False
    assert missing_log in result['reason']
    assert 'did not complete' in last_update_error(state_path)['reason']


def test_debian_helper_uses_apt_then_succeeds(tmp_path):
    plan = _make_plan(tmp_path, method=METHOD_DEBIAN, asset_name='deb')
    calls = []

    def run_cmd(argv):
        calls.append(list(argv))
        return 0 if argv[1] == 'apt-get' else 99

    result = apply_update(plan, wait_pid_exit_fn=lambda p, t: True,
                          run_cmd=run_cmd, relaunch=lambda argv: None)
    assert result == 0
    assert calls[0][:3] == ['pkexec', 'apt-get', 'install']
    assert len(calls) == 1  # no fallback needed


def test_debian_helper_falls_back_to_dpkg(tmp_path):
    plan = _make_plan(tmp_path, method=METHOD_DEBIAN, asset_name='deb')
    calls = []

    def run_cmd(argv):
        calls.append(list(argv))
        return 1 if argv[1] == 'apt-get' else 0

    result = apply_update(plan, wait_pid_exit_fn=lambda p, t: True,
                          run_cmd=run_cmd, relaunch=lambda argv: None)
    assert result == 0
    assert [c[1] for c in calls] == ['apt-get', 'dpkg']


def test_debian_helper_both_fail(tmp_path):
    plan = _make_plan(tmp_path, method=METHOD_DEBIAN, asset_name='deb')
    result = apply_update(plan, wait_pid_exit_fn=lambda p, t: True,
                          run_cmd=lambda argv: 1,
                          relaunch=lambda argv: None)
    assert result == 1
    from compiler.update import last_update_error

    assert 'dpkg' in last_update_error(plan['state_path'])['reason']


def test_fedora_helper_dnf_then_rpm_umb(tmp_path):
    plan = _make_plan(tmp_path, method=METHOD_FEDORA, asset_name='rpm')
    calls = []

    def run_cmd(argv):
        calls.append(list(argv))
        return 1 if argv[1] == 'dnf' else 0

    result = apply_update(plan, wait_pid_exit_fn=lambda p, t: True,
                          run_cmd=run_cmd, relaunch=lambda argv: None)
    assert result == 0
    assert [c[1] for c in calls] == ['dnf', 'rpm']


def test_arch_helper_exact_argv(tmp_path):
    plan = _make_plan(tmp_path, method=METHOD_ARCH,
                      asset_name='easy-math-lang-git-7.1.0-1-x86_64.pkg.tar.zst')
    calls = []

    def run_cmd(argv):
        calls.append(list(argv))
        return 0

    result = apply_update(plan, wait_pid_exit_fn=lambda p, t: True,
                          run_cmd=run_cmd, relaunch=lambda argv: None)
    assert result == 0
    assert calls[0][:3] == ['pkexec', 'pacman', '-U']
    assert '--noconfirm' in calls[0]
    assert '-Sy' not in calls[0]


def test_arch_helper_failure_reports(tmp_path):
    plan = _make_plan(tmp_path, method=METHOD_ARCH,
                      asset_name='pkg.pkg.tar.zst')
    result = apply_update(plan, wait_pid_exit_fn=lambda p, t: True,
                          run_cmd=lambda argv: 1,
                          relaunch=lambda argv: None)
    assert result == 1
    from compiler.update import last_update_error

    assert 'pacman' in last_update_error(plan['state_path'])['reason']


def test_helper_success_clears_previous_error(tmp_path):
    """The inline (macOS) flow clears a persisted error on success."""
    from compiler.update import record_update_error, last_update_error

    plan = _make_plan(tmp_path, method=METHOD_MACOS,
                      macos={'target_app': str(tmp_path / 'app.app'),
                             'new_app': str(tmp_path / 'new.app'),
                             'backup': str(tmp_path / 'app.app.update-backup')})
    record_update_error('7.0.0', 'old failure', '/tmp/old.log',
                        plan['state_path'])
    new_app = plan['macos']['new_app']
    _make_bundle_at(new_app, 'new-bin')
    _make_bundle_at(plan['macos']['target_app'], 'old-bin')
    result = apply_update(plan, wait_pid_exit_fn=lambda p, t: True,
                          run_cmd=lambda argv: 0,
                          relaunch=lambda argv: None,
                          _rename=os.rename)
    assert result == 0
    assert last_update_error(plan['state_path']) is None


# --------------------------------------------------------------------------
# macOS swap: success and rollback
# --------------------------------------------------------------------------

def _make_bundle(root, name='Easy Math Lang.app', marker='old'):
    bundle = root / name
    macos_dir = bundle / 'Contents' / 'MacOS'
    macos_dir.mkdir(parents=True)
    (macos_dir / 'easy-math-editor').write_text(marker, encoding='utf-8')
    return str(bundle)


def _macos_plan(tmp_path):
    target = _make_bundle(tmp_path, marker='old-bin')
    new_app = str(tmp_path / '.EasyMathLang-update-deadbeef.app')
    _make_bundle_at(tmp_path / '.EasyMathLang-update-deadbeef.app', 'new-bin')
    macos = {'target_app': target, 'new_app': new_app,
             'backup': target + '.update-backup'}
    return target, new_app, macos


def _make_bundle_at(path, marker):
    macos_dir = os.path.join(path, 'Contents', 'MacOS')
    os.makedirs(macos_dir, exist_ok=True)
    with open(os.path.join(macos_dir, 'easy-math-editor'), 'w',
              encoding='utf-8') as handle:
        handle.write(marker)


def test_macos_swap_success(tmp_path):
    target, new_app, macos = _macos_plan(tmp_path)
    plan = _make_plan(tmp_path, method=METHOD_MACOS, asset_name='dmg',
                      macos=macos)
    result = apply_update(plan, wait_pid_exit_fn=lambda p, t: True,
                          relaunch=lambda argv: None, _rename=os.rename)
    assert result == 0
    with open(os.path.join(target, 'Contents', 'MacOS',
                           'easy-math-editor'), encoding='utf-8') as handle:
        assert handle.read() == 'new-bin'
    assert not os.path.exists(macos['backup'])  # backup dropped on success


def test_macos_swap_rollback_restores_old(tmp_path):
    target, new_app, macos = _macos_plan(tmp_path)
    plan = _make_plan(tmp_path, method=METHOD_MACOS, asset_name='dmg',
                      macos=macos)
    calls = []

    def flaky_rename(src, dst):
        calls.append((src, dst))
        if dst == target and src == new_app:
            raise OSError('disk is full')
        return os.rename(src, dst)

    result = apply_update(plan, wait_pid_exit_fn=lambda p, t: True,
                          relaunch=lambda argv: None, _rename=flaky_rename)
    assert result == 1
    # Old bundle is back in place with its content intact.
    with open(os.path.join(target, 'Contents', 'MacOS',
                           'easy-math-editor'), encoding='utf-8') as handle:
        assert handle.read() == 'old-bin'
    from compiler.update import last_update_error

    assert last_update_error(plan['state_path']) is not None


def test_macos_swap_missing_new_app(tmp_path):
    target = _make_bundle(tmp_path, marker='old-bin')
    macos = {'target_app': target,
             'new_app': str(tmp_path / 'does-not-exist.app'),
             'backup': target + '.update-backup'}
    plan = _make_plan(tmp_path, method=METHOD_MACOS, asset_name='dmg',
                      macos=macos)
    result = apply_update(plan, wait_pid_exit_fn=lambda p, t: True,
                          relaunch=lambda argv: None)
    assert result == 1
    with open(os.path.join(target, 'Contents', 'MacOS',
                           'easy-math-editor'), encoding='utf-8') as handle:
        assert handle.read() == 'old-bin'


# --------------------------------------------------------------------------
# prepare_macos_update (pre-quit staging)
# --------------------------------------------------------------------------

def test_prepare_macos_update_full_flow(tmp_path):
    target = _make_bundle(tmp_path / 'Applications', marker='old-bin')
    dmg = tmp_path / 'EasyMathLang-macOS-arm64.dmg'
    dmg.write_bytes(b'fake dmg')
    mountpoint_holder = {}

    def fake_run_cmd(argv):
        if argv[:2] == ['hdiutil', 'attach']:
            mountpoint = argv[argv.index('-mountpoint') + 1]
            mountpoint_holder['mp'] = mountpoint
            _make_bundle_at(
                os.path.normpath(os.path.join(mountpoint,
                                              'Easy Math Lang.app')),
                            'new-bin')
            return 0
        if argv[:2] == ['hdiutil', 'detach']:
            return 0
        return 1

    macos = prepare_macos_update(str(dmg), target_app=target,
                                 run_cmd=fake_run_cmd,
                                 temp_dir=str(tmp_path / 'stage'))
    assert macos['target_app'] == target
    assert macos['mountpoint'] == mountpoint_holder['mp']
    # The DMG stays mounted for the helper to swap and detach.
    assert macos.get('stage_dir') is None  # caller-provided temp dir
    assert os.path.isdir(macos['new_app'])
    with open(os.path.join(macos['new_app'], 'Contents', 'MacOS',
                           'easy-math-editor'), encoding='utf-8') as handle:
        assert handle.read() == 'new-bin'


def test_macos_helper_detaches_dmg_and_cleans_staging(tmp_path):
    target, new_app, macos = _macos_plan(tmp_path)
    macos['mountpoint'] = str(tmp_path / 'dmg-mount')
    stage_dir = tmp_path / 'easymath-dmg-cafe1234'
    stage_dir.mkdir()
    macos['stage_dir'] = str(stage_dir)
    plan = _make_plan(tmp_path, method=METHOD_MACOS, asset_name='dmg',
                      macos=macos)
    calls = []

    def fake_run_cmd(argv):
        calls.append(list(argv))
        return 0

    result = apply_update(plan, wait_pid_exit_fn=lambda p, t: True,
                          run_cmd=fake_run_cmd,
                          relaunch=lambda argv: None,
                          _rename=os.rename)
    assert result == 0
    assert calls and calls[0][:2] == ['hdiutil', 'detach']
    assert calls[0][2] == macos['mountpoint']
    assert not stage_dir.exists()  # staging dir cleaned up


def test_prepare_macos_update_mount_failure(tmp_path):
    dmg = tmp_path / 'x.dmg'
    dmg.write_bytes(b'fake')
    with pytest.raises(DownloadError, match='mount'):
        prepare_macos_update(str(dmg), target_app='/tmp/app.app',
                             run_cmd=lambda argv: 1,
                             temp_dir=str(tmp_path / 'stage'))


def test_prepare_macos_update_empty_dmg_is_an_error(tmp_path):
    dmg = tmp_path / 'x.dmg'
    dmg.write_bytes(b'fake')

    def fake_run_cmd(argv):
        if argv[:2] == ['hdiutil', 'attach']:
            os.makedirs(argv[argv.index('-mountpoint') + 1], exist_ok=True)
            return 0
        return 0

    with pytest.raises(DownloadError, match='no .app'):
        prepare_macos_update(str(dmg), target_app='/tmp/app.app',
                             run_cmd=fake_run_cmd,
                             temp_dir=str(tmp_path / 'stage'))


# --------------------------------------------------------------------------
# Helper CLI wiring
# --------------------------------------------------------------------------

@pytest.mark.skipif(os.name == 'nt', reason='sibling resolution is POSIX-shaped here')
def test_spawn_helper_prefers_sibling_cli(tmp_path, monkeypatch):
    bin_dir = tmp_path / 'bundle bin'  # space in the path on purpose
    bin_dir.mkdir()
    cli = bin_dir / 'easy-math-lang'
    cli.write_text('#!/bin/sh\nexit 0\n')
    cli.chmod(0o755)
    editor = bin_dir / 'easy-math-editor'
    editor.write_text('#!/bin/sh\nexit 0\n')
    editor.chmod(0o755)
    monkeypatch.setattr(sys, 'executable', str(editor))
    spawned = []

    class FakePopen:
        def __init__(self, argv, **kwargs):
            spawned.append(argv)

    monkeypatch.setattr(_updater.subprocess, 'Popen', FakePopen)
    _updater.spawn_helper('/tmp/plan with spaces.json')
    assert spawned[0][0] == str(cli)
    assert spawned[0][1:] == ['--apply-update', '/tmp/plan with spaces.json']


@pytest.mark.skipif(os.name == 'nt', reason='sibling resolution is POSIX-shaped here')
def test_spawn_helper_uses_current_cli(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, 'executable', str(tmp_path / 'easy-math-lang'))
    (tmp_path / 'easy-math-lang').write_text('#!/bin/sh\nexit 0\n')
    (tmp_path / 'easy-math-lang').chmod(0o755)
    spawned = []

    class FakePopen:
        def __init__(self, argv, **kwargs):
            spawned.append(argv)

    monkeypatch.setattr(_updater.subprocess, 'Popen', FakePopen)
    _updater.spawn_helper('/tmp/plan.json')
    assert spawned[0][0] == str(tmp_path / 'easy-math-lang')


def test_spawn_helper_missing_cli_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, 'executable',
                        str(tmp_path / 'easy-math-editor'))
    with pytest.raises(FileNotFoundError):
        _updater.spawn_helper('/tmp/plan.json')


def test_apply_update_flag_rejects_extra_args(monkeypatch, capsys):
    from compiler import pipeline as _pipeline

    monkeypatch.setattr(sys, 'argv',
                        ['easy-math-lang', '--apply-update', 'a.json', 'b.json'])
    with pytest.raises(SystemExit) as exc:
        _pipeline.main()
    assert exc.value.code == 2


def test_apply_update_flag_missing_plan_exits_2(monkeypatch, capsys):
    from compiler import pipeline as _pipeline

    monkeypatch.setattr(sys, 'argv', ['easy-math-lang', '--apply-update',
                                      '/nonexistent/plan.json'])
    with pytest.raises(SystemExit) as exc:
        _pipeline.main()
    assert exc.value.code == 2


def test_apply_update_flag_runs_helper(monkeypatch, tmp_path):
    from compiler import pipeline as _pipeline
    from compiler import updater as _u

    plan = _make_plan(tmp_path)
    path = tmp_path / 'plan.json'
    write_plan(plan, str(path))
    monkeypatch.setattr(_u, 'apply_update', lambda plan_: 0)
    monkeypatch.setattr(sys, 'argv',
                        ['easy-math-lang', '--apply-update', str(path)])
    with pytest.raises(SystemExit) as exc:
        _pipeline.main()
    assert exc.value.code == 0


# ----------------------------------------------------------------------
# TOCTOU: re-verification before the elevated install runs
# ----------------------------------------------------------------------

def test_integrity_check_refuses_tampered_content(tmp_path):
    from compiler.updater import verify_file_unchanged

    path = tmp_path / 'installer.exe'
    path.write_bytes(b'original bytes')
    import hashlib

    digest = hashlib.sha256(b'original bytes').hexdigest()
    verify_file_unchanged(str(path), digest, len(b'original bytes'))  # no raise
    path.write_bytes(b'evil bytes')
    with pytest.raises(DownloadError, match='changed after verification'):
        verify_file_unchanged(str(path), digest, len(b'original bytes'))


def test_integrity_check_refuses_size_change(tmp_path):
    from compiler.updater import verify_file_unchanged

    path = tmp_path / 'installer.exe'
    blob = b'A' * 4096
    path.write_bytes(blob + b'extra')
    import hashlib

    digest = hashlib.sha256(blob + b'extra').hexdigest()
    # Size check fires before the digest is even read.
    with pytest.raises(DownloadError, match='changed after verification'):
        verify_file_unchanged(str(path), digest, len(blob))


def test_integrity_check_refuses_symlink(tmp_path):
    from compiler.updater import verify_file_unchanged

    target = tmp_path / 'real-installer.exe'
    target.write_bytes(b'real installer')
    link = tmp_path / 'linked-installer.exe'
    link.symlink_to(target)
    import hashlib

    digest = hashlib.sha256(b'real installer').hexdigest()
    with pytest.raises(DownloadError, match='symlink'):
        verify_file_unchanged(str(link), digest, len(b'real installer'))


def test_integrity_check_refuses_missing_sha(tmp_path):
    from compiler.updater import verify_file_unchanged

    with pytest.raises(DownloadError, match='missing the verified SHA-256'):
        verify_file_unchanged('/tmp/whatever', None)


def _tamper(plan):
    with open(plan['installer'], 'wb') as handle:
        handle.write(b'swapped after verification')


def test_tampered_installer_never_reaches_windows_install(tmp_path):
    plan = _make_plan(tmp_path, relaunch=['C:\\App\\easy-math-editor.exe'])
    _tamper(plan)
    spawned = []

    result = apply_update(plan, wait_pid_exit_fn=lambda p, t: True,
                          spawn_fn=lambda argv: spawned.append(argv),
                          relaunch=lambda argv: None)
    assert result == 1
    assert spawned == []  # the installer never ran
    from compiler.update import last_update_error, get_pending_update

    assert 'changed after verification' in \
        last_update_error(plan['state_path'])['reason']
    assert get_pending_update(plan['state_path']) is None
    assert not os.path.isdir(plan['temp_dir'])


def test_tampered_installer_never_reaches_linux_install(tmp_path):
    plan = _make_plan(tmp_path, method=METHOD_DEBIAN, asset_name='deb')
    _tamper(plan)
    calls = []

    result = apply_update(plan, wait_pid_exit_fn=lambda p, t: True,
                          run_cmd=lambda argv: calls.append(argv) or 0)
    assert result == 1
    assert calls == []  # pkexec never invoked
    assert 'changed after verification' in \
        _update_error(plan['state_path'])['reason']
    assert not os.path.isdir(plan['temp_dir'])


def _update_error(state_path):
    from compiler.update import last_update_error

    return last_update_error(state_path)


def test_tampered_installer_never_reaches_macos_swap(tmp_path):
    plan = _make_plan(tmp_path, method=METHOD_MACOS, asset_name='dmg',
                      macos={'target_app': str(tmp_path / 'app.app'),
                             'new_app': str(tmp_path / 'new.app'),
                             'backup': str(tmp_path / 'app.app.update-backup')})
    _tamper(plan)
    renames = []

    result = apply_update(plan, wait_pid_exit_fn=lambda p, t: True,
                          _rename=lambda s, d: renames.append((s, d)))
    assert result == 1
    assert renames == []  # the bundle swap never ran
    assert 'changed after verification' in _update_error(plan['state_path'])['reason']
    assert not os.path.isdir(plan['temp_dir'])


def test_installer_reverified_after_the_pid_wait(tmp_path):
    """The check happens AFTER waiting (the file may be swapped during
    the 120s wait), not before it."""
    plan = _make_plan(tmp_path, method=METHOD_DEBIAN, asset_name='deb')
    swapped = {'done': False}

    def slow_wait(pid, timeout):
        with open(plan['installer'], 'wb') as handle:
            handle.write(b'swapped DURING the wait')
        swapped['done'] = True
        return True

    calls = []
    result = apply_update(plan, wait_pid_exit_fn=slow_wait,
                          run_cmd=lambda argv: calls.append(argv) or 0)
    assert swapped['done']
    assert result == 1
    assert calls == []


@pytest.mark.skipif(os.name != 'posix',
                    reason='Windows mode bits carry no group/other write meaning')
def test_load_plan_refuses_group_or_world_writable(tmp_path):
    plan = _make_plan(tmp_path)
    path = tmp_path / 'plan.json'
    write_plan(plan, str(path))
    os.chmod(path, 0o666)
    with pytest.raises(ValueError, match='writable'):
        load_plan(str(path))


def test_load_plan_refuses_plan_without_sha256(tmp_path):
    plan = _make_plan(tmp_path)
    plan.pop('sha256', None)
    path = tmp_path / 'plan.json'
    write_plan(plan, str(path))
    with pytest.raises(ValueError, match='sha256'):
        load_plan(str(path))


def test_helper_temp_dir_is_private(tmp_path):
    plan = _make_plan(tmp_path)
    if os.name == 'posix':
        assert (os.stat(plan['temp_dir']).st_mode & 0o777) == 0o700


def test_prepare_macos_update_reverifies_dmg(tmp_path):
    import hashlib
    import os as _os

    dmg = tmp_path / 'x.dmg'
    dmg.write_bytes(b'dmg bytes')
    with pytest.raises(DownloadError, match='changed after verification'):
        prepare_macos_update(str(dmg), target_app='/tmp/target.app',
                             run_cmd=lambda argv: pytest.fail(
                                 'hdiutil must not run'),
                             expected_sha256=hashlib.sha256(b'other').hexdigest(),
                             expected_size=len(b'dmg bytes'))
