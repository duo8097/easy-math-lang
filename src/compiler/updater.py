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

from .update import (CHECK_TIMEOUT, ReleaseAsset, ReleaseInfo, USER_AGENT,
                     clear_update_error, record_update_error)

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


# ----------------------------------------------------------------------
# Per-platform install commands (B4) — argv lists only, never shell
# ----------------------------------------------------------------------

HELPER_WAIT_SECONDS = 120
INSTALL_TIMEOUT = 900


def windows_setup_command(asset_path, log_path):
    """Inno Setup silent flags for the Windows installer.

    PrivilegesRequired=admin in setup.iss, so Windows shows the UAC
    prompt — that is the user's verification. The flags must stay valid
    for this setup.iss (they are all standard Inno Setup 6 flags).
    """
    return [
        asset_path,
        '/SILENT',
        '/SP-',
        '/NORESTART',
        '/CLOSEAPPLICATIONS',
        '/RESTARTAPPLICATIONS',
        f'/LOG={log_path}',
    ]


def debian_install_command(asset_path):
    return ['pkexec', 'apt-get', 'install', '-y', asset_path]


def debian_fallback_command(asset_path):
    return ['pkexec', 'dpkg', '-i', asset_path]


def fedora_install_command(asset_path):
    return ['pkexec', 'dnf', 'install', '-y', asset_path]


def fedora_fallback_command(asset_path):
    return ['pkexec', 'rpm', '-U', asset_path]


def arch_install_command(asset_path):
    return ['pkexec', 'pacman', '-U', '--noconfirm', asset_path]


# ----------------------------------------------------------------------
# Update helper (B5) — the running app is never replaced while running
# ----------------------------------------------------------------------
# The helper is this same CLI binary invoked with ``--apply-update
# <plan.json>`` (works inside the frozen bundle, needs no interpreter on
# the target machine). It waits for the app's PID to exit, runs the
# platform installer command, logs to a file in the config dir, then
# relaunches the app. The helper itself never runs with more privilege
# than needed — only the installer command (pkexec/UAC) is elevated.
# On any failure the old version is left runnable and the failure is
# written to the state file; the next editor start shows it once.


def default_log_path():
    from .update import default_config_dir

    return os.path.join(default_config_dir(), 'update.log')


def default_plan_path(temp_dir):
    return os.path.join(temp_dir, 'update-plan.json')


def build_update_plan(*, version, method, asset_path, temp_dir,
                      relaunch_argv, pid=None, wait_timeout=HELPER_WAIT_SECONDS,
                      macos=None, state_path=None, log_path=None,
                      install_log_path=None):
    """Assemble the JSON-able plan consumed by ``--apply-update``."""
    plan = {
        'version': version,
        'method': method,
        'installer': asset_path,
        'pid': int(pid if pid is not None else os.getpid()),
        'relaunch_argv': list(relaunch_argv or []),
        'log_path': log_path or default_log_path(),
        'state_path': state_path or _default_state_path_safe(),
        'temp_dir': temp_dir,
        'wait_timeout': int(wait_timeout),
        'install_log_path': install_log_path
        or os.path.join(temp_dir, 'installer.log'),
    }
    if macos is not None:
        plan['macos'] = dict(macos)
    return plan


def _default_state_path_safe():
    from .update import default_state_path

    try:
        return default_state_path()
    except Exception:
        return ''


def write_plan(plan, path):
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(plan, handle, indent=1, sort_keys=True)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def load_plan(path):
    with open(path, 'r', encoding='utf-8') as handle:
        plan = json.load(handle)
    if not isinstance(plan, dict):
        raise ValueError('update plan must be a JSON object')
    for key in ('version', 'method', 'installer', 'pid', 'log_path',
                'temp_dir', 'relaunch_argv'):
        if key not in plan:
            raise ValueError(f'update plan is missing {key!r}')
    return plan


