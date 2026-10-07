"""Unknown-command diagnostics."""

import re
import sys

KNOWN_COMMANDS = {
    'define', 'p',
    'frac', 'fraction', 'abs', 'absolute', 'sin', 'cos', 'tan',
    'sqrt', 'squareroot', 'square-root', 'cbrt', 'cuberoot',
    'cube-root', 'log', 'ln',
    'pow', 'power', 'root', 'sum', 'summation', 'prod', 'product',
    'lim', 'limit',
    'table', 'matrix', 'mat',
    # symbol shortcuts handled separately: pi, infinity, degree, ...
}

# Friendly hint for common typos / LaTeX habits.
_SUGGESTIONS = {
    'fraction': 'frac',
    'power': 'pow',
    'squareroot': 'sqrt',
    'square-root': 'sqrt',
    'cuberoot': 'cbrt',
    'cube-root': 'cbrt',
    'absolute': 'abs',
    'summation': 'sum',
    'product': 'prod',
    'limit': 'lim',
    'fracd': 'frac',
    'squrt': 'sqrt',
    'sqt': 'sqrt',
    'tabl': 'table',
    'tabel': 'table',
    'tabble': 'table',
    'matrx': 'matrix',
    'matix': 'matrix',
    'martix': 'matrix',
}

KNOWN_GEOMETRY_COMMANDS = {
    'point', 'line', 'ray', 'circle', 'triangle', 'right-angle', 'angle',
    'equal-angle', 'equal-length', 'parallel', 'perp', 'on-line', 'on-circle',
    'distance', 'midpoint', 'intersection', 'arc', 'label',
    'length', 'angle-value', 'draw',
}


def warn_unknown_commands(text, line_no):
    """Warn if *name(...) appears where name is not in KNOWN_COMMANDS."""
    import difflib
    for m in re.finditer(r'\*([A-Za-z][A-Za-z0-9_\-]*)\s*\(', text):
        cmd = m.group(1)
        if cmd in KNOWN_COMMANDS:
            continue
        if cmd in KNOWN_GEOMETRY_COMMANDS or cmd.replace('_', '-') in KNOWN_GEOMETRY_COMMANDS:
            print(
                f'[Warning] Line {line_no}: *{cmd}(...) is only valid inside *draw(...) — treated as plain text',
                file=sys.stderr,
            )
            continue
        hint = _SUGGESTIONS.get(cmd)
        if hint is None:
            close = difflib.get_close_matches(
                cmd, sorted(KNOWN_COMMANDS | KNOWN_GEOMETRY_COMMANDS),
                n=1, cutoff=0.6,
            )
            hint = close[0] if close else None
        extra = f" Did you mean '*{hint}(...)'?" if hint else ""
        print(
            f'[Warning] Line {line_no}: unknown command *{cmd}(...) — treated as plain text.{extra}',
            file=sys.stderr,
        )
