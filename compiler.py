import re
import sys
import subprocess
import ast
import operator

def compile_ezmath(input_file, output_pdf=None):
    if output_pdf is None:
        output_pdf = input_file.rsplit('.', 1)[0] + '.pdf'

    variables = {}
    defines = {}
    mult_sym = '*'

    with open(input_file, 'r', encoding='utf-8') as f:
        raw_text = f.read()

    def strip_comments(text):
        cleaned_lines = []
        for raw_line in text.splitlines():
            line = re.sub(r'//.*?//', '', raw_line)
            if '//' in line:
                line = line.split('//', 1)[0]
            cleaned_lines.append(line)
        return "\n".join(cleaned_lines)

    lines = strip_comments(raw_text).splitlines()
    output_lines = []
    in_f_block = False

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

    # Bug 16 fix: detect circular variable references with a visited set
    def replace_vars(text, _visited=None):
        if _visited is None:
            _visited = set()
        while True:
            changed = False
            for var, val in variables.items():
                token = f"<{var}>"
                if token in text:
                    if var in _visited:
                        print(f"[WARNING] Circular variable reference detected: <{var}>. Leaving unexpanded.")
                        continue
                    _visited.add(var)
                    text = text.replace(token, str(val))
                    changed = True
            if not changed:
                break
        return text

    # Bug 17 fix: use proper \b word boundaries instead of manual lookarounds
    def replace_defines(text):
        for k, v in defines.items():
            text = re.sub(rf'\b{re.escape(k)}\b', v, text)
        return text

    def evaluate_calc(expression):
        # Substitute variables and defines first
        expression = replace_vars(expression)
        expression = replace_defines(expression)
        try:
            eval_expr = expression.replace(mult_sym, '*').strip()
            eval_expr = re.sub(r'(?<=\d)\s+(?=\d)', '', eval_expr)
            eval_expr = eval_expr.replace('^', '**')
            tree = ast.parse(eval_expr, mode='eval')

            def eval_node(node):
                if isinstance(node, ast.Expression):
                    return eval_node(node.body)
                if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                    return node.value
                if isinstance(node, ast.BinOp) and type(node.op) in safe_operators:
                    return safe_operators[type(node.op)](eval_node(node.left), eval_node(node.right))
                if isinstance(node, ast.UnaryOp) and type(node.op) in safe_operators:
                    return safe_operators[type(node.op)](eval_node(node.operand))
                raise ValueError("calc only supports numbers and math operators")

            res = eval_node(tree)
            if isinstance(res, float) and res.is_integer():
                res = int(res)
            return str(res)
        except Exception as e:
            return f"[Calc Error: {e}]"

    def process_assignment_or_define(statement):
        nonlocal mult_sym
        statement = statement.strip()
        if not statement:
            return

        if statement.startswith('define(write_type.multiplication'):
            clean_stmt = statement[:-1] if statement.endswith(')') else statement
            # Bug 1 fix: split('=', 2) so values containing '=' are captured whole
            parts = clean_stmt.split('=', 2)
            if len(parts) >= 3:
                mult_sym = parts[2].strip()
            return

        if statement.startswith('define(') and statement.endswith(')'):
            inner = statement[7:-1].strip()
            if '=' in inner:
                k, v = inner.split('=', 1)
                k = k.strip()
                v = v.strip()
                if len(k) == 1:
                    print(f"[WARNING] Single-character define name '{k}' may corrupt plain text.")
                v = replace_vars(v)
                v = _apply_calc_in_string(v)
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
            val_part = _apply_calc_in_string(val_part)
            variables[var_name] = val_part
            return

    # Bug 9 fix: depth-counter based calc() extractor, handles nested parentheses
    def _apply_calc_in_string(text):
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
                # unclosed — leave as-is
                out.append(text[m.start():])
                break
            expr = text[start:i - 1]
            out.append(evaluate_calc(expr))
            pos = i
        return ''.join(out)

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
                    # Note: '/' IS escaped because Typst treats a leading '/' as a
                    # definition-list term (/ term: def) and will error without escaping.
                    .replace('/', r'\/')
                )
        return ''.join(tokens)

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
            ('leq', '≤'),
            ('le', '≤'),
            ('geq', '≥'),
            ('ge', '≥'),
            ('neq', '≠'),
            ('ne', '≠'),
            ('approx', '≈'),
            ('cong', '≅'),
            ('pm', '±'),
            ('mp', '∓'),
            ('prop', '∝'),
            ('propto', '∝'),
            ('xx', '×'),
            ('times', '×'),
            ('cdot', '⋅'),
            ('div', '÷'),
            ('sqrt', '√'),
            ('cbrt', '∛'),
            ('deg', '°'),
            ('degree', '°'),
            ('angle', '∠'),
            ('triangle', '△'),
            ('parallel', '∥'),
            ('perp', '⊥'),
            ('infty', '∞'),
            ('infinity', '∞'),
            ('forall', '∀'),
            ('exists', '∃'),
            ('notin', '∉'),
            ('isin', '∈'),
            ('subseteq', '⊆'),
            ('supseteq', '⊇'),
            ('superseteq', '⊇'),
            ('subset', '⊂'),
            ('supset', '⊃'),
            ('superset', '⊃'),
            ('union', '∪'),
            ('intersect', '∩'),
            ('intersection', '∩'),
            ('emptyset', '∅'),
            ('empty', '∅'),
            ('land', '∧'),
            ('lor', '∨'),
            ('lnot', '¬'),
            ('therefore', '∴'),
            ('because', '∵'),
            ('alpha', 'α'),
            ('beta', 'β'),
            ('gamma', 'γ'),
            ('delta', 'δ'),
            ('epsilon', 'ε'),
            ('theta', 'θ'),
            ('lambda', 'λ'),
            ('mu', 'μ'),
            ('pi', 'π'),
            ('sigma', 'σ'),
            ('omega', 'ω'),
            ('Delta', 'Δ'),
            ('Sigma', 'Σ'),
            ('Omega', 'Ω'),
        ]
        for old, new in symbol_replacements:
            text = text.replace(old, new)
        for old, new in word_replacements:
            text = re.sub(rf'\b{re.escape(old)}\b', new, text)
        return text

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith('```'):
            continue

        # Handle single-line *define(...) or define(...)
        if (line.startswith('*define(') or line.startswith('define(')) and line.endswith(')'):
            prefix_len = 8 if line.startswith('*define(') else 7
            inner_stmt = line[prefix_len:-1]
            process_assignment_or_define('define(' + inner_stmt + ')')
            continue

        # Bug 14 fix: only *f(...) triggers single-line block mode — bare f(...) is plain text
        # Handle multi-line blocks: *( or *f( or f(
        if line.startswith('*f(') and line.endswith(')'):
            inner = line[3:-1].strip()
            if inner.startswith('frac(') or inner.startswith('root('):
                pass
            else:
                process_assignment_or_define(inner)
                continue
        elif line in ('*(', '*f(', 'f('):
            in_f_block = True
            continue
        elif line == ')' and in_f_block:
            in_f_block = False
            continue

        if in_f_block:
            process_assignment_or_define(line)
            continue

        if re.match(r'^<[^<>]+>\s*=', line):
            process_assignment_or_define(line)
            continue

        # --- Text Output Formatting Phase ---
        text = line

        # 1. *p(...) or p(...): Print raw text directly, bypassing all other rules
        p_match = re.match(r'^\*?p\((.*)\)$', text)
        if p_match:
            output_lines.append(escape_typst_outside_math(p_match.group(1)))
            continue

        # 2. Substitute variables <var>
        text = replace_vars(text)

        # 3. Substitute defines
        text = replace_defines(text)

        # 4. Evaluate calc() — using depth-counter extractor (Bug 9 fix)
        text = _apply_calc_in_string(text)

        # 5. Math Constructs Formatting Phase
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

        # Bug 15 fix: clean_inner_math() recursively processes nested math calls
        # by applying all math-function replacers and then stripping wrapper $...$
        def clean_inner_math(s):
            s = replace_vars(s.strip())
            s = replace_defines(s)
            s = s.replace('$', '')
            s = re.sub(r'\*(sin|cos|tan|log|ln|pi|infinity|degree)\b', r'\1', s)
            s = replace_symbol_shortcuts(s)

            # Recursively resolve nested math calls
            for fn_name, fn_min, fn_fmt in _math_call_specs():
                s = replace_math_call(s, fn_name, fn_min, fn_fmt)
            # Strip $...$ wrappers added by nested replace_math_call so the result
            # embeds cleanly inside the parent math block
            s = re.sub(r'\$([^$]+)\$', r'\1', s)
            return s

        # Specs for all math functions — used both in the main loop and recursively
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
                 lambda args: f"$display(sum_({clean_inner_math(args[0])})^({clean_inner_math(args[1])}) ({clean_inner_math(args[2])}))$"),
                ('prod', 3,
                 lambda args: f"$display(product_({clean_inner_math(args[0])})^({clean_inner_math(args[1])}) ({clean_inner_math(args[2])}))$"),
                ('lim', 2,
                 lambda args: f"$lim_({clean_inner_math(args[0])}) ({clean_inner_math(args[1])})$"),
            ]

        def group_power_base(s):
            s = clean_inner_math(s)
            if re.search(r'\s[+\-*/]\s|[+\-*/]', s) and not (s.startswith('(') and s.endswith(')')):
                return f"({s})"
            return s

        for fn_name, fn_min, fn_fmt in _math_call_specs():
            text = replace_math_call(text, fn_name, fn_min, fn_fmt)

        # *pi, *infinity
        text = re.sub(r'\*pi\b', '$pi$', text)
        text = re.sub(r'\*infinity\b', '$infinity$', text)

        # Merge adjacent math formulas like $...$ / $...$ or $...$$..$$ into a single $...$
        # Also clean up any accidental double dollars inside a math block
        def merge_math(t):
            t = re.sub(r'\$([^\$]+)\$', lambda m: '$' + m.group(1).replace('$', '') + '$', t)
            return t

        text = merge_math(text)

        # base_index like A_1 or a_ij
        # Bug 5 fix: only apply index_replacer to plain-text tokens, not inside $...$
        def index_replacer(match):
            base = match.group(1)
            index = match.group(2)
            if len(index) == 1:
                return f"${base}_{index}$"
            return f"${base}_(\"{ index}\")$"

        tokens_for_index = re.split(r'(\$.*?\$)', text)
        for i, tok in enumerate(tokens_for_index):
            if not (tok.startswith('$') and tok.endswith('$') and len(tok) >= 2):
                tokens_for_index[i] = re.sub(r'\b([A-Za-z]+)_([A-Za-z0-9]+)\b', index_replacer, tok)
        text = ''.join(tokens_for_index)

        # Bug 11 fix: apply replace_symbol_shortcuts only to non-math tokens
        tokens_for_sym = re.split(r'(\$.*?\$)', text)
        for i, tok in enumerate(tokens_for_sym):
            if not (tok.startswith('$') and tok.endswith('$') and len(tok) >= 2):
                tokens_for_sym[i] = replace_symbol_shortcuts(tok)
        text = ''.join(tokens_for_sym)

        # 6. Apply multiplication symbol outside math blocks
        tokens = re.split(r'(\$.*?\$)', text)
        for i, token in enumerate(tokens):
            if not (token.startswith('$') and token.endswith('$') and len(token) >= 2):
                tokens[i] = token.replace('*', mult_sym)
        text = ''.join(tokens)

        # 7. Escape special Typst syntax characters outside of math blocks ($...$)
        text = escape_typst_outside_math(text)

        output_lines.append(text)

    # Bug 18 fix: warn if a block was never closed
    if in_f_block:
        print("[WARNING] Unclosed block '(' detected — content inside may have been silently consumed.")

    # Generate Typst File
    typst_file = input_file.rsplit('.', 1)[0] + '.typ'

    typst_content = [
        "#set text(size: 12pt)",
        "#set page(paper: \"a4\", margin: 2cm)",
        "#align(center)[= Easy Math Document]",
        ""
    ]

    for index, out_line in enumerate(output_lines):
        typst_content.append(out_line + " \\")
        if index < len(output_lines) - 1:
            typst_content.append("#v(0.65em)")

    with open(typst_file, 'w', encoding='utf-8') as tf:
        tf.write("\n".join(typst_content) + "\n")

    print(f"Generated intermediate file: {typst_file}")

    # Compile using Typst
    print("Compiling PDF with Typst...")
    try:
        subprocess.run(["typst", "compile", "--ignore-system-fonts", typst_file, output_pdf], check=True)
        print(f"Successfully compiled {input_file} to {output_pdf} via Typst!")
    except FileNotFoundError:
        print("\n[ERROR] Typst is not installed or not in PATH.")
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Typst compilation failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python compiler.py <input.ezmath> [output.pdf]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else input_file.rsplit('.', 1)[0] + '.pdf'
    compile_ezmath(input_file, output_file)
