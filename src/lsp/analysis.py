"""Document analysis for the LSP, built on the existing compiler.

There is intentionally no second parser here.  Analysis mirrors the
compiler pipeline (`compiler/pipeline.py`) line classification and reuses:
  - `comments.strip_comments` for comment handling,
  - `CompileContext` + `statements.process_assignment_or_define` for the
    semantic state (definitions and their values),
  - `variables.replace_vars` / `replace_defines` for substitution,
  - `calc.apply_calc_in_string` for calc() validation,
  - `diagnostics.KNOWN_COMMANDS` (+ the same unknown-command rule) and
    `geometry.parse_draw_block` (geometry diagnostics) for diagnostics.

The only LSP-specific work is turning compiler results into positioned
diagnostics/symbols: the compiler is line-oriented, so line numbers map
1:1 and character offsets are found by scanning the source line.  Checks
run on the source text (pre-substitution) so reported ranges are exact;
substitution is applied to a copy only to decide resolvability.
"""

import contextlib
import difflib
import io
import re

from compiler.calc import apply_calc_in_string, evaluate_calc
from compiler.comments import strip_comments
from compiler.diagnostics import KNOWN_COMMANDS, KNOWN_GEOMETRY_COMMANDS
from compiler.statements import (
    _normalize_friendly_statement,
    process_assignment_or_define,
)
from compiler.state import CompileContext
from compiler import tables as _tables
from compiler.variables import replace_defines, replace_vars
from geometry.parsing import parse_draw_block
from . import builtins

IDENT = r'[A-Za-z_][A-Za-z0-9_]*'
VAR_TOKEN = re.compile(r'<([^<>]+)>')
CALC_OPEN = re.compile(r'(?<![A-Za-z0-9_])\*?calc\(')
CMD_CALL = re.compile(r'\*([A-Za-z][A-Za-z0-9_\-]*)\s*\(')
P_LINE = re.compile(r'^\*p\((.*)\)$')
WORD_AT = re.compile(IDENT)


class Diag:
    """A diagnostic with 0-based line/character positions."""

    def __init__(self, line, start, end, severity, message):
        self.line = line
        self.start = start
        self.end = end
        self.severity = severity  # 'error' | 'warning'
        self.message = message

    def __repr__(self):
        return f'Diag({self.line}:{self.start}-{self.end} {self.severity} {self.message!r})'


class Definition:
    """A named declaration: define, variable or draw block."""

    def __init__(self, name, kind, line, start, end, value=None):
        self.name = name
        self.kind = kind  # 'define' | 'variable' | 'draw'
        self.line = line
        self.start = start
        self.end = end
        self.value = value

    def __repr__(self):
        return f'Definition({self.name!r} {self.kind} @{self.line})'


class Analysis:
    def __init__(self):
        self.diagnostics = []
        self.definitions = []
        self.values = {}  # name -> (kind, value, def_line)


@contextlib.contextmanager
def _quiet():
    """Suppress compiler stderr chatter; diagnostics are derived by us."""
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        yield buf


def _balanced_range(text, open_index):
    """End index (exclusive) of the ')' matching text[open_index] == '('.

    Returns None when unbalanced (syntax error).
    """
    depth = 0
    for i in range(open_index, len(text)):
        if text[i] == '(':
            depth += 1
        elif text[i] == ')':
            depth -= 1
            if depth == 0:
                return i + 1
    return None


def _mask_p_segments(code):
    """Replace balanced *p(...) spans with spaces (preserving offsets).

    Raw *p content bypasses all checks, like the compiler. Unclosed
    *p( is left intact so later checks can still flag it.
    """
    chars = list(code)
    pos = 0
    pat = re.compile(r'\*p\(')
    while True:
        m = pat.search(code, pos)
        if not m:
            break
        close = _balanced_range(code, m.end() - 1)
        if close is None:
            break
        for i in range(m.start(), close):
            chars[i] = ' '
        pos = close
    return ''.join(chars)


def _unescaped_bs_positions(s):
    """Offsets of unescaped ``\\`` in *s* (``\\\\`` ignored)."""
    out = []
    i, n = 0, len(s)
    while i < n:
        if s[i] == '\\':
            if i + 1 < n and s[i + 1] == '\\':
                i += 2
                continue
            out.append(i)
        i += 1
    return out


