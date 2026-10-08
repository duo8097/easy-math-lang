"""Static checks for the Linux packages (.deb + .rpm)."""

import os
import re

import pytest

WORKFLOW = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".github",
                 "workflows", "build-linux-installers.yml"))
SCRIPT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "installer", "build_linux.sh"))
PKGBUILD = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "installer", "PKGBUILD"))
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


def test_files_exist():
    assert os.path.isfile(WORKFLOW), "Linux workflow missing"
    assert os.path.isfile(SCRIPT), "Linux build script missing"


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


def test_script_builds_all_three_binaries(script_text):
    for name in ("easy-math-lang", "easy-math-lsp", "easy-math-editor"):
        assert name in script_text
    assert "entry_compiler.py" in script_text
    assert "pyinstaller" in script_text
    assert "ezmath" in script_text


def test_script_collects_plot_and_pdf_backends(script_text):
    # *plot(...) needs matplotlib; PDF export needs typst; geometry needs numpy.
    for dep in ("--collect-all typst", "--collect-all numpy",
                "--collect-all matplotlib"):
        assert dep in script_text


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


def test_script_emits_stable_release_names(script_text):
    assert "EasyMathLang-Linux-amd64.deb" in script_text
    assert "EasyMathLang-Linux-amd64.rpm" in script_text


def test_workflow_triggers_on_tag_and_dispatch(workflow_text):
    assert "v*" in workflow_text
    assert "workflow_dispatch" in workflow_text
    assert "softprops/action-gh-release" in workflow_text


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
    assert "${TAG#v}" in workflow_text


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


def test_pkgbuild_collects_matplotlib():
    with open(PKGBUILD, encoding="utf-8") as h:
        text = h.read()
    assert text.count("--collect-all matplotlib") >= 2, (
        "PKGBUILD compiler+editor builds must collect matplotlib for *plot")


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
