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
import re
import urllib.error
import urllib.request

APP_NAME = 'EasyMath Lang'
DISTRIBUTION_NAME = 'easy-math-lang'
# Fallback when installed metadata is unavailable (e.g. frozen build).
# Source of truth stays ``pyproject.toml``; keep this in sync on release.
FALLBACK_VERSION = '1.1.1'

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
    fetch_latest = fetch or get_latest_release_info
    try:
        latest, url = fetch_latest()
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
    else:
        emit('You are up to date.')
    return 0
