#!/usr/bin/env python3
"""Generate OG image and favicon set from the app icon glyph.

Usage:
    python3 scripts/build_og_and_favicons.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / 'site' / 'assets' / 'img'

GLYPH = '{ * \u03a3 }'
BG = (18, 20, 26)
FG = (254, 136, 8)


def make_og() -> None:
    W, H = 1200, 630
    img = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(img)
    for x in range(0, W, 40):
        draw.line([(x, 0), (x, H)], fill=(28, 30, 38))
    for y in range(0, H, 40):
        draw.line([(0, y), (W, y)], fill=(28, 30, 38))
    # try a monospace font
    font = None
    for cand in ('DejaVuSansMono-Bold.ttf', 'DejaVuSansMono.ttf'):
        try:
            font = ImageFont.truetype(cand, 180)
            break
        except OSError:
            pass
    if font is None:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), GLYPH, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((W - tw) / 2 - bbox[0], (H - th) / 2 - bbox[1]), GLYPH, fill=FG, font=font)
    img.save(IMG / 'og-image.png')


def make_favicon_svg() -> None:
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="6" fill="#12141a"/>
  <text x="16" y="22" font-family="monospace" font-size="14" font-weight="700" fill="#fe8808" text-anchor="middle">{ * \u03a3 }</text>
</svg>'''
    (IMG / 'favicon.svg').write_text(svg, encoding='utf-8')


def make_png(size: int, name: str) -> None:
    img = Image.new('RGBA', (size, size), BG + (255,))
    draw = ImageDraw.Draw(img)
    font = None
    for cand in ('DejaVuSansMono-Bold.ttf',):
        try:
            font = ImageFont.truetype(cand, max(8, size // 4))
            break
        except OSError:
            pass
    if font is None:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), GLYPH, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]), GLYPH, fill=FG, font=font)
    img.save(IMG / name)


def main() -> int:
    IMG.mkdir(parents=True, exist_ok=True)
    make_og()
    make_favicon_svg()
    make_png(32, 'favicon-32.png')
    make_png(180, 'apple-touch-icon.png')
    print('done')
    return 0


if __name__ == '__main__':
    sys.exit(main())
