"""Unknown-command diagnostics."""

import re
import sys

KNOWN_COMMANDS = {
    'define', 'p',
    'frac', 'abs', 'sin', 'cos', 'tan', 'sqrt', 'log', 'ln',
    'pow', 'root', 'sum', 'prod', 'lim',
    # symbol shortcuts handled separately: pi, infinity, degree, ...
}


def warn_unknown_commands(text, line_no):
    """Warn if *name(...) appears where name is not in KNOWN_COMMANDS."""
    for m in re.finditer(r'\*([A-Za-z][A-Za-z0-9_]*)\s*\(', text):
        cmd = m.group(1)
        if cmd not in KNOWN_COMMANDS:
            print(
                f'[Warning] Line {line_no}: unknown command *{cmd}(...) — treated as plain text',
                file=sys.stderr,
            )
