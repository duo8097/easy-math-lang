"""Document pipeline: line loop, text phases, Typst generation."""

import re
import subprocess
import sys

import geometry

from .calc import apply_calc_in_string
from .comments import strip_comments
from .diagnostics import warn_unknown_commands
from .escaping import escape_typst_outside_math, index_replacer, merge_math
from .math_commands import math_call_specs, replace_math_call
from .statements import process_assignment_or_define
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


def compile_ezmath(input_file, output_pdf=None):
    """Compile an .ezmath document to PDF via an intermediate Typst file.

    Actual processing order (per text line, after comment stripping):
        assignments/defines/draw-blocks (control lines)
          -> *p(...) raw passthrough
          -> <variable> substitution
          -> undefined-variable check (hard error)
          -> define (bare-word) substitution
          -> calc(...) evaluation
          -> math commands (*frac, *pow, *root, *sum, *prod, *lim, ...)
          -> unknown *command(...) warning
          -> *pi / *infinity
          -> subscript notation (A_1, outside math only)
          -> symbol shortcuts (outside math only)
          -> multiplication-symbol replacement (outside math only)
          -> Typst escaping (outside math only)
        Finally: Typst file generation + `typst compile`.
    """
    if output_pdf is None:
        output_pdf = input_file.rsplit('.', 1)[0] + '.pdf'

    ctx = CompileContext()

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            raw_text = f.read()
    except OSError as e:
        print(f'[Error] Cannot open input file {input_file!r}: {e}', file=sys.stderr)
        return

    lines = strip_comments(raw_text).splitlines()
    output_lines = []
    in_f_block = False
    block_type = None
    block_content = []

    for line_no, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue
        if line.startswith('```'):
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
            output_lines.append(geometry.parse_draw_block(inner))
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
                output_lines.append(geometry.parse_draw_block('\n'.join(block_content)))
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

        # --- Text Output Formatting Phase ---
        # 1. *p(...): raw passthrough segments (balanced parens, multiple
        # per line allowed). Raw parts bypass all later rules; surrounding
        # text flows through the normal pipeline. Bare p(...) is text.
        p_segs = _extract_p_segments(line)
        if any(is_raw for is_raw, _ in p_segs):
            placeholders = {}
            text = ''
            for k, (is_raw, content) in enumerate(p_segs):
                if is_raw:
                    ph = f'\x00P{k}\x00'
                    placeholders[ph] = escape_typst_outside_math(content)
                    text += ph
                else:
                    text += content
        else:
            text = line
            placeholders = {}

        # 2. Substitute variables <var>
        text = replace_vars(ctx, text)

        # 3. Check for undefined variables (hard error)
        text = check_undefined_vars(text, line_no)

        # 4. Substitute defines
        text = replace_defines(ctx, text)

        # 5. Evaluate calc()
        text = apply_calc_in_string(ctx, text, line_no=line_no)

        # 6. Math constructs
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
                # snake_case words like my_file.
                tokens_for_index[i] = re.sub(
                    r'\b([A-Za-z])_([A-Za-z0-9]+)\b', index_replacer, tok
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
        text = escape_typst_outside_math(text)

        for ph, raw in placeholders.items():
            text = text.replace(ph, raw)

        output_lines.append(text)

    # Warn if a block was never closed
    if in_f_block:
        print(
            "[WARNING] Unclosed block '(' detected — content inside may have been silently consumed.",
            file=sys.stderr,
        )

    # ------------------------------------------------------------------
    # Generate Typst file
    # ------------------------------------------------------------------
    typst_file = input_file.rsplit('.', 1)[0] + '.typ'

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

    with open(typst_file, 'w', encoding='utf-8') as tf:
        tf.write('\n'.join(typst_content) + '\n')

    print(f'Generated intermediate file: {typst_file}')

    # ------------------------------------------------------------------
    # Compile with Typst
    # ------------------------------------------------------------------
    print('Compiling PDF with Typst...')
    try:
        subprocess.run(
            ['typst', 'compile', '--ignore-system-fonts', typst_file, output_pdf],
            check=True,
        )
        print(f'Successfully compiled {input_file} to {output_pdf} via Typst!')
    except FileNotFoundError:
        print(
            '\n[ERROR] Typst is not installed or not in PATH.\n'
            'Install it from https://typst.app before running easy-math-lang.',
            file=sys.stderr,
        )
    except subprocess.CalledProcessError as e:
        print(f'\n[ERROR] Typst compilation failed: {e}', file=sys.stderr)


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print('Usage: easy-math-lang <input.ezmath> [output.pdf]')
        sys.exit(0 if len(sys.argv) > 1 else 1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else input_file.rsplit('.', 1)[0] + '.pdf'
    compile_ezmath(input_file, output_file)


if __name__ == '__main__':
    main()
