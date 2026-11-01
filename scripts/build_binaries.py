#!/usr/bin/env python3
"""Build the Easy Math binaries with PyInstaller.

Single source of truth for the PyInstaller flags: the CI workflow
(``.github/workflows/build-installers.yml``) and every local build script
(``scripts/build_local.ps1``, ``scripts/build_macos.sh``,
``installer/build_linux.sh``, ``installer/PKGBUILD``) call this script,
so a flag change lands everywhere at once.

This implementation (Approach A) keeps 3 separate executables but ships
them from ONE shared library directory: the CLI and the language server
reuse the desktop editor's collected libraries instead of each carrying
their own copy (NumPy, Matplotlib, Typst, PySide6, …). The editor stays
the "owner" of the library set because it is the only target that needs
the GUI modules.

Usage (from the repo root)::

    uv run --frozen python scripts/build_binaries.py [--jobs N] [--full-pyside6]

Outputs (in ``dist/``):

========================  ====================================
``easy-math-lang/``         shared onedir bundle directory:
                            ``easy-math-lang`` (compiler CLI),
                            ``easy-math-lsp`` (language server),
                            ``easy-math-editor`` (desktop editor) and a
                            single ``_internal/`` with all heavy libraries
``easy-math-lang/ezmath``   short alias: symlink on POSIX, copy on Windows
========================  ====================================

The three executables live next to one ``_internal`` directory, which is
how PyInstaller's onedir layout shares libraries: the bootloader resolves
``sys._MEIPASS`` from the executable's own location, so every executable
in the same directory reuses the same library copy.

``--full-pyside6`` adds ``--collect-all PySide6`` to the editor build.
Use only for troubleshooting; macOS must not (the full PySide6 tree drags
in the nested Qt tool apps that break ``codesign``).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
STAGING = ROOT / "build" / "dist-staging"

# Final shared bundle directory (contains the exes + one _internal).
SHARED_DIR = "easy-math-lang"


# One frozen entry point per binary. All of them are assembled into the
# same shared onedir directory at the end of the build.
ENTRIES = {
    "easy-math-lang": "from compiler import main",
    "easy-math-lsp": "from lsp.server import main",
    "easy-math-editor": "from editor.app import main",
}

# Prefer normal package hooks to collect-all (which includes tests/backends).
# Geometry diagnostics need NumPy in the LSP but do not render PDFs/plots.
COMMON_EXCLUDES = ["pytest", "numpy.tests", "numpy.f2py", "matplotlib.tests"]
GUI_EXCLUDES = ["PySide6", "PyQt6", "PyQt5", "PySide2", "tkinter"]

# The editor drives its own modules through Qt, so they must be hidden
# imports; PySide6.QtPdf/QtPdfWidgets back the PDF preview and
# PySide6.QtSvg the *draw gallery/template thumbnails (both imported
# lazily).
EDITOR_HIDDEN = [
    "editor.app",
    "editor.editor_widget",
    "editor.lsp_client",
    "editor.main_window",
    "editor.draw_gallery",
    "editor.draw_template",
]


def _executable(name: str) -> str:
    """Platform file name of a built binary (``foo`` or ``foo.exe``)."""
    return f"{name}.exe" if os.name == "nt" else name


def _run(cmd: list[str], cache_dir: Path) -> None:
    print("$ " + " ".join(cmd), flush=True)
    # PyInstaller's binary cache is mutable; concurrent targets must not
    # rewrite the same cached DLL/shared library.
    env = dict(os.environ, PYINSTALLER_CONFIG_DIR=str(cache_dir))
    subprocess.run(cmd, cwd=ROOT, check=True, env=env)


def _build(name: str, import_line: str, full_pyside6: bool,
           strip_binaries: bool = False) -> None:
    """Freeze one binary with PyInstaller into its own staging bundle."""
    # Stable paths and unchanged shim mtimes let PyInstaller reuse Analysis/PYZ.
    generated = ROOT / "build" / "entrypoints" / name
    generated.mkdir(parents=True, exist_ok=True)
    shim = generated / f"{name.replace('-', '_')}_entry.py"
    source = f"{import_line}\nif __name__ == '__main__':\n    main()\n"
    if not shim.exists() or shim.read_text(encoding="utf-8") != source:
        shim.write_text(source, encoding="utf-8")

    cmd = [
        sys.executable, "-m", "PyInstaller", str(shim),
        "--name", name,
        "--noconfirm",
        "--distpath", str(STAGING),
        "--workpath", str(ROOT / "build"),
        # Generated files stay under the ignored build directory.
        "--specpath", str(generated),
        "--additional-hooks-dir", str(ROOT / "scripts" / "pyinstaller_hooks"),
    ]
    # Switch CLI and LSP from onefile to onedir to share heavy libraries
    # with the editor. The editor remains onedir for GUI functionality.
    # Each target freezes into its own staging bundle; _assemble() later
    # merges them into the shared dist bundle.
    if name == "easy-math-editor":
        cmd += ["--onedir", "--windowed"]
    elif name in ("easy-math-lang", "easy-math-lsp"):
        cmd += ["--onedir", "--console"]
    else:
        raise AssertionError(f"unknown entry point: {name}")
    if strip_binaries:
        # PyInstaller strips cached native libraries BEFORE packing them.
        # Never run strip on the finished onefile executable: its appended
        # payload would be lost. Windows/macOS keep their default behavior.
        cmd += ["--strip"]

    excludes = list(COMMON_EXCLUDES)
    if name != "easy-math-editor":
        excludes += GUI_EXCLUDES
    if name == "easy-math-lsp":
        excludes += ["typst", "matplotlib"]
    for module in excludes:
        cmd += ["--exclude-module", module]

    if name == "easy-math-editor":
        for mod in EDITOR_HIDDEN:
            cmd += ["--hidden-import", mod]
        if full_pyside6:
            cmd += ["--collect-all", "PySide6"]
        else:
            # Collect only the Qt PDF/SVG modules instead of
            # the whole PySide6 tree (see the module docstring).
            cmd += ["--hidden-import", "PySide6.QtPdf"]
            cmd += ["--hidden-import", "PySide6.QtPdfWidgets"]
            cmd += ["--hidden-import", "PySide6.QtSvg"]
        previews = ROOT / "src" / "editor" / "assets" / "draw_previews"
        if previews.is_dir():
            sep = ";" if os.name == "nt" else ":"
            cmd += ["--add-data", f"{previews}{sep}editor/assets/draw_previews"]

    _run(cmd, ROOT / "build" / ".pyinstaller-cache" / name)


def _assemble() -> None:
    """Merge the staged builds into one shared onedir bundle directory.

    The desktop editor build carries the full heavy library set (PySide6,
    NumPy, Matplotlib, Typst, …). The CLI and LSP builds carry smaller,
    more focused sets, so their executables are placed next to the editor's
    collected libraries: every executable in a directory reuses that
    directory as ``sys._MEIPASS``, which is exactly the PyInstaller onedir
    "shared library directory" behavior we want (one physical copy of each
    heavy library in the final install).
    """
    editor_bundle = STAGING / "easy-math-editor"
    editor_app = editor_bundle / "easy-math-editor.app"
    cli_exe = STAGING / "easy-math-lang" / _executable("easy-math-lang")
    lsp_exe = STAGING / "easy-math-lsp" / _executable("easy-math-lsp")
    for path in (cli_exe, lsp_exe):
        if not path.is_file():
            print(f"::error::missing build output: {path}", file=sys.stderr)
            raise SystemExit(1)

    shared = DIST / SHARED_DIR
    if shared.exists():
        shutil.rmtree(shared)
    shared.mkdir(parents=True)
    shutil.copy2(cli_exe, shared / _executable("easy-math-lang"))
    shutil.copy2(lsp_exe, shared / _executable("easy-math-lsp"))

    editor_dest = shared / _executable("easy-math-editor")
    if editor_app.is_dir():
        # macOS: the editor ships as an .app bundle; its ``Contents/Frameworks``
        # directory is the shared library directory. Helper executables placed
        # in the bundle's ``Contents/MacOS`` (see scripts/package_macos.sh) share
        # it with the editor. The .app itself is emitted at ``dist/`` root so the
        # packaging/signing step can bundle the helpers into it.
        shutil.copytree(editor_app / "Contents" / "Frameworks",
                        shared / "_internal", dirs_exist_ok=True)
        app_dest = DIST / "easy-math-editor.app"
        if app_dest.exists():
            shutil.rmtree(app_dest)
        shutil.copytree(editor_app, app_dest)
    else:
        editor_exe = editor_bundle / _executable("easy-math-editor")
        if not editor_exe.is_file():
            print(f"::error::missing build output: {editor_exe}",
                  file=sys.stderr)
            raise SystemExit(1)
        shutil.copy2(editor_exe, editor_dest)
        shutil.copytree(editor_bundle / "_internal", shared / "_internal",
                        dirs_exist_ok=True)

    # Short alias for the compiler: inside the shared bundle it reuses the
    # same _internal directory as the real executable.
    _alias()


def _alias() -> None:
    """Create the short compiler alias inside the shared bundle.

    The CLI is an onedir executable living in the shared bundle directory
    next to the single ``_internal`` library directory; the alias reuses
    that same library directory.
    """
    shared = DIST / SHARED_DIR
    alias = shared / _executable("ezmath")
    alias.unlink(missing_ok=True)
    if os.name == "nt":
        shutil.copy2(shared / _executable("easy-math-lang"), alias)
        alias.chmod(0o755)
    else:
        alias.symlink_to("easy-math-lang")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--jobs", type=int,
        help="number of independent PyInstaller processes; overrides "
             "EASYMATH_BUILD_JOBS (default: up to 2 CPUs)")
    parser.add_argument(
        "--full-pyside6", action="store_true",
        help="collect the whole PySide6 package in the editor build "
             "(troubleshooting only; macOS must not use it)")
    parser.add_argument(
        "--strip", action=argparse.BooleanOptionalAction,
        default=sys.platform.startswith("linux"),
        help="strip native libraries before packing (default: Linux only); "
             "--no-strip retains native symbols for debugging")
    args = parser.parse_args(argv[1:])
    if args.jobs is None:
        try:
            args.jobs = int(os.environ.get(
                "EASYMATH_BUILD_JOBS", str(min(2, os.cpu_count() or 1))))
        except ValueError:
            parser.error("EASYMATH_BUILD_JOBS must be a positive integer")
    if args.jobs < 1:
        parser.error("--jobs must be at least 1")
    if args.strip and not shutil.which("strip"):
        parser.error("strip not found; install binutils or pass --no-strip")

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("::error::PyInstaller is missing — run: uv sync --frozen",
              file=sys.stderr)
        return 1

    DIST.mkdir(parents=True, exist_ok=True)
    STAGING.mkdir(parents=True, exist_ok=True)
    # Each target has its own named work directory and stable spec/shim.
    # Resolve every future before assembling: failed builds must fail CI.
    with ThreadPoolExecutor(max_workers=min(args.jobs, len(ENTRIES))) as pool:
        builds = [pool.submit(_build, name, import_line, args.full_pyside6,
                              args.strip)
                  for name, import_line in ENTRIES.items()]
        for build in builds:
            build.result()
    _assemble()
    _alias()

    print("\nBuild OK:")
    print(f"  {DIST / SHARED_DIR}/")  # shared onedir bundle (one _internal)
    print(f"  {DIST / SHARED_DIR / _executable('ezmath')} (alias)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
