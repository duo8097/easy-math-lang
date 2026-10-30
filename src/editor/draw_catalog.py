"""Qt-free catalog + insertion math for the editor's *draw gallery.

One entry per command in ``geometry.commands.KNOWN_GEOMETRY_COMMANDS``
covering the gallery cards (group, title, syntax, description, example)
plus the pure functions the gallery needs:

- :func:`find_enclosing_draw_block` — span of the ``*draw(...)`` block
  containing an offset (mirrors ``compiler.pipeline``'s detection).
- :func:`build_insert_text` — where an example block / command line
  goes: inside an existing block it lands just before the closing
  ``)``; outside it becomes its own ``*draw(...)`` block.
- :func:`commands_in` / :func:`symbol_for_command` — which commands
  the template window's palette pins to the top (the ones the code
  uses), and which commands have a ``geo-*`` parameter dialog.

Sources of truth — never duplicated here:

- the command list: ``geometry.commands.KNOWN_GEOMETRY_COMMANDS``
- syntax + one-line description: ``lsp.builtins.GEOMETRY_DOCS``
- ``geo-*`` dialog mapping: ``editor.symbol_registry`` (None when a
  command has no parameter dialog, e.g. ``equal-angle``).

Examples are validated by the tests through
``geometry.parse_draw_block`` — the ONE geometry parser; this module
never re-implements parsing or solving.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

try:  # Reuse compiler tables; fall back gracefully on odd sys.path setups.
    from geometry.commands import KNOWN_GEOMETRY_COMMANDS as _GEO_KNOWN
except Exception:  # pragma: no cover - defensive
    _GEO_KNOWN = frozenset()

try:
    from lsp.builtins import GEOMETRY_DOCS
except Exception:  # pragma: no cover - defensive
    GEOMETRY_DOCS = {}

# ----------------------------------------------------------------------
# Groups
# ----------------------------------------------------------------------

GROUP_SHAPES = 'Shapes'
GROUP_ANGLES = 'Angles'
GROUP_CONSTRAINTS = 'Constraints'
GROUP_MEASURE = 'Measure & Label'

#: Stable gallery order.
GROUPS = (GROUP_SHAPES, GROUP_ANGLES, GROUP_CONSTRAINTS, GROUP_MEASURE)

#: Indentation used for generated ``*draw(...)`` blocks and for lines
#: added to a block that has no content yet.
DEFAULT_INDENT = '    '


# ----------------------------------------------------------------------
# Entries
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class CatalogEntry:
    """One geometry command as shown on a gallery card."""

    id: str            # unique; also the thumbnail file name (<id>.svg)
    command: str       # compiler command name (no '*')
    group: str         # one of GROUPS
    title: str         # short human title
    syntax: str        # from GEOMETRY_DOCS (never hand-written)
    description: str   # one line, from GEOMETRY_DOCS (never hand-written)
    example: str       # full multi-line *draw(...) block, validated in tests
    symbol: str | None  # geo-* palette id with a dialog, else None

    @property
    def search_text(self) -> str:
        """Lower-cased haystack for the gallery's search box."""
        return ' '.join((self.id, self.command, self.group, self.title,
                         self.syntax, self.description)).lower()


