"""Centralized Symbol Bar metadata for Easy Math Lang.

Qt-free: pure data + source generation + validation + insertion math,
so it can be unit-tested without a display and reused by the editor,
the symbol bar, and (indirectly) the LSP/completion docs.

Architecture (incremental, palette stays curated)::

    Compiler metadata  (symbols / diagnostics / geometry tables,
                        ``math_call_specs`` arities, LSP ``*_DOCS`` signatures)
      │  syntax / signature / docs  (source of truth, never duplicated here)
      ↓
    Symbol Registry    (this module: curated selection + category,
                        display, dialog fields, insertion behavior)
      │  category / display / fields / command / wrap / cursor
      ↓
    Symbol Bar         (presentational only)

The palette never auto-adds every compiler command; editors curate
which commands deserve an entry.  Command names, glyphs, signatures
and descriptions are *derived* from the compiler/LSP tables above so a
glyph or signature change flows through instead of drifting.
Geometry actions always generate a full ``*draw(...)`` wrapper because
bare ``*line(...)`` outside ``*draw`` is not valid geometry.

Geometry note: bare ``*line(...)`` / ``*angle(...)`` outside ``*draw(...)``
is NOT valid geometry (compiler warns and treats it as plain text, and
``*triangle`` would even be rewritten to ``△`` by symbol shortcuts).
Every geometry action therefore generates a full ``*draw(...)`` wrapper.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger('easy-math-editor.symbols')

try:  # Reuse compiler tables; fall back to empty on odd sys.path setups.
    from compiler.diagnostics import KNOWN_COMMANDS
    from compiler.symbols import SYMBOL_REPLACEMENTS, WORD_REPLACEMENTS
    from geometry.commands import KNOWN_GEOMETRY_COMMANDS as _GEO_KNOWN
except Exception:  # pragma: no cover - defensive, editor still loads
    KNOWN_COMMANDS = set()
    SYMBOL_REPLACEMENTS = []
    WORD_REPLACEMENTS = []
    _GEO_KNOWN = set()

try:
    from lsp.builtins import GEOMETRY_DOCS, KEYWORD_DOCS, MATH_DOCS
except Exception:  # pragma: no cover - defensive
    MATH_DOCS = {}
    KEYWORD_DOCS = {}
    GEOMETRY_DOCS = {}

POINT_NAME_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]*$')
IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

CATEGORIES = ('Basic', 'Math', 'Variables', 'Geometry', 'Text')


@dataclass
class SymbolField:
    """One dialog input."""

    key: str
    label: str
    placeholder: str = ''
    default: str = ''
    required: bool = True
    pattern: str | None = None
    help: str = ''

    def validate(self, value: str) -> str | None:
        """Return an error message, or None when *value* is acceptable."""
        text = (value or '').strip()
        if not text:
            if self.required:
                return f'{self.label} is required.'
            return None
        if self.pattern:
            if not re.match(self.pattern, text):
                return f'{self.label} looks invalid: {value!r}.'
        return None


@dataclass
class Symbol:
    """One toolbar action.

    ``command`` is the compiler command name (``frac``, ``line``, ...)
    or None for non-command constructs (variables, headings, skeleton).
    ``wrap_draw`` wraps the generated ``*cmd(...)`` in ``*draw(...)``.
    ``cursor_offset`` is the caret offset inside the inserted text
    (None means "at the end").
    """

    name: str
    display: str
    syntax: str
    category: str
    description: str
    requires_dialog: bool
    insert_text: str | None = None
    fields: list[SymbolField] = field(default_factory=list)
    command: str | None = None
    wrap_draw: bool = False
    cursor_offset: int | None = None

    @property
    def tooltip(self) -> str:
        base = self.syntax if not self.description else f'{self.syntax} — {self.description}'
        hint = 'Opens dialog' if self.requires_dialog else 'Inserts directly'
        return f'{base}\n{self.category} • {hint}'


def _req(key, label, placeholder='', pattern=None, help=''):
    return SymbolField(key=key, label=label, placeholder=placeholder,
                       required=True, pattern=pattern, help=help)


def _opt(key, label, placeholder='', pattern=None, help=''):
    return SymbolField(key=key, label=label, placeholder=placeholder,
                       required=False, pattern=pattern, help=help)


# Lookup tables derived once from the compiler (single source of truth
# for glyphs; the curated lists below only choose *which* entries the
# palette exposes, never the glyph itself).
_WORD_GLYPH: dict[str, str] = dict(WORD_REPLACEMENTS)
_ASCII_GLYPH: dict[str, str] = dict(SYMBOL_REPLACEMENTS)


def _math_sig_desc(cmd: str) -> tuple[str, str]:
    sig, desc = MATH_DOCS.get(cmd, (f'*{cmd}(...)', ''))
    return sig, desc


def _geo_sig_desc(cmd: str) -> tuple[str, str]:
    sig, desc = GEOMETRY_DOCS.get(cmd, (f'*{cmd}(...)', ''))
    return sig, desc


# ----------------------------------------------------------------------
# Symbol table
# ----------------------------------------------------------------------

def _direct(name, display, insert, category, syntax, description,
            cursor_offset=None):
    return Symbol(name=name, display=display, syntax=syntax,
                  category=category, description=description,
                  requires_dialog=False, insert_text=insert, fields=[],
                  command=None, wrap_draw=False,
                  cursor_offset=cursor_offset)


def _dialog(name, display, syntax, category, description, fields,
            command=None, wrap_draw=False):
    return Symbol(name=name, display=display, syntax=syntax,
                  category=category, description=description,
                  requires_dialog=True, insert_text=None,
                  fields=list(fields), command=command,
                  wrap_draw=wrap_draw, cursor_offset=None)


def _direct_ascii(name, ascii_src, category, label):
    """Curated ASCII shortcut; glyph/display derived from the compiler."""
    glyph = _ASCII_GLYPH.get(ascii_src, ascii_src)
    return _direct(name, glyph, ascii_src, category, ascii_src,
                   f'{label} ({ascii_src} → {glyph})')


def _direct_word(name, word, category, label):
    """Curated *word shortcut; glyph/display derived from the compiler."""
    glyph = _WORD_GLYPH.get(word, word)
    insert = f'*{word}'
    return _direct(name, glyph, insert, category, insert,
                   f'{label} ({insert} → {glyph})')


def _math_dialog(name, display, cmd, fields):
    """Curated math command; syntax/docs derived from MATH_DOCS."""
    sig, desc = _math_sig_desc(cmd)
    return _dialog(name, display, sig, 'Math', desc or sig, fields,
                   command=cmd, wrap_draw=False)


def _geo_dialog(name, display, cmd, fields):
    """Curated geometry command; syntax/docs derived from GEOMETRY_DOCS."""
    sig, desc = _geo_sig_desc(cmd)
    return _dialog(name, display, sig, 'Geometry', desc or sig, fields,
                   command=cmd, wrap_draw=True)


def _build_symbols() -> list[Symbol]:
    symbols: list[Symbol] = [
        # -- Basic: curated ASCII + *word shortcuts; glyphs derived above --
        _direct_ascii('le', '<=', 'Basic', 'Less-or-equal'),
        _direct_ascii('ge', '>=', 'Basic', 'Greater-or-equal'),
        _direct_ascii('ne', '!=', 'Basic', 'Not equal'),
        _direct_ascii('approx', '~=', 'Basic', 'Approximately equal'),
        _direct_ascii('arrow-r', '->', 'Basic', 'Right arrow'),
        _direct_ascii('arrow-R', '=>', 'Basic', 'Implies'),
        _direct_ascii('arrow-lr', '<->', 'Basic', 'Left-right arrow'),
        _direct_ascii('pm', '+-', 'Basic', 'Plus-minus'),
        _direct_ascii('ellipsis', '...', 'Basic', 'Ellipsis'),
        _direct_word('times', 'times', 'Basic', 'Multiplication sign'),
        _direct_word('div', 'div', 'Basic', 'Division sign'),
        _direct_word('cdot', 'cdot', 'Basic', 'Centered dot'),
        _direct_word('pi-sym', 'pi', 'Basic', 'Pi'),
        _direct_word('infinity-sym', 'infinity', 'Basic', 'Infinity'),
        _direct_word('deg', 'deg', 'Basic', 'Degree'),
        _direct_word('alpha', 'alpha', 'Basic', 'Greek alpha'),
        _direct_word('beta', 'beta', 'Basic', 'Greek beta'),
        _direct_word('gamma', 'gamma', 'Basic', 'Greek gamma'),
        _direct_word('theta', 'theta', 'Basic', 'Greek theta'),
        _direct_word('lambda', 'lambda', 'Basic', 'Greek lambda'),
        _direct_word('omega', 'omega', 'Basic', 'Greek omega'),
        _direct_word('forall', 'forall', 'Basic', 'For all'),
        _direct_word('exists', 'exists', 'Basic', 'There exists'),
        _direct_word('isin', 'isin', 'Basic', 'Element of'),
        _direct_word('cup', 'cup', 'Basic', 'Union'),
        _direct_word('cap', 'cap', 'Basic', 'Intersection'),
        _direct_word('emptyset', 'emptyset', 'Basic', 'Empty set'),
        _direct_word('partial', 'partial', 'Basic', 'Partial'),

        # -- Math / calculation (dialogs; syntax/docs derived from MATH_DOCS) --
        _dialog('calc', 'calc()', 'calc(expression)', 'Math',
                KEYWORD_DOCS.get('calc', ('', 'Evaluate a math expression.'))[1],
                [_req('expression', 'Expression', '2 + 3 * 4')]),
        _math_dialog('frac', 'a/b', 'frac',
                [_req('numerator', 'Numerator', '2'),
                 _req('denominator', 'Denominator', '3')]),
        _math_dialog('sqrt', '√', 'sqrt',
                [_req('expression', 'Expression', '16')]),
        _math_dialog('pow', 'xⁿ', 'pow',
                [_req('base', 'Base', 'x'),
                 _req('exponent', 'Exponent', '2')]),
        _math_dialog('root', 'ⁿ√', 'root',
                [_req('index', 'Index', '3'),
                 _req('radicand', 'Radicand', '27')]),
        _math_dialog('sum', '∑', 'sum',
                [_req('lower', 'Lower', 'i = 1'),
                 _req('upper', 'Upper', 'n'),
                 _req('expression', 'Expression', 'i')]),
        _math_dialog('prod', '∏', 'prod',
                [_req('lower', 'Lower', 'i = 1'),
                 _req('upper', 'Upper', 'n'),
                 _req('expression', 'Expression', 'i')]),
        _math_dialog('lim', 'lim', 'lim',
                [_req('condition', 'Condition', 'x -> 0'),
                 _req('expression', 'Expression', 'sin(x) / x')]),
        _math_dialog('sin', 'sin', 'sin',
                [_req('expression', 'Expression', 'x')]),
        _math_dialog('cos', 'cos', 'cos',
                [_req('expression', 'Expression', 'x')]),
        _math_dialog('tan', 'tan', 'tan',
                [_req('expression', 'Expression', 'x')]),
        _math_dialog('log', 'log', 'log',
                [_req('expression', 'Expression', '10')]),
        _math_dialog('ln', 'ln', 'ln',
                [_req('expression', 'Expression', '2.718')]),
        _math_dialog('abs', '|x|', 'abs',
                [_req('expression', 'Expression', 'x - 5')]),
        _math_dialog('cbrt', '∛', 'cbrt',
                [_req('expression', 'Expression', '27')]),

        # -- Variables / definitions --
        _dialog('var-def', '<x> =', '<name> = value', 'Variables',
                'Define a variable. Referenced later as <name>.',
                [_req('name', 'Name', 'x', pattern=IDENT_RE.pattern,
                      help='Letters, digits, _ — must start with a letter or _.'),
                 _req('value', 'Value', '5')]),
        _dialog('define', '*define', KEYWORD_DOCS.get('define', ('*define(name = value)', ''))[0], 'Variables',
                KEYWORD_DOCS.get('define', ('', 'Define a reusable value.'))[1],
                [_req('name', 'Name', 'pi2', pattern=IDENT_RE.pattern),
                 _req('value', 'Value', '3.14')]),

        # -- Geometry (all wrapped in *draw for validity) --
        # Cursor lands just inside the closing paren so follow-up
        # commands stay inside the draw block (no snippet engine).
        _direct('draw-skeleton', '*draw', '*draw(\n*point(A = 0, 0)\n*point(B = 3, 0)\n*line(A ; B)\n)',
                'Geometry', '*draw(...)',
                'Draw skeleton — a minimal valid draw block.',
                cursor_offset=len('*draw(\n*point(A = 0, 0)\n*point(B = 3, 0)\n*line(A ; B)\n)') - 1),
        _geo_dialog('geo-point', 'Point', 'point',
                [_req('name', 'Name', 'A', pattern=POINT_NAME_RE.pattern),
                 _opt('x', 'X (optional)', '0'),
                 _opt('y', 'Y (optional)', '0')]),
        _geo_dialog('geo-line', 'Line', 'line',
                [_req('a', 'Point A', 'A', pattern=POINT_NAME_RE.pattern),
                 _req('b', 'Point B', 'B', pattern=POINT_NAME_RE.pattern)]),
        _geo_dialog('geo-ray', 'Ray', 'ray',
                [_req('a', 'Start A', 'A', pattern=POINT_NAME_RE.pattern),
                 _req('b', 'Through B', 'B', pattern=POINT_NAME_RE.pattern)]),
        _geo_dialog('geo-circle', 'Circle', 'circle',
                [_req('center', 'Center', 'O', pattern=POINT_NAME_RE.pattern),
                 _req('radius', 'Radius or point', '3')]),
        _geo_dialog('geo-triangle', 'Triangle', 'triangle',
                [_req('a', 'Point A', 'A', pattern=POINT_NAME_RE.pattern),
                 _req('b', 'Point B', 'B', pattern=POINT_NAME_RE.pattern),
                 _req('c', 'Point C', 'C', pattern=POINT_NAME_RE.pattern)]),
        _geo_dialog('geo-right-angle', 'Right∠', 'right-angle',
                [_req('p1', 'Point 1', 'B', pattern=POINT_NAME_RE.pattern),
                 _req('vertex', 'Vertex (middle)', 'A', pattern=POINT_NAME_RE.pattern),
                 _req('p2', 'Point 2', 'C', pattern=POINT_NAME_RE.pattern)]),
        _geo_dialog('geo-angle', 'Angle', 'angle',
                [_req('a', 'Point A', 'A', pattern=POINT_NAME_RE.pattern),
                 _req('vertex', 'Vertex B', 'B', pattern=POINT_NAME_RE.pattern),
                 _req('c', 'Point C', 'C', pattern=POINT_NAME_RE.pattern),
                 _opt('label', 'Label (optional)', '60°')]),
        _geo_dialog('geo-arc', 'Arc', 'arc',
                [_req('center', 'Center', 'O', pattern=POINT_NAME_RE.pattern),
                 _req('start', 'Start', 'A', pattern=POINT_NAME_RE.pattern),
                 _req('end', 'End', 'B', pattern=POINT_NAME_RE.pattern)]),
        _geo_dialog('geo-label', 'Label', 'label',
                [_req('point', 'Point', 'P', pattern=POINT_NAME_RE.pattern),
                 _req('text', 'Text', 'hello world')]),
        _geo_dialog('geo-length', 'Length', 'length',
                [_req('a', 'Point A', 'A', pattern=POINT_NAME_RE.pattern),
                 _req('b', 'Point B', 'B', pattern=POINT_NAME_RE.pattern),
                 _opt('value', 'Shown value (optional)', '5')]),
        _geo_dialog('geo-angle-value', 'Angle°', 'angle-value',
                [_req('a', 'Point A', 'A', pattern=POINT_NAME_RE.pattern),
                 _req('vertex', 'Vertex B', 'B', pattern=POINT_NAME_RE.pattern),
                 _req('c', 'Point C', 'C', pattern=POINT_NAME_RE.pattern),
                 _opt('value', 'Shown value (optional)', '90')]),
        _geo_dialog('geo-distance', 'Dist', 'distance',
                [_req('a', 'Point A', 'A', pattern=POINT_NAME_RE.pattern),
                 _req('b', 'Point B', 'B', pattern=POINT_NAME_RE.pattern),
                 _req('d', 'Distance', '5')]),
        _geo_dialog('geo-midpoint', 'Mid', 'midpoint',
                [_req('a', 'Point A', 'A', pattern=POINT_NAME_RE.pattern),
                 _req('b', 'Point B', 'B', pattern=POINT_NAME_RE.pattern),
                 _req('c', 'Midpoint C', 'C', pattern=POINT_NAME_RE.pattern)]),
        _geo_dialog('geo-parallel', 'Parallel', 'parallel',
                [_req('a', 'Point A', 'A', pattern=POINT_NAME_RE.pattern),
                 _req('b', 'Point B', 'B', pattern=POINT_NAME_RE.pattern),
                 _req('c', 'Point C', 'C', pattern=POINT_NAME_RE.pattern),
                 _req('d', 'Point D', 'D', pattern=POINT_NAME_RE.pattern)]),
        _geo_dialog('geo-perp', 'Perp', 'perp',
                [_req('a', 'Point A', 'A', pattern=POINT_NAME_RE.pattern),
                 _req('b', 'Point B', 'B', pattern=POINT_NAME_RE.pattern),
                 _req('c', 'Point C', 'C', pattern=POINT_NAME_RE.pattern),
                 _opt('d', 'Point D (optional, 4-arg form)', 'D',
                      pattern=POINT_NAME_RE.pattern)]),
        _geo_dialog('geo-on-line', 'OnLine', 'on-line',
                [_req('a', 'Point A', 'A', pattern=POINT_NAME_RE.pattern),
                 _req('b', 'Point B', 'B', pattern=POINT_NAME_RE.pattern),
                 _req('c', 'Point C', 'C', pattern=POINT_NAME_RE.pattern)]),
        _geo_dialog('geo-on-circle', 'OnCircle', 'on-circle',
                [_req('center', 'Center O', 'O', pattern=POINT_NAME_RE.pattern),
                 _req('radius', 'Radius', '3'),
                 _req('point', 'Point A', 'A', pattern=POINT_NAME_RE.pattern)]),
        _geo_dialog('geo-equal-length', '=Len', 'equal-length',
                [_req('a', 'Point A', 'A', pattern=POINT_NAME_RE.pattern),
                 _req('b', 'Point B', 'B', pattern=POINT_NAME_RE.pattern),
                 _req('c', 'Point C', 'C', pattern=POINT_NAME_RE.pattern),
                 _req('d', 'Point D', 'D', pattern=POINT_NAME_RE.pattern)]),
        _geo_dialog('geo-intersection', 'Xsect', 'intersection',
                [_req('name', 'New point', 'X', pattern=POINT_NAME_RE.pattern),
                 _req('line1', 'Line 1', 'line(A ; B)'),
                 _req('line2', 'Line 2', 'line(C ; D)')]),

        # -- Text / formatting --
        _dialog('inline-math', '\\…\\', '\\ expression \\', 'Text',
                'Inline math (\\ ... \\)).',
                [_req('expression', 'Expression', 'x^2 + y^2')]),
        _dialog('heading', '# H', '# Title', 'Text',
                'Heading block.',
                [_req('title', 'Title', 'My heading')]),
        _dialog('list-item', '- item', '- item', 'Text',
                'Bullet list item.',
                [_req('text', 'Item text', 'First item')]),
        _dialog('raw-p', '*p', '*p(expression)', 'Text',
                KEYWORD_DOCS.get('p', ('*p(expression)', ''))[1] or 'Raw passthrough.',
                [_req('content', 'Content', 'raw typst')]),
    ]
    return symbols


SYMBOLS: list[Symbol] = _build_symbols()
_BY_NAME: dict[str, Symbol] = {s.name: s for s in SYMBOLS}


def list_symbols() -> list[Symbol]:
    """All registered symbols in toolbar order."""
    return list(SYMBOLS)


def list_categories() -> list[str]:
    """Category names in a stable UI order (existing ones only)."""
    present = [c for c in CATEGORIES if any(s.category == c for s in SYMBOLS)]
    extra = sorted({s.category for s in SYMBOLS} - set(present))
    return present + extra


def symbols_in_category(category: str) -> list[Symbol]:
    if category in ('All', '', None):
        return list(SYMBOLS)
    return [s for s in SYMBOLS if s.category == category]


def get_symbol(name: str) -> Symbol:
    try:
        return _BY_NAME[name]
    except KeyError:
        raise KeyError(f'unknown symbol {name!r}') from None


def validate_fields(symbol: Symbol, values: dict) -> list[str]:
    """Validate *values* for *symbol*; return a list of error messages."""
    errors: list[str] = []
    for f in symbol.fields:
        err = f.validate((values or {}).get(f.key, ''))
        if err:
            errors.append(err)
    # Cross-field rule: point coordinates come as a pair.
    if symbol.name == 'geo-point':
        x = (values or {}).get('x', '').strip()
        y = (values or {}).get('y', '').strip()
        if bool(x) != bool(y):
            errors.append('X and Y must either both be set or both be empty.')
    return errors


def _v(values: dict, key: str) -> str:
    return (values or {}).get(key, '').strip()


def _generic_args(sym: Symbol, vals: dict) -> list[str]:
    """Field values in order, skipping empty optionals (already validated)."""
    args: list[str] = []
    for f in sym.fields:
        v = _v(vals, f.key)
        if v:
            args.append(v)
        elif f.required:
            # validate_fields guarantees this cannot happen, but keep the
            # generator total instead of emitting an empty argument.
            args.append(v)
    return args


def _generic_build(sym: Symbol, vals: dict) -> str:
    """Build ``*cmd(a ; b)`` (optionally ``*draw``-wrapped) from metadata.

    The command name and field order live on the Symbol; the canonical
    ``;`` separator matches the compiler's friendly splitter (commas
    also work, but ``;`` keeps ``100,000``-style numbers intact).
    """
    assert sym.command
    inner = f"*{sym.command}({' ; '.join(_generic_args(sym, vals))})"
    if sym.wrap_draw:
        return f"*draw({inner})"
    return inner


# Palette ids with bespoke syntax (not a plain ``*cmd(args)`` shape).
_CUSTOM_SYMBOLS = frozenset({
    'calc', 'var-def', 'define', 'inline-math', 'heading', 'list-item',
    'raw-p', 'geo-point', 'geo-length', 'geo-angle-value',
})


def cursor_offset_for_insert(symbol: Symbol | str, text: str) -> int:
    """Caret offset inside *text* (defaults to the end).

    Only the draw skeleton sets an explicit offset so follow-up typing
    stays inside the ``*draw(...)`` block; dialog results already carry
    their arguments, so ending at the end is the useful position.
    """
    sym = get_symbol(symbol) if isinstance(symbol, str) else symbol
    if sym.cursor_offset is None:
        return len(text or '')
    try:
        off = int(sym.cursor_offset)
    except (TypeError, ValueError):
        return len(text or '')
    return max(0, min(off, len(text or '')))


def build_source(symbol: Symbol | str, values: dict | None = None) -> str:
    """Generate Easy Math Lang source for *symbol*.

    Raises ValueError when required fields are missing/invalid.
    Direct (dialog-free) symbols ignore *values* and return their
    ``insert_text`` verbatim.
    """
    sym = get_symbol(symbol) if isinstance(symbol, str) else symbol
    vals = dict(values or {})
    if not sym.requires_dialog:
        if sym.insert_text is None:
            raise ValueError(f'symbol {sym.name!r} has no insert text')
        return sym.insert_text
    errors = validate_fields(sym, vals)
    if errors:
        raise ValueError('; '.join(errors))
    n = sym.name
    # Bespoke shapes (kept explicit; everything else flows through the
    # generic ``*command`` builder above so compiler syntax is not
    # repeated per command).
    if n == 'calc':
        return f"calc({_v(vals, 'expression')})"
    if n == 'var-def':
        return f"<{_v(vals, 'name')}> = {_v(vals, 'value')}"
    if n == 'define':
        return f"*define({_v(vals, 'name')} = {_v(vals, 'value')})"
    if n == 'inline-math':
        return f"\\ {_v(vals, 'expression')} \\"
    if n == 'heading':
        return f"# {_v(vals, 'title')}"
    if n == 'list-item':
        return f"- {_v(vals, 'text')}"
    if n == 'raw-p':
        return f"*p({_v(vals, 'content')})"
    # -- geometry: always wrapped in *draw(...) --
    if n == 'geo-point':
        name = _v(vals, 'name')
        x = _v(vals, 'x')
        y = _v(vals, 'y')
        if x and y:
            return f"*draw(*point({name} = {x}, {y}))"
        return f"*draw(*point({name}))"
    if n == 'geo-length':
        base = f"*length({_v(vals, 'a')} ; {_v(vals, 'b')})"
        value = _v(vals, 'value')
        if value:
            return f"*draw({base} = {value})"
        return f"*draw({base})"
    if n == 'geo-angle-value':
        base = f"*angle-value({_v(vals, 'a')} ; {_v(vals, 'vertex')} ; {_v(vals, 'c')})"
        value = _v(vals, 'value')
        if value:
            return f"*draw({base} = {value})"
        return f"*draw({base})"
    if sym.command and n not in _CUSTOM_SYMBOLS:
        return _generic_build(sym, vals)
    raise ValueError(f'no generator for symbol {sym.name!r}')


def apply_insert(original: str, start: int, end: int, insert: str,
                 cursor_offset: int | None = None) -> tuple[str, int]:
    """Pure insertion math (Qt-free, unit-testable).

    Replace ``original[start:end]`` with *insert* (like QTextCursor
    does when a selection exists). Returns ``(new_text, new_cursor)``
    where ``new_cursor`` sits at ``start + cursor_offset`` (or right
    after the inserted text when *cursor_offset* is None).
    Indices are clamped; reversed ranges are normalized.
    """
    text = original or ''
    insert = insert or ''
    n = len(text)
    try:
        s = int(start)
    except (TypeError, ValueError):
        s = 0
    try:
        e = int(end)
    except (TypeError, ValueError):
        e = s
    s = max(0, min(s, n))
    e = max(0, min(e, n))
    if e < s:
        s, e = e, s
    new_text = text[:s] + insert + text[e:]
    if cursor_offset is None:
        return new_text, s + len(insert)
    try:
        off = int(cursor_offset)
    except (TypeError, ValueError):
        return new_text, s + len(insert)
    return new_text, s + max(0, min(off, len(insert)))


def _math_min_args() -> dict[str, int]:
    """Minimum arities from the compiler's own ``math_call_specs``.

    Reuses the compiler table (needs no context: only the name/count
    pair is read, formatters are never invoked). Empty on fallback
    setups so the editor still loads.
    """
    try:
        from compiler.math_commands import math_call_specs
        return {name: int(min_args) for name, min_args, _fmt in math_call_specs(None)}
    except Exception:
        return {}


def _cross_check() -> None:
    """Warn once when the palette drifts from compiler/LSP tables."""
    try:
        words = {w for w, _g in WORD_REPLACEMENTS}
        ascii_src = {old for old, _new in SYMBOL_REPLACEMENTS}
        for s in SYMBOLS:
            if s.requires_dialog:
                continue
            ins = s.insert_text or ''
            if ins.startswith('*'):
                word = ins[1:]
                if words and word not in words:
                    # Not every direct insert is a *word (e.g. multiline
                    # draw skeleton); only warn for single-token Inserts.
                    if re.fullmatch(r'\*[A-Za-z]+', ins):
                        logger.warning('symbol %r inserts %r not in WORD_REPLACEMENTS',
                                       s.name, ins)
            else:
                if ascii_src and ins not in ascii_src and '\n' not in ins:
                    logger.warning('symbol %r inserts %r not in SYMBOL_REPLACEMENTS',
                                   s.name, ins)
        # Curated commands must exist in the compiler tables; generic
        # math entries additionally match the compiler's min-arity so a
        # signature change (e.g. a new required arg) is noticed here
        # instead of silently generating invalid source.
        min_args = _math_min_args()
        for s in SYMBOLS:
            if not s.requires_dialog or not s.command:
                continue
            cmd = s.command
            if s.wrap_draw:
                if _GEO_KNOWN and cmd not in _GEO_KNOWN:
                    logger.warning('symbol %r command %r not in KNOWN_GEOMETRY_COMMANDS',
                                   s.name, cmd)
                if cmd in GEOMETRY_DOCS and GEOMETRY_DOCS[cmd][0] != s.syntax:
                    logger.warning('symbol %r syntax drifted from GEOMETRY_DOCS[%r]',
                                   s.name, cmd)
            else:
                if KNOWN_COMMANDS and cmd not in KNOWN_COMMANDS:
                    logger.warning('symbol %r command %r not in KNOWN_COMMANDS',
                                   s.name, cmd)
                if cmd in MATH_DOCS and MATH_DOCS[cmd][0] != s.syntax:
                    logger.warning('symbol %r syntax drifted from MATH_DOCS[%r]',
                                   s.name, cmd)
                if cmd in min_args and s.name not in _CUSTOM_SYMBOLS:
                    required = sum(1 for f in s.fields if f.required)
                    if required < min_args[cmd]:
                        logger.warning(
                            'symbol %r has %d required field(s) but compiler needs %d for *%s',
                            s.name, required, min_args[cmd], cmd)
        # Non-command dialogs (calc/define/blocks) keep working even if
        # the command tables change; only the define/raw-p keywords can
        # drift, so check those two explicitly.
        for s in SYMBOLS:
            if not s.requires_dialog or s.command:
                continue
            if s.name == 'define' and KNOWN_COMMANDS and 'define' not in KNOWN_COMMANDS:
                logger.warning('symbol %r keyword missing from KNOWN_COMMANDS', s.name)
            if s.name == 'raw-p' and KNOWN_COMMANDS and 'p' not in KNOWN_COMMANDS:
                logger.warning('symbol %r keyword missing from KNOWN_COMMANDS', s.name)
    except Exception:  # never break the editor on a metadata check
        pass


_cross_check()
