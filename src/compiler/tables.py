"""Tables and matrices (*table, *matrix / *mat).

Syntax (same separators everywhere, friendly by default):

    *table(Name ; Age ; City | Alice ; 20 ; Hanoi | Bob ; 22 ; Saigon)
    *matrix(1 ; 2 | 3 ; 4)

- Rows are separated by ``|`` (a single pipe at paren depth 0).
- Cells inside a row are separated by ``;`` — or by ``,`` when the row
  contains no ``;`` (same friendly rule as *frac, *pow, ...).
- ``*mat(...)`` is an alias of ``*matrix(...)``.
- Variables, defines, calc(), math commands and symbol shortcuts all
  work inside cells.

Row separator details:

- ``|`` inside ``"..."`` quotes or nested ``()``/``{}``/``[]`` never
  splits (so ``*frac(1 ; 2)`` and ``"a|b"`` survive).
- ``||`` (logical or), ``|-`` / ``-|`` and ``|->`` (maps-to) are ASCII
  symbol shortcuts — a ``|`` immediately adjacent to another ``|`` or
  to ``-`` never splits, so ``A || B`` stays one cell.
- Use ``*mid`` for a literal | inside a cell, or quote it: ``"a|b"``.

Multiline block form (one row per line, ``|`` optional — newlines also
break rows, empty rows are ignored):

    *table(
        Name ; Age
        Alice ; 20
    )
    *matrix(
        1 ; 2
        3 ; 4
    )

Typst mapping:

- ``*table`` -> ``#table(columns: N, [cell], ...)`` (text mode).
- ``*matrix`` -> ``$mat(a, b; c, d)$`` (Typst math ``mat``).

This module is deliberately standalone (stdlib only): the compiler
pipeline and the LSP both reuse the parsing helpers, while cell
rendering callbacks live with the callers (text pipeline vs math
pipeline) so there are no import cycles.
"""

import re
import sys

TABLE_NAMES = ('table',)
MATRIX_NAMES = ('matrix', 'mat')
ALL_NAMES = ('table', 'matrix', 'mat')

_CALL_RE = re.compile(r'\*(table|matrix|mat)\s*\(')


def is_table_call(name):
    return name == 'table'


def is_matrix_call(name):
    return name in MATRIX_NAMES


def find_next_call(text, start=0):
    """Locate the next *table/*matrix/*mat call at/after *start*.

    Returns (name, call_start, inner_start, call_end, inner_raw) where
    *call_start* is the index of ``*``, *inner_start* the index just
    after ``(``, *call_end* one past the matching ``)``, and
    *inner_raw* the raw inner text. Returns None when no opener
    remains. When the opener is unclosed, warns and returns a
    ('unclosed', ...) marker so callers can skip it without looping.
    """
    pos = start
    while True:
        m = _CALL_RE.search(text, pos)
        if not m:
            return None
        name = m.group(1)
        call_start = m.start()
        inner_start = m.end()
        depth = 1
        i = inner_start
        in_quote = False
        while i < len(text) and depth > 0:
            ch = text[i]
            if ch == '"' and (i == 0 or text[i - 1] != '\\'):
                in_quote = not in_quote
            elif not in_quote:
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
            i += 1
        if depth != 0:
            return ('unclosed', name, call_start, inner_start, None, None)
        call_end = i
        inner_raw = text[inner_start:call_end - 1]
        return (name, call_start, inner_start, call_end, inner_raw)


