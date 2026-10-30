"""Tests for the Qt-free *draw gallery catalog (editor.draw_catalog).

Two hard rules are exercised here:

1. One parser: every example is validated by calling
   ``geometry.parse_draw_block`` (offline, no Typst, no network) —
   the catalog never parses geometry itself.
2. The catalog stays in lock-step with the compiler's command table
   and the LSP's GEOMETRY_DOCS, like the registry's ``_cross_check``.
"""

import hashlib
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from editor.draw_catalog import (  # noqa: E402
    CATALOG,
    GROUPS,
    CatalogEntry,
    build_insert_text,
    catalog_entries,
    draw_block_body,
    find_enclosing_draw_block,
    get_entry,
)
from geometry.commands import KNOWN_GEOMETRY_COMMANDS  # noqa: E402

# equal-angle is [planned] in GEOMETRY_DOCS: codegen deliberately raises
# "*equal-angle is not yet implemented" (the palette excludes it too —
# see test_symbol_palette.test_palette_stays_curated_not_exhaustive).
# Its example is otherwise validated like every other entry, and the test
# below pins the failure to exactly that documented message.
PLANNED_COMMANDS = {'equal-angle'}


# ----------------------------------------------------------------------
# Catalog coverage / metadata
# ----------------------------------------------------------------------

def test_catalog_covers_known_geometry_commands_exactly():
    commands = {e.command for e in CATALOG}
    assert commands == set(KNOWN_GEOMETRY_COMMANDS)
    assert len(CATALOG) == len(KNOWN_GEOMETRY_COMMANDS)


def test_catalog_ids_unique_and_stable():
    ids = [e.id for e in CATALOG]
    assert len(set(ids)) == len(ids)
    # id doubles as the thumbnail file name: keep it filename-safe.
    assert all(e.id and ' ' not in e.id and '/' not in e.id for e in CATALOG)
    # get_entry resolves by id and by command.
    assert get_entry('perp') is get_entry('perp')
    assert get_entry('perp').command == 'perp'
    with pytest.raises(KeyError):
        get_entry('nope')


def test_catalog_groups_are_known_and_ordered():
    assert set(GROUPS) == {e.group for e in CATALOG}
    assert all(e.group in GROUPS for e in CATALOG)
    # Grouping is sensible: no draw-only marker under Constraints, etc.
    by_group = {g: [e.command for e in catalog_entries(g)] for g in GROUPS}
    assert 'perp' in by_group['Constraints']
    assert 'triangle' in by_group['Shapes']
    assert 'angle-value' in by_group['Measure & Label']
    assert 'right-angle' in by_group['Angles']
    # catalog_entries(None/'All') returns everything.
    assert len(catalog_entries(None)) == len(CATALOG)
    assert len(catalog_entries('All')) == len(CATALOG)


def test_catalog_reuses_geometry_docs_text():
    """Syntax + description come from GEOMETRY_DOCS — never duplicated."""
    from lsp.builtins import GEOMETRY_DOCS
    assert set(GEOMETRY_DOCS) == set(KNOWN_GEOMETRY_COMMANDS)
    for entry in CATALOG:
        syntax, description = GEOMETRY_DOCS[entry.command]
        assert entry.syntax == syntax, entry.command
        assert entry.description == description, entry.command
        assert entry.syntax and entry.description


def test_catalog_symbol_mapping_matches_registry():
    from editor.symbol_registry import get_symbol, list_symbols
    geo_dialogs = {s.command: s.name for s in list_symbols()
                   if s.requires_dialog and s.wrap_draw and s.command}
    for entry in CATALOG:
        if entry.symbol is None:
            assert entry.command not in geo_dialogs, entry.command
            continue
        assert geo_dialogs.get(entry.command) == entry.symbol
        sym = get_symbol(entry.symbol)
        assert sym.wrap_draw and sym.command == entry.command
    # Commands with no parameter dialog yet.
    assert {e.command for e in CATALOG if e.symbol is None} == \
        {'equal-angle'}


def test_every_example_shows_its_own_command():
    for entry in CATALOG:
        assert isinstance(entry.example, str)
        assert entry.example.startswith('*draw(')
        assert entry.example.endswith(')')
        assert f'*{entry.command}(' in entry.example, entry.command


