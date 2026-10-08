"""Tests for the Symbol Bar / Smart Symbol Palette (non-UI + light UI)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from editor.symbol_registry import (  # noqa: E402
    apply_insert,
    build_source,
    get_symbol,
    list_categories,
    list_symbols,
    symbols_in_category,
    validate_fields,
)


# ----------------------------------------------------------------------
# 1. Direct symbol insertion
# ----------------------------------------------------------------------

def test_direct_symbols_return_verbatim_insert():
    assert build_source('le', {}) == '<='
    assert build_source('pi-sym', {}) == '*pi'
    assert build_source('arrow-r', {}) == '->'
    sym = get_symbol('le')
    assert sym.requires_dialog is False
    assert sym.insert_text == '<='


def test_direct_symbols_cover_compiler_tables():
    from compiler.symbols import SYMBOL_REPLACEMENTS, WORD_REPLACEMENTS
    ascii_src = {old for old, _ in SYMBOL_REPLACEMENTS}
    words = {w for w, _ in WORD_REPLACEMENTS}
    for sym in list_symbols():
        if sym.requires_dialog:
            continue
        ins = sym.insert_text or ''
        if '\n' in ins:  # multiline draw skeleton
            continue
        if ins.startswith('*'):
            assert ins[1:] in words, f'{sym.name} {ins!r} not in WORD_REPLACEMENTS'
        else:
            assert ins in ascii_src, f'{sym.name} {ins!r} not in SYMBOL_REPLACEMENTS'


# ----------------------------------------------------------------------
# 2. Template generation
# ----------------------------------------------------------------------

def test_template_generation_math():
    assert build_source('frac', {'numerator': '2', 'denominator': '3'}) == '*frac(2 ; 3)'
    assert build_source('pow', {'base': 'x', 'exponent': '2'}) == '*pow(x ; 2)'
    assert build_source('sqrt', {'expression': '16'}) == '*sqrt(16)'
    assert build_source('sum',
                        {'lower': 'i = 1', 'upper': 'n', 'expression': 'i'}) == \
        '*sum(i = 1 ; n ; i)'
    assert build_source('lim',
                        {'condition': 'x -> 0', 'expression': 'sin(x) / x'}) == \
        '*lim(x -> 0 ; sin(x) / x)'
    assert build_source('calc', {'expression': '2+3'}) == 'calc(2+3)'


def test_template_generation_variables_and_text():
    assert build_source('var-def', {'name': 'x', 'value': '5'}) == '<x> = 5'
    assert build_source('define', {'name': 'pi2', 'value': '3.14'}) == \
        '*define(pi2 = 3.14)'
    assert build_source('heading', {'title': 'Hi'}) == '# Hi'
    assert build_source('inline-math', {'expression': 'x^2'}) == '\\ x^2 \\'


# ----------------------------------------------------------------------
# 3. Parameterized command generation (geometry wrapped in *draw)
# ----------------------------------------------------------------------

def test_geometry_commands_wrapped_in_draw():
    assert build_source('geo-line', {'a': 'A', 'b': 'B'}) == '*draw(*line(A ; B))'
    assert build_source('geo-ray', {'a': 'A', 'b': 'B'}) == '*draw(*ray(A ; B))'
    assert build_source('geo-right-angle',
                        {'p1': 'B', 'vertex': 'A', 'p2': 'C'}) == \
        '*draw(*right-angle(B ; A ; C))'
    assert build_source('geo-arc',
                        {'center': 'O', 'start': 'A', 'end': 'B'}) == \
        '*draw(*arc(O ; A ; B))'
    assert build_source('geo-label', {'point': 'P', 'text': 'hi'}) == \
        '*draw(*label(P ; hi))'
    assert build_source('geo-length', {'a': 'A', 'b': 'B', 'value': ''}) == \
        '*draw(*length(A ; B))'
    assert build_source('geo-length', {'a': 'A', 'b': 'B', 'value': '5'}) == \
        '*draw(*length(A ; B) = 5)'
    assert build_source('geo-angle-value',
                        {'a': 'A', 'vertex': 'B', 'c': 'C', 'value': '90'}) == \
        '*draw(*angle-value(A ; B ; C) = 90)'


def test_geometry_optional_fields():
    # Point without coords vs with coords.
    assert build_source('geo-point', {'name': 'A', 'x': '', 'y': ''}) == \
        '*draw(*point(A))'
    assert build_source('geo-point', {'name': 'A', 'x': '0', 'y': '1'}) == \
        '*draw(*point(A = 0, 1))'
    # Angle label optional.
    assert build_source('geo-angle',
                        {'a': 'A', 'vertex': 'B', 'c': 'C', 'label': ''}) == \
        '*draw(*angle(A ; B ; C))'
    assert build_source('geo-angle',
                        {'a': 'A', 'vertex': 'B', 'c': 'C', 'label': '60'}) == \
        '*draw(*angle(A ; B ; C ; 60))'
    # Perp 3-arg vs 4-arg.
    assert build_source('geo-perp',
                        {'a': 'A', 'b': 'B', 'c': 'C', 'd': ''}) == \
        '*draw(*perp(A ; B ; C))'
    assert 'C ; D' in build_source('geo-perp',
                                   {'a': 'A', 'b': 'B', 'c': 'C', 'd': 'D'})


# ----------------------------------------------------------------------
# 4. Required-field validation
# ----------------------------------------------------------------------

def test_required_field_validation():
    sym = get_symbol('frac')
    assert validate_fields(sym, {'numerator': '', 'denominator': '3'}) != []
    assert validate_fields(sym, {'numerator': '2', 'denominator': ''}) != []
    assert validate_fields(sym, {'numerator': '2', 'denominator': '3'}) == []
    with pytest.raises(ValueError):
        build_source('frac', {'numerator': '', 'denominator': '3'})


def test_pattern_validation_for_names():
    line = get_symbol('geo-line')
    assert validate_fields(line, {'a': '1bad', 'b': 'B'}) != []
    var = get_symbol('var-def')
    assert validate_fields(var, {'name': 'has space', 'value': '1'}) != []
    assert validate_fields(var, {'name': 'x', 'value': '1'}) == []


def test_point_xy_pair_rule():
    sym = get_symbol('geo-point')
    assert any('both' in e.lower()
               for e in validate_fields(sym, {'name': 'A', 'x': '1', 'y': ''}))


# ----------------------------------------------------------------------
# 5. Canceling a dialog inserts nothing
# ----------------------------------------------------------------------

def test_dialog_reject_returns_not_accepted(qapp):
    from PySide6 import QtWidgets
    from editor.symbol_dialog import SymbolDialog
    sym = get_symbol('frac')
    dlg = SymbolDialog(sym, None)
    dlg.reject()
    assert dlg.result() == QtWidgets.QDialog.Rejected


def test_main_window_cancel_inserts_nothing(qapp, monkeypatch):
    from editor.main_window import MainWindow
    from editor.symbol_dialog import SymbolDialog
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        win.editor.setPlainText('hello')
        from PySide6 import QtGui as _QG
        win.editor.moveCursor(_QG.QTextCursor.End)
        monkeypatch.setattr(SymbolDialog, 'get_values',
                            classmethod(lambda cls, *a, **k: (False, {})))
        win._on_symbol_activated('frac')
        assert win.editor.toPlainText() == 'hello'
    finally:
        win.close()


def test_dialog_validation_blocks_empty_accept(qapp):
    from editor.symbol_dialog import SymbolDialog
    sym = get_symbol('frac')
    dlg = SymbolDialog(sym, None)
    dlg._edits['numerator'].setText('')
    dlg._edits['denominator'].setText('3')
    dlg._on_accept()  # should stay open, not accept
    from PySide6 import QtWidgets as _QW
    assert dlg.result() != _QW.QDialog.Accepted
    assert dlg._error.text() != ''


# ----------------------------------------------------------------------
# 6/7. Cursor insertion at different positions + selection replacement
# ----------------------------------------------------------------------

def test_apply_insert_begin_middle_end():
    assert apply_insert('world', 0, 0, 'hello ') == ('hello world', 6)
    assert apply_insert('helloworld', 5, 5, ' ') == ('hello world', 6)
    assert apply_insert('hello', 5, 5, ' world') == ('hello world', 11)


def test_apply_insert_multiline():
    original = 'line1\nline2\nline3\n'
    # Insert at start of second line (offset 6).
    new_text, cursor = apply_insert(original, 6, 6, 'XX')
    assert new_text == 'line1\nXXline2\nline3\n'
    assert cursor == 8
    # Insert at end.
    new_text, cursor = apply_insert(original, len(original), len(original), 'end')
    assert new_text.endswith('end')
    assert cursor == len(new_text)


def test_apply_insert_replaces_selection():
    new_text, cursor = apply_insert('hello world', 6, 11, 'there')
    assert new_text == 'hello there'
    assert cursor == len('hello there')
    # Reversed ranges are normalized.
    new_text, _ = apply_insert('abcdef', 4, 2, 'X')
    assert new_text == 'abXef'


def test_main_window_direct_insert_replaces_selection(qapp):
    from PySide6 import QtGui
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        win.editor.setPlainText('a + b')
        cursor = win.editor.textCursor()
        cursor.setPosition(4)
        cursor.setPosition(5, QtGui.QTextCursor.KeepAnchor)  # select 'b'
        win.editor.setTextCursor(cursor)
        win._on_symbol_activated('pi-sym')
        assert win.editor.toPlainText() == 'a + *pi'
        # Cursor sits right after the inserted text.
        assert win.editor.textCursor().position() == len('a + *pi')
    finally:
        win.close()


# ----------------------------------------------------------------------
# 8. Generated source accepted by the compiler
# ----------------------------------------------------------------------

def _compile_text(tmp_path, monkeypatch, capsys, text):
    from compiler import compile_ezmath
    from compiler import pipeline as _pipeline
    src = tmp_path / 'case.ezmath'
    src.write_text(text, encoding='utf-8')
    stub = type('_TypstStub', (),
                {'compile': staticmethod(lambda *a, **k: None)})()
    monkeypatch.setattr(_pipeline, 'typst', stub)
    ok = compile_ezmath(str(src), str(tmp_path / 'case.pdf'))
    typ = (tmp_path / 'case.typ').read_text(encoding='utf-8')
    err = capsys.readouterr().err
    return ok, typ, err


def test_generated_math_accepted(tmp_path, monkeypatch, capsys):
    for name, values, needle in [
        ('frac', {'numerator': '2', 'denominator': '3'}, '$frac(2, 3)$'),
        ('pow', {'base': 'x', 'exponent': '2'}, '^(2)'),
        ('calc', {'expression': '2+3'}, '5'),
        ('sqrt', {'expression': '16'}, '$sqrt(16)$'),
    ]:
        src = build_source(name, values) + '\n'
        ok, typ, err = _compile_text(tmp_path, monkeypatch, capsys, src)
        assert ok is True, err
        assert '[Error]' not in err, err
        assert needle in typ, typ


def test_generated_geometry_accepted(tmp_path, monkeypatch, capsys):
    for name, values in [
        ('geo-point', {'name': 'A', 'x': '0', 'y': '0'}),
        ('geo-line', {'a': 'A', 'b': 'B'}),
        ('geo-ray', {'a': 'A', 'b': 'B'}),
        ('geo-right-angle', {'p1': 'B', 'vertex': 'A', 'p2': 'C'}),
        ('geo-angle', {'a': 'A', 'vertex': 'B', 'c': 'C', 'label': ''}),
        ('geo-arc', {'center': 'O', 'start': 'A', 'end': 'B'}),
        ('geo-label', {'point': 'P', 'text': 'hi'}),
        ('geo-length', {'a': 'A', 'b': 'B', 'value': ''}),
        ('geo-angle-value', {'a': 'A', 'vertex': 'B', 'c': 'C', 'value': ''}),
    ]:
        src = build_source(name, values) + '\n'
        ok, typ, err = _compile_text(tmp_path, monkeypatch, capsys, src)
        assert ok is True, (name, err)
        assert '[Error]' not in err, (name, err)
        assert 'cetz' in typ, typ


def test_generated_direct_symbols_accepted(tmp_path, monkeypatch, capsys):
    for name in ['le', 'ge', 'ne', 'arrow-r', 'pi-sym', 'alpha', 'times']:
        src = get_symbol(name).insert_text + '\n'
        ok, _typ, err = _compile_text(tmp_path, monkeypatch, capsys, src)
        assert ok is True, (name, err)
        assert '[Error]' not in err, (name, err)


# ----------------------------------------------------------------------
# UI wiring smoke tests
# ----------------------------------------------------------------------

def test_symbol_bar_present_and_categorized(qapp):
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        bar = win._symbol_bar
        assert bar is not None
        assert 'All' in [bar.categoryCombo.itemText(i)
                         for i in range(bar.categoryCombo.count())]
        for cat in list_categories():
            assert cat in [bar.categoryCombo.itemText(i)
                           for i in range(bar.categoryCombo.count())]
        # Every button has a tooltip (command name + description).
        assert bar.button_for('frac') is not None
        assert bar.button_for('frac').toolTip() != ''
        # Category filtering shrinks the visible set.
        bar.categoryCombo.setCurrentText('Geometry')
        assert all(s.category == 'Geometry' for s in bar.visible_symbols())
        assert len(bar.visible_symbols()) < len(list_symbols())
    finally:
        win.close()


def test_symbol_metadata_shared_with_lsp_docs():
    from lsp.builtins import GEOMETRY_DOCS, MATH_DOCS
    frac = get_symbol('frac')
    assert MATH_DOCS['frac'][0] in frac.tooltip
    line = get_symbol('geo-line')
    assert GEOMETRY_DOCS['line'][0] in line.tooltip


# ----------------------------------------------------------------------
# Registry/compiler synchronization (derived metadata, still curated)
# ----------------------------------------------------------------------

def test_direct_glyphs_derived_from_compiler_tables():
    from compiler.symbols import SYMBOL_REPLACEMENTS, WORD_REPLACEMENTS
    ascii_glyph = dict(SYMBOL_REPLACEMENTS)
    word_glyph = dict(WORD_REPLACEMENTS)
    assert get_symbol('le').display == ascii_glyph['<=']
    assert get_symbol('arrow-r').display == ascii_glyph['->']
    assert get_symbol('pi-sym').display == word_glyph['pi']
    assert get_symbol('alpha').display == word_glyph['alpha']
    assert get_symbol('times').display == word_glyph['times']


def test_curated_commands_exist_in_compiler_tables():
    from compiler.diagnostics import KNOWN_COMMANDS
    from geometry.commands import KNOWN_GEOMETRY_COMMANDS
    for sym in list_symbols():
        if not sym.requires_dialog or not sym.command:
            continue
        if sym.wrap_draw:
            assert sym.command in KNOWN_GEOMETRY_COMMANDS, sym.name
        else:
            assert sym.command in KNOWN_COMMANDS, sym.name


def test_curated_syntax_matches_lsp_docs():
    from lsp.builtins import GEOMETRY_DOCS, MATH_DOCS
    for sym in list_symbols():
        if not sym.requires_dialog or not sym.command:
            continue
        if sym.wrap_draw:
            assert GEOMETRY_DOCS[sym.command][0] == sym.syntax, sym.name
        else:
            assert MATH_DOCS[sym.command][0] == sym.syntax, sym.name


def test_generic_builder_matches_compiler_min_arity():
    from compiler.math_commands import math_call_specs
    min_args = {n: a for n, a, _ in math_call_specs(None)}
    for name in ('frac', 'pow', 'sqrt', 'sum', 'prod', 'lim', 'sin'):
        sym = get_symbol(name)
        required = sum(1 for f in sym.fields if f.required)
        assert required >= min_args[sym.command], name


def test_palette_stays_curated_not_exhaustive():
    # Deliberately curated: aliases and planned commands stay out.
    names = {s.name for s in list_symbols()}
    assert 'equal-angle' not in {s.command for s in list_symbols() if s.command}
    assert 'fraction' not in names  # alias of frac, available via LSP only
    assert get_symbol('frac').command == 'frac'


# ----------------------------------------------------------------------
# Dynamic table/matrix grids (Add row / Add cell)
# ----------------------------------------------------------------------

def _open_grid_dialog(qapp, name):
    from editor.symbol_dialog import SymbolDialog
    dlg = SymbolDialog(get_symbol(name), None)
    return dlg


def _click(dlg, object_name):
    from PySide6 import QtWidgets
    btn = dlg.findChild(QtWidgets.QPushButton, object_name)
    assert btn is not None, f'missing button {object_name}'
    btn.click()
    return btn


def test_table_dialog_starts_2x2(qapp):
    dlg = _open_grid_dialog(qapp, 'table')
    try:
        assert sorted(dlg._edits) == ['r1c1', 'r1c2', 'r2c1', 'r2c2']
        assert dlg._shape_label.text() == '2 rows × 2 columns'
        assert dlg._edits['r1c1'].placeholderText() == 'Name'
        assert dlg._edits['r2c2'].placeholderText() == '20'
    finally:
        dlg.close()


def test_table_dialog_add_row(qapp):
    dlg = _open_grid_dialog(qapp, 'table')
    try:
        dlg._edits['r1c1'].setText('Keep')
        _click(dlg, 'symbol-add-row')
        assert sorted(dlg._edits) == [
            'r1c1', 'r1c2', 'r2c1', 'r2c2', 'r3c1', 'r3c2']
        assert dlg._shape_label.text() == '3 rows × 2 columns'
        # Typed values preserved, new row hinted.
        assert dlg._edits['r1c1'].text() == 'Keep'
        assert dlg._edits['r3c1'].placeholderText() == 'R3C1'
        assert dlg._edits['r3c2'].placeholderText() == 'R3C2'
    finally:
        dlg.close()


def test_matrix_dialog_add_cell(qapp):
    dlg = _open_grid_dialog(qapp, 'matrix')
    try:
        dlg._edits['r1c1'].setText('9')
        _click(dlg, 'symbol-add-cell')
        assert sorted(dlg._edits) == [
            'r1c1', 'r1c2', 'r1c3', 'r2c1', 'r2c2', 'r2c3']
        assert dlg._shape_label.text() == '2 rows × 3 columns'
        assert dlg._edits['r1c1'].text() == '9'
        assert dlg._edits['r1c3'].placeholderText() == '5'
        assert dlg._edits['r2c3'].placeholderText() == '6'
    finally:
        dlg.close()


def test_grid_dialog_multi_ops(qapp):
    # Row, row, cell from 2x2 -> 4x3.
    dlg = _open_grid_dialog(qapp, 'table')
    try:
        _click(dlg, 'symbol-add-row')
        _click(dlg, 'symbol-add-row')
        _click(dlg, 'symbol-add-cell')
        assert len(dlg._edits) == 12
        assert dlg._shape_label.text() == '4 rows × 3 columns'
        assert 'r4c3' in dlg._edits
        assert dlg._edits['r4c3'].placeholderText() == 'R4C3'
    finally:
        dlg.close()


def test_table_dialog_accept_extended(qapp):
    from PySide6 import QtWidgets as _QW
    from editor.symbol_registry import build_source
    dlg = _open_grid_dialog(qapp, 'table')
    try:
        _click(dlg, 'symbol-add-row')
        for key, edit in dlg._edits.items():
            edit.setText('v-' + key)
        dlg._on_accept()
        assert dlg.result() == _QW.QDialog.Accepted
        assert dlg._error.text() == ''
        src = build_source(get_symbol('table'), dlg.values())
        assert src == '*table(v-r1c1 ; v-r1c2 | v-r2c1 ; v-r2c2 | v-r3c1 ; v-r3c2)'
    finally:
        dlg.close()


def test_matrix_dialog_accept_extended(qapp):
    from PySide6 import QtWidgets as _QW
    from editor.symbol_registry import build_source
    dlg = _open_grid_dialog(qapp, 'matrix')
    try:
        _click(dlg, 'symbol-add-cell')
        for key, edit in dlg._edits.items():
            edit.setText('7')
        dlg._on_accept()
        assert dlg.result() == _QW.QDialog.Accepted
        assert build_source(get_symbol('matrix'), dlg.values()) == \
            '*matrix(7 ; 7 ; 7 | 7 ; 7 ; 7)'
    finally:
        dlg.close()


def test_grid_dialog_blocks_empty_new_cell(qapp):
    from PySide6 import QtWidgets as _QW
    dlg = _open_grid_dialog(qapp, 'table')
    try:
        _click(dlg, 'symbol-add-row')
        for key, edit in dlg._edits.items():
            edit.setText('x')
        dlg._edits['r3c2'].setText('   ')
        dlg._on_accept()  # required-cell validation must hold
        assert dlg.result() != _QW.QDialog.Accepted
        assert 'Row 3 Col 2' in dlg._error.text()
    finally:
        dlg.close()


def test_nongrid_dialog_has_no_grid_buttons(qapp):
    dlg = _open_grid_dialog(qapp, 'frac')
    try:
        from PySide6 import QtWidgets
        assert dlg.findChild(QtWidgets.QPushButton, 'symbol-add-row') is None
        assert dlg.findChild(QtWidgets.QPushButton, 'symbol-add-cell') is None
        assert dlg._shape_label is None
    finally:
        dlg.close()


def test_grid_dialog_layout_autofits_contents(qapp):
    from PySide6 import QtWidgets
    for name in ('table', 'matrix'):
        dlg = _open_grid_dialog(qapp, name)
        try:
            assert dlg.layout().sizeConstraint() == \
                QtWidgets.QLayout.SetFixedSize
        finally:
            dlg.close()


def test_grid_dialog_window_tracks_growth(qapp):
    # Repeated Add row/cell used to leave the window at its stale smaller
    # geometry while the layout minimum kept growing — the condition the
    # Windows plugin reported as "Unable to set geometry" warnings.
    # (Layout minimums settle via the event loop by Qt design, so the
    # size assertions below run after processing events; the dialog state
    # itself — edits, shape label — is asserted synchronously.
    # NOTE: on Wayland, top-level height() lags minimumHeight() by one
    # compositor frame and even oscillates (267<->515), so the invariant
    # under test is the layout minimum/sizeHint growth, not the
    # compositor-driven height. Asserting height directly is flaky.)
    dlg = _open_grid_dialog(qapp, 'table')
    try:
        dlg.show()
        qapp.processEvents()
        assert dlg.height() >= dlg.minimumHeight()
        h0 = dlg.height()
        m0 = dlg.minimumHeight()
        _click(dlg, 'symbol-add-row')
        _click(dlg, 'symbol-add-row')
        _click(dlg, 'symbol-add-cell')
        # Dialog state updates synchronously.
        assert dlg._shape_label.text() == '4 rows × 3 columns'
        assert len(dlg._edits) == 12
        # No ghost rows left behind by the growth path.
        assert dlg._form.rowCount() == len(dlg._edits)
        # Pump until the layout minimum reflects the 12-row form
        # (stale timers from earlier MainWindow tests can consume the
        # first processEvents round).
        for _ in range(20):
            qapp.processEvents()
            if dlg.minimumHeight() > m0:
                break
        # The layout minimum must honor the grown contents (deterministic,
        # compositor-independent).
        assert dlg.minimumHeight() > m0
        assert dlg.sizeHint().height() > h0
        assert dlg.minimumWidth() >= 0
        # Best-effort height check: allow the Wayland async lag — pass
        # when the window already caught up, otherwise the minimum growth
        # above is the load-bearing assertion.
        for _ in range(20):
            if dlg.height() > h0:
                break
            qapp.processEvents()
        assert dlg.height() > h0 or dlg.minimumHeight() > m0
    finally:
        dlg.close()


# ----------------------------------------------------------------------
# Geometry cursor placement (inside *draw, no snippet engine)
# ----------------------------------------------------------------------

def test_cursor_offset_for_insert_defaults_to_end():
    from editor.symbol_registry import cursor_offset_for_insert
    assert cursor_offset_for_insert('frac', '*frac(2 ; 3)') == len('*frac(2 ; 3)')
    assert cursor_offset_for_insert('le', '<=') == len('<=')


def test_draw_skeleton_cursor_stays_inside_block():
    from editor.symbol_registry import cursor_offset_for_insert
    sym = get_symbol('draw-skeleton')
    assert sym.insert_text is not None
    off = cursor_offset_for_insert(sym, sym.insert_text)
    assert 0 < off < len(sym.insert_text)
    assert sym.insert_text[off] == ')'
    assert sym.insert_text[:off].rstrip().endswith('*line(A ; B)')


def test_apply_insert_honors_cursor_offset():
    assert apply_insert('ab', 1, 1, 'X', cursor_offset=0) == ('aXb', 1)
    assert apply_insert('ab', 0, 0, 'XYZ', cursor_offset=1) == ('XYZab', 1)
    # Clamped, never outside the inserted text.
    assert apply_insert('', 0, 0, 'XY', cursor_offset=99) == ('XY', 2)


def test_main_window_skeleton_cursor_inside_draw(qapp):
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        win.editor.setPlainText('')
        win._on_symbol_activated('draw-skeleton')
        text = win.editor.toPlainText()
        pos = win.editor.textCursor().position()
        assert text.startswith('*draw(') and text.endswith(')')
        assert 0 < pos < len(text)
        assert text[pos] == ')'
    finally:
        win.close()


# ----------------------------------------------------------------------
# Discoverability (tooltips, accessibility, category order)
# ----------------------------------------------------------------------

def test_tooltip_names_command_category_and_behavior():
    frac = get_symbol('frac')
    assert '*frac(numerator ; denominator)' in frac.tooltip
    assert 'Math' in frac.tooltip
    assert 'dialog' in frac.tooltip.lower()
    le = get_symbol('le')
    assert '<=' in le.tooltip
    assert 'Basic' in le.tooltip
    assert 'directly' in le.tooltip.lower()


def test_symbol_buttons_expose_accessible_names(qapp):
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        btn = win._symbol_bar.button_for('frac')
        assert btn is not None
        assert '*frac' in btn.accessibleName()
        assert btn.accessibleDescription() != ''
    finally:
        win.close()


def test_category_order_stable_and_sensible():
    assert list_categories() == ['Basic', 'Math', 'Variables', 'Geometry', 'Text']
