#!/usr/bin/env python3
"""Generate static JSON data files for the site from repository sources.

The site never duplicates the *draw catalog or example snippets: this script
reads them from the real source (editor.draw_catalog, compiler) and writes
JSON under site/assets/data/. Run it after changing the catalog.

Usage:
    python3 scripts/build_site_data.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

OUT_DIR = ROOT / 'site' / 'assets' / 'data'


def build_comparison() -> list[dict]:
    pairs = [
        {
            "title": "Fraction",
            "latex": "\\\\frac{2}{3}",
            "ezmath": "*frac(2 ; 3)\n",
        },
        {
            "title": "Power and root",
            "latex": "x^{2} + \\\\sqrt{x + 1}",
            "ezmath": "*pow(x ; 2) + *root(2 ; x + 1)\n",
        },
        {
            "title": "Sum and integral",
            "latex": "\\\\sum_{i=1}^{n} i, \\\\int_{0}^{1} x^{2} dx",
            "ezmath": "*sum(i = 1 ; n ; i)\n*int(0 ; 1 ; x^2)\n",
        },
        {
            "title": "Limit",
            "latex": "\\\\lim_{x \\\\to 0} \\\\frac{\\\\sin x}{x}",
            "ezmath": "*lim(x -> 0 ; *frac(sin(x) ; x))\n",
        },
        {
            "title": "Matrix",
            "latex": "\\\\begin{pmatrix} a & b \\\\\\\\ c & d \\\\end{pmatrix}",
            "ezmath": "*matrix(a ; b | c ; d)\n",
        },
        {
            "title": "Column vector",
            "latex": "\\\\begin{pmatrix} 3 \\\\\\\\ 4 \\\\end{pmatrix}",
            "ezmath": "*vec(3 ; 4)\n",
        },
        {
            "title": "System of equations",
            "latex": "\\\\begin{cases} x + y = 5 \\\\\\\\ x - y = 1 \\\\end{cases}",
            "ezmath": "*cases(x + y = 5 | x - y = 1)\n",
        },
        {
            "title": "Piecewise function",
            "latex": "\\\\begin{cases} x^2, & x \\\\ge 0 \\\\\\\\ -x, & x < 0 \\\\end{cases}",
            "ezmath": "*cases(x^2 ; x >= 0 | -x ; x < 0)\n",
        },
        {
            "title": "Geometry figure",
            "latex": "% (TikZ omitted for brevity)",
            "ezmath": "*draw(\n    *point(A = 0, 0)\n    *point(B = 3, 0)\n    *point(C = 0, 4)\n    *triangle(A ; B ; C)\n)\n",
        },
        {
            "title": "Greek symbols",
            "latex": "\\\\alpha, \\\\beta, \\\\gamma, \\\\Delta",
            "ezmath": "*alpha *beta *gamma *Delta\n",
        },
    ]
    for p in pairs:
        p['latex_chars'] = len(p['latex'])
        p['ezmath_chars'] = len(p['ezmath'])
        p['latex_lines'] = p['latex'].count('\n') + 1
        p['ezmath_lines'] = p['ezmath'].count('\n') + 1
    return pairs


def build_examples() -> list[dict]:
    examples = []
    # Showcase snippets already on the landing page.
    showcase = [
        ('Basic math', '<width> = 5\n<area> = calc(<width> * 2)\n\nArea: <area>\n'),
        ('Fraction and equation', '*frac(2 ; 3)\n\n*frac(x + 1 ; x - 1)\n\nSolve: *frac(x ; 2) + *frac(1 ; 3) = *frac(5 ; 6)\n'),
        ('Vector', 'Vector: *vec(3 ; 4)\n\nLength: *root(2 ; *pow(3 ; 2) + *pow(4 ; 2))\n'),
        ('Simple *draw', '*draw(\n    *point(A = 0, 0)\n    *point(B = 3, 0)\n    *point(C = 0, 4)\n    *triangle(A ; B ; C)\n)\n'),
    ]
    for name, code in showcase:
        examples.append({'name': name, 'code': code})
    try:
        from editor.draw_catalog import CATALOG
        for entry in CATALOG:
            examples.append({'name': entry.title, 'code': entry.example + '\n', 'group': entry.group})
    except Exception as exc:
        print('draw catalog unavailable:', exc, file=sys.stderr)
    return examples


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    examples = build_examples()
    (OUT_DIR / 'examples.json').write_text(
        json.dumps(examples, ensure_ascii=False, indent=2), encoding='utf-8',
        newline='\n')
    comparison = build_comparison()
    (OUT_DIR / 'comparison.json').write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2), encoding='utf-8',
        newline='\n')
    print(f'wrote {len(examples)} examples, {len(comparison)} comparison pairs')
    return 0


if __name__ == '__main__':
    sys.exit(main())