# (command, group, title) — order defines the gallery order.  The test
# suite asserts this covers KNOWN_GEOMETRY_COMMANDS exactly.
_COMMAND_SPECS: tuple[tuple[str, str, str], ...] = (
    ('point', GROUP_SHAPES, 'Point'),
    ('line', GROUP_SHAPES, 'Line segment'),
    ('ray', GROUP_SHAPES, 'Ray'),
    ('circle', GROUP_SHAPES, 'Circle'),
    ('triangle', GROUP_SHAPES, 'Triangle'),
    ('arc', GROUP_SHAPES, 'Arc'),
    ('angle', GROUP_ANGLES, 'Angle marker'),
    ('right-angle', GROUP_ANGLES, 'Right-angle marker'),
    ('equal-angle', GROUP_ANGLES, 'Equal angles'),
    ('distance', GROUP_CONSTRAINTS, 'Distance'),
    ('parallel', GROUP_CONSTRAINTS, 'Parallel lines'),
    ('perp', GROUP_CONSTRAINTS, 'Perpendicular'),
    ('on-line', GROUP_CONSTRAINTS, 'Point on a line'),
    ('on-circle', GROUP_CONSTRAINTS, 'Point on a circle'),
    ('equal-length', GROUP_CONSTRAINTS, 'Equal lengths'),
    ('midpoint', GROUP_CONSTRAINTS, 'Midpoint'),
    ('intersection', GROUP_CONSTRAINTS, 'Intersection'),
    ('label', GROUP_MEASURE, 'Text label'),
    ('length', GROUP_MEASURE, 'Length measure'),
    ('angle-value', GROUP_MEASURE, 'Angle measure'),
)

