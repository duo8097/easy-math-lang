"""Self-update machinery (stdlib only).

Detects how this copy of easy-math-lang was installed, picks the
matching asset from a GitHub release, and downloads it safely:

  * HTTPS only, allowlisted GitHub hosts (github.com,
    objects.githubusercontent.com, release-assets.githubusercontent.com),
    redirects to any other host are refused;
  * short connect timeout, generous read timeout;
  * size cap (1 GiB) and a size that must agree with the API's ``size``;
  * downloads to a fresh private temp dir (mode 0700) with a ``.part``
    suffix; progress callback and cancellation supported;
  * SHA-256 verified against ``SHA256SUMS.txt`` from the SAME release —
    no sums file, no asset line or a mismatch aborts with an error and
    deletes the file. There is no "skip verification" path;
  * the temp dir is cleaned up on failure and on cancel.

Every network, subprocess, platform and filesystem-location call is
injectable, so the test-suite never touches the real network, real
installers, real pkexec or the real system.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

from .update import CHECK_TIMEOUT, ReleaseAsset, ReleaseInfo, \
    USER_AGENT, normalize_version

ALLOWED_DOWNLOAD_HOSTS = frozenset({
    'github.com',
    'objects.githubusercontent.com',
    'release-assets.githubusercontent.com',
})
MAX_DOWNLOAD_BYTES = 1 << 30  # 1 GiB
MAX_SUMS_BYTES = 1 << 20      # SHA256SUMS.txt is tiny
CHUNK_SIZE = 256 * 1024
CONNECT_TIMEOUT = 10   # seconds; short so a dead network never hangs
READ_TIMEOUT = 120     # seconds; generous for big assets on slow links

METHOD_WINDOWS = 'windows'
METHOD_MACOS = 'macos'
METHOD_DEBIAN = 'debian'
METHOD_FEDORA = 'fedora'
METHOD_ARCH = 'arch'
METHOD_SOURCE = 'source'
METHOD_UNKNOWN = 'unknown'

ASSET_WINDOWS = 'EasyMathLang-Windows-x64-Setup.exe'
ASSET_MACOS = 'EasyMathLang-macOS-arm64.dmg'
ASSET_DEBIAN = 'EasyMathLang-Debian-amd64.deb'
ASSET_FEDORA = 'EasyMathLang-Fedora-amd64.rpm'
ARCH_ASSET_RE = re.compile(r'^easy-math-lang-git-.+-x86_64\.pkg\.tar\.zst$')
SHA256SUMS_NAME = 'SHA256SUMS.txt'
DEB_PACKAGE_NAME = 'easymath'   # installer/build_linux.sh (DEBIAN/control)
RPM_PACKAGE_NAME = 'easymath'   # installer/build_linux.sh (easymath.spec)
ARCH_PACKAGE_NAME = 'easy-math-lang-git'  # installer/PKGBUILD


class DownloadError(Exception):
    """Any failure while downloading or verifying an asset."""


class DownloadCancelled(DownloadError):
    """The user cancelled the download."""


def _url_allowed(url):
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False, None
    if parsed.scheme != 'https':
        return False, None
    host = (parsed.hostname or '').lower()
    if host not in ALLOWED_DOWNLOAD_HOSTS:
        return False, host
    return True, host


def _check_url(url):
    ok, host = _url_allowed(url)
    if not ok:
        raise DownloadError(
            f'refusing to download from disallowed host: {host or url!r} '
            f'(allowed: {", ".join(sorted(ALLOWED_DOWNLOAD_HOSTS))})')
    return url


class _AllowlistRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuse redirects to any host outside the allowlist."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        try:
            parsed = urllib.parse.urlparse(newurl)
        except Exception:
            raise DownloadError(f'refusing redirect to unparsable URL: '
                                f'{newurl!r}')
        host = (parsed.hostname or '').lower()
        if parsed.scheme != 'https' or host not in ALLOWED_DOWNLOAD_HOSTS:
            raise DownloadError(
                f'refusing redirect to disallowed host: {host or newurl!r}')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _default_opener():
    return urllib.request.build_opener(_AllowlistRedirectHandler())


def _open(opener_or_none, request, timeout):
    opener = opener_or_none or _default_opener()
    if callable(opener):
        return opener(request, timeout=timeout)
    return opener.open(request, timeout=timeout)


def _set_read_timeout(response):
    """Best effort: keep the connect timeout short, the read generous."""
    try:
        fp = getattr(response, 'fp', None)
        sock = getattr(fp, '_sock', None)
        if sock is not None:
            sock.settimeout(READ_TIMEOUT)
    except Exception:
        pass


def _read_all(response, limit):
    chunks = []
    read = 0
    while True:
        chunk = response.read(CHUNK_SIZE)
        if not chunk:
            break
        read += len(chunk)
        if read > limit:
            raise DownloadError(f'response exceeds the {limit}-byte cap.')
        chunks.append(chunk)
    return b''.join(chunks)


def parse_sha256sums(text):
    """Parse ``sha256sum``-format output (``<hash>  <filename>``).

    Accepts the binary-mode marker (``<hash> *<filename>``). Malformed
    lines are ignored; the caller decides whether the asset is missing.
    """
    sums = {}
    for line in (text or '').splitlines():
        match = re.match(
            r'^([0-9a-fA-F]{64})\s+\*?(.+?)\s*$', line)
        if match:
            sums[match.group(2)] = match.group(1).lower()
    return sums


def sha256_of_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b''):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_sha256sums(sums_url, *, urlopen=None, timeout=CHECK_TIMEOUT):
    """GET and parse SHA256SUMS.txt from the same release."""
    _check_url(sums_url)
    opener = urlopen or _default_opener()
    request = urllib.request.Request(
        sums_url, headers={'User-Agent': USER_AGENT,
                           'Accept': 'text/plain'})
    try:
        response = _open(opener, request, timeout)
        try:
            raw = _read_all(response, MAX_SUMS_BYTES)
        finally:
            close = getattr(response, 'close', None)
            if callable(close):
                close()
    except DownloadError:
        raise
    except Exception:
        raise DownloadError('network unavailable while fetching '
                            'SHA256SUMS.txt.')
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        raise DownloadError('SHA256SUMS.txt is not valid UTF-8.')
    return parse_sha256sums(text)


@dataclasses.dataclass
class DownloadResult:
    path: str               # final (verified) path inside the temp dir
    sha256: str
    size: int
    temp_dir: str


def _content_length(response):
    headers = getattr(response, 'headers', None)
    if headers is None:
        return None
    try:
        value = headers.get('Content-Length')
    except Exception:
        return None
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _cleanup_dir(path, created):
    if not created:
        return
    try:
        shutil.rmtree(path, ignore_errors=True)
    except OSError:
        pass


def download_asset(url, dest_name=None, *, expected_size=None,
                   sha256sums_url=None, temp_dir=None, progress=None,
                   should_cancel=None, urlopen=None):
    """Download *url* and verify it against the release's SHA256SUMS.txt.

    *url* must be an allowlisted GitHub asset host. The partial file is
    written to a fresh private temp dir with a ``.part`` suffix and is
    renamed to its final name only after the SHA-256 matches the sums
    file from the same release. ``progress(downloaded, total)`` is
    called as bytes arrive; ``should_cancel()`` is polled per chunk.

    Raises :class:`DownloadCancelled` on cancel and :class:`DownloadError`
    on any failure; the temp dir is removed in both cases.
    """
    _check_url(url)
    if dest_name is None:
        dest_name = os.path.basename(urllib.parse.urlparse(url).path)
    if not dest_name or '/' in dest_name or '\\' in dest_name:
        raise DownloadError(f'invalid asset name: {dest_name!r}')
    if sha256sums_url is None:
        raise DownloadError(
            'SHA256SUMS.txt is missing from this release — refusing to '
            'install an unverified file.')
    _check_url(sha256sums_url)

    created_dir = temp_dir is None
    tmp_dir = temp_dir or tempfile.mkdtemp(prefix='easymath-update-')
    try:
        os.chmod(tmp_dir, 0o700)
    except OSError:
        pass
    part_path = os.path.join(tmp_dir, dest_name + '.part')
    final_path = os.path.join(tmp_dir, dest_name)

    def _fail(message):
        try:
            os.unlink(part_path)
        except OSError:
            pass
        try:
            os.unlink(final_path)
        except OSError:
            pass
        if created_dir:
            _cleanup_dir(tmp_dir, True)
        raise DownloadError(message)

    try:
        opener = urlopen or _default_opener()
        request = urllib.request.Request(
            url, headers={'User-Agent': USER_AGENT,
                          'Accept': 'application/octet-stream'})
        try:
            response = _open(opener, request, CONNECT_TIMEOUT)
        except DownloadError:
            raise
        except Exception:
            _fail('network unavailable while downloading the asset.')
        try:
            _set_read_timeout(response)
            final_url = None
            geturl = getattr(response, 'geturl', None)
            if callable(geturl):
                try:
                    final_url = geturl()
                except Exception:
                    final_url = None
            if final_url:
                _check_url(final_url)
            content_length = _content_length(response)
            total = content_length
            if expected_size is not None and total is None:
                total = expected_size
            if content_length is not None and content_length > MAX_DOWNLOAD_BYTES:
                _fail(f'asset is larger than the {MAX_DOWNLOAD_BYTES}-byte '
                      f'cap.')
            if (expected_size is not None and content_length is not None
                    and content_length != expected_size):
                _fail(f'asset size on the server ({content_length} bytes) '
                      f'does not match the API size ({expected_size} bytes).')
            downloaded = 0
            with open(part_path, 'wb') as handle:
                while True:
                    if should_cancel is not None and should_cancel():
                        try:
                            os.unlink(part_path)
                        except OSError:
                            pass
                        _cleanup_dir(tmp_dir, created_dir)
                        raise DownloadCancelled('download cancelled.')
                    chunk = response.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if downloaded > MAX_DOWNLOAD_BYTES:
                        _fail(f'asset is larger than the '
                              f'{MAX_DOWNLOAD_BYTES}-byte cap.')
                    if (expected_size is not None
                            and downloaded > expected_size):
                        _fail(f'downloaded more than the expected '
                              f'{expected_size} bytes.')
                    handle.write(chunk)
                    if progress is not None:
                        try:
                            progress(downloaded, total)
                        except Exception:
                            pass
        finally:
            close = getattr(response, 'close', None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass

        if expected_size is not None and downloaded != expected_size:
            _fail(f'downloaded {downloaded} bytes, expected {expected_size}.')

        # --- verify against SHA256SUMS.txt from the SAME release ---------
        sums = fetch_sha256sums(sha256sums_url, urlopen=urlopen)
        expected_hash = sums.get(dest_name)
        if expected_hash is None:
            _fail(f'SHA256SUMS.txt has no entry for {dest_name}.')
        actual_hash = sha256_of_file(part_path)
        if actual_hash != expected_hash:
            _fail(f'SHA-256 mismatch for {dest_name} '
                  f'(expected {expected_hash}, got {actual_hash}).')

        try:
            os.replace(part_path, final_path)
        except OSError as exc:
            _fail(f'cannot move the downloaded asset into place: {exc}')
        return DownloadResult(path=final_path, sha256=actual_hash,
                              size=downloaded, temp_dir=tmp_dir)
    except DownloadCancelled:
        try:
            os.unlink(part_path)
        except OSError:
            pass
        _cleanup_dir(tmp_dir, created_dir)
        raise
    except DownloadError:
        raise
    except Exception as exc:
        try:
            os.unlink(part_path)
        except OSError:
            pass
        _cleanup_dir(tmp_dir, created_dir)
        raise DownloadError(f'download failed: {exc}')


# ----------------------------------------------------------------------
# Install-method detection
# ----------------------------------------------------------------------

@dataclasses.dataclass
class InstallInfo:
    method: str            # one of the METHOD_* constants
    one_click: bool        # a verified one-click path is provable here
    detail: str = ''       # e.g. which package manager owns the binary


def _default_run_cmd(argv):
    try:
        result = subprocess.run(argv, capture_output=True, timeout=10,
                                text=True, check=False)
        return result.returncode, (result.stdout or '') + (result.stderr or '')
    except Exception:
        return -1, ''


def _default_which(name):
    return shutil.which(name)


def _macos_bundle_for(executable):
    """Return the .app bundle path containing *executable*, or None."""
    try:
        path = os.path.realpath(executable)
    except OSError:
        path = executable
    parts = path.split(os.sep)
    for index, part in enumerate(parts):
        if part.endswith('.app'):
            bundle = os.sep.join(parts[:index + 1])
            return bundle or ('/' + bundle)
    return None


def _writable_parent(path):
    try:
        return os.access(os.path.dirname(path.rstrip(os.sep)) or '.', os.W_OK)
    except OSError:
        return False


def detect_install_method(*, frozen=None, platform_name=None,
                          executable=None, run_cmd=None, which=None):
    """Detect how this copy was installed.

    Returns an :class:`InstallInfo`. The one-click path is offered only
    when the current install is provably managed that way; otherwise the
    caller falls back to manual instructions.
    """
    import platform

    if frozen is None:
        frozen = getattr(sys, 'frozen', False)
    if platform_name is None:
        platform_name = platform.system().lower()
    else:
        platform_name = platform_name.lower()
    exe = executable or sys.executable
    run_cmd = run_cmd or _default_run_cmd
    which = which or _default_which

    if not frozen:
        return InstallInfo(METHOD_SOURCE, False, 'source/uv checkout')

    if platform_name.startswith('win'):
        return InstallInfo(METHOD_WINDOWS, True, 'PyInstaller bundle')

    if platform_name == 'darwin':
        bundle = _macos_bundle_for(exe)
        if bundle is not None:
            try:
                writable = os.access(os.path.dirname(bundle.rstrip(os.sep)),
                                     os.W_OK)
            except OSError:
                writable = False
            if writable:
                return InstallInfo(METHOD_MACOS, True, bundle)
            return InstallInfo(METHOD_MACOS, False,
                               f'{bundle} (not writable by this user)')
        return InstallInfo(METHOD_MACOS, False, 'not inside an .app bundle')

    if platform_name == 'linux':
        try:
            real_exe = os.path.realpath(exe)
        except OSError:
            real_exe = exe
        if which('dpkg'):
            rc, out = run_cmd(['dpkg', '-S', real_exe])
            if rc == 0 and re.search(r'(?m)(^|[\s:])' + re.escape(DEB_PACKAGE_NAME)
                                     + r'([\s:]|$)', out):
                return InstallInfo(METHOD_DEBIAN, True, DEB_PACKAGE_NAME)
        if which('rpm'):
            rc, out = run_cmd(['rpm', '-qf', real_exe])
            if rc == 0 and re.match(r'^' + re.escape(RPM_PACKAGE_NAME) + r'(-|$)',
                                    out.strip()):
                return InstallInfo(METHOD_FEDORA, True, RPM_PACKAGE_NAME)
        if which('pacman'):
            rc, out = run_cmd(['pacman', '-Qo', real_exe])
            if rc == 0 and ARCH_PACKAGE_NAME in out:
                return InstallInfo(METHOD_ARCH, True, ARCH_PACKAGE_NAME)
        # "Frozen, but not provably one of our packages" — manual path.
        return InstallInfo(METHOD_UNKNOWN, False,
                           'frozen bundle not owned by a known package')
    return InstallInfo(METHOD_UNKNOWN, False, platform_name or 'unknown OS')


def release_asset_for(method, assets):
    """Pick the asset matching this installation method."""
    exact = {METHOD_WINDOWS: ASSET_WINDOWS,
             METHOD_MACOS: ASSET_MACOS,
             METHOD_DEBIAN: ASSET_DEBIAN,
             METHOD_FEDORA: ASSET_FEDORA}
    if method in exact:
        target = exact[method]
        for asset in assets or []:
            if asset.name == target:
                return asset
        return None
    if method == METHOD_ARCH:
        for asset in assets or []:
            if ARCH_ASSET_RE.match(asset.name):
                return asset
        return None
    return None


def sha256sums_asset(assets):
    for asset in assets or []:
        if asset.name == SHA256SUMS_NAME:
            return asset
    return None


def update_hint(method, asset_name=None):
    """Short 'how to update this install' hint for the given method."""
    if method == METHOD_WINDOWS:
        return ('Download and run EasyMathLang-Windows-x64-Setup.exe '
                '(you will see a UAC prompt).')
    if method == METHOD_MACOS:
        return ('Open the .dmg and drag Easy Math Lang to Applications, '
                'replacing the existing app.')
    if method == METHOD_DEBIAN:
        name = asset_name or ASSET_DEBIAN
        return f'Sudo apt install ./{name}  (or: sudo dpkg -i ./{name})'
    if method == METHOD_FEDORA:
        name = asset_name or ASSET_FEDORA
        return f'Sudo dnf install ./{name}  (or: sudo rpm -U ./{name})'
    if method == METHOD_ARCH:
        name = asset_name or 'easy-math-lang-git-<ver>-<rel>-x86_64.pkg.tar.zst'
        return f'Sudo pacman -U ./{name}'
    if method == METHOD_SOURCE:
        return 'This is a source checkout — update with: git pull && uv sync'
    return ('Download the asset for your platform from the release page '
            'and install it manually.')


def one_click_supported(info, *, which=None, environ=None):
    """True when the one-click update path is usable right now."""
    if not info.one_click:
        return False
    if info.method in (METHOD_DEBIAN, METHOD_FEDORA, METHOD_ARCH):
        which = which or _default_which
        if which('pkexec') is None:
            return False
        env = os.environ if environ is None else environ
        # polkit needs a graphical session for its agent; without one the
        # auth dialog can never appear — show the manual command instead.
        if not (env.get('DISPLAY') or env.get('WAYLAND_DISPLAY')):
            return False
    return True


def manual_commands_for(method, asset_name=None):
    """The exact manual command(s) to update, for fallback display."""
    return update_hint(method, asset_name)
