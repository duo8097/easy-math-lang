"""Diagnostics: unknown-command warnings and Python-style reports.

:func:`report` is the central diagnostic printer. It keeps the classic
first line byte-identical (``[Error] Line N: message`` — asserted by
tests, parsed by the editor, counted by the strict-mode counter) and
adds a Python-traceback-style context block under it::

    [Error] Line 12: undefined variable <widht>
      File "bai1.ezmath", line 12, column 8
        Tong = <widht> + 2
               ^^^^^^^

The block is only printed when a compile is active (see
:func:`bind_source`): the compile records the original source lines and
the filename on its ``CompileContext``, so the echo always shows the
real ``.ezmath`` line — line numbers here always refer to the original
file, never to transformed text or the generated ``.typ``.

Columns count characters, not bytes. Tabs are expanded to 4 columns.
Very long lines are truncated around the span with an ellipsis. When no
column is known (or it falls outside the line) the block prints the
``File ... line N`` header and the source line without a caret.

Color is applied only on a TTY and never when ``NO_COLOR`` is set, so
captured stderr (the editor's StringIO) stays plain text.
"""

import difflib
import os
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


# ------------------------------------------------------------------
# Python-style context blocks
# ------------------------------------------------------------------

TAB_SIZE = 4
# Echoed source lines longer than this are truncated around the span.
MAX_SOURCE_WIDTH = 200

# Set to the CompileContext of the active compile (or None). Callers
# bind via bind_source(); the pipeline's compile decorator clears it
# after the compile finishes.
_active_ctx = None


def bind_source(ctx):
    """Bind *ctx* (a CompileContext with source_lines/source_name)."""
    global _active_ctx
    _active_ctx = ctx


def unbind_source():
    """Clear the active compile binding (end of compile)."""
    global _active_ctx
    _active_ctx = None


def _active_source_line(ctx, line_no):
    if ctx is None or line_no is None:
        return None
    lines = getattr(ctx, 'source_lines', None)
    if not lines:
        return None
    try:
        index = int(line_no) - 1
        if index < 0:
            # Line numbers are 1-based; never wrap to the last line.
            return None
        src = lines[index]
    except (IndexError, TypeError, ValueError, OverflowError):
        return None
    return src if isinstance(src, str) else None


def source_span(line_no, pattern, occurrence=0):
    """Char span of the ``occurrence``-th regex match on the raw source
    line for *line_no* (0-based ``[start, end)``), or ``None``.

    Best effort: transformed text offsets are not reliable anchors for
    the original file, so matches are re-located by regex on the
    original line instead. Matches inside an ``[UNDEFINED: <name>]``
    placeholder are skipped so they never anchor the search.
    """
    src = _active_source_line(_active_ctx, line_no)
    if src is None:
        return None
    hits = 0
    try:
        for m in re.finditer(pattern, src):
            if src[max(0, m.start() - 12):m.start()] == '[UNDEFINED: ':
                continue
            if hits == occurrence:
                return (m.start(), m.end())
            hits += 1
    except Exception:
        return None
    return None


def source_col_for(line_no, pattern, occurrence=0):
    """1-based ``(col, end_col)`` for ``source_span`` or ``(None, None)``.

    ``end_col`` is one past the last character of the match.
    """
    span = source_span(line_no, pattern, occurrence=occurrence)
    if span is None:
        return None, None
    return span[0] + 1, span[1] + 1


def last_unescaped_bs_col(line_no):
    """1-based column of the last unescaped ``\\`` on the raw source
    line for *line_no* (the unclosed-math-delimiter opener), or
    ``(None, None)`` when the line is unavailable or has none."""
    src = _active_source_line(_active_ctx, line_no)
    if src is None:
        return None, None
    last = None
    i, n = 0, len(src)
    while i < n:
        if src[i] == '\\':
            if i + 1 < n and src[i + 1] == '\\':
                i += 2
                continue
            last = i
        i += 1
    if last is None:
        return None, None
    return last + 1, last + 2


def _bare_pattern(cmd):
    return (r'(?<![^\W_])(?<!\\)(?<!\*)\*'
            + re.escape(cmd)
            + r'(?![\w\-])(?!\s*\()')


def _call_pattern(cmd):
    return r'\*\s*' + re.escape(cmd) + r'(?![\w\-])\s*\('


