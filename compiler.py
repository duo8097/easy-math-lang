import re
import sys
import os
import subprocess

def compile_ezmath(input_file, output_pdf):
    variables = {}
    defines = {}
    mult_sym = '*'

    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

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
        try:
            eval_expr = expression.replace(mult_sym, '*')
            return str(eval(eval_expr))
        except Exception as e:
            return f"[Calc Error: {e}]"

    for line in lines:
        line = line.strip()
        if not line or line.startswith('//'):
            continue
            
        # Inline comment removal
        if '//' in line and not line.startswith('//'):
            line = line.split('//')[0].strip()

        # Handle multi-line block states
        if line == 'f(':
            in_f_block = True
            continue
        elif line == ')' and in_f_block:
            in_f_block = False
            continue
            
        # Single-line definition block processing (skip frac as it's meant for output)
        if line.startswith('f(') and line.endswith(')') and not 'frac(' in line:
            inner = line[2:-1].strip()
            if inner.startswith('define(write_type.multiplication'):
                clean_inner = inner[:-1] if inner.endswith(')') else inner
                parts = clean_inner.split('=')
                if len(parts) >= 3:
                    mult_sym = parts[2].strip()
            elif inner.startswith('define('):
                inner_def = inner[7:-1].strip()
                if '=' in inner_def:
                    k, v = inner_def.split('=', 1)
                    defines[k.strip()] = replace_vars(v.strip())
            continue

        if in_f_block:
            if line.startswith('<') and '=' in line:
                var_part, val_part = line.split('=', 1)
                var_name = var_part.strip()[1:-1]
                variables[var_name] = replace_vars(val_part.strip())
            elif line.startswith('define('):
                if line.startswith('define(write_type.multiplication'):
                    clean_inner = line[:-1] if line.endswith(')') else line
                    parts = clean_inner.split('=')
                    if len(parts) >= 3:
                        mult_sym = parts[2].strip()
                else:
                    inner_def = line[7:-1].strip()
                    if '=' in inner_def:
                        k, v = inner_def.split('=', 1)
                        defines[k.strip()] = replace_vars(v.strip())
            continue
            
        # --- Text Output Formatting Phase ---
        text = line
        
        # 1. p(): Print raw text directly, bypassing all other rules
        if text.startswith('p(') and text.endswith(')'):
            text = text[2:-1]
            output_lines.append(text)
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
            
        # 5. Handle f(frac(numerator ; denominator))
        def frac_replacer(match):
            numerator = match.group(1).strip()
            denominator = match.group(2).strip()
            # Typst uses $frac(a, b)$ for math fractions
            return f"$frac({numerator}, {denominator})$"
            
        text = re.sub(r'f\(frac\((.*?);(.*?)\)\)', frac_replacer, text)
        
        # 6. Apply multiplication symbol
        text = text.replace('*', mult_sym)
        
        output_lines.append(text)

    # Generate Typst File
    typst_file = input_file.replace('.ezmath', '.typ')
    
    typst_content = [
        "#set text(size: 12pt)",
        "#set page(paper: \"a4\", margin: 2cm)",
        "#align(center)[= Easy Math Document]",
        ""
    ]
    
    for out_line in output_lines:
        typst_content.append(out_line + " \\") 
        
    with open(typst_file, 'w', encoding='utf-8') as tf:
        tf.write("\n".join(typst_content))
        
    print(f"Generated intermediate file: {typst_file}")

    # Compile using Typst
    print("Compiling PDF with Typst...")
    try:
        subprocess.run(["typst", "compile", typst_file, output_pdf], check=True)
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
    output_file = sys.argv[2] if len(sys.argv) > 2 else input_file.replace('.ezmath', '.pdf')
    compile_ezmath(input_file, output_file)
