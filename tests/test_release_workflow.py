"""Static regression tests for the release job of the installer workflow.

The updater verifies downloaded assets against ``SHA256SUMS.txt`` from
the same release; a release without it breaks self-update. These tests
pin the workflow shape: the sums file is generated over exactly the
downloaded artifacts, covers every expected asset, and is uploaded.
"""

import os
import re

WORKFLOW = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '.github',
                 'workflows', 'build-installers.yml'))

with open(WORKFLOW, encoding='utf-8') as handle:
    WORKFLOW_TEXT = handle.read()

EXPECTED_ASSETS = [
    'EasyMathLang-Windows-x64-Setup.exe',
    'EasyMathLang-macOS-arm64.dmg',
    'EasyMathLang-Debian-amd64.deb',
    'EasyMathLang-Fedora-amd64.rpm',
]


def test_release_job_generates_sha256sums_txt():
    assert re.search(r'(?m)^\s+- name: Generate SHA256SUMS\.txt\s*$',
                     WORKFLOW_TEXT), 'release job must generate SHA256SUMS.txt'
    match = re.search(r'(?ms)name: Generate SHA256SUMS\.txt\n(.*?)(?=^\s+- name:)',
                      WORKFLOW_TEXT)
    assert match, 'Generate step has no body'
    body = match.group(1)
    assert 'sha256sum * > SHA256SUMS.txt' in body


def test_release_assets_verified_before_upload():
    match = re.search(
        r'(?ms)name: Verify all expected release assets are present\n(.*?)(?=^\s+- name:)',
        WORKFLOW_TEXT)
    assert match, 'release job must verify the expected assets exist'
    body = match.group(1)
    for asset in EXPECTED_ASSETS:
        assert asset in body
    assert 'easy-math-lang-git-' in body  # Arch pattern
    assert 'pkg.tar.zst' in body
    assert 'SHA256SUMS.txt' in body


def test_release_uploads_the_sums_file():
    # softprops/action-gh-release uploads every file in release-files/,
    # which must include SHA256SUMS.txt (generated there, not git-tracked).
    assert re.search(r'(?m)^\s+files: release-files/\*\s*$', WORKFLOW_TEXT)


def test_expected_assets_match_installer_outputs():
    """The documented asset names must be produced by the build jobs."""
    linux = (open(os.path.join(os.path.dirname(__file__), '..',
                               'installer', 'build_linux.sh'),
                  encoding='utf-8').read())
    assert 'EasyMathLang-Debian-amd64.deb' in linux
    assert 'EasyMathLang-Fedora-amd64.rpm' in linux
    arch = (open(os.path.join(os.path.dirname(__file__), '..',
                              'installer', 'build_arch.sh'),
                 encoding='utf-8').read())
    assert 'easy-math-lang-git-' in arch
    iss = (open(os.path.join(os.path.dirname(__file__), '..',
                             'installer', 'setup.iss'),
                encoding='utf-8').read())
    assert 'OutputBaseFilename=EasyMathLang-Windows-x64-Setup' in iss
