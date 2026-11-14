"""Tests for ``scripts/bump_version.py`` (no real repo, no network).

The script runs against a temporary copy of the repo layout; ``uv
lock`` is replaced by an injected fake runner. Covers: major/minor/
patch/explicit targets, rc versions, ``--dry-run`` (no writes),
refusal on a lower version, refusal on an empty [Unreleased], rollback
when one file fails, and failure on a missing or duplicated anchor.
"""

import importlib.util
import json
import os
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    'bump_version', REPO_ROOT / 'scripts' / 'bump_version.py')
bump_version = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bump_version)


PYPROJECT = '''[project]
name = "easy-math-lang"
version = "{version}"
description = "fixture"
'''

UV_LOCK = '''version = 1

[[package]]
name = "easy-math-lang"
version = "{version}"
source = {{ editable = "." }}
'''

UPDATE_PY = '''"""fixture."""

FALLBACK_VERSION = '{version}'
REPO = 'duo8097/easy-math-lang'
'''

LSP_SERVER = '''"""fixture."""

SERVER_NAME = 'easy-math-lsp'
SERVER_VERSION = '{version}'
'''

EDITOR_APP = '''"""fixture."""


def _app_version():
    return '{version}'
'''

HELP_DIALOGS = '''"""fixture."""


class AboutDialog:
    def __init__(self, version='{version}', parent=None):
        pass
'''

PKGBUILD = '''# fixture
pkgname=easy-math-lang-git
pkgver={pkgver}
pkgrel=1
'''

BUG_REPORT = '''name: Bug report
body:
  - type: input
    id: version
    attributes:
      placeholder: "{version}"
'''

CHANGELOG = '''# Changelog

## [Unreleased]

### Added
- Something shiny.

## [{version}] - 2026-11-12

### Fixed
- An older fix.

[Unreleased]: https://github.com/duo8097/easy-math-lang/compare/v{version}...HEAD
[{version}]: https://github.com/duo8097/easy-math-lang/compare/v6.0.0...v{version}
'''

README = '''# fixture

## Changelog

### [{version}] - 2026-11-12

#### Added
- Something shiny.

Earlier releases are listed in
[CHANGELOG.md](CHANGELOG.md).

[{version}]: https://github.com/duo8097/easy-math-lang/compare/v6.0.0...v{version}
'''

CHANGELOG_EMPTY_UNRELEASED = '''# Changelog

## [Unreleased]

## [{version}] - 2026-11-12

### Fixed
- An older fix.

[Unreleased]: https://github.com/duo8097/easy-math-lang/compare/v{version}...HEAD
[{version}]: https://github.com/duo8097/easy-math-lang/compare/v6.0.0...v{version}
'''


def _write(root, relpath, content):
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')


@pytest.fixture
def temp_repo(tmp_path):
    """A minimal but complete copy of the repo layout at 7.0.0."""
    version = '7.0.0'
    _write(tmp_path, 'pyproject.toml', PYPROJECT.format(version=version))
    _write(tmp_path, 'uv.lock', UV_LOCK.format(version=version))
    _write(tmp_path, 'src/compiler/update.py', UPDATE_PY.format(version=version))
    _write(tmp_path, 'src/lsp/server.py', LSP_SERVER.format(version=version))
    _write(tmp_path, 'src/editor/app.py', EDITOR_APP.format(version=version))
    _write(tmp_path, 'src/editor/help_dialogs.py',
           HELP_DIALOGS.format(version=version))
    _write(tmp_path, 'installer/PKGBUILD',
           PKGBUILD.format(pkgver=version))
    _write(tmp_path, '.github/ISSUE_TEMPLATE/bug_report.yml',
           BUG_REPORT.format(version=version))
    _write(tmp_path, 'CHANGELOG.md', CHANGELOG.format(version=version))
    _write(tmp_path, 'README.md', README.format(version=version))
    return tmp_path


