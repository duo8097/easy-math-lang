"""Document pipeline: line loop, text phases, Typst generation."""

import os
import re
import sys

# The `typst` PDF backend is imported lazily by _require_typst() on first
# export so processes that never compile (editor startup, LSP-only runs)
# don't pay for the native extension up front. Tests monkeypatch the
# `typst` module attribute below with a stub, which keeps working because
# _require_typst() returns any non-None value as-is.
typst = None
_typst_import_failed = False


def _require_typst():
    """Return the `typst` backend module, importing it on first use."""
    global typst, _typst_import_failed
    if typst is not None or _typst_import_failed:
        return typst
    try:
        import typst as _backend
    except ImportError:
        _typst_import_failed = True
        return None
    typst = _backend
    return typst

from .calc import apply_calc_in_string
from .comments import strip_comments
from .diagnostics import warn_unknown_commands
from .escaping import escape_typst_outside_math, index_replacer, merge_math
from .inline_math import find_unescaped, process_math_inner
from .math_commands import (
    clean_inner_math,
    math_call_specs,
    normalize_friendly_calls,
    replace_math_call,
    split_top_level_args,
)
from .statements import _normalize_friendly_statement, process_assignment_or_define
from .source_links import link_prefix as _source_link_prefix
from .source_map import SourcePosition, SourceSpan, TypstSourceMap, default_map_path
from .state import CompileContext
from .symbols import replace_symbol_shortcuts
from .variables import check_undefined_vars, replace_defines, replace_vars
from . import tables as _tables
from . import plots as _plots


def _extract_p_segments(text):
    """Split text into (is_raw, content) segments for balanced *p(...).

    Finds every ``*p(`` with depth-aware paren matching. Unclosed
    ``*p(`` is left as normal text so later passes can warn.
    """
    segs = []
    pos = 0
    pat = re.compile(r'\*p\(')
    while True:
        m = pat.search(text, pos)
        if not m:
            segs.append((False, text[pos:]))
            break
        if m.start() > pos:
            segs.append((False, text[pos:m.start()]))
        start = m.end()
        depth = 1
        i = start
        while i < len(text) and depth > 0:
            if text[i] == '(':
                depth += 1
            elif text[i] == ')':
                depth -= 1
            i += 1
        if depth != 0:
            segs.append((False, text[m.start():]))
            break
        segs.append((True, text[start:i - 1]))
        pos = i
    return segs


def _first_unescaped_bs(text):
    """Index of first unescaped ``\\`` (``\\\\`` ignored), or None."""
    i, n = 0, len(text)
    while i < n:
        if text[i] == '\\':
            if i + 1 < n and text[i + 1] == '\\':
                i += 2
                continue
            return i
        i += 1
    return None


def _detection_text(raw):
    """Copy of *raw* with ``*p(...)`` raw spans blanked (length-preserved).

    Used only to locate math delimiters so a backslash inside ``*p()``
    never toggles math mode. Offsets match the original string.
    """
    chars = list(raw)
    pos = 0
    pat = re.compile(r'\*p\(')
    while True:
        m = pat.search(raw, pos)
        if not m:
            break
        depth = 1
        i = m.end()
        while i < len(raw) and depth > 0:
            if raw[i] == '(':
                depth += 1
            elif raw[i] == ')':
                depth -= 1
            i += 1
        if depth != 0:
            break
        for j in range(m.start(), i):
            chars[j] = ' '
        pos = i
    return ''.join(chars)


def _expand_tables_and_matrices(ctx, text, line_no, depth):
    """Expand *table/*matrix/*mat calls to Typst, protected by placeholders.

    Runs AFTER vars/calc/inline-math (like math commands) so variables
    holding tables still expand; per-cell rendering re-applies the full
    pipeline (tables) or math cleaning (matrices) so variables inside
    cells work too. Returns (new_text, {placeholder: typst}).
    """
    placeholders = {}
    idx = 0
    pos = 0
    out = []
    while True:
        found = _tables.find_next_call(text, pos)
        if not found:
            out.append(text[pos:])
            break
        if found[0] == 'unclosed':
            _, name, call_start, inner_start, _, _ = found
            print(
                f'[Warning] Line {line_no}: unclosed *{name}(... — '
                f'missing closing parenthesis',
                file=sys.stderr,
            )
            out.append(text[pos:inner_start])
            pos = inner_start
            continue
        name, call_start, _inner_start, call_end, inner_raw = found
        out.append(text[pos:call_start])
        if _tables.is_table_call(name):
            grid_raw = _tables.parse_grid(inner_raw)
            norm = _tables.normalize_grid(grid_raw, line_no, 'table')
            if norm is None:
                out.append(text[call_start:call_end])
                pos = call_end
                continue
            rendered = []
            for row in norm:
                r_out = []
                for cell_raw in row:
                    if not cell_raw.strip():
                        r_out.append('')
                        continue
                    # Full text pipeline per cell (nested tables OK).
                    r_out.append(
                        _render_text_line(
                            ctx, cell_raw, line_no, _table_depth=depth + 1
                        )
                    )
                rendered.append(r_out)
            typ = _tables.build_table_typst(rendered)
            ph = f'\x07{idx}\x07'
            idx += 1
            placeholders[ph] = typ
            out.append(ph)
            pos = call_end
        else:
            grid_raw = _tables.parse_grid(inner_raw)
            norm = _tables.normalize_grid(grid_raw, line_no, 'matrix')
            if norm is None:
                out.append(text[call_start:call_end])
                pos = call_end
                continue
            rendered = []
            for row in norm:
                r_out = []
                for cell_raw in row:
                    if not cell_raw.strip():
                        r_out.append('')
                        continue
                    if re.search(r'\*(table|matrix|mat)\s*\(', cell_raw):
                        print(
                            f'[Warning] Line {line_no}: *{name}(...) cell '
                            f'contains a nested table/matrix — only math '
                            f'commands are supported inside matrices',
                            file=sys.stderr,
                        )
                    r_out.append(clean_inner_math(ctx, cell_raw))
                rendered.append(r_out)
            typ = f'${_tables.build_matrix_math_inner(rendered)}$'
            ph = f'\x07{idx}\x07'
            idx += 1
            placeholders[ph] = typ
            out.append(ph)
            pos = call_end
    return ''.join(out), placeholders