def split_rows_top_level(s):
    """Split *s* on top-level ``|`` row separators.

    Depth-aware for (), {} and [], quote-aware for "...". A ``|``
    adjacent to another ``|`` or to ``-`` is part of an ASCII symbol
    (||, |-, -|, |->) and never splits.
    """
    parts = []
    cur = []
    dp = db = br = 0
    in_quote = False
    n = len(s)
    for idx, ch in enumerate(s):
        if ch == '"' and (idx == 0 or s[idx - 1] != '\\'):
            in_quote = not in_quote
            cur.append(ch)
            continue
        if in_quote:
            cur.append(ch)
            continue
        if ch == '(':
            dp += 1
        elif ch == ')' and dp > 0:
            dp -= 1
        elif ch == '{':
            db += 1
        elif ch == '}' and db > 0:
            db -= 1
        elif ch == '[':
            br += 1
        elif ch == ']' and br > 0:
            br -= 1
        if ch == '|' and dp == 0 and db == 0 and br == 0:
            prev_c = s[idx - 1] if idx > 0 else ''
            next_c = s[idx + 1] if idx + 1 < n else ''
            if prev_c in ('|', '-') or next_c in ('|', '-'):
                cur.append(ch)
                continue
            parts.append(''.join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append(''.join(cur))
    return parts


def split_cells_top_level(row):
    """Split one row into cells (friendly ``;``-wins rule).

    Same rule as math_commands.split_top_level_args: when ``;`` appears
    at depth 0, split on ``;`` only (so ``100,000`` stays intact);
    otherwise split on ``,`` too. Quote- and depth-aware.
    """
    def _has_top_semi(s):
        dp = db = br = 0
        q = False
        for i, ch in enumerate(s):
            if ch == '"' and (i == 0 or s[i - 1] != '\\'):
                q = not q
                continue
            if q:
                continue
            if ch == '(':
                dp += 1
            elif ch == ')' and dp > 0:
                dp -= 1
            elif ch == '{':
                db += 1
            elif ch == '}' and db > 0:
                db -= 1
            elif ch == '[':
                br += 1
            elif ch == ']' and br > 0:
                br -= 1
            elif ch == ';' and dp == 0 and db == 0 and br == 0:
                return True
        return False

    has_semi = _has_top_semi(row)
    seps = (';',) if has_semi else (';', ',')
    parts = []
    cur = []
    dp = db = br = 0
    in_quote = False
    for idx, ch in enumerate(row):
        if ch == '"' and (idx == 0 or row[idx - 1] != '\\'):
            in_quote = not in_quote
            cur.append(ch)
            continue
        if in_quote:
            cur.append(ch)
            continue
        if ch == '(':
            dp += 1
        elif ch == ')' and dp > 0:
            dp -= 1
        elif ch == '{':
            db += 1
        elif ch == '}' and db > 0:
            db -= 1
        elif ch == '[':
            br += 1
        elif ch == ']' and br > 0:
            br -= 1
        if ch in seps and dp == 0 and db == 0 and br == 0:
            parts.append(''.join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    parts.append(''.join(cur).strip())
    return parts


def parse_grid(inner):
    """Parse raw inner text into a raw grid (list of rows of cells)."""
    rows_raw = split_rows_top_level(inner)
    return [split_cells_top_level(r) for r in rows_raw]


def normalize_grid(grid, line_no, kind):
    """Filter empties, pad ragged rows, warn; None when empty.

    - Drops rows where every cell is blank (lets ``a | | b`` and
      trailing ``|`` work, and lets block form join lines with ``|``).
    - Pads short rows with ``''`` up to the widest row and warns.
    - Returns None (caller leaves input as-is) when nothing remains.
    """
    kept = [r for r in grid if any(c.strip() for c in r)]
    if not kept:
        print(
            f'[Warning] Line {line_no}: *{kind}(...) is empty — leaving as-is',
            file=sys.stderr,
        )
        return None
    widths = [len(r) for r in kept]
    ncols = max(widths)
    if len(set(widths)) != 1:
        print(
            f'[Warning] Line {line_no}: *{kind}(...) rows have different '
            f'lengths {widths} — padding to {ncols} column(s)',
            file=sys.stderr,
        )
        kept = [r + [''] * (ncols - len(r)) for r in kept]
    return kept


def _escape_brackets_outside_math(s):
    """Escape [ ] outside $...$ so table cells can't close [cell] early."""
    parts = re.split(r'(\$.*?\$)', s)
    for i, tok in enumerate(parts):
        if not (tok.startswith('$') and tok.endswith('$') and len(tok) >= 2):
            tok = tok.replace('[', r'\[').replace(']', r'\]')
            parts[i] = tok
    return ''.join(parts)


def build_table_typst(rendered_grid):
    """Build ``#table(...)`` from already-rendered cell strings."""
    ncols = len(rendered_grid[0])
    flat = []
    for row in rendered_grid:
        for cell in row:
            flat.append(f'[{_escape_brackets_outside_math(cell)}]')
    return f'#table(columns: {ncols}, {", ".join(flat)})'


def build_matrix_math_inner(rendered_grid):
    """Build Typst ``mat(...)`` inner (no surrounding ``$``)."""
    rows = [', '.join(c if c.strip() else '0' for c in row) for row in rendered_grid]
    # Empty matrix cells have no sensible math value; '0' keeps Typst
    # compiling instead of aborting the whole PDF (tables use []).
    return f'mat({"; ".join(rows)})'


def join_block_lines(lines):
    """Join multiline *table/*matrix block lines into one inner string.

    Newlines act as row breaks too (``|`` still works): lines are
    joined with `` | `` and empty rows are dropped later by
    normalize_grid, so both styles below give two rows::

        Name ; Age
        Alice ; 20

        Name ; Age |
        Alice ; 20
    """
    return ' | '.join(l.strip() for l in lines)
