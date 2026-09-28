"""Document pipeline: line loop, text phases, Typst generation."""

import os
import re
import sys

try:
    import typst
except ImportError:  # pragma: no cover - degraded mode without PDF backend
    typst = None

from .calc import apply_calc_in_string
from .comments import strip_comments
from .diagnostics import warn_unknown_commands
from .escaping import escape_typst_outside_math, index_replacer, merge_math
from .inline_math import find_unescaped, process_math_inner
from .math_commands import (
    math_call_specs,
    normalize_friendly_calls,
    replace_math_call,
)
from .statements import _normalize_friendly_statement, process_assignment_or_define
from .state import CompileContext
from .symbols import replace_symbol_shortcuts
from .variables import check_undefined_vars, replace_defines, replace_vars


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


def _render_text_line(ctx, raw, line_no):
    """Run the text pipeline for one logical (single-line) text unit.

    Handles ``*p(...)`` raw segments and balanced ``\\ ... \\`` inline
    math pairs. Callers guarantee no cross-line unclosed math remains.
    A lone unescaped ``\\`` produces an unclosed-math diagnostic and is
    left for Typst escaping.
    """
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
    for i, token in enumerate(tokens):
        if not (token.startswith('$') and token.endswith('$') and len(token) >= 2):
            tokens[i] = token.replace('*', ctx.mult_sym)
    text = ''.join(tokens)

    # 13. Escape special Typst syntax characters outside math blocks
    # (user '$' are placeholders here; generated $...$ are preserved).
    text = escape_typst_outside_math(text, escape_dollar=True)
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
    if typst is None:
        print(
            '\n[ERROR] The `typst` Python package is not installed.\n'
            'Run `uv sync` to install it, then retry.',
            file=sys.stderr,
        )
        return False
    if fmt == 'typ':
        try:
            parent = os.path.dirname(os.path.abspath(output_path))
            if parent:
                os.makedirs(parent, exist_ok=True)
            if os.path.abspath(output_path) != os.path.abspath(typst_file):
                shutil.copyfile(typst_file, output_path)
            print(f'Successfully exported {input_str} to {output_path} (Typst source)!')
            return True
        except OSError as e:
            print(f'\n[ERROR] Typst export failed: {e}', file=sys.stderr)
            return False
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
            typst.compile(typst_file, output_path, **kwargs)
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
                typst.compile(typst_file, patterned, **kwargs)
                print(f'Successfully compiled {input_str} to {patterned} via Typst!')
                return True
            raise
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


