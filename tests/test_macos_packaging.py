"""Static checks for the macOS build workflow + helper scripts."""

import os
import re

import pytest

WORKFLOW = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".github",
                 "workflows", "build-installers.yml"))
SCRIPT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "scripts", "build_macos.sh"))
BUILDER = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "scripts", "build_binaries.py"))
PACKAGE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "scripts", "package_macos.sh"))
GUARD = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "scripts",
                 "check_tag_version.py"))
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


@pytest.fixture(scope="module")
def builder_text():
    with open(BUILDER, encoding="utf-8") as h:
        return h.read()


@pytest.fixture(scope="module")
def package_text():
    with open(PACKAGE, encoding="utf-8") as h:
        return h.read()


@pytest.fixture(scope="module")
def guard_text():
    with open(GUARD, encoding="utf-8") as h:
        return h.read()


def job_section(workflow_text, job_id):
    """Steps of one job in the unified build workflow."""
    starts = [
        m.start() for m in re.finditer(r"^  [\w-]+:", workflow_text, re.M)
    ]
    for i, s in enumerate(starts):
        if workflow_text[s:].split(":", 1)[0].strip() == job_id:
            end = starts[i + 1] if i + 1 < len(starts) else len(workflow_text)
            return workflow_text[s:end]
    raise AssertionError(f"job {job_id} missing from workflow")


def test_workflow_has_all_platform_jobs(workflow_text):
    for job_id in ("build-macos", "build-linux", "build-windows"):
        section = job_section(workflow_text, job_id)
        assert "upload-artifact" in section, f"{job_id} uploads no artifacts"
    release = job_section(workflow_text, "release")
    assert "softprops/action-gh-release" in release


def test_workflow_exists():
    assert os.path.isfile(WORKFLOW), "macOS workflow missing"
    assert os.path.isfile(SCRIPT), "macOS build script missing"
    assert os.path.isfile(BUILDER), "shared binary builder missing"
    assert os.path.isfile(PACKAGE), "macOS packaging script missing"


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
    assert workflow_text.index("pytest") < workflow_text.index(
        "build_binaries.py")


def test_workflow_builds_all_three_binaries(workflow_text, builder_text):
    # The binary names live in the shared builder the workflow calls.
    assert "build_binaries.py" in workflow_text
    for name in ("easy-math-lang", "easy-math-lsp", "easy-math-editor"):
        assert name in builder_text


def test_workflow_provides_ezmath_alias(workflow_text, builder_text):
    assert "ezmath" in builder_text
    assert "build_binaries.py" in workflow_text


def test_workflow_creates_dmg_only(workflow_text):
    macos = job_section(workflow_text, "build-macos")
    assert "hdiutil" in macos
    assert ".dmg" in macos
    assert ".zip" not in macos
    assert "ditto" not in macos


def test_packaging_bundles_helpers_into_app(package_text):
    # Helpers must live inside the .app (Contents/Resources/bin) so the
    # editor works when only the .app is dragged to /Applications.
    assert "Contents/Resources/bin" in package_text
    assert "easy-math-editor.app" in package_text
    # The old EasyMath/{bin,editor} split duplicated Qt and broke the
    # app-alone layout; it must be gone.
    assert "staging/EasyMath" not in package_text


def test_packaging_ships_only_app(package_text):
    assert 'cp -R "$APP" "$STAGE/"' in package_text
    assert "staging/EasyMath/editor" not in package_text


def test_packaging_has_applications_symlink(package_text):
    assert "ln -s /Applications" in package_text


def test_workflow_builds_dmg_from_staged_app(workflow_text, package_text):
    macos = job_section(workflow_text, "build-macos")
    assert "-srcfolder staging" in macos
    assert "package_macos.sh --stage" in macos
    assert "easy-math-editor.app" in package_text


