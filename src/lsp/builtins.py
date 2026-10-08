"""Built-in completion/hover data (microcopy lives here, not in the compiler).

Function names and geometry command names are cross-checked against the
compiler's own tables (see _CROSS_CHECK below); only the short
descriptions are LSP-layer additions.
"""

from compiler.diagnostics import KNOWN_COMMANDS
from compiler.symbols import WORD_REPLACEMENTS
from geometry.commands import KNOWN_GEOMETRY_COMMANDS

# name -> (signature, short description), from rule.txt.
# Friendly aliases point at the same docs (completion shows both).
MATH_DOCS = {
    'frac': ('*frac(numerator ; denominator)', 'Fraction. Comma also works: *frac(2, 3).'),
    'fraction': ('*fraction(numerator ; denominator)', 'Fraction (alias of *frac).'),
    'abs': ('*abs(expression)', 'Absolute value.'),
    'absolute': ('*absolute(expression)', 'Absolute value (alias of *abs).'),
    'sin': ('*sin(x)', 'Sine.'),
    'cos': ('*cos(x)', 'Cosine.'),
    'tan': ('*tan(x)', 'Tangent.'),
    'sqrt': ('*sqrt(x)', 'Square root.'),
    'squareroot': ('*squareroot(x)', 'Square root (alias of *sqrt).'),
    'square-root': ('*square-root(x)', 'Square root (alias of *sqrt).'),
    'cbrt': ('*cbrt(x)', 'Cube root (same as *root(3 ; x)).'),
    'cuberoot': ('*cuberoot(x)', 'Cube root (alias of *cbrt).'),
    'cube-root': ('*cube-root(x)', 'Cube root (alias of *cbrt).'),
    'log': ('*log(x)', 'Logarithm.'),
    'ln': ('*ln(x)', 'Natural logarithm.'),
    'pow': ('*pow(base ; exponent)', 'Power. Comma also works: *pow(x, 2).'),
    'power': ('*power(base ; exponent)', 'Power (alias of *pow).'),
    'root': ('*root(index ; radicand)', 'Root.'),
    'sum': ('*sum(lower ; upper ; expression)', 'Summation.'),
    'summation': ('*summation(lower ; upper ; expression)', 'Summation (alias of *sum).'),
    'prod': ('*prod(lower ; upper ; expression)', 'Product.'),
    'product': ('*product(lower ; upper ; expression)', 'Product (alias of *prod).'),
    'lim': ('*lim(variable -> value ; expression)', 'Limit.'),
    'limit': ('*limit(variable -> value ; expression)', 'Limit (alias of *lim).'),
    'table': ('*table(cell ; cell | cell ; cell)', 'Table. Rows split on |, cells on ; (comma works when no ;).'),
    'matrix': ('*matrix(1 ; 2 | 3 ; 4)', 'Matrix (Typst mat). Rows split on |, cells on ;.'),
    'mat': ('*mat(1 ; 2 | 3 ; 4)', 'Matrix (alias of *matrix).'),
    'plot': ('*plot(expression ; xmin ; xmax)', 'Plot y=f(x) as SVG (numerical, 1000 samples).'),
}

KEYWORD_DOCS = {
    'define': ('*define(name = value)', 'Define a reusable value. Also: *define x = 5, let x = 5.'),
    'calc': ('calc(expression)', 'Evaluate a math expression.'),
    'p': ('*p(expression)', 'Print raw text, bypassing other rules.'),
}

GEOMETRY_DOCS = {
    'point': ('*point(name) / *point(name = x, y)', 'Create a point.'),
    'line': ('*line(A ; B)', 'Draw a segment from A to B.'),
    'ray': ('*ray(A ; B)', 'Ray starting at A through B.'),
    'circle': ('*circle(center ; radius-or-point)', 'Draw a circle.'),
    'triangle': ('*triangle(A ; B ; C)', 'Draw triangle ABC.'),
    'right-angle': ('*right-angle(B ; A ; C)', 'Right-angle marker at A.'),
    'angle': ('*angle(A ; B ; C [; label])', 'Angle marker at B.'),
    'equal-angle': ('*equal-angle(...)', 'Mark two angles equal. [planned]'),
    'equal-length': ('*equal-length(A ; B ; C ; D)', 'Mark AB and CD equal.'),
    'parallel': ('*parallel(A ; B ; C ; D)', 'AB is parallel to CD.'),
    'perp': ('*perp(...)', 'Perpendicular constraint/marker.'),
    'on-line': ('*on-line(A ; B ; C)', 'C lies on line AB.'),
    'on-circle': ('*on-circle(O ; r ; A)', 'A lies on the circle.'),
    'distance': ('*distance(A ; B ; d)', 'AB has length d.'),
    'midpoint': ('*midpoint(A ; B ; C)', 'C is the midpoint of AB.'),
    'intersection': ('*intersection(C ; line(A;B) ; line(D;E))', 'Point at intersection.'),
    'arc': ('*arc(center ; start ; end)', 'Arc around center from start to end (counterclockwise).'),
    'label': ('*label(point ; text)', 'Custom text label near a point.'),
    'length': ('*length(A ; B)', 'Show the measured length of AB.'),
    'angle-value': ('*angle-value(A ; B ; C)', 'Show the measured angle at B.'),
}

# Sanity: every builtin we advertise must exist in the compiler tables, and
# every compiler math command must be advertised (no silent divergence).
_CROSS_CHECK = (
    set(MATH_DOCS) <= KNOWN_COMMANDS
    and {'frac', 'abs', 'sin', 'cos', 'tan', 'sqrt', 'cbrt', 'log', 'ln',
         'pow', 'root', 'sum', 'prod', 'lim'} <= set(MATH_DOCS)
    and set(GEOMETRY_DOCS) == set(KNOWN_GEOMETRY_COMMANDS)
)
if not _CROSS_CHECK:  # pragma: no cover - startup safety, not a crash
    import logging as _logging
    _logging.getLogger('easy-math-lsp').warning(
        'lsp builtins diverged from compiler command tables; '
        'continuing with best-effort tables'
    )


def symbol_entries():
    """Yield (word, glyph) from the compiler's own replacement table."""
    return list(WORD_REPLACEMENTS)
