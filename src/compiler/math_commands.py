"""Math commands (*frac, *pow, *root, *sum, *prod, *lim, ...)."""

import re

from .calc import apply_calc_in_string
from .symbols import replace_symbol_shortcuts
from .variables import replace_defines, replace_vars


def split_top_level_args(args):
    """Split on ';' (or ',' friendly) at paren depth 0 (tracks (), {} and []).

    Friendly rule: when ';' appears at depth 0, split on ';' only
    (so ``*frac(100,000 ; 2)`` keeps ``100,000`` intact). Otherwise
    split on ',' so ``*frac(2,3)`` works like ``*frac(2 ; 3)``.
    Separators inside double-quoted strings are ignored so
    ``*frac("a;b" ; c)`` keeps ``"a;b"`` intact.
    """
    # Scan for a depth-0 ';' first to decide the separator set.
    # Quote-aware: separators inside "..." never count.
    def _has_top_semi(s):
        _dp = _db = _br = 0
        _q = False
        for _i, _ch in enumerate(s):
            if _ch == '"' and (_i == 0 or s[_i - 1] != '\\'):
                _q = not _q
                continue
            if _q:
                continue
            if _ch == '(':
                _dp += 1
            elif _ch == ')' and _dp > 0:
                _dp -= 1
            elif _ch == '{':
                _db += 1
            elif _ch == '}' and _db > 0:
                _db -= 1
            elif _ch == '[':
                _br += 1
            elif _ch == ']' and _br > 0:
                _br -= 1
            elif _ch == ';' and _dp == 0 and _db == 0 and _br == 0:
                return True
        return False

    has_semi = _has_top_semi(args)
    seps = (';',) if has_semi else (';', ',')
    parts = []
    current = []
    depth_paren = 0
    depth_brace = 0
    depth_bracket = 0
    in_quote = False
    idx = 0
    for char in args:
        if char == '"' and (idx == 0 or args[idx - 1] != '\\'):
            in_quote = not in_quote
            current.append(char)
            idx += 1
            continue
        if in_quote:
            current.append(char)
            idx += 1
            continue
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
        if (char in seps and depth_paren == 0
                and depth_brace == 0 and depth_bracket == 0):
            parts.append(''.join(current).strip())
            current = []
        else:
            current.append(char)
        idx += 1
    parts.append(''.join(current).strip())
    return parts


# Friendly aliases: alias -> canonical math command. Users may write
# *fraction(...) instead of *frac(...), etc. Bare (star-less) calls
# like frac(2 ; 3) are also accepted (see normalize_friendly_calls).
MATH_ALIASES = {
    'fraction': 'frac',
    'power': 'pow',
    'squareroot': 'sqrt',
    'square-root': 'sqrt',
    'cuberoot': 'cbrt',
    'cube-root': 'cbrt',
    'cbrt': 'cbrt',
    'absolute': 'abs',
    'summation': 'sum',
    'product': 'prod',
    'limit': 'lim',
}

_CANONICAL_MATH_NAMES = (
    'frac', 'abs', 'sin', 'cos', 'tan', 'sqrt', 'log', 'ln',
    'pow', 'root', 'sum', 'prod', 'lim', 'cbrt',
)


def normalize_friendly_calls(text):
    """Rewrite friendly math spellings to canonical ``*name(...)`` form.

    Only starred aliases (``*fraction(`` -> ``*frac(`` etc., see
    MATH_ALIASES). Bare ``frac(`` without ``*`` is deliberately NOT
    rewritten here: doing so before outer commands (e.g. ``*lim``)
    are expanded causes nested ``$...$`` double-wrapping
    (``*lim(x -> 0 ; sin(x)/x)`` regressed to
    ``$lim_(...) ($sin(x)$ / x)$``). Beginners keep the ``*`` prefix;
    friendliness comes from commas, aliases, ``let`` and blocks.
    Idempotent and safe to call repeatedly.
    """
    # Starred aliases: *fraction( -> *frac(. Hyphenated aliases need
    # re.escape (e.g. square-root). Skip identity (cbrt -> cbrt).
    for alias, canon in MATH_ALIASES.items():
        if alias == canon:
            continue
        text = re.sub(
            r'\*' + re.escape(alias) + r'\s*\(',
            f'*{canon}(',
            text,
        )
    return text


def escape_number_commas(s):
    """Escape literal commas that belong to numbers for Typst math.

    A bare comma inside Typst math function args is an argument
    separator, so emitting ``$frac(100,000, 7)$`` fails with
    "unexpected argument" (no PDF). Verified: ``$frac(100\\,000, 7)$``
    compiles. Only a comma directly between two digits is escaped,
    so genuine ``", "`` separators (which the formatters below always
    emit with a trailing space) survive untouched.
    """
    return re.sub(r'(?<=\d),(?=\d)', r'\\,', s)