def test_packaging_prunes_nested_dot_apps_before_sign(package_text):
    assert "__dot__app" in package_text
    # Cleanup prints what it removes before deleting.
    assert "-name '*__dot__app' -print" in package_text
    # Pruning runs before signing.
    assert package_text.index("__dot__app") < package_text.index(
        'codesign --force --sign - "$APP"')
    # Bundle size is logged.
    assert 'du -sh "$APP"' in package_text


def test_editor_build_drops_collect_all_pyside6(workflow_text, script_text,
                                                 builder_text):
    # The macOS bundle must not collect the whole PySide6 package: the
    # nested Qt tool apps break codesign. The shared builder only does
    # that on Windows (or with --full-pyside6).
    assert "--collect-all PySide6" not in workflow_text
    assert "--collect-all PySide6" not in script_text
    assert '"--collect-all", "PySide6"' in builder_text
    assert 'os.name == "nt" or full_pyside6' in builder_text
    for hidden in ("PySide6.QtPdf", "PySide6.QtPdfWidgets"):
        assert hidden in builder_text, f"builder missing {hidden}"
    # Typst/numpy collection must stay.
    assert "typst" in builder_text
    assert "numpy" in builder_text


def test_smoke_checks_qt_platform_plugin():
    with open(SMOKE, encoding="utf-8") as h:
        text = h.read()
    assert "plugins/platforms" in text
    assert "libqcocoa.dylib" in text


def test_sign_step_fails_loudly(workflow_text, package_text):
    for text in (workflow_text, package_text):
        assert "continue-on-error" not in text
        assert "|| true" not in text


def test_sign_uses_macho_check_only(package_text):
    # Only real Mach-O files are signed; never plain directories.
    assert 'file -b "$f"' in package_text
    assert "Mach-O" in package_text
    assert "-print0" in package_text
    assert "read -r -d ''" in package_text
    # Old approach signed directories and any +x file; it must be gone.
    assert "-perm +111" not in package_text
    assert "-maxdepth 1 -mindepth 1" not in package_text


def test_sign_macho_loop_before_bundle(package_text):
    assert package_text.index("Mach-O") < package_text.index(
        'codesign --force --sign - "$APP"')
    # Bundled helpers are asserted executable before the loop covers them.
    assert "Contents/Resources/bin" in package_text


def test_sign_failure_prints_diagnostics(package_text):
    assert 'codesign -dvvv "$APP"' in package_text
    assert 'find "$APP" -type l' in package_text


def test_sign_verifies_everything(package_text):
    assert "codesign --verify --deep --strict" in package_text
    assert "codesign --verify --strict" in package_text


def test_final_bundle_sign_avoids_deep(package_text):
    hits = [
        line
        for line in package_text.splitlines()
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
    # Release ships the DMG and only runs on tag builds.
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


def test_script_mirrors_workflow(script_text, builder_text):
    # The local driver only orchestrates; the PyInstaller flags live in
    # the shared builder.
    assert "scripts/build_binaries.py" in script_text
    assert "scripts/package_macos.sh" in script_text
    for token in ("easy-math-lang", "easy-math-lsp", "easy-math-editor",
                  "ezmath", "PyInstaller"):
        assert token in script_text, f"script missing {token}"
    for token in ("entry", "PyInstaller", "ezmath"):
        assert token in builder_text, f"builder missing {token}"


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
    assert workflow_text.index("smoke_macos.sh") > workflow_text.index(
        "package_macos.sh")
    assert workflow_text.index("smoke_macos.sh") < workflow_text.index("hdiutil")


def test_release_marks_hyphen_tags_prerelease(workflow_text):
    assert "prerelease:" in workflow_text
    assert "contains(github.ref_name, '-')" in workflow_text


def test_release_guards_tag_matches_pyproject(workflow_text, guard_text):
    assert "Guard tag matches pyproject version" in workflow_text
    assert "check_tag_version.py" in workflow_text
    # The guard reads the version from pyproject.toml and strips the
    # leading "v" before comparing.
    assert "pyproject.toml" in guard_text
    assert 'removeprefix("v")' in guard_text
    assert "return 1" in guard_text


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
