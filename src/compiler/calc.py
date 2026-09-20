"""Safe calc(...) arithmetic evaluation (depth-aware, AST-based)."""

import ast
import operator
import re
import sys

from .variables import replace_defines, replace_vars

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


def evaluate_calc(ctx, expression, line_no=None, _depth=0):
    if _depth > 20:
        loc = f' Line {line_no}:' if line_no else ''
        print(f'[Error]{loc} calc(): nested too deep in: {expression!r}', file=sys.stderr)
        return '[Calc Error: nested too deep]'
    expression = replace_vars(ctx, expression)
    expression = replace_defines(ctx, expression)
    # Resolve nested calc(...) inside-out so calc(calc(1+1)+1) works.
    try:
        nested = apply_calc_in_string(ctx, expression, line_no=line_no, _depth=_depth + 1)
    except RecursionError:
        loc = f' Line {line_no}:' if line_no else ''
        print(f'[Error]{loc} calc(): nested too deep in: {expression!r}', file=sys.stderr)
        return '[Calc Error: nested too deep]'
    if nested != expression:
        expression = nested
    try:
        # Only treat mult_sym as an operator when spaced, so decimals
        # (3.14) and words containing 'x' are not corrupted.
        if ctx.mult_sym != '*':
            eval_expr = re.sub(
                r'\s' + re.escape(ctx.mult_sym) + r'\s', ' * ', f' {expression} '
            ).strip()
        else:
            eval_expr = expression.strip()
        eval_expr = re.sub(r'(?<=\d)\s+(?=\d{3}\b)', '', eval_expr)
        eval_expr = eval_expr.replace('^', '**')
        tree = ast.parse(eval_expr, mode='eval')

        def eval_node(node):
            if isinstance(node, ast.Expression):
                return eval_node(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return node.value
            if isinstance(node, ast.BinOp) and type(node.op) in safe_operators:
                left = eval_node(node.left)
                right = eval_node(node.right)
                if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) and right == 0:
                    raise ZeroDivisionError("division by zero")
                if isinstance(node.op, ast.Pow):
                    # Guard against gigantic bigint DoS (e.g. 9 ** 9 ** 9).
                    try:
                        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                            if abs(right) > 1000 or (abs(left) > 10 and abs(right) > 100):
                                raise ValueError('calc: exponent too large')
                    except ValueError:
                        raise
                    except Exception:
                        pass
                result = safe_operators[type(node.op)](left, right)
                if isinstance(result, int) and abs(result) > 10 ** 4000:
                    raise ValueError('calc: result too large')
                return result
            if isinstance(node, ast.UnaryOp) and type(node.op) in safe_operators:
                return safe_operators[type(node.op)](eval_node(node.operand))
            raise ValueError('calc only supports numbers and math operators')

        res = eval_node(tree)
        if isinstance(res, float) and res.is_integer():
            res = int(res)
        return str(res)
    except ZeroDivisionError:
        loc = f' Line {line_no}:' if line_no else ''
        print(f'[Error]{loc} calc(): division by zero in: {expression!r}', file=sys.stderr)
        return '[Calc Error: division by zero]'
    except RecursionError:
        loc = f' Line {line_no}:' if line_no else ''
        print(f'[Error]{loc} calc(): nested too deep in: {expression!r}', file=sys.stderr)
        return '[Calc Error: nested too deep]'
    except Exception as e:
        loc = f' Line {line_no}:' if line_no else ''
        print(f'[Error]{loc} calc(): {e} in: {expression!r}', file=sys.stderr)
        return f'[Calc Error: {e}]'


def apply_calc_in_string(ctx, text, line_no=None, _depth=0):
    """Evaluate every calc(...) in text (handles nested parentheses)."""
    if _depth > 20:
        loc = f' Line {line_no}:' if line_no else ''
        print(f'[Error]{loc} calc(): nested too deep — leaving as-is', file=sys.stderr)
        return text
    out = []
    pos = 0
    pattern = re.compile(r'(?<![A-Za-z0-9_])calc\(')
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
            loc = f' Line {line_no}:' if line_no else ''
            print(
                f'[Error]{loc} calc(): unclosed parenthesis — leaving as-is',
                file=sys.stderr,
            )
            out.append(text[m.start():])
            break
        expr = text[start:i - 1]
        out.append(evaluate_calc(ctx, expr, line_no=line_no, _depth=_depth + 1))
        pos = i
    return ''.join(out)