# ----------------------------------------------------------------------
# Examples parse with the ONE geometry parser (offline)
# ----------------------------------------------------------------------

def test_examples_parse_cleanly_with_geometry_parser(capsys):
    from geometry.parsing import parse_draw_block

    for entry in CATALOG:
        # Mirror the pipeline: strip the *draw(...) wrapper, parse the body.
        body = draw_block_body(entry.example)
        assert body != entry.example
        out = parse_draw_block(body)
        captured = capsys.readouterr()
        assert captured.out == '', entry.command
        assert '// [Error]' not in out, entry.command
        if entry.command in PLANNED_COMMANDS:
            # The documented failure is the only one, and it is the
            # compiler rejecting the not-yet-implemented command — the
            # example's syntax/geometry itself is fine.
            lines = [ln for ln in captured.err.splitlines() if ln.strip()]
            assert len(lines) == 1, (entry.command, captured.err)
            assert 'not yet implemented' in lines[0]
            assert '[GeometryError] *equal-angle' in lines[0]
            assert '// [GeometryError] *equal-angle:' in out
        else:
            assert captured.err == '', (entry.command, captured.err)
            assert '[GeometryError]' not in out, entry.command
            assert '[GeometryWarning]' not in out, entry.command
        # The generated Typst carries the CeTZ import (the preview
        # rendering script relies on this).
        assert '#import "@preview/cetz:0.4.2"' in out, entry.command


def test_draw_block_body_matches_pipeline_extraction():
    single = '*draw(*triangle(A ; B ; C))'
    multi = '*draw(\n    *point(A = 0, 0)\n    *line(A ; B)\n)'
    assert draw_block_body(single) == '*triangle(A ; B ; C)'
    assert draw_block_body(multi) == '\n    *point(A = 0, 0)\n    *line(A ; B)\n'
    # Non-block text passes through (already an unwrapped body).
    assert draw_block_body('*point(A = 0, 0)') == '*point(A = 0, 0)'


# ----------------------------------------------------------------------
# find_enclosing_draw_block — table-driven
# ----------------------------------------------------------------------

# Spans below are computed from the fixtures (never hand-counted):
_BLANK_MULTI = '*draw(\n    *line(A ; B)\n)'            # span (0, 26)
_MULTI_TAIL = _BLANK_MULTI + ' tail'                    # text after block
_BEFORE = 'before\n*draw(\n    *line(A ; B)\n)'         # block starts at 7
_SINGLE = '*draw(*triangle(A ; B ; C))'
_SINGLE_TAIL = _SINGLE + ' tail'
_NESTED = '*draw(*intersection(P ; line(A ; B) ; line(C ; D)))'
_NESTED_TAIL = _NESTED + ' tail'
_OPEN_COMMENT = '*draw( // open\n    *line(A ; B)\n) // done'
_SEG_COMMENT = '*draw(\n    *line(A ; B) // seg\n)'
_HIDDEN = '// *draw(\n    *line(A ; B)\n)'
_FENCE1 = '```\n*draw(\n    *line(A ; B)\n)\n```'
_FENCE2 = 'before\n```\n*draw(*point(A = 0, 0))\n```'

_MULTILINE_SPAN = (_BLANK_MULTI.index('*draw('),
                   _BLANK_MULTI.index('\n)') + 2)
_MULTI = (
    'intro text\n'
    '*draw(\n'
    '    *point(A = 0, 0)\n'
    '    *intersection(P ; line(A ; B) ; line(C ; D))\n'
    ')\n'
    'after text'
)
_MULTI_SPAN = (_MULTI.index('*draw('), _MULTI.index('\n)\n') + 2)


