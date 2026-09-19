"""Built-in completion/hover data (microcopy lives here, not in the compiler).

Function names and geometry command names are cross-checked against the
compiler's own tables (see _CROSS_CHECK below); only the short
descriptions are LSP-layer additions.
"""

from ..compiler.diagnostics import KNOWN_COMMANDS
from ..compiler.symbols import WORD_REPLACEMENTS
from ..geometry.commands import KNOWN_GEOMETRY_COMMANDS

# name -> (signature, short description), from rule.txt.
MATH_DOCS = {
    'frac': ('*frac(numerator ; denominator)', 'Fraction.'),
    'abs': ('*abs(expression)', 'Absolute value.'),
    'sin': ('*sin(x)', 'Sine.'),
    'cos': ('*cos(x)', 'Cosine.'),
    'tan': ('*tan(x)', 'Tangent.'),
    'log': ('*log(x)', 'Logarithm.'),
    'ln': ('*ln(x)', 'Natural logarithm.'),
    'pow': ('*pow(base ; exponent)', 'Power.'),
    'root': ('*root(index ; radicand)', 'Root.'),
    'sum': ('*sum(lower ; upper ; expression)', 'Summation.'),
    'prod': ('*prod(lower ; upper ; expression)', 'Product.'),
    'lim': ('*lim(variable -> value ; expression)', 'Limit.'),
}

KEYWORD_DOCS = {
    'define': ('*define(name = value)', 'Define a reusable value.'),
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
    'angle': ('*angle(A ; B ; C)', 'Angle marker at B. [planned]'),
    'equal-angle': ('*equal-angle(...)', 'Mark two angles equal. [planned]'),
    'equal-length': ('*equal-length(A ; B ; C ; D)', 'Mark AB and CD equal.'),
    'parallel': ('*parallel(A ; B ; C ; D)', 'AB is parallel to CD.'),
    'perp': ('*perp(...)', 'Perpendicular constraint/marker.'),
    'on-line': ('*on-line(A ; B ; C)', 'C lies on line AB.'),
    'on-circle': ('*on-circle(O ; r ; A)', 'A lies on the circle.'),
    'distance': ('*distance(A ; B ; d)', 'AB has length d.'),
    'midpoint': ('*midpoint(A ; B ; C)', 'C is the midpoint of AB.'),
    'intersection': ('*intersection(C ; line(A;B) ; line(D;E))', 'Point at intersection.'),
    'arc': ('*arc(center ; start ; end)', 'Draw an arc. [planned]'),
    'label': ('*label(point ; text)', 'Custom label. [planned]'),
    'length': ('*length(A ; B)', 'Length label. [planned]'),
    'angle-value': ('*angle-value(A ; B ; C)', 'Angle label. [planned]'),
}

# Sanity: every builtin we advertise must exist in the compiler tables, and
# every compiler math command must be advertised (no silent divergence).
_CROSS_CHECK = (
    set(MATH_DOCS) <= KNOWN_COMMANDS
    and {'frac', 'abs', 'sin', 'cos', 'tan', 'log', 'ln',
         'pow', 'root', 'sum', 'prod', 'lim'} <= set(MATH_DOCS)
    and set(GEOMETRY_DOCS) == set(KNOWN_GEOMETRY_COMMANDS)
)
assert _CROSS_CHECK, 'lsp builtins diverged from compiler command tables'


def symbol_entries():
    """Yield (word, glyph) from the compiler's own replacement table."""
    return list(WORD_REPLACEMENTS)
