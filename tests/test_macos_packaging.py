"""Static checks for the macOS build workflow + helper script."""

import os
import re

import pytest

WORKFLOW = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".github",
                 "workflows", "build-macos-installer.yml"))
SCRIPT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "scripts", "build_macos.sh"))


@pytest.fixture(scope="module")
def workflow_text():
    with open(WORKFLOW, encoding="utf-8") as h:
        return h.read()


@pytest.fixture(scope="module")
def script_text():
    with open(SCRIPT, encoding="utf-8") as h:
        return h.read()


def test_workflow_exists():
    assert os.path.isfile(WORKFLOW), "macOS workflow missing"
    assert os.path.isfile(SCRIPT), "macOS build script missing"


def test_workflow_triggers_on_tag_and_dispatch(workflow_text):
    assert "v*" in workflow_text
    assert "workflow_dispatch" in workflow_text


def test_workflow_builds_both_arches(workflow_text):
    assert "macos-14" in workflow_text
    # The previous Intel image was retired by GitHub on 2025-12-04;
    # Intel builds must target macos-15-intel (the last Intel image).
    assert "macos-15-intel" in workflow_text
    assert not re.search(r"runner:\s*macos-13\b", workflow_text)
    assert "arm64" in workflow_text
    assert "x64" in workflow_text or "x86_64" in workflow_text or "intel" in workflow_text.lower()


def test_workflow_runs_tests_before_build(workflow_text):
    assert "pytest" in workflow_text
    assert workflow_text.index("pytest") < workflow_text.index("pyinstaller")


def test_workflow_builds_all_three_binaries(workflow_text):
    for name in ("easy-math-lang", "easy-math-lsp", "easy-math-editor"):
        assert name in workflow_text


def test_workflow_provides_ezmath_alias(workflow_text):
    assert "ezmath" in workflow_text


def test_workflow_creates_dmg_and_zip(workflow_text):
    assert "hdiutil" in workflow_text
    assert ".dmg" in workflow_text
    assert ".zip" in workflow_text or "ditto" in workflow_text


def test_workflow_uploads_and_releases(workflow_text):
    assert "upload-artifact" in workflow_text
    assert "softprops/action-gh-release" in workflow_text


def test_script_mirrors_workflow(script_text, workflow_text):
    for token in ("easy-math-lang", "easy-math-lsp", "easy-math-editor",
                  "entry_compiler.py", "pyinstaller"):
        assert token in script_text, f"script missing {token}"
    assert "ezmath" in script_text


def test_script_is_executable_bash():
    with open(SCRIPT, encoding="utf-8") as h:
        first = h.readline()
    assert first.startswith("#!") and "bash" in first
