"""Tests for ``compiler.update`` (update check is fully mocked: no network).

Covers: equal / newer / older versions, ``v`` prefix, ``0.10.0`` vs
``0.9.0``, malformed JSON, missing ``tag_name``, HTTP errors and
timeout/network exceptions, plus the ``--check-update`` CLI output.
"""

import json
import os
import sys
import urllib.error

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from compiler import update as _update  # noqa: E402
from compiler.update import (  # noqa: E402
    UpdateCheckError,
    check_update_status,
    compare_versions,
    extract_release_info,
    fetch_latest_release_data,
    get_latest_release_info,
    normalize_version,
    run_check_update,
)


TAG_URL = 'https://github.com/duo8097/easy-math-lang/releases/tag/v0.1.1'


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.closed = False

    def read(self):
        return self._payload

    def close(self):
        self.closed = True


def _make_urlopen(payload=None, exc=None):
    """Fake ``urlopen`` capturing (request, timeout); no real network."""
    calls = []

    def _open(request, timeout=None):
        calls.append((request, timeout))
        if exc is not None:
            raise exc
        return _FakeResponse(payload)

    _open.calls = calls
    return _open


def _json_bytes(obj):
    return json.dumps(obj).encode('utf-8')


# --------------------------------------------------------------------------
# Version normalization / comparison
# --------------------------------------------------------------------------

def test_normalize_strips_v_prefix():
    assert normalize_version('v0.1.1') == '0.1.1'
    assert normalize_version('V0.1.1') == '0.1.1'
    assert normalize_version('0.1.1') == '0.1.1'
    assert normalize_version('  v0.1.1  ') == '0.1.1'


def test_compare_equal_versions():
    assert compare_versions('0.1.0', '0.1.0') == 0
    assert compare_versions('v0.1.0', '0.1.0') == 0


def test_compare_remote_newer():
    assert compare_versions('0.1.0', '0.1.1') == -1
    assert compare_versions('0.1.0', '0.2.0') == -1
    assert compare_versions('0.1.0', '1.0.0') == -1


def test_compare_local_newer():
    assert compare_versions('0.1.1', '0.1.0') == 1
    assert compare_versions('1.0.0', '0.9.9') == 1


def test_compare_multi_digit_segments():
    # Pure string comparison would say '0.9.0' > '0.10.0'; ints must win.
    assert compare_versions('0.9.0', '0.10.0') == -1
    assert compare_versions('0.10.0', '0.9.0') == 1
    assert compare_versions('0.10.0', '0.10.0') == 0


def test_compare_uneven_length():
    assert compare_versions('0.1', '0.1.0') == 0
    assert compare_versions('1.0.0.1', '1.0.0') == 1


def test_compare_ignores_build_metadata():
    # Semver section 10: build metadata carries no precedence.
    assert compare_versions('1.0', '1.0+build') == 0
    assert compare_versions('1.0+build', '1.0') == 0
    assert compare_versions('1.0+build.1', '1.0+build.2') == 0
    assert compare_versions('1.0-rc1', '1.0+build') == -1
    assert compare_versions('1.0+build', '1.0-rc1') == 1


def test_compare_numeric_prerelease_identifiers():
    # Semver section 11: numeric identifiers compare as ints.
    assert compare_versions('1.0-rc2', '1.0-rc10') == -1
    assert compare_versions('1.0-rc10', '1.0-rc2') == 1
    assert compare_versions('1.0-a2', '1.0-a10') == -1
    assert compare_versions('1.0-alpha.2', '1.0-alpha.10') == -1
    assert compare_versions('1.0-rc1', '1.0-rc1') == 0
    assert compare_versions('1.0-rc1', '1.0') == -1
    assert compare_versions('1.0', '1.0-rc1') == 1


