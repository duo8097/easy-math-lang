#!/usr/bin/env python3
"""Fuzz-style audit script for easy-math-lang compiler (reproducible, seeded)."""
import os, sys, tempfile, random, time
sys.path.insert(0, 'src')
from compiler.pipeline import compile_ezmath

random.seed(42)

categories = [
    ("empty", ''),
    ("newline", '\n'),
    ("backslash", "\\"),
    ("math_unclosed", '\\hello'),
    ("block_unclosed", '*('),
    ("plot_bad_expr", '*plot(1/0 ; 0 ; 1)'),
    ("plot_bad_bounds", '*plot(x ; 1 ; 0)'),
    ("table_deep", '*table(\n' + 'A | B\n' * 10 + ')'),
    ("image_bad", '*image(../../../etc/passwd)'),
    ("unicode", '*pi\n*alpha'),
    ("crlf", 'hello\r\nworld'),
    ("large_num", '9^9^9'),
    ("calc_nested", 'calc(calc(1+1)+1)'),
]

crashes = {cat: 0 for cat, _ in categories}
hangs = {}

with tempfile.TemporaryDirectory() as td:
    for i in range(1000):
        cat, base = random.choice(categories)
        extra = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 ', k=random.randint(0, 20)))
        content = base + extra
        path = os.path.join(td, f'fuzz_{cat}_{i}.ezmath')
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(content)
        try:
            start = time.perf_counter()
            ok = compile_ezmath(path, output=path.replace('.ezmath', '.pdf'), format='pdf')
            elapsed = time.perf_counter() - start
            if elapsed > 10:
                hangs[cat] = hangs.get(cat, 0) + 1
                # We don't abort, just record.
        except Exception:
            crashes[cat] += 1
            # Expected: compiler catches errors gracefully; uncaught exception is a crash.

print('Fuzz results (1000 inputs, seed=42):')
print('Crash counts by category:', crashes)
print('Hang counts (>10s) by category:', hangs)
print('Total crashes:', sum(crashes.values()))
print('Total hangs:', sum(hangs.values()))
if sum(crashes.values()) == 0:
    print('No crashes detected.')
else:
    print('CRASHES DETECTED — see details above.')