def _expand_plots(ctx, text, line_no):
    """Expand ``*plot(expression ; xmin ; xmax)`` to ``#image(...)``.

    Each plot is rendered to ``<stem>-plot-<n>.svg`` next to the
    intermediate ``.typ`` file (see ``ctx.plot_dir``/``ctx.plot_stem``)
    and referenced by basename so the Typst build stays relocatable.
    Failures never abort the build: a ``[Plot Error: ...]`` literal is
    emitted and reported on stderr, mirroring ``calc()`` error UX.
    Returns (new_text, {placeholder: typst}).
    """
    placeholders = {}
    idx = 0
    pos = 0
    out = []
    while True:
        found = _plots.find_next_plot_call(text, pos)
        if not found:
            out.append(text[pos:])
            break
        if found[0] == 'unclosed':
            _, call_start, inner_start, _, _ = found
            print(
                f'[Warning] Line {line_no}: unclosed *plot(... — '
                f'missing closing parenthesis',
                file=sys.stderr,
            )
            out.append(text[pos:inner_start])
            pos = inner_start
            continue
        _call_start, _inner_start, call_end, inner_raw = found
        out.append(text[pos:_call_start])
        args = split_top_level_args(inner_raw)
        err = None
        if len(args) != 3:
            err = (f'*plot(...) needs 3 arguments: expression ; xmin ; xmax '
                   f'(got {len(args)})')
        elif not args[0].strip():
            err = '*plot(...) needs an expression to plot'
        elif not args[1].strip() or not args[2].strip():
            err = '*plot(...) needs xmin and xmax bounds'
        if err is None:
            try:
                xmin = _plots.evaluate_bound(ctx, args[1])
                xmax = _plots.evaluate_bound(ctx, args[2])
            except ValueError as e:
                err = f'*plot(...) invalid bounds: {e}'
                xmin = xmax = None
            else:
                if xmin >= xmax:
                    err = (f'*plot(...) needs xmin < xmax '
                           f'(got {xmin} >= {xmax})')
        if err is not None:
            print(f'[Error] Line {line_no}: {err}', file=sys.stderr)
            out.append(f'[Plot Error: {err}]')
            pos = call_end
            continue
        ctx.plot_index = int(getattr(ctx, 'plot_index', 0) or 0) + 1
        plot_dir = getattr(ctx, 'plot_dir', None) or os.getcwd()
        plot_stem = getattr(ctx, 'plot_stem', None) or 'doc'
        fname = _plots.plot_filename(plot_stem, ctx.plot_index)
        fpath = os.path.join(plot_dir, fname)
        try:
            _plots.render_plot_svg(ctx, args[0], xmin, xmax, fpath)
        except ValueError as e:
            print(f'[Error] Line {line_no}: *plot(...) {e}',
                  file=sys.stderr)
            out.append(f'[Plot Error: {e}]')
            pos = call_end
            continue
        except Exception as e:
            print(f'[Error] Line {line_no}: *plot(...) failed: {e}',
                  file=sys.stderr)
            out.append(f'[Plot Error: {e}]')
            pos = call_end
            continue
        ph = f'\x06{idx}\x06'
        idx += 1
        placeholders[ph] = f'#image("{fname}", width: 80%)'
        out.append(ph)
        pos = call_end
    return ''.join(out), placeholders


DOC_TITLE_NAMES = ('doc_title', 'doc-title', 'doctitle', 'title')

_DOC_TITLE_OPEN_RE = re.compile(r'^\*(doc_title|doc-title|doctitle|title)\s*\(')


def _match_doc_title(line):
    """Match a top-level ``*doc_title(...)`` control line.

    Returns None when *line* is not a doc-title opener, otherwise
    ('ok', name, inner_raw) or ('unclosed', name). The whole line must
    be a single call (trailing whitespace allowed) so titles containing
    parentheses still parse via depth-aware matching.
    """
    m = _DOC_TITLE_OPEN_RE.match(line)
    if not m:
        return None
    name = m.group(1)
    open_paren = m.end() - 1
    depth = 0
    in_quote = False
    for i in range(open_paren, len(line)):
        ch = line[i]
        if ch == '"' and (i == 0 or line[i - 1] != '\\'):
            in_quote = not in_quote
            continue
        if in_quote:
            continue
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                inner_raw = line[open_paren + 1:i]
                tail = line[i + 1:].strip()
                if tail:
                    return None
                return ('ok', name, inner_raw)
    return ('unclosed', name)


def _doc_title_plain(ctx, raw):
    """Plain-text title for ``#set document(title: ...)`` metadata.

    Expands variables/defines/calc and symbol shortcuts so the PDF
    properties show readable text (``*alpha`` -> ``α``), then strips
    Typst math wrappers. Falls back to the default title when empty.
    """
    from .symbols import replace_symbol_shortcuts

    s = replace_vars(ctx, raw)
    s = replace_defines(ctx, s)
    s = apply_calc_in_string(ctx, s)
    s = replace_symbol_shortcuts(s)
    s = s.replace('$', '').strip()
    s = re.sub(r'\s+', ' ', s)
    return s or 'Easy Math Document'


def _escape_doc_title_brackets(rendered):
    """Escape ``[``/``]`` outside ``$...$`` so a title stays inside ``[...]``."""
    parts = re.split(r'(\$.*?\$)', rendered)
    for i, tok in enumerate(parts):
        if not (tok.startswith('$') and tok.endswith('$') and len(tok) >= 2):
            parts[i] = tok.replace('[', r'\[').replace(']', r'\]')
    return ''.join(parts)


DOC_FONT_NAMES = ('doc_font', 'doc-font', 'docfont')

_DOC_FONT_OPEN_RE = re.compile(r'^\*(doc_font|doc-font|docfont)\s*\(')

_DOC_FONT_FAMILY_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9 _\-]*$')
_DOC_FONT_SIZE_RE = re.compile(r'^(\d+(?:\.\d+)?)\s*(pt|mm|cm|in|em)?$')

DEFAULT_DOC_FONT_SIZE = '12pt'


def _match_doc_font(line):
    """Match a top-level ``*doc_font(...)`` control line.

    Returns None when *line* is not a doc-font opener, otherwise
    ('ok', name, inner_raw) or ('unclosed', name). Same depth-aware
    matching as :func:`_match_doc_title`.
    """
    m = _DOC_FONT_OPEN_RE.match(line)
    if not m:
        return None
    name = m.group(1)
    open_paren = m.end() - 1
    depth = 0
    in_quote = False
    for i in range(open_paren, len(line)):
        ch = line[i]
        if ch == '"' and (i == 0 or line[i - 1] != '\\'):
            in_quote = not in_quote
            continue
        if in_quote:
            continue
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                inner_raw = line[open_paren + 1:i]
                tail = line[i + 1:].strip()
                if tail:
                    return None
                return ('ok', name, inner_raw)
    return ('unclosed', name)


def _parse_doc_font(inner_raw):
    """Split ``family [; size]`` into (family, size) or (None, error).

    Only a top-level ``;`` separates the arguments so commas inside
    family names (e.g. ``DejaVu Sans``) survive. Size defaults to
    :data:`DEFAULT_DOC_FONT_SIZE`; a bare number means points.
    """
    depth = 0
    in_quote = False
    for i, ch in enumerate(inner_raw):
        if ch == '"' and (i == 0 or inner_raw[i - 1] != '\\'):
            in_quote = not in_quote
        elif not in_quote:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth = max(0, depth - 1)
            elif ch == ';' and depth == 0:
                return inner_raw[:i].strip(), inner_raw[i + 1:].strip()
    return inner_raw.strip(), ''


def _valid_doc_font_family(family):
    """A Typst-safe font family name, or None when invalid."""
    text = (family or '').strip().strip('"')
    if _DOC_FONT_FAMILY_RE.match(text):
        return re.sub(r'\s+', ' ', text)
    return None


def _valid_doc_font_size(size):
    """A Typst length like ``12pt`` (bare numbers mean points), or None."""
    m = _DOC_FONT_SIZE_RE.match((size or '').strip())
    if not m:
        return None
    number, unit = m.group(1), m.group(2) or 'pt'
    try:
        if float(number) <= 0:
            return None
    except ValueError:
        return None
    return f'{number}{unit}'


def _eml_line_span(source_file, start_1based, end_1based, raw_lines):
    """Whole-line ``.eml`` span (0-based, code-point columns).

    Uses the original (pre-comment-strip) *raw_lines* for column widths
    so editor navigation lands on the visible line. Empty/missing lines
    map to a zero-width start-of-line span (still resolvable by line).
    """
    try:
        s = max(1, int(start_1based)) - 1
    except (TypeError, ValueError):
        s = 0
    try:
        e = max(1, int(end_1based)) - 1
    except (TypeError, ValueError):
        e = s
    if e < s:
        s, e = e, s
    def _width(idx):
        try:
            text = raw_lines[idx]
        except (IndexError, TypeError):
            return 0
        if not isinstance(text, str):
            return 0
        return len(text)
    return SourceSpan(
        source_file=source_file,
        start=SourcePosition(s, 0),
        end=SourcePosition(e, _width(e)),
    )


