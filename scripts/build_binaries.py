#!/usr/bin/env python3
"""Build the Easy Math binaries with PyInstaller.

Single source of truth for the PyInstaller flags: the CI workflow
(``.github/workflows/build-installers.yml``) and every local build script
(``scripts/build_local.ps1``, ``scripts/build_macos.sh``,
``installer/build_linux.sh``, ``installer/PKGBUILD``) call this script,
so a flag change lands everywhere at once.

Usage (from the repo root)::

    uv run --frozen python scripts/build_binaries.py [--jobs N] [--full-pyside6]

Outputs (in ``dist/``):

=========================  ====================================
``easy-math-lang[.exe]``   compiler CLI (onefile)
``ezmath[.exe]``           short alias: symlink on POSIX, copy on Windows
``easy-math-lsp[.exe]``    language server (onefile)
``easy-math-editor/``      desktop editor (onedir, windowed)
=========================  ====================================

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

# One frozen entry point per binary.
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
# imports; PySide6.QtPdf/QtPdfWidgets back the PDF preview.
EDITOR_HIDDEN = [
    "editor.app",
    "editor.editor_widget",
    "editor.lsp_client",
    "editor.main_window",
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
    """Freeze one binary with PyInstaller."""
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
        "--distpath", str(DIST),
        "--workpath", str(ROOT / "build"),
        # Generated files stay under the ignored build directory.
        "--specpath", str(generated),
        "--additional-hooks-dir", str(ROOT / "scripts" / "pyinstaller_hooks"),
    ]
    cmd += ["--onedir", "--windowed"] if name == "easy-math-editor" \
        else ["--onefile"]
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
            # Collect only the Qt PDF modules instead of
            # the whole PySide6 tree (see the module docstring).
            cmd += ["--hidden-import", "PySide6.QtPdf"]
            cmd += ["--hidden-import", "PySide6.QtPdfWidgets"]

    _run(cmd, ROOT / "build" / ".pyinstaller-cache" / name)


def _alias() -> None:
    """Create a relocatable POSIX alias; Windows keeps a standalone copy."""
    source = DIST / _executable("easy-math-lang")
    if not source.is_file():
        print(f"::error::compiler output missing: {source}", file=sys.stderr)
        raise SystemExit(1)
    target = DIST / _executable("ezmath")
    # Remove a previous copy/link first; copy2 must never follow a stale
    # symlink and accidentally overwrite the real compiler.
    target.unlink(missing_ok=True)
    if os.name == "nt":
        shutil.copy2(source, target)
        target.chmod(0o755)
    else:
        target.symlink_to(source.name)


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
    # Each target has its own named work directory and stable spec/shim.
    # Resolve every future before creating the alias: failed builds must fail CI.
    with ThreadPoolExecutor(max_workers=min(args.jobs, len(ENTRIES))) as pool:
        builds = [pool.submit(_build, name, import_line, args.full_pyside6,
                              args.strip)
                  for name, import_line in ENTRIES.items()]
        for build in builds:
            build.result()
    _alias()

    print("\nBuild OK:")
    for name in ("easy-math-lang", "ezmath", "easy-math-lsp"):
        print(f"  {DIST / _executable(name)}")
    print(f"  {DIST / 'easy-math-editor'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
