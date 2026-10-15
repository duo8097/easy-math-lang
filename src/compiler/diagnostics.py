"""Unknown-command diagnostics."""

import difflib
import re
import sys

from .symbols import WORD_REPLACEMENTS

# Bare *word keywords that render as glyphs (not commands); a bare
# occurrence must stay silent (e.g. *alpha, *pi, *quad).
_SYMBOL_WORDS = frozenset(old for old, _new in WORD_REPLACEMENTS)

KNOWN_COMMANDS = {
    'define', 'p',
    'doc_title', 'doc-title', 'doctitle', 'title',
    'doc_font', 'doc-font', 'docfont',
    'frac', 'fraction', 'abs', 'absolute', 'sin', 'cos', 'tan',
    'sqrt', 'squareroot', 'square-root', 'cbrt', 'cuberoot',
    'cube-root', 'log', 'ln',
    'pow', 'power', 'root', 'sum', 'summation', 'prod', 'product',
    'lim', 'limit',
    'int', 'integral', 'oint', 'cases', 'vec', 'binom',
    'diff', 'pdiff', 'det', 'set', 'align',
    'cot', 'sec', 'csc', 'arcsin', 'arccos', 'arctan',
    'sinh', 'cosh', 'tanh', 'coth',
    'hat', 'bar', 'overline', 'tilde', 'dot',
    'table', 'matrix', 'mat',
    'plot',
    'bold', 'b', 'italic', 'i', 'underline', 'u',
    'newpage', 'pagebreak', 'image',
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
    'frcc': 'frac',
    'squrt': 'sqrt',
    'sqt': 'sqrt',
    'tabl': 'table',
    'tabel': 'table',
    'tabble': 'table',
    'matrx': 'matrix',
    'matix': 'matrix',
    'martix': 'matrix',
    'blod': 'bold',
    'textbf': 'bold',
    'textit': 'italic',
}

KNOWN_GEOMETRY_COMMANDS = {
    'point', 'line', 'ray', 'circle', 'triangle', 'right-angle', 'angle',
    'equal-angle', 'equal-length', 'parallel', 'perp', 'on-line', 'on-circle',
    'distance', 'midpoint', 'intersection', 'arc', 'label',
    'length', 'angle-value', 'draw',
}


def _levenshtein(a, b):
    """Small edit distance for suggestion gating (stdlib only)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1,
                         prev[j - 1] + (ca != cb))
        prev = cur
    return prev[len(b)]


def _suggest_command(cmd):
    """Closest known command name for *cmd, or None when nothing is close."""
    hint = _SUGGESTIONS.get(cmd)
    if hint is None:
        close = difflib.get_close_matches(
            cmd, sorted(KNOWN_COMMANDS | KNOWN_GEOMETRY_COMMANDS),
            n=1, cutoff=0.8,
        )
        if close and _levenshtein(cmd, close[0]) <= 2:
            hint = close[0]
        else:
            hint = None
    return hint


# Bare *word without parens. The star must start a word: not preceded
# by a letter/digit (a*b is multiplication), another star (** is the
# multiplication dot) or a backslash (escaped asterisk). The word must
# match in full (no partial backtrack into *cmd(...) — a following '('
# belongs to the *cmd(...) path, not here). Shared with the LSP
# (analysis.py), which masks protected spans before matching.
BARE_COMMAND_RE = re.compile(
    r'(?<![A-Za-z0-9_*\\])\*([A-Za-z][A-Za-z0-9_\-]*)(?![A-Za-z0-9_\-])(?!\s*\()'
)


def _warn_bare_command(cmd, line_no):
    """Emit the diagnostic for one bare *cmd (no parens)."""
    if cmd in KNOWN_COMMANDS or cmd in _SYMBOL_WORDS or cmd == 'calc':
        # Known command used without parens, a symbol keyword (*alpha,
        # *pi, *quad, ...), or bare calc: all render literally today,
        # so they stay silent.
        return
    if cmd == 'draw':
        # Top-level *draw(...) is valid; a bare *draw is unclosed/malformed.
        print(
            f'[Warning] Line {line_no}: unclosed or malformed *draw(...) — treated as plain text',
            file=sys.stderr,
        )
        return
    if cmd in KNOWN_GEOMETRY_COMMANDS or cmd.replace('_', '-') in KNOWN_GEOMETRY_COMMANDS:
        print(
            f'[Warning] Line {line_no}: *{cmd} is only valid inside *draw(...) — treated as plain text',
            file=sys.stderr,
        )
        return
    hint = _suggest_command(cmd)
    extra = f" Did you mean '*{hint}(...)'?" if hint else ""
    print(
        f'[Warning] Line {line_no}: unknown command *{cmd} — treated as plain text.{extra}',
        file=sys.stderr,
    )


def warn_unknown_commands(text, line_no):
    """Warn if *name(...) appears where name is not in KNOWN_COMMANDS."""
    for m in re.finditer(r'\*([A-Za-z][A-Za-z0-9_\-]*)\s*\(', text):
        cmd = m.group(1)
        if cmd in KNOWN_COMMANDS:
            continue
        if cmd == 'draw':
            # Top-level *draw(...) is valid (pipeline handles single-line
            # and block forms); a leftover here is unclosed/malformed,
            # not "inside *draw".
            hint = None
            print(
                f'[Warning] Line {line_no}: unclosed or malformed *draw(...) — treated as plain text',
                file=sys.stderr,
            )
            continue
        if cmd in KNOWN_GEOMETRY_COMMANDS or cmd.replace('_', '-') in KNOWN_GEOMETRY_COMMANDS:
            print(
                f'[Warning] Line {line_no}: *{cmd}(...) is only valid inside *draw(...) — treated as plain text',
                file=sys.stderr,
            )
            continue
        hint = _suggest_command(cmd)
        extra = f" Did you mean '*{hint}(...)'?" if hint else ""
        print(
            f'[Warning] Line {line_no}: unknown command *{cmd}(...) — treated as plain text.{extra}',
            file=sys.stderr,
        )
    # Bare *word without parens (e.g. *foo, *bogus). Generated $...$
    # math spans are skipped: 'a*b' inside math is multiplication,
    # not a command. Callers (*p/raw, calc, math-placeholder stages)
    # run before this, so their contents never reach the scan.
    for tok in re.split(r'(\$.*?\$)', text):
        if len(tok) >= 2 and tok.startswith('$') and tok.endswith('$'):
            continue
        for m in BARE_COMMAND_RE.finditer(tok):
            _warn_bare_command(m.group(1), line_no)
