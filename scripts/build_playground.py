#!/usr/bin/env python3
"""Build the in-browser playground package from the real compiler source.

Produces ``site/assets/playground/easymath.whl`` — a wheel built from the
repository's own source tree (via ``uv build``), so the playground runs the
real compiler with a single source of truth. No compiler code is copied or
duplicated here.

Usage:
    python3 scripts/build_playground.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE_DIR = ROOT / 'site'
OUT_DIR = SITE_DIR / 'assets' / 'playground'
WHEEL_NAME = 'easymath.whl'


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
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
    shutil.copyfile(wheels[0], OUT_DIR / WHEEL_NAME)
    print(f'wrote {OUT_DIR / WHEEL_NAME} ({(OUT_DIR / WHEEL_NAME).stat().st_size} bytes)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