def test_compare_dotted_prerelease_identifiers():
    # Semver section 11: identifiers split on '.', shorter prefix first.
    assert compare_versions('1.0-rc.1', '1.0-rc1') == -1
    assert compare_versions('1.0-rc1', '1.0-rc.1') == 1
    assert compare_versions('1.0-a.b', '1.0-a-b') == -1
    assert compare_versions('1.0-alpha', '1.0-alpha.1') == -1
    assert compare_versions('1.0-alpha.1', '1.0-alpha.beta') == -1
    assert compare_versions('1.0-1', '1.0-a') == -1


def test_normalize_leaves_non_version_words_alone():
    assert normalize_version('version') == 'version'
    assert normalize_version('v') == 'v'
    assert normalize_version('') == ''
    assert normalize_version(None) == ''
    with pytest.raises(UpdateCheckError):
        compare_versions('version', '1.0.0')


# --------------------------------------------------------------------------
# Payload extraction
# --------------------------------------------------------------------------

def test_extract_release_info_with_v_prefix():
    version, url = extract_release_info(
        {'tag_name': 'v0.1.1', 'html_url': TAG_URL})
    assert version == '0.1.1'
    assert url == TAG_URL


def test_extract_release_info_without_v_prefix():
    version, url = extract_release_info(
        {'tag_name': '0.1.1', 'html_url': TAG_URL})
    assert version == '0.1.1'


def test_extract_release_info_missing_url_falls_back():
    version, url = extract_release_info({'tag_name': 'v0.2.0'})
    assert version == '0.2.0'
    assert 'github.com/duo8097/easy-math-lang' in url


def test_extract_missing_tag_name():
    with pytest.raises(UpdateCheckError):
        extract_release_info({'html_url': TAG_URL})
    with pytest.raises(UpdateCheckError):
        extract_release_info({})
    with pytest.raises(UpdateCheckError):
        extract_release_info({'tag_name': ''})
    with pytest.raises(UpdateCheckError):
        extract_release_info({'tag_name': None})


def test_extract_non_dict_payload():
    with pytest.raises(UpdateCheckError):
        extract_release_info(['v0.1.1'])


# --------------------------------------------------------------------------
# Fetch layer (mocked transport)
# --------------------------------------------------------------------------

def test_fetch_sends_get_with_timeout_and_user_agent():
    opener = _make_urlopen(_json_bytes({'tag_name': 'v0.1.1'}))
    data = fetch_latest_release_data(urlopen=opener)
    assert data == {'tag_name': 'v0.1.1'}
    (request, timeout), = opener.calls
    assert request.full_url == _update.LATEST_RELEASE_URL
    assert request.get_method() == 'GET'
    assert request.data is None  # GET only: no body sent
    assert timeout == _update.CHECK_TIMEOUT
    assert 3 <= timeout <= 5
    assert request.get_header('User-agent')


def test_fetch_malformed_json():
    opener = _make_urlopen(b'{not valid json')
    with pytest.raises(UpdateCheckError):
        fetch_latest_release_data(urlopen=opener)


def test_fetch_non_dict_json():
    opener = _make_urlopen(_json_bytes(['v0.1.1']))
    with pytest.raises(UpdateCheckError):
        fetch_latest_release_data(urlopen=opener)


def test_fetch_http_error():
    opener = _make_urlopen(exc=urllib.error.HTTPError(
        _update.LATEST_RELEASE_URL, 500, 'Server Error', {}, None))
    with pytest.raises(UpdateCheckError, match='network unavailable'):
        fetch_latest_release_data(urlopen=opener)


def test_fetch_url_error_dns():
    opener = _make_urlopen(exc=urllib.error.URLError('dns failure'))
    with pytest.raises(UpdateCheckError, match='network unavailable'):
        fetch_latest_release_data(urlopen=opener)


def test_fetch_timeout():
    opener = _make_urlopen(exc=TimeoutError('timed out'))
    with pytest.raises(UpdateCheckError, match='network unavailable'):
        fetch_latest_release_data(urlopen=opener)


