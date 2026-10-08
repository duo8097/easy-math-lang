"""Function plots (*plot): numerically evaluate and render SVG via Matplotlib.

Pipeline (mirrors the ``*table``/``*matrix`` extension pattern):

    parse/validate (this module)
      -> numerical evaluation on a NumPy grid (AST walk, no ``eval``)
      -> SVG generation (Matplotlib, Agg backend, text stays text)
      -> Typst emission (``#image("...")`` with a relative path)

Expression syntax is the same family as ``calc(...)`` (see
:mod:`compiler.calc`): ``+ - * / % ^`` (``^`` is power), parentheses,
decimal points/commas and thousands separators. Additionally the plot
variable ``x``, the constants ``pi``/``e`` (``*pi`` is accepted too)
and the single-argument functions ``sin cos tan sqrt cbrt log ln abs
exp`` are supported, where ``log`` is base-10 like Typst's ``log`` and
``ln`` is the natural logarithm.

Plots are generated numerically (1000 samples by default). Values
that are not finite are skipped, and segments are broken across large
jumps so discontinuities such as ``1/x`` do not draw a misleading
vertical line.
"""

import ast
import operator
import re
import warnings

PLOT_SAMPLES = 1000

_PLOT_CALL_RE = re.compile(r'\*plot\s*\(')

_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARYOPS = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _numpy_funcs():
    """Whitelisted single-argument functions (lazy numpy import)."""
    import numpy as _np
    return {
        'sin': _np.sin,
        'cos': _np.cos,
        'tan': _np.tan,
        'sqrt': _np.sqrt,
        'cbrt': _np.cbrt,
        'log': _np.log10,
        'ln': _np.log,
        'abs': _np.abs,
        'exp': _np.exp,
    }


def _numpy_consts():
    import numpy as _np
    return {'pi': _np.pi, 'e': _np.e}


def find_next_plot_call(text, start=0):
    """Locate the next ``*plot(`` call at/after *start*.

    Returns ``(call_start, inner_start, call_end, inner_raw)`` with
    depth-aware paren matching (quote-aware for ``"..."``), or None
    when no opener remains. Unclosed openers return an ``('unclosed',
    ...)`` marker so callers can warn without looping.
    """
    pos = start
    while True:
        m = _PLOT_CALL_RE.search(text, pos)
        if not m:
            return None
        call_start = m.start()
        inner_start = m.end()
        depth = 1
        i = inner_start
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
            return ('unclosed', call_start, inner_start, None, None)
        return (call_start, inner_start, i, text[inner_start:i - 1])


def _preprocess_expression(ctx, raw):
    """Substitute vars/defines and normalize calc-style syntax."""
    from .variables import replace_defines, replace_vars
    expr = replace_vars(ctx, raw)
    expr = replace_defines(ctx, expr)
    expr = re.sub(r'\*pi\b', 'pi', expr)
    expr = re.sub(r'\*infinity\b', 'inf', expr)
    # Accept math-command spellings (*sin(x), *sqrt(x)) inside plots:
    # single-argument functions map to their bare numpy equivalents.
    expr = re.sub(
        r'\*(sin|cos|tan|sqrt|cbrt|log|ln|abs|exp)\s*\(', r'\1(', expr)
    if ctx.mult_sym != '*':
        expr = re.sub(
            r'\s' + re.escape(ctx.mult_sym) + r'\s', ' * ', f' {expr} '
        ).strip()
    expr = re.sub(r'(?<=\d)\s+(?=\d{3}\b)', '', expr)
    expr = re.sub(r'(?<=\d),(?=\d{3}(?:,\d{3})*(?!\d))', '', expr)
    expr = re.sub(r'(?<=\d),(?=\d)', '.', expr)
    expr = expr.replace('^', '**')
    return expr.strip()