def _helper_cli_candidates():
    """Ordered candidate argv lists for the update helper binary.

    The helper is the CLI binary (it understands ``--apply-update``),
    never the editor GUI. In the frozen bundle the CLI ships next to
    the editor inside the same directory; for frozen CLI runs the
    current executable is the CLI itself.
    """
    candidates = []
    exe = sys.executable
    name = os.path.basename(exe).lower()
    exe_dir = os.path.dirname(exe)
    cli = 'easy-math-lang.exe' if os.name == 'nt' else 'easy-math-lang'
    sibling = os.path.join(exe_dir, cli)
    if name in ('easy-math-lang', 'easy-math-lang.exe', 'ezmath',
                'ezmath.exe'):
        candidates.append([exe, '--apply-update'])
    if os.path.isfile(sibling):
        candidates.append([sibling, '--apply-update'])
    return candidates


def spawn_helper(plan_path, *, log_path=None):
    """Spawn the detached helper (the CLI binary with --apply-update)."""
    argv = None
    for candidate in _helper_cli_candidates():
        path = candidate[0]
        if path and os.path.isfile(path) and os.access(path, os.X_OK):
            argv = candidate + [str(plan_path)]
            break
    if argv is None:
        raise FileNotFoundError(
            'the update helper (easy-math-lang CLI binary) could not '
            'be located next to this executable; aborting before the '
            'app quits')
    if os.name == 'nt':
        flags = getattr(subprocess, 'DETACHED_PROCESS', 0) \
            | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
        process = subprocess.Popen(argv, close_fds=True,
                                   creationflags=flags)
    else:
        process = subprocess.Popen(argv, close_fds=True,
                                   start_new_session=True)
    return process


# ----------------------------------------------------------------------
# PID waiting (platform dependent; injectable for tests)
# ----------------------------------------------------------------------

def wait_pid_exit(pid, timeout, *, _poll=None, _sleep=None):
    """True when *pid* is gone within *timeout* seconds."""
    import time

    poll = _poll or _default_pid_gone
    sleep = _sleep or time.sleep
    deadline = time.monotonic() + max(0.0, float(timeout))
    while True:
        if poll(pid):
            return True
        if time.monotonic() >= deadline:
            return False
        sleep(0.2)


