"""Check whether a newer EasyMath release is available (CLI-only).

Queries the GitHub Releases API (GET only, short timeout, no user data
sent) and compares the latest ``tag_name`` against the installed version
with real semantic-version ordering (``0.10.0 > 0.9.0``).

Stdlib only (``urllib``/``json``/``re``): ``packaging`` is not a direct
dependency of this project and may be missing from frozen builds, so
version parsing is implemented here. Never raises on network problems:
every failure surfaces as :class:`UpdateCheckError`, and
:func:`run_check_update` always exits 0 so a dead network never crashes
the CLI.
"""

import json
import os
import re
import time
import urllib.error
import urllib.request

APP_NAME = 'EasyMath Lang'
DISTRIBUTION_NAME = 'easy-math-lang'
# Fallback when installed metadata is unavailable (e.g. frozen build).
# Source of truth stays ``pyproject.toml``; keep this in sync on release.
FALLBACK_VERSION = '7.0.0'

REPO = 'duo8097/easy-math-lang'
LATEST_RELEASE_URL = (
    f'https://api.github.com/repos/{REPO}/releases/latest'
)
RELEASES_PAGE_URL = f'https://github.com/{REPO}/releases/latest'
CHECK_TIMEOUT = 4  # seconds; short so a dead network never hangs the CLI
USER_AGENT = 'EasyMath-Lang-update-check'


class UpdateCheckError(Exception):
    """Any failure while checking for updates (network or bad payload)."""


def get_current_version():
    """Installed EasyMath version (``pyproject.toml`` via import metadata)."""
    try:
        from importlib.metadata import version

        found = version(DISTRIBUTION_NAME)
        if isinstance(found, str) and found.strip():
            return found.strip()
    except Exception:
        pass
    return FALLBACK_VERSION


def normalize_version(tag):
    """Strip whitespace and a leading ``v``/``V`` (``v0.1.1`` -> ``0.1.1``).

    The prefix is only stripped when followed by a digit, so words like
    ``version`` are left untouched.
    """
    text = tag.strip() if isinstance(tag, str) else ''
    if re.match(r'^[vV]\d', text):
        text = text[1:]
    return text.strip()


def _suffix_key(suffix):
    """Comparable key for a pre-release suffix (semver §11).

    Split on ``.`` into identifiers first, so ``1.0-rc.1 < 1.0-rc1`` and
    ``1.0-a.b < 1.0-a-b``. Numeric identifiers compare as ints (and sort
    before alphanumeric ones); mixed identifiers (``rc10``) compare their
    digit/non-digit runs numerically (``rc2 < rc10``).
    """
    keys = []
    for identifier in suffix.split('.'):
        if identifier.isdigit():
            keys.append((0, int(identifier)))
        else:
            chunks = tuple(
                (0, int(chunk)) if chunk.isdigit() else (1, chunk)
                for chunk in re.findall(r'\d+|\D+', identifier)
            )
            keys.append((1, chunks))
    return tuple(keys)


def _version_key(text):
    """Comparable key: (numeric release tuple, final/pre-release marker).

    ``0.10.0 > 0.9.0`` because segments compare as ints; a bare release
    (``1.0``) sorts after its pre-releases (``1.0rc1``); build metadata
    (``1.0+build``) is ignored per semver §10.
    """
    version = normalize_version(text)
    # Build metadata (+...) carries no precedence (semver §10).
    version = version.split('+', 1)[0]
    match = re.match(r'^(\d+(?:\.\d+)*)', version)
    if not match:
        raise UpdateCheckError(f'invalid version {text!r}.')
    numbers = tuple(int(part) for part in match.group(1).split('.'))
    suffix = version[match.end():].lstrip('.-').lower()
    if not suffix:
        return (numbers, (1,))
    return (numbers, (0, _suffix_key(suffix)))


