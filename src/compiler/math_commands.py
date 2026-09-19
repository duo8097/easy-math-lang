"""Math commands (*frac, *pow, *root, *sum, *prod, *lim, ...)."""

import re

from .calc import apply_calc_in_string
from .symbols import replace_symbol_shortcuts
from .variables import replace_defines, replace_vars


def split_top_level_args(args):
    """Split on ';' at paren depth 0."""
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


def replace_math_call(text, name, min_args, formatter):
    """Replace *name(...) calls using depth-aware paren matching."""
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


def clean_inner_math(ctx, s):
    """Normalize a math argument: vars, defines, calc, nested math calls."""
    s = replace_vars(ctx, s.strip())
    s = replace_defines(ctx, s)
    s = apply_calc_in_string(ctx, s)
    s = s.replace('$', '')
    s = replace_symbol_shortcuts(s)
    for fn_name, fn_min, fn_fmt in math_call_specs(ctx):
        s = replace_math_call(s, fn_name, fn_min, fn_fmt)
    s = re.sub(r'\$([^$]+)\$', r'\1', s)
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
        ('log', 1, lambda args: f"$log({clean_inner_math(ctx, args[0])})$"),
        ('ln',  1, lambda args: f"$ln({clean_inner_math(ctx, args[0])})$"),
        ('pow', 2,
         lambda args: f"${group_power_base(ctx, args[0])}^({clean_inner_math(ctx, args[1])})$"),
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
    if re.search(r'\s[+\-*/]\s|[+\-*/]', s) and not (s.startswith('(') and s.endswith(')')):
        return f'({s})'
    return s