#: A full ``*draw(...)`` block showing the command in a meaningful
#: context.  Only syntax documented in docs/geometry.md /
#: examples/draw_test.ezmath and exercised by geometry/commands.py is
#: used; tests parse every example with geometry.parse_draw_block.
_EXAMPLES: dict[str, str] = {
    'point': (
        '*draw(\n'
        '    *point(A = 0, 0)\n'
        '    *point(B = 5, 0)\n'
        '    *point(C)\n'
        '    *distance(A ; C ; 3)\n'
        '    *distance(B ; C ; 4)\n'
        '    *line(A ; C)\n'
        '    *line(B ; C)\n'
        ')'
    ),
    'line': (
        '*draw(\n'
        '    *point(A = 1, 1)\n'
        '    *point(B = 6, 4)\n'
        '    *line(A ; B)\n'
        ')'
    ),
    'ray': (
        '*draw(\n'
        '    *point(A = 1, 1)\n'
        '    *point(B = 4, 3)\n'
        '    *ray(A ; B)\n'
        ')'
    ),
    'circle': (
        '*draw(\n'
        '    *point(O = 0, 0)\n'
        '    *point(A = 3, 0)\n'
        '    *circle(O ; A)\n'
        ')'
    ),
    'triangle': (
        '*draw(\n'
        '    *point(A = 0, 0)\n'
        '    *point(B = 6, 0)\n'
        '    *point(C = 3, 4)\n'
        '    *triangle(A ; B ; C)\n'
        ')'
    ),
    'arc': (
        '*draw(\n'
        '    *point(O = 0, 0)\n'
        '    *point(A = 4, 0)\n'
        '    *point(B = 0, 4)\n'
        '    *arc(O ; A ; B)\n'
        '    *line(O ; A)\n'
        '    *line(O ; B)\n'
        ')'
    ),
    'angle': (
        '*draw(\n'
        '    *point(A = 0, 0)\n'
        '    *point(B = 4, 0)\n'
        '    *point(C = 1, 3)\n'
        '    *triangle(A ; B ; C)\n'
        '    *angle(A ; B ; C ; 45°)\n'
        ')'
    ),
    'right-angle': (
        '*draw(\n'
        '    *point(A = 0, 0)\n'
        '    *point(B = 5, 0)\n'
        '    *point(C = 0, 4)\n'
        '    *triangle(A ; B ; C)\n'
        '    *right-angle(B ; A ; C)\n'
        ')'
    ),
    # equal-angle is [planned] (codegen raises "not yet implemented");
    # the example shows the intended usage with two congruent angles.
    'equal-angle': (
        '*draw(\n'
        '    *point(A = 0, 0)\n'
        '    *point(B = 4, 0)\n'
        '    *point(C = 2, 3)\n'
        '    *point(D = 7, 0)\n'
        '    *point(E = 11, 0)\n'
        '    *point(F = 9, 3)\n'
        '    *triangle(A ; B ; C)\n'
        '    *triangle(D ; E ; F)\n'
        '    *equal-angle(A ; B ; C ; D ; E ; F)\n'
        ')'
    ),
    'distance': (
        '*draw(\n'
        '    *point(A = 0, 0)\n'
        '    *point(B)\n'
        '    *distance(A ; B ; 5)\n'
        '    *line(A ; B)\n'
        ')'
    ),
    'parallel': (
        '*draw(\n'
        '    *point(A = 0, 0)\n'
        '    *point(B = 5, 0)\n'
        '    *point(C = 1, 3)\n'
        '    *point(D)\n'
        '    *parallel(A ; B ; C ; D)\n'
        '    *distance(C ; D ; 5)\n'
        '    *line(A ; B)\n'
        '    *line(C ; D)\n'
        ')'
    ),
    'perp': (
        # Right triangle built with *perp (docs/geometry.md example 1).
        '*draw(\n'
        '    *point(A = 0, 0)\n'
        '    *point(B = 4, 0)\n'
        '    *point(C)\n'
        '    *distance(A ; C ; 3)\n'
        '    *perp(A ; B ; A ; C)\n'
        '    *triangle(A ; B ; C)\n'
        '    *right-angle(B ; A ; C)\n'
        ')'
    ),
    'on-line': (
        '*draw(\n'
        '    *point(A = 0, 0)\n'
        '    *point(B = 5, 2)\n'
        '    *point(C)\n'
        '    *on-line(A ; B ; C)\n'
        '    *distance(B ; C ; 3)\n'
        '    *line(A ; B)\n'
        '    *line(B ; C)\n'
        ')'
    ),
    'on-circle': (
        '*draw(\n'
        '    *point(O = 0, 0)\n'
        '    *circle(O ; 3)\n'
        '    *point(A)\n'
        '    *on-circle(O ; 3 ; A)\n'
        '    *line(O ; A)\n'
        ')'
    ),
    'equal-length': (
        # Isosceles triangle (docs/geometry.md example 2).
        '*draw(\n'
        '    *point(A = 0, 0)\n'
        '    *point(B = 6, 0)\n'
        '    *point(C)\n'
        '    *equal-length(A ; C ; B ; C)\n'
        '    *distance(A ; C ; 5)\n'
        '    *triangle(A ; B ; C)\n'
        ')'
    ),
    'midpoint': (
        '*draw(\n'
        '    *point(A = 0, 0)\n'
        '    *point(B = 6, 0)\n'
        '    *point(M)\n'
        '    *midpoint(A ; B ; M)\n'
        '    *point(C = 2, 5)\n'
        '    *triangle(A ; B ; C)\n'
        '    *line(C ; M)\n'
        ')'
    ),
    'intersection': (
        '*draw(\n'
        '    *point(A = 0, 0)\n'
        '    *point(B = 5, 0)\n'
        '    *point(C = 0, 4)\n'
        '    *point(D = 5, 4)\n'
        '    *intersection(P ; line(A ; D) ; line(B ; C))\n'
        '    *line(A ; D)\n'
        '    *line(B ; C)\n'
        ')'
    ),
    'label': (
        '*draw(\n'
        '    *point(A = 0, 0)\n'
        '    *point(B = 5, 0)\n'
        '    *point(C = 2, 4)\n'
        '    *triangle(A ; B ; C)\n'
        '    *label(A ; vertex)\n'
        ')'
    ),
    'length': (
        '*draw(\n'
        '    *point(A = 0, 0)\n'
        '    *point(B = 4, 0)\n'
        '    *point(C = 0, 3)\n'
        '    *triangle(A ; B ; C)\n'
        '    *length(A ; B)\n'
        '    *length(A ; C) = 3\n'
        ')'
    ),
    'angle-value': (
        '*draw(\n'
        '    *point(A = 0, 0)\n'
        '    *point(B = 6, 0)\n'
        '    *point(C = 6, 4)\n'
        '    *triangle(A ; B ; C)\n'
        '    *right-angle(A ; B ; C)\n'
        '    *angle-value(B ; A ; C)\n'
        ')'
    ),
}