def _render_text_line(ctx, raw, line_no, _table_depth=0):
    """Run the text pipeline for one logical (single-line) text unit.

    Handles ``*p(...)`` raw segments and balanced ``\\ ... \\`` inline
    math pairs. Callers guarantee no cross-line unclosed math remains.
    A lone unescaped ``\\`` produces an unclosed-math diagnostic and is
    left for Typst escaping.
    """
    if _table_depth > 20:
        print(
            f'[Warning] Line {line_no}: table/matrix nested too deep — '
            f'leaving as-is',
            file=sys.stderr,
        )
        return raw
    # --- 1. *p(...): raw passthrough segments (balanced parens, multiple
    # per line allowed). Raw parts bypass all later rules; surrounding
    # text flows through the normal pipeline. Bare p(...) is text.
    p_segs = _extract_p_segments(raw)
    for is_raw, content in p_segs:
        if not is_raw and '*p(' in content:
            print(
                f'[Warning] Line {line_no}: unclosed *p( — treated as plain text',
                file=sys.stderr,
            )
            break
    if any(is_raw for is_raw, _ in p_segs):
        placeholders = {}
        text = ''
        for k, (is_raw, content) in enumerate(p_segs):
            if is_raw:
                # Digit-only placeholder: define names must match
                # [A-Za-z_][A-Za-z0-9_]* so replace_defines can never
                # rewrite it (old \x00P{k}\x00 collided with define(P1)).
                ph = f'\x01{k}\x01'
                placeholders[ph] = escape_typst_outside_math(content)
                text += ph
            else:
                text += content
    else:
        text = raw
        placeholders = {}

    # Protect literal user '$' so later $...$ splits only see generated
    # math. Without this, "cost $5 and $x" pairs into a fake math span
    # that skips escaping (injection/bypass). Digit-only placeholders
    # are immune to define substitution.
    dollar_placeholders = {}
    if '$' in text:
        parts = text.split('$')
        text = parts[0]
        for k, seg in enumerate(parts[1:], start=0):
            ph = f'\x05{k}\x05'
            dollar_placeholders[ph] = ph
            text += ph + seg
        # Note: split removed the '$' chars; each becomes a placeholder.

    # 2. Substitute variables <var>
    text = replace_vars(ctx, text)

    # 3. Check for undefined variables (hard error)
    text = check_undefined_vars(text, line_no, ctx)

    # 4. Substitute defines
    text = replace_defines(ctx, text)

    # 5. Evaluate calc()
    text = apply_calc_in_string(ctx, text, line_no=line_no)

    # 5b. Inline math \\ ... \\ (balanced pairs on this line).
    math_placeholders = {}
    m_idx = 0
    while True:
        opening = _first_unescaped_bs(text)
        if opening is None:
            break
        closing = _first_unescaped_bs(text[opening + 1:])
        if closing is None:
            print(
                f'[Error] Line {line_no}: unclosed math delimiter '
                f'\\ ... \\ — missing closing \\.',
                file=sys.stderr,
            )
            break
        closing += opening + 1
        inner_raw = text[opening + 1:closing]
        tail = text[closing + 1:]
        wrapped = process_math_inner(ctx, inner_raw, line_no)
        # Digit-only placeholder (see *p() above): immune to
        # bare-word define substitution (old \x00M{i}\x00 matched \bM0\b).
        ph = f'\x00{m_idx}\x02'
        m_idx += 1
        math_placeholders[ph] = wrapped
        text = text[:opening] + ph + tail

    # 5c. Tables and matrices (*table / *matrix / *mat). Runs after
    # vars/calc/inline-math (like math commands) so <vars> holding
    # tables still expand; cells re-render via the full pipeline.
    table_placeholders = {}
    if _table_depth <= 20:
        text, table_placeholders = _expand_tables_and_matrices(
            ctx, text, line_no, _table_depth
        )

    # 5d. Function plots (*plot). Same placeholder discipline as
    # tables: the SVGs are written next to the .typ file and only the
    # basename is embedded, so the Typst build stays relocatable.
    plot_placeholders = {}
    if _table_depth <= 20:
        text, plot_placeholders = _expand_plots(ctx, text, line_no)

    # 6. Math constructs (friendly aliases + bare calls first).
    text = normalize_friendly_calls(text)
    for fn_name, fn_min, fn_fmt in math_call_specs(ctx):
        text = replace_math_call(text, fn_name, fn_min, fn_fmt)

    # 7. Warn about unknown *command(...)
    warn_unknown_commands(text, line_no)

    # 8. *pi, *infinity
    text = re.sub(r'\*pi\b', '$pi$', text)
    text = re.sub(r'\*infinity\b', '$infinity$', text)

    # 9. Merge/clean adjacent math blocks
    text = merge_math(text)

    # 10. Subscript notation A_1 / a_ij (outside math blocks only)
    tokens_for_index = re.split(r'(\$.*?\$)', text)
    for i, tok in enumerate(tokens_for_index):
        if not (tok.startswith('$') and tok.endswith('$') and len(tok) >= 2):
            # Single-letter base only (A_1, x_n): avoids corrupting
            # snake_case words like my_file. Chained A_1_2 is one index.
            tokens_for_index[i] = re.sub(
                r'\b([A-Za-z])_([A-Za-z0-9]+(?:_[A-Za-z0-9]+)*)\b', index_replacer, tok
            )
    text = ''.join(tokens_for_index)

    # 11. Symbol shortcuts (outside math blocks only)
    tokens_for_sym = re.split(r'(\$.*?\$)', text)
    for i, tok in enumerate(tokens_for_sym):
        if not (tok.startswith('$') and tok.endswith('$') and len(tok) >= 2):
            tokens_for_sym[i] = replace_symbol_shortcuts(tok)
    text = ''.join(tokens_for_sym)

    # 12. Apply multiplication symbol outside math blocks
    tokens = re.split(r'(\$.*?\$)', text)
    if ctx.mult_sym != '*':
        # Protect *command( spans (unknown/geometry outside draw) so their
        # leading '*' is not corrupted into the multiplication glyph.
        _cmd_prot = {}

        def _protect_cmd(m):
            ph = f'\x03{len(_cmd_prot)}\x04'
            _cmd_prot[ph] = m.group(0)
            return ph

        for i, token in enumerate(tokens):
            if not (token.startswith('$') and token.endswith('$') and len(token) >= 2):
                tokens[i] = re.sub(r'\*[A-Za-z][A-Za-z0-9_\-]*\s*\(', _protect_cmd, token)
        for i, token in enumerate(tokens):
            if not (token.startswith('$') and token.endswith('$') and len(token) >= 2):
                # Spaced replacement: 2*3 -> '2 . 3' (not '2.5'-style
                # corruption to '2.3'), 2 * 3 stays '2 . 3'.
                tokens[i] = re.sub(r'\s*\*\s*', f' {ctx.mult_sym} ', token)
        text = ''.join(tokens)
        for ph, orig in _cmd_prot.items():
            text = text.replace(ph, orig)
    else:
        text = ''.join(tokens)

    # 13. Escape special Typst syntax characters outside math blocks
    # (user '$' are placeholders here; generated $...$ are preserved).
    text = escape_typst_outside_math(text, escape_dollar=True)
    # Restore tables/matrices first so inner $/math placeholders kept
    # inside them are still restored by the steps below.
    for ph, typ in table_placeholders.items():
        text = text.replace(ph, typ)
    for ph, typ in plot_placeholders.items():
        text = text.replace(ph, typ)
    # Restore literal dollars as escaped Typst dollars.
    for ph in dollar_placeholders:
        text = text.replace(ph, r'\$')

    for ph, raw_content in placeholders.items():
        text = text.replace(ph, raw_content)
    for ph, wrapped in math_placeholders.items():
        text = text.replace(ph, wrapped)

    return text


