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
from compiler.diagnostics import KNOWN_COMMANDS
from compiler.statements import process_assignment_or_define
from compiler.state import CompileContext
from compiler.variables import replace_defines, replace_vars
from geometry.parsing import parse_draw_block
from . import builtins

IDENT = r'[A-Za-z_][A-Za-z0-9_]*'
VAR_TOKEN = re.compile(r'<([^<>]+)>')
CALC_OPEN = re.compile(r'calc\(')
CMD_CALL = re.compile(r'\*([A-Za-z][A-Za-z0-9_]*)\s*\(')
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
    for source in (cap.getvalue().splitlines(), out.splitlines()):
        for raw in source:
            m = re.match(r'(?://\s*)?\[(GeometryError|GeometryWarning)\]\s*(.*)', raw.strip())
            if not m:
                continue
            severity = 'error' if m.group(1) == 'GeometryError' else 'warning'
            message = m.group(2).strip() or m.group(1)
            key = (severity, message)
            if key in seen:
                continue
            seen.add(key)
            analysis.diagnostics.append(
                Diag(start_line, 0, anchor_end, severity, message)
            )


def analyze_text(text):
    """Analyze a document; never raises on malformed input."""
    analysis = Analysis()
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
    in_math = False
    math_start = 0
    math_start_char = 0

    with _quiet():
        for idx, code in enumerate(lines):
            s = code.strip()
            if not s:
                continue
            if s.startswith('```'):
                continue

            # *define(...) / define(...)
            if (s.startswith('*define(') or s.startswith('define(')) and s.endswith(')'):
                prefix_len = 8 if s.startswith('*define(') else 7
                inner = s[prefix_len:-1]
                before = _snapshot(ctx)
                process_assignment_or_define(ctx, 'define(' + inner + ')', line_no=idx + 1)
                _record_new(ctx, before, code, idx, analysis)
                continue

            # Single-line *draw(...)
            if s.startswith('*draw(') and s.endswith(')'):
                inner = s[6:-1]
                inner = replace_vars(ctx, inner)
                inner = replace_defines(ctx, inner)
                pos = code.index('*draw')
                analysis.definitions.append(Definition('draw', 'draw', idx, pos, pos + 5))
                _analyze_draw(inner, lines, idx, idx, analysis)
                continue

            # Single-line *f(...)
            if s.startswith('*f(') and s.endswith(')'):
                inner = s[3:-1].strip()
                if not (inner.startswith('frac(') or inner.startswith('root(')):
                    before = _snapshot(ctx)
                    process_assignment_or_define(ctx, inner, line_no=idx + 1)
                    _record_new(ctx, before, code, idx, analysis)
                    continue
            elif ((s.startswith('*(') and s.endswith(')') and len(s) > 3)
                  or (s.startswith('f(') and s.endswith(')') and len(s) > 3
                      and not s.startswith('frac('))):
                inner = s[2:-1].strip()
                if inner and not inner.startswith('*'):
                    if re.match(r'^<[^<>]+>\s*=', inner) or inner.startswith('define('):
                        before = _snapshot(ctx)
                        process_assignment_or_define(ctx, inner, line_no=idx + 1)
                        _record_new(ctx, before, code, idx, analysis)
                        continue
            if s in ('*(', '*f(', 'f(', '*draw('):
                in_f_block = True
                block_type = s
                block_content = []
                block_start = idx
                continue
            elif s == ')' and in_f_block:
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

            if in_f_block:
                block_content.append((idx, s))
                continue

            if re.match(r'^<[^<>]+>\s*=', s):
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
            unresolved = []
            seen_names = set()
            for m in VAR_TOKEN.finditer(substituted):
                name = m.group(1)
                if not re.fullmatch(rf'\s*{IDENT}\s*', name):
                    continue
                clean = name.strip()
                if clean in ctx.variables or clean in ctx.defines:
                    continue
                if clean not in seen_names:
                    seen_names.add(clean)
                    unresolved.append((name, clean))
            known = sorted(set(ctx.variables) | set(ctx.defines))
            for name, clean in unresolved:
                # Every source occurrence gets its own range (code.find
                # would collapse duplicates onto the first one).
                for occ in re.finditer(rf'<{re.escape(name)}>', check_code):
                    message = f'Undefined variable <{clean}>'
                    suggestion = difflib.get_close_matches(clean, known, n=1, cutoff=0.6)
                    if suggestion:
                        message += f". Did you mean '{suggestion[0]}'?"
                    analysis.diagnostics.append(Diag(
                        idx, occ.start(), occ.end(), 'error', message,
                    ))

            for m in CMD_CALL.finditer(check_code):
                if m.group(1) not in KNOWN_COMMANDS:
                    analysis.diagnostics.append(Diag(
                        idx, m.start(), m.end(), 'warning',
                        f"Unknown command *{m.group(1)}(...) — treated as plain text",
                    ))

            sub_all = replace_defines(ctx, substituted)
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
            'warning', "Unclosed block '(' — content may be silently consumed",
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


def complete(text, line, character):
    """Completion candidates at a cursor position (client filters by prefix)."""
    analysis = analyze_text(text)
    lines = text.splitlines()
    cur = lines[line] if 0 <= line < len(lines) else ''
    head = cur[:max(0, character)]
    star = bool(re.search(r'\*(?=[A-Za-z_][A-Za-z0-9_]*$)', head))

    items = []
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
    token = None
    for m in WORD_AT.finditer(cur):
        if m.start() <= character <= m.end():
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