def _symbol_map() -> dict[str, str]:
    """command name -> palette id of its ``geo-*`` dialog symbol."""
    try:
        from editor.symbol_registry import list_symbols
    except Exception:  # pragma: no cover - defensive
        return {}
    mapping: dict[str, str] = {}
    for sym in list_symbols():
        if sym.requires_dialog and sym.wrap_draw and sym.command:
            mapping.setdefault(sym.command, sym.name)
    return mapping


def _build_catalog() -> tuple[CatalogEntry, ...]:
    symbols = _symbol_map()
    entries = []
    for command, group, title in _COMMAND_SPECS:
        syntax, description = GEOMETRY_DOCS.get(
            command, (f'*{command}(...)', ''))
        entries.append(CatalogEntry(
            id=command,
            command=command,
            group=group,
            title=title,
            syntax=syntax or f'*{command}(...)',
            description=description or title,
            example=_EXAMPLES[command],
            symbol=symbols.get(command),
        ))
    return tuple(entries)


#: All entries, in gallery order.
CATALOG: tuple[CatalogEntry, ...] = _build_catalog()


def catalog_entries(group: str | None = None) -> list[CatalogEntry]:
    """Every entry (optionally filtered to one group), gallery order."""
    if group in (None, '', 'All'):
        return list(CATALOG)
    return [e for e in CATALOG if e.group == group]


def get_entry(key: str) -> CatalogEntry:
    """Entry by id/command; raises KeyError when unknown."""
    for entry in CATALOG:
        if entry.id == key or entry.command == key:
            return entry
    raise KeyError(f'unknown draw catalog entry {key!r}')


def symbol_for_command(command: str) -> str | None:
    """Palette id of the ``geo-*`` parameter dialog for *command*.

    ``None`` when the command has no dialog (e.g. ``equal-angle``) or
    is not a geometry command at all — the template window's palette
    uses this to grey out rows it cannot open.
    """
    return _symbol_map().get(command)


#: A call-like ``name(`` occurrence (``*point(``, nested ``line(``).
_COMMAND_CALL_RE = re.compile(r'([A-Za-z][A-Za-z0-9-]*)\s*\(')


def commands_in(text: str) -> list[str]:
    """Geometry commands called in *text*, first-appearance order.

    Identifies the commands the template window's palette pins to the
    top — the palette lists every catalog command, these are the ones
    actually used in the (editable) snippet: wrapped
    (``*point(...)``) or nested (the unstarred ``line(...)`` inside
    ``intersection``), each exactly once where it is first used.
    Non-geometry calls (``draw(``, ``calc(``, user functions …) are
    not catalog commands and drop out, and so do commands mentioned
    only in ``//`` comments or fenced code blocks — the same line
    rules ``find_enclosing_draw_block`` applies.
    """
    text = text if isinstance(text, str) else str(text or '')
    known = {entry.command for entry in CATALOG}
    seen: list[str] = []
    in_fence = False
    for raw in text.split('\n'):
        if raw.strip().startswith('```'):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in _COMMAND_CALL_RE.finditer(_strip_line_comment(raw)):
            name = match.group(1)
            if name in known and name not in seen:
                seen.append(name)
    return seen


# ----------------------------------------------------------------------
# Block detection (mirrors compiler.pipeline's *draw handling)
# ----------------------------------------------------------------------

def _iter_lines(text: str):
    """Yield ``(line_start_offset, line_without_newline)``."""
    start = 0
    for line in text.split('\n'):
        yield start, line
        start += len(line) + 1


