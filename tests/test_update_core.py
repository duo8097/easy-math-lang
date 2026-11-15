"""Tests for the release-info/state layer of ``compiler.update``.

No network: ``urlopen`` is a fake. Covers ReleaseInfo parsing, the
on-disk update state (corrupt/missing/24h throttle/skipped/ETag/304),
prerelease filtering, and the ``--check-update`` presentation.
"""

import json
import os
import sys
import time
import urllib.error

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from compiler import update as _update  # noqa: E402
from compiler.update import (  # noqa: E402
    ReleaseInfo,
    UpdateCheckError,
    check_for_update,
    clear_update_error,
    is_prerelease_version,
    last_update_error,
    load_state,
    parse_release_info,
    record_update_error,
    release_info_from_state,
    save_state,
    set_auto_check,
    get_auto_check,
    skip_version,
)


def _release_payload(version='7.1.0', prerelease=False):
    return {
        'tag_name': f'v{version}',
        'html_url': f'https://github.com/duo8097/easy-math-lang/releases/tag/v{version}',
        'body': 'Release notes\n\nSome details.',
        'prerelease': prerelease,
        'published_at': '2026-11-13T10:00:00Z',
        'assets': [
            {'name': 'EasyMathLang-Windows-x64-Setup.exe',
             'browser_download_url': 'https://github.com/duo8097/easy-math-lang/releases/download/v7.1.0/EasyMathLang-Windows-x64-Setup.exe',
             'size': 12345},
            {'name': 'SHA256SUMS.txt',
             'browser_download_url': 'https://github.com/duo8097/easy-math-lang/releases/download/v7.1.0/SHA256SUMS.txt',
             'size': 256},
        ],
    }


def _fake_urlopen(payload=None, exc=None, headers=None):
    calls = []

    class _Resp:
        def __init__(self, body, hdrs):
            self._body = body
            self.headers = hdrs or {}

        def read(self):
            return self._body

        def close(self):
            pass

        def geturl(self):
            return 'https://api.github.com/repos/duo8097/easy-math-lang/releases/latest'

    def _open(request, timeout=None):
        calls.append((request, timeout))
        if exc is not None:
            raise exc
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        return _Resp(body, headers)

    _open.calls = calls
    return _open


def _state(tmp_path, **overrides):
    path = tmp_path / 'state.json'
    state = _update.default_state()
    state.update(overrides)
    save_state(state, path)
    return path


# --------------------------------------------------------------------------
# ReleaseInfo parsing
# --------------------------------------------------------------------------

def test_parse_release_info_full():
    info = parse_release_info(_release_payload())
    assert info.version == '7.1.0'
    assert info.html_url.endswith('v7.1.0')
    assert 'Some details.' in info.notes
    assert info.prerelease is False
    assert info.published == '2026-11-13T10:00:00Z'
    assert [a.name for a in info.assets] == [
        'EasyMathLang-Windows-x64-Setup.exe', 'SHA256SUMS.txt']
    assert info.assets[0].size == 12345


def test_parse_release_info_notes_truncated():
    payload = _release_payload()
    payload['body'] = 'x' * 5000
    info = parse_release_info(payload)
    assert len(info.notes) <= 2001
    assert info.notes.endswith('…')


def test_release_info_state_roundtrip():
    info = parse_release_info(_release_payload())
    restored = ReleaseInfo.from_dict(info.to_dict())
    assert restored.version == info.version
    assert restored.html_url == info.html_url
    assert restored.notes == info.notes
    assert [a.name for a in restored.assets] == [a.name for a in info.assets]


def test_release_info_from_dict_tolerates_junk():
    info = ReleaseInfo.from_dict({'version': '7.1.0',
                                  'assets': [{'name': 'x'}, 'junk', {}]})
    assert info.assets == []
    with pytest.raises(UpdateCheckError):
        ReleaseInfo.from_dict({'assets': []})
    with pytest.raises(UpdateCheckError):
        ReleaseInfo.from_dict('not a dict')