def _record_new(ctx, before, stmt_text, line_no, analysis):
    """Record names defined by one processed statement."""
    new_vars = set(ctx.variables) - before[0]
    new_defs = set(ctx.defines) - before[1]
    for name in sorted(new_vars | new_defs):
        kind = 'define' if name in ctx.defines else 'variable'
        value = ctx.variables.get(name)
        m = re.search(rf'<{re.escape(name)}>', stmt_text)
        if m is None:
            m = re.search(rf'\b{re.escape(name)}\b', stmt_text)
        start, end = (m.start(), m.end()) if m else (0, len(stmt_text))
        analysis.definitions.append(
            Definition(name, kind, line_no, start, end,
                       value=None if value is None else str(value))
        )


def _snapshot(ctx):
    return set(ctx.variables), set(ctx.defines)


def _analyze_draw(block_text, lines, start_line, end_line, analysis):
    """Geometry diagnostics for one draw block (compiler output reused)."""
    with _quiet() as cap:
        out = parse_draw_block(block_text)
    seen = set()
    anchor_end = len(lines[start_line]) if start_line < len(lines) else 0
    # Single-line anchor on the block opener (Diag is single-line);
    # the message names the failing command for precise location.
    for source in (cap.getvalue().splitlines(), out.splitlines()):
        for raw in source:
            m = re.match(r'(?://\s*)?\[(GeometryError|GeometryWarning)\]\s*(.*)', raw.strip())
            if not m:
                continue
            severity = 'error' if m.group(1) == 'GeometryError' else 'warning'
            message = m.group(2).strip() or m.group(1)
            key = (severity, message, start_line, end_line)
            if key in seen:
                continue
            seen.add(key)
            analysis.diagnostics.append(
                Diag(start_line, 0, anchor_end, severity, message)
            )


def _table_shape_message(inner, kind):
    """Return a warning string when a table/matrix grid is ragged/empty."""
    try:
        grid = _tables.parse_grid(inner)
    except Exception:
        return None
    kept = [r for r in grid if any(c.strip() for c in r)]
    if not kept:
        return f'*{kind}(...) is empty'
    widths = sorted({len(r) for r in kept})
    if len(widths) != 1:
        return (
            f'*{kind}(...) rows have different lengths '
            f'{sorted(len(r) for r in kept)} — short rows are padded'
        )
    return None


def _validate_table_calls(line_text, idx, analysis, *, in_math_pairs):
    """Emit shape warnings for single-line *table/*matrix calls."""
    pos = 0
    while True:
        try:
            found = _tables.find_next_call(line_text, pos)
        except Exception:
            return
        if not found:
            return
        if found[0] == 'unclosed':
            _, name, call_start, inner_start, _, _ = found
            analysis.diagnostics.append(Diag(
                idx, call_start, inner_start, 'warning',
                f'Unclosed *{name}(... — missing closing parenthesis',
            ))
            pos = inner_start
            continue
        name, call_start, _s, call_end, inner_raw = found
        if name == 'table' and in_math_pairs:
            # Tables are text mode; the compiler warns too.
            analysis.diagnostics.append(Diag(
                idx, call_start, call_end, 'warning',
                '*table(...) cannot be used inside math \\ ... \\',
            ))
            pos = call_end
            continue
        msg = _table_shape_message(inner_raw, name)
        if msg:
            analysis.diagnostics.append(Diag(
                idx, call_start, call_end, 'warning', msg,
            ))
        pos = call_end


def _validate_table_block(block_type, block_content, lines,
                           start_line, end_line, analysis):
    """Shape diagnostics for a multiline *table/*matrix/*mat block."""
    kind = block_type[1:-1]
    joined = _tables.join_block_lines(
        [stmt for _, stmt in block_content]
    )
    msg = _table_shape_message(joined, kind)
    anchor_end = len(lines[start_line]) if start_line < len(lines) else 0
    if msg:
        analysis.diagnostics.append(
            Diag(start_line, 0, anchor_end, 'warning', msg)
        )


def analyze_text(text):
    """Analyze a document; never raises on malformed input."""
    analysis = Analysis()
    try:
        if not isinstance(text, str):
            analysis.diagnostics.append(
                Diag(0, 0, 0, 'error', 'Invalid document text')
            )
            return analysis
        return _analyze_text_inner(text, analysis)
    except Exception as e:
        try:
            analysis.diagnostics.append(
                Diag(0, 0, 0, 'error', f'Analysis failed: {e}')
            )
        except Exception:
            pass
        return analysis