@pytest.mark.parametrize('text,pos,expected', [
    # --- multi-line form ---
    (_BLANK_MULTI, 0, _MULTILINE_SPAN),
    (_BLANK_MULTI, 8, _MULTILINE_SPAN),        # content line
    (_BLANK_MULTI, 25, _MULTILINE_SPAN),       # the ')'
    (_BLANK_MULTI, 26, _MULTILINE_SPAN),       # just past ')'
    (_MULTI_TAIL, 28, None),                   # after the block
    (_BEFORE, 3, None),                        # before the block
    # Content before/after the block is not inside it.
    (_MULTI, 3, None),                         # 'intro text'
    (_MULTI, _MULTI.index('after text'), None),
    (_MULTI, _MULTI_SPAN[0] + 3, _MULTI_SPAN),
    (_MULTI, _MULTI.index('intersection'), _MULTI_SPAN),
    # --- single-line form ---
    (_SINGLE, 6, (0, len(_SINGLE))),
    (_SINGLE, 20, (0, len(_SINGLE))),          # inside nested args
    (_SINGLE, len(_SINGLE), (0, len(_SINGLE))),  # just past ')'
    (_SINGLE_TAIL, len(_SINGLE) + 1, None),    # after the block
    # Nested parens like line(A ; B) must not confuse the span.
    (_NESTED, 30, (0, len(_NESTED))),
    (_NESTED, len(_NESTED), (0, len(_NESTED))),
    (_NESTED_TAIL, len(_NESTED) + 1, None),
    # --- comments ---
    # Opener may carry a trailing // comment (the pipeline strips it).
    (_OPEN_COMMENT, 8,
     (0, _OPEN_COMMENT.index('\n)') + 2)),
    (_OPEN_COMMENT, _OPEN_COMMENT.index('*line'),
     (0, _OPEN_COMMENT.index('\n)') + 2)),
    (_SEG_COMMENT, 12, (0, _SEG_COMMENT.index('\n)') + 2)),
    # Inside the trailing comment after the closer ')' is outside.
    (_OPEN_COMMENT, _OPEN_COMMENT.index('// done'), None),
    # A *draw( hidden behind // is not a block opener.
    (_HIDDEN, 4, None),
    # --- fenced code samples are not blocks ---
    (_FENCE1, 8, None),
    (_FENCE2, 12, None),
    # --- no block at all ---
    ('hello', 2, None),
    ('', 0, None),
    (')\n*draw(', 0, None),
])
def test_find_enclosing_draw_block_table(text, pos, expected):
    assert find_enclosing_draw_block(text, pos) == expected


def test_find_enclosing_draw_block_tolerates_bad_pos():
    text = '*draw(\n    *line(A ; B)\n)'
    assert find_enclosing_draw_block(text, None) == (0, len(text))
    assert find_enclosing_draw_block(text, 10 ** 9) == (0, len(text))
    assert find_enclosing_draw_block(text, -5) == (0, len(text))


# ----------------------------------------------------------------------
# build_insert_text — table-driven
# ----------------------------------------------------------------------

def test_insert_inside_multi_line_block():
    text = '*draw(\n    *triangle(A ; B ; C)\n)'
    edit = build_insert_text('*perp(A ; B ; A ; C)', text, 10)
    assert (edit.start, edit.end) == (len(text) - 1, len(text) - 1)
    result = text[:edit.start] + edit.insert + text[edit.end:]
    assert result == (
        '*draw(\n'
        '    *triangle(A ; B ; C)\n'
        '    *perp(A ; B ; A ; C)\n'
        ')'
    )
    # Caret lands right after the inserted command line.
    assert result[edit.cursor - 1] == ')'
    assert result[edit.cursor] == '\n'
    # Inserted line matches the block's indentation.
    assert edit.insert.startswith('    *perp')


def test_insert_inside_block_matches_existing_indentation():
    text = '*draw(\n  *line(A ; B)\n)'
    edit = build_insert_text('*point(C)', text, 12)
    assert edit.insert == '  *point(C)\n'


def test_insert_inside_block_with_trailing_comment_on_closer():
    text = '*draw(\n    *line(A ; B)\n) // done'
    edit = build_insert_text('*point(C)', text, 12)
    result = text[:edit.start] + edit.insert + text[edit.end:]
    assert result == '*draw(\n    *line(A ; B)\n    *point(C)\n) // done'


