#!/usr/bin/env python3
"""Download, verify and extract the vendored Typst packages.

The compiler ships the Typst packages needed for ``*draw`` inside the
repository (and the packaged builds) so ``*draw`` works fully offline,
with no first-run download from packages.typst.org.

This script downloads the pinned tarballs from
``https://packages.typst.org/preview/<name>-<version>.tar.gz``, verifies
their SHA-256 hashes (pinned below, in this file), and extracts them to::

    vendor/typst-packages/preview/<name>/<version>/

everything the Typst ``package_path`` resolver expects. Files that are
not needed to compile (manuals, galleries, docs PDFs, tests) are
pruned; ``typst.toml``, every ``.typ`` source the package needs, its
LICENSE file(s), the README and runtime assets (e.g. CeTZ's WASM core)
are kept.

The download only happens when this script is run explicitly — the
vendored files are committed to the repository, so source checkouts and
CI builds need no network access. Re-run it to bump a package:

1. Edit the version pins below (keep them in sync with
   ``src/typst_bundle/__init__.py`` — ``tests/test_typst_bundle.py``
   fails otherwise).
2. Delete ``vendor/typst-packages/preview/<name>`` and re-run:

       uv run --frozen python scripts/vendor_typst_packages.py

3. Review the diff and commit the updated files.

Use ``--check`` to verify the vendored tree without any network access
(fails if a package directory or its ``typst.toml`` is missing or does
not match the pinned name/version).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor" / "typst-packages"
BASE_URL = "https://packages.typst.org/preview"

# Pinned packages: (name, version, sha256 of the .tar.gz).
# Keep in sync with src/typst_bundle/__init__.py (TYPST_PACKAGES).
PACKAGES = (
    ("cetz", "0.4.2",
     "e1d2f121b166f1520fc529cad834e2ca5e0b6bcab6816e1d0e07d70836aa0b59"),
    ("oxifmt", "1.0.0",
     "7d17a1fc8ad01740ec3cb2b03c7360a4225ff9318e5710765fa98ea6fd59594f"),
)

# Directories pruned after extraction: not needed to compile. Compared
# case-insensitively against each path component below the package root.
PRUNE_DIRS = {
    "manual",
    "gallery",
    "docs",
    "doc",
    "tests",
    "test",
    "examples",
}

# Files pruned after extraction (matched against the file name).
PRUNE_FILES = {
    # Documentation PDFs are never needed to compile.
    # (Upstream already excludes them from the published tarball; this
    # is belt and braces for future versions.)
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, dest: Path) -> None:
    print(f"downloading {url}")
    with urllib.request.urlopen(url, timeout=60) as response:
        with dest.open("wb") as handle:
            shutil.copyfileobj(response, handle)


def _read_manifest(package_dir: Path) -> tuple[str, str]:
    """Return (name, version) from the package's typst.toml."""
    import tomllib

    manifest = package_dir / "typst.toml"
    with manifest.open("rb") as handle:
        data = tomllib.load(handle)
    package = data.get("package", {})
    return str(package.get("name", "")), str(package.get("version", ""))


def _prune(package_dir: Path) -> None:
    for dirpath, dirnames, filenames in os.walk(package_dir, topdown=True):
        keep = []
        for dirname in dirnames:
            if dirname.lower() in PRUNE_DIRS:
                shutil.rmtree(os.path.join(dirpath, dirname))
            else:
                keep.append(dirname)
        dirnames[:] = keep
        for filename in filenames:
            if filename.lower().endswith(".pdf") or filename in PRUNE_FILES:
                os.remove(os.path.join(dirpath, filename))
    # Drop directories that are now empty (the tarballs ship an empty
    # gallery/ directory for CeTZ).
    for dirpath, dirnames, _ in os.walk(package_dir, topdown=False):
        if dirpath != str(package_dir) and not os.listdir(dirpath):
            os.rmdir(dirpath)


def _tree_size(package_dir: Path) -> int:
    total = 0
    for dirpath, _, filenames in os.walk(package_dir):
        for filename in filenames:
            total += os.path.getsize(os.path.join(dirpath, filename))
    return total


def _format_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if size < 1024 or unit == "GiB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{num_bytes} B"


def _extract_verified(archive: Path, target: Path, name: str, version: str,
                      expected_sha256: str) -> None:
    actual = _sha256(archive)
    if actual != expected_sha256:
        raise SystemExit(
            f"SHA-256 mismatch for {name}-{version}.tar.gz\n"
            f"  expected: {expected_sha256}\n"
            f"  actual:   {actual}\n"
            f"Refusing to extract. If you intentionally bumped the pin, "
            f"update PACKAGES in {Path(__file__).name}.")
    staging = target.parent / f".tmp-{name}-{version}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        with tarfile.open(archive) as tar:
            # filter="data" rejects absolute/parent-traversing members.
            tar.extractall(staging, filter="data")
        if target.exists():
            shutil.rmtree(target)
        os.replace(staging, target)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _check_tree() -> list[str]:
    problems = []
    for name, version, _ in PACKAGES:
        package_dir = VENDOR / "preview" / name / version
        if not package_dir.is_dir():
            problems.append(f"missing vendored package: {package_dir}")
            continue
        try:
            manifest_name, manifest_version = _read_manifest(package_dir)
        except Exception as exc:  # noqa: BLE001 - report any parse failure
            problems.append(f"{package_dir}: cannot read typst.toml: {exc}")
            continue
        if (manifest_name, manifest_version) != (name, version):
            problems.append(
                f"{package_dir}: typst.toml says "
                f"{manifest_name} {manifest_version}, expected {name} {version}")
    return problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true",
        help="verify the vendored tree without network access")
    args = parser.parse_args(argv[1:])

    if args.check:
        problems = _check_tree()
        if problems:
            for problem in problems:
                print(f"error: {problem}", file=sys.stderr)
            return 1
        print("vendored Typst packages OK")
        return 0

    VENDOR.mkdir(parents=True, exist_ok=True)
    total = 0
    with tempfile.TemporaryDirectory(prefix="typst-packages-") as tmp:
        for name, version, sha256 in PACKAGES:
            archive = Path(tmp) / f"{name}-{version}.tar.gz"
            _download(f"{BASE_URL}/{name}-{version}.tar.gz", archive)
            target = VENDOR / "preview" / name / version
            target.parent.mkdir(parents=True, exist_ok=True)
            _extract_verified(archive, target, name, version, sha256)
            _prune(target)
            manifest_name, manifest_version = _read_manifest(target)
            if (manifest_name, manifest_version) != (name, version):
                raise SystemExit(
                    f"{target}: typst.toml says "
                    f"{manifest_name} {manifest_version}, "
                    f"expected {name} {version}")
            size = _tree_size(target)
            total += size
            print(f"vendored {name} {version}: {_format_size(size)} "
                  f"-> {target.relative_to(ROOT)}")
    print(f"total vendored: {_format_size(total)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