def fake_uv_lock(cmd, cwd=None):
    """Stand-in for ``uv lock``: bumps the easy-math-lang entry in place."""
    assert cmd[-1] == 'lock'
    pyproject = Path(cwd) / 'pyproject.toml'
    with open(pyproject, 'rb') as handle:
        version = tomllib.load(handle)['project']['version']
    lock = Path(cwd) / 'uv.lock'
    text = lock.read_text(encoding='utf-8')
    text = text.replace(f'version = "7.0.0"', f'version = "{version}"', 1)
    lock.write_text(text, encoding='utf-8')
    return 0


def failing_uv_lock(cmd, cwd=None):
    return 3


def _snapshot_tree(root):
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob('*')) if path.is_file()
    }


def _run(root, *argv, uv_runner=fake_uv_lock):
    return bump_version.main(list(argv), root=root, uv_runner=uv_runner)


# --------------------------------------------------------------------------
# Target resolution / validation
# --------------------------------------------------------------------------

def test_pkgbuild_pkgver_mapping():
    assert bump_version.pkgbuild_pkgver('7.0.0') == '7.0.0'
    assert bump_version.pkgbuild_pkgver('7.1.0-rc.1') == '7.1.0rc1'
    assert bump_version.pkgbuild_pkgver('8.0.0-rc.12') == '8.0.0rc12'


def test_resolve_major_minor_patch(temp_repo):
    assert bump_version.resolve_target('7.0.0', 'major', False) == '8.0.0'
    assert bump_version.resolve_target('7.0.0', 'minor', False) == '7.1.0'
    assert bump_version.resolve_target('7.0.0', 'patch', False) == '7.0.1'
    # A prerelease current version bumps the release it leads to.
    assert bump_version.resolve_target('7.1.0-rc.1', 'minor', False) == '7.2.0'


def test_resolve_explicit_version(temp_repo):
    assert bump_version.resolve_target('7.0.0', '7.1.0', False) == '7.1.0'
    assert bump_version.resolve_target('7.0.0', '7.1.0-rc.1', False) == '7.1.0-rc.1'


def test_resolve_rejects_garbage():
    with pytest.raises(bump_version.BumpError):
        bump_version.resolve_target('7.0.0', 'seven', False)
    with pytest.raises(bump_version.BumpError):
        bump_version.resolve_target('7.0.0', '7.0', False)
    with pytest.raises(bump_version.BumpError):
        bump_version.resolve_target('7.0.0', '7.0.0.1', False)


def test_validate_refuses_lower_or_equal(temp_repo):
    with pytest.raises(bump_version.BumpError):
        bump_version.resolve_target('7.0.0', '6.9.9', False)
    with pytest.raises(bump_version.BumpError):
        bump_version.resolve_target('7.0.0', '7.0.0', False)
    # --force allows it.
    assert bump_version.resolve_target('7.0.0', '7.0.0', True) == '7.0.0'
    assert bump_version.resolve_target('7.0.0', '6.9.9', True) == '6.9.9'
    # Prereleases sort before their release.
    with pytest.raises(bump_version.BumpError):
        bump_version.resolve_target('7.1.0', '7.1.0-rc.1', False)
    assert bump_version.resolve_target('7.1.0-rc.1', '7.1.0', False) == '7.1.0'


# --------------------------------------------------------------------------
# End-to-end bumps against the fixture repo
# --------------------------------------------------------------------------

def test_bump_patch(temp_repo):
    assert _run(temp_repo, 'patch') == 0
    with open(temp_repo / 'pyproject.toml', 'rb') as handle:
        assert tomllib.load(handle)['project']['version'] == '7.0.1'
    assert "FALLBACK_VERSION = '7.0.1'" in (
        temp_repo / 'src/compiler/update.py').read_text()
    assert "SERVER_VERSION = '7.0.1'" in (
        temp_repo / 'src/lsp/server.py').read_text()
    assert "return '7.0.1'" in (temp_repo / 'src/editor/app.py').read_text()
    assert "version='7.0.1'" in (
        temp_repo / 'src/editor/help_dialogs.py').read_text()
    assert 'pkgver=7.0.1\n' in (temp_repo / 'installer/PKGBUILD').read_text()
    assert 'placeholder: "7.0.1"' in (
        temp_repo / '.github/ISSUE_TEMPLATE/bug_report.yml').read_text()
    changelog = (temp_repo / 'CHANGELOG.md').read_text()
    assert '## [Unreleased]\n\n## [7.0.1] - ' in changelog
    assert '[Unreleased]: https://github.com/duo8097/easy-math-lang/compare/v7.0.1...HEAD' in changelog
    assert '[7.0.1]: https://github.com/duo8097/easy-math-lang/compare/v7.0.0...v7.0.1' in changelog
    readme = (temp_repo / 'README.md').read_text()
    assert '### [7.0.1] - ' in readme
    assert '[7.0.1]: https://github.com/duo8097/easy-math-lang/compare/v7.0.0...v7.0.1' in readme
    assert '#### Added\n- Something shiny.' in readme
    # uv.lock was refreshed by the (fake) uv lock.
    assert 'version = "7.0.1"' in (temp_repo / 'uv.lock').read_text()


