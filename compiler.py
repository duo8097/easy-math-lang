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

    def replace_vars(text):
        while True:
            changed = False
            for var, val in variables.items():
                if f"<{var}>" in text:
                    text = text.replace(f"<{var}>", str(val))
                    changed = True
            if not changed:
                break
        return text

    def replace_defines(text):
        for k, v in defines.items():
            text = re.sub(rf'(?<![<\w]){re.escape(k)}(?![>\w])', v, text)
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
            parts = clean_stmt.split('=')
            if len(parts) >= 3:
                mult_sym = parts[2].strip()
            return

        if statement.startswith('define(') and statement.endswith(')'):
            inner = statement[7:-1].strip()
            if '=' in inner:
                k, v = inner.split('=', 1)
                k = k.strip()
                v = v.strip()
                v = replace_vars(v)
                def _calc_sub(m):
                    return evaluate_calc(m.group(1))
                v = re.sub(r'calc\((.*?)\)', _calc_sub, v)
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
            def _calc_sub(m):
                return evaluate_calc(m.group(1))
            val_part = re.sub(r'calc\((.*?)\)', _calc_sub, val_part)
            variables[var_name] = val_part
            return

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
        replacements = [
            ('<=>', '⇔'),
            ('=>', '⇒'),
            ('->', '→'),
        ]
        for old, new in replacements:
            text = text.replace(old, new)
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

        # Handle multi-line blocks: *( or *f( or f(
        if (line.startswith('*f(') or line.startswith('f(')) and line.endswith(')'):
            prefix_len = 3 if line.startswith('*f(') else 2
            inner = line[prefix_len:-1].strip()
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

        # 4. Evaluate calc()
        calc_matches = re.findall(r'calc\((.*?)\)', text)
        for match in calc_matches:
            result = evaluate_calc(match)
            text = text.replace(f'calc({match})', result)

        # 5. Math Constructs Formatting Phase
        def clean_inner_math(s):
            s = replace_vars(s.strip())
            s = replace_defines(s)
            s = s.replace('$', '')
            s = re.sub(r'\*(sin|cos|tan|log|ln|pi|infinity|degree)\b', r'\1', s)
            s = replace_symbol_shortcuts(s)
            return s

        def group_power_base(s):
            s = clean_inner_math(s)
            if re.search(r'\s[+\-*/]\s|[+\-*/]', s) and not (s.startswith('(') and s.endswith(')')):
                return f"({s})"
            return s

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

        text = replace_math_call(
            text,
            'frac',
            2,
            lambda args: f"$frac({clean_inner_math(args[0])}, {clean_inner_math(args[1])})$"
        )
        text = replace_math_call(
            text,
            'abs',
            1,
            lambda args: f"$abs({clean_inner_math(args[0])})$"
        )

        for fn_name in ('sin', 'cos', 'tan', 'log', 'ln'):
            text = replace_math_call(
                text,
                fn_name,
                1,
                lambda args, fn_name=fn_name: f"${fn_name}({clean_inner_math(args[0])})$"
            )

        # *pi, *infinity
        text = re.sub(r'\*pi\b', '$pi$', text)
        text = re.sub(r'\*infinity\b', '$infinity$', text)

        text = replace_math_call(
            text,
            'pow',
            2,
            lambda args: f"${group_power_base(args[0])}^({clean_inner_math(args[1])})$"
        )
        text = replace_math_call(
            text,
            'root',
            2,
            lambda args: f"$root({clean_inner_math(args[0])}, {{{clean_inner_math(args[1])}}})$"
        )
        text = replace_math_call(
            text,
            'sum',
            3,
            lambda args: f"$display(sum_({clean_inner_math(args[0])})^({clean_inner_math(args[1])}) ({clean_inner_math(args[2])}))$"
        )
        text = replace_math_call(
            text,
            'prod',
            3,
            lambda args: f"$display(product_({clean_inner_math(args[0])})^({clean_inner_math(args[1])}) ({clean_inner_math(args[2])}))$"
        )
        text = replace_math_call(
            text,
            'lim',
            2,
            lambda args: f"$lim_({clean_inner_math(args[0])}) ({clean_inner_math(args[1])})$"
        )

        # Merge adjacent math formulas like $...$ / $...$ or $...$$...$ into a single $...$
        # Also clean up any accidental double dollars inside a math block
        def merge_math(t):
            # If line is like "$lim_({cond}) (sin(x)$ / x)", merge into single $...$
            t = re.sub(r'\$([^\$]+)\$', lambda m: '$' + m.group(1).replace('$', '') + '$', t)
            return t

        text = merge_math(text)

        # base_index like A_1 or a_ij
        def index_replacer(match):
            base = match.group(1)
            index = match.group(2)
            if len(index) == 1:
                return f"${base}_{index}$"
            return f"${base}_(\"{index}\")$"

        text = re.sub(r'\b([A-Za-z]+)_([A-Za-z0-9]+)\b', index_replacer, text)

        text = replace_symbol_shortcuts(text)

        # 6. Apply multiplication symbol outside math blocks
        tokens = re.split(r'(\$.*?\$)', text)
        for i, token in enumerate(tokens):
            if not (token.startswith('$') and token.endswith('$') and len(token) >= 2):
                tokens[i] = token.replace('*', mult_sym)
        text = ''.join(tokens)

        # 7. Escape special Typst syntax characters outside of math blocks ($...$)
        text = escape_typst_outside_math(text)

        output_lines.append(text)


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