def compare_versions(local, remote):
    """-1 if ``local`` < ``remote``, 0 if equal, 1 if ``local`` > ``remote``."""
    local_key = _version_key(local)
    remote_key = _version_key(remote)
    pad = max(len(local_key[0]), len(remote_key[0]))
    local_padded = local_key[0] + (0,) * (pad - len(local_key[0]))
    remote_padded = remote_key[0] + (0,) * (pad - len(remote_key[0]))
    left = (local_padded, local_key[1])
    right = (remote_padded, remote_key[1])
    if left < right:
        return -1
    if left > right:
        return 1
    return 0


def fetch_latest_release_data(url=LATEST_RELEASE_URL,
                              timeout=CHECK_TIMEOUT, urlopen=None):
    """GET the GitHub latest-release JSON (``urlopen`` is injectable)."""
    opener = urlopen or urllib.request.urlopen
    try:
        request = urllib.request.Request(
            url,
            headers={
                'User-Agent': USER_AGENT,
                'Accept': 'application/vnd.github+json',
            },
        )
        response = opener(request, timeout=timeout)
        try:
            raw = response.read()
        finally:
            close = getattr(response, 'close', None)
            if callable(close):
                close()
    except UpdateCheckError:
        raise
    except Exception:
        raise UpdateCheckError('network unavailable.')
    try:
        text = raw.decode('utf-8') if isinstance(raw, bytes) else raw
        data = json.loads(text)
    except (ValueError, UnicodeDecodeError, TypeError, AttributeError):
        raise UpdateCheckError('invalid response from server.')
    if not isinstance(data, dict):
        raise UpdateCheckError('invalid response from server.')
    return data


def extract_release_info(data):
    """Return ``(version, html_url)`` from a releases API payload."""
    if not isinstance(data, dict):
        raise UpdateCheckError('invalid response from server.')
    # GitHub returns {"message": "API rate limit exceeded", ...} on 403/429
    # and {"message": "Not Found"} when no releases exist yet.
    if 'tag_name' not in data and isinstance(data.get('message'), str):
        msg = data['message'].lower()
        if 'rate limit' in msg or 'abuse' in msg or '429' in msg:
            raise UpdateCheckError('rate limited — try again later.')
        if 'not found' in msg or 'no releases' in msg:
            raise UpdateCheckError('no releases published yet.')
        raise UpdateCheckError('missing release info in server response.')
    tag = data.get('tag_name')
    if not isinstance(tag, str) or not tag.strip():
        raise UpdateCheckError('missing release info in server response.')
    version = normalize_version(tag)
    try:
        _version_key(version)
    except UpdateCheckError:
        raise UpdateCheckError('invalid response from server.')
    url = data.get('html_url')
    if not isinstance(url, str) or not url.strip():
        url = RELEASES_PAGE_URL
    return version, url.strip()


def get_latest_release_info(url=LATEST_RELEASE_URL,
                            timeout=CHECK_TIMEOUT, urlopen=None):
    """Fetch and parse the latest release; ``(version, html_url)``."""
    return extract_release_info(
        fetch_latest_release_data(url=url, timeout=timeout, urlopen=urlopen))


def check_update_status(current_version, latest_version):
    """``'newer'`` if an update exists, ``'current'``/``'ahead'`` otherwise."""
    result = compare_versions(current_version, latest_version)
    if result < 0:
        return 'newer'
    if result > 0:
        return 'ahead'
    return 'current'


def run_check_update(current_version=None, fetch=None, out=None):
    """CLI presentation for ``--check-update``; always returns exit code 0."""
    emit = out or print
    current = current_version or get_current_version()
    emit(f'{APP_NAME} {current}')
    fetch_latest = fetch or get_latest_release
    try:
        result = fetch_latest()
        if isinstance(result, tuple):
            # Legacy fetch contract: ``(version, html_url)``.
            latest, url, assets = result[0], result[1], []
        else:
            latest, url, assets = result.version, result.html_url, result.assets
        status = check_update_status(current, latest)
    except UpdateCheckError as exc:
        emit(f'Could not check for updates: {exc}')
        return 0
    except Exception:
        emit('Could not check for updates: network unavailable.')
        return 0
    if status == 'newer':
        emit(f'A new version is available: {latest}')
        emit(url)
        try:
            from . import updater

            method = updater.detect_install_method()
            asset = updater.release_asset_for(method, assets)
            if asset is not None:
                emit(f'Asset for this installation: {asset.name}')
            emit(updater.update_hint(method,
                                     asset.name if asset is not None else None))
        except Exception:
            pass  # best-effort hint; the release URL above still helps
    else:
        emit('You are up to date.')
    return 0


