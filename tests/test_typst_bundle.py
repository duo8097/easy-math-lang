"""Vendored Typst packages: single source of truth and tree check.

The Typst packages for ``*draw`` are vendored under
``vendor/typst-packages/`` and must exactly match the pinned versions
in ``src/typst_bundle/__init__.py``. These tests fail when they drift
apart (e.g. a version bump in the constant without re-running
``scripts/vendor_typst_packages.py``, or a hand-edited vendored tree).
"""

import importlib.util
import os
import re
import sys
import tomllib

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import typst_bundle
from typst_bundle import (
    TYPST_PACKAGES,
    cetz_import_line,
    cetz_spec,
    vendored_packages_dir,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENDOR = os.path.join(ROOT, 'vendor', 'typst-packages')
VENDOR_SCRIPT = os.path.join(ROOT, 'scripts', 'vendor_typst_packages.py')


def _read_manifest(package_dir):
    with open(os.path.join(package_dir, 'typst.toml'), 'rb') as handle:
        return tomllib.load(handle).get('package', {})


def test_cetz_spec_format():
    assert re.fullmatch(r'@preview/cetz:\d+\.\d+\.\d+', cetz_spec())
    assert cetz_import_line() == f'#import "{cetz_spec()}"'


def test_vendored_tree_contains_exactly_the_pinned_packages():
    preview = os.path.join(VENDOR, 'preview')
    found = []
    for name in sorted(os.listdir(preview)):
        name_dir = os.path.join(preview, name)
        if not os.path.isdir(name_dir):
            continue
        for version in sorted(os.listdir(name_dir)):
            if os.path.isdir(os.path.join(name_dir, version)):
                found.append((name, version))
    assert found == sorted(TYPST_PACKAGES), (
        f'vendored packages {found} != pinned {sorted(TYPST_PACKAGES)}; '
        f'edit src/typst_bundle/__init__.py and re-run '
        f'scripts/vendor_typst_packages.py')


def test_every_vendored_package_has_matching_manifest():
    for name, version in TYPST_PACKAGES:
        package_dir = os.path.join(VENDOR, 'preview', name, version)
        assert os.path.isdir(package_dir), f'missing vendored package: {package_dir}'
        manifest = os.path.join(package_dir, 'typst.toml')
        assert os.path.isfile(manifest), f'missing typst.toml in {package_dir}'
        meta = _read_manifest(package_dir)
        assert meta.get('name') == name, f'{manifest}: name {meta.get("name")!r} != {name!r}'
        assert meta.get('version') == version, (
            f'{manifest}: version {meta.get("version")!r} != {version!r}')


def test_every_vendored_package_ships_license_and_entry():
    for name, version in TYPST_PACKAGES:
        package_dir = os.path.join(VENDOR, 'preview', name, version)
        entries = os.listdir(package_dir)
        licenses = [e for e in entries if e.upper().startswith('LICENSE')]
        assert licenses, f'{package_dir} ships no LICENSE file'


def _load_vendor_script():
    spec = importlib.util.spec_from_file_location('vendor_typst_packages', VENDOR_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_vendor_script_pins_match_constant():
    module = _load_vendor_script()
    pinned = [(name, version) for name, version, _ in module.PACKAGES]
    assert pinned == list(TYPST_PACKAGES), (
        'scripts/vendor_typst_packages.py PACKAGES drifted from '
        'src/typst_bundle/__init__.py TYPST_PACKAGES')
    for _, _, sha256 in module.PACKAGES:
        assert re.fullmatch(r'[0-9a-f]{64}', sha256), 'SHA-256 pin must be 64 hex chars'


def test_vendored_packages_dir_resolves_from_source():
    assert vendored_packages_dir() == os.path.normpath(VENDOR)


def test_vendored_packages_dir_frozen_layout(monkeypatch, tmp_path):
    # Frozen build without the bundle -> None (caller falls back to the
    # default Typst behavior, never crashes).
    monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
    assert typst_bundle.vendored_packages_dir() is None
    # Complete bundle -> the bundle directory is returned.
    for name, version in TYPST_PACKAGES:
        package_dir = tmp_path / 'typst-packages' / 'preview' / name / version
        package_dir.mkdir(parents=True)
        (package_dir / 'typst.toml').write_text(
            f'[package]\nname = "{name}"\nversion = "{version}"\n',
            encoding='utf-8')
    assert typst_bundle.vendored_packages_dir() == str(tmp_path / 'typst-packages')
