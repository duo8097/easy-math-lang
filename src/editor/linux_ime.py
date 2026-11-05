"""fcitx5 IME plugin support for PySide6 on Linux.

PySide6 bundles Qt with only the ibus and compose platforminputcontexts
plugins, so on Linux systems running fcitx5 (e.g. for Vietnamese Telex via
fcitx5-lotus) no input method works out of the box. This module locates the
system's fcitx5 platform input context plugin and symlinks it into a private
plugin directory that is prepended to ``QT_PLUGIN_PATH`` before QApplication
is created.

The fix:

* runs on Linux only (no-op on Windows/macOS),
* is opt-out via ``EZMATH_NO_IME_FIX=1``,
* does nothing when ``QT_IM_MODULE`` is set to something other than
  ``fcitx``/``fcitx5``,
* only proceeds when the system Qt major.minor matches PySide6's bundled Qt
  (when the system version cannot be determined it proceeds with a warning),
* never raises: any failure is logged to stderr and the editor starts anyway.
"""

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# System plugin search locations, in order of precedence. Each is checked for
# platforminputcontexts/libfcitx5platforminputcontextplugin.so.
_STANDARD_PLUGIN_DIRS = (
    Path("/usr/lib/qt6/plugins"),
    Path("/usr/lib64/qt6/plugins"),
    Path("/usr/lib/x86_64-linux-gnu/qt6/plugins"),
    Path("/usr/lib/aarch64-linux-gnu/qt6/plugins"),
    Path("/usr/lib/qt/plugins"),
)

_PLUGIN_RELPATH = Path("platforminputcontexts") / "libfcitx5platforminputcontextplugin.so"


def _is_linux() -> bool:
    """Check if we're running on Linux."""
    return sys.platform.startswith("linux")


def _should_skip() -> bool:
    """Check if we should skip the IME fix.

    Returns True when not on Linux, when ``EZMATH_NO_IME_FIX=1`` is set, or
    when ``QT_IM_MODULE`` is set to something other than ``fcitx``/``fcitx5``.
    """
    if not _is_linux():
        logger.debug("Not on Linux, skipping fcitx5 IME fix")
        return True

    if os.environ.get("EZMATH_NO_IME_FIX") == "1":
        logger.debug("EZMATH_NO_IME_FIX=1 is set, skipping fcitx5 IME fix")
        return True

    qt_im_module = os.environ.get("QT_IM_MODULE", "")
    if qt_im_module and qt_im_module not in ("fcitx", "fcitx5"):
        logger.debug(f"QT_IM_MODULE={qt_im_module} is set, skipping fcitx5 IME fix")
        return True

    return False