def test_insert_inside_block_with_content_comments():
    text = '*draw(\n    *line(A ; B) // the segment\n)'
    edit = build_insert_text('*point(C)', text, 12)
    result = text[:edit.start] + edit.insert + text[edit.end:]
    assert '    *point(C)\n)' in result
    assert '// the segment' in result  # untouched


def test_insert_inside_single_line_block_converts_to_multiline():
    # A single-line *draw(...) must be the whole line to count as a
    # block (the pipeline strips and matches the full line) — so the
    # surrounding text goes on its own lines.
    text = 'before\n*draw(*triangle(A ; B ; C))\nafter'
    pos = text.index('*triangle') + 5
    edit = build_insert_text('*perp(A ; B ; A ; C)', text, pos)
    result = text[:edit.start] + edit.insert + text[edit.end:]
    assert result == (
        'before\n'
        '*draw(\n'
        '    *triangle(A ; B ; C)\n'
        '    *perp(A ; B ; A ; C)\n'
        ')\n'
        'after'
    )
    # The surrounding text keeps its offsets sane: caret is inside the block.
    assert result[edit.cursor] == '\n'
    assert result[edit.cursor - 1] == ')'


def test_insert_inside_single_line_block_with_nested_parens():
    text = '*draw(*intersection(P ; line(A ; B) ; line(C ; D)))'
    edit = build_insert_text('*point(Z)', text, 10)
    result = text[:edit.start] + edit.insert + text[edit.end:]
    assert result == (
        '*draw(\n'
        '    *intersection(P ; line(A ; B) ; line(C ; D))\n'
        '    *point(Z)\n'
        ')'
    )


def test_insert_outside_block_on_empty_document():
    # A single-line source stays single-line (valid on its own line).
    edit = build_insert_text('*draw(*line(A ; B))', '', 0)
    assert edit.start == edit.end == 0
    assert edit.insert == '*draw(*line(A ; B))'
    assert edit.cursor == len(edit.insert)  # caret after the closing ')'


def test_insert_outside_block_wraps_bare_command_line():
    # Cursor sits at the end of the 'x = 5' line content, so a leading
    # newline keeps the new block on its own line.
    edit = build_insert_text('*perp(A ; B ; C)', 'x = 5\n', 5)
    assert edit.start == edit.end == 5
    assert edit.insert == '\n*draw(\n    *perp(A ; B ; C)\n)'


def test_insert_outside_block_is_newline_safe_mid_line():
    text = 'hello world'
    pos = 5  # cursor between 'hello' and ' world'
    edit = build_insert_text('*draw(*point(A))', text, pos)
    assert edit.start == edit.end == pos
    result = text[:edit.start] + edit.insert + text[edit.end:]
    assert result == 'hello\n*draw(*point(A))\n world'
    # Caret sits right after the block, before the trailing newline.
    assert result[edit.cursor] == '\n'
    assert result[edit.cursor - 1] == ')'


def test_insert_outside_block_at_line_start_needs_no_prefix_newline():
    text = '*define(a = 1)\nnext line'
    pos = text.index('\n') + 1
    edit = build_insert_text('*draw(*point(A))', text, pos)
    assert not edit.insert.startswith('\n')
    result = text[:edit.start] + edit.insert + text[edit.end:]
    assert result.split('\n')[1].startswith('*draw(')


def test_insert_example_block_inside_existing_block():
    """A full multi-line example collapses to its command lines."""
    from editor.draw_catalog import get_entry as _get
    example = _get('perp').example
    text = '*draw(\n    *point(Z = 1, 1)\n)'
    edit = build_insert_text(example, text, 10)
    result = text[:edit.start] + edit.insert + text[edit.end:]
    lines = result.split('\n')
    assert lines[0] == '*draw('
    assert lines[1] == '    *point(Z = 1, 1)'
    # Every example line lands inside the block, indented, wrapper dropped.
    assert lines[-1] == ')'
    body = lines[2:-1]
    assert all(line.startswith('    *') for line in body)
    assert any('*perp(A ; B ; A ; C)' in line for line in body)
    assert not any(line.startswith('*draw(') for line in body[1:])


def test_insert_accepts_catalog_entry_directly():
    entry = get_entry('line')
    assert isinstance(entry, CatalogEntry)
    edit = build_insert_text(entry, '', 0)
    assert edit.insert.startswith('*draw(\n')
    assert '*line(A ; B)' in edit.insert


