"""Static checks for the Linux packages (.deb + .rpm)."""

import os
import re

import pytest

WORKFLOW = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".github",
                 "workflows", "build-installers.yml"))
SCRIPT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "installer", "build_linux.sh"))
BUILDER = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "scripts", "build_binaries.py"))
GUARD = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "scripts",
                 "check_tag_version.py"))
PKGBUILD = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "installer", "PKGBUILD"))
ARCH_SCRIPT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "installer", "build_arch.sh"))
INSTALL_DOC = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "docs", "installation.md"))
PACKAGING_DOC = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "docs", "packaging.md"))
README = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "README.md"))
PYPROJECT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "pyproject.toml"))


@pytest.fixture(scope="module")
def workflow_text():
    with open(WORKFLOW, encoding="utf-8") as h:
        return h.read()


@pytest.fixture(scope="module")
def script_text():
    with open(SCRIPT, encoding="utf-8") as h:
        return h.read()


@pytest.fixture(scope="module")
def builder_text():
    with open(BUILDER, encoding="utf-8") as h:
        return h.read()


def job_section(workflow_text, job_id):
    """Steps of one job in the build workflow."""
    import re
    starts = [
        m.start() for m in re.finditer(r"^  [\w-]+:", workflow_text, re.M)
    ]
    for i, s in enumerate(starts):
        if workflow_text[s:].split(":", 1)[0].strip() == job_id:
            end = starts[i + 1] if i + 1 < len(starts) else len(workflow_text)
            return workflow_text[s:end]
    raise AssertionError(f"job {job_id} missing from workflow")


def test_files_exist():
    assert os.path.isfile(WORKFLOW), "Linux workflow missing"
    assert os.path.isfile(SCRIPT), "Linux build script missing"
    assert os.path.isfile(BUILDER), "shared binary builder missing"


def test_script_is_executable_bash():
    with open(SCRIPT, encoding="utf-8") as h:
        first = h.readline()
    assert first.startswith("#!") and "bash" in first
    assert os.access(SCRIPT, os.X_OK), "build_linux.sh is not executable"


def test_script_fails_loudly():
    with open(SCRIPT, encoding="utf-8") as h:
        text = h.read()
    assert "set -euo pipefail" in text


def test_script_reads_version_from_pyproject(script_text):
    assert "pyproject.toml" in script_text
    # Version must be dynamic, never hard-coded into the script.
    assert not re.search(r"\b3\.\d+\.\d+\b", script_text)
    assert not re.search(r"\b4\.\d+\.\d+\b", script_text)


def test_script_builds_all_three_binaries(script_text, builder_text):
    # The script drives the shared builder, which owns the PyInstaller
    # flags for the three binaries.
    assert "scripts/build_binaries.py" in script_text
    for name in ("easy-math-lang", "easy-math-lsp", "easy-math-editor"):
        assert name in builder_text
    assert "entry" in builder_text
    assert "PyInstaller" in builder_text
    assert "ezmath" in builder_text


def test_script_collects_plot_and_pdf_backends(builder_text):
    # *plot(...) needs matplotlib; PDF export needs typst; geometry needs numpy.
    for dep in ("typst", "numpy", "matplotlib"):
        assert dep in builder_text
    assert '"--collect-all"' in builder_text


def test_script_stages_fhs_tree(script_text):
    for path in ("usr/bin/easy-math-lang",
                 "usr/bin/easy-math-lsp",
                 "usr/bin/easy-math-editor",
                 "usr/lib/easy-math-lang",
                 "usr/share/applications/easy-math-editor.desktop",
                 "usr/share/doc/easymath"):
        assert path in script_text


def test_script_builds_deb_with_control(script_text):
    assert "dpkg-deb" in script_text
    for field in ("Package: easymath", "Version:", "Architecture: amd64",
                  "Maintainer:", "Description:"):
        assert field in script_text


def test_script_builds_rpm_with_spec(script_text):
    assert "rpmbuild" in script_text
    assert "BuildArch:" in script_text
    assert "x86_64" in script_text
    # rpmbuild is optional locally (CI installs it); the .deb must still build.
    assert "skipping .rpm" in script_text


def test_script_requires_dpkg_deb(script_text):
    assert "command -v dpkg-deb" in script_text
    assert "exit 1" in script_text


def test_stable_distro_names_agree(script_text, workflow_text):
    """Distro-scoped package names must agree across script, CI, and docs."""
    texts = [script_text, workflow_text]
    for path in (INSTALL_DOC, PACKAGING_DOC, README):
        with open(path, encoding="utf-8") as h:
            texts.append(h.read())
    for name in ("EasyMathLang-Debian-amd64.deb",
                 "EasyMathLang-Fedora-amd64.rpm"):
        for text in texts:
            assert name in text, f"{name} missing somewhere"
    assert "EasyMathLang-Linux-amd64" not in script_text
    assert "EasyMathLang-Linux-amd64" not in workflow_text