# --------------------------------------------------------------------------
# Release info, assets and on-disk state (self-update building blocks)
# --------------------------------------------------------------------------
# Everything below is stdlib-only and every network/filesystem-location
# call is injectable so tests never touch the real network or the user's
# real config directory.

import dataclasses

NOTES_LIMIT = 2000  # release notes are truncated for display
AUTO_CHECK_INTERVAL = 24 * 3600  # automatic checks hit the network at most once per day
STATE_FILE_NAME = 'update-state.json'


@dataclasses.dataclass
class ReleaseAsset:
    name: str
    download_url: str
    size: int = 0


@dataclasses.dataclass
class ReleaseInfo:
    version: str
    html_url: str
    notes: str
    prerelease: bool
    published: str
    assets: list  # list[ReleaseAsset]

    def to_dict(self):
        return {
            'version': self.version,
            'html_url': self.html_url,
            'notes': self.notes,
            'prerelease': self.prerelease,
            'published': self.published,
            'assets': [dataclasses.asdict(asset) for asset in self.assets],
        }

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise UpdateCheckError('invalid cached release info.')
        assets = []
        for item in data.get('assets') or []:
            if not isinstance(item, dict):
                continue
            name = item.get('name')
            url = item.get('download_url') or item.get('browser_download_url')
            if not isinstance(name, str) or not name.strip():
                continue
            if not isinstance(url, str) or not url.strip():
                continue
            try:
                size = int(item.get('size') or 0)
            except (TypeError, ValueError):
                size = 0
            assets.append(ReleaseAsset(name.strip(), url.strip(),
                                       max(0, size)))
        notes = data.get('notes') if isinstance(data.get('notes'), str) else ''
        version = normalize_version(str(data.get('version') or ''))
        _version_key(version)  # raises UpdateCheckError on garbage
        return cls(
            version=version,
            html_url=str(data.get('html_url') or RELEASES_PAGE_URL),
            notes=notes[:NOTES_LIMIT],
            prerelease=bool(data.get('prerelease')),
            published=str(data.get('published') or ''),
            assets=assets,
        )


def parse_release_info(data, notes_limit=NOTES_LIMIT):
    """Build a :class:`ReleaseInfo` from a releases API payload."""
    version, url = extract_release_info(data)
    notes = data.get('body') if isinstance(data.get('body'), str) else ''
    notes = notes.strip()
    if len(notes) > notes_limit:
        notes = notes[:notes_limit - 1].rstrip() + '…'
    published = data.get('published_at') or data.get('created_at') or ''
    prerelease = bool(data.get('prerelease'))
    assets = []
    for item in data.get('assets') or []:
        if not isinstance(item, dict):
            continue
        name = item.get('name')
        url_ = item.get('browser_download_url')
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(url_, str) or not url_.strip():
            continue
        try:
            size = int(item.get('size'))
        except (TypeError, ValueError):
            size = 0
        assets.append(ReleaseAsset(name.strip(), url_.strip(),
                                   max(0, size)))
    return ReleaseInfo(version=version, html_url=url, notes=notes,
                       prerelease=prerelease, published=str(published or ''),
                       assets=assets)


def get_latest_release(url=LATEST_RELEASE_URL, timeout=CHECK_TIMEOUT,
                       urlopen=None):
    """Fetch and parse the latest release as a :class:`ReleaseInfo`."""
    return parse_release_info(
        fetch_latest_release_data(url=url, timeout=timeout, urlopen=urlopen))