def _strip_line_comment(line: str) -> str:
    """Remove a trailing ``//`` comment from *line* (length-preserving
    prefix), reusing the compiler's own protection rules.

    Mirrors the per-line core of ``compiler.comments.strip_comments``
    (URL shield + balanced ``*command(...)`` ranges) but works on a
    single line so the caller keeps exact offsets into the original
    text — ``strip_comments`` on the whole document would shift every
    offset after the first comment.
    """
    from compiler.comments import _find_comment_start, _protected_ranges

    placeholder = '\x00URLSLASH\x00'
    line_prot = re.sub(
        r'([A-Za-z][A-Za-z0-9+.-]*://\S*)',
        lambda m: m.group(1).replace('/', placeholder),
        line,
    )
    idx = _find_comment_start(line_prot, _protected_ranges(line_prot))
    if idx != -1:
        line_prot = line_prot[:idx]
    return line_prot.replace(placeholder, '/')


def find_enclosing_draw_block(text: str, pos: int) -> tuple[int, int] | None:
    """Span ``(start, end)`` of the ``*draw(...)`` block containing *pos*.

    ``start`` is the offset of the ``*`` in ``*draw(``; ``end`` sits
    just past the closing ``)``.  Returns None when *pos* is outside
    every block (or inside a fenced code sample).

    Mirrors ``compiler.pipeline``: a single-line ``*draw(...)`` (the
    line starts with ``*draw(`` and ends with ``)``) or a multi-line
    block opened by a line that is exactly ``*draw(`` and closed by a
    line that is exactly ``)`` — after ``//`` comment stripping and
    whitespace trimming, with ``//`` comments, fenced blocks and nested
    parentheses (``line(A ; B)``) handled the same way the compiler
    handles them.  No second parser: this only locates the block; the
    contents stay the geometry package's business.
    """
    text = text if isinstance(text, str) else str(text or '')
    try:
        pos = int(pos)
    except (TypeError, ValueError):
        pos = 0
    pos = max(0, min(pos, len(text)))

    in_fence = False
    in_block = False
    block_start = 0
    for line_start, raw in _iter_lines(text):
        if raw.strip().startswith('```'):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        commentless = _strip_line_comment(raw)
        core = commentless.strip()
        if not core:
            continue
        if in_block:
            if core == ')':
                end = line_start + commentless.index(')') + 1
                if block_start <= pos <= end:
                    return (block_start, end)
                in_block = False
            continue
        # Single-line form is checked first, like the pipeline does.
        if core.startswith('*draw(') and core.endswith(')'):
            lead = len(raw) - len(raw.lstrip())
            start = line_start + lead
            end = start + len(core)
            if start <= pos <= end:
                return (start, end)
            continue
        if core == '*draw(':
            in_block = True
            block_start = line_start + (len(raw) - len(raw.lstrip()))
    return None


def draw_block_body(text: str) -> str:
    """Inner content of a ``*draw(...)`` block — exactly what
    ``geometry.parse_draw_block`` receives.

    The compiler strips the ``*draw(`` / ``)`` wrapper before calling
    the ONE geometry parser (single-line: ``line[6:-1]``; multi-line:
    the lines between opener and closer); this mirrors that for the
    tests and the preview-rendering script, and passes non-block text
    through unchanged (treated as an already-unwrapped body).
    """
    span = find_enclosing_draw_block(text, 0)
    if span is None:
        return text
    start, end = span
    return text[start + 6:end - 1]


# ----------------------------------------------------------------------
# Insertion math
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class TextInsert:
    """One document edit: replace ``text[start:end]`` with ``insert``.

    ``cursor_offset`` places the caret at ``start + cursor_offset``
    inside the freshly inserted text.  Applying the whole thing inside
    ``QTextCursor.beginEditBlock()/endEditBlock()`` makes it a single
    undo step.
    """

    start: int
    end: int
    insert: str
    cursor_offset: int

    @property
    def cursor(self) -> int:
        return self.start + self.cursor_offset


