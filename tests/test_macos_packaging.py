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
INSTALL_DOC = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "docs", "installation.md"))
README = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "README.md"))


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
    assert "softprops/action-gh-release" in workflow_text


def test_workflow_builds_arm64_only(workflow_text):
    assert "macos-15" in workflow_text
    assert "arm64" in workflow_text
    assert "arch: arm64" in workflow_text
    # No Intel runner, retired images, floating runner, or x64 artifact
    # (checked as runs-on values: the pinning comment names macos-14 and
    # macos-latest without using them).
    assert "macos-15-intel" not in workflow_text
    assert not re.search(r"runner:\s*macos-14\b", workflow_text)
    assert not re.search(r"runner:\s*macos-13\b", workflow_text)
    assert not re.search(r"runner:\s*macos-latest", workflow_text)
    assert "EasyMathLang-macOS-x64" not in workflow_text
    assert not re.search(r"arch:\s*x64", workflow_text)


def test_docs_are_arm64_only():
    for path in (INSTALL_DOC, README):
        with open(path, encoding="utf-8") as h:
            text = h.read()
        assert "EasyMathLang-macOS-x64" not in text
    with open(os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "docs",
                         "packaging.md")), encoding="utf-8") as h:
        packaging = h.read()
    assert "EasyMathLang-macOS-x64" not in packaging
    assert "macos-15-intel" not in packaging


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


def test_workflow_prunes_nested_dot_apps_before_sign(workflow_text):
    assert "__dot__app" in workflow_text
    assert "Remove nested Qt tool apps" in workflow_text
    # Cleanup prints what it removes before deleting.
    assert "-name '*__dot__app' -print" in workflow_text
    # Cleanup runs after helpers are bundled, before signing.
    assert workflow_text.index("Bundle helpers into the .app") < workflow_text.index(
        "__dot__app"
    )
    assert workflow_text.index("__dot__app") < workflow_text.index(
        "Sign bundle inside-out"
    )
    # Bundle size is logged before/after pruning and after the editor build.
    assert "du -sh dist/easy-math-editor.app" in workflow_text


def test_editor_build_drops_collect_all_pyside6(workflow_text, script_text):
    assert "--collect-all PySide6" not in workflow_text
    assert "--collect-all PySide6" not in script_text
    for hidden in ("PySide6.QtPdf", "PySide6.QtPdfWidgets"):
        assert hidden in workflow_text, f"workflow missing {hidden}"
        assert hidden in script_text, f"build script missing {hidden}"
    # Typst/numpy collection must stay.
    assert "--collect-all typst" in workflow_text
    assert "--collect-all numpy" in workflow_text


def test_smoke_checks_qt_platform_plugin():
    with open(SMOKE, encoding="utf-8") as h:
        text = h.read()
    assert "plugins/platforms" in text
    assert "libqcocoa.dylib" in text


def test_sign_step_fails_loudly(workflow_text):
    assert "continue-on-error" not in workflow_text
    assert "|| true" not in workflow_text


def test_sign_uses_macho_check_only(workflow_text):
    # Only real Mach-O files are signed; never plain directories.
    assert 'file -b "$f"' in workflow_text
    assert "Mach-O" in workflow_text
    assert "-print0" in workflow_text
    assert "read -r -d ''" in workflow_text
    # Old approach signed directories and any +x file; it must be gone.
    assert "-perm +111" not in workflow_text
    assert "-maxdepth 1 -mindepth 1" not in workflow_text


def test_sign_macho_loop_before_bundle(workflow_text):
    assert workflow_text.index("Mach-O") < workflow_text.index(
        'codesign --force --sign - "$APP"'
    )
    # Bundled helpers are asserted executable before the loop covers them.
    assert "Contents/Resources/bin" in workflow_text


def test_sign_failure_prints_diagnostics(workflow_text):
    assert 'codesign -dvvv "$APP"' in workflow_text
    assert 'find "$APP" -type l' in workflow_text


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
    assert "Create GitHub Release" in workflow_text
    assert "if-no-files-found: error" in workflow_text
    assert "retention-days: 14" in workflow_text
    assert "EasyMathLang-macOS-${{ matrix.arch }}" in workflow_text
    assert "fail-fast: false" in workflow_text
    # Release ships the same DMG+ZIP and only runs on tag builds.
    assert "startsWith(github.ref, 'refs/tags/')" in workflow_text
    assert workflow_text.index("upload-artifact") < workflow_text.index(
        "softprops/action-gh-release"
    )


def test_workflow_permissions_write(workflow_text):
    assert "contents: write" in workflow_text


def test_workflow_uploads_after_smoke(workflow_text):
    assert "scripts/smoke_macos.sh" in workflow_text
    assert "upload-artifact" in workflow_text
    assert workflow_text.index("scripts/smoke_macos.sh") < workflow_text.index(
        "upload-artifact"
    )


def test_script_mirrors_workflow(script_text, workflow_text):
    for token in ("easy-math-lang", "easy-math-lsp", "easy-math-editor",
                  "entry_compiler.py", "pyinstaller"):
        assert token in script_text, f"script missing {token}"
    assert "ezmath" in script_text


def test_build_script_requires_arm64(script_text):
    assert 'uname -m' in script_text
    assert "This build targets Apple Silicon (arm64) only" in script_text


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


def test_release_marks_hyphen_tags_prerelease(workflow_text):
    assert "prerelease:" in workflow_text
    assert "contains(github.ref_name, '-')" in workflow_text


def test_release_guards_tag_matches_pyproject(workflow_text):
    assert "Guard tag matches pyproject version" in workflow_text
    assert "pyproject.toml" in workflow_text
    # Leading "v" is stripped before comparing with the project version.
    assert "${TAG#v}" in workflow_text
    assert "exit 1" in workflow_text


def test_installation_docs_cover_adhoc_first_launch():
    with open(INSTALL_DOC, encoding="utf-8") as h:
        text = h.read()
    assert "not notarized" in text
    assert "xattr -dr com.apple.quarantine" in text
    assert "Right-click" in text or "right-click" in text


def test_readme_marks_macos_experimental():
    with open(README, encoding="utf-8") as h:
        text = h.read()
    assert "experimental" in text.lower()