def _analyze_text_inner(text, analysis):
    ctx = CompileContext()
    raw_lines = text.splitlines()
    lines = strip_comments(text).splitlines()
    # strip_comments preserves line count, but be defensive.
    while len(lines) < len(raw_lines):
        lines.append('')

    in_f_block = False
    block_type = None
    block_content = []
    block_start = 0
    in_table_block = False
    table_type = None
    table_content = []
    table_start = 0
    in_math = False
    math_start = 0
    math_start_char = 0

    with _quiet():
        in_fence = False
        for idx, code in enumerate(lines):
            s = code.strip()
            if not s:
                continue
            if s.startswith('```'):
                in_fence = not in_fence
                continue
            if in_fence:
                continue

            # Control lines suspended while multiline math is open
            # (mirrors compiler/pipeline.py: tail after the closer is
            # still processed as normal text). Buffered math lines still
            # get text checks below (undefined vars/calc), matching the
            # compiler which validates the joined math body.
            math_buffered = False
            if in_math:
                masked = _mask_p_segments(code)
                _bs_close = _unescaped_bs_positions(masked)
                if not _bs_close:
                    math_buffered = True
                else:
                    # Mirror the compiler (compiler/pipeline.py): the first
                    # unescaped backslash closes multiline math; the tail
                    # after it is normal text (it may open new math pairs,
                    # handled by the single-line tracking below).
                    in_math = False
                    first = _bs_close[0]
                    code = code[first + 1:]
                    s = code.strip()
                    if not s:
                        continue

            # *define(...) / define(...) — suspended inside math buffer.
            # Space-tolerant like the compiler
            # (pipeline.py accepts '*define (x = 1)').
            _m_def = re.match(r'^(\*?define)\s*\((.*)\)\s*$', s)
            if not math_buffered and _m_def and _m_def.group(2) is not None:
                prefix_len = len(_m_def.group(1)) + 1  # name + '('
                inner = s[_m_def.start(2):_m_def.end(2)]
                before = _snapshot(ctx)
                process_assignment_or_define(ctx, 'define(' + inner + ')', line_no=idx + 1)
                _record_new(ctx, before, code, idx, analysis)
                continue

            # Friendly: let/var and bare *define without parens.
            if not math_buffered:
                _norm = _normalize_friendly_statement(s)
                if _norm != s and (
                    _norm.startswith('define(')
                    or re.match(r'^<[^<>]+>\s*=', _norm)
                ):
                    before = _snapshot(ctx)
                    process_assignment_or_define(ctx, _norm, line_no=idx + 1)
                    _record_new(ctx, before, code, idx, analysis)
                    continue

            # Single-line *draw(...) — suspended inside math buffer.
            if not math_buffered and s.startswith('*draw(') and s.endswith(')'):
                inner = s[6:-1]
                inner = replace_vars(ctx, inner)
                inner = replace_defines(ctx, inner)
                inner = apply_calc_in_string(ctx, inner)
                pos = code.index('*draw')
                analysis.definitions.append(Definition('draw', 'draw', idx, pos, pos + 5))
                if '[Calc Error' in inner:
                    analysis.diagnostics.append(Diag(
                        idx, pos, pos + 5, 'error', inner[inner.index('[Calc Error'):inner.index('[Calc Error') + 120],
                    ))
                _analyze_draw(inner, lines, idx, idx, analysis)
                continue

            # Single-line *f(...) — suspended inside math buffer.
            if not math_buffered and s.startswith('*f(') and s.endswith(')'):
                inner = s[3:-1].strip()
                if not (inner.startswith('frac(') or inner.startswith('root(')):
                    before = _snapshot(ctx)
                    process_assignment_or_define(ctx, inner, line_no=idx + 1)
                    _record_new(ctx, before, code, idx, analysis)
                    continue
            elif not math_buffered and ((s.startswith('*(') and s.endswith(')') and len(s) > 3)
                  or (s.startswith('f(') and s.endswith(')') and len(s) > 3
                      and not s.startswith('frac('))):
                inner = s[2:-1].strip()
                if inner and not inner.startswith('*'):
                    _inner_norm = _normalize_friendly_statement(inner)
                    if (re.match(r'^<[^<>]+>\s*=', inner)
                            or inner.startswith('define(')
                            or _inner_norm != inner):
                        before = _snapshot(ctx)
                        process_assignment_or_define(ctx, inner, line_no=idx + 1)
                        _record_new(ctx, before, code, idx, analysis)
                        continue
            if not math_buffered and s in ('*(', '*f(', 'f(', '*draw('):
                in_f_block = True
                block_type = s
                block_content = []
                block_start = idx
                continue
            elif not math_buffered and s == ')' and in_f_block:
                if block_type == '*draw(':
                    pos = lines[block_start].index('*draw')
                    analysis.definitions.append(
                        Definition('draw', 'draw', block_start, pos, pos + 5)
                    )
                    _analyze_draw(
                        '\n'.join(stmt for _, stmt in block_content),
                        lines, block_start, idx, analysis,
                    )
                else:
                    for stmt_idx, stmt in block_content:
                        before = _snapshot(ctx)
                        process_assignment_or_define(ctx, stmt, line_no=stmt_idx + 1)
                        _record_new(ctx, before, lines[stmt_idx], stmt_idx, analysis)
                in_f_block = False
                continue

            # Multiline *table/*matrix/*mat blocks: buffer rows for shape
            # validation, but inner lines still get normal text checks
            # below (variables/calc inside cells must resolve).
            if not math_buffered and not in_f_block and s in (
                '*table(', '*matrix(', '*mat(',
            ):
                in_table_block = True
                table_type = s
                table_content = []
                table_start = idx
                continue
            if not math_buffered and s == ')' and in_table_block:
                _validate_table_block(
                    table_type, table_content, lines,
                    table_start, idx, analysis,
                )
                in_table_block = False
                table_type = None
                table_content = []
                continue

            if in_f_block and not math_buffered:
                block_content.append((idx, s))
                continue
            if in_table_block and not math_buffered:
                table_content.append((idx, s))
                # Fall through to text checks so cell contents validate.
                # Assignments are NOT processed here (mirrors the compiler:
                # table blocks hold rows, not definitions).

            if not math_buffered and not in_table_block and re.match(r'^<[^<>]+>\s*=', s):
                before = _snapshot(ctx)
                process_assignment_or_define(ctx, s, line_no=idx + 1)
                _record_new(ctx, before, code, idx, analysis)
                continue

            # --- Text line checks (positions refer to the source line) ---
            # *p(...) raw spans are masked so their contents bypass checks.
            check_code = _mask_p_segments(code)
            if check_code.strip() == '':
                continue

            # --- Inline math state (mirrors compiler toggle semantics) ---
            # Checks below still run on math contents (variables/calc are
            # valid inside math); this only tracks unclosed delimiters.
            bs = _unescaped_bs_positions(check_code)
            if in_math:
                if len(bs) % 2 == 1:
                    in_math = False
            else:
                if len(bs) % 2 == 1:
                    in_math = True
                    math_start = idx
                    math_start_char = bs[-1]
            # Warn on empty \ \ pairs on this line.
            tmp = check_code
            while True:
                o = _unescaped_bs_positions(tmp)
                if len(o) < 2:
                    break
                inner = tmp[o[0] + 1:o[1]]
                if inner.strip() == '':
                    analysis.diagnostics.append(Diag(
                        idx, o[0], o[1] + 1, 'warning',
                        'Empty math expression \\ \\.',
                    ))
                    tmp = tmp[:o[0]] + ' ' * (o[1] + 1 - o[0]) + tmp[o[1] + 1:]
                else:
                    tmp = tmp[:o[0]] + ' ' * (o[1] + 1 - o[0]) + tmp[o[1] + 1:]

            substituted = replace_vars(ctx, check_code)
            known = sorted(set(ctx.variables) | set(ctx.defines))
            # Flag every undefined <name> occurrence in source offsets
            # (spacing variants like <oops> vs < oops > are distinct).
            for occ in VAR_TOKEN.finditer(check_code):
                raw_name = occ.group(1)
                if not re.fullmatch(rf'\s*{IDENT}\s*', raw_name):
                    continue
                # Mirror the compiler's << >> guard on the substituted
                # text is approximations; use source adjacency here.
                if occ.start() > 0 and check_code[occ.start() - 1] == '<':
                    continue
                if occ.end() < len(check_code) and check_code[occ.end()] == '>':
                    continue
                clean = raw_name.strip()
                # Resolvability check on substituted values.
                if clean in ctx.variables or clean in ctx.defines:
                    continue
                # Also skip if substitution already resolved it
                # (e.g. defined later on the same line is not supported;
                # keep simple: undefined means not in ctx).
                message = f'Undefined variable <{clean}>'
                suggestion = difflib.get_close_matches(clean, known, n=1, cutoff=0.6)
                if suggestion:
                    message += f". Did you mean '{suggestion[0]}'?"
                analysis.diagnostics.append(Diag(
                    idx, occ.start(), occ.end(), 'error', message,
                ))

            # Mask single-line math pairs so commands inside math don't
            # warn (mirrors compiler placeholders before warn_unknown).
            _math_masked = check_code
            while True:
                _o = _unescaped_bs_positions(_math_masked)
                if len(_o) < 2:
                    break
                _math_masked = (
                    _math_masked[:_o[0]] + ' ' * (_o[1] + 1 - _o[0]) + _math_masked[_o[1] + 1:]
                )
            for m in CMD_CALL.finditer(_math_masked):
                cmd = m.group(1)
                if cmd in KNOWN_COMMANDS:
                    continue
                if cmd in KNOWN_GEOMETRY_COMMANDS or cmd.replace('_', '-') in KNOWN_GEOMETRY_COMMANDS:
                    analysis.diagnostics.append(Diag(
                        idx, m.start(), m.end(), 'warning',
                        f"*{cmd}(...) is only valid inside *draw(...) — treated as plain text",
                    ))
                    continue
                analysis.diagnostics.append(Diag(
                    idx, m.start(), m.end(), 'warning',
                    f"Unknown command *{cmd}(...) — treated as plain text",
                ))

            # Table/matrix shape checks (text mode). Matrices also work
            # inside \ ... \ math, so validate them on the unmasked line;
            # tables inside math get their own warning.
            _validate_table_calls(
                _math_masked, idx, analysis, in_math_pairs=False,
            )
            if _math_masked != check_code:
                # Only the insides of \ ... \ pairs (offsets preserved):
                # tables are invalid there, matrices get shape checks.
                _starts = _unescaped_bs_positions(check_code)
                _chars = list(check_code)
                _in_pair = [False] * len(_chars)
                for _k in range(0, len(_starts) - 1, 2):
                    for _j in range(_starts[_k], _starts[_k + 1] + 1):
                        _in_pair[_j] = True
                _math_only = ''.join(
                    c if _in_pair[_j] else ' '
                    for _j, c in enumerate(_chars)
                )
                _validate_table_calls(
                    _math_only, idx, analysis, in_math_pairs=True,
                )

            for m in CALC_OPEN.finditer(check_code):
                close = _balanced_range(check_code, m.end() - 1)
                if close is None:
                    analysis.diagnostics.append(Diag(
                        idx, m.start(), len(check_code), 'error',
                        'Unclosed parenthesis in calc(...)',
                    ))
                    continue
                # Evaluate the expression extracted from the source line
                # directly (evaluate_calc re-applies var/define
                # substitution). Slicing sub_all with source offsets is
                # wrong when earlier substitutions changed the length.
                expr = check_code[m.end():close - 1]
                res = evaluate_calc(ctx, expr)
                if res.startswith('[Calc Error'):
                    analysis.diagnostics.append(Diag(
                        idx, m.start(), close, 'error', res,
                    ))

    if in_math:
        analysis.diagnostics.append(Diag(
            math_start, math_start_char,
            len(lines[math_start]) if math_start < len(lines) else math_start_char + 1,
            'error', 'Unclosed math delimiter \\ ... \\ — missing closing \\.',
        ))

    if in_f_block:
        analysis.diagnostics.append(Diag(
            block_start, 0,
            len(lines[block_start]) if block_start < len(lines) else 0,
            'error', "Unclosed block '(' — content may be silently consumed",
        ))

    if in_table_block:
        analysis.diagnostics.append(Diag(
            table_start, 0,
            len(lines[table_start]) if table_start < len(lines) else 0,
            'error', "Unclosed block '(' — content may be silently consumed",
        ))

    for d in analysis.definitions:
        kind, value = d.kind, d.value
        if value is not None and '<' in value:
            with _quiet():
                resolved = replace_vars(ctx, value)
            if '<' not in resolved:
                value = resolved
        analysis.values[d.name] = (kind, value, d.line)
    return analysis


