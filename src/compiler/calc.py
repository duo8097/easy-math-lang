"""Safe calc(...) arithmetic evaluation (depth-aware, AST-based)."""

import ast
import operator
import re

from .safemath import bounded_power, preprocess_math_expr, scalar_consts, scalar_funcs
from .variables import replace_defines, replace_vars
from .diagnostics import report

safe_operators = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: bounded_power,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def evaluate_calc(ctx, expression, line_no=None, _depth=0):
    if _depth > 20:
        report('Error', line_no or None,
               f'calc(): nested too deep in: {expression!r}')
        return '[Calc Error: nested too deep]'
    expression = replace_vars(ctx, expression)
    expression = replace_defines(ctx, expression)
    # Resolve nested calc(...) inside-out so calc(calc(1+1)+1) works.
    try:
        nested = apply_calc_in_string(ctx, expression, line_no=line_no, _depth=_depth + 1)
    except RecursionError:
        report('Error', line_no or None,
               f'calc(): nested too deep in: {expression!r}')
        return '[Calc Error: nested too deep]'
    if nested != expression:
        expression = nested
    try:
        # Shared preprocessing (safemath): <vars>/defines (idempotent
        # here), *sin(x)/*pi spellings, custom multiplication symbol,
        # thousands separators, decimal dots, ^ power. Only treat
        # mult_sym as an operator when spaced, so decimals (3.14) and
        # words containing 'x' are not corrupted.
        eval_expr = preprocess_math_expr(ctx, expression)
        tree = ast.parse(eval_expr, mode='eval')
        funcs = scalar_funcs()
        consts = scalar_consts()

        def eval_node(node):
            if isinstance(node, ast.Expression):
                return eval_node(node.body)
            if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                return node.value
            if isinstance(node, ast.Name):
                if node.id in consts:
                    return consts[node.id]
                raise ValueError(
                    f'unknown name {node.id!r} — only numbers, pi, e and '
                    f'{sorted(funcs)} are supported')
            if isinstance(node, ast.Call):
                if not isinstance(node.func, ast.Name):
                    raise ValueError('only plain function names are supported')
                fname = node.func.id
                if fname not in funcs:
                    raise ValueError(
                        f'unsupported function {fname!r} — supported: '
                        f'{sorted(funcs)}')
                if len(node.args) != 1 or node.keywords:
                    raise ValueError(
                        f'function {fname!r} takes exactly one argument')
                return funcs[fname](eval_node(node.args[0]))
            if isinstance(node, ast.BinOp) and type(node.op) in safe_operators:
                left = eval_node(node.left)
                right = eval_node(node.right)
                if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) and right == 0:
                    raise ZeroDivisionError("division by zero")
                result = safe_operators[type(node.op)](left, right)
                if isinstance(result, int) and abs(result) >= 10 ** 4000:
                    raise ValueError('calc: result too large')
                return result
            if isinstance(node, ast.UnaryOp) and type(node.op) in safe_operators:
                return safe_operators[type(node.op)](eval_node(node.operand))
            raise ValueError('calc only supports numbers and math operators')

        res = eval_node(tree)
        import math as _math
        if isinstance(res, complex):
            raise ValueError('calc: result is a complex number')
        if isinstance(res, float):
            if not _math.isfinite(res):
                raise ValueError('calc: result is not finite (inf/nan)')
            if res.is_integer():
                res = int(res)
        return str(res)
    except ZeroDivisionError:
        report('Error', line_no or None,
               f'calc(): division by zero in: {expression!r}')
        return '[Calc Error: division by zero]'
    except RecursionError:
        report('Error', line_no or None,
               f'calc(): nested too deep in: {expression!r}')
        return '[Calc Error: nested too deep]'
    except Exception as e:
        report('Error', line_no or None, f'calc(): {e} in: {expression!r}')
        return f'[Calc Error: {e}]'


def apply_calc_in_string(ctx, text, line_no=None, _depth=0):
    """Evaluate every calc(...) in text (handles nested parentheses)."""
    if _depth > 20:
        report('Error', line_no or None,
               f'calc(): nested too deep — leaving as-is')
        return text
    out = []
    pos = 0
    pattern = re.compile(r'(?<![A-Za-z0-9_])\*?calc\(')
    while True:
        m = pattern.search(text, pos)
        if not m:
            out.append(text[pos:])
            break
        matched = m.group(0)
        if matched.startswith('*'):
            report(
                'Warning', line_no or None,
                f'*calc(...) — leading * ignored, treating as calc(...)',
            )
            out.append(text[pos:m.start()])
            # Skip the leading '*' but keep 'calc(' for evaluation below.
            out.append('')
            pos = m.start() + 1
            # Re-search from the 'calc(' just after '*'.
            continue
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
            report(
                'Error', line_no or None,
                'calc(): unclosed parenthesis — leaving as-is',
            )
            out.append(text[m.start():])
            break
        expr = text[start:i - 1]
        out.append(evaluate_calc(ctx, expr, line_no=line_no, _depth=_depth + 1))
        pos = i
    return ''.join(out)