def test_bump_major_and_minor(temp_repo):
    assert _run(temp_repo, 'major') == 0
    with open(temp_repo / 'pyproject.toml', 'rb') as handle:
        assert tomllib.load(handle)['project']['version'] == '8.0.0'


def test_bump_rc_version_pkgbuild_mapping(temp_repo):
    assert _run(temp_repo, '7.1.0-rc.1') == 0
    assert 'pkgver=7.1.0rc1\n' in (temp_repo / 'installer/PKGBUILD').read_text()
    changelog = (temp_repo / 'CHANGELOG.md').read_text()
    assert '## [7.1.0-rc.1] - ' in changelog
    assert 'compare/v7.1.0-rc.1...HEAD' in changelog
    assert 'compare/v7.0.0...v7.1.0-rc.1' in changelog


def test_bump_explicit_prerelease_stays_syncable(temp_repo):
    """An rc bump must pass find_version_mismatches (tag-build guard)."""
    assert _run(temp_repo, '7.1.0-rc.1') == 0
    assert bump_version.find_version_mismatches(temp_repo) == []


def test_bump_explicit(temp_repo):
    assert _run(temp_repo, '7.3.0') == 0
    with open(temp_repo / 'pyproject.toml', 'rb') as handle:
        assert tomllib.load(handle)['project']['version'] == '7.3.0'


def test_dry_run_writes_nothing(temp_repo, capsys):
    before = _snapshot_tree(temp_repo)
    assert _run(temp_repo, 'patch', '--dry-run') == 0
    assert _snapshot_tree(temp_repo) == before
    out = capsys.readouterr().out
    assert 'Dry run' in out
    assert '-version = "7.0.0"' in out
    assert '+version = "7.0.1"' in out
    assert 'Would run: uv lock' in out


def test_lower_version_refused_and_tree_untouched(temp_repo, capsys):
    before = _snapshot_tree(temp_repo)
    assert _run(temp_repo, '6.0.0') == 1
    assert _snapshot_tree(temp_repo) == before


def test_empty_unreleased_refused(temp_repo, capsys):
    _write(temp_repo, 'CHANGELOG.md',
           CHANGELOG_EMPTY_UNRELEASED.format(version='7.0.0'))
    before = _snapshot_tree(temp_repo)
    assert _run(temp_repo, 'patch') == 1
    assert _snapshot_tree(temp_repo) == before
    assert 'empty' in capsys.readouterr().err


def test_empty_unreleased_allowed_with_force(temp_repo):
    _write(temp_repo, 'CHANGELOG.md',
           CHANGELOG_EMPTY_UNRELEASED.format(version='7.0.0'))
    assert _run(temp_repo, 'patch', '--force') == 0
    assert '## [7.0.1] - ' in (temp_repo / 'CHANGELOG.md').read_text()


def test_no_changelog(temp_repo):
    before_changelog = (temp_repo / 'CHANGELOG.md').read_text()
    before_readme = (temp_repo / 'README.md').read_text()
    assert _run(temp_repo, 'patch', '--no-changelog') == 0
    assert (temp_repo / 'CHANGELOG.md').read_text() == before_changelog
    assert (temp_repo / 'README.md').read_text() == before_readme
    assert "version = \"7.0.1\"" in (temp_repo / 'pyproject.toml').read_text()