def test_is_prerelease_version():
    assert is_prerelease_version('7.1.0-rc.1')
    assert is_prerelease_version('v7.1.0-rc.1')
    assert not is_prerelease_version('7.1.0')
    assert not is_prerelease_version('1.0+build')


# --------------------------------------------------------------------------
# State file
# --------------------------------------------------------------------------

def test_state_missing_file_resets_to_defaults(tmp_path):
    state = load_state(tmp_path / 'does-not-exist.json')
    assert state['last_check'] == 0.0
    assert state['latest'] is None
    assert state['auto_check'] is True
    assert state['last_update_error'] is None


def test_state_corrupt_file_resets_silently(tmp_path):
    path = tmp_path / 'state.json'
    path.write_text('{not json at all', encoding='utf-8')
    state = load_state(path)
    assert state['latest'] is None
    path.write_text('["a list, not a dict"]', encoding='utf-8')
    assert load_state(path)['latest'] is None


def test_state_roundtrip_and_prune(tmp_path):
    path = tmp_path / 'state.json'
    state = _update.default_state()
    state['etag'] = 'abc123'
    state['skipped_version'] = '7.1.0'
    state['auto_check'] = False
    assert save_state(state, path)
    loaded = load_state(path)
    assert loaded['etag'] == 'abc123'
    assert loaded['skipped_version'] == '7.1.0'
    assert loaded['auto_check'] is False


def test_save_state_into_unwritable_location_returns_false(tmp_path):
    blocker = tmp_path / 'blocker'
    blocker.write_text('not a directory', encoding='utf-8')
    assert save_state(_update.default_state(),
                      str(blocker / 'child' / 'state.json')) is False


def test_auto_check_and_skip_version(tmp_path):
    path = _state(tmp_path)
    assert get_auto_check(path) is True
    set_auto_check(False, path)
    assert get_auto_check(path) is False
    skip_version('7.1.0', path)
    assert load_state(path)['skipped_version'] == '7.1.0'
    skip_version('7.2.0-rc.1', path)
    assert load_state(path)['skipped_version'] == '7.2.0-rc.1'


def test_record_and_clear_update_error(tmp_path):
    path = _state(tmp_path)
    record_update_error('7.1.0', 'SHA-256 mismatch', '/tmp/update.log', path)
    err = last_update_error(path)
    assert err['version'] == '7.1.0'
    assert err['reason'] == 'SHA-256 mismatch'
    assert err['log_path'] == '/tmp/update.log'
    clear_update_error(path)
    assert last_update_error(path) is None
    # Clearing a clean state is a no-op (does not raise).
    clear_update_error(path)


# --------------------------------------------------------------------------
# check_for_update (interactive vs throttled, ETag/304, prerelease)
# --------------------------------------------------------------------------

def test_check_for_update_newer_and_cached(tmp_path):
    path = _state(tmp_path)
    opener = _fake_urlopen(_release_payload(), headers={'ETag': '"etag-1"'})
    result = check_for_update('7.0.0', interactive=True, urlopen=opener,
                              now=1_000_000.0, state_path=path)
    assert result.status == 'newer'
    assert result.latest.version == '7.1.0'
    assert not result.from_cache
    state = load_state(path)
    assert state['etag'] == '"etag-1"'
    assert state['last_check'] == 1_000_000.0
    assert state['latest']['version'] == '7.1.0'


def test_check_for_update_etag_304_uses_cache(tmp_path):
    path = _state(tmp_path,
                  etag='"cached-etag"',
                  last_check=0.0,
                  latest=parse_release_info(_release_payload()).to_dict())
    opener = _fake_urlopen(exc=urllib.error.HTTPError(
        'url', 304, 'Not Modified', {}, None))
    result = check_for_update('7.0.0', interactive=True, urlopen=opener,
                              now=2_000_000.0, state_path=path)
    assert result.status == 'newer'
    assert result.from_cache
    (request, _timeout), = opener.calls
    assert request.get_header('If-none-match') == '"cached-etag"'
    # The 304 refreshes last_check (so the throttle keeps working).
    assert load_state(path)['last_check'] == 2_000_000.0