def _get_system_qt_version() -> Optional[str]:
    """Get the system Qt version.

    Tries ``qmake6 -query QT_VERSION`` first, then ``qtpaths6 --query
    QT_VERSION``. Returns the version string (e.g. ``"6.12.0"``), or ``None``
    when it cannot be determined (the caller proceeds with a warning).
    """
    try:
        result = subprocess.run(
            ["qmake6", "-query", "QT_VERSION"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            version = result.stdout.strip().splitlines()[0].strip()
            logger.debug(f"Got Qt version from qmake6: {version}")
            return version
    except (subprocess.SubprocessError, OSError) as e:
        logger.debug(f"Failed to get Qt version from qmake6: {e}")

    try:
        result = subprocess.run(
            ["qtpaths6", "--query", "QT_VERSION"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            if output:
                # `qtpaths6 --query QT_VERSION` prints just the version; be
                # tolerant of "QT_VERSION: 6.12.0" style output as well.
                for line in output.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    candidate = line.split(":", 1)[-1].strip() if ":" in line else line
                    if candidate and candidate[0].isdigit():
                        logger.debug(f"Got Qt version from qtpaths6: {candidate}")
                        return candidate
    except (subprocess.SubprocessError, OSError) as e:
        logger.debug(f"Failed to get Qt version from qtpaths6: {e}")

    logger.warning(
        "Could not determine the system Qt version (qmake6/qtpaths6 not "
        "available or failed); assuming it matches PySide6's Qt and "
        "proceeding. Set EZMATH_NO_IME_FIX=1 to disable the fcitx5 IME fix."
    )
    return None


def _get_pyside6_qt_version() -> Optional[str]:
    """Get PySide6's bundled Qt version (e.g. ``"6.12.0"``), or ``None``."""
    try:
        from PySide6 import QtCore

        version = QtCore.qVersion()
        logger.debug(f"PySide6 Qt version: {version}")
        return version
    except Exception as e:
        logger.warning(f"Failed to get PySide6 Qt version: {e}")
        return None


def _major_minor(version: str) -> str:
    parts = version.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else version


def _check_version_match(
    system_version: Optional[str], pyside6_version: Optional[str]
) -> bool:
    """Check whether the system Qt matches PySide6's Qt at major.minor.

    An unknown version on either side is not treated as a mismatch (the
    caller proceeds with a warning); only a known mismatch returns False.
    """
    if not system_version or not pyside6_version:
        logger.warning(
            "Could not verify that the system Qt matches PySide6's Qt "
            f"(system={system_version!r}, pyside6={pyside6_version!r}); "
            "proceeding anyway."
        )
        return True

    match = _major_minor(system_version) == _major_minor(pyside6_version)
    if not match:
        logger.warning(
            f"System Qt ({system_version}) does not match PySide6's Qt "
            f"({pyside6_version}) at the major.minor level; skipping the "
            "fcitx5 IME fix. fcitx5 input will not work in the editor. "
            "Set EZMATH_NO_IME_FIX=1 to silence this warning."
        )
    return match


def _iter_search_paths() -> List[Path]:
    """Return the plugin search paths, in order, deduplicated."""
    paths: List[Path] = []

    qt_plugin_path = os.environ.get("QT_PLUGIN_PATH", "")
    for entry in qt_plugin_path.split(os.pathsep):
        entry = entry.strip()
        if entry:
            paths.append(Path(entry))

    paths.extend(_STANDARD_PLUGIN_DIRS)

    seen = set()
    unique: List[Path] = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def _find_fcitx5_plugin() -> Optional[Path]:
    """Find the system fcitx5 platforminputcontexts plugin.

    Searches ``$QT_PLUGIN_PATH`` entries first, then the standard system Qt6
    plugin directories. Symlinks are resolved. Returns the resolved plugin
    path, or ``None`` when not found.
    """
    for search_path in _iter_search_paths():
        plugin_path = search_path / _PLUGIN_RELPATH
        try:
            if plugin_path.is_file():
                resolved = plugin_path.resolve()
                logger.debug(f"Found fcitx5 plugin at: {resolved}")
                return resolved
        except OSError as e:
            logger.debug(f"Error checking {plugin_path}: {e}")

    logger.warning(
        "Could not find libfcitx5platforminputcontextplugin.so in QT_PLUGIN_PATH "
        "or the standard system Qt plugin directories; fcitx5 input will not "
        "work in the editor. Install the fcitx5 Qt6 platform input context "
        "plugin (e.g. the fcitx5-qt package) to enable it."
    )
    return None


def _create_private_plugin_dir() -> Path:
    """Create and return the private plugin dir under the user cache.

    Located at ``$XDG_CACHE_HOME/easy-math-lang/qt-plugins/platforminputcontexts``
    (default ``~/.cache/...``). The dir's parent (``qt-plugins``) is what gets
    prepended to ``QT_PLUGIN_PATH``.
    """
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    cache_dir = Path(xdg_cache) if xdg_cache else Path.home() / ".cache"

    plugin_dir = cache_dir / "easy-math-lang" / "qt-plugins" / "platforminputcontexts"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Created private plugin directory: {plugin_dir}")
    return plugin_dir


def _ensure_plugin_symlink(plugin_path: Path, target_dir: Path) -> bool:
    """Symlink ``plugin_path`` into ``target_dir``, copying as a fallback.

    Idempotent: an existing link pointing at the right target is left alone;
    a stale link/copy (or a broken symlink) is replaced. Returns True on
    success, False otherwise.
    """
    plugin_path = plugin_path.resolve()
    target_file = target_dir / plugin_path.name

    try:
        if target_file.is_symlink() or target_file.exists():
            if target_file.is_symlink():
                if target_file.readlink() == plugin_path:
                    logger.debug(f"Symlink already points to {plugin_path}")
                    return True
                logger.debug(f"Replacing stale symlink: {target_file}")
            else:
                # A copied .so from a previous run: keep it only if it matches.
                try:
                    if target_file.stat().st_mtime == plugin_path.stat().st_mtime and (
                        target_file.stat().st_size == plugin_path.stat().st_size
                    ):
                        logger.debug(f"Existing copy at {target_file} looks current")
                        return True
                except OSError:
                    pass
                logger.debug(f"Replacing stale file: {target_file}")
            target_file.unlink()

        try:
            target_file.symlink_to(plugin_path)
            logger.debug(f"Created symlink: {target_file} -> {plugin_path}")
            return True
        except OSError as e:
            logger.warning(f"Failed to create symlink ({e}); falling back to copy")
            shutil.copy2(plugin_path, target_file)
            logger.debug(f"Created copy: {target_file} <- {plugin_path}")
            return True
    except OSError as e:
        logger.error(f"Failed to set up fcitx5 plugin in {target_dir}: {e}")
        return False


def _setup_fcitx5_ime() -> bool:
    """Do the full IME setup; returns True (also when skipped/failed)."""
    if _should_skip():
        return True

    logger.info("Setting up fcitx5 IME support for PySide6 on Linux")

    system_version = _get_system_qt_version()
    pyside6_version = _get_pyside6_qt_version()

    if not _check_version_match(system_version, pyside6_version):
        # Actual major.minor mismatch: the plugin would not load (or worse,
        # corrupt Qt). One clear warning, then skip.
        return True

    plugin_path = _find_fcitx5_plugin()
    if not plugin_path:
        return True

    try:
        target_dir = _create_private_plugin_dir()
    except OSError as e:
        logger.warning(f"Failed to create private plugin directory: {e}")
        return True

    if not _ensure_plugin_symlink(plugin_path, target_dir):
        return True

    # Prepend the private dir's parent (…/qt-plugins) to QT_PLUGIN_PATH,
    # keeping any user-provided entries after ours.
    parent_dir = str(target_dir.parent)
    existing = os.environ.get("QT_PLUGIN_PATH", "")
    os.environ["QT_PLUGIN_PATH"] = (
        f"{parent_dir}{os.pathsep}{existing}" if existing else parent_dir
    )
    os.environ.setdefault("QT_IM_MODULE", "fcitx")

    logger.info(f"Set QT_PLUGIN_PATH={os.environ['QT_PLUGIN_PATH']}")
    logger.info(f"Set QT_IM_MODULE={os.environ['QT_IM_MODULE']}")
    logger.info("fcitx5 IME setup completed successfully")
    return True


def setup_fcitx5_ime() -> bool:
    """Entry point: call at the top of ``main()``, before QApplication.

    Never raises; any unexpected error is logged to stderr and the editor
    continues without the IME fix.
    """
    try:
        if not logging.getLogger(__name__).handlers and not logging.root.handlers:
            logging.basicConfig(level=logging.WARNING)
        return _setup_fcitx5_ime()
    except Exception as e:  # noqa: BLE001 - must never break editor startup
        logger.error(f"Unexpected error in fcitx5 IME setup: {e}")
        return True
