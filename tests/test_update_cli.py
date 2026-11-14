"""Tests for `easy-math-lang --update` / `ezmath --update` (B6).

All network/installer/pkexec calls are fakes; no test touches the real
system. Covers current-vs-latest output, the notes summary, the
confirmation prompt (and --yes), download+verify flow, failure exit
codes, the unsupported-install path and the standalone-flag rules.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from compiler import update as _update  # noqa: E402
from compiler import updater as _updater  # noqa: E402
from compiler.update import ReleaseInfo, ReleaseAsset  # noqa: E402
from compiler.updater import (  # noqa: E402
    METHOD_MACOS,
    METHOD_SOURCE,
    METHOD_WINDOWS,
    DownloadCancelled,
    DownloadError,
    DownloadResult,
    InstallInfo,
    run_self_update,
)

TAG_URL = 'https://github.com/duo8097/easy-math-lang/releases/tag/v7.1.0'
ASSET = ReleaseAsset('EasyMathLang-Windows-x64-Setup.exe',
                     'https://github.com/x/EasyMathLang-Windows-x64-Setup.exe',
                     50 * 1024 * 1024)
SUMS = ReleaseAsset('SHA256SUMS.txt',
                    'https://github.com/x/SHA256SUMS.txt', 256)


def _release_payload(version='7.1.0', prerelease=False, with_sums=True):
    assets = [{'name': ASSET.name, 'browser_download_url': ASSET.download_url,
               'size': ASSET.size}]
    if with_sums:
        assets.append({'name': 'SHA256SUMS.txt',
                       'browser_download_url': SUMS.download_url,
                       'size': 256})
    return {
        'tag_name': f'v{version}',
        'html_url': TAG_URL,
        'body': 'Big new release with fixes.',
        'prerelease': prerelease,
        'published_at': '2026-11-13T10:00:00Z',
        'assets': assets,
    }


def _fake_urlopen(payload):
    body = json.dumps(payload).encode()

    class _Resp:
        def __init__(self):
            self.headers = {'Content-Length': str(len(body))}

        def read(self):
            return body

        def close(self):
            pass

    def _open(request, timeout=None):
        return _Resp()

    return _open


def _fake_download(result=None, exc=None):
    calls = []

    def _download(url, dest_name=None, *, expected_size=None,
                  sha256sums_url=None, temp_dir=None, progress=None,
                  should_cancel=None, urlopen=None):
        calls.append({'url': url, 'dest_name': dest_name,
                      'expected_size': expected_size,
                      'sha256sums_url': sha256sums_url})
        if progress:
            progress(10, 100)
            progress(100, 100)
        if exc is not None:
            raise exc
        temp_dir = temp_dir or _default_tmp()
        os.makedirs(temp_dir, exist_ok=True)
        path = os.path.join(temp_dir, dest_name)
        with open(path, 'wb') as handle:
            handle.write(b'downloaded')
        return result or DownloadResult(path=path, sha256='ab' * 32,
                                        size=100, temp_dir=temp_dir)

    _download.calls = calls
    return _download


def _default_tmp():
    import tempfile

    return tempfile.mkdtemp(prefix='easymath-test-')


def _state(tmp_path):
    return str(tmp_path / 'state.json')


def _windows_detect():
    return InstallInfo(METHOD_WINDOWS, True, 'PyInstaller bundle')


# --------------------------------------------------------------------------
# Happy path / prompt behavior
# --------------------------------------------------------------------------

def test_update_up_to_date(tmp_path, capsys, monkeypatch):
    payload = _release_payload('7.0.0')  # same as installed
    code = run_self_update(current_version='7.0.0',
                           urlopen=_fake_urlopen(payload),
                           state_path=_state(tmp_path),
                           detect_fn=_windows_detect)
    assert code == 0
    out = capsys.readouterr().out
    assert 'You are up to date.' in out


def test_update_confirmed_downloads_and_spawns_helper(tmp_path, capsys):
    download = _fake_download()
    spawns = []
    payload = _release_payload()
    code = run_self_update(current_version='7.0.0', yes=True,
                           urlopen=_fake_urlopen(payload),
                           state_path=_state(tmp_path),
                           download_fn=download,
                           detect_fn=_windows_detect,
                           spawn_fn=spawns.append)
    assert code == 0
    out = capsys.readouterr().out
    assert 'A new version is available: 7.1.0' in out
    assert TAG_URL in out
    assert 'Big new release with fixes.' in out
    assert f'Asset: {ASSET.name}' in out
    assert 'UAC' in out
    # Verification is wired: the sums URL from the same release is passed.
    assert download.calls[0]['sha256sums_url'] == SUMS.download_url
    assert len(spawns) == 1
    plan_path = spawns[0]
    with open(plan_path, encoding='utf-8') as handle:
        plan = json.load(handle)
    assert plan['version'] == '7.1.0'
    assert plan['method'] == METHOD_WINDOWS
    assert plan['relaunch_argv'] == []  # CLI never relaunches
    assert plan['pid'] == os.getpid()


def test_update_prompt_decline_does_nothing(tmp_path, capsys):
    download = _fake_download()
    spawns = []
    payload = _release_payload()
    code = run_self_update(current_version='7.0.0',
                           ask=lambda: 'n',
                           urlopen=_fake_urlopen(payload),
                           state_path=_state(tmp_path),
                           download_fn=download,
                           detect_fn=_windows_detect,
                           spawn_fn=spawns.append)
    assert code == 0
    assert 'Update cancelled.' in capsys.readouterr().out
    assert download.calls == []
    assert spawns == []


def test_update_prompt_empty_answer_is_no(tmp_path, capsys):
    payload = _release_payload()
    code = run_self_update(current_version='7.0.0',
                           ask=lambda: '',
                           urlopen=_fake_urlopen(payload),
                           state_path=_state(tmp_path),
                           detect_fn=_windows_detect)
    assert code == 0
    assert 'Update cancelled.' in capsys.readouterr().out


def test_update_prompt_eof_is_an_error(tmp_path, capsys):
    payload = _release_payload()

    def _eof():
        raise EOFError

    code = run_self_update(current_version='7.0.0',
                           ask=_eof,
                           urlopen=_fake_urlopen(payload),
                           state_path=_state(tmp_path),
                           detect_fn=_windows_detect)
    assert code == 1
    assert '--yes' in capsys.readouterr().err


def test_update_notes_summary_is_truncated(tmp_path, capsys):
    payload = _release_payload()
    payload['body'] = 'line\n' * 400  # far beyond the summary limit
    code = run_self_update(current_version='7.0.0', yes=False,
                           ask=lambda: 'n',
                           urlopen=_fake_urlopen(payload),
                           state_path=_state(tmp_path),
                           detect_fn=_windows_detect)
    assert code == 0
    out = capsys.readouterr().out
    assert '…' in out
    assert len(out.split('Release notes (summary):', 1)[1]) < len(payload['body'])


# --------------------------------------------------------------------------
# Failure paths (exit non-zero)
# --------------------------------------------------------------------------

def test_update_network_failure(tmp_path, capsys):
    import urllib.error

    def _boom(request, timeout=None):
        raise urllib.error.URLError('down')

    code = run_self_update(current_version='7.0.0', yes=True,
                           urlopen=_boom, state_path=_state(tmp_path),
                           detect_fn=_windows_detect)
    assert code == 1
    captured = capsys.readouterr()
    assert 'Could not check for updates' in captured.err
    assert 'releases' in captured.out


def test_update_unsupported_install_prints_hint(tmp_path, capsys):
    payload = _release_payload()
    download = _fake_download()
    code = run_self_update(
        current_version='7.0.0', yes=True,
        urlopen=_fake_urlopen(payload),
        state_path=_state(tmp_path),
        download_fn=download,
        detect_fn=lambda: InstallInfo(METHOD_SOURCE, False,
                                      'source/uv checkout'))
    assert code == 1
    out = capsys.readouterr().out
    assert 'git pull && uv sync' in out
    assert download.calls == []  # never attempted


def test_update_missing_sums_refuses_install(tmp_path, capsys):
    payload = _release_payload(with_sums=False)
    download = _fake_download()
    code = run_self_update(current_version='7.0.0', yes=True,
                           urlopen=_fake_urlopen(payload),
                           state_path=_state(tmp_path),
                           download_fn=download,
                           detect_fn=_windows_detect)
    assert code == 1
    out = capsys.readouterr().out
    assert 'SHA256SUMS.txt' in out
    assert download.calls == []


def test_update_download_verification_failure(tmp_path, capsys):
    download = _fake_download(
        exc=DownloadError('SHA-256 mismatch for x (expected 00, got 11)'))
    code = run_self_update(current_version='7.0.0', yes=True,
                           urlopen=_fake_urlopen(_release_payload()),
                           state_path=_state(tmp_path),
                           download_fn=download,
                           detect_fn=_windows_detect)
    assert code == 1
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert 'SHA-256 mismatch' in combined
    assert ASSET.name in captured.out  # manual asset hint printed
    assert TAG_URL in captured.out


def test_update_cancel_mid_download_is_clean_exit(tmp_path, capsys):
    download = _fake_download(exc=DownloadCancelled('download cancelled.'))
    code = run_self_update(current_version='7.0.0', yes=True,
                           urlopen=_fake_urlopen(_release_payload()),
                           state_path=_state(tmp_path),
                           download_fn=download,
                           detect_fn=_windows_detect)
    assert code == 0
    assert 'cancelled' in capsys.readouterr().out.lower()


def test_update_helper_spawn_failure(tmp_path, capsys):
    def _boom(plan_path):
        raise OSError('cannot fork')

    code = run_self_update(current_version='7.0.0', yes=True,
                           urlopen=_fake_urlopen(_release_payload()),
                           state_path=_state(tmp_path),
                           download_fn=_fake_download(),
                           detect_fn=_windows_detect,
                           spawn_fn=_boom)
    assert code == 1
    assert 'could not launch' in capsys.readouterr().err


def test_update_prerelease_not_offered_to_release_installs(tmp_path, capsys):
    payload = _release_payload('7.1.0-rc.1', prerelease=True)
    code = run_self_update(current_version='7.0.0', yes=True,
                           urlopen=_fake_urlopen(payload),
                           state_path=_state(tmp_path),
                           detect_fn=_windows_detect)
    assert code == 0
    assert 'You are up to date.' in capsys.readouterr().out


def test_update_macos_stages_bundle(tmp_path, capsys):
    prepared = []

    def fake_prepare(path, *, executable=None, version=None):
        prepared.append((path, executable, version))
        return {'target_app': '/Applications/Easy Math Lang.app',
                'new_app': '/tmp/staged.app',
                'backup': '/Applications/Easy Math Lang.app.update-backup'}

    mac_asset = ReleaseAsset('EasyMathLang-macOS-arm64.dmg',
                             'https://github.com/x/EasyMathLang-macOS-arm64.dmg',
                             60 * 1024 * 1024)
    payload = _release_payload()
    payload['assets'] = [
        {'name': mac_asset.name,
         'browser_download_url': mac_asset.download_url,
         'size': mac_asset.size},
        {'name': 'SHA256SUMS.txt',
         'browser_download_url': SUMS.download_url, 'size': 256},
    ]
    download = _fake_download()
    spawns = []
    code = run_self_update(
        current_version='7.0.0', yes=True,
        urlopen=_fake_urlopen(payload), state_path=_state(tmp_path),
        download_fn=download,
        detect_fn=lambda: InstallInfo(METHOD_MACOS, True,
                                      '/Applications/Easy Math Lang.app'),
        prepare_macos_fn=fake_prepare,
        spawn_fn=spawns.append)
    assert code == 0
    assert prepared and prepared[0][2] == '7.1.0'
    with open(spawns[0], encoding='utf-8') as handle:
        plan = json.load(handle)
    assert plan['macos']['target_app'] == '/Applications/Easy Math Lang.app'


# --------------------------------------------------------------------------
# Pipeline wiring
# --------------------------------------------------------------------------

def test_cli_update_yes_flag(monkeypatch):
    from compiler import updater as _u

    captured = {}

    def _fake(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(_u, 'run_self_update', _fake)
    from compiler import pipeline as _pipeline

    monkeypatch.setattr(sys, 'argv', ['easy-math-lang', '--update'])
    with pytest.raises(SystemExit) as exc:
        _pipeline.main()
    assert exc.value.code == 0
    assert captured == {'yes': False}

    captured.clear()
    monkeypatch.setattr(sys, 'argv', ['easy-math-lang', '--update', '--yes'])
    with pytest.raises(SystemExit) as exc:
        _pipeline.main()
    assert captured == {'yes': True}


def test_cli_update_extra_args_are_an_error(monkeypatch, capsys):
    from compiler import pipeline as _pipeline

    monkeypatch.setattr(sys, 'argv', ['easy-math-lang', '--update', 'foo'])
    with pytest.raises(SystemExit) as exc:
        _pipeline.main()
    assert exc.value.code == 2
    assert 'takes no arguments' in capsys.readouterr().err


def test_cli_update_and_yes_only(monkeypatch):
    from compiler import pipeline as _pipeline

    monkeypatch.setattr(sys, 'argv', ['easy-math-lang', '--update', '--yes', 'x'])
    with pytest.raises(SystemExit) as exc:
        _pipeline.main()
    assert exc.value.code == 2


def test_ezmath_update_alias(monkeypatch):
    """ezmath shares pipeline.main, so --update works the same there."""
    from compiler import pipeline as _pipeline
    import compiler.updater as _u

    captured = {}

    def _fake(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(_u, 'run_self_update', _fake)
    monkeypatch.setattr(sys, 'argv', ['ezmath', '--update', '--yes'])
    with pytest.raises(SystemExit) as exc:
        _pipeline.main()
    assert captured == {'yes': True}
