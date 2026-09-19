"""*define(...) and <var> = ... assignment processing."""

import sys

from .calc import apply_calc_in_string
from .variables import replace_vars


def process_assignment_or_define(ctx, statement, line_no=None):
    statement = statement.strip()
    if not statement:
        return

    if statement.startswith('define(write_type.multiplication'):
        clean_stmt = statement[:-1] if statement.endswith(')') else statement
        # Support both documented single-'=' form ( = .) and legacy
        # double-'=' form ( = * = .): value is always after the last '='.
        parts = clean_stmt.split('=')
        if len(parts) >= 2:
            ctx.mult_sym = parts[-1].strip()
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
            v = replace_vars(ctx, v)
            v = apply_calc_in_string(ctx, v, line_no=line_no)
            ctx.defines[k] = v
            ctx.variables[k] = v
        return

    if statement.startswith('<') and '=' in statement:
        var_part, val_part = statement.split('=', 1)
        var_name = var_part.strip()
        if var_name.startswith('<') and var_name.endswith('>'):
            var_name = var_name[1:-1].strip()
        val_part = val_part.strip()
        val_part = replace_vars(ctx, val_part)
        val_part = apply_calc_in_string(ctx, val_part, line_no=line_no)
        ctx.variables[var_name] = val_part
        return