def test_missing_anchor_aborts_and_writes_nothing(temp_repo):
    update_py = temp_repo / 'src/compiler/update.py'
    text = update_py.read_text(encoding='utf-8')
    update_py.write_text(
        text.replace("FALLBACK_VERSION = '7.0.0'\n", ''), encoding='utf-8')
    before = _snapshot_tree(temp_repo)
    assert _run(temp_repo, 'patch') == 1
    assert _snapshot_tree(temp_repo) == before


def test_duplicated_anchor_aborts_and_writes_nothing(temp_repo):
    update_py = temp_repo / 'src/compiler/update.py'
    text = update_py.read_text(encoding='utf-8')
    update_py.write_text(text + "FALLBACK_VERSION = '7.0.0'\n",
                         encoding='utf-8')
    before = _snapshot_tree(temp_repo)
    assert _run(temp_repo, 'patch') == 1
    assert _snapshot_tree(temp_repo) == before


def test_rollback_when_a_write_fails(temp_repo):
    # README.md as a directory makes its atomic write fail mid-run;
    # every file written before it must be restored.
    (temp_repo / 'README.md').unlink()
    (temp_repo / 'README.md').mkdir()
    before = _snapshot_tree(temp_repo)
    assert _run(temp_repo, 'patch') == 1
    assert _snapshot_tree(temp_repo) == before


def test_uv_lock_failure_restores_tree(temp_repo):
    before = _snapshot_tree(temp_repo)
    assert _run(temp_repo, 'patch', uv_runner=failing_uv_lock) == 1
    assert _snapshot_tree(temp_repo) == before


def test_uv_missing_is_a_clear_error(temp_repo, monkeypatch, capsys):
    monkeypatch.setattr(bump_version.shutil, 'which', lambda name: None)
    before = _snapshot_tree(temp_repo)
    assert _run(temp_repo, 'patch', uv_runner=None) == 1
    assert _snapshot_tree(temp_repo) == before
    assert 'uv is missing' in capsys.readouterr().err


def test_commit_makes_one_release_commit(temp_repo, monkeypatch):
    import subprocess

    monkeypatch.setenv('GIT_AUTHOR_NAME', 'Test')
    monkeypatch.setenv('GIT_AUTHOR_EMAIL', 'test@example.com')
    monkeypatch.setenv('GIT_COMMITTER_NAME', 'Test')
    monkeypatch.setenv('GIT_COMMITTER_EMAIL', 'test@example.com')
    subprocess.run(['git', 'init', '-q'], cwd=temp_repo, check=True)
    subprocess.run(['git', 'add', '-A'], cwd=temp_repo, check=True)
    subprocess.run(['git', 'commit', '-qm', 'base'],
                   cwd=temp_repo, check=True)
    assert _run(temp_repo, 'patch', '--commit') == 0
    log = subprocess.run(['git', 'log', '-1', '--format=%s'],
                         cwd=temp_repo, capture_output=True, text=True,
                         check=True).stdout.strip()
    assert log == 'chore(release): v7.0.1'
    # Only the script-touched files (plus uv.lock) are in the commit.
    names = subprocess.run(['git', 'show', '--name-only', '--format='],
                           cwd=temp_repo, capture_output=True, text=True,
                           check=True).stdout.split()
    assert 'pyproject.toml' in names
    assert 'CHANGELOG.md' in names
    assert 'uv.lock' in names


def test_date_override(temp_repo):
    assert _run(temp_repo, 'patch', '--date', '2030-05-01') == 0
    assert '## [7.0.1] - 2030-05-01' in (
        temp_repo / 'CHANGELOG.md').read_text()


def test_invalid_date(temp_repo, capsys):
    assert _run(temp_repo, 'patch', '--date', 'May 1st') == 2
    assert _run(temp_repo, 'patch', '--date', '2030-13-99') == 2


def test_mismatches_detect_stale_tree(temp_repo):
    assert bump_version.find_version_mismatches(temp_repo) == []
    update_py = temp_repo / 'src/compiler/update.py'
    update_py.write_text(
        update_py.read_text().replace('7.0.0', '6.0.0'), encoding='utf-8')
    mismatches = bump_version.find_version_mismatches(temp_repo)
    assert any('FALLBACK_VERSION' in label for _path, label, _found in mismatches)