def _header_value(response, name):
    headers = getattr(response, 'headers', None)
    if headers is None:
        return None
    try:
        value = headers.get(name)
    except Exception:
        return None
    return value if isinstance(value, str) and value.strip() else None


def fetch_release(url=LATEST_RELEASE_URL, timeout=CHECK_TIMEOUT,
                  urlopen=None, etag=None):
    """GET the latest release, honoring ``If-None-Match``.

    Returns ``(payload, etag)``. ``payload`` is ``None`` when the server
    answered 304 Not Modified (the caller then reuses its cache). Raises
    :class:`UpdateCheckError` on every other failure.
    """
    opener = urlopen or urllib.request.urlopen
    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'application/vnd.github+json',
    }
    if etag:
        headers['If-None-Match'] = etag
    try:
        request = urllib.request.Request(url, headers=headers)
        response = opener(request, timeout=timeout)
        try:
            raw = response.read()
            new_etag = _header_value(response, 'ETag')
        finally:
            close = getattr(response, 'close', None)
            if callable(close):
                close()
    except urllib.error.HTTPError as exc:
        if getattr(exc, 'code', None) == 304:
            return None, etag
        raise UpdateCheckError('network unavailable.')
    except UpdateCheckError:
        raise
    except Exception:
        raise UpdateCheckError('network unavailable.')
    try:
        text = raw.decode('utf-8') if isinstance(raw, bytes) else raw
        data = json.loads(text)
    except (ValueError, UnicodeDecodeError, TypeError, AttributeError):
        raise UpdateCheckError('invalid response from server.')
    if not isinstance(data, dict):
        raise UpdateCheckError('invalid response from server.')
    return data, new_etag


# ----------------------------------------------------------------------
# On-disk state (~/.config/ezmath/update-state.json)
# ----------------------------------------------------------------------
# The editor's existing config directory is reused; the path helpers
# are injectable and independent of PySide6 (compiler stays stdlib-only).

def default_config_dir():
    """User config dir (``~/.config/ezmath``; same as the editor's)."""
    return os.path.join(os.path.expanduser('~'), '.config', 'ezmath')


def default_state_path():
    return os.path.join(default_config_dir(), STATE_FILE_NAME)


def default_state():
    return {
        'last_check': 0.0,
        'etag': None,
        'latest': None,
        'skipped_version': None,
        'auto_check': True,
        'last_update_error': None,
    }


def load_state(path=None):
    """Load the update state file. Corrupt/unreadable state resets
    silently to the defaults (never raises)."""
    state = default_state()
    if path is None:
        path = default_state_path()
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
    except Exception:
        return state
    if not isinstance(data, dict):
        return state
    merged = default_state()
    for key, value in data.items():
        if key in merged:
            merged[key] = value
    if not isinstance(merged['latest'], (dict, type(None))):
        merged['latest'] = None
    if not isinstance(merged['last_update_error'], (dict, type(None))):
        merged['last_update_error'] = None
    return merged


def save_state(state, path=None):
    """Atomically write the update state file. Best effort: returns
    False instead of raising when the filesystem refuses."""
    import tempfile

    if path is None:
        path = default_state_path()
    try:
        directory = os.path.dirname(path)
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, prefix='.update-state-')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                json.dump(state, handle, indent=1, sort_keys=True)
                handle.write('\n')
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except OSError:
        return False
    return True


def is_prerelease_version(version):
    """True for semver prereleases (``7.1.0-rc.1``)."""
    text = normalize_version(str(version or '')).split('+', 1)[0]
    return bool(re.match(r'^\d+\.\d+\.\d+-', text))


def release_info_from_state(state):
    latest = state.get('latest')
    if not isinstance(latest, dict):
        return None
    try:
        return ReleaseInfo.from_dict(latest)
    except UpdateCheckError:
        return None