def test_workflow_runs_on_every_commit(workflow_text):
    # Unfiltered push: every commit builds. Tag pushes additionally
    # publish the stable GitHub Release (see Create GitHub Release).
    assert "workflow_dispatch" in workflow_text
    assert "tags:" not in workflow_text
    assert "softprops/action-gh-release" in workflow_text
    assert "startsWith(github.ref, 'refs/tags/')" in workflow_text


def test_workflow_runs_nightly_schedule(workflow_text):
    assert "schedule" in workflow_text
    assert "cron" in workflow_text


def test_workflow_pins_ubuntu_and_arch(workflow_text):
    assert "ubuntu-24.04" in workflow_text
    assert "amd64" in workflow_text
    # Pinned image only (the "do not use ubuntu-latest" comment names it
    # without using it).
    assert not re.search(r"runner:\s*ubuntu-latest", workflow_text)


def test_workflow_runs_tests_before_build(workflow_text):
    assert "pytest" in workflow_text
    assert "build_linux.sh" in workflow_text
    assert workflow_text.index("pytest") < workflow_text.index(
        "build_linux.sh")


def test_workflow_guards_tag_matches_pyproject(workflow_text):
    assert "Guard tag matches pyproject version" in workflow_text
    assert "check_tag_version.py" in workflow_text
    with open(GUARD, encoding="utf-8") as h:
        guard = h.read()
    assert 'removeprefix("v")' in guard
    assert "pyproject.toml" in guard


def test_workflow_smokes_installed_deb(workflow_text):
    assert "dpkg -i" in workflow_text
    assert "easy-math-lang --version" in workflow_text
    assert "example.ezmath" in workflow_text


def test_workflow_inspects_rpm(workflow_text):
    assert "rpm -qip" in workflow_text
    assert "rpm -qlp" in workflow_text


def test_workflow_uploads_and_releases(workflow_text):
    assert "upload-artifact" in workflow_text
    assert "if-no-files-found: error" in workflow_text
    assert "retention-days: 14" in workflow_text
    assert "fail-fast: false" in workflow_text
    assert "startsWith(github.ref, 'refs/tags/')" in workflow_text
    assert "contains(github.ref_name, '-')" in workflow_text
    assert "contents: write" in workflow_text


def test_pkgbuild_uses_shared_builder():
    with open(PKGBUILD, encoding="utf-8") as h:
        text = h.read()
    # The Arch recipe drives the same selective Qt builder as CI.
    assert "scripts/build_binaries.py" in text
    assert "--full-pyside6" not in text
    # No PyInstaller invocation of its own.
    assert "pyinstaller entry" not in text.lower()
    assert "-m pyinstaller" not in text.lower()


def test_pkgbuild_version_falls_back_to_pyproject():
    with open(PKGBUILD, encoding="utf-8") as h:
        text = h.read()
    # A VCS checkout describes the commit; the CI source tarball has no
    # git metadata and falls back to the declared project version.
    assert "git describe" in text
    assert "pyproject.toml" in text


def test_arch_script_packs_the_checkout_and_runs_makepkg():
    with open(ARCH_SCRIPT, encoding="utf-8") as h:
        text = h.read()
    assert "set -euo pipefail" in text
    assert "makepkg" in text
    assert "PKGDEST" in text
    assert "installer/PKGBUILD" in text
    # The working tree is packed, so the package never depends on the
    # upstream repository or on git metadata.
    assert "easy-math-lang.tar.gz" in text
    assert "sha256sum" in text


def test_workflow_builds_arch_package(workflow_text):
    arch = job_section(workflow_text, "build-arch")
    # makepkg only runs on Arch and refuses to run as root.
    assert "archlinux" in arch
    assert "useradd" in arch
    assert "installer/build_arch.sh" in arch
    assert "upload-artifact" in arch
    assert "EasyMathLang-Arch-x86_64" in arch
    assert "if-no-files-found: error" in arch
    assert "retention-days: 14" in arch
    # The release waits for the Arch package as well.
    release = job_section(workflow_text, "release")
    assert "build-arch" in release


def test_installation_docs_cover_deb_and_rpm():
    with open(INSTALL_DOC, encoding="utf-8") as h:
        text = h.read()
    assert ".deb" in text
    assert ".rpm" in text
    assert "dpkg -i" in text


def test_packaging_docs_cover_linux():
    with open(PACKAGING_DOC, encoding="utf-8") as h:
        text = h.read()
    assert ".deb" in text
    assert ".rpm" in text
    assert "build_linux.sh" in text


def test_readme_mentions_linux_packages():
    with open(README, encoding="utf-8") as h:
        text = h.read()
    assert ".deb" in text
    assert ".rpm" in text


def test_no_hardcoded_old_version_in_packaging():
    for path in (SCRIPT, WORKFLOW, PKGBUILD):
        with open(path, encoding="utf-8") as h:
            text = h.read()
        assert "3.1.0" not in text
