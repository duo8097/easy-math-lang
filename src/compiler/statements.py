"""*define(...) and <var> = ... assignment processing."""

import re
import sys

from .calc import apply_calc_in_string
from .variables import replace_vars

IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def process_assignment_or_define(ctx, statement, line_no=None):
    statement = statement.strip()
    if not statement:
        return
    # Block content arrives raw (pipeline passes block lines unwrapped),
    # so tolerate the '*define(...)' star form here too.
    if statement.startswith('*define(') or statement.startswith('*define ('):
        statement = statement[1:].lstrip()
    # Tolerate 'define (' with space between name and paren.
    if re.match(r'^define\s*\(', statement):
        statement = re.sub(r'^define\s*\(', 'define(', statement, count=1)

    if statement.startswith('define(write_type.multiplication'):
        clean_stmt = statement[:-1] if statement.endswith(')') else statement
        # Value is after the FIRST '=' following the known prefix.
        # Legacy double-'=' form ('= * = .') is unwrapped to '.'.
        prefix = 'define(write_type.multiplication'
        rest = clean_stmt[len(prefix):].lstrip()
        if rest.startswith('='):
            rest = rest[1:].lstrip()
            # Legacy: '= * = .' -> strip leading '* =' to get real value.
            if rest.startswith('*'):
                after_star = rest[1:].lstrip()
                if after_star.startswith('='):
                    rest = after_star[1:].lstrip()
        else:
            eq = rest.find('=')
            rest = rest[eq + 1:].lstrip() if eq != -1 else ''
        val = rest.strip()
        # Whitelist safe single glyphs; reject Typst-significant chars
        # ($, \, <, >, #, @, `) that would inject math/escapes downstream.
        allowed = {'.', ',', '·', '×', 'x', '*', '⋅', ':'}
        if not val or val not in allowed:
            print(
                f"[WARNING] Line {line_no}: invalid multiplication symbol {val!r} — ignored",
                file=sys.stderr,
            )
        else:
            ctx.mult_sym = val
        return

    if statement.startswith('define(') and statement.endswith(')'):
        inner = statement[7:-1].strip()
        if '=' not in inner:
            print(
                f"[WARNING] Line {line_no}: *define() without '=' — ignored: {statement!r}",
                file=sys.stderr,
            )
            return
        k, v = inner.split('=', 1)
        k = k.strip()
        v = v.strip()
        if not k or not IDENT_RE.match(k):
            print(
                f"[WARNING] Line {line_no}: invalid define name {k!r} — ignored",
                file=sys.stderr,
            )
            return
        if len(k) == 1:
            print(
                f"[WARNING] Line {line_no}: Single-character define name '{k}' "
                f"may corrupt plain text.",
                file=sys.stderr,
            )
        v = replace_vars(ctx, v)
        v = apply_calc_in_string(ctx, v, line_no=line_no)
        ctx.defines[k] = v
        ctx.variables[k] = v
        return

    if statement.startswith('<') and '=' in statement:
        var_part, val_part = statement.split('=', 1)
        var_name = var_part.strip()
        if not (var_name.startswith('<') and var_name.endswith('>')):
            print(
                f"[WARNING] Line {line_no}: malformed assignment — ignored: {statement!r}",
                file=sys.stderr,
            )
            return
        var_name = var_name[1:-1].strip()
        if not var_name or not IDENT_RE.match(var_name):
            print(
                f"[WARNING] Line {line_no}: invalid variable name {var_name!r} — ignored",
                file=sys.stderr,
            )
            return
        val_part = val_part.strip()
        if '\\' in val_part:
            print(
                f"[WARNING] Line {line_no}: assignment value contains '\\' "
                f"(math delimiters are not expanded in values) — stored literally: {statement!r}",
                file=sys.stderr,
            )
        val_part = replace_vars(ctx, val_part)
        val_part = apply_calc_in_string(ctx, val_part, line_no=line_no)
        ctx.variables[var_name] = val_part
        return
    # Not an assignment/define (e.g. stray text inside a block).
    print(
        f"[WARNING] Line {line_no}: line inside block is not an assignment or define — ignored: {statement!r}",
        file=sys.stderr,
    )