def test_insert_empty_source_raises():
    with pytest.raises(ValueError):
        build_insert_text('', 'text', 0)
    with pytest.raises(ValueError):
        build_insert_text('   \n  ', 'text', 0)


def test_insert_result_is_a_valid_block_for_the_compiler():
    """Round-trip: the edited document still parses with the one parser."""
    from geometry.parsing import parse_draw_block

    text = '*draw(\n    *triangle(A ; B ; C)\n)'
    edit = build_insert_text('*right-angle(B ; A ; C)', text, 10)
    result = text[:edit.start] + edit.insert + text[edit.end:]
    body = draw_block_body(result)
    out = parse_draw_block(body)
    assert '[GeometryError]' not in out


# ----------------------------------------------------------------------
# Template-window palette helpers (commands_in / symbol_for_command)
# ----------------------------------------------------------------------

def test_commands_in_reports_catalog_calls_in_order():
    from editor.draw_catalog import commands_in
    # First-appearance order, deduped: the *perp example.
    assert commands_in(get_entry('perp').example) == [
        'point', 'distance', 'perp', 'triangle', 'right-angle']
    # Nested (unstarred) calls count; *draw itself is not a catalog
    # command; unknown calls (variables, calc, user fns) drop out.
    nested = ('*draw(\n'
              '    *intersection(P ; line(A ; D) ; line(B ; C))\n'
              '    *foo(A)\n'
              ')')
    assert commands_in(nested) == ['intersection', 'line']
    assert commands_in('*draw(\n)') == []
    assert commands_in('') == []
    assert commands_in(None) == []


def test_commands_in_ignores_comments_and_fenced_blocks():
    from editor.draw_catalog import commands_in
    # Commands only MENTIONED in a // comment are not used code —
    # pinning them would bold rows the snippet never calls.  Same
    # line rules as find_enclosing_draw_block (comment stripping).
    commented = ('*draw(\n'
                 '    *point(A = 0, 0) // sketch the circle(\n'
                 '    // *line(A ; B)\n'
                 ')')
    assert commands_in(commented) == ['point']
    assert commands_in('// see https://example.com/x( and *line(\n'
                       '*draw(\n)') == []
    # Fenced code blocks are documentation, not the snippet itself.
    fenced = '```\n*circle(O ; A)\n```\n*draw(\n    *line(A ; B)\n)'
    assert commands_in(fenced) == ['line']


def test_symbol_for_command_maps_to_geo_dialog_or_none():
    from editor.draw_catalog import symbol_for_command
    assert symbol_for_command('perp') == 'geo-perp'
    assert symbol_for_command('point') == 'geo-point'
    # equal-angle is [planned]: no geo-* symbol in the registry.
    assert symbol_for_command('equal-angle') is None
    assert symbol_for_command('draw') is None
    assert symbol_for_command('nope') is None


# ----------------------------------------------------------------------
# Preview manifest (stale detection) — skipped until generated
# ----------------------------------------------------------------------

_MANIFEST = os.path.join(os.path.dirname(__file__), '..', 'src', 'editor',
                         'assets', 'draw_previews', 'manifest.json')


def test_examples_match_preview_manifest():
    """Each example's hash must match the committed manifest (the SVG
    previews were rendered from those exact examples)."""
    if not os.path.isfile(_MANIFEST):
        pytest.skip('no manifest.json — run scripts/build_draw_previews.py '
                    'to (re)generate previews')
    with open(_MANIFEST, encoding='utf-8') as handle:
        manifest = json.load(handle)
    entries = manifest.get('examples', manifest)
    stale = []
    for entry in CATALOG:
        digest = hashlib.sha256(entry.example.encode('utf-8')).hexdigest()
        recorded = entries.get(entry.id)
        if isinstance(recorded, dict):
            recorded = recorded.get('sha256')
        if recorded != digest:
            stale.append(entry.id)
    assert not stale, (
        f'stale previews for {stale}: examples changed since the SVGs '
        'were rendered — rerun scripts/build_draw_previews.py')
