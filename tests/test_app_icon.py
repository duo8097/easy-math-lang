"""Static and runtime checks for the Easy Math app icon wiring.

Covers the three icon surfaces:

- the Qt window/taskbar icon (the single 256px PNG bundled under
  ``editor/assets`` and resolved by ``editor.paths.icon_path``),
- the Windows executable + Inno Setup icon (the multi-size
  ``icons/ezmath.ico`` asset, referenced only at build time), and
- the Linux/Arch desktop entry + hicolor icons (``Icon=ezmath`` with
  one PNG per size installed under
  ``/usr/share/icons/hicolor/<size>x<size>/apps/``).

Nothing here may regenerate, resize or re-encode the ``icons/`` assets:
they are input files, and the checks below only read them.
"""

import os
import re
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

ICONS = os.path.join(ROOT, "icons")
BUNDLED_ICON = os.path.join(ROOT, "src", "editor", "assets", "ezmath-256.png")
ISS = os.path.join(ROOT, "installer", "setup.iss")
DESKTOP = os.path.join(ROOT, "installer", "easy-math-editor.desktop")
PKGBUILD = os.path.join(ROOT, "installer", "PKGBUILD")
BUILD_LINUX = os.path.join(ROOT, "installer", "build_linux.sh")
BUILDER = os.path.join(ROOT, "scripts", "build_binaries.py")

ICON_SIZES = (16, 32, 48, 64, 128, 256)


def _read(path):
    with open(path, encoding="utf-8-sig") as handle:
        return handle.read()


def test_icon_assets_exist_as_provided():
    for name in ("ezmath.ico", "ezmath-icon.png"):
        assert os.path.isfile(os.path.join(ICONS, name)), name
    for size in ICON_SIZES:
        path = os.path.join(ICONS, f"ezmath-{size}.png")
        assert os.path.isfile(path), f"missing icons/ezmath-{size}.png"


def test_bundled_icon_is_verbatim_copy_of_icons_256():
    assert os.path.isfile(BUNDLED_ICON), \
        "src/editor/assets/ezmath-256.png is missing"
    with open(os.path.join(ICONS, "ezmath-256.png"), "rb") as handle:
        original = handle.read()
    with open(BUNDLED_ICON, "rb") as handle:
        bundled = handle.read()
    assert bundled == original, \
        "the bundled icon must be a verbatim copy of icons/ezmath-256.png"


def test_icon_path_resolves_inside_package_without_cwd():
    from editor.paths import icon_path

    path = icon_path()
    assert path is not None, "icon_path() returned None in a checkout"
    assert os.path.isfile(path)
    # Must live inside the editor package, never the repo-root icons/
    # folder and never relative to the current working directory.
    assert os.path.realpath(path) == os.path.realpath(
        os.path.join(ROOT, "src", "editor", "assets", "ezmath-256.png"))
    assert not os.path.realpath(path).startswith(
        os.path.realpath(ICONS) + os.sep)


def test_packaged_icon_loads_as_qicon(qapp):
    from editor.paths import icon_path

    from PySide6 import QtGui

    icon = QtGui.QIcon(icon_path())
    assert not icon.isNull()


def test_main_window_carries_app_icon(qapp):
    pytest.importorskip("PySide6")
    from editor.main_window import MainWindow

    window = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        assert not window.windowIcon().isNull()
    finally:
        window.close()


def test_builder_embeds_ico_on_windows_only():
    text = _read(BUILDER)
    assert '"--icon"' in text
    assert "icons" in text and "ezmath.ico" in text
    # The flag is gated on Windows: Linux ignores --icon and macOS would
    # need an .icns bundle, which is not shipped.
    assert 'os.name == "nt"' in text


def test_builder_bundles_only_the_256_png():
    text = _read(BUILDER)
    assert "ezmath-256.png" in text
    assert "--add-data" in text
    # The whole icons/ folder (including the 1024px master and the .ico)
    # must never be shipped inside the Python bundle.
    for name in ("ezmath-icon.png", "ezmath-16.png", "ezmath-32.png",
                 "ezmath-48.png", "ezmath-64.png", "ezmath-128.png"):
        assert name not in text, \
            f"{name} must not be bundled in the frozen binaries"


def test_setup_iss_uses_app_icon():
    text = _read(ISS)
    setup = re.search(r"(?ms)^\[Setup\]\s*\n(.*?)(?=^\[|\Z)", text)
    assert setup, "no [Setup] section found"
    for key in ("SetupIconFile", "UninstallDisplayIcon"):
        match = re.search(rf"(?im)^{key}\s*=\s*(\S+)\s*$", setup.group(1))
        assert match, f"{key} missing from [Setup]"
        assert "icons\\ezmath.ico" in match.group(1) or \
            "icons/ezmath.ico" in match.group(1)


def test_desktop_entry_uses_theme_icon():
    text = _read(DESKTOP)
    match = re.search(r"(?m)^Icon\s*=\s*(\S+)\s*$", text)
    assert match, "desktop entry has no Icon= line"
    assert match.group(1) == "ezmath"


def test_pkgbuild_installs_hicolor_icons():
    text = _read(PKGBUILD)
    assert "usr/share/icons/hicolor" in text
    for size in ICON_SIZES:
        assert f"${{size}}x${{size}}" in text or \
            f"{size}x{size}" in text or \
            "icons/ezmath-${size}.png" in text


def test_linux_staging_and_rpm_spec_install_hicolor_icons():
    text = _read(BUILD_LINUX)
    assert "usr/share/icons/hicolor" in text
    assert "icons/ezmath-" in text
    for size in ICON_SIZES:
        assert f"/usr/share/icons/hicolor/{size}x{size}/apps/ezmath.png" \
            in text, f"rpm %files entry missing for size {size}"