# Typst math identifiers that must survive space_out_bare_identifiers().
# Everything else that looks like a bare multi-letter word (MD, ABC, MBC)
# is an "unknown variable" in Typst and aborts the whole PDF build, so we
# split it into implicit products (M D, A B C) which always compile.
_TYPST_MATH_KEEP = frozenset({
    'frac', 'abs', 'sin', 'cos', 'tan', 'sqrt', 'cbrt', 'root',
    'sum', 'product', 'prod', 'lim', 'display',
    'pi', 'infinity',
    'upright', 'bracket', 'lr', 'mid',
})


def space_out_bare_identifiers(s):
    """Split bare multi-letter words so Typst math compiles.

    ``$frac(MD, AD)$`` fails with "unknown variable: MD" because Typst
    reads ``MD`` as one variable name. ``$frac(M D, A D)$`` (implicit
    product) compiles and renders as math italic, which is the right
    look for segment/triangle names (MD, ABC, MBC, ...).

    Kept intact: quoted strings ("MD"), Typst functions/constants in
    _TYPST_MATH_KEEP, function calls (word followed by '('), and
    single letters/digits. Idempotent: already-spaced output is stable.

    Letters directly after a digit also split (4ac -> 4a c, 2xy -> 2x y)
    so the quadratic discriminant b^2 - 4ac does not abort Typst with
    "unknown variable: ac". The digit stays glued to the first letter
    (4a), which Typst reads as implicit product and compiles fine.
    """
    # Split out "..." quoted spans so we never touch string contents.
    parts = re.split(r'("[^"]*")', s)
    for idx in range(0, len(parts), 2):
        seg = parts[idx]

        def _repl(m):
            word = m.group(1)
            if len(word) < 2:
                return word
            if word in _TYPST_MATH_KEEP:
                return word
            # Function call: name directly followed by '(' stays whole.
            # Whitespace before '(' is NOT a call (e.g. 'AB (x)'): split
            # it so Typst doesn't abort on unknown variable 'AB'.
            after = seg[m.end():]
            if after.startswith('('):
                return word
            return ' '.join(word)

        parts[idx] = re.sub(
            r'(?<![A-Za-z_])([A-Za-z][A-Za-z0-9]*)(?![A-Za-z0-9_])',
            _repl,
            seg,
        )
    return ''.join(parts)


def replace_math_call(text, name, min_args, formatter, _depth=0):
    """Replace *name(...) calls using depth-aware paren matching."""
    import sys
    if _depth > 20:
        print(f'[Warning] *{name}(...) nested too deep — leaving as-is',
              file=sys.stderr)
        return text
    try:
        return _replace_math_call(text, name, min_args, formatter, _depth)
    except RecursionError:
        print(f'[Warning] *{name}(...) nested too deep — leaving as-is',
              file=sys.stderr)
        return text


def _replace_math_call(text, name, min_args, formatter, _depth=0):
    import sys
    import re
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
        in_quote = False
        while i < len(text) and depth > 0:
            ch = text[i]
            if ch == '"' and (i == 0 or text[i - 1] != '\\'):
                in_quote = not in_quote
            elif not in_quote:
                if ch == '(':
                    depth += 1
                elif ch == ')':
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


def clean_inner_math(ctx, s, _depth=0):
    """Normalize a math argument: vars, defines, calc, nested math calls."""
    import sys
    if _depth > 20:
        print('[Warning] math nesting too deep — leaving as-is',
              file=sys.stderr)
        return s
    try:
        return _clean_inner_math(ctx, s, _depth)
    except RecursionError:
        print('[Warning] math nesting too deep — leaving as-is',
              file=sys.stderr)
        return s


def _clean_inner_math(ctx, s, _depth=0):
    s = normalize_friendly_calls(s.strip())
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
    s = normalize_friendly_calls(s)
    for fn_name, fn_min, fn_fmt in math_call_specs(ctx):
        s = replace_math_call(s, fn_name, fn_min, fn_fmt)
    s = re.sub(r'\$([^$]+)\$', r'\1', s)
    # Escape thousands commas (100,000 -> 100\,000) so Typst does not
    # read them as argument separators. See escape_number_commas.
    s = escape_number_commas(s)
    # Split bare multi-letter identifiers (MD -> M D) so Typst does not
    # abort with "unknown variable: MD". See space_out_bare_identifiers.
    s = space_out_bare_identifiers(s)
    if ctx.mult_sym != '*':
        # Protect quoted strings and *command( (unknown commands left as
        # text) so '"a*b"' survives; space the operator: 2*3 -> '2 . 3'.
        _prot = {}

        def _pm(m):
            ph = f'\x03{len(_prot)}\x04'
            _prot[ph] = m.group(0)
            return ph

        s = re.sub(r'"[^"]*"', _pm, s)
        s = re.sub(r'\*[A-Za-z][A-Za-z0-9_\-]*\s*\(', _pm, s)
        s = re.sub(r'\s*\*\s*', f' {ctx.mult_sym} ', s)
        for ph, orig in _prot.items():
            s = s.replace(ph, orig)
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
        ('cbrt', 1, lambda args: f"$root(3, {{{clean_inner_math(ctx, args[0])}}})$"),
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