def test_fetch_invalid_url_type_is_update_error():
    # Request() construction must not leak a raw ValueError to callers.
    with pytest.raises(UpdateCheckError):
        fetch_latest_release_data(url=None)
    with pytest.raises(UpdateCheckError):
        fetch_latest_release_data(url=123)


def test_get_latest_release_info_end_to_end_mocked():
    opener = _make_urlopen(
        _json_bytes({'tag_name': 'v0.1.1', 'html_url': TAG_URL}))
    assert get_latest_release_info(urlopen=opener) == ('0.1.1', TAG_URL)


# --------------------------------------------------------------------------
# Status + CLI presentation
# --------------------------------------------------------------------------

def test_status_equal_is_current():
    assert check_update_status('0.1.0', '0.1.0') == 'current'


def test_status_remote_newer():
    assert check_update_status('0.1.0', '0.1.1') == 'newer'
    assert check_update_status('0.9.0', '0.10.0') == 'newer'


def test_status_local_newer():
    assert check_update_status('0.2.0', '0.1.9') == 'ahead'


def test_run_check_update_up_to_date(capsys):
    code = run_check_update(
        current_version='0.1.0',
        fetch=lambda: ('0.1.0', TAG_URL))
    assert code == 0
    out = capsys.readouterr().out
    assert 'EasyMath Lang 0.1.0' in out
    assert 'You are up to date.' in out


def test_run_check_update_newer(capsys):
    code = run_check_update(
        current_version='0.1.0',
        fetch=lambda: ('0.1.1', TAG_URL))
    assert code == 0
    out = capsys.readouterr().out
    assert 'EasyMath Lang 0.1.0' in out
    assert 'A new version is available: 0.1.1' in out
    assert TAG_URL in out


def test_run_check_update_local_newer_still_up_to_date(capsys):
    code = run_check_update(
        current_version='0.2.0',
        fetch=lambda: ('0.1.1', TAG_URL))
    assert code == 0
    assert 'You are up to date.' in capsys.readouterr().out


def test_run_check_update_v_prefix_from_api(capsys):
    opener = _make_urlopen(
        _json_bytes({'tag_name': 'v0.1.1', 'html_url': TAG_URL}))
    code = run_check_update(
        current_version='0.1.0',
        fetch=lambda: get_latest_release_info(urlopen=opener))
    assert code == 0
    out = capsys.readouterr().out
    assert 'A new version is available: 0.1.1' in out


def test_run_check_update_network_failure_is_not_a_crash(capsys):
    def _boom():
        raise UpdateCheckError('network unavailable.')

    code = run_check_update(current_version='0.1.0', fetch=_boom)
    assert code == 0  # normal network error must not crash the CLI
    out = capsys.readouterr().out
    assert 'Could not check for updates: network unavailable.' in out


def test_run_check_update_unexpected_error_is_not_a_crash(capsys):
    def _boom():
        raise RuntimeError('weird')

    code = run_check_update(current_version='0.1.0', fetch=_boom)
    assert code == 0
    assert 'Could not check for updates:' in capsys.readouterr().out


# --------------------------------------------------------------------------
# CLI wiring (pipeline.main keeps its manual parser)
# --------------------------------------------------------------------------

def test_cli_help_mentions_check_update(monkeypatch, capsys):
    from compiler import pipeline as _pipeline

    monkeypatch.setattr(sys, 'argv', ['easy-math-lang', '--help'])
    with pytest.raises(SystemExit) as exc:
        _pipeline.main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert '--check-update' in out
    assert 'Check whether a newer EasyMath release is available' in out
    assert '--version' in out


def test_cli_version(monkeypatch, capsys):
    from compiler import pipeline as _pipeline

    monkeypatch.setattr(sys, 'argv', ['easy-math-lang', '--version'])
    with pytest.raises(SystemExit) as exc:
        _pipeline.main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert out.strip() == f'EasyMath Lang {_update.get_current_version()}'


