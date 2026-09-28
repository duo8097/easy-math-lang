"""Static checks for the macOS build workflow + helper script."""

import os
import re

import pytest

WORKFLOW = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".github",
                 "workflows", "build-macos-installer.yml"))
SCRIPT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "scripts", "build_macos.sh"))
SMOKE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "scripts", "smoke_macos.sh"))


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


def test_workflow_bundles_helpers_into_app(workflow_text):
    # Helpers must live inside the .app (Contents/Resources/bin) so the
    # editor works when only the .app is dragged to /Applications.
    assert "Contents/Resources/bin" in workflow_text
    assert "easy-math-editor.app" in workflow_text
    # The old EasyMath/{bin,editor} split duplicated Qt and broke the
    # app-alone layout; it must be gone.
    assert "staging/EasyMath" not in workflow_text


def test_workflow_ships_only_app(workflow_text):
    assert 'cp -R "dist/easy-math-editor.app" staging/' in workflow_text
    assert "staging/EasyMath/editor" not in workflow_text


def test_workflow_has_applications_symlink(workflow_text):
    assert "ln -s /Applications" in workflow_text


def test_workflow_zip_from_staged_content(workflow_text):
    assert "cd staging" in workflow_text
    assert "ditto" in workflow_text


def test_sign_step_fails_loudly(workflow_text):
    assert "continue-on-error" not in workflow_text
    assert "|| true" not in workflow_text


def test_sign_inside_out_before_bundle(workflow_text):
    assert "Contents/Frameworks" in workflow_text
    assert (
        workflow_text.index("Contents/Frameworks")
        < workflow_text.index('codesign --force --sign - "$APP"')
    )


def test_sign_verifies_everything(workflow_text):
    assert "codesign --verify --deep --strict" in workflow_text
    assert "codesign --verify --strict" in workflow_text


def test_final_bundle_sign_avoids_deep(workflow_text):
    hits = [
        line
        for line in workflow_text.splitlines()
        if line.strip().startswith("codesign")
        and "--verify" not in line
        and (".app" in line or "$APP" in line)
    ]
    assert hits, "expected an explicit final .app signing invocation"
    for line in hits:
        assert "--deep" not in line, (
            f"must not use --deep for the final bundle: {line}"
        )


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


def test_smoke_script_exists_and_is_bash():
    assert os.path.isfile(SMOKE), "macOS smoke script missing"
    with open(SMOKE, encoding="utf-8") as h:
        text = h.read()
    assert text.splitlines()[0].startswith("#!") and "bash" in text.splitlines()[0]


def test_smoke_script_covers_compiler_exports_lsp_editor():
    with open(SMOKE, encoding="utf-8") as h:
        text = h.read()
    assert "examples/example.ezmath" in text
    assert "--format" in text
    for token in ("png", "svg", "html"):
        assert token in text
    assert "easy-math-lsp" in text
    assert "QT_QPA_PLATFORM" in text
    # GNU timeout exit code: still running when killed -> success.
    assert "124" in text
    # Signature info must be logged but never fail the build.
    assert "spctl" in text
    assert "xattr" in text


def test_smoke_script_tests_staged_app_not_dist():
    with open(SMOKE, encoding="utf-8") as h:
        text = h.read()
    # Helpers/editor resolve through the staged .app bundle layout.
    assert 'APP="$STAGING/easy-math-editor.app"' in text
    assert "Contents/Resources/bin" in text
    assert "Contents/MacOS/easy-math-editor" in text


def test_workflow_runs_smoke_on_staged_app(workflow_text):
    assert "scripts/smoke_macos.sh" in workflow_text
    # Smoke runs after staging and before DMG creation so a broken
    # bundle never ships.
    assert workflow_text.index("smoke_macos.sh") > workflow_text.index("Stage DMG")
    assert workflow_text.index("smoke_macos.sh") < workflow_text.index("hdiutil")
