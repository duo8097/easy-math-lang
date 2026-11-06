"""Vendored Typst packages — single source of truth.

The compiler ships the Typst packages needed for ``*draw`` inside the
repository (``vendor/typst-packages/``) and inside the frozen packaged
builds (PyInstaller's ``sys._MEIPASS``), so ``*draw`` works fully
offline with no first-run download from packages.typst.org.

This module defines which packages are vendored (and at which pinned
versions) and builds the ``#import`` line the geometry codegen emits.
Both ``geometry`` and ``compiler`` import it; it lives at the top
level (not inside either package) so neither has to import the other.

Stdlib only, and nothing here may import ``geometry``, ``compiler`` or
``editor`` — keep it a leaf module.
"""

from __future__ import annotations

import os
import sys

CEZ_PACKAGE_NAME = "cetz"
CEZ_VERSION = "0.4.2"

# Every package vendored under vendor/typst-packages/preview/<name>/<version>/.
# Keep in sync with the pins in scripts/vendor_typst_packages.py —
# tests/test_typst_bundle.py fails otherwise.
TYPST_PACKAGES = (
    (CEZ_PACKAGE_NAME, CEZ_VERSION),
    ("oxifmt", "1.0.0"),  # imported by CeTZ (src/deps.typ)
)

# Directory name inside the PyInstaller bundle (sys._MEIPASS) and inside
# the repository's vendor/ directory. The layout below it must be
# preview/<name>/<version>/ — that is what Typst's package_path resolver
# expects.
BUNDLE_DIRNAME = "typst-packages"


def cetz_spec() -> str:
    """The fully-qualified Typst import specifier (``@preview/cetz:0.4.2``)."""
    return f"@preview/{CEZ_PACKAGE_NAME}:{CEZ_VERSION}"


def cetz_import_line() -> str:
    """The ``#import`` line emitted into generated Typst documents."""
    return f'#import "{cetz_spec()}"'


def _is_complete(root: str) -> bool:
    for name, version in TYPST_PACKAGES:
        if not os.path.isfile(
                os.path.join(root, "preview", name, version, "typst.toml")):
            return False
    return True


def vendored_packages_dir() -> str | None:
    """Absolute path of the vendored package root, or ``None``.

    Pass the result to Typst as ``package_path`` (the layout below it is
    ``preview/<name>/<version>``). ``None`` means the bundle is missing —
    callers must fall back to Typst's default behavior (an already
    populated user cache, or a download from packages.typst.org), never
    crash.
    """
    frozen = getattr(sys, "_MEIPASS", None)
    if frozen:
        candidate = os.path.join(frozen, BUNDLE_DIRNAME)
        return candidate if _is_complete(candidate) else None
    # Source checkout: this file is <repo>/src/typst_bundle/__init__.py.
    candidate = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        os.pardir, os.pardir, "vendor", BUNDLE_DIRNAME))
    return candidate if _is_complete(candidate) else None