def _default_pid_gone(pid):
    if os.name == 'nt':
        return _windows_pid_gone(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False  # exists, owned by someone else
    except OSError:
        return True
    return False


def _windows_pid_gone(pid):
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
    except Exception:
        # Without ctypes we cannot tell; assume the app is gone so the
        # helper does not deadlock — the installer would fail safely.
        return True
    synchronize = 0x00100000  # SYNCHRONIZE
    wait_object_0 = 0x00000000
    handle = kernel32.OpenProcess(synchronize, False, pid)
    if not handle:
        return True  # ERROR_INVALID_PARAMETER: no such process
    try:
        return kernel32.WaitForSingleObject(handle, 0) == wait_object_0
    finally:
        kernel32.CloseHandle(handle)


# ----------------------------------------------------------------------
# macOS: mount the DMG and stage the new bundle (pre-quit, fail-safe)
# ----------------------------------------------------------------------

def prepare_macos_update(dmg_path, *, target_app=None, run_cmd=None,
                         temp_dir=None, version=None, **plan_kwargs):
    """Mount the DMG, copy the new .app next to the target, detach.

    Runs BEFORE the app quits; on any failure nothing is left behind
    and the error is raised so the caller can show it without quitting.
    The actual bundle swap happens in the helper after the app exits.
    Returns the ``macos`` dict for the update plan.
    """
    run_cmd = run_cmd or _helper_run_cmd
    executable = plan_kwargs.get('executable') or sys.executable
    if target_app is None:
        target_app = _macos_bundle_for(executable)
    if target_app is None:
        raise DownloadError('not running from an .app bundle — use the '
                            'manual steps in the release notes.')
    created_tmp = temp_dir is None
    tmp_dir = temp_dir or tempfile.mkdtemp(prefix='easymath-dmg-')
    try:
        os.chmod(tmp_dir, 0o700)
    except OSError:
        pass
    mountpoint = os.path.join(tmp_dir, 'dmg')
    os.makedirs(mountpoint, exist_ok=True)

    def _detach():
        rc = run_cmd(['hdiutil', 'detach', mountpoint])
        return rc == 0

    attached = False
    new_app = None
    try:
        rc = run_cmd(['hdiutil', 'attach', '-nobrowse', '-readonly',
                      '-mountpoint', mountpoint, dmg_path])
        if rc != 0:
            raise DownloadError(f'could not mount the DMG (hdiutil exited '
                                f'with {rc}).')
        attached = True
        app_in_dmg = None
        try:
            for entry in os.listdir(mountpoint):
                if entry.endswith('.app'):
                    app_in_dmg = os.path.join(mountpoint, entry)
                    break
        except OSError as exc:
            raise DownloadError(f'could not read the mounted DMG: {exc}')
        if app_in_dmg is None:
            raise DownloadError('the DMG contains no .app bundle.')
        target_dir = os.path.dirname(target_app.rstrip(os.sep)) or '.'
        suffix = os.urandom(4).hex()
        new_app = os.path.join(target_dir,
                               f'.EasyMathLang-update-{suffix}.app')
        try:
            shutil.copytree(app_in_dmg, new_app, symlinks=True)
        except (OSError, shutil.Error) as exc:
            shutil.rmtree(new_app, ignore_errors=True)
            new_app = None
            raise DownloadError(f'could not copy the new app bundle: {exc}')
    except BaseException:
        if new_app is not None:
            shutil.rmtree(new_app, ignore_errors=True)
        if attached:
            try:
                _detach()
            except Exception:
                pass
        if created_tmp:
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except OSError:
                pass
        raise
    # On success the DMG stays mounted until the helper swaps the new
    # bundle in place and detaches it there; the plan records the
    # mountpoint (and the staging dir when we created one).
    backup = target_app.rstrip(os.sep) + '.update-backup'
    result = {'target_app': target_app, 'new_app': new_app,
              'backup': backup, 'mountpoint': mountpoint}
    if created_tmp:
        result['stage_dir'] = tmp_dir
    return result


# ----------------------------------------------------------------------
# The helper itself
# ----------------------------------------------------------------------

def _helper_log(path):
    def log(message):
        try:
            with open(path, 'a', encoding='utf-8') as handle:
                handle.write(f'[{_now_iso()}] {message}\n')
        except OSError:
            pass
    return log


def _now_iso():
    import datetime

    return datetime.datetime.now().isoformat(timespec='seconds')


def _helper_run_cmd(argv):
    try:
        result = subprocess.run(argv, timeout=INSTALL_TIMEOUT, check=False)
        return result.returncode
    except subprocess.TimeoutExpired:
        return 124
    except OSError:
        return 127


def _fail_update(plan, log, reason):
    version = plan.get('version', '?')
    log_path = plan.get('log_path') or default_log_path()
    log(f'update FAILED: {reason}')
    record_update_error(version, reason, log_path, plan.get('state_path') or None)


def _cleanup_temp(plan, log):
    temp_dir = plan.get('temp_dir')
    if not temp_dir:
        return
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
        log(f'removed temp dir {temp_dir}')
    except OSError as exc:
        log(f'could not remove temp dir {temp_dir}: {exc}')


def _relaunch(plan, log, relaunch=None):
    argv = plan.get('relaunch_argv') or []
    if not argv:
        log('no relaunch requested (e.g. CLI update); done')
        return
    if relaunch is not None:
        relaunch(argv)
        log(f'relaunched: {argv}')
        return
    try:
        if plan.get('method') == METHOD_MACOS:
            subprocess.Popen(['open', '-n'] + argv, close_fds=True,
                             start_new_session=True)
        elif os.name == 'nt':
            flags = getattr(subprocess, 'DETACHED_PROCESS', 0) \
                | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
            subprocess.Popen(argv, close_fds=True, creationflags=flags)
        else:
            subprocess.Popen(argv, close_fds=True, start_new_session=True)
        log(f'relaunched: {argv}')
    except Exception as exc:
        log(f'could not relaunch {argv}: {exc}')


def _macos_swap(plan, log, *, rename=os.rename, run_cmd=None):
    """Swap the new .app bundle into place with a backup + rollback."""
    macos = plan.get('macos') or {}
    target = macos.get('target_app')
    new_app = macos.get('new_app')
    backup = macos.get('backup')
    if not target or not new_app or not backup:
        return False, 'incomplete macOS swap plan'
    run_cmd = run_cmd or _helper_run_cmd

    def _detach():
        mountpoint = macos.get('mountpoint')
        if not mountpoint:
            return
        try:
            rc = run_cmd(['hdiutil', 'detach', mountpoint])
            log(f'hdiutil detach exited with {rc}')
        except Exception as exc:
            log(f'could not detach the DMG at {mountpoint}: {exc}')
        stage_dir = macos.get('stage_dir')
        if stage_dir and os.path.basename(stage_dir.rstrip(os.sep)).startswith('easymath-dmg-'):
            try:
                shutil.rmtree(stage_dir, ignore_errors=True)
                log(f'removed staging dir {stage_dir}')
            except OSError as exc:
                log(f'could not remove staging dir {stage_dir}: {exc}')

    if not os.path.isdir(new_app):
        _detach()
        return False, f'new app bundle not found at {new_app}'
    had_old = os.path.isdir(target)
    try:
        if had_old:
            if os.path.isdir(backup):
                shutil.rmtree(backup)
            rename(target, backup)
            log(f'backed up {target} -> {backup}')
        rename(new_app, target)
        log(f'moved {new_app} -> {target}')
    except OSError as exc:
        # Roll back: restore the backup if the swap failed halfway.
        log(f'swap failed: {exc}')
        if had_old and not os.path.isdir(target) and os.path.isdir(backup):
            try:
                rename(backup, target)
                log(f'restored backup {backup} -> {target}')
            except OSError as restore_exc:
                log(f'ROLLBACK FAILED: could not restore {backup}: '
                    f'{restore_exc}')
                _detach()
                return False, (f'swap failed and rollback failed: {exc} '
                               f'(old app kept at {backup})')
        _detach()
        return False, f'swap failed: {exc}'
    # Swap succeeded; drop the backup.
    try:
        if os.path.isdir(backup):
            shutil.rmtree(backup)
            log(f'removed backup {backup}')
    except OSError as exc:
        log(f'could not remove backup {backup}: {exc}')
    _detach()
    return True, 'ok'


def _run_installer(plan, log, run_cmd=None):
    method = plan.get('method')
    installer = plan.get('installer')
    run_cmd = run_cmd or _helper_run_cmd
    if method == METHOD_WINDOWS:
        argv = windows_setup_command(installer, plan.get('install_log_path')
                                     or (plan.get('log_path', '') + '.setup.log'))
        log(f'running Windows installer: {argv}')
        rc = run_cmd(argv)
        log(f'installer exited with {rc}')
        return (rc == 0), (f'installer exited with {rc}' if rc != 0 else 'ok')
    if method == METHOD_DEBIAN:
        for argv in (debian_install_command(installer),
                     debian_fallback_command(installer)):
            log(f'running {argv}')
            rc = run_cmd(argv)
            log(f'command exited with {rc}')
            if rc == 0:
                return True, 'ok'
        return False, 'both `pkexec apt-get install -y` and ' \
            '`pkexec dpkg -i` failed (see log)'
    if method == METHOD_FEDORA:
        for argv in (fedora_install_command(installer),
                     fedora_fallback_command(installer)):
            log(f'running {argv}')
            rc = run_cmd(argv)
            log(f'command exited with {rc}')
            if rc == 0:
                return True, 'ok'
        return False, 'both `pkexec dnf install -y` and ' \
            '`pkexec rpm -U` failed (see log)'
    if method == METHOD_ARCH:
        argv = arch_install_command(installer)
        log(f'running {argv}')
        rc = run_cmd(argv)
        log(f'command exited with {rc}')
        return (rc == 0), (f'`pkexec pacman -U --noconfirm` exited with {rc}'
                           if rc != 0 else 'ok')
    if method == METHOD_MACOS:
        ok, detail = _macos_swap(plan, log)
        return ok, detail
    return False, f'unsupported install method: {method!r}'


def apply_update(plan, *, wait_pid_exit_fn=None, run_cmd=None, relaunch=None,
                 _rename=os.rename):
    """The helper's entry point. Returns the process exit code."""
    log = _helper_log(plan.get('log_path') or default_log_path())
    log(f'update helper started for v{plan.get("version")} '
        f'(pid {plan.get("pid")}, method {plan.get("method")})')

    wait = wait_pid_exit_fn or wait_pid_exit
    if not wait(plan.get('pid'), plan.get('wait_timeout', HELPER_WAIT_SECONDS)):
        _fail_update(plan, log,
                     f'the application (pid {plan.get("pid")}) did not exit '
                     f'within {plan.get("wait_timeout")}s — update aborted; '
                     f'nothing was changed')
        _cleanup_temp(plan, log)
        return 1
    log('application exited; installing update')

    if plan.get('method') == METHOD_MACOS:
        ok, detail = _macos_swap(plan, log, rename=_rename, run_cmd=run_cmd)
    else:
        ok, detail = _run_installer(plan, log, run_cmd=run_cmd)

    if not ok:
        _fail_update(plan, log, detail)
        _relaunch(plan, log, relaunch)
        _cleanup_temp(plan, log)
        return 1
    clear_update_error(plan.get('state_path') or None)
    log('update installed successfully')
    _relaunch(plan, log, relaunch)
    _cleanup_temp(plan, log)
    return 0


# ----------------------------------------------------------------------
# CLI self-update (B6) — `easy-math-lang --update` / `ezmath --update`
# ----------------------------------------------------------------------

NOTES_SUMMARY_LIMIT = 700
DOWNLOAD_BAR_WIDTH = 28


def _notes_summary(notes, limit=NOTES_SUMMARY_LIMIT):
    text = (notes or '').strip()
    if not text:
        return ''
    if len(text) <= limit:
        return text
    cut = text[:limit]
    # Prefer a line boundary; fall back to a hard cut.
    if '\n' in cut:
        cut = cut.rsplit('\n', 1)[0]
    return cut.rstrip() + '\n…'


def _text_progress(stream):
    def progress(done, total):
        if total and total > 0:
            pct = done / total
            filled = int(DOWNLOAD_BAR_WIDTH * pct)
            bar = '#' * filled + '.' * (DOWNLOAD_BAR_WIDTH - filled)
            stream.write(f'\rDownloading [{bar}] {pct * 100:5.1f}% '
                         f'({done / 1e6:.1f}/{total / 1e6:.1f} MB)')
        else:
            stream.write(f'\rDownloading… {done / 1e6:.1f} MB')
        try:
            stream.flush()
        except Exception:
            pass
    return progress


def run_self_update(*, current_version=None, yes=False, ask=None, out=None,
                    err=None, urlopen=None, state_path=None, download_fn=None,
                    detect_fn=None, prepare_macos_fn=None, spawn_fn=None):
    """The ``--update`` flow. Returns the process exit code.

    Shows current vs latest and a notes summary, asks for confirmation
    (``yes=True`` skips only the prompt — verification can never be
    skipped), downloads with a text progress bar, verifies SHA-256,
    then hands over to the detached helper and exits 0. Exits non-zero
    on failure (network, verification, unsupported install) and says
    what to do instead.
    """
    from . import update as _update

    emit = out or print
    err_emit = err or (lambda msg: print(msg, file=sys.stderr))
    stream = out if out is not None else sys.stdout

    def _fail(reason):
        err_emit(f'Update failed: {reason}')
        _manual_hint()
        return 1

    current = current_version or _update.get_current_version()
    emit(f'{_update.APP_NAME} {current}')

    result = _update.check_for_update(current, interactive=True,
                                      urlopen=urlopen, state_path=state_path)
    if result.error is not None:
        err_emit(f'Could not check for updates: {result.error}')
        emit(_update.RELEASES_PAGE_URL)
        return 1
    info = result.latest
    if result.status != 'newer' or info is None:
        emit('You are up to date.')
        return 0

    emit(f'A new version is available: {info.version}')
    emit(info.html_url)
    if info.published:
        emit(f'Published: {info.published}')
    summary = _notes_summary(info.notes)
    if summary:
        emit('Release notes (summary):')
        emit(summary)

    method_info = (detect_fn or detect_install_method)()
    asset = release_asset_for(method_info.method, info.assets)
    sums = sha256sums_asset(info.assets)
    one_click = one_click_supported(method_info)

    def _manual_hint():
        if asset is not None:
            emit(f'Download the asset for this installation: '
                 f'{asset.name} ({_format_size(asset.size)})')
        emit(update_hint(method_info.method,
                         asset.name if asset is not None else None))
        emit(f'Or download it manually from:\n{info.html_url}')

    if not one_click or asset is None or sums is None:
        emit('')
        if method_info.method == METHOD_SOURCE:
            emit('This is a source checkout — updates are applied with '
                 'git, not by this tool.')
        elif sums is None:
            emit('This release is missing SHA256SUMS.txt — the download '
                 'cannot be verified, so it will not be installed.')
        else:
            emit('One-click update is not available for this installation '
                 f'({method_info.detail or method_info.method}).')
        _manual_hint()
        return 1

    emit('')
    emit(f'Asset: {asset.name} ({_format_size(asset.size)})')
    if method_info.method == METHOD_WINDOWS:
        emit('You will see a UAC prompt from Windows — that is your '
             'verification.')
    elif method_info.method in (METHOD_DEBIAN, METHOD_FEDORA, METHOD_ARCH):
        emit('You will be asked to authenticate (polkit) — that is your '
             'verification.')
    emit('The app must restart to finish the update. Unsaved documents '
         'should be saved first.')

    if not yes:
        prompter = ask or (lambda: input('Update now? [y/N] '))
        try:
            answer = prompter()
        except (EOFError, KeyboardInterrupt, OSError):
            err_emit('No terminal to ask for confirmation '
                     '(use --yes to proceed non-interactively).')
            return 1
        if not str(answer).strip().lower().startswith('y'):
            emit('Update cancelled.')
            return 0

    # --- download + verify (verification can never be skipped) -----------
    download = download_fn or download_asset
    try:
        result_dl = download(
            asset.download_url, dest_name=asset.name,
            expected_size=asset.size or None,
            sha256sums_url=sums.download_url,
            progress=_text_progress(stream), urlopen=urlopen)
    except DownloadCancelled:
        emit('\nDownload cancelled.')
        return 0
    except DownloadError as exc:
        return _fail(str(exc))
    except Exception as exc:
        return _fail(f'download failed: {exc}')
    if hasattr(stream, 'write'):
        try:
            stream.write('\n')
            stream.flush()
        except Exception:
            pass
    emit(f'Downloaded {result_dl.path}')
    emit(f'SHA-256 verified: {result_dl.sha256}')

    # --- stage + spawn the helper, then exit before installing -----------
    try:
        plan_path = stage_update_plan(
            info, method_info, result_dl, relaunch_argv=[],
            prepare_macos_fn=prepare_macos_fn, state_path=state_path,
            pid=os.getpid())
    except DownloadError as exc:
        try:
            shutil.rmtree(result_dl.temp_dir, ignore_errors=True)
        except OSError:
            pass
        return _fail(str(exc))
    spawn = spawn_fn or spawn_helper
    try:
        spawn(plan_path)
    except Exception as exc:
        try:
            shutil.rmtree(result_dl.temp_dir, ignore_errors=True)
        except OSError:
            pass
        return _fail(f'could not launch the update helper: {exc}')
    emit('The update will be installed in the background after this '
         'process exits.')
    emit(f'If anything goes wrong, see {default_log_path()}')
    return 0


def _format_size(size):
    try:
        size = int(size)
    except (TypeError, ValueError):
        return 'unknown size'
    if size <= 0:
        return 'unknown size'
    return f'{size / (1024 * 1024):.1f} MB'


def stage_update_plan(info, method_info, result_dl, *, relaunch_argv,
                      prepare_macos_fn=None, state_path=None, pid=None):
    """Build the helper plan (and stage the macOS bundle) for the update.

    *relaunch_argv* is empty for the CLI (nothing to restart) or the
    editor binary (GUI update) when the install finishes.
    """
    macos = None
    if method_info.method == METHOD_MACOS:
        prepare = prepare_macos_fn or prepare_macos_update
        macos = prepare(result_dl.path, executable=sys.executable,
                        version=info.version)
    from .update import default_state_path

    try:
        state_path = state_path or default_state_path()
    except Exception:
        state_path = ''
    plan = build_update_plan(
        version=info.version, method=method_info.method,
        asset_path=result_dl.path, temp_dir=result_dl.temp_dir,
        relaunch_argv=relaunch_argv, macos=macos,
        pid=pid if pid is not None else os.getpid(),
        state_path=state_path)
    plan_path = default_plan_path(result_dl.temp_dir)
    write_plan(plan, plan_path)
    return plan_path
