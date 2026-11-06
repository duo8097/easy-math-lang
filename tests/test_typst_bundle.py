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


def _make_bundle(root):
    for name, version in TYPST_PACKAGES:
        package_dir = root / 'preview' / name / version
        package_dir.mkdir(parents=True)
        (package_dir / 'typst.toml').write_text(
            f'[package]\nname = "{name}"\nversion = "{version}"\n',
            encoding='utf-8')


def test_vendored_packages_dir_frozen_layout(monkeypatch, tmp_path):
    # Frozen build without the bundle -> None (caller falls back to the
    # default Typst behavior, never crashes).
    monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
    assert typst_bundle.vendored_packages_dir() is None
    # Complete bundle -> the bundle directory is returned.
    _make_bundle(tmp_path / 'typst-packages')
    assert typst_bundle.vendored_packages_dir() == str(tmp_path / 'typst-packages')


def test_vendored_packages_dir_wheel_layout(monkeypatch, tmp_path):
    # pip-installed wheel: the bundle ships inside the package as
    # package data (typst_bundle/typst-packages).
    pkg = tmp_path / 'site-packages' / 'typst_bundle'
    pkg.mkdir(parents=True)
    (pkg / '__init__.py').write_text('# wheel data host', encoding='utf-8')
    _make_bundle(pkg / 'typst-packages')
    monkeypatch.setattr(typst_bundle, '__file__', str(pkg / '__init__.py'))
    assert typst_bundle.vendored_packages_dir() == str(pkg / 'typst-packages')


def test_vendored_packages_dir_missing_everywhere(monkeypatch, tmp_path):
    pkg = tmp_path / 'site-packages' / 'typst_bundle'
    pkg.mkdir(parents=True)
    (pkg / '__init__.py').write_text('# wheel data host', encoding='utf-8')
    monkeypatch.setattr(typst_bundle, '__file__', str(pkg / '__init__.py'))
    assert typst_bundle.vendored_packages_dir() is None


# --------------------------------------------------------------------------
# Offline compile: an empty, temporary Typst package cache must be enough,
# and must stay empty — proving the vendored bundle (not a download)
# served the CeTZ import.
# --------------------------------------------------------------------------

def _isolated_env(monkeypatch, tmp_path):
    """Redirect every cache/data dir Typst may consult into tmp_path."""
    home = tmp_path / 'home'
    cache = tmp_path / 'cache'
    data = tmp_path / 'data'
    local = tmp_path / 'localappdata'
    roaming = tmp_path / 'appdata'
    xdg = tmp_path / 'xdg-config'
    for d in (home, cache, data, local, roaming, xdg):
        d.mkdir()
    # Linux (XDG_CACHE_HOME / XDG_DATA_HOME), macOS (~/Library/...) and
    # Windows (%LOCALAPPDATA% / %APPDATA% / %USERPROFILE%) equivalents.
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setenv('USERPROFILE', str(home))
    monkeypatch.setenv('XDG_CACHE_HOME', str(cache))
    monkeypatch.setenv('XDG_DATA_HOME', str(data))
    monkeypatch.setenv('XDG_CONFIG_HOME', str(xdg))
    monkeypatch.setenv('LOCALAPPDATA', str(local))
    monkeypatch.setenv('APPDATA', str(roaming))
    return cache


def test_draw_compiles_with_empty_package_cache(monkeypatch, tmp_path):
    import typst as real_typst
    from compiler import pipeline

    record = {}

    class _RecordingTypst:
        """Real compile, but with the package cache forced to an empty
        temporary directory (the dirs crate ignores env vars on Windows,
        so we pin it explicitly) and the call kwargs recorded."""

        @staticmethod
        def compile(*args, **kwargs):
            record.update(kwargs)
            forced_cache = str(tmp_path / 'forced-cache')
            os.makedirs(forced_cache, exist_ok=True)
            kwargs.setdefault('package_cache_path', forced_cache)
            return real_typst.compile(*args, **kwargs)

    cache_dir = _isolated_env(monkeypatch, tmp_path)
    monkeypatch.setattr(pipeline, 'typst', _RecordingTypst)

    src = tmp_path / 'draw.ezmath'
    src.write_text('*draw(\n'
                   '    *point(A = 0, 0)\n'
                   '    *point(B = 3, 4)\n'
                   '    *line(A ; B)\n'
                   ')\n', encoding='utf-8')
    out = tmp_path / 'draw.pdf'
    assert pipeline.compile_ezmath(str(src), output=str(out)) is True
    assert out.is_file() and out.stat().st_size > 0

    # The compile must have been given the vendored bundle as
    # package_path...
    assert record.get('package_path') == os.path.normpath(VENDOR)
    # ...and nothing may have been downloaded into any redirected cache.
    for base in (cache_dir, tmp_path / 'home', tmp_path / 'data',
                 tmp_path / 'localappdata', tmp_path / 'appdata',
                 tmp_path / 'forced-cache'):
        leftovers = [p for p in base.rglob('*') if p.is_dir()]
        assert leftovers == [], (
            f'typst cache/data appeared under {base}: {leftovers} — '
            f'the bundle was not used')
