import re
import sys
import os
import subprocess

def compile_ezmath(input_file, output_pdf=None):
    if output_pdf is None:
        output_pdf = input_file.rsplit('.', 1)[0] + '.pdf'

    variables = {}
    defines = {}
    mult_sym = '*'

    with open(input_file, 'r', encoding='utf-8') as f:
        raw_text = f.read()

    # Rule: "// //": comment, can be inline //comment// or line-ending //
    # Notice rule.txt: "*f(define(write_type.multiplication = * = //sth like . in vn or x in global, i use . because im vn btw// .))"
    # Remove paired comments //...// first:
    raw_text = re.sub(r'//.*?//', '', raw_text, flags=re.DOTALL)

    lines = raw_text.splitlines()
    output_lines = []
    in_f_block = False

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

    def evaluate_calc(expression):
        # Substitute variables and defines first
        expression = replace_vars(expression)
        for k, v in defines.items():
            if k in expression:
                expression = expression.replace(k, v)
        try:
            eval_expr = expression.replace(mult_sym, '*').strip()
            res = eval(eval_expr)
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
                tokens[i] = token.replace('\\', r'\\').replace('*', r'\*').replace('_', r'\_')
        return ''.join(tokens)

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Remaining comments //
        if '//' in line:
            line = line.split('//')[0].strip()
            if not line:
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
        for k, v in defines.items():
            if k in text:
                text = text.replace(k, v)

        # 4. Evaluate calc()
        calc_matches = re.findall(r'calc\((.*?)\)', text)
        for match in calc_matches:
            result = evaluate_calc(match)
            text = text.replace(f'calc({match})', result)

        # 5. Math Constructs Formatting Phase
        def clean_inner_math(s):
            s = replace_vars(s.strip())
            for k, v in defines.items():
                if k in s:
                    s = s.replace(k, v)
            s = s.replace('$', '')
            s = re.sub(r'\*(sin|cos|tan|log|ln|pi|infinity|degree)\b', r'\1', s)
            return s

        # *frac(numerator ; denominator)
        def frac_replacer(match):
            numerator = clean_inner_math(match.group(1))
            denominator = clean_inner_math(match.group(2))
            return f"$frac({numerator}, {denominator})$"

        text = re.sub(r'(?:\*?f\(frac|\*frac)\((.*?);(.*?)\)\)?', frac_replacer, text)

        # *root(index ; radicand)
        def root_replacer(match):
            index = clean_inner_math(match.group(1))
            radicand = clean_inner_math(match.group(2))
            return f"$root({index}, {{{radicand}}})$"

        text = re.sub(r'(?:\*?f\(root|\*root)\((.*?);(.*?)\)\)?', root_replacer, text)

        # *abs(expression)
        def abs_replacer(match):
            expr = clean_inner_math(match.group(1))
            return f"$abs({expr})$"

        text = re.sub(r'\*abs\((.*)\)', abs_replacer, text)

        # *sin(x), *cos(x), *tan(x), *log(x), *ln(x)
        def trig_replacer(match):
            fn = match.group(1)
            expr = clean_inner_math(match.group(2))
            return f"${fn}({expr})$"

        text = re.sub(r'\*(sin|cos|tan|log|ln)\((.*)\)', trig_replacer, text)

        # *pi, *infinity
        text = re.sub(r'\*pi\b', '$pi$', text)
        text = re.sub(r'\*infinity\b', '$infinity$', text)

        # *pow(base ; exponent)
        def pow_replacer(match):
            base = clean_inner_math(match.group(1))
            exp = clean_inner_math(match.group(2))
            return f"${base}^({exp})$"

        text = re.sub(r'\*pow\((.*?);(.*)\)', pow_replacer, text)

        # *sum(lower ; upper ; expression)
        def sum_replacer(match):
            lower = clean_inner_math(match.group(1))
            upper = clean_inner_math(match.group(2))
            expr = clean_inner_math(match.group(3))
            return f"$sum_({lower})^({upper}) ({expr})$"

        text = re.sub(r'\*sum\((.*?);(.*?);(.*)\)', sum_replacer, text)

        # *prod(lower ; upper ; expression)
        def prod_replacer(match):
            lower = clean_inner_math(match.group(1))
            upper = clean_inner_math(match.group(2))
            expr = clean_inner_math(match.group(3))
            return f"$product_({lower})^({upper}) ({expr})$"

        text = re.sub(r'\*prod\((.*?);(.*?);(.*)\)', prod_replacer, text)

        # *lim(variable -> value ; expression)
        def lim_replacer(match):
            cond = clean_inner_math(match.group(1))
            expr = clean_inner_math(match.group(2))
            return f"$lim_({cond}) ({expr})$"

        text = re.sub(r'\*lim\((.*?);(.*)\)', lim_replacer, text)

        # Merge adjacent math formulas like $...$ / $...$ or $...$$...$ into a single $...$
        # Also clean up any accidental double dollars inside a math block
        def merge_math(t):
            # If line is like "$lim_({cond}) (sin(x)$ / x)", merge into single $...$
            t = re.sub(r'\$([^\$]+)\$', lambda m: '$' + m.group(1).replace('$', '') + '$', t)
            return t

        text = merge_math(text)

        # base_index like A_1
        text = re.sub(r'\b([A-Za-z]+)_([A-Za-z0-9]+)\b', r'$\1_\2$', text)

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

    for out_line in output_lines:
        typst_content.append(out_line + " \\")

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