def _expand_tabs(line):
    """Return (expanded_line, char_spans, total_width).

    ``char_spans[i]`` is the ``(start, end)`` offset of original
    character *i* in the expanded line. Columns in the report count
    original characters, the caret arithmetic works on the expanded
    text, so both stay consistent when tabs are present.
    """
    spans = []
    out = []
    width = 0
    for ch in line:
        if ch == '\t':
            stop = width + (TAB_SIZE - (width % TAB_SIZE))
            out.append(' ' * (stop - width))
            spans.append((width, stop))
            width = stop
        else:
            out.append(ch)
            spans.append((width, width + 1))
            width += 1
    return ''.join(out), spans, width


def _char_offset(spans, total, index):
    """Expanded offset of the 1-based *index* (``len+1`` == end of line)."""
    if index <= 0:
        return 0
    if index > len(spans):
        return total
    return spans[index - 1][0]


def _char_end_offset(spans, total, index):
    """Expanded end offset of the 1-based character at *index*
    (``len+1`` == end of line)."""
    if index <= 0:
        return 0
    if index > len(spans):
        return total
    return spans[index - 1][1]


def _fit_window(expanded, span_start, span_end, total):
    """Truncate an over-long expanded line around the span.

    Returns ``(display, span_start_in_display, truncated_left)``.
    """
    if total <= MAX_SOURCE_WIDTH:
        return expanded, span_start, False
    # Keep some context before the caret, never push the window off
    # the end of the line.
    start = max(0, min(span_start - 60, total - MAX_SOURCE_WIDTH))
    end = start + MAX_SOURCE_WIDTH
    display = expanded[start:end]
    truncated_left = start > 0
    if truncated_left:
        display = '…' + display
    if end < total:
        display += '…'
    return display, span_start - start + (1 if truncated_left else 0), truncated_left


def _color_enabled():
    if os.environ.get('NO_COLOR') is not None:
        return False
    try:
        return bool(sys.stderr.isatty())
    except Exception:
        return False


def _ansi(code, text):
    return f'\x1b[{code}m{text}\x1b[0m'



def report(severity, line_no, message, *, col=None, end_col=None):
    """Print a diagnostic: the classic first line, then a context block.

    The first line (``[Error] Line N: message``) is byte-identical to
    the previous direct prints. Under it, a Python-style block shows
    the original source line; when *col* (1-based, characters) is given
    a caret line underlines the span. When no source is bound to the
    active compile, or *line_no* is out of range, only the first line
    is printed.
    """
    try:
        if line_no is None:
            first = f'[{severity}] {message}'
        else:
            first = f'[{severity}] Line {line_no}: {message}'
        print(first, file=sys.stderr)
    except Exception:
        return
    try:
        _print_source_context(severity, line_no, col, end_col)
    except Exception:
        # A broken context block must never break the build.
        pass



def _print_source_context(severity, line_no, col, end_col):
    ctx = _active_ctx
    src = _active_source_line(ctx, line_no)
    if src is None:
        return
    name = getattr(ctx, 'source_name', '') or getattr(ctx, 'source_file', '')
    name = str(name or '<source>').replace('\r', ' ').replace('\n', ' ')
    src = src.replace('\r', '')
    expanded, spans, total = _expand_tabs(src)
    ncols = len(src)

    def _as_int(value):
        try:
            return int(value)
        except (TypeError, ValueError, OverflowError):
            return None

    col = _as_int(col)
    if col is not None and (col < 1 or col > ncols + 1):
        col = None
    if col is not None:
        end_col = _as_int(end_col)
        if end_col is None or end_col < col or end_col > ncols + 1:
            # Unknown/invalid end: underline just the one character.
            end_col = col + 1
    else:
        end_col = None

    color = _color_enabled()
    file_text = f'  File "{name}", line {line_no}'
    if col is not None:
        file_text += f', column {col}'
    if color:
        file_text = _ansi(2, file_text)
    print(file_text, file=sys.stderr)

    if col is None:
        print('    ' + expanded, file=sys.stderr)
        return
    span_start = _char_offset(spans, total, col)
    # end_col is one past the last character (1-based); the end offset is
    # the end of the character at index end_col - 1.
    span_end = _char_end_offset(spans, total, end_col - 1)
    caret = max(1, span_end - span_start)
    display, display_start, _left = _fit_window(expanded, span_start,
                                                span_start + caret, total)
    caret = max(1, min(caret, len(display) - display_start))
    print('    ' + display, file=sys.stderr)
    caret_text = _ansi(
        '1;31' if str(severity).lower().startswith('error') else '1;33',
        '^' * caret,
    ) if color else '^' * caret
    print('    ' + ' ' * display_start + caret_text, file=sys.stderr)


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
# belongs to the *cmd(...) path, not here). Letter classes are
# Unicode-aware ([^\W\d_] matches letters in any script) so *lưu reports
# *lưu, not a truncated *l. Shared with the LSP (analysis.py), which
# masks protected spans before matching.
BARE_COMMAND_RE = re.compile(
    r'(?<![^\W_])(?<!\\)(?<!\*)\*([^\W\d_][\w\-]*)(?![\w\-])(?!\s*\()'
)


