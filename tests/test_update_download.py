"""Tests for the safe downloader in ``compiler.updater``.

No real network: ``urlopen`` is a fake. Covers the host allowlist,
redirect refusal, size cap/mismatch, SHA-256 verification (mismatch,
missing sums file, missing asset line), cancel mid-download, temp-dir
cleanup and ``.part`` handling.
"""

import hashlib
import json
import os
import sys
import urllib.error

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from compiler import updater as _updater  # noqa: E402
from compiler.updater import (  # noqa: E402
    DownloadCancelled,
    DownloadError,
    download_asset,
    fetch_sha256sums,
    parse_sha256sums,
    sha256_of_file,
)

ASSET_URL = ('https://github.com/duo8097/easy-math-lang/releases/download/'
             'v7.1.0/EasyMathLang-Windows-x64-Setup.exe')
SUMS_URL = ('https://github.com/duo8097/easy-math-lang/releases/download/'
            'v7.1.0/SHA256SUMS.txt')
ASSET_NAME = 'EasyMathLang-Windows-x64-Setup.exe'
PAYLOAD = b'MZ fake installer payload' * 100


def _sums_body(entries):
    """entries: list of (filename, bytes)"""
    lines = []
    for name, blob in entries:
        lines.append(f'{hashlib.sha256(blob).hexdigest()}  {name}')
    return '\n'.join(lines) + '\n'


class _FakeResponse:
    def __init__(self, body, url, headers=None, chunk_size=None):
        self._body = body
        self._url = url
        self.headers = headers or {'Content-Length': str(len(body))}
        self._closed = False
        self._pos = 0
        self._chunk_size = chunk_size or len(body) or 1

    def read(self, size=-1):
        if self._pos >= len(self._body):
            return b''
        if size is None or size < 0:
            size = len(self._body) - self._pos
        chunk = self._body[self._pos:self._pos + size]
        self._pos += len(chunk)
        return chunk

    def close(self):
        self._closed = True

    def geturl(self):
        return self._url


def _fake_urlopen(routes):
    """routes: dict url -> bytes | exception | _FakeResponse"""
    calls = []

    def _open(request, timeout=None):
        calls.append((request, timeout))
        url = request.full_url
        item = routes.get(url)
        if item is None:
            raise AssertionError(f'unexpected URL: {url}')
        if isinstance(item, Exception):
            raise item
        if isinstance(item, _FakeResponse):
            return item
        return _FakeResponse(item, url)

    _open.calls = calls
    return _open


def _routes(asset=PAYLOAD, sums=None):
    return {
        ASSET_URL: _FakeResponse(asset, ASSET_URL),
        SUMS_URL: _FakeResponse(
            sums if sums is not None else _sums_body(
                [(ASSET_NAME, asset)]).encode(),
            SUMS_URL),
    }


# --------------------------------------------------------------------------
# Host allowlist / redirects
# --------------------------------------------------------------------------

def test_download_refuses_non_allowlisted_host(tmp_path):
    opener = _fake_urlopen({})
    with pytest.raises(DownloadError, match='disallowed host'):
        download_asset('https://evil.example.com/file.exe',
                       temp_dir=str(tmp_path), urlopen=opener,
                       sha256sums_url=SUMS_URL)


def test_download_refuses_http_scheme(tmp_path):
    with pytest.raises(DownloadError, match='disallowed host'):
        download_asset('http://github.com/duo8097/easy-math-lang/'
                       'releases/download/v1/x.exe',
                       temp_dir=str(tmp_path), sha256sums_url=SUMS_URL)


def test_redirect_handler_refuses_foreign_host():
    handler = _updater._AllowlistRedirectHandler()
    with pytest.raises(DownloadError, match='disallowed host'):
        handler.redirect_request(
            None, None, 302, 'Found', {},
            'https://evil.example.com/payload.exe')


def test_redirect_handler_accepts_github_assets():
    import urllib.request

    handler = _updater._AllowlistRedirectHandler()
    req = urllib.request.Request('https://github.com/x')
    result = handler.redirect_request(
        req, None, 302, 'Found', {},
        'https://objects.githubusercontent.com/123/payload.exe')
    assert result is not None