def _in_p_span(line_text, character):
    """True when the cursor offset lies inside a balanced *p(...) span."""
    pat = re.compile(r'\*p\(')
    pos = 0
    while True:
        m = pat.search(line_text, pos)
        if not m:
            return False
        close = _balanced_range(line_text, m.end() - 1)
        if close is None:
            return False
        if m.start() <= character < close:
            return True
        pos = close


def complete(text, line, character):
    """Completion candidates at a cursor position (client filters by prefix)."""
    analysis = analyze_text(text)
    lines = text.splitlines()
    cur = lines[line] if 0 <= line < len(lines) else ''
    # Inside *p(...) raw spans the compiler ignores variables; suppress
    # variable/define items there (keep symbol/function help).
    in_p = _in_p_span(cur, max(0, character))
    head = cur[:max(0, character)]
    star = bool(re.search(r'\*(?=[A-Za-z_][A-Za-z0-9_]*$)', head))

    items = []
    if not in_p:
        for name, (kind, value, _def_line) in sorted(analysis.values.items()):
            items.append({
                'label': name,
                'kind': 'variable' if kind == 'variable' else 'constant',
                'detail': f'= {value}' if value else kind,
            })
    for name in sorted(builtins.MATH_DOCS):
        sig, _desc = builtins.MATH_DOCS[name]
        items.append({'label': name, 'kind': 'function', 'detail': sig})
    for name in sorted(builtins.KEYWORD_DOCS):
        sig, _desc = builtins.KEYWORD_DOCS[name]
        items.append({'label': name, 'kind': 'keyword', 'detail': sig})
    for name in sorted(builtins.GEOMETRY_DOCS):
        sig, _desc = builtins.GEOMETRY_DOCS[name]
        items.append({'label': name, 'kind': 'function', 'detail': f'geometry: {sig}'})
    if not in_p and 'draw' not in builtins.GEOMETRY_DOCS:
        # *draw(...) is the geometry wrapper itself (not an inner solver
        # command, so it stays out of GEOMETRY_DOCS on purpose); suggest
        # it explicitly so typing *dr completes.
        items.append({'label': 'draw', 'kind': 'function',
                      'detail': 'geometry: *draw(...)'})
    if star:
        for word, glyph in builtins.symbol_entries():
            items.append({
                'label': f'*{word}', 'kind': 'keyword',
                'detail': f'symbol {glyph}',
            })
    return items