def _warn_bare_command(cmd, line_no, occurrence=0):
    """Emit the diagnostic for one bare *cmd (no parens)."""
    if cmd in KNOWN_COMMANDS or cmd in _SYMBOL_WORDS or cmd == 'calc':
        # Known command used without parens, a symbol keyword (*alpha,
        # *pi, *quad, ...), or bare calc: all render literally today,
        # so they stay silent.
        return
    if cmd == 'draw':
        # Top-level *draw(...) is valid; a bare *draw is unclosed/malformed.
        col, end_col = source_col_for(line_no, _bare_pattern(cmd), occurrence)
        report(
            'Warning', line_no,
            'unclosed or malformed *draw(...) — treated as plain text',
            col=col, end_col=end_col,
        )
        return
    if cmd in KNOWN_GEOMETRY_COMMANDS or cmd.replace('_', '-') in KNOWN_GEOMETRY_COMMANDS:
        col, end_col = source_col_for(line_no, _bare_pattern(cmd), occurrence)
        report(
            'Warning', line_no,
            f'*{cmd} is only valid inside *draw(...) — treated as plain text',
            col=col, end_col=end_col,
        )
        return
    hint = _suggest_command(cmd)
    extra = f" Did you mean '*{hint}(...)'?" if hint else ""
    col, end_col = source_col_for(line_no, _bare_pattern(cmd), occurrence)
    report(
        'Warning', line_no,
        f'unknown command *{cmd} — treated as plain text.{extra}',
        col=col, end_col=end_col,
    )


def warn_unknown_commands(text, line_no):
    """Warn if *name(...) appears where name is not in KNOWN_COMMANDS."""
    call_seen = {}
    for m in re.finditer(r'\*([^\W\d_][\w\-]*)\s*\(', text):
        cmd = m.group(1)
        occurrence = call_seen.get(cmd, 0)
        call_seen[cmd] = occurrence + 1
        if cmd in KNOWN_COMMANDS:
            continue
        if cmd == 'draw':
            # Top-level *draw(...) is valid (pipeline handles single-line
            # and block forms); a leftover here is unclosed/malformed,
            # not "inside *draw".
            hint = None
            col, end_col = source_col_for(line_no, _call_pattern(cmd), occurrence)
            report(
                'Warning', line_no,
                'unclosed or malformed *draw(...) — treated as plain text',
                col=col, end_col=end_col,
            )
            continue
        if cmd in KNOWN_GEOMETRY_COMMANDS or cmd.replace('_', '-') in KNOWN_GEOMETRY_COMMANDS:
            col, end_col = source_col_for(line_no, _call_pattern(cmd), occurrence)
            report(
                'Warning', line_no,
                f'*{cmd}(...) is only valid inside *draw(...) — treated as plain text',
                col=col, end_col=end_col,
            )
            continue
        hint = _suggest_command(cmd)
        extra = f" Did you mean '*{hint}(...)'?" if hint else ""
        col, end_col = source_col_for(line_no, _call_pattern(cmd), occurrence)
        report(
            'Warning', line_no,
            f'unknown command *{cmd}(...) — treated as plain text.{extra}',
            col=col, end_col=end_col,
        )
    # Bare *word without parens (e.g. *foo, *bogus). Generated $...$
    # math spans are skipped: 'a*b' inside math is multiplication,
    # not a command. Callers (*p/raw, calc, math-placeholder stages)
    # run before this, so their contents never reach the scan.
    bare_seen = {}
    for tok in re.split(r'(\$.*?\$)', text):
        if len(tok) >= 2 and tok.startswith('$') and tok.endswith('$'):
            continue
        for m in BARE_COMMAND_RE.finditer(tok):
            cmd = m.group(1)
            occurrence = bare_seen.get(cmd, 0)
            bare_seen[cmd] = occurrence + 1
            _warn_bare_command(cmd, line_no, occurrence)