def test_final_url_foreign_after_redirect_is_refused(tmp_path):
    """A response whose final URL left the allowlist is rejected."""
    foreign = _FakeResponse(PAYLOAD, 'https://evil.example.com/x.exe')
    opener = _fake_urlopen({ASSET_URL: foreign,
                            SUMS_URL: _FakeResponse(
                                _sums_body([(ASSET_NAME, PAYLOAD)]).encode(),
                                SUMS_URL)})
    with pytest.raises(DownloadError, match='disallowed host'):
        download_asset(ASSET_URL, dest_name=ASSET_NAME,
                       temp_dir=str(tmp_path), urlopen=opener,
                       sha256sums_url=SUMS_URL)


# --------------------------------------------------------------------------
# SHA-256 verification
# --------------------------------------------------------------------------

def test_successful_download_and_verify(tmp_path):
    opener = _fake_urlopen(_routes())
    progress = []
    result = download_asset(
        ASSET_URL, dest_name=ASSET_NAME, expected_size=len(PAYLOAD),
        sha256sums_url=SUMS_URL, temp_dir=str(tmp_path), urlopen=opener,
        progress=lambda done, total: progress.append((done, total)))
    assert os.path.isfile(result.path)
    assert result.sha256 == hashlib.sha256(PAYLOAD).hexdigest()
    assert sha256_of_file(result.path) == result.sha256
    assert progress and progress[-1][0] == len(PAYLOAD)
    # Exactly one sums GET and one asset GET.
    urls = [r.full_url for r, _ in opener.calls]
    assert ASSET_URL in urls and SUMS_URL in urls


def test_hash_mismatch_deletes_file(tmp_path):
    bad_sums = f'{"0" * 64}  {ASSET_NAME}\n'.encode()
    opener = _fake_urlopen(_routes(sums=bad_sums))
    with pytest.raises(DownloadError, match='SHA-256 mismatch'):
        download_asset(ASSET_URL, dest_name=ASSET_NAME,
                       sha256sums_url=SUMS_URL, temp_dir=str(tmp_path),
                       urlopen=opener)
    assert not os.path.exists(os.path.join(tmp_path, ASSET_NAME))
    assert not os.path.exists(os.path.join(tmp_path, ASSET_NAME + '.part'))


def test_missing_sums_file_aborts(tmp_path):
    opener = _fake_urlopen({ASSET_URL: _FakeResponse(PAYLOAD, ASSET_URL)})
    with pytest.raises(DownloadError, match='SHA256SUMS'):
        download_asset(ASSET_URL, dest_name=ASSET_NAME, temp_dir=str(tmp_path),
                       urlopen=opener, sha256sums_url=None)


def test_missing_asset_line_in_sums_aborts(tmp_path):
    other = _sums_body([('SomeoneElse.dmg', b'x')]).encode()
    opener = _fake_urlopen(_routes(sums=other))
    with pytest.raises(DownloadError, match='no entry'):
        download_asset(ASSET_URL, dest_name=ASSET_NAME,
                       sha256sums_url=SUMS_URL, temp_dir=str(tmp_path),
                       urlopen=opener)
    assert not os.path.exists(os.path.join(tmp_path, ASSET_NAME))


def test_sums_file_with_binary_marker_parses():
    blob = b'abc'
    text = f'{hashlib.sha256(blob).hexdigest()} *{ASSET_NAME}\n'
    sums = parse_sha256sums(text)
    assert sums[ASSET_NAME] == hashlib.sha256(blob).hexdigest()


# --------------------------------------------------------------------------
# Size cap / mismatch
# --------------------------------------------------------------------------

def test_content_length_over_cap_refused(tmp_path):
    huge = _FakeResponse(b'x', ASSET_URL,
                         headers={'Content-Length': str(_updater.MAX_DOWNLOAD_BYTES + 1)})
    opener = _fake_urlopen({ASSET_URL: huge})
    with pytest.raises(DownloadError, match='cap'):
        download_asset(ASSET_URL, dest_name=ASSET_NAME,
                       sha256sums_url=SUMS_URL, temp_dir=str(tmp_path),
                       urlopen=opener)