@dataclasses.dataclass
class UpdateCheckResult:
    status: str          # 'newer' | 'current' | 'ahead'
    current: str
    latest: ReleaseInfo | None
    error: str | None
    from_cache: bool
    skipped: bool        # latest version == the skipped version


def check_for_update(current_version=None, *, interactive=False,
                     urlopen=None, now=None, state_path=None,
                     timeout=CHECK_TIMEOUT):
    """Check GitHub for a newer release.

    Automatic checks (``interactive=False``) are throttled to at most
    once per 24h and use ETag/If-None-Match so a 304 costs nothing.
    Manual checks (``interactive=True``) always hit the network.
    Never raises: network/parse problems surface as
    ``UpdateCheckResult.error``.
    """
    current = current_version or get_current_version()
    if now is None:
        now = time.time()
    path = state_path or default_state_path()
    state = load_state(path)

    def _result_from_cache():
        cached = release_info_from_state(state)
        skipped = bool(state.get('skipped_version')) and cached is not None \
            and state['skipped_version'] == cached.version
        if cached is None:
            return UpdateCheckResult('current', current, None, None,
                                     True, False)
        status = check_update_status(current, cached.version)
        if status == 'newer' and cached.prerelease \
                and not is_prerelease_version(current):
            status = 'current'
        return UpdateCheckResult(status, current, cached, None, True,
                                 skipped)

    last_check = state.get('last_check') or 0.0
    try:
        last_check = float(last_check)
    except (TypeError, ValueError):
        last_check = 0.0
    if not interactive and last_check and now - last_check < AUTO_CHECK_INTERVAL:
        return _result_from_cache()

    try:
        payload, new_etag = fetch_release(timeout=timeout, urlopen=urlopen,
                                          etag=state.get('etag'))
    except UpdateCheckError as exc:
        cached = _result_from_cache()
        return UpdateCheckResult(cached.status, current, cached.latest,
                                 str(exc), cached.from_cache, cached.skipped)
    if payload is None:  # 304 Not Modified — cache is still valid
        state['last_check'] = now
        save_state(state, path)
        return _result_from_cache()
    try:
        latest = parse_release_info(payload)
    except UpdateCheckError as exc:
        return UpdateCheckResult('current', current, None, str(exc),
                                 False, False)
    skipped = bool(state.get('skipped_version')) \
        and state['skipped_version'] == latest.version
    state['last_check'] = now
    state['etag'] = new_etag
    state['latest'] = latest.to_dict()
    save_state(state, path)
    status = check_update_status(current, latest.version)
    if status == 'newer' and latest.prerelease \
            and not is_prerelease_version(current):
        # Ignore prereleases unless the installed version is itself one.
        status = 'current'
    return UpdateCheckResult(status, current, latest, None, False, skipped)


def skip_version(version, state_path=None):
    """Remember that the user skipped *version* (don't nag again)."""
    path = state_path or default_state_path()
    state = load_state(path)
    state['skipped_version'] = normalize_version(str(version or '')) or None
    save_state(state, path)


def get_auto_check(state_path=None):
    return bool(load_state(state_path).get('auto_check', True))


def set_auto_check(enabled, state_path=None):
    path = state_path or default_state_path()
    state = load_state(path)
    state['auto_check'] = bool(enabled)
    save_state(state, path)


def record_update_error(version, reason, log_path, state_path=None):
    """Persist a failed self-update so the next start can report it."""
    path = state_path or default_state_path()
    state = load_state(path)
    state['last_update_error'] = {
        'version': normalize_version(str(version or '')),
        'reason': str(reason or 'unknown error'),
        'log_path': str(log_path or ''),
        'when': time.time(),
    }
    save_state(state, path)


def last_update_error(state_path=None):
    return load_state(state_path).get('last_update_error')


def clear_update_error(state_path=None):
    path = state_path or default_state_path()
    state = load_state(path)
    if state.get('last_update_error') is not None:
        state['last_update_error'] = None
        save_state(state, path)
