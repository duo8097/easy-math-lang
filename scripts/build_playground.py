#!/usr/bin/env python3
"""Build the in-browser playground package from the real compiler source.

Produces a valid wheel under ``site/assets/playground/`` plus a
``wheel.json`` naming the file, so the playground can install the real
compiler with a single source of truth. Desktop-only dependencies
(PySide6) and the native ``typst`` package are stripped from the wheel
metadata because they are not installable in Pyodide; the playground only
needs the pure-Python compiler (NumPy and Matplotlib are provided by
Pyodide).

Usage:
    python3 scripts/build_playground.py
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE_DIR = ROOT / 'site'
OUT_DIR = SITE_DIR / 'assets' / 'playground'


def _strip_deps(metadata: str) -> str:
    lines = metadata.splitlines(keepends=True)
    out = []
    for line in lines:
        if line.startswith('Requires-Dist:'):
            if re.search(r'\b(pyside6|typst|matplotlib|numpy|pygls)\b', line,
                         re.IGNORECASE):
                continue
        out.append(line)
    return ''.join(out)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.iterdir():
        if old.is_file():
            old.unlink()
    work = ROOT / '.build' / 'playground'
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    try:
        subprocess.run(
            ['uv', 'build', '--wheel', '--out-dir', str(work)],
            cwd=ROOT, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f'build failed: {exc}', file=sys.stderr)
        return 1
    wheels = list(work.glob('*.whl'))
    if not wheels:
        print('no wheel produced', file=sys.stderr)
        return 1
    src_wheel = wheels[0]

    # Rewrite metadata to drop non-Pyodide dependencies, keeping the
    # standard filename so micropip can identify the distribution.
    dst_wheel = OUT_DIR / src_wheel.name
    with zipfile.ZipFile(src_wheel) as zin:
        names = zin.namelist()
        with zipfile.ZipFile(dst_wheel, 'w', zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename.endswith('.dist-info/METADATA'):
                    data = _strip_deps(data.decode('utf-8')).encode('utf-8')
                zout.writestr(info, data)

    (OUT_DIR / 'wheel.json').write_text(
        json.dumps({'file': dst_wheel.name}), encoding='utf-8', newline='\n')
    print(f'wrote {dst_wheel} ({dst_wheel.stat().st_size} bytes)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
