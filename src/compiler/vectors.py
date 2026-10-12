"""Vector diagrams (*vec): numerically evaluate and render SVG via Matplotlib.

Pipeline (mirrors the ``*plot`` extension pattern):

    parse/validate (this module)
      -> numerical evaluation of the two components (AST walk, no ``eval``)
      -> SVG generation (Matplotlib, Agg backend, text stays text)
      -> Typst emission (``#image("...")`` with a relative path)

Expression syntax is the same family as ``*plot``/``calc(...)`` (see
:mod:`compiler.plots`): ``+ - * / % ^`` (``^`` is power), parentheses,
decimal points (dots) and thousands separators. Additionally the
constants ``pi``/``e`` (``*pi`` is accepted too) and the
single-argument functions ``sin cos tan cot sec csc arcsin arccos
arctan sinh cosh tanh coth sqrt cbrt log ln abs exp`` are supported,
where ``log`` is base-10 and ``ln`` is the natural logarithm. There is
no ``x`` variable (unlike *plot): both components must evaluate to
finite numbers.

``*vec`` takes exactly 2 components (``*vec(x ; y)``); commas work too
(``*vec(3, 4)``), and ``;`` wins when present so ``*vec(100,000 ; 2)``
keeps ``100,000`` intact (same friendly rule as *matrix cells).
"""

import ast
import operator
import re
import warnings

_VEC_CALL_RE = re.compile(r'\*vec\s*\(')

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
        'cot': lambda x: 1.0 / _np.tan(x),
        'sec': lambda x: 1.0 / _np.cos(x),
        'csc': lambda x: 1.0 / _np.sin(x),
        'arcsin': _np.arcsin,
        'arccos': _np.arccos,
        'arctan': _np.arctan,
        'sinh': _np.sinh,
        'cosh': _np.cosh,
        'tanh': _np.tanh,
        'coth': lambda x: 1.0 / _np.tanh(x),
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


def find_next_vec_call(text, start=0):
    """Locate the next ``*vec(`` call at/after *start*.

    Returns ``(call_start, inner_start, call_end, inner_raw)`` with
    depth-aware paren matching (quote-aware for ``"..."``), or None
    when no opener remains. Unclosed openers return an ``('unclosed',
    ...)`` marker so callers can warn without looping.
    """
    pos = start
    while True:
        m = _VEC_CALL_RE.search(text, pos)
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


def _preprocess_component(ctx, raw):
    """Substitute vars/defines and normalize calc-style syntax."""
    from .variables import replace_defines, replace_vars
    expr = replace_vars(ctx, raw)
    expr = replace_defines(ctx, expr)
    expr = re.sub(r'\*pi\b', 'pi', expr)
    # Accept math-command spellings (*sin(x), *sqrt(x)) inside vecs:
    # single-argument functions map to their bare numpy equivalents.
    expr = re.sub(
        r'\*(sin|cos|tan|cot|sec|csc|arcsin|arccos|arctan|sinh|cosh|tanh|coth|sqrt|cbrt|log|ln|abs|exp)\s*\(', r'\1(', expr)
    if ctx.mult_sym != '*':
        expr = re.sub(
            r'\s' + re.escape(ctx.mult_sym) + r'\s', ' * ', f' {expr} '
        ).strip()
    expr = re.sub(r'(?<=\d)\s+(?=\d{3}\b)', '', expr)
    # Decimal separator is a dot (3.5); commas are thousands only.
    expr = re.sub(r'(?<=\d),(?=\d{3}(?:,\d{3})*(?!\d))', '', expr)
    expr = expr.replace('^', '**')
    return expr.strip()