def hover(text, line, character):
    """Hover info for the identifier under the cursor, or None."""
    analysis = analyze_text(text)
    lines = text.splitlines()
    if not (0 <= line < len(lines)):
        return None
    cur = lines[line]
    if _in_p_span(cur, character):
        # Raw passthrough: the compiler treats contents literally.
        return None
    token = None
    for m in WORD_AT.finditer(cur):
        if m.start() <= character < m.end():
            token = m
            break
    if token is None:
        return None
    name = token.group(0)
    if name in analysis.values:
        kind, value, def_line = analysis.values[name]
        shown_kind = 'Define' if kind == 'define' else 'Variable'
        body = f'**{name}**\n\n{shown_kind}'
        if value:
            body += f'\n\nValue: {value}'
        body += f'\n\nDefined at line {def_line + 1}'
        return {'value': body, 'start': token.start(), 'end': token.end()}
    if name in builtins.MATH_DOCS:
        sig, desc = builtins.MATH_DOCS[name]
        return {'value': f'**{name}**\n\nFunction\n\n{sig}\n\n{desc}',
                'start': token.start(), 'end': token.end()}
    if name in builtins.KEYWORD_DOCS:
        sig, desc = builtins.KEYWORD_DOCS[name]
        return {'value': f'**{name}**\n\nKeyword\n\n{sig}\n\n{desc}',
                'start': token.start(), 'end': token.end()}
    if name in builtins.GEOMETRY_DOCS:
        sig, desc = builtins.GEOMETRY_DOCS[name]
        return {'value': f'**{name}**\n\nGeometry command\n\n{sig}\n\n{desc}',
                'start': token.start(), 'end': token.end()}
    for word, glyph in builtins.symbol_entries():
        if name == word:
            return {'value': f'**{name}**\n\nSymbol\n\n`*{word}` → {glyph}',
                    'start': token.start(), 'end': token.end()}
    return None


def document_symbols(text):
    """Flat (name, kind, line, start, end) symbols for the document."""
    return [
        (d.name, d.kind, d.line, d.start, d.end)
        for d in analyze_text(text).definitions
    ]
