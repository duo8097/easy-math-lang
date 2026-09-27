"""Math commands (*frac, *pow, *root, *sum, *prod, *lim, ...)."""

import re

from .calc import apply_calc_in_string
from .symbols import replace_symbol_shortcuts
from .variables import replace_defines, replace_vars


def split_top_level_args(args):
    """Split on ';' at paren depth 0 (tracks (), {} and [])."""
    parts = []
    current = []
    depth_paren = 0
    depth_brace = 0
    depth_bracket = 0
    for char in args:
        if char == '(':
            depth_paren += 1
        elif char == ')' and depth_paren > 0:
            depth_paren -= 1
        elif char == '{':
            depth_brace += 1
        elif char == '}' and depth_brace > 0:
            depth_brace -= 1
        elif char == '[':
            depth_bracket += 1
        elif char == ']' and depth_bracket > 0:
            depth_bracket -= 1
        if (char == ';' and depth_paren == 0
                and depth_brace == 0 and depth_bracket == 0):
            parts.append(''.join(current).strip())
            current = []
        else:
            current.append(char)
    parts.append(''.join(current).strip())
    return parts


def replace_math_call(text, name, min_args, formatter):
    """Replace *name(...) calls using depth-aware paren matching."""
    import sys
    pattern = re.compile(r'\*' + re.escape(name) + r'\s*\(')
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
            print(
                f'[Warning] unclosed *{name}(... — missing closing parenthesis',
                file=sys.stderr,
            )
            # Emit the opener literally and continue scanning so later
            # valid calls on the same line are still processed.
            out.append(text[match.start():match.end()])
            pos = match.end()
            continue
        args = split_top_level_args(text[start:i - 1])
        if len(args) < min_args:
            print(
                f'[Warning] *{name}(...) expects {min_args} argument(s), '
                f'got {len(args)} — leaving as-is',
                file=sys.stderr,
            )
            out.append(text[match.start():i])
        elif any(a == '' for a in args[:min_args]):
            print(
                f'[Warning] *{name}(...) has empty argument(s) — leaving as-is',
                file=sys.stderr,
            )
            out.append(text[match.start():i])
        else:
            if len(args) > min_args:
                print(
                    f'[Warning] *{name}(...) expects {min_args} argument(s), '
                    f'got {len(args)} — extra arguments ignored',
                    file=sys.stderr,
                )
                args = args[:min_args]
            out.append(formatter(args))
        pos = i
    return ''.join(out)


def clean_inner_math(ctx, s):
    """Normalize a math argument: vars, defines, calc, nested math calls."""
    s = replace_vars(ctx, s.strip())
    s = replace_defines(ctx, s)
    s = apply_calc_in_string(ctx, s)
    # Unify *pi/*infinity with the text/math paths: text renders $pi$,
    # inline math renders pi inside $...$, so normalize to bare words
    # here before symbol shortcuts (which map *pi -> π).
    s = re.sub(r'\*pi\b', 'pi', s)
    s = re.sub(r'\*infinity\b', 'infinity', s)
    # Strip only temporary $ wrappers (e.g. from nested math calls),
    # not every literal '$': a literal dollar in args is preserved for
    # the final unwrap below.
    s = replace_symbol_shortcuts(s)
    for fn_name, fn_min, fn_fmt in math_call_specs(ctx):
        s = replace_math_call(s, fn_name, fn_min, fn_fmt)
    s = re.sub(r'\$([^$]+)\$', r'\1', s)
    if ctx.mult_sym != '*':
        s = s.replace('*', ctx.mult_sym)
    return s


def math_call_specs(ctx):
    return [
        ('frac', 2,
         lambda args: f"$frac({clean_inner_math(ctx, args[0])}, {clean_inner_math(ctx, args[1])})$"),
        ('abs', 1,
         lambda args: f"$abs({clean_inner_math(ctx, args[0])})$"),
        ('sin', 1, lambda args: f"$sin({clean_inner_math(ctx, args[0])})$"),
        ('cos', 1, lambda args: f"$cos({clean_inner_math(ctx, args[0])})$"),
        ('tan', 1, lambda args: f"$tan({clean_inner_math(ctx, args[0])})$"),
        ('sqrt', 1, lambda args: f"$sqrt({clean_inner_math(ctx, args[0])})$"),
        ('log', 1, lambda args: f"$log({clean_inner_math(ctx, args[0])})$"),
        ('ln',  1, lambda args: f"$ln({clean_inner_math(ctx, args[0])})$"),
        ('pow', 2,
         lambda args: _format_pow(ctx, args)),
        ('root', 2,
         lambda args: f"$root({clean_inner_math(ctx, args[0])}, {{{clean_inner_math(ctx, args[1])}}})$"),
        ('sum', 3,
         lambda args: (
             f"$display(sum_({clean_inner_math(ctx, args[0])})^({clean_inner_math(ctx, args[1])}) "
             f"({clean_inner_math(ctx, args[2])}))$"
         )),
        ('prod', 3,
         lambda args: (
             f"$display(product_({clean_inner_math(ctx, args[0])})^({clean_inner_math(ctx, args[1])}) "
             f"({clean_inner_math(ctx, args[2])}))$"
         )),
        ('lim', 2,
         lambda args: f"$lim_({clean_inner_math(ctx, args[0])}) ({clean_inner_math(ctx, args[1])})$"),
    ]


def group_power_base(ctx, s):
    s = clean_inner_math(ctx, s)
    # Wrap compound bases in parens. A word-internal hyphen (foo-bar)
    # is not an operator; require spacing or non-word context for '-',
    # while '+', '*', '/' anywhere indicate a compound expression.
    has_spaced_op = bool(re.search(r'\s[+\-*/]\s', s))
    has_plus_star_slash = bool(re.search(r'[+*/]', s))
    has_minus_op = bool(
        re.search(r'(?<![A-Za-z0-9_])-(?![A-Za-z0-9_])', s)
        or re.search(r'(?<=\d)-(?=\d)', s)
        or re.search(r'\s-\s', s)
    )
    if (has_spaced_op or has_plus_star_slash or has_minus_op) and not (
        s.startswith('(') and s.endswith(')') and _outer_parens_balanced(s)
    ):
        return f'({s})'
    return s


def _outer_parens_balanced(s):
    """True when the outer (...) wraps the whole string."""
    if not (s.startswith('(') and s.endswith(')')):
        return False
    depth = 0
    for i, ch in enumerate(s):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0 and i != len(s) - 1:
                return False
    return depth == 0


def _format_pow(ctx, args):
    import sys
    base = group_power_base(ctx, args[0])
    exp = clean_inner_math(ctx, args[1])
    # *pow(A ; *degree) means A° per spec, not A^(°).
    if exp == '°':
        return f'${base}°$'
    if not exp.strip():
        print(
            '[Warning] *pow(...) has empty exponent — emitting base only',
            file=sys.stderr,
        )
        return f'${base}$'
    return f'${base}^({exp})$'
