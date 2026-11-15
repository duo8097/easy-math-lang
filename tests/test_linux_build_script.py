"""Split-stage tests for ``installer/build_linux.sh``.

The real package builds need dpkg-deb / rpmbuild; those are exercised
here against a tiny fake ``dist/easy-math-lang/`` bundle and the tests
skip cleanly when the tools are absent. Everything else (subcommand
dispatch, the never-PyInstaller rule for deb/rpm, the shared staging)
is checked statically.
"""

import os
import shutil
import subprocess
import sys

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SCRIPT = os.path.join(REPO_ROOT, 'installer', 'build_linux.sh')

FAKE_BUNDLE_FILES = ('easy-math-lang', 'easy-math-lsp', 'easy-math-editor')


def _read():
    with open(SCRIPT, encoding='utf-8') as handle:
        return handle.read()


# ----------------------------------------------------------------------
# Static checks
# ----------------------------------------------------------------------

def test_subcommands_dispatch():
    import re

    text = _read()
    for sub in ('binary', 'deb', 'rpm', 'all'):
        assert re.search(rf'(?m)^  {re.escape(sub)}\)\s*$', text), sub
    assert 'unknown subcommand' in text


def test_binary_stage_is_the_only_pyinstaller_user():
    """`deb` and `rpm` must never invoke PyInstaller."""
    text = _read()

    def _body(name):
        start = text.index(f'{name}() {{')
        end = text.index('\n}\n', start)
        return text[start:end]

    assert 'build_binaries.py' in _body('cmd_binary')
    for name in ('cmd_deb', 'cmd_rpm'):
        assert 'build_binaries.py' not in _body(name), name
        assert 'pyinstaller' not in _body(name).lower(), name


def test_deb_and_rpm_fail_fast_without_bundle():
    text = _read()
    assert 'require_bundle' in text
    for token in ('dist/easy-math-lang/', '_internal',
                  "run 'bash installer/build_linux.sh binary' first"):
        assert token in text


def test_shared_staging_is_used_by_both_packages():
    """Both packages must stage through the ONE shared function."""
    text = _read()
    assert text.count('stage_fhs') >= 3  # def + 2 call sites
    deb = text.index('cmd_deb() {')
    rpm = text.index('cmd_rpm() {')
    staging_calls = [i for i in range(len(text))
                     if text.startswith('  stage_fhs ', i)
                     or text.startswith('\tstage_fhs ', i)]
    assert any(deb < i < rpm for i in staging_calls), 'deb must call stage_fhs'
    assert any(i > rpm for i in staging_calls), 'rpm must call stage_fhs'
    # Exactly one copy of the onedir bundle staging exists in the script.
    assert text.count('cp -a dist/easy-math-lang/.') == 1


def test_tool_requirements_documented_in_header():
    text = _read()
    header = text.split('\n\n', 1)[0]
    for token in ('binary:', 'deb:', 'rpm:', 'all:',
                  'dpkg-deb', 'rpmbuild', 'uv'):
        assert token in header, token


def test_deb_and_rpm_take_no_arguments():
    text = _read()
    assert "[ $# -eq 0 ]" in text  # extra args rejected for deb/rpm


def test_all_keeps_rpm_optional_but_rpm_is_hard_required():
    text = _read()
    all_body = text[text.index('cmd_all() {'):text.index('\n}\n',
                                                        text.index('cmd_all() {'))]
    assert 'rpmbuild not found' in all_body
    assert 'skipping .rpm' in all_body
    rpm_body = text[text.index('cmd_rpm() {'):text.index('\n}\n',
                                                         text.index('cmd_rpm() {'))]
    assert 'rpmbuild not found' in rpm_body
    assert 'exit 1' in rpm_body


def test_stable_asset_names_unchanged():
    text = _read()
    assert 'EasyMathLang-Debian-amd64.deb' in text
    assert 'EasyMathLang-Fedora-amd64.rpm' in text
    assert 'EasyMathLang-Linux-amd64' not in text
    assert 'Package: easymath' in text


# ----------------------------------------------------------------------
# Functional: tiny fake bundle -> real package (when tools exist)
# ----------------------------------------------------------------------

