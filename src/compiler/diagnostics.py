"""Unknown-command diagnostics."""

import re
import sys

KNOWN_COMMANDS = {
    'define', 'p',
    'frac', 'abs', 'sin', 'cos', 'tan', 'sqrt', 'log', 'ln',
    'pow', 'root', 'sum', 'prod', 'lim',
    # symbol shortcuts handled separately: pi, infinity, degree, ...
}

KNOWN_GEOMETRY_COMMANDS = {
    'point', 'line', 'ray', 'circle', 'triangle', 'right-angle', 'angle',
    'equal-angle', 'equal-length', 'parallel', 'perp', 'on-line', 'on-circle',
    'distance', 'midpoint', 'intersection', 'arc', 'label',
    'length', 'angle-value', 'draw',
}


def warn_unknown_commands(text, line_no):
    """Warn if *name(...) appears where name is not in KNOWN_COMMANDS."""
    for m in re.finditer(r'\*([A-Za-z][A-Za-z0-9_]*)\s*\(', text):
        cmd = m.group(1)
        if cmd in KNOWN_COMMANDS:
            continue
        if cmd in KNOWN_GEOMETRY_COMMANDS or cmd.replace('_', '-') in KNOWN_GEOMETRY_COMMANDS:
            print(
                f'[Warning] Line {line_no}: *{cmd}(...) is only valid inside *draw(...) — treated as plain text',
                file=sys.stderr,
            )
            continue
        print(
            f'[Warning] Line {line_no}: unknown command *{cmd}(...) — treated as plain text',
            file=sys.stderr,
        )
