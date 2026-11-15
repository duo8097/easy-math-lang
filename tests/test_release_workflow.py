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

ALL_ASSET_JOBS = ('build-macos', 'build-linux-binary', 'build-deb',
                  'build-rpm', 'build-windows', 'build-arch')


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


def _job_section(text, job_id):
    starts = [m.start() for m in re.finditer(r'(?m)^  [\w-]+:', text)]
    for i, s in enumerate(starts):
        if text[s:].split(':', 1)[0].strip() == job_id:
            end = starts[i + 1] if i + 1 < len(starts) else len(text)
            return text[s:end]
    raise AssertionError(f'job {job_id} missing from workflow')


def test_three_linux_jobs_exist_and_chain_via_needs():
    binary = _job_section(WORKFLOW_TEXT, 'build-linux-binary')
    assert 'bash installer/build_linux.sh binary' in binary
    assert 'upload-artifact' in binary
    for job_id in ('build-deb', 'build-rpm'):
        section = _job_section(WORKFLOW_TEXT, job_id)
        assert re.search(r'(?m)^\s+needs: build-linux-binary\s*$', section), \
            f'{job_id} must need build-linux-binary'
        want = ('bash installer/build_linux.sh deb' if job_id == 'build-deb'
                else 'bash installer/build_linux.sh rpm')
        assert want in section, f'{job_id} must run {want}'


def test_release_job_needs_every_asset_producing_job():
    release = _job_section(WORKFLOW_TEXT, 'release')
    needs = re.search(r'(?m)^\s+needs: \[([^\]]+)\]\s*$', release)
    assert needs, 'release job must have a needs list'
    wanted = {job.strip() for job in needs.group(1).split(',')}
    assert set(ALL_ASSET_JOBS) <= wanted, (
        f'release must need every asset-producing job: {wanted}')


def test_intermediate_bundle_artifact_does_not_match_release_pattern():
    """The bundle hand-off artifact must NOT match the release job's
    EasyMathLang* download pattern, or it would be published as an
    asset and break SHA256SUMS verification."""
    binary = _job_section(WORKFLOW_TEXT, 'build-linux-binary')
    match = re.search(r'(?ms)name: Upload binary bundle artifact\n(.*?)(?=^\s+- name:|\Z)',
                      binary)
    assert match, 'binary job must upload the bundle artifact'
    body = match.group(1)
    name = re.search(r'(?m)^\s+name:\s*(\S+)\s*$', body).group(1)
    assert name == 'linux-bundle-amd64'
    assert not re.match(r'^EasyMathLang', name)
    # The release job's own download pattern stays EasyMathLang*.
    release = _job_section(WORKFLOW_TEXT, 'release')
    assert re.search(r'(?m)^\s+pattern: EasyMathLang\*\s*$', release)


def test_rpm_job_pins_a_concrete_container_tag():
    rpm = _job_section(WORKFLOW_TEXT, 'build-rpm')
    match = re.search(r'(?m)^\s+image:\s*fedora:(\d+(?:\.\d+)?)\s*$', rpm)
    assert match, 'build-rpm must pin a concrete Fedora container tag'
    assert match.group(1) != 'latest'


def test_sha256sums_covers_exactly_the_five_assets_plus_sums():
    """The sums step counts files; the bundle tarball must not leak in."""
    release = _job_section(WORKFLOW_TEXT, 'release')
    sums = re.search(r'(?ms)name: Generate SHA256SUMS\.txt\n(.*?)(?=^\s+- name:)',
                     release).group(1)
    assert 'find . -maxdepth 1 -type f ! -name SHA256SUMS.txt' in sums
    # The bundle artifact (linux-bundle-amd64) must not match the
    # release download pattern, so exactly the 5 assets land in it.
    assert 'linux-bundle' not in release
    for asset in EXPECTED_ASSETS:
        assert asset in release
    assert 'easy-math-lang-git-' in release