def test_cli_check_update_newer(monkeypatch, capsys):
    from compiler import pipeline as _pipeline

    monkeypatch.setattr(sys, 'argv', ['easy-math-lang', '--check-update'])
    monkeypatch.setattr(
        _update, 'get_latest_release_info', lambda **k: ('9.9.9', TAG_URL))
    with pytest.raises(SystemExit) as exc:
        _pipeline.main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert 'A new version is available: 9.9.9' in out
    assert TAG_URL in out


def test_cli_check_update_network_failure(monkeypatch, capsys):
    from compiler import pipeline as _pipeline

    def _boom(**kwargs):
        raise UpdateCheckError('network unavailable.')

    monkeypatch.setattr(sys, 'argv', ['easy-math-lang', '--check-update'])
    monkeypatch.setattr(_update, 'get_latest_release_info', _boom)
    with pytest.raises(SystemExit) as exc:
        _pipeline.main()
    assert exc.value.code == 0
    assert 'Could not check for updates: network unavailable.' in \
        capsys.readouterr().out


def test_cli_flag_after_filename_does_not_hijack_compile(
        monkeypatch, capsys):
    """A trailing flag must not swallow the compile job (regression)."""
    from compiler import pipeline as _pipeline

    def _must_not_run(**kwargs):
        raise AssertionError('update check must not run here')

    monkeypatch.setattr(
        sys, 'argv', ['easy-math-lang', 'doc.ezmath', '--check-update'])
    monkeypatch.setattr(_update, 'get_latest_release_info', _must_not_run)
    with pytest.raises(SystemExit) as exc:
        _pipeline.main()
    # Falls through to the compile path: missing file -> failure, exit 1.
    assert exc.value.code == 1
    assert 'Cannot open input file' in capsys.readouterr().err


def test_cli_version_with_extra_arg_is_an_error(monkeypatch, capsys):
    from compiler import pipeline as _pipeline

    monkeypatch.setattr(sys, 'argv', ['easy-math-lang', '--version', 'x'])
    with pytest.raises(SystemExit) as exc:
        _pipeline.main()
    assert exc.value.code == 2
    assert 'takes no arguments' in capsys.readouterr().err


def test_cli_check_update_with_extra_arg_is_an_error(monkeypatch, capsys):
    from compiler import pipeline as _pipeline

    monkeypatch.setattr(
        sys, 'argv', ['easy-math-lang', '--check-update', 'x'])
    with pytest.raises(SystemExit) as exc:
        _pipeline.main()
    assert exc.value.code == 2
    assert 'takes no arguments' in capsys.readouterr().err


def test_cli_too_many_operands_is_an_error(monkeypatch, capsys):
    from compiler import pipeline as _pipeline

    monkeypatch.setattr(
        sys, 'argv', ['easy-math-lang', 'a.ezmath', 'b.pdf', 'c.pdf'])
    with pytest.raises(SystemExit) as exc:
        _pipeline.main()
    assert exc.value.code == 2
    assert 'too many arguments' in capsys.readouterr().err


def test_cli_double_dash_treats_flag_like_name_as_file(
        monkeypatch, capsys):
    from compiler import pipeline as _pipeline

    monkeypatch.setattr(sys, 'argv', ['easy-math-lang', '--', '--version'])
    with pytest.raises(SystemExit) as exc:
        _pipeline.main()
    # Compile path (file missing) instead of printing the version.
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert 'Cannot open input file' in captured.err
    assert 'EasyMath Lang' not in captured.out


def test_cli_bare_double_dash_is_usage_error(monkeypatch, capsys):
    from compiler import pipeline as _pipeline

    monkeypatch.setattr(sys, 'argv', ['easy-math-lang', '--'])
    with pytest.raises(SystemExit) as exc:
        _pipeline.main()
    assert exc.value.code == 1
    assert 'Usage:' in capsys.readouterr().out
