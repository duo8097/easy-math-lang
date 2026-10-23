"""Shared safe math evaluator: function whitelist for calc/plot.

Single source of truth for the single-argument function whitelist
(``sin cos tan cot sec csc arcsin arccos arctan sinh cosh tanh coth
sqrt cbrt log ln abs exp``, where ``log`` is base-10 like Typst's
``log`` and ``ln`` is the natural logarithm) plus the constants
``pi`` and ``e``.

- Scalar (stdlib :mod:`math`) implementations back ``calc()``.
- NumPy implementations back ``*plot`` (elementwise).
- Shared preprocessing: ``<vars>``/defines, ``*``-spellings
  (``*sin(x)``, ``*pi``), the custom multiplication symbol,
  thousands separators, decimal dots and ``^`` power.

The ``*``-spelling mapping only fires when the star starts a word
(not preceded by a letter, digit or another star), so ``2*sin(x)``
stays ``2 * sin(x)`` (multiplication) instead of collapsing to
``2sin(x)``, and ``2**sin(x)`` keeps its ``**`` power.
"""

import math
import re

#: Whitelisted single-argument functions (evaluation order irrelevant).
FUNCTION_NAMES = (
    'sin', 'cos', 'tan', 'cot', 'sec', 'csc',
    'arcsin', 'arccos', 'arctan',
    'sinh', 'cosh', 'tanh', 'coth',
    'sqrt', 'cbrt', 'log', 'ln', 'abs', 'exp',
)

#: Whitelisted constants (scalar values; NumPy equivalents via numpy_consts).
CONST_NAMES = ('pi', 'e')


def bounded_power(left, right):
    """Bound scalar powers before Python allocates enormous integers.

    NumPy arrays already use fixed-size arithmetic. Scalar subexpressions
    in plots need the same guard as calc, even before array conversion.
    """
    if type(left) in (int, float) and type(right) in (int, float):
        if abs(right) > 1000 or (abs(left) > 10 and abs(right) > 100):
            raise ValueError('calc: exponent too large')
    return left ** right


def scalar_consts():
    """``{'pi': ..., 'e': ...}`` (stdlib floats, for ``calc()``)."""
    return {'pi': math.pi, 'e': math.e}


def _cbrt(x):
    """Cube root that snaps exact cubes back to whole floats.

    Some libm builds return e.g. 3.0000000000000004 for cbrt(27),
    which would print as ``3.0000000000000004`` instead of ``3``.
    When the result rounds to an integer whose cube is exactly the
    input, return that integer as a float (the calc layer then folds
    it to an int); otherwise return the raw libm value untouched.
    """
    r = math.cbrt(x)
    if math.isfinite(r):
        n = round(r)
        try:
            if n ** 3 == x:
                return float(n)
        except (OverflowError, ValueError):
            pass
    return r


def scalar_funcs():
    """Name -> callable for ``calc()`` (stdlib :mod:`math` semantics)."""
    return {
        'sin': math.sin,
        'cos': math.cos,
        'tan': math.tan,
        'cot': lambda x: 1.0 / math.tan(x),
        'sec': lambda x: 1.0 / math.cos(x),
        'csc': lambda x: 1.0 / math.sin(x),
        'arcsin': math.asin,
        'arccos': math.acos,
        'arctan': math.atan,
        'sinh': math.sinh,
        'cosh': math.cosh,
        'tanh': math.tanh,
        'coth': lambda x: 1.0 / math.tanh(x),
        'sqrt': math.sqrt,
        'cbrt': _cbrt,
        'log': math.log10,
        'ln': math.log,
        'abs': abs,
        'exp': math.exp,
    }


def numpy_funcs():
    """Name -> callable for ``*plot`` (lazy NumPy import)."""
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


def numpy_consts():
    """``{'pi': ..., 'e': ...}`` (lazy NumPy import, for plot)."""
    import numpy as _np
    return {'pi': _np.pi, 'e': _np.e}


_STAR_FUNC_RE = re.compile(
    r'(?<![A-Za-z0-9_*])\*(' + '|'.join(FUNCTION_NAMES) + r')\s*\('
)
_STAR_PI_RE = re.compile(r'(?<![A-Za-z0-9_*])\*pi\b')
_STAR_INFINITY_RE = re.compile(r'(?<![A-Za-z0-9_*])\*infinity\b')


def preprocess_math_expr(ctx, raw, *, map_infinity=False):
    """Substitute vars/defines and normalize calc-style syntax (shared).

    Steps (same family as the old per-module copies): ``<vars>`` and
    defines, ``*``-spellings (``*sin(x)`` -> ``sin(x)``, ``*pi`` ->
    ``pi``), the custom multiplication symbol (spaced only, so
    decimals and words are safe), thousands separators (spaces and
    commas), and ``^`` power. ``*infinity`` -> ``inf`` only when
    *map_infinity* is true (plots); ``calc()`` rejects it.
    """
    from .variables import replace_defines, replace_vars
    expr = replace_vars(ctx, raw)
    expr = replace_defines(ctx, expr)
    expr = _STAR_FUNC_RE.sub(r'\1(', expr)
    expr = _STAR_PI_RE.sub('pi', expr)
    if map_infinity:
        expr = _STAR_INFINITY_RE.sub('inf', expr)
    if ctx.mult_sym != '*':
        expr = re.sub(
            r'\s' + re.escape(ctx.mult_sym) + r'\s', ' * ', f' {expr} '
        ).strip()
    expr = re.sub(r'(?<=\d)\s+(?=\d{3}\b)', '', expr)
    # Decimal separator is a dot (3.5); commas are thousands only and
    # are stripped first (100,000 -> plain digits). A comma that
    # remains (e.g. 3,5) is left as-is so ast.parse fails with a clear
    # error — use a dot for decimals and ';' for argument separators.
    expr = re.sub(r'(?<=\d),(?=\d{3}(?:,\d{3})*(?!\d))', '', expr)
    expr = expr.replace('^', '**')
    return expr.strip()