def test_api_size_disagrees_with_content_length(tmp_path):
    opener = _fake_urlopen(_routes())
    with pytest.raises(DownloadError, match='does not match'):
        download_asset(ASSET_URL, dest_name=ASSET_NAME,
                       expected_size=len(PAYLOAD) + 1,
                       sha256sums_url=SUMS_URL, temp_dir=str(tmp_path),
                       urlopen=opener)


def test_downloaded_bytes_must_match_api_size(tmp_path):
    # Server claims a small Content-Length but streams more.
    resp = _FakeResponse(PAYLOAD * 2, ASSET_URL,
                         headers={'Content-Length': str(len(PAYLOAD))})
    opener = _fake_urlopen({ASSET_URL: resp})
    with pytest.raises(DownloadError, match='expected'):
        download_asset(ASSET_URL, dest_name=ASSET_NAME,
                       expected_size=len(PAYLOAD),
                       sha256sums_url=SUMS_URL, temp_dir=str(tmp_path),
                       urlopen=opener)


# --------------------------------------------------------------------------
# Cancel / cleanup / .part
# --------------------------------------------------------------------------

def test_cancel_mid_download_cleans_up(tmp_path):
    big = b'MZ' * 300_000  # ~600 KB: several 256 KB chunks
    calls = {'n': 0}

    def should_cancel():
        calls['n'] += 1
        return calls['n'] >= 3  # cancel after a couple of chunks

    sum_body = _sums_body([(ASSET_NAME, big)]).encode()
    opener = _fake_urlopen({ASSET_URL: _FakeResponse(big, ASSET_URL),
                            SUMS_URL: _FakeResponse(sum_body, SUMS_URL)})
    with pytest.raises(DownloadCancelled):
        download_asset(ASSET_URL, dest_name=ASSET_NAME,
                       sha256sums_url=SUMS_URL, temp_dir=str(tmp_path),
                       urlopen=opener, should_cancel=should_cancel)
    assert calls['n'] >= 3  # cancel was actually consulted mid-stream
    assert not os.path.exists(os.path.join(tmp_path, ASSET_NAME + '.part'))
    assert not os.path.exists(os.path.join(tmp_path, ASSET_NAME))
    # A caller-provided temp_dir is the caller's to keep.
    assert os.path.isdir(tmp_path)


def test_fresh_temp_dir_cleanup_on_failure():
    import glob
    import tempfile

    leftovers_before = set(glob.glob(os.path.join(
        tempfile.gettempdir(), 'easymath-update-*')))
    opener = _fake_urlopen(_routes(sums=b'garbage!!!\n'))
    with pytest.raises(DownloadError):
        # No temp_dir: one is created for us and must be cleaned up.
        download_asset(ASSET_URL, dest_name=ASSET_NAME,
                       sha256sums_url=SUMS_URL, urlopen=opener)
    leftovers_after = set(glob.glob(os.path.join(
        tempfile.gettempdir(), 'easymath-update-*')))
    assert leftovers_after == leftovers_before


def test_part_suffix_and_rename_on_success(tmp_path):
    part_seen = []

    def progress(done, total):
        part = os.path.join(tmp_path, ASSET_NAME + '.part')
        if os.path.exists(part) and part not in part_seen:
            part_seen.append(part)

    opener = _fake_urlopen(_routes())
    result = download_asset(ASSET_URL, dest_name=ASSET_NAME,
                            sha256sums_url=SUMS_URL, temp_dir=str(tmp_path),
                            urlopen=opener, progress=progress)
    assert part_seen, 'the .part file must exist while downloading'
    assert not os.path.exists(os.path.join(tmp_path, ASSET_NAME + '.part'))
    assert os.path.isfile(result.path)


def test_fetch_sha256sums_404_raises(tmp_path):
    opener = _fake_urlopen({SUMS_URL: urllib.error.HTTPError(
        SUMS_URL, 404, 'Not Found', {}, None)})
    with pytest.raises(DownloadError, match='SHA256SUMS'):
        fetch_sha256sums(SUMS_URL, urlopen=opener)


def test_fetch_sha256sums_foreign_host_refused():
    with pytest.raises(DownloadError, match='disallowed host'):
        fetch_sha256sums('https://evil.example.com/SHA256SUMS.txt')
