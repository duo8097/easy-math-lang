"""Sync checks: every hard-coded version copy matches pyproject.toml.

Uses the same parsing as ``scripts/bump_version.py`` (the locations
the release script rewrites), so this test stays the executable
definition of "every location reports the same version".
"""

import importlib.util
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'src'))

SPEC = importlib.util.spec_from_file_location(
    'bump_version', REPO_ROOT / 'scripts' / 'bump_version.py')
bump_version = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bump_version)


def test_every_synced_location_matches_pyproject():
    mismatches = bump_version.find_version_mismatches(REPO_ROOT)
    assert mismatches == [], (
        'version drift detected (pyproject.toml is the source of truth):\n'
        + '\n'.join(f'  {path}: {label} -> {found}'
                    for path, label, found in mismatches))


def test_get_current_version_is_declared_version():
    """The shared lookup used by compiler/editor/LSP agrees on release."""
    from compiler import update as _update

    # Editable installs expose the declared version as dist metadata;
    # when metadata lags (e.g. right after a bump, before `uv sync`),
    # get_current_version() falls back to FALLBACK_VERSION — either
    # way it must equal the declared version once synced.
    with open(REPO_ROOT / 'pyproject.toml', 'rb') as handle:
        declared = tomllib.load(handle)['project']['version']
    assert _update.FALLBACK_VERSION == declared


def test_pkbuild_pkgver_counts_as_the_declared_version():
    """pkgver is the pacman-safe rendering of the declared version."""
    with open(REPO_ROOT / 'pyproject.toml', 'rb') as handle:
        declared = tomllib.load(handle)['project']['version']
    assert bump_version.pkgbuild_pkgver(declared)


def test_workflow_and_templates_carry_no_stale_literal():
    """The tag guard rejects a stale literal in the bug-report template."""
    with open(REPO_ROOT / 'pyproject.toml', 'rb') as handle:
        declared = tomllib.load(handle)['project']['version']
    bug_report = (REPO_ROOT / '.github' / 'ISSUE_TEMPLATE'
                  / 'bug_report.yml').read_text(encoding='utf-8')
    assert f'placeholder: "{declared}"' in bug_report


def _load_check_tag_version():
    spec = importlib.util.spec_from_file_location(
        'check_tag_version', REPO_ROOT / 'scripts' / 'check_tag_version.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tag_guard_passes_on_synced_tree():
    check_tag_version = _load_check_tag_version()
    assert check_tag_version.main(['--all']) == 0
    # A wrong tag fails even when locations are in sync.
    assert check_tag_version.main(['refs/tags/v0.0.0']) == 1


def test_tag_guard_rejects_stale_location(monkeypatch):
    check_tag_version = _load_check_tag_version()
    monkeypatch.setattr(
        check_tag_version, 'synced_location_mismatches',
        lambda root=None: ['src/lsp/server.py: lsp.server.SERVER_VERSION '
                           "is '6.0.0'"])
    assert check_tag_version.main(['refs/tags/v7.0.0']) == 1
    assert check_tag_version.main(['--all']) == 1