def _try_friendly_block(ctx, line, line_no):
    """Render markdown-friendly block syntax to Typst, or None.

    - ``# Title`` / ``## Sub`` / ``### Subsub`` -> ``= Title`` etc.
    - ``= Title`` / ``== Sub`` (Typst headings) stay headings.
    - ``- item`` / ``+ item`` -> Typst lists (not escaped literals).
    - ``1. item`` -> Typst enumeration.
    Inner text flows through the normal text pipeline so variables,
    calc, math and symbols keep working inside headings/lists.
    Returns the Typst line or None when *line* is not a friendly block.
    """
    m = re.match(r'^(#{1,3})\s+(.*\S)\s*$', line)
    if m:
        level = len(m.group(1))
        inner = _render_text_line(ctx, m.group(2), line_no)
        return f"{'=' * level} {inner}"
    m = re.match(r'^(=+)\s+(.*\S)\s*$', line)
    if m:
        inner = _render_text_line(ctx, m.group(2), line_no)
        return f"{m.group(1)} {inner}"
    m = re.match(r'^([-+])\s+(.*\S)\s*$', line)
    if m:
        inner = _render_text_line(ctx, m.group(2), line_no)
        return f"{m.group(1)} {inner}"
    m = re.match(r'^(\d+)\.\s+(.*\S)\s*$', line)
    if m:
        inner = _render_text_line(ctx, m.group(2), line_no)
        # Preserve the original number for readability; Typst auto-numbers.
        return f"{m.group(1)}. {inner}"
    return None


def _parse_draw_safe(block_text, line_no=None):
    """Parse a draw block without ever crashing the build.

    Returns Typst output; on hard failure emits a comment placeholder
    and reports [Error] so compile_ezmath returns False upstream.
    """
    try:
        import geometry
    except ImportError:
        try:
            from .. import geometry
        except ImportError as e:
            loc = f' Line {line_no}:' if line_no else ''
            print(f'[Error]{loc} geometry support missing ({e}) — draw skipped',
                  file=sys.stderr)
            return '// [Error] draw skipped: geometry support missing'
    try:
        return geometry.parse_draw_block(block_text)
    except Exception as e:
        loc = f' Line {line_no}:' if line_no else ''
        print(f'[Error]{loc} invalid *draw block ({e})', file=sys.stderr)
        return f'// [Error] invalid draw block: {e}'


def _is_draw_error_placeholder(out_line):
    return out_line.startswith('// [Error]')


def _render_math_inner_multiline(ctx, full_raw, line_no):
    """Substitute vars/defines/calc then convert a multiline math body."""
    # Protect *p(...) raw spans so they bypass math processing, mirroring
    # the single-line path.
    p_segs = _extract_p_segments(full_raw)
    if any(is_raw for is_raw, _ in p_segs):
        out_parts = []
        for is_raw, content in p_segs:
            if is_raw:
                out_parts.append(escape_typst_outside_math(content))
            elif not content.strip():
                out_parts.append(content)
            else:
                sub = replace_vars(ctx, content)
                sub = check_undefined_vars(sub, line_no, ctx)
                sub = replace_defines(ctx, sub)
                sub = apply_calc_in_string(ctx, sub, line_no=line_no)
                out_parts.append(process_math_inner(ctx, sub, line_no))
        return ' '.join(p for p in out_parts if p != '').strip()
    sub = replace_vars(ctx, full_raw)
    sub = check_undefined_vars(sub, line_no, ctx)
    sub = replace_defines(ctx, sub)
    sub = apply_calc_in_string(ctx, sub, line_no=line_no)
    return process_math_inner(ctx, sub, line_no)


SUPPORTED_EXPORT_FORMATS = ('pdf', 'png', 'svg', 'html', 'typ')

FORMAT_BY_EXT = {
    '.pdf': 'pdf',
    '.png': 'png',
    '.svg': 'svg',
    '.html': 'html',
    '.htm': 'html',
    '.typ': 'typ',
}


def infer_export_format(output_path, explicit=None):
    """Return the export format for *output_path* (or None + error).

    *explicit* (``--format``) wins when given; otherwise the output
    extension decides (``out.png`` -> ``png``). Unknown extensions fall
    back to ``pdf`` with a warning so ``out`` still produces something.
    """
    if explicit is not None:
        fmt = str(explicit).strip().lower().lstrip('.')
        if fmt in ('htm',):
            fmt = 'html'
        if fmt not in SUPPORTED_EXPORT_FORMATS:
            print(
                f"[Error] unsupported export format {explicit!r} — "
                f"choose from {', '.join(SUPPORTED_EXPORT_FORMATS)}",
                file=sys.stderr,
            )
            return None
        return fmt
    ext = os.path.splitext(os.fspath(output_path))[1].lower()
    if ext in FORMAT_BY_EXT:
        return FORMAT_BY_EXT[ext]
    print(
        f"[Warning] unknown output extension {ext!r} — assuming pdf. "
        f"Use --format to pick from {', '.join(SUPPORTED_EXPORT_FORMATS)}.",
        file=sys.stderr,
    )
    return 'pdf'


def _resolve_export(output_pdf, explicit_format, explicit_ppi, input_str):
    """Normalize (output_path, format, ppi) for compile_ezmath/CLI/editor.

    Keeps the legacy default (``<base>.pdf``) when no output is given.
    Returns (output_path, format, ppi) or (None, None, None) on error.
    """
    if output_pdf is None:
        base, _ = os.path.splitext(input_str)
        out_path = base + '.pdf'
    else:
        out_path = os.fspath(output_pdf)
    fmt = infer_export_format(out_path, explicit_format)
    if fmt is None:
        return None, None, None
    ppi = None
    if explicit_ppi is not None:
        try:
            ppi = int(explicit_ppi)
            if ppi <= 0 or ppi > 1200:
                raise ValueError('ppi out of range')
        except (ValueError, TypeError):
            print(
                f"[Error] invalid --ppi {explicit_ppi!r} — "
                f"expected an integer 1..1200",
                file=sys.stderr,
            )
            return None, None, None
    return out_path, fmt, ppi