@pytest.fixture
def fake_repo(tmp_path):
    """Minimal repo copy with a tiny fake dist/easy-math-lang/ bundle."""
    repo = tmp_path / 'repo'
    (repo / 'installer').mkdir(parents=True)
    (repo / 'icons').mkdir()
    (repo / 'dist' / 'easy-math-lang' / '_internal').mkdir(parents=True)
    (repo / 'dist' / 'easy-math-lang' / '_internal' / 'marker.txt').write_text(
        'fake internal file', encoding='utf-8')
    for name in FAKE_BUNDLE_FILES:
        exe = repo / 'dist' / 'easy-math-lang' / name
        exe.write_text(f'#!/bin/sh\necho fake-{name}\n', encoding='utf-8')
        exe.chmod(0o755)
    for src in ('build_linux.sh',):
        shutil.copy(SCRIPT, repo / 'installer' / src)
    os.chmod(repo / 'installer' / 'build_linux.sh', 0o755)
    shutil.copy(os.path.join(REPO_ROOT, 'pyproject.toml'), repo)
    shutil.copy(os.path.join(REPO_ROOT, 'README.md'), repo)
    shutil.copy(os.path.join(REPO_ROOT, 'LICENSE'), repo)
    shutil.copy(os.path.join(REPO_ROOT, 'THIRD_PARTY_LICENSES'), repo)
    shutil.copy(os.path.join(REPO_ROOT, 'installer',
                             'easy-math-editor.desktop'), repo / 'installer')
    for name in ('ezmath-16.png', 'ezmath-32.png', 'ezmath-48.png',
                 'ezmath-64.png', 'ezmath-128.png', 'ezmath-256.png'):
        shutil.copy(os.path.join(REPO_ROOT, 'icons', name), repo / 'icons')
    return repo


def _run(repo, *argv):
    return subprocess.run(['bash', 'installer/build_linux.sh', *argv],
                          cwd=repo, capture_output=True, text=True)


def _tree_files(root):
    """All regular files and symlinks below *root* (relative posix paths)."""
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        for name in filenames:
            files.append(os.path.relpath(os.path.join(dirpath, name), root))
    return sorted(set(files))


@pytest.mark.skipif(shutil.which('dpkg-deb') is None,
                    reason='dpkg-deb not installed')
def test_deb_subcommand_packages_the_staged_tree(fake_repo):
    result = _run(fake_repo, 'deb')
    assert result.returncode == 0, result.stderr
    deb = fake_repo / 'dist' / 'EasyMathLang-Debian-amd64.deb'
    assert deb.is_file()
    # The package file list must match the staged FHS tree exactly
    # (excluding the DEBIAN/ control dir, which dpkg-deb consumes).
    stage = fake_repo / 'dist' / 'linux-stage'
    [stage_dir] = [d for d in stage.iterdir() if d.is_dir()]
    staged = [
        p for p in _tree_files(stage_dir)
        if not p.startswith('DEBIAN/')]
    listed = subprocess.run(
        ['dpkg-deb', '--contents', str(deb)],
        capture_output=True, text=True, check=True).stdout
    packaged = []
    dir_entries = []
    for line in listed.splitlines():
        # dpkg-deb --contents lines: <perms> <owner>/<group> <size> <date> <time> <path>
        # symlinks are printed with a trailing " -> <target>".
        if ' -> ' in line:
            path = line.split(' -> ', 1)[0].split()[-1]
        else:
            parts = line.split()
            if len(parts) < 6:
                continue
            path = parts[-1]
        parts = line.split()
        if parts and parts[0].startswith('d'):
            dir_entries.append(path)
        else:
            packaged.append(path.lstrip('./'))
    assert sorted(packaged) == staged
    assert any('usr/lib/easy-math-lang' in d for d in dir_entries)
    for name in FAKE_BUNDLE_FILES:
        assert f'usr/lib/easy-math-lang/{name}' in listed
    assert 'usr/bin/ezmath -> easy-math-lang' in listed


@pytest.mark.skipif(shutil.which('dpkg-deb') is None,
                    reason='dpkg-deb not installed')
def test_deb_fails_fast_without_bundle(fake_repo):
    shutil.rmtree(fake_repo / 'dist' / 'easy-math-lang')
    result = _run(fake_repo, 'deb')
    assert result.returncode == 1
    assert 'build_linux.sh binary' in result.stderr


@pytest.mark.skipif(shutil.which('rpmbuild') is None,
                    reason='rpmbuild not installed')
def test_rpm_subcommand_packages_the_staged_tree(fake_repo):
    result = _run(fake_repo, 'rpm')
    assert result.returncode == 0, result.stderr
    rpm = fake_repo / 'dist' / 'EasyMathLang-Fedora-amd64.rpm'
    assert rpm.is_file()
    stage = fake_repo / 'dist' / 'linux-stage'
    [stage_dir] = [d for d in stage.iterdir() if d.is_dir()]
    staged = [
        p for p in _tree_files(stage_dir)
        if not p.startswith('DEBIAN/')]
    listed = subprocess.run(
        ['rpm', '-qlp', str(rpm)],
        capture_output=True, text=True, check=True).stdout
    files = sorted(l for l in listed.splitlines()
                   if l and not l.endswith('/'))
    assert files == sorted(f'/{p}' for p in staged)