def _split_source(source) -> tuple[list[str], str]:
    """Normalize *source* into ``(inner_command_lines, wrapped_block)``.

    *source* may be a :class:`CatalogEntry` (its example), a full
    ``*draw(...)`` block (single- or multi-line, as produced by
    ``symbol_registry.build_source``) or one/more bare command lines.
    """
    if isinstance(source, CatalogEntry):
        text = source.example
    else:
        text = source if isinstance(source, str) else str(source or '')
    text = text.replace('\r\n', '\n').replace('\r', '\n').strip('\n')
    if not text.strip():
        raise ValueError('nothing to insert')
    lines = text.split('\n')
    if lines[0].startswith('*draw('):
        if len(lines) == 1 and lines[0].endswith(')'):
            # Single-line *draw(...) — mirror the pipeline's [6:-1].
            inner = [lines[0][6:-1].strip()] if lines[0][6:-1].strip() else []
            wrapped = text
            return inner, wrapped
        if lines[-1].strip() == ')':
            inner = [ln.strip() for ln in lines[1:-1] if ln.strip()]
            wrapped = text
            return inner, wrapped
        raise ValueError('unterminated *draw(...) block')
    # Bare command line(s): wrap them for the "outside a block" case.
    body = '\n'.join(DEFAULT_INDENT + ln.strip() for ln in lines if ln.strip())
    wrapped = f'*draw(\n{body}\n)'
    return [ln.strip() for ln in lines if ln.strip()], wrapped


def _inner_indent(text: str, start: int, end: int) -> str:
    """Indentation of existing block content (default 4 spaces)."""
    inner = text[start:end]
    for line in inner.split('\n')[1:]:
        stripped = line.strip()
        if stripped and stripped != ')':
            return line[:len(line) - len(line.lstrip())]
    return DEFAULT_INDENT


def build_insert_text(source, text: str, pos: int) -> TextInsert:
    """Where to put *source* in *text* so the document stays valid.

    - Cursor inside a ``*draw(...)`` block: the command line(s) are
      added just before the closing ``)``, indented like the block's
      existing content.  A single-line block is expanded to the
      multi-line form first (a line break cannot be inserted before
      its ``)`` without breaking the block).
    - Cursor anywhere else: the source becomes its own ``*draw(...)``
      block on its own line — newline-safe when *pos* is mid-line.

    Raises ValueError for an empty *source*.
    """
    inner, wrapped = _split_source(source)
    if not inner:
        # e.g. an empty *draw() — insert the wrapper as-is.
        inner = []
    text = text if isinstance(text, str) else str(text or '')
    try:
        pos = int(pos)
    except (TypeError, ValueError):
        pos = 0
    pos = max(0, min(pos, len(text)))

    span = find_enclosing_draw_block(text, pos)
    if span is None:
        # Outside: own block, on its own line.
        prefix_nl = pos > 0 and text[pos - 1] != '\n'
        suffix_nl = pos < len(text) and text[pos] != '\n'
        insert = ('\n' if prefix_nl else '') + wrapped
        if suffix_nl:
            insert += '\n'
        # Caret lands right after the block's closing ')'.
        offset = len(insert) - (1 if suffix_nl else 0)
        return TextInsert(pos, pos, insert, offset)

    start, end = span
    if '\n' not in text[start:end]:
        # Single-line block: expand to multi-line, then append.
        existing = text[start + 6:end - 1].strip()
        lines = ['*draw(']
        if existing:
            lines.append(DEFAULT_INDENT + existing)
        lines.extend(DEFAULT_INDENT + line for line in inner)
        lines.append(')')
        new_block = '\n'.join(lines)
        # Caret after the last inserted command line.
        offset = len(new_block) - len(')') - 1
        return TextInsert(start, end, new_block, offset)

    # Multi-line block: insert just before the closing ')' line.
    indent = _inner_indent(text, start, end)
    close_line = text.rfind('\n', start, end)
    insert_at = close_line + 1 if close_line != -1 else end
    insert = ''.join(indent + line + '\n' for line in inner)
    return TextInsert(insert_at, insert_at, insert, max(0, len(insert) - 1))