def _run_typst_export(typst_file, output_path, fmt, ppi, input_str=''):
    """Run typst.compile() for one export; True on success.

    - ``typ``: just copy the intermediate file to *output_path*.
    - ``pdf``/``html``: single-file compile.
    - ``png``/``svg``: single-file when the doc fits one page; when
      Typst reports "multiple pages", retry with a ``stem-{p}.ext``
      pattern so every page lands on disk (Typst requires ``{p}``).
    """
    import shutil
    label = {'pdf': 'PDF', 'png': 'PNG image(s)', 'svg': 'SVG image(s)',
             'html': 'HTML', 'typ': 'Typst'} .get(fmt, fmt.upper())
    print(f'Compiling {label} with Typst...')

    def _copy_plot_sidecars(dst_dir):
        """Copy ``<stem>-plot-*.svg`` next to *dst_dir* for typ/html.

        PDF/PNG/SVG embeds the images; raw Typst source and HTML keep
        external ``#image("...")`` references, so the SVGs must travel
        with the exported file when it lands in another directory.
        """
        import glob as _glob
        try:
            tdir = os.path.dirname(os.path.abspath(typst_file))
            tstem = os.path.splitext(os.path.basename(typst_file))[0]
            ddir = os.path.abspath(dst_dir) if dst_dir else os.getcwd()
            if os.path.abspath(tdir) == os.path.abspath(ddir):
                return
            os.makedirs(ddir, exist_ok=True)
            for svg in sorted(
                    _glob.glob(os.path.join(tdir, f'{tstem}-plot-*.svg'))):
                try:
                    shutil.copyfile(
                        svg, os.path.join(ddir, os.path.basename(svg)))
                except OSError:
                    pass
        except Exception:
            pass
    if _require_typst() is None:
        print(
            '\n[ERROR] The `typst` Python package is not installed.\n'
            'Run `uv sync` to install it, then retry.',
            file=sys.stderr,
        )
        return False
    _backend = typst
    if fmt == 'typ':
        try:
            parent = os.path.dirname(os.path.abspath(output_path))
            if parent:
                os.makedirs(parent, exist_ok=True)
            if os.path.abspath(output_path) != os.path.abspath(typst_file):
                shutil.copyfile(typst_file, output_path)
            _copy_plot_sidecars(parent)
            print(f'Successfully exported {input_str} to {output_path} (Typst source)!')
            return True
        except OSError as e:
            print(f'\n[ERROR] Typst export failed: {e}', file=sys.stderr)
            return False
    if ppi is not None and fmt != 'png':
        print(
            f'[Warning] --ppi {ppi} only affects PNG export — ignoring for {fmt}',
            file=sys.stderr,
        )
    try:
        parent = os.path.dirname(os.path.abspath(output_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        kwargs = {'ignore_system_fonts': True}
        if fmt != 'pdf':
            kwargs['format'] = fmt
        if fmt == 'png' and ppi is not None:
            kwargs['ppi'] = ppi
        try:
            _backend.compile(typst_file, output_path, **kwargs)
        except RuntimeError as e:
            # Typst PNG/SVG multi-page error: retry with {p} pattern.
            if fmt in ('png', 'svg') and 'multiple pages' in str(e).lower() \
                    and '{p}' not in output_path:
                stem, ext = os.path.splitext(output_path)
                patterned = f'{stem}-{{p}}{ext}'
                print(
                    f'[Info] document has multiple pages — '
                    f'writing {patterned} (one file per page)',
                )
                _backend.compile(typst_file, patterned, **kwargs)
                print(f'Successfully compiled {input_str} to {patterned} via Typst!')
                return True
            raise
        if fmt == 'html':
            _copy_plot_sidecars(os.path.dirname(os.path.abspath(output_path)))
        print(f'Successfully compiled {input_str} to {output_path} via Typst!')
        return True
    except FileNotFoundError as e:
        # Input .typ vanished between write and compile (I/O race).
        print(f'\n[ERROR] Typst compilation failed (file not found): {e}', file=sys.stderr)
        return False
    except Exception as e:
        # typst.TypstError (bad markup) and any other compile failure.
        print(f'\n[ERROR] Typst compilation failed: {e}', file=sys.stderr)
        return False


def compile_ezmath(input_file, output_pdf=None, *, output=None, format=None, ppi=None,
                   source_map=True, source_map_path=None,
                   embed_source_comments=False, embed_source_links=False):
    """Compile an .ezmath document via an intermediate Typst file.

    Actual processing order (per text line, after comment stripping):
        assignments/defines/draw-blocks (control lines)
          -> *p(...) raw passthrough
          -> <variable> substitution
          -> undefined-variable check (hard error)
          -> define (bare-word) substitution
          -> calc(...) evaluation
          -> inline math \\ ... \\ (multiline supported, see below)
          -> tables/matrices (*table / *matrix / *mat, | rows, ;/, cells)
          -> function plots (*plot(expression ; xmin ; xmax) -> SVG #image)
          -> math commands (*frac, *pow, *root, *sum, *prod, *lim, ...)
             (friendly: ',' works like ';', *fraction etc. are aliases)
          -> unknown *command(...) warning
          -> *pi / *infinity
          -> subscript notation (A_1, outside math only)
          -> symbol shortcuts (outside math only, incl. == -> =)
          -> multiplication-symbol replacement (outside math only)
          -> Typst escaping (outside math only)
          -> friendly blocks (# headings, -/+ lists, 1. enums)
        Finally: Typst file generation + `typst.compile()` (PyPI package).

    Export: *output* (alias *output_pdf* for backward compat) picks the
    destination; *format* (pdf/png/svg/html/typ) defaults to the output
    extension. ``typ`` writes only the intermediate source. ``png``honours
    *ppi*. Multi-page PNG/SVG automatically uses ``stem-{p}.ext``.

    Inline math: an unescaped ``\\`` opens math mode, the next
    unescaped ``\\`` closes it. ``\\\\`` is a literal backslash.
    Pairs on one line become ``$...$``; an unclosed opener buffers
    following lines until its closer (control lines are suspended
    while math is open). Content inside is processed with the same
    math-command/symbol pipeline as the rest of the document.

    Source map: when *source_map* is true (default) a sidecar JSON file
    mapping generated ``.typ`` ranges back to ``.eml`` spans is written
    next to the intermediate ``.typ`` file (``<base>.smap.json``, or
    *source_map_path* when given). Pass ``source_map=False`` to skip it.
    When *embed_source_comments* is true, ``// eml: ...`` comment lines
    are also emitted into the ``.typ`` (robust Typst comments, ignored
    in the PDF); defaults to off so ``.typ`` output stays unchanged.
    When *embed_source_links* is true, each mapped body block is wrapped
    in ``#link("eml-src://typ/<line>/<col>")[...]`` (see
    :mod:`editor.preview_links`); Typst emits standard PDF ``/URI``
    annotations without changing the rendered appearance, and the URL
    pins the exact generated-Typ position for preview click navigation.
    Header directive lines (``#set``) are never wrapped. Defaults to off
    so exports stay clean; the live preview enables it.

    Returns True on success, False on failure (.typ is still written
    whenever parsing reaches the codegen stage).
    """
    # Backward compat: compile_ezmath(src, out.pdf) still works.
    if output is None:
        _out_arg = output_pdf
    elif output_pdf is None:
        _out_arg = output
    else:
        # Both given (CLI passes output=..., legacy passes output_pdf=...):
        # explicit `output=` wins.
        _out_arg = output
    _explicit_format = format
    _explicit_ppi = ppi
    try:
        if _out_arg is None:
            # Default <base>.pdf (legacy behavior).
            base, _ = os.path.splitext(os.fspath(input_file))
            _out_arg = base + '.pdf'
        else:
            _out_arg = os.fspath(_out_arg)
        input_str = os.fspath(input_file)
    except (TypeError, ValueError) as e:
        print(f'[Error] Invalid input/output path: {e}', file=sys.stderr)
        return False

    ctx = CompileContext()
    # Plot SVGs live next to the intermediate .typ file; the Typst
    # output only embeds basenames so the build stays relocatable.
    _typ_base, _ = os.path.splitext(input_str)
    _typ_file_early = _typ_base + '.typ'
    ctx.plot_dir = os.path.dirname(os.path.abspath(_typ_file_early)) or '.'
    ctx.plot_stem = os.path.splitext(
        os.path.basename(_typ_file_early))[0] or 'doc'
    ctx.plot_index = 0

    try:
        with open(input_str, 'r', encoding='utf-8') as f:
            raw_text = f.read()
    except (OSError, UnicodeDecodeError, TypeError, ValueError) as e:
        print(f'[Error] Cannot open input file {input_str!r}: {e}', file=sys.stderr)
        return False

    lines = strip_comments(raw_text).splitlines()
    raw_source_lines = raw_text.splitlines()
    # Parallel to output_lines: original .eml span for each entry (None
    # for consumed control lines, which produce no output).
    output_lines: list[str] = []
    output_spans: list[SourceSpan | None] = []
    # Absolute source id stored in spans (preview uses a temp copy; the
    # editor maps it back to the live document by line/col).
    _src_id = os.path.abspath(input_str)
    ctx.source_file = _src_id
    draw_failed = False
    in_f_block = False
    block_type = None
    block_content: list[str] = []
    block_start_line = 0
    in_math = False
    math_buf = []
    math_start = 0
    in_fence = False

    def _append_output(text: str, start_1: int, end_1: int):
        output_lines.append(text)
        try:
            output_spans.append(_eml_line_span(_src_id, start_1, end_1, raw_source_lines))
        except Exception:
            output_spans.append(None)

    for line_no, line in enumerate(lines, start=1):
        stripped_fence = line.strip()
        if stripped_fence.startswith('```'):
            in_fence = not in_fence
            continue
        if in_fence:
            # Fenced code blocks are literal: no assignments, no math,
            # no Typst structure. Force every '$' literal.
            _append_output(
                escape_typst_outside_math(line.rstrip('\n')).replace('$', r'\$'),
                line_no, line_no,
            )
            continue
        line = line.strip()
        if not line:
            continue

        # --- Multiline math continuation (control lines suspended) ---
        if in_math:
            det = _detection_text(line)
            closing = _first_unescaped_bs(det)
            if closing is None:
                math_buf.append(line)
                continue
            head, tail = line[:closing], line[closing + 1:]
            math_buf.append(head)
            full_raw = ' '.join(p for p in math_buf if p != '').strip()
            wrapped = _render_math_inner_multiline(ctx, full_raw, math_start)
            in_math = False
            math_buf = []
            if not tail.strip():
                if wrapped:
                    _append_output(wrapped, math_start, line_no)
                continue
            # Tail is normal text that may hold further math pairs.
            # Wrapped is already $...$ — never re-run it through
            # _render_text_line (its dollars would be escaped to \$).
            rendered_tail = _render_text_line(ctx, tail, line_no)
            if wrapped:
                combined = (wrapped + ' ' + rendered_tail).strip()
                if combined:
                    _append_output(combined, math_start, line_no)
            else:
                if rendered_tail:
                    _append_output(rendered_tail, line_no, line_no)
            continue

        # Friendly: let/var and bare *define without parens.
        # _normalize_friendly_statement rewrites e.g. "let x = 5" to
        # "<x> = 5" and "*define x = 5" to "define(x = 5)".
        _norm_stmt = _normalize_friendly_statement(line)
        if _norm_stmt != line and (
            _norm_stmt.startswith('define(')
            or re.match(r'^<[^<>]+>\s*=', _norm_stmt)
        ):
            process_assignment_or_define(ctx, _norm_stmt, line_no=line_no)
            continue

        # Handle single-line *define(...) or define(...) (space-tolerant).
        _m_def = re.match(r'^(\*?define)\s*\((.*)\)\s*$', line)
        if _m_def and _m_def.group(2) is not None:
            inner_stmt = _m_def.group(2)
            process_assignment_or_define(ctx, 'define(' + inner_stmt + ')', line_no=line_no)
            continue

        # Single-line *draw(...) — parse inner block directly
        if line.startswith('*draw(') and line.endswith(')'):
            inner = line[6:-1]
            inner = replace_vars(ctx, inner)
            inner = replace_defines(ctx, inner)
            inner = apply_calc_in_string(ctx, inner, line_no=line_no)
            drawn = _parse_draw_safe(inner, line_no=line_no)
            _append_output(drawn, line_no, line_no)
            if _is_draw_error_placeholder(drawn):
                draw_failed = True
            continue

        # Multi-line blocks: *( or *f( or f( or *draw(
        # Single-line silent blocks: *(...), *f(...), f(...) holding
        # one assignment (e.g. *(<a> = 1)).
        if line.startswith('*f(') and line.endswith(')'):
            inner = line[3:-1].strip()
            if not (inner.startswith('frac(') or inner.startswith('root(')):
                process_assignment_or_define(ctx, inner, line_no=line_no)
                continue
        elif ((line.startswith('*(') and line.endswith(')')
               and len(line) > 3)
              or (line.startswith('f(') and line.endswith(')')
                  and len(line) > 3 and not line.startswith('frac('))):
            if line.startswith('*('):
                inner = line[2:-1].strip()
            else:  # f(...)
                inner = line[2:-1].strip()
            if inner and not inner.startswith('*'):
                # Heuristic: only treat as a silent block when it looks
                # like an assignment/define, otherwise fall through to
                # normal text (e.g. math grouping). Friendly let/var
                # (let x = 5 -> <x> = 5) counts as an assignment so
                # single-line *(let x = 5) matches the LSP and the
                # multi-line block path (which normalizes inside
                # process_assignment_or_define).
                _inner_norm = _normalize_friendly_statement(inner)
                if (re.match(r'^<[^<>]+>\s*=', inner) or inner.startswith('define(')
                        or _inner_norm != inner):
                    process_assignment_or_define(ctx, inner, line_no=line_no)
                    continue
        if line in ('*(', '*f(', 'f(', '*draw(',
                      '*table(', '*matrix(', '*mat('):
            in_f_block = True
            block_type = line
            block_content = []
            block_start_line = line_no
            continue
        elif line == ')' and in_f_block:
            if block_type == '*draw(':
                drawn = _parse_draw_safe('\n'.join(block_content), line_no=line_no)
                _append_output(drawn, block_start_line, line_no)
                if _is_draw_error_placeholder(drawn):
                    draw_failed = True
            elif block_type in ('*table(', '*matrix(', '*mat('):
                cmd_name = block_type[1:-1]
                joined = _tables.join_block_lines(block_content)
                single = f'*{cmd_name}({joined})'
                _append_output(
                    _render_text_line(ctx, single, line_no),
                    block_start_line, line_no,
                )
            else:
                for stmt in block_content:
                    process_assignment_or_define(ctx, stmt, line_no=line_no)
            in_f_block = False
            continue

        if in_f_block:
            block_content.append(line)
            continue

        if re.match(r'^<[^<>]+>\s*=', line):
            process_assignment_or_define(ctx, line, line_no=line_no)
            continue

        # --- Document title: *doc_title(...) is a control line (consumed) ---
        _doc = _match_doc_title(line)
        if _doc is not None:
            if _doc[0] == 'unclosed':
                print(
                    f'[Warning] Line {line_no}: unclosed *{_doc[1]}(... — '
                    f'missing closing parenthesis',
                    file=sys.stderr,
                )
            else:
                _, _name, _inner = _doc
                if not _inner.strip():
                    print(
                        f'[Warning] Line {line_no}: *{_name}(...) is empty — '
                        f'using default title',
                        file=sys.stderr,
                    )
                    continue
                else:
                    if ctx.doc_title_raw is not None:
                        print(
                            f'[Warning] Line {line_no}: multiple *doc_title(...) — '
                            f'using last one',
                            file=sys.stderr,
                        )
                    ctx.doc_title_raw = _inner.strip()
                    ctx.doc_title_line = line_no
                    continue
                # Unclosed titles fall through to normal text so the
                # user still sees the line instead of silent loss.

        # --- Document font: *doc_font(...) is a control line (consumed) ---
        _font = _match_doc_font(line)
        if _font is not None:
            if _font[0] == 'unclosed':
                print(
                    f'[Warning] Line {line_no}: unclosed *{_font[1]}(... — '
                    f'missing closing parenthesis',
                    file=sys.stderr,
                )
            else:
                _, _fname, _finner = _font
                if not _finner.strip():
                    print(
                        f'[Warning] Line {line_no}: *{_fname}(...) is empty — '
                        f'using default font',
                        file=sys.stderr,
                    )
                    continue
                _family_raw, _size_raw = _parse_doc_font(_finner)
                _family = _valid_doc_font_family(_family_raw)
                _size = _valid_doc_font_size(_size_raw) if _size_raw else \
                    DEFAULT_DOC_FONT_SIZE
                if _family is None or (_size_raw and _size is None):
                    print(
                        f'[Warning] Line {line_no}: invalid *{_fname}(...) — '
                        f'ignored: {line!r}',
                        file=sys.stderr,
                    )
                    continue
                if ctx.doc_font_family is not None:
                    print(
                        f'[Warning] Line {line_no}: multiple *doc_font(...) — '
                        f'using last one',
                        file=sys.stderr,
                    )
                ctx.doc_font_family = _family
                ctx.doc_font_size = _size
                continue
                # Unclosed font lines fall through to normal text so the
                # user still sees the line instead of silent loss.

        # --- Friendly blocks: # headings, - / + lists, 1. enums, = headings ---
        _friendly = _try_friendly_block(ctx, line, line_no)
        if _friendly is not None:
            _append_output(_friendly, line_no, line_no)
            continue

        # --- Inline-math multiline opener detection ---
        det = _detection_text(line)
        positions = find_unescaped(det)
        if len(positions) % 2 == 1:
            # Unclosed opener: render head now, buffer the rest.
            # Only simple case (one opener, closer on a later line) is
            # buffered; multiple pairs plus a trailing opener still
            # buffers just the tail after the last opener for simplicity:
            # find last opener when odd count.
            opening = positions[-1]
            head, rest = line[:opening], line[opening + 1:]
            # Render any balanced pairs inside head normally.
            if head.strip():
                _append_output(_render_text_line(ctx, head, line_no), line_no, line_no)
            math_buf = [rest]
            math_start = line_no
            in_math = True
            continue

        # --- Normal single-line text ---
        _append_output(_render_text_line(ctx, line, line_no), line_no, line_no)

    if in_math:
        print(
            f'[Error] Line {math_start}: unclosed math delimiter '
            f'\\ ... \\ — missing closing \\. Emitting buffered '
            f'content as text.',
            file=sys.stderr,
        )
        leftover = ' '.join(p for p in math_buf if p != '').strip()
        if leftover:
            _append_output(_render_text_line(ctx, leftover, math_start), math_start, math_start)

    # Warn if a block was never closed.
    # An unclosed block silently swallows its buffered lines, so fail
    # the build loudly instead of reporting success with missing content.
    unclosed_block = in_f_block
    if in_f_block:
        print(
            "[ERROR] Unclosed block '(' detected — content inside was not emitted. "
            "Add the missing ')' to fix.",
            file=sys.stderr,
        )

    # ------------------------------------------------------------------
    # Generate Typst file
    # ------------------------------------------------------------------
    base, _ = os.path.splitext(input_str)
    typst_file = base + '.typ'
    if os.path.abspath(typst_file) == os.path.abspath(input_str):
        # Input already ends with .typ: writing the intermediate back
        # would destroy the source. Fail loudly instead.
        print(
            f"[ERROR] Input file {input_str!r} would be overwritten by the "
            f"intermediate Typst output — rename it to .ezmath and retry.",
            file=sys.stderr,
        )
        return False

    if ctx.doc_font_family is not None:
        _font_rule = (f'#set text(font: ("{ctx.doc_font_family}",), '
                      f'size: {ctx.doc_font_size or DEFAULT_DOC_FONT_SIZE})')
    else:
        _font_rule = '#set text(size: 12pt)'
    typst_content: list[str] = [
        _font_rule,
        '#set page(paper: "a4", margin: 2cm)',
    ]
    # Parallel to typst_content: .eml span for mapped lines, None for
    # generated-only lines (headers without source, blank, separators,
    # source comments). Used to build the sidecar source map below.
    _typ_span_for_line: list[SourceSpan | None] = [None, None]
    _title_span_meta: SourceSpan | None = None
    _title_span_head: SourceSpan | None = None
    if ctx.doc_title_raw is not None and ctx.doc_title_line:
        try:
            _title_span_meta = _eml_line_span(
                _src_id, ctx.doc_title_line, ctx.doc_title_line,
                raw_source_lines,
            )
            _title_span_head = _eml_line_span(
                _src_id, ctx.doc_title_line, ctx.doc_title_line,
                raw_source_lines,
            )
        except Exception:
            _title_span_meta = _title_span_head = None
    if ctx.doc_title_raw is not None:
        _rendered_title = _escape_doc_title_brackets(
            _render_text_line(
                ctx, ctx.doc_title_raw, ctx.doc_title_line or 1
            )
        )
        _plain_title = _doc_title_plain(ctx, ctx.doc_title_raw)
        _escaped_meta = _plain_title.replace('\\', '\\\\').replace('"', '\\"')
        typst_content.append(f'#set document(title: "{_escaped_meta}")')
        _typ_span_for_line.append(_title_span_meta)
        typst_content.append(f'#align(center)[= {_rendered_title}]')
        _typ_span_for_line.append(_title_span_head)
    else:
        typst_content.append('#set document(title: "Easy Math Document")')
        _typ_span_for_line.append(None)
        typst_content.append('#align(center)[= Easy Math Document]')
        _typ_span_for_line.append(None)
    typst_content.append('')
    _typ_span_for_line.append(None)

    def _eml_comment_for(span: SourceSpan | None) -> str | None:
        if span is None:
            return None
        try:
            return (
                f"// eml:{span.source_file}:"
                f"{span.start.line + 1}:{span.start.column + 1}-"
                f"{span.end.line + 1}:{span.end.column + 1}"
            )
        except Exception:
            return None

    for index, out_line in enumerate(output_lines):
        span: SourceSpan | None = None
        try:
            span = output_spans[index] if index < len(output_spans) else None
        except Exception:
            span = None
        if embed_source_comments:
            comment = _eml_comment_for(span)
            if comment is not None:
                typst_content.append(comment)
                _typ_span_for_line.append(None)
        sublines = str(out_line).split('\n')
        # Source-link wrapping (preview click navigation): pin the block to
        # its Typst start position. Inline only — no new lines, so the
        # sidecar map stays identical. Skipped for unmapped blocks and for
        # bodies that already contain a link (no nested #link).
        _link_open = ''
        if (embed_source_links and span is not None
                and '#link(' not in str(out_line)):
            try:
                _link_open = _source_link_prefix(len(typst_content), 0)
            except Exception:
                _link_open = ''
        for si, sub in enumerate(sublines):
            if si == 0 and _link_open:
                sub = _link_open + sub
            if si < len(sublines) - 1:
                typst_content.append(sub)
            elif _link_open:
                # Close the link BEFORE the linebreak marker: `\]`
                # would parse as an escaped literal bracket and leave
                # the link body unclosed.
                typst_content.append(sub + '] \\')
            else:
                typst_content.append(sub + ' \\')
            _typ_span_for_line.append(span)
        if index < len(output_lines) - 1:
            typst_content.append('#v(0.65em)')
            _typ_span_for_line.append(None)

    try:
        with open(typst_file, 'w', encoding='utf-8') as tf:
            tf.write('\n'.join(typst_content) + '\n')
    except OSError as e:
        print(f'\n[ERROR] Cannot write intermediate file {typst_file!r}: {e}',
              file=sys.stderr)
        return False

    # --- Sidecar source map (additive; never breaks the build) ---
    try:
        _map_path: str | None = None
        if source_map_path is not None:
            _map_path = os.fspath(source_map_path)
        elif source_map:
            _map_path = default_map_path(typst_file)
        if _map_path:
            _smap = TypstSourceMap(
                source_file=_src_id,
                typ_file=os.path.abspath(typst_file),
            )
            # Coalesce consecutive typ lines sharing the same span object
            # into one range entry (multi-line draw -> one .eml span).
            # Distinct output entries keep distinct entries even when spans
            # are equal by value (one .eml -> multiple typ regions, e.g.
            # the two title lines above stay separate).
            _run_span: SourceSpan | None = None
            _run_start = 0
            for _ti, _sp in enumerate(_typ_span_for_line):
                if _sp is None:
                    if _run_span is not None:
                        _end_line = _ti - 1
                        _smap.add(
                            SourcePosition(_run_start, 0),
                            SourcePosition(
                                _end_line, len(typst_content[_end_line])),
                            _run_span,
                        )
                        _run_span = None
                    continue
                if _run_span is None:
                    _run_span = _sp
                    _run_start = _ti
                elif _sp is not _run_span:
                    _end_line = _ti - 1
                    _smap.add(
                        SourcePosition(_run_start, 0),
                        SourcePosition(
                            _end_line, len(typst_content[_end_line])),
                        _run_span,
                    )
                    _run_span = _sp
                    _run_start = _ti
                # else: same object -> extend run
            if _run_span is not None:
                _end_line = len(_typ_span_for_line) - 1
                _smap.add(
                    SourcePosition(_run_start, 0),
                    SourcePosition(_end_line, len(typst_content[_end_line])),
                    _run_span,
                )
            _smap.save(_map_path)
    except Exception as exc:  # additive only: log and continue
        print(f'[Warning] could not write source map: {exc}', file=sys.stderr)

    try:
        # Drop CPython's source-line cache (tracebacks/warnings during
        # parsing and first-use heavy imports can leave ~10MB of module
        # text cached here for the life of the editor process; it is only
        # a cache and re-reads from disk on demand).
        import linecache as _linecache
        _linecache.clearcache()
    except Exception:
        pass

    print(f'Generated intermediate file: {typst_file}')

    if unclosed_block:
        print(
            '\n[ERROR] Build failed: unclosed block — output PDF not attempted. '
            'Add the missing \')\' and retry.',
            file=sys.stderr,
        )
        return False

    if draw_failed:
        print(
            '\n[ERROR] Build failed: invalid *draw block — output PDF not attempted. '
            'Fix the geometry errors above and retry.',
            file=sys.stderr,
        )
        return False

    # ------------------------------------------------------------------
    # Compile with Typst (PyPI `typst` package — no external binary needed)
    # ------------------------------------------------------------------
    # Export resolution is centralized in _resolve_export() so the CLI,
    # the editor and direct API calls share format inference + pagination.
    _out_path, _fmt, _ppi = _resolve_export(
        _out_arg, _explicit_format, _explicit_ppi,
        input_str=input_str,
    )
    if _out_path is None or _fmt is None:
        return False
    return _run_typst_export(
        typst_file, _out_path, _fmt, _ppi, input_str=input_str,
    )


def _print_usage():
    print('Usage: easy-math-lang <input.ezmath> [output.pdf]')
    print('       easy-math-lang [--format FORMAT] [--ppi PPI] [-o OUTPUT] <input.ezmath>')
    print('')
    print('Export formats: pdf, png, svg, html, typ (default: from output extension).')
    print('  PNG/SVG multi-page documents write stem-{p}.ext (one file per page).')
    print('  Examples:')
    print('    easy-math-lang doc.ezmath                # doc.pdf')
    print('    easy-math-lang doc.ezmath out.png        # PNG image(s)')
    print('    easy-math-lang --format png doc.ezmath   # doc.png')
    print('    easy-math-lang --format png --ppi 300 doc.ezmath -o hi.png')
    print('')
    print('Options:')
    print('  -h, --help      Show this help and exit')
    print('  --version       Show version and exit')
    print('  --check-update  Check whether a newer EasyMath release '
          'is available')
    print('  --format FMT    Export format: pdf, png, svg, html, typ')
    print('  --ppi PPI       PNG resolution 1..1200 (default: Typst default)')
    print('  -o, --output FILE  Output file (same as positional [output])')
    print('  --list-formats  List supported export formats and exit')
    print('  --              Treat remaining arguments as file names '
          '(e.g. a file literally named --version)')


def _standalone_flag_error(flag):
    print(f'error: {flag} takes no arguments', file=sys.stderr)
    _print_usage()
    sys.exit(2)


def main():
    args = sys.argv[1:]
    # `--` escape hatch: everything after the first `--` is a file
    # operand, so files with flag-like names (e.g. `--version`) stay
    # compilable. Leading `--` keeps legacy behavior (args become the
    # file list, no option parsing).
    positional_only = False
    dashdash = []
    if '--' in args:
        cut = args.index('--')
        if cut == 0:
            args = args[1:]
            positional_only = True
        else:
            dashdash = args[cut + 1:]
            args = args[:cut]
    # Standalone flags are only honored in flag position (args[0]); a
    # trailing flag after a filename must not hijack the compile job.
    if not positional_only and args[:1] == ['--check-update']:
        if len(args) > 1:
            _standalone_flag_error('--check-update')
        from .update import run_check_update
        sys.exit(run_check_update())
    if not positional_only and args[:1] == ['--version']:
        if len(args) > 1:
            _standalone_flag_error('--version')
        from .update import APP_NAME, get_current_version
        print(f'{APP_NAME} {get_current_version()}')
        sys.exit(0)
    if not positional_only and args[:1] == ['--list-formats']:
        if len(args) > 1:
            _standalone_flag_error('--list-formats')
        print(', '.join(SUPPORTED_EXPORT_FORMATS))
        sys.exit(0)
    if not args or (not positional_only and args[0] in ('-h', '--help')):
        _print_usage()
        sys.exit(0 if args and not positional_only else 1)

    # Extract export options (--format/--ppi/-o) anywhere in the args
    # (except in positional-only `--` mode). Unknown --flags after a
    # filename (e.g. `doc.ezmath --check-update`) stay positionals so
    # the legacy "trailing flag is an output file" test keeps passing.
    exp_format = None
    exp_ppi = None
    exp_output = None
    positionals = []
    if not positional_only:
        i = 0
        while i < len(args):
            a = args[i]
            if a in ('--format', '--ppi', '--output', '-o'):
                if i + 1 >= len(args):
                    print(f'error: {a} needs a value', file=sys.stderr)
                    _print_usage()
                    sys.exit(2)
                val = args[i + 1]
                if a == '--format':
                    exp_format = val
                elif a == '--ppi':
                    exp_ppi = val
                else:
                    if exp_output is not None:
                        print('error: multiple --output/-o given',
                              file=sys.stderr)
                        _print_usage()
                        sys.exit(2)
                    exp_output = val
                i += 2
                continue
            if a.startswith('--format='):
                exp_format = a.split('=', 1)[1]
                i += 1
                continue
            if a.startswith('--ppi='):
                exp_ppi = a.split('=', 1)[1]
                i += 1
                continue
            if a.startswith('--output='):
                if exp_output is not None:
                    print('error: multiple --output/-o given',
                          file=sys.stderr)
                    _print_usage()
                    sys.exit(2)
                exp_output = a.split('=', 1)[1]
                i += 1
                continue
            positionals.append(a)
            i += 1
        positionals.extend(dashdash)
    else:
        positionals = list(args) + list(dashdash)

    if len(positionals) > 2:
        print(f'error: too many arguments: {" ".join(positionals[2:])}',
              file=sys.stderr)
        _print_usage()
        sys.exit(2)
    if not positionals:
        _print_usage()
        sys.exit(1)

    input_file = positionals[0]
    if exp_output is not None and len(positionals) > 1:
        print('error: output given twice (-o/--output and positional)',
              file=sys.stderr)
        _print_usage()
        sys.exit(2)
    if len(positionals) > 1:
        output_file = positionals[1]
    elif exp_output is not None:
        output_file = exp_output
    else:
        base, _ = os.path.splitext(os.fspath(input_file))
        output_file = base + '.pdf'
    ok = compile_ezmath(input_file, output_file,
                        format=exp_format, ppi=exp_ppi)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