def evaluate_vec_component(ctx, raw):
    """Evaluate one *vec* component to a finite float.

    Raises ValueError with a user-facing reason for unsupported syntax
    (unknown names/functions, multi-arg calls, non-numeric literals)
    or non-finite results.
    """
    import math as _math
    import numpy as _np
    expr = _preprocess_component(ctx, raw)
    if not expr:
        raise ValueError('empty component')
    try:
        tree = ast.parse(expr, mode='eval')
    except SyntaxError as e:
        raise ValueError(f'cannot parse component {raw.strip()!r}: {e}')
    funcs = _numpy_funcs()
    consts = _numpy_consts()

    def eval_node(node):
        if isinstance(node, ast.Expression):
            return eval_node(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                raise ValueError(f'unsupported value {node.value!r}')
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise ValueError(f'unsupported value {node.value!r}')
        if isinstance(node, ast.Name):
            if node.id in consts:
                return float(consts[node.id])
            if node.id in ('inf', 'nan'):
                return float(getattr(_np, node.id))
            raise ValueError(
                f'unknown name {node.id!r} — only numbers, pi, e and '
                f'{sorted(funcs)} are supported')
        if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
            left = eval_node(node.left)
            right = eval_node(node.right)
            if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) and right == 0:
                raise ValueError('division by zero')
            return float(_BINOPS[type(node.op)](left, right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARYOPS:
            return float(_UNARYOPS[type(node.op)](eval_node(node.operand)))
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
            return float(funcs[fname](eval_node(node.args[0])))
        raise ValueError(
            f'unsupported syntax {ast.dump(node)} — use numbers, '
            f'+ - * / % ^ and single-argument functions')

    with _np.errstate(all='ignore'):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            try:
                result = eval_node(tree)
            except (ZeroDivisionError, OverflowError) as e:
                raise ValueError(str(e) or 'non-finite result')
    val = float(result)
    if not _math.isfinite(val):
        raise ValueError(f'component {raw.strip()!r} is not finite')
    return val


def vec_filename(stem, index):
    """SVG file name for the *index*-th vec diagram (1-based)."""
    return f'{stem}-vec-{index}.svg'


def render_vec_svg(ctx, dx, dy, out_path):
    """Render one 2D vector arrow (origin -> (dx, dy)); return the label.

    Raises ValueError (bad components) or OSError/RuntimeError
    (SVG backend failure) with user-facing messages.
    """
    import math as _math
    dx = float(dx)
    dy = float(dy)
    if not (_math.isfinite(dx) and _math.isfinite(dy)):
        raise ValueError(
            f'vector ({dx!r}, {dy!r}) is not finite')
    try:
        import matplotlib
        try:
            matplotlib.use('Agg')
        except Exception:
            pass
        import matplotlib.pyplot as plt
    except ImportError:
        raise RuntimeError(
            'vector diagrams need matplotlib — run `uv sync` to install it')
    label = f'vec({dx:g}, {dy:g})'
    try:
        with plt.rc_context({'svg.fonttype': 'none'}):
            fig, ax = plt.subplots(figsize=(5.5, 3.5))
            if dx == 0.0 and dy == 0.0:
                ax.plot([0.0], [0.0], marker='o', markersize=4,
                        color='#1f6feb', linestyle='None', label=label)
            else:
                ax.quiver(0.0, 0.0, dx, dy, angles='xy', scale_units='xy',
                          scale=1.0, color='#1f6feb', width=0.008,
                          headwidth=4.0, headlength=5.0, label=label)
            # Invisible span forces autoscaling to include origin and tip
            # (quiver alone does not autoscale reliably).
            ax.plot([0.0, dx], [0.0, dy], alpha=0.0)
            ax.set_xlabel('x')
            ax.set_ylabel('y')
            ax.set_title(label)
            ax.axhline(0, color='black', linewidth=0.8)
            ax.axvline(0, color='black', linewidth=0.8)
            ax.grid(True, linestyle='--', alpha=0.4)
            ax.set_aspect('equal', adjustable='datalim')
            ax.margins(0.15)
            fig.tight_layout()
            fig.savefig(out_path, format='svg', bbox_inches='tight')
            plt.close(fig)
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f'could not generate vec SVG: {e}')
    return label
