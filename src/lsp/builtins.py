"""Built-in completion/hover data (microcopy lives here, not in the compiler).

Function names and geometry command names are cross-checked against the
compiler's own tables (see _CROSS_CHECK below); only the short
descriptions are LSP-layer additions.
"""

from compiler.diagnostics import KNOWN_COMMANDS
from compiler.symbols import WORD_REPLACEMENTS
from geometry.commands import KNOWN_GEOMETRY_COMMANDS

# name -> (signature, short description).
#
# Math commands and their aliases are derived from the default command
# registry (src/compiler/commands.toml) so the LSP never drifts from the
# compiler. Non-math names (style, table, plot, image, page break) stay
# here because they are not part of the math registry.
from compiler.command_registry import DEFAULT_REGISTRY as _DEFAULT_REGISTRY

_EXTRA_MATH_DOCS = {
    'table': ('*table(cell ; cell | cell ; cell)', 'Table. Rows split on |, cells on ; (comma works when no ;).'),
    'plot': ('*plot(expression ; xmin ; xmax)', 'Plot y=f(x) as SVG (numerical, 1000 samples).'),
    'image': ('*image(path [; width])', 'Image from a file (width like 50% or 6cm). Relative paths resolve from the document folder.'),
    'newpage': ('*newpage', 'Page break (Typst pagebreak). Alias: *pagebreak. Bare or *newpage().'),
    'pagebreak': ('*pagebreak', 'Page break (alias of *newpage).'),
    'bold': ('*bold(text)', 'Bold text. Short alias: *b(...). Nesting, variables and calc() work inside.'),
    'b': ('*b(text)', 'Bold text (alias of *bold).'),
    'italic': ('*italic(text)', 'Italic text. Short alias: *i(...).'),
    'i': ('*i(text)', 'Italic text (alias of *italic).'),
    'underline': ('*underline(text)', 'Underlined text. Short alias: *u(...).'),
    'u': ('*u(text)', 'Underlined text (alias of *underline).'),
}

MATH_DOCS = {}
for _spec in _DEFAULT_REGISTRY.commands.values():
    MATH_DOCS[_spec.name] = (_spec.usage, _spec.doc)
    for _alias in _spec.aliases:
        _alias_usage = _spec.usage.replace(
            '*' + _spec.name, '*' + _alias, 1)
        MATH_DOCS[_alias] = (
            _alias_usage,
            f'{_spec.doc} (alias of *{_spec.name})',
        )
MATH_DOCS.update(_EXTRA_MATH_DOCS)

KEYWORD_DOCS = {
    'define': ('*define(name = value)', 'Define a reusable value. Also: *define x = 5, let x = 5.'),
    'calc': ('calc(expression)', 'Evaluate a math expression (numbers, pi/e, and sin/sqrt/... functions).'),
    'p': ('*p(expression)', 'Print raw text, bypassing other rules.'),
    'doc_title': ('*doc_title(title)', 'Set the document title (centered heading + PDF metadata). Aliases: *doc-title, *doctitle, *title.'),
    'doc_font': ('*doc_font(family [; size])', 'Set the document font family and size (e.g. *doc_font(DejaVu Sans ; 14pt)). Aliases: *doc-font, *docfont.'),
    # The *draw wrapper is a top-level control structure, not an inner
    # solver command: the geometry commands inside it live in
    # GEOMETRY_DOCS (kept == geometry.commands.KNOWN_GEOMETRY_COMMANDS,
    # which has no 'draw'), so *draw is documented here to give it
    # hover/completion without polluting the solver-command tables.
    'draw': ('*draw(...)', 'Draw a geometry figure. The block holds the geometry commands (*point, *line, *triangle, ...) and the constraint solver places the points.'),
}

GEOMETRY_DOCS = {
    'point': ('*point(name) / *point(name = x, y)', 'Create a point.'),
    'line': ('*line(A ; B)', 'Draw a segment from A to B.'),
    'ray': ('*ray(A ; B)', 'Ray starting at A through B.'),
    'circle': ('*circle(center ; radius-or-point)', 'Draw a circle.'),
    'triangle': ('*triangle(A ; B ; C)', 'Draw triangle ABC.'),
    'right-angle': ('*right-angle(B ; A ; C)', 'Right-angle marker at A.'),
    'angle': ('*angle(A ; B ; C [; label])', 'Angle marker at B.'),
    'equal-angle': ('*equal-angle(A ; B ; C ; D ; E ; F)', 'Angle ABC equals angle DEF (solver constraint; both angles get the same arc + tick marks).'),
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

# Constructors usable on the right side of *point(NAME = ...) — computed
# analytically, not commands of their own (kept out of
# KNOWN_GEOMETRY_COMMANDS/GEOMETRY_DOCS on purpose; see docs/geometry.md
# "Construction points"). Hover/completion read this table.
GEOMETRY_CONSTRUCTION_DOCS = {
    'midpoint': ('midpoint(A ; B)', 'Midpoint of segment AB. In *point(M = ...).'),
    'foot': ('foot(P ; line(A ; B))', 'Perpendicular foot of P on line AB.'),
    'reflect': ('reflect(P ; line(A ; B)) / reflect(P ; O)', 'Reflect P in a line, or through a point O.'),
    'intersect': ('intersect(line(A ; B) ; line(C ; D)) / intersect(... ; circle(...) ; k)', 'Intersection of two lines or circles (k = 1 or 2 picks the solution).'),
    'centroid': ('centroid(A ; B ; C)', 'Center of mass of the triangle ABC.'),
    'circumcenter': ('circumcenter(A ; B ; C)', 'Center of the circle through A, B, C.'),
    'incenter': ('incenter(A ; B ; C)', 'Center of the incircle of triangle ABC.'),
    'orthocenter': ('orthocenter(A ; B ; C)', 'Intersection of the triangle\'s altitudes.'),
}

# Sanity: geometry docs must match the geometry command table. Math docs
# are now derived from the command registry, so they cannot diverge.
_CROSS_CHECK = (set(GEOMETRY_DOCS) == set(KNOWN_GEOMETRY_COMMANDS))
if not _CROSS_CHECK:  # pragma: no cover - startup safety, not a crash
    import logging as _logging
    _logging.getLogger('easy-math-lsp').warning(
        'lsp builtins diverged from geometry command tables; '
        'continuing with best-effort tables'
    )


def symbol_entries():
    """Yield (word, glyph) from the compiler's own replacement table."""
    return list(WORD_REPLACEMENTS)
