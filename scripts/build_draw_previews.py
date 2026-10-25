#!/usr/bin/env python3
"""Render the *draw gallery thumbnails from the catalog examples.

The gallery never draws at runtime: every card image is a pre-rendered
SVG in ``src/editor/assets/draw_previews/<id>.svg`` produced by this
script (plus a ``manifest.json`` recording hashes, checked by
``tests/test_draw_catalog.py`` / ``tests/test_draw_gallery.py``).

Pipeline per catalog entry — the ONE geometry parser only::

    editor.draw_catalog entry.example
      -> draw_block_body()            # strip the *draw(...) wrapper
      -> geometry.parse_draw_block()  # -> Typst + @preview/cetz code
      -> assert the cetz import is present
      -> wrap: #set page(width: auto, height: auto, margin: 8pt)
      -> typst.compile(..., format='svg')
      -> src/editor/assets/draw_previews/<id>.svg

Nothing is hand-written: an example that stops compiling fails the run,
and changing an example invalidates its hash in the manifest.

Usage (from the repo root)::

    uv run python scripts/build_draw_previews.py            # write
    uv run python scripts/build_draw_previews.py --check    # verify only

Requires the ``typst`` package (already a project dependency) and, on
the first run, network access for Typst to fetch ``@preview/cetz`` —
never at editor runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'src'))

PREVIEW_DIR = os.path.join(ROOT, 'src', 'editor', 'assets', 'draw_previews')
MANIFEST_PATH = os.path.join(PREVIEW_DIR, 'manifest.json')
MANIFEST_VERSION = 1

#: Every thumbnail renders inside this auto-sized page.
PAGE_SETUP = '#set page(width: auto, height: auto, margin: 8pt)\n'


def render_one(entry) -> tuple[bytes, str]:
    """SVG bytes for one catalog entry + the Typst source used."""
    import typst
    from geometry.parsing import parse_draw_block

    from editor.draw_catalog import draw_block_body

    body = draw_block_body(entry.example)
    code = parse_draw_block(body)  # raises on invalid examples
    if '#import "@preview/cetz' not in code:
        raise RuntimeError(
            f'{entry.id}: parse_draw_block produced no cetz import')
    source = PAGE_SETUP + code + '\n'
    svg = typst.compile(source.encode('utf-8'), format='svg')
    if not isinstance(svg, (bytes, bytearray)):
        raise RuntimeError(f'{entry.id}: typst did not return SVG bytes')
    if not svg.lstrip().startswith(b'<svg') and b'<svg' not in svg[:512]:
        raise RuntimeError(f'{entry.id}: output does not look like SVG')
    return bytes(svg), source


def build(check: bool = False) -> int:
    from editor.draw_catalog import CATALOG

    rendered: dict[str, dict[str, str]] = {}
    stale: list[str] = []
    os.makedirs(PREVIEW_DIR, exist_ok=True)

    for entry in CATALOG:
        svg, _source = render_one(entry)
        path = os.path.join(PREVIEW_DIR, f'{entry.id}.svg')
        example_hash = hashlib.sha256(
            entry.example.encode('utf-8')).hexdigest()
        rendered[entry.id] = {
            # 'sha256' = the example the SVG was rendered from (the
            # stale-detection key tests/test_draw_catalog.py checks);
            # 'svg_sha256' = the rendered file itself.
            'sha256': example_hash,
            'svg_sha256': hashlib.sha256(svg).hexdigest(),
        }
        if check:
            if not os.path.isfile(path):
                stale.append(f'{entry.id}.svg (missing)')
            else:
                with open(path, 'rb') as fh:
                    current = fh.read()
                if current != svg:
                    stale.append(f'{entry.id}.svg (differs)')
        else:
            with open(path, 'wb') as fh:
                fh.write(svg)
            print(f'  {entry.id:<14} {len(svg):>6} bytes')

    manifest = {'version': MANIFEST_VERSION, 'examples': rendered}
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) +
                      '\n').encode('utf-8')
    if check:
        if not os.path.isfile(MANIFEST_PATH):
            stale.append('manifest.json (missing)')
        else:
            with open(MANIFEST_PATH, 'rb') as fh:
                if fh.read() != manifest_bytes:
                    stale.append('manifest.json (differs)')
        if stale:
            print('previews out of date:')
            for item in stale:
                print(f'  {item}')
            print('run: uv run python scripts/build_draw_previews.py')
            return 1
        print(f'ok: {len(rendered)} previews match the catalog')
        return 0

    with open(MANIFEST_PATH, 'wb') as fh:
        fh.write(manifest_bytes)
    print(f'wrote {len(rendered)} previews + manifest.json to '
          f'{os.path.relpath(PREVIEW_DIR, ROOT)}')
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--check', action='store_true',
                        help='verify existing previews instead of writing')
    args = parser.parse_args(argv)
    return build(check=args.check)


if __name__ == '__main__':
    raise SystemExit(main())
