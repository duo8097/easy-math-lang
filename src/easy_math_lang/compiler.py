import re
import sys
import subprocess
import ast
import operator
from . import geometry

# ---------------------------------------------------------------------------
# Known DSL commands (used for unknown-command warning)
# ---------------------------------------------------------------------------

KNOWN_COMMANDS = {
    'define', 'p',
    'frac', 'abs', 'sin', 'cos', 'tan', 'log', 'ln',
    'pow', 'root', 'sum', 'prod', 'lim',
    # symbol shortcuts handled separately: pi, infinity, degree, ...
}


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

    variables = {}
    defines = {}
    mult_sym = '*'

    with open(input_file, 'r', encoding='utf-8') as f:
        raw_text = f.read()

    # ------------------------------------------------------------------
    # Comment stripping
    # ------------------------------------------------------------------
    def strip_comments(text):
        cleaned_lines = []
        for raw_line in text.splitlines():
            # Protect URL schemes (https://, http://, ftp://) from // comment stripping
            placeholder = '\x00URLSLASH\x00'
            line_prot = re.sub(r'([A-Za-z][A-Za-z0-9+.-]*://)', lambda m: m.group(1).replace('/', placeholder), raw_line)
            if '//' in line_prot:
                line_prot = line_prot.split('//', 1)[0]
            line = line_prot.replace(placeholder, '/')
            cleaned_lines.append(line)
        return '\n'.join(cleaned_lines)

    lines = strip_comments(raw_text).splitlines()
    output_lines = []
    in_f_block = False
    block_type = None
    block_content = []

    # ------------------------------------------------------------------
    # Safe arithmetic evaluator
    # ------------------------------------------------------------------
    safe_operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    # ------------------------------------------------------------------
    # Variable substitution (circular-reference safe)
    # ------------------------------------------------------------------
    def replace_vars(text, _visited=None):
        if _visited is None:
            _visited = set()
        while True:
            changed = False
            for var, val in variables.items():
                token = f'<{var}>'
                if token in text:
                    if var in _visited:
                        print(
                            f'[WARNING] Circular variable reference detected: <{var}>. '
                            f'Leaving unexpanded.',
                            file=sys.stderr,
                        )
                        continue
                    _visited.add(var)
                    text = text.replace(token, str(val))
                    changed = True
            if not changed:
                break
        return text

    # ------------------------------------------------------------------
    # Define substitution
    # ------------------------------------------------------------------
    def replace_defines(text):
        # Recursive expansion (up to 10 passes) so chained defines resolve
        # regardless of definition order.
        for _ in range(10):
            changed = False
            for k, v in defines.items():
                new_text = re.sub(rf'\b{re.escape(k)}\b', v, text)
                if new_text != text:
                    changed = True
                    text = new_text
            if not changed:
                break
        return text

    # ------------------------------------------------------------------
    # Undefined variable detection (hard error)
    # ------------------------------------------------------------------
    def check_undefined_vars(text, line_no):
        remaining = re.findall(r'<([^<>]+)>', text)
        for name in remaining:
            # Only flag identifier-like names (tmp1, width). Symbol
            # shortcuts such as <=> / -> / => contain non-identifier
            # chars and are handled later by replace_symbol_shortcuts.
            if not re.fullmatch(r'\s*[A-Za-z_][A-Za-z0-9_]*\s*', name):
                continue
            print(
                f'[Error] Line {line_no}: undefined variable <{name}>',
                file=sys.stderr,
            )
            text = text.replace(f'<{name}>', f'[UNDEFINED: <{name}>]')
        return text

    # ------------------------------------------------------------------
    # calc() evaluator (depth-counter, handles nested parentheses)
    # ------------------------------------------------------------------
    def evaluate_calc(expression, line_no=None):
        expression = replace_vars(expression)
        expression = replace_defines(expression)
        try:
            # Only treat mult_sym as an operator when spaced, so decimals
            # (3.14) and words containing 'x' are not corrupted.
            if mult_sym != '*':
                eval_expr = re.sub(
                    r'\s' + re.escape(mult_sym) + r'\s', ' * ', f' {expression} '
                ).strip()
            else:
                eval_expr = expression.strip()
            eval_expr = re.sub(r'(?<=\d)\s+(?=\d)', '', eval_expr)
            eval_expr = eval_expr.replace('^', '**')
            tree = ast.parse(eval_expr, mode='eval')

            def eval_node(node):
                if isinstance(node, ast.Expression):
                    return eval_node(node.body)
                if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                    return node.value
                if isinstance(node, ast.BinOp) and type(node.op) in safe_operators:
                    left = eval_node(node.left)
                    right = eval_node(node.right)
                    if isinstance(node.op, ast.Div) and right == 0:
                        raise ZeroDivisionError("division by zero")
                    return safe_operators[type(node.op)](left, right)
                if isinstance(node, ast.UnaryOp) and type(node.op) in safe_operators:
                    return safe_operators[type(node.op)](eval_node(node.operand))
                raise ValueError('calc only supports numbers and math operators')

            res = eval_node(tree)
            if isinstance(res, float) and res.is_integer():
                res = int(res)
            return str(res)
        except ZeroDivisionError as e:
            loc = f' Line {line_no}:' if line_no else ''
            print(f'[Error]{loc} calc(): division by zero in: {expression!r}', file=sys.stderr)
            return f'[Calc Error: division by zero]'
        except Exception as e:
            loc = f' Line {line_no}:' if line_no else ''
            print(f'[Error]{loc} calc(): {e} in: {expression!r}', file=sys.stderr)
            return f'[Calc Error: {e}]'

    def _apply_calc_in_string(text, line_no=None):
        out = []
        pos = 0
        pattern = re.compile(r'calc\(')
        while True:
            m = pattern.search(text, pos)
            if not m:
                out.append(text[pos:])
                break
            out.append(text[pos:m.start()])
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
                loc = f' Line {line_no}:' if line_no else ''
                print(
                    f'[Error]{loc} calc(): unclosed parenthesis — leaving as-is',
                    file=sys.stderr,
                )
                out.append(text[m.start():])
                break
            expr = text[start:i - 1]
            out.append(evaluate_calc(expr, line_no=line_no))
            pos = i
        return ''.join(out)

    # ------------------------------------------------------------------
    # Assignment / define processing
    # ------------------------------------------------------------------
    def process_assignment_or_define(statement, line_no=None):
        nonlocal mult_sym
        statement = statement.strip()
        if not statement:
            return

        if statement.startswith('define(write_type.multiplication'):
            clean_stmt = statement[:-1] if statement.endswith(')') else statement
            # Support both documented single-'=' form ( = .) and legacy
            # double-'=' form ( = * = .): value is always after the last '='.
            parts = clean_stmt.split('=')
            if len(parts) >= 2:
                mult_sym = parts[-1].strip()
            return

        if statement.startswith('define(') and statement.endswith(')'):
            inner = statement[7:-1].strip()
            if '=' in inner:
                k, v = inner.split('=', 1)
                k = k.strip()
                v = v.strip()
                if len(k) == 1:
                    print(
                        f"[WARNING] Line {line_no}: Single-character define name '{k}' "
                        f"may corrupt plain text.",
                        file=sys.stderr,
                    )
                v = replace_vars(v)
                v = _apply_calc_in_string(v, line_no=line_no)
                defines[k] = v
                variables[k] = v
            return

        if statement.startswith('<') and '=' in statement:
            var_part, val_part = statement.split('=', 1)
            var_name = var_part.strip()
            if var_name.startswith('<') and var_name.endswith('>'):
                var_name = var_name[1:-1].strip()
            val_part = val_part.strip()
            val_part = replace_vars(val_part)
            val_part = _apply_calc_in_string(val_part, line_no=line_no)
            variables[var_name] = val_part
            return

    # ------------------------------------------------------------------
    # Typst escaping (only outside math blocks)
    # ------------------------------------------------------------------
    def escape_typst_outside_math(content):
        tokens = re.split(r'(\$.*?\$)', content)
        for i, token in enumerate(tokens):
            if not (token.startswith('$') and token.endswith('$') and len(token) >= 2):
                tokens[i] = (
                    token
                    .replace('\\', r'\\')
                    .replace('*', r'\*')
                    .replace('_', r'\_')
                    .replace('<', r'\<')
                    .replace('>', r'\>')
                    .replace('#', r'\#')
                    .replace('@', r'\@')
                    .replace('`', r'\`')
                    # NOTE: '/' is escaped because Typst treats a leading '/' as a
                    # definition-list term.  This is intentional and has been kept
                    # unchanged pending a concrete regression report.
                    .replace('/', r'\/')
                )
        return ''.join(tokens)

    # ------------------------------------------------------------------
    # Top-level argument splitter (depth-aware)
    # ------------------------------------------------------------------
    def split_top_level_args(args):
        parts = []
        current = []
        depth = 0
        for char in args:
            if char == '(':
                depth += 1
            elif char == ')' and depth > 0:
                depth -= 1
            if char == ';' and depth == 0:
                parts.append(''.join(current).strip())
                current = []
            else:
                current.append(char)
        parts.append(''.join(current).strip())
        return parts

    # ------------------------------------------------------------------
    # Symbol shortcuts
    # ------------------------------------------------------------------
    def replace_symbol_shortcuts(text):
        symbol_replacements = [
            ('|->', '↦'),
            ('<->', '↔'),
            ('<=>', '⇔'),
            ('=>', '⇒'),
            ('<=', '≤'),
            ('>=', '≥'),
            ('!=', '≠'),
            ('&&', '∧'),
            ('||', '∨'),
            ('==', '='),
            ('+-', '±'),
            ('-+', '∓'),
            ('...', '…'),
            ('::', '∷'),
            ('~=~', '≅'),
            ('~=', '≈'),
            ('~~', '≈'),
            ('**', '⋅'),
            ('<-', '←'),
            ('->', '→'),
        ]
        word_replacements = [
            ('leq', '≤'), ('le', '≤'), ('geq', '≥'), ('ge', '≥'),
            ('neq', '≠'), ('ne', '≠'), ('approx', '≈'), ('cong', '≅'),
            ('pm', '±'), ('mp', '∓'), ('prop', '∝'), ('propto', '∝'),
            ('xx', '×'), ('times', '×'), ('cdot', '⋅'), ('div', '÷'),
            ('sqrt', '√'), ('cbrt', '∛'), ('deg', '°'), ('degree', '°'),
            ('angle', '∠'), ('triangle', '△'), ('parallel', '∥'), ('perp', '⊥'),
            ('infty', '∞'), ('infinity', '∞'), ('forall', '∀'), ('exists', '∃'),
            ('notin', '∉'), ('isin', '∈'), ('subseteq', '⊆'), ('supseteq', '⊇'),
            ('superseteq', '⊇'), ('subset', '⊂'), ('supset', '⊃'), ('superset', '⊃'),
            ('union', '∪'), ('intersect', '∩'), ('intersection', '∩'),
            ('emptyset', '∅'), ('empty', '∅'),
            ('land', '∧'), ('lor', '∨'), ('lnot', '¬'),
            ('therefore', '∴'), ('because', '∵'),
            ('alpha', 'α'), ('beta', 'β'), ('gamma', 'γ'), ('delta', 'δ'),
            ('epsilon', 'ε'), ('theta', 'θ'), ('lambda', 'λ'), ('mu', 'μ'),
            ('pi', 'π'), ('sigma', 'σ'), ('omega', 'ω'),
            ('Delta', 'Δ'), ('Sigma', 'Σ'), ('Omega', 'Ω'),
        ]
        for old, new in symbol_replacements:
            text = text.replace(old, new)
        for old, new in word_replacements:
            text = re.sub(rf'\*{re.escape(old)}\b', new, text)
        return text

    # ------------------------------------------------------------------
    # Math call helpers
    # ------------------------------------------------------------------
    def replace_math_call(text, name, min_args, formatter):
        pattern = re.compile(r'\*' + re.escape(name) + r'\(')
        pos = 0
        out = []
        while True:
            match = pattern.search(text, pos)
            if not match:
                out.append(text[pos:])
                break
            out.append(text[pos:match.start()])
            start = match.end()
            depth = 1
            i = start
            while i < len(text) and depth > 0:
                if text[i] == '(':
                    depth += 1
                elif text[i] == ')':
                    depth -= 1
                i += 1
            if depth != 0:
                out.append(text[match.start():])
                break
            args = split_top_level_args(text[start:i - 1])
            if len(args) < min_args:
                out.append(text[match.start():i])
            else:
                out.append(formatter(args))
            pos = i
        return ''.join(out)

    def clean_inner_math(s):
        s = replace_vars(s.strip())
        s = replace_defines(s)
        s = _apply_calc_in_string(s)
        s = s.replace('$', '')
        s = replace_symbol_shortcuts(s)
        for fn_name, fn_min, fn_fmt in _math_call_specs():
            s = replace_math_call(s, fn_name, fn_min, fn_fmt)
        s = re.sub(r'\$([^$]+)\$', r'\1', s)
        return s

    def _math_call_specs():
        return [
            ('frac', 2,
             lambda args: f"$frac({clean_inner_math(args[0])}, {clean_inner_math(args[1])})$"),
            ('abs', 1,
             lambda args: f"$abs({clean_inner_math(args[0])})$"),
            ('sin', 1, lambda args: f"$sin({clean_inner_math(args[0])})$"),
            ('cos', 1, lambda args: f"$cos({clean_inner_math(args[0])})$"),
            ('tan', 1, lambda args: f"$tan({clean_inner_math(args[0])})$"),
            ('log', 1, lambda args: f"$log({clean_inner_math(args[0])})$"),
            ('ln',  1, lambda args: f"$ln({clean_inner_math(args[0])})$"),
            ('pow', 2,
             lambda args: f"${group_power_base(args[0])}^({clean_inner_math(args[1])})$"),
            ('root', 2,
             lambda args: f"$root({clean_inner_math(args[0])}, {{{clean_inner_math(args[1])}}})$"),
            ('sum', 3,
             lambda args: (
                 f"$display(sum_({clean_inner_math(args[0])})^({clean_inner_math(args[1])}) "
                 f"({clean_inner_math(args[2])}))$"
             )),
            ('prod', 3,
             lambda args: (
                 f"$display(product_({clean_inner_math(args[0])})^({clean_inner_math(args[1])}) "
                 f"({clean_inner_math(args[2])}))$"
             )),
            ('lim', 2,
             lambda args: f"$lim_({clean_inner_math(args[0])}) ({clean_inner_math(args[1])})$"),
        ]

    def group_power_base(s):
        s = clean_inner_math(s)
        if re.search(r'\s[+\-*/]\s|[+\-*/]', s) and not (s.startswith('(') and s.endswith(')')):
            return f'({s})'
        return s

    # ------------------------------------------------------------------
    # Unknown *command warning (allowlist-based)
    # ------------------------------------------------------------------
    def warn_unknown_commands(text, line_no):
        """Warn if *name(...) appears where name is not in KNOWN_COMMANDS."""
        for m in re.finditer(r'\*([A-Za-z][A-Za-z0-9_]*)\s*\(', text):
            cmd = m.group(1)
            if cmd not in KNOWN_COMMANDS:
                print(
                    f'[Warning] Line {line_no}: unknown command *{cmd}(...) — treated as plain text',
                    file=sys.stderr,
                )

    # ------------------------------------------------------------------
    # Main line processing loop
    # ------------------------------------------------------------------
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
            process_assignment_or_define('define(' + inner_stmt + ')', line_no=line_no)
            continue

        # Single-line *draw(...) — parse inner block directly
        if line.startswith('*draw(') and line.endswith(')'):
            inner = line[6:-1]
            inner = replace_vars(inner)
            inner = replace_defines(inner)
            inner = _apply_calc_in_string(inner, line_no=line_no)
            output_lines.append(geometry.parse_draw_block(inner))
            continue

        # Multi-line blocks: *( or *f( or f( or *draw(
        if line.startswith('*f(') and line.endswith(')'):
            inner = line[3:-1].strip()
            if not (inner.startswith('frac(') or inner.startswith('root(')):
                process_assignment_or_define(inner, line_no=line_no)
                continue
        elif line in ('*(', '*f(', 'f(', '*draw('):
            in_f_block = True
            block_type = line
            block_content = []
            continue
        elif line == ')' and in_f_block:
            if block_type == '*draw(':
                output_lines.append(geometry.parse_draw_block('\n'.join(block_content)))
            else:
                for stmt in block_content:
                    process_assignment_or_define(stmt, line_no=line_no)
            in_f_block = False
            continue

        if in_f_block:
            block_content.append(line)
            continue

        if re.match(r'^<[^<>]+>\s*=', line):
            process_assignment_or_define(line, line_no=line_no)
            continue

        # --- Text Output Formatting Phase ---
        text = line

        # 1. *p(...): Print raw text directly, bypassing all other rules
        # Spec requires the '*' prefix, so bare p(...) is normal text.
        p_match = re.match(r'^\*p\((.*)\)$', text)
        if p_match:
            output_lines.append(escape_typst_outside_math(p_match.group(1)))
            continue

        # 2. Substitute variables <var>
        text = replace_vars(text)

        # 3. Check for undefined variables (hard error)
        text = check_undefined_vars(text, line_no)

        # 4. Substitute defines
        text = replace_defines(text)

        # 5. Evaluate calc()
        text = _apply_calc_in_string(text, line_no=line_no)

        # 6. Math constructs
        for fn_name, fn_min, fn_fmt in _math_call_specs():
            text = replace_math_call(text, fn_name, fn_min, fn_fmt)

        # 7. Warn about unknown *command(...)
        warn_unknown_commands(text, line_no)

        # 8. *pi, *infinity
        text = re.sub(r'\*pi\b', '$pi$', text)
        text = re.sub(r'\*infinity\b', '$infinity$', text)

        # 9. Merge/clean adjacent math blocks
        def merge_math(t):
            t = re.sub(r'\$([^\$]+)\$', lambda m: '$' + m.group(1).replace('$', '') + '$', t)
            return t

        text = merge_math(text)

        # 10. Subscript notation A_1 / a_ij (outside math blocks only)
        def index_replacer(match):
            base = match.group(1)
            index = match.group(2)
            if len(index) == 1:
                return f'${base}_{index}$'
            return f'${base}_("{index}")$'

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
                tokens[i] = token.replace('*', mult_sym)
        text = ''.join(tokens)

        # 13. Escape special Typst syntax characters outside math blocks
        text = escape_typst_outside_math(text)

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
    if len(sys.argv) < 2:
        print('Usage: easy-math-lang <input.ezmath> [output.pdf]')
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else input_file.rsplit('.', 1)[0] + '.pdf'
    compile_ezmath(input_file, output_file)


if __name__ == '__main__':
    main()