def evaluate_on_grid(ctx, raw_expr, x_values):
    """Evaluate *raw_expr* elementwise over the NumPy array *x_values*.

    Raises ValueError with a user-facing reason for unsupported syntax
    (unknown names/functions, multi-arg calls, non-numeric literals).
    """
    import numpy as _np
    expr = _preprocess_expression(ctx, raw_expr)
    if not expr:
        raise ValueError('empty expression')
    try:
        tree = ast.parse(expr, mode='eval')
    except SyntaxError as e:
        raise ValueError(f'cannot parse expression {raw_expr.strip()!r}: {e}')
    funcs = _numpy_funcs()
    consts = _numpy_consts()

    def eval_node(node):
        if isinstance(node, ast.Expression):
            return eval_node(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                raise ValueError(f'unsupported value {node.value!r}')
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f'unsupported value {node.value!r}')
        if isinstance(node, ast.Name):
            if node.id == 'x':
                return x_values
            if node.id in consts:
                return consts[node.id]
            if node.id in ('inf', 'nan'):
                return getattr(_np, node.id)
            raise ValueError(
                f'unknown name {node.id!r} — only x, pi, e and '
                f'{sorted(funcs)} are supported')
        if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
            return _BINOPS[type(node.op)](eval_node(node.left),
                                          eval_node(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARYOPS:
            return _UNARYOPS[type(node.op)](eval_node(node.operand))
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
        raise ValueError(
            f'unsupported syntax {ast.dump(node)} — use numbers, x, '
            f'+ - * / % ^ and single-argument functions')

    with _np.errstate(all='ignore'):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            result = eval_node(tree)
    arr = _np.asarray(result, dtype=float)
    if arr.ndim == 0:
        arr = _np.full_like(x_values, float(arr), dtype=float)
    return arr


def evaluate_bound(ctx, raw):
    """Evaluate a plot bound with the ``calc`` evaluator; return float.

    Raises ValueError with a user-facing reason when the bound is not
    a finite number.
    """
    import math as _math
    from .calc import evaluate_calc
    text = (raw or '').strip()
    if not text:
        raise ValueError('empty bound')
    res = evaluate_calc(ctx, text)
    if isinstance(res, str) and res.startswith('[Calc Error'):
        raise ValueError(res[12:-1] if res.endswith(']') else res)
    try:
        val = float(res)
    except (TypeError, ValueError):
        raise ValueError(f'bound {raw.strip()!r} is not numeric')
    if not _math.isfinite(val):
        raise ValueError(f'bound {raw.strip()!r} is not finite')
    return val


def split_plot_segments(x_values, y_values):
    """Split the sampled curve into drawable runs.

    Breaks at non-finite samples and across large vertical jumps so a
    discontinuity such as ``1/x`` never draws one misleading line from
    the last negative to the first positive sample. Returns a list of
    ``(xs, ys)`` arrays; every pair has at least one point.
    """
    import numpy as _np
    x = _np.asarray(x_values, dtype=float)
    y = _np.asarray(y_values, dtype=float)
    finite = _np.isfinite(y)
    if not bool(_np.any(finite)):
        return []
    span = float(_np.max(y[finite]) - _np.min(y[finite]))
    jump = span / 30.0 if span > 0 else float('inf')
    segments = []
    cur_x, cur_y = [], []
    prev_y = None
    for xi, yi, ok in zip(x.tolist(), y.tolist(), finite.tolist()):
        if not ok:
            if cur_x:
                segments.append((_np.array(cur_x), _np.array(cur_y)))
                cur_x, cur_y = [], []
            prev_y = None
            continue
        if prev_y is not None and abs(yi - prev_y) > jump:
            if cur_x:
                segments.append((_np.array(cur_x), _np.array(cur_y)))
                cur_x, cur_y = [], []
        cur_x.append(xi)
        cur_y.append(yi)
        prev_y = yi
    if cur_x:
        segments.append((_np.array(cur_x), _np.array(cur_y)))
    return segments


def plot_filename(stem, index):
    """SVG file name for the *index*-th plot (1-based)."""
    return f'{stem}-plot-{index}.svg'


def render_plot_svg(ctx, raw_expr, xmin, xmax, out_path,
                    samples=PLOT_SAMPLES):
    """Numerically evaluate and render one plot; return the expression.

    Raises ValueError (bad expression/bounds) or OSError/RuntimeError
    (SVG backend failure) with user-facing messages.
    """
    import numpy as _np
    x = _np.linspace(float(xmin), float(xmax), int(samples), dtype=float)
    y = evaluate_on_grid(ctx, raw_expr, x)
    segments = split_plot_segments(x, y)
    if not segments:
        raise ValueError(
            f'expression {raw_expr.strip()!r} has no finite values '
            f'on [{xmin}, {xmax}]')
    try:
        import matplotlib
        try:
            matplotlib.use('Agg')
        except Exception:
            pass
        import matplotlib.pyplot as plt
    except ImportError:
        raise RuntimeError(
            'plotting needs matplotlib — run `uv sync` to install it')
    try:
        with plt.rc_context({'svg.fonttype': 'none'}):
            fig, ax = plt.subplots(figsize=(5.5, 3.5))
            label = raw_expr.strip()
            for _si, (sx, sy) in enumerate(segments):
                if len(sx) == 1:
                    ax.plot([sx[0]], [sy[0]], marker='o', markersize=3,
                            color='#1f6feb', linestyle='None')
                else:
                    ax.plot(sx, sy, color='#1f6feb', linewidth=1.6,
                            label=label if _si == 0 else None)
            ax.set_xlabel('x')
            ax.set_ylabel(f'y = {label}')
            ax.axhline(0, color='black', linewidth=0.8)
            ax.axvline(0, color='black', linewidth=0.8)
            ax.grid(True, linestyle='--', alpha=0.4)
            ax.margins(0.05)
            fig.tight_layout()
            fig.savefig(out_path, format='svg', bbox_inches='tight')
            plt.close(fig)
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f'could not generate plot SVG: {e}')
    return raw_expr.strip()