def test_check_for_update_auto_throttled_to_once_per_day(tmp_path):
    path = _state(tmp_path,
                  etag='"cached-etag"',
                  last_check=1_000_000.0,
                  latest=parse_release_info(_release_payload()).to_dict())
    calls = []

    def _must_not_call(request, timeout=None):
        calls.append(request)
        raise AssertionError('automatic check must not hit the network')

    result = check_for_update('7.0.0', interactive=False,
                              urlopen=_must_not_call,
                              now=1_000_000.0 + 3600, state_path=path)
    assert result.from_cache
    assert calls == []
    assert result.status == 'newer'


def test_check_for_update_auto_runs_after_a_day(tmp_path):
    path = _state(tmp_path,
                  etag='"cached-etag"',
                  last_check=1_000_000.0,
                  latest=parse_release_info(_release_payload()).to_dict())
    opener = _fake_urlopen(exc=urllib.error.HTTPError(
        'url', 304, 'Not Modified', {}, None))
    result = check_for_update('7.0.0', interactive=False, urlopen=opener,
                              now=1_000_000.0 + 24 * 3600 + 1,
                              state_path=path)
    assert opener.calls  # network IS used again after 24h


def test_check_for_update_manual_always_hits_network(tmp_path):
    path = _state(tmp_path,
                  last_check=9_999_999.0,
                  latest=parse_release_info(_release_payload()).to_dict())
    opener = _fake_urlopen(_release_payload('7.2.0'))
    result = check_for_update('7.0.0', interactive=True, urlopen=opener,
                              now=1_000_001.0, state_path=path)
    assert opener.calls
    assert result.latest.version == '7.2.0'


def test_check_for_update_prerelease_filtered_for_release_installs(tmp_path):
    path = _state(tmp_path)
    opener = _fake_urlopen(_release_payload('7.1.0-rc.1', prerelease=True))
    result = check_for_update('7.0.0', interactive=True, urlopen=opener,
                              now=1.0, state_path=path)
    assert result.status == 'current'  # prerelease ignored


def test_check_for_update_prerelease_visible_for_prerelease_installs(tmp_path):
    path = _state(tmp_path)
    opener = _fake_urlopen(_release_payload('7.1.0-rc.1', prerelease=True))
    result = check_for_update('7.1.0-rc.0', interactive=True, urlopen=opener,
                              now=1.0, state_path=path)
    assert result.status == 'newer'


def test_check_for_update_network_error_keeps_cache(tmp_path):
    path = _state(tmp_path,
                  last_check=0.0,
                  latest=parse_release_info(_release_payload()).to_dict())
    opener = _fake_urlopen(exc=urllib.error.URLError('no route'))
    result = check_for_update('7.0.0', interactive=True, urlopen=opener,
                              now=3_000_000.0, state_path=path)
    assert result.error == 'network unavailable.'
    assert result.latest is not None  # cached copy retained


def test_check_for_update_marks_skipped_version(tmp_path):
    path = _state(tmp_path, last_check=0.0)
    skip_version('7.1.0', path)
    opener = _fake_urlopen(_release_payload())
    result = check_for_update('7.0.0', interactive=True, urlopen=opener,
                              now=1.0, state_path=path)
    assert result.skipped is True


def test_release_info_from_state_invalid(tmp_path):
    path = _state(tmp_path, latest={'assets': 'not-a-list', 'version': ''})
    assert release_info_from_state(load_state(path)) is None
    path = _state(tmp_path, latest={'version': '', 'notes': ''})
    assert release_info_from_state(load_state(path)) is None