def compile_ezmath(input_file, output_pdf=None, *, output=None, format=None, ppi=None):
    """Compile an .ezmath document via an intermediate Typst file.

    Actual processing order (per text line, after comment stripping):
        assignments/defines/draw-blocks (control lines)
          -> *p(...) raw passthrough
          -> <variable> substitution
          -> undefined-variable check (hard error)
          -> define (bare-word) substitution
          -> calc(...) evaluation
          -> inline math \\ ... \\ (multiline supported, see below)
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
    if _out_arg is None:
        # Default <base>.pdf (legacy behavior).
        base, _ = os.path.splitext(os.fspath(input_file))
        _out_arg = base + '.pdf'
    else:
        _out_arg = os.fspath(_out_arg)
    input_str = os.fspath(input_file)

    ctx = CompileContext()

    try:
        with open(input_str, 'r', encoding='utf-8') as f:
            raw_text = f.read()
    except (OSError, UnicodeDecodeError) as e:
        print(f'[Error] Cannot open input file {input_str!r}: {e}', file=sys.stderr)
        return False

    lines = strip_comments(raw_text).splitlines()
    output_lines = []
    draw_failed = False
    in_f_block = False
    block_type = None
    block_content = []
    in_math = False
    math_buf = []
    math_start = 0
    in_fence = False

    for line_no, line in enumerate(lines, start=1):
        stripped_fence = line.strip()
        if stripped_fence.startswith('```'):
            in_fence = not in_fence
            continue
        if in_fence:
            # Fenced code blocks are literal: no assignments, no math,
            # no Typst structure. Force every '$' literal.
            output_lines.append(
                escape_typst_outside_math(line.rstrip('\n')).replace('$', r'\$')
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
            combined = (wrapped + ' ' + tail).strip() if tail.strip() else wrapped
            if not combined:
                continue
            if not tail.strip():
                if wrapped:
                    output_lines.append(wrapped)
                continue
            # Tail may hold further math pairs; render as text.
            output_lines.append(_render_text_line(ctx, combined, line_no))
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

        # Handle single-line *define(...) or define(...)
        if (line.startswith('*define(') or line.startswith('define(')) and line.endswith(')'):
            prefix_len = 8 if line.startswith('*define(') else 7
            inner_stmt = line[prefix_len:-1]
            process_assignment_or_define(ctx, 'define(' + inner_stmt + ')', line_no=line_no)
            continue

        # Single-line *draw(...) — parse inner block directly
        if line.startswith('*draw(') and line.endswith(')'):
            inner = line[6:-1]
            inner = replace_vars(ctx, inner)
            inner = replace_defines(ctx, inner)
            inner = apply_calc_in_string(ctx, inner, line_no=line_no)
            drawn = _parse_draw_safe(inner, line_no=line_no)
            output_lines.append(drawn)
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
            else:
                inner = line[2:-1].strip()
            if inner and not inner.startswith('*'):
                # Heuristic: only treat as a silent block when it looks
                # like an assignment/define, otherwise fall through to
                # normal text (e.g. math grouping).
                if re.match(r'^<[^<>]+>\s*=', inner) or inner.startswith('define('):
                    process_assignment_or_define(ctx, inner, line_no=line_no)
                    continue
        if line in ('*(', '*f(', 'f(', '*draw('):
            in_f_block = True
            block_type = line
            block_content = []
            continue
        elif line == ')' and in_f_block:
            if block_type == '*draw(':
                drawn = _parse_draw_safe('\n'.join(block_content), line_no=line_no)
                output_lines.append(drawn)
                if _is_draw_error_placeholder(drawn):
                    draw_failed = True
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

        # --- Friendly blocks: # headings, - / + lists, 1. enums, = headings ---
        _friendly = _try_friendly_block(ctx, line, line_no)
        if _friendly is not None:
            output_lines.append(_friendly)
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
                output_lines.append(_render_text_line(ctx, head, line_no))
            math_buf = [rest]
            math_start = line_no
            in_math = True
            continue

        # --- Normal single-line text ---
        output_lines.append(_render_text_line(ctx, line, line_no))

    if in_math:
        print(
            f'[Error] Line {math_start}: unclosed math delimiter '
            f'\\ ... \\ — missing closing \\. Emitting buffered '
            f'content as text.',
            file=sys.stderr,
        )
        leftover = ' '.join(p for p in math_buf if p != '').strip()
        if leftover:
            output_lines.append(_render_text_line(ctx, leftover, math_start))

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

    typst_content = [
        '#set text(size: 12pt)',
        '#set page(paper: "a4", margin: 2cm)',
        '#align(center)[= Easy Math Document]',
        '',
    ]

    for index, out_line in enumerate(output_lines):
        typst_content.append(out_line + ' \\')
        if index < len(output_lines) - 1:
            typst_content.append('#v(0.65em)')

    try:
        with open(typst_file, 'w', encoding='utf-8') as tf:
            tf.write('\n'.join(typst_content) + '\n')
    except OSError as e:
        print(f'\n[ERROR] Cannot write intermediate file {typst_file!r}: {e}',
              file=sys.stderr)
        return False

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
    # `--` escape hatch: everything after it is a file operand, so files
    # with flag-like names (e.g. `--version`) stay compilable.
    positional_only = args[:1] == ['--']
    if positional_only:
        args = args[1:]
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
    else:
        positionals = list(args)

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
