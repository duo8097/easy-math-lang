#!/usr/bin/env python3
"""Build the Easy Math binaries with PyInstaller.

Single source of truth for the PyInstaller flags: the CI workflow
(``.github/workflows/build-installers.yml``) and every local build script
(``scripts/build_local.ps1``, ``scripts/build_macos.sh``,
``installer/build_linux.sh``, ``installer/PKGBUILD``) call this script,
so a flag change lands everywhere at once.

Usage (from the repo root)::

    uv run python scripts/build_binaries.py [--full-pyside6]

Outputs (in ``dist/``):

=========================  ====================================
``easy-math-lang[.exe]``   compiler CLI (onefile)
``ezmath[.exe]``           short alias: a copy of the compiler
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
import tempfile
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

# Data files and submodules PyInstaller cannot detect on its own.
# matplotlib is needed by *plot, typst by the PDF export, numpy by the
# geometry solver.
COLLECT = {
    "easy-math-lang": ["typst", "numpy", "matplotlib"],
    "easy-math-lsp": ["pygls", "typst", "numpy"],
    "easy-math-editor": ["typst", "numpy", "matplotlib"],
}

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


def _build(name: str, import_line: str, full_pyside6: bool) -> None:
    """Freeze one binary with PyInstaller."""
    with tempfile.TemporaryDirectory(prefix="easy-math-build-") as tmp:
        # The shim lives in a temp dir: no entry_*.py left in the repo.
        shim = Path(tmp) / f"{name.replace('-', '_')}_entry.py"
        shim.write_text(
            f"{import_line}\n"
            "if __name__ == '__main__':\n"
            "    main()\n",
            encoding="utf-8",
        )

        cmd = [
            sys.executable, "-m", "PyInstaller", str(shim),
            "--name", name,
            "--noconfirm",
            "--distpath", str(DIST),
            "--workpath", str(ROOT / "build"),
            # The spec file belongs to the temp dir as well: nothing is
            # left behind in the repository.
            "--specpath", tmp,
        ]
        cmd += ["--onedir", "--windowed"] if name == "easy-math-editor" \
            else ["--onefile"]

        for module in COLLECT[name]:
            cmd += ["--collect-all", module]

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
    """``ezmath`` is the short CLI alias: the same binary, copied."""
    source = DIST / _executable("easy-math-lang")
    if not source.is_file():
        print(f"::error::compiler output missing: {source}", file=sys.stderr)
        raise SystemExit(1)
    target = DIST / _executable("ezmath")
    shutil.copy2(source, target)
    target.chmod(0o755)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--jobs", type=int, default=1,
        help="number of independent PyInstaller processes (default: 1)")
    parser.add_argument(
        "--full-pyside6", action="store_true",
        help="collect the whole PySide6 package in the editor build "
             "(troubleshooting only; macOS must not use it)")
    args = parser.parse_args(argv[1:])
    if args.jobs < 1:
        parser.error("--jobs must be at least 1")

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("::error::PyInstaller is missing — run: uv sync --frozen",
              file=sys.stderr)
        return 1

    DIST.mkdir(parents=True, exist_ok=True)
    # Each target has its own named work directory and temporary spec/shim.
    # Resolve every future before creating the alias: failed builds must fail CI.
    with ThreadPoolExecutor(max_workers=min(args.jobs, len(ENTRIES))) as pool:
        builds = [pool.submit(_build, name, import_line, args.full_pyside6)
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
