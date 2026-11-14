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
    asset.write_bytes(b'installer')
    temp_dir = tmp_path / 'work'
    temp_dir.mkdir()
    plan = build_update_plan(
        version='7.1.0', method=method, asset_path=str(asset),
        temp_dir=str(temp_dir),
        relaunch_argv=relaunch if relaunch is not None else ['/opt/app/app'],
        pid=4242, wait_timeout=30, macos=macos,
        state_path=state_path or str(tmp_path / 'state.json'),
        log_path=log_path or str(tmp_path / 'update.log'),
        install_log_path=str(tmp_path / 'installer.log'))
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
    assert argv[1:] == ['/SILENT', '/SP-', '/NORESTART', '/CLOSEAPPLICATIONS',
                        '/RESTARTAPPLICATIONS', '/LOG=/tmp/log dir/i.log']


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


def test_windows_helper_success(tmp_path):
    plan = _make_plan(tmp_path, relaunch=['C:\\App\\easy-math-editor.exe'])
    seen = []

    def relaunch(argv):
        seen.append(argv)

    result = apply_update(plan, wait_pid_exit_fn=lambda p, t: True,
                          run_cmd=lambda argv: 0, relaunch=relaunch)
    assert result == 0
    assert seen == [['C:\\App\\easy-math-editor.exe']]
    assert not os.path.isdir(plan['temp_dir'])


def test_windows_helper_failure_keeps_old_and_reports(tmp_path):
    plan = _make_plan(tmp_path, relaunch=['C:\\App\\easy-math-editor.exe'])

    def run_cmd(argv):
        return 5

    seen = []
    result = apply_update(plan, wait_pid_exit_fn=lambda p, t: True,
                          run_cmd=run_cmd,
                          relaunch=lambda argv: seen.append(argv))
    assert result == 1
    assert seen == [['C:\\App\\easy-math-editor.exe']]  # old app relaunched
    from compiler.update import last_update_error

    err = last_update_error(plan['state_path'])
    assert err is not None
    assert 'exited with 5' in err['reason']
    assert err['log_path'] == plan['log_path']
    log = _read_log(plan['log_path'])
    assert 'installer exited with 5' in log


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
    from compiler.update import record_update_error, last_update_error

    plan = _make_plan(tmp_path)
    record_update_error('7.0.0', 'old failure', '/tmp/old.log',
                        plan['state_path'])
    result = apply_update(plan, wait_pid_exit_fn=lambda p, t: True,
                          run_cmd=lambda argv: 0,
                          relaunch=lambda argv: None)
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
    assert os.path.isdir(macos['new_app'])
    with open(os.path.join(macos['new_app'], 'Contents', 'MacOS',
                           'easy-math-editor'), encoding='utf-8') as handle:
        assert handle.read() == 'new-bin'


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
