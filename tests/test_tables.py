"""Tests for *table / *matrix / *mat (single-line + block form)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from compiler import compile_ezmath
from compiler import pipeline as _pipeline


def compile_text(tmp_path, monkeypatch, capsys, text):
    src = tmp_path / "case.ezmath"
    src.write_text(text, encoding="utf-8")
    stub = type("_TypstStub", (), {"compile": staticmethod(lambda *a, **k: None)})()
    monkeypatch.setattr(_pipeline, "typst", stub)
    ok = compile_ezmath(str(src), str(tmp_path / "case.pdf"))
    typ = (tmp_path / "case.typ").read_text(encoding="utf-8")
    err = capsys.readouterr().err
    return ok, typ, err


def test_table_basic(tmp_path, monkeypatch, capsys):
    ok, typ, err = compile_text(
        tmp_path, monkeypatch, capsys,
        "*table(Name ; Age | Alice ; 20)\n",
    )
    assert ok is True
    assert "#table(columns: 2," in typ
    assert "[Name]" in typ and "[Alice]" in typ and "[20]" in typ
    assert "[Error]" not in err


def test_table_comma_cells(tmp_path, monkeypatch, capsys):
    ok, typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "*table(A, B | C, D)\n"
    )
    assert ok is True
    assert "#table(columns: 2," in typ


def test_table_thousands_kept(tmp_path, monkeypatch, capsys):
    ok, typ, _ = compile_text(
        tmp_path, monkeypatch, capsys,
        "*table(Price ; Qty | 100,000 ; 2)\n",
    )
    assert ok is True
    assert "100,000" in typ


def test_matrix_basic(tmp_path, monkeypatch, capsys):
    ok, typ, err = compile_text(
        tmp_path, monkeypatch, capsys, "*matrix(1 ; 2 | 3 ; 4)\n"
    )
    assert ok is True
    assert "$mat(1, 2; 3, 4)$" in typ
    assert "[Error]" not in err


def test_mat_alias(tmp_path, monkeypatch, capsys):
    ok, typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "*mat(1 ; 2 | 3 ; 4)\n"
    )
    assert ok is True
    assert "$mat(1, 2; 3, 4)$" in typ


def test_matrix_math_inside(tmp_path, monkeypatch, capsys):
    ok, typ, _ = compile_text(
        tmp_path, monkeypatch, capsys,
        "*matrix(*frac(1 ; 2) ; x | 3 ; 4)\n",
    )
    assert ok is True
    assert "frac(1, 2)" in typ
    assert typ.count("$mat(") == 1


def test_table_vars_calc_symbols(tmp_path, monkeypatch, capsys):
    ok, typ, _ = compile_text(
        tmp_path, monkeypatch, capsys,
        "<a> = 5\n*table(Item ; Value | Apple ; <a> | Total ; calc(2 + 3))\n",
    )
    assert ok is True
    assert "[Apple]" in typ and "[5]" in typ
    assert "[UNDEFINED" not in typ


def test_table_block_form(tmp_path, monkeypatch, capsys):
    ok, typ, _ = compile_text(
        tmp_path, monkeypatch, capsys,
        "*table(\nName ; Age\nAlice ; 20\n)\n",
    )
    assert ok is True
    assert "#table(columns: 2," in typ
    assert "[Alice]" in typ


def test_matrix_block_form(tmp_path, monkeypatch, capsys):
    ok, typ, _ = compile_text(
        tmp_path, monkeypatch, capsys,
        "*matrix(\n1 ; 2\n3 ; 4\n)\n",
    )
    assert ok is True
    assert "$mat(1, 2; 3, 4)$" in typ


def test_ragged_warns_and_pads(tmp_path, monkeypatch, capsys):
    ok, typ, err = compile_text(
        tmp_path, monkeypatch, capsys, "*table(A ; B | C)\n"
    )
    assert ok is True
    assert "different lengths" in err
    assert "#table(columns: 2," in typ


def test_empty_leaves_as_is(tmp_path, monkeypatch, capsys):
    ok, typ, err = compile_text(
        tmp_path, monkeypatch, capsys, "*table()\n"
    )
    assert ok is True
    assert "empty" in err.lower()
    assert "#table" not in typ


def test_unclosed_warns(tmp_path, monkeypatch, capsys):
    ok, typ, err = compile_text(
        tmp_path, monkeypatch, capsys, "*matrix(1 ; 2\n"
    )
    assert ok is True
    assert "unclosed" in err.lower()
    assert "$mat(" not in typ


def test_pipe_symbols_survive(tmp_path, monkeypatch, capsys):
    ok, typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "*table(A || B | C ; D)\n"
    )
    assert ok is True
    assert "∨" in typ
    assert "#table(columns: 2," in typ


def test_matrix_in_inline_math(tmp_path, monkeypatch, capsys):
    ok, typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "\\ *matrix(1 ; 2 | 3 ; 4) \\\n"
    )
    assert ok is True
    assert "mat(1, 2; 3, 4)" in typ


def test_table_in_text_with_surrounding(tmp_path, monkeypatch, capsys):
    ok, typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "See *table(A ; B) here\n"
    )
    assert ok is True
    assert "See " in typ and " here" in typ
    assert "#table" in typ


def test_real_pdf_table_matrix(tmp_path):
    import pytest as _pytest
    _pytest.importorskip("typst")
    from compiler import pipeline as _pipe
    src = tmp_path / "case.ezmath"
    src.write_text(
        "*table(Name ; Age | Alice ; 20)\n*matrix(1 ; 2 | 3 ; 4)\n",
        encoding="utf-8",
    )
    out = tmp_path / "case.pdf"
    assert _pipe.compile_ezmath(str(src), str(out)) is True
    assert out.is_file() and out.stat().st_size > 0


def test_lsp_no_error_for_valid_table():
    from lsp import analysis
    res = analysis.analyze_text("*table(A ; B | C ; D)\n*matrix(1 ; 2 | 3 ; 4)\n")
    assert not [d for d in res.diagnostics if d.severity == "error"]


def test_lsp_warns_ragged_table():
    from lsp import analysis
    res = analysis.analyze_text("*table(A ; B | C)\n")
    assert any("different lengths" in d.message for d in res.diagnostics)


def test_lsp_table_block_valid():
    from lsp import analysis
    res = analysis.analyze_text("*table(\nA ; B\nC ; D\n)\n")
    assert not [d for d in res.diagnostics if d.severity == "error"]


def test_table_brackets_escaped(tmp_path, monkeypatch, capsys):
    ok, typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "*table(a]b ; C | D ; E)\n"
    )
    assert ok is True
    assert "#table(columns: 2," in typ
    assert r"a\]b" in typ


def test_table_brackets_real_pdf(tmp_path):
    import pytest as _pytest
    _pytest.importorskip("typst")
    from compiler import pipeline as _pipe
    src = tmp_path / "case.ezmath"
    src.write_text("*table(a]b ; C | D ; E)\n", encoding="utf-8")
    out = tmp_path / "case.pdf"
    assert _pipe.compile_ezmath(str(src), str(out)) is True
    assert out.is_file() and out.stat().st_size > 0


def test_mat_block_form(tmp_path, monkeypatch, capsys):
    ok, typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "*mat(\n1 ; 2\n3 ; 4\n)\n"
    )
    assert ok is True
    assert "$mat(1, 2; 3, 4)$" in typ


def test_table_dollar_literal(tmp_path, monkeypatch, capsys):
    ok, typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "*table(cost $5 ; ok)\n"
    )
    assert ok is True
    assert "#table" in typ
    assert r"\$5" in typ


def test_table_mult_sym(tmp_path, monkeypatch, capsys):
    ok, typ, _ = compile_text(
        tmp_path, monkeypatch, capsys,
        "*define(write_type.multiplication = .)\n*table(2 * 3 ; ok)\n",
    )
    assert ok is True
    assert "2 . 3" in typ


def test_lsp_completion_includes_tables():
    from lsp import analysis
    items = analysis.complete("*tab", 0, 4)
    labels = [i["label"] for i in items]
    assert "table" in labels
    assert "matrix" in labels
    assert "mat" in labels


def test_lsp_hover_table():
    from lsp import analysis
    found = analysis.hover("*table(A ; B)\n", 0, 2)
    assert found is not None
    assert "table" in found["value"].lower()


def test_palette_table_build():
    from editor.symbol_registry import build_source
    src = build_source('table', {'r1c1': 'Name', 'r1c2': 'Age',
                                 'r2c1': 'Alice', 'r2c2': '20'})
    assert src == "*table(Name ; Age | Alice ; 20)"


def test_palette_matrix_build():
    from editor.symbol_registry import build_source
    src = build_source('matrix', {'r1c1': '1', 'r1c2': '2',
                                  'r2c1': '3', 'r2c2': '4'})
    assert src == "*matrix(1 ; 2 | 3 ; 4)"


def test_palette_table_requires_all_cells():
    import pytest as _pytest
    from editor.symbol_registry import build_source
    with _pytest.raises(ValueError):
        build_source('table', {'r1c1': '', 'r1c2': 'B',
                               'r2c1': 'C', 'r2c2': 'D'})


def test_palette_generated_source_compiles(tmp_path, monkeypatch, capsys):
    from editor.symbol_registry import build_source
    for name, values, needle in [
        ('table', {'r1c1': 'Name', 'r1c2': 'Age',
                   'r2c1': 'Alice', 'r2c2': '20'}, "#table(columns: 2,"),
        ('matrix', {'r1c1': '1', 'r1c2': '2',
                    'r2c1': '3', 'r2c2': '4'}, "$mat(1, 2; 3, 4)$"),
    ]:
        src = build_source(name, values) + "\n"
        ok, typ, err = compile_text(tmp_path, monkeypatch, capsys, src)
        assert ok is True, err
        assert needle in typ, typ


# ----------------------------------------------------------------------
# Dynamic grids: default 2x2, Add row / Add cell, repeated ops
# ----------------------------------------------------------------------

def _grid_values(rows, cols, prefix='v'):
    return {f'r{r}c{c}': f'{prefix}{r}{c}'
            for r in range(1, rows + 1) for c in range(1, cols + 1)}


def test_grid_default_shape_and_placeholders():
    from editor.symbol_registry import (
        get_symbol, grid_shape_of_fields, is_grid_symbol,
    )
    for name, base in [
        ('table', {'r1c1': 'Name', 'r1c2': 'Age',
                   'r2c1': 'Alice', 'r2c2': '20'}),
        ('matrix', {'r1c1': '1', 'r1c2': '2',
                    'r2c1': '3', 'r2c2': '4'}),
    ]:
        sym = get_symbol(name)
        assert is_grid_symbol(sym) is True
        assert grid_shape_of_fields(sym.fields) == (2, 2)
        assert {f.key: f.placeholder for f in sym.fields} == base


def test_grid_add_row_fields():
    from editor.symbol_registry import make_grid_fields
    fields = make_grid_fields('table', 3, 2)
    assert [f.key for f in fields] == [
        'r1c1', 'r1c2', 'r2c1', 'r2c2', 'r3c1', 'r3c2']
    assert [f.label for f in fields] == [
        'Row 1 Col 1', 'Row 1 Col 2', 'Row 2 Col 1',
        'Row 2 Col 2', 'Row 3 Col 1', 'Row 3 Col 2']
    by_key = {f.key: f for f in fields}
    # Base placeholders preserved, new row hinted.
    assert (by_key['r1c1'].placeholder, by_key['r1c2'].placeholder,
            by_key['r2c1'].placeholder, by_key['r2c2'].placeholder) == \
        ('Name', 'Age', 'Alice', '20')
    assert (by_key['r3c1'].placeholder, by_key['r3c2'].placeholder) == \
        ('R3C1', 'R3C2')
    fields = make_grid_fields('matrix', 3, 2)
    by_key = {f.key: f for f in fields}
    assert (by_key['r1c1'].placeholder, by_key['r1c2'].placeholder,
            by_key['r2c1'].placeholder, by_key['r2c2'].placeholder) == \
        ('1', '2', '3', '4')
    assert (by_key['r3c1'].placeholder, by_key['r3c2'].placeholder) == \
        ('5', '6')


def test_grid_add_cell_fields():
    from editor.symbol_registry import make_grid_fields
    fields = make_grid_fields('table', 2, 3)
    assert [f.key for f in fields] == [
        'r1c1', 'r1c2', 'r1c3', 'r2c1', 'r2c2', 'r2c3']
    by_key = {f.key: f for f in fields}
    assert by_key['r1c1'].placeholder == 'Name'
    assert by_key['r2c2'].placeholder == '20'
    assert (by_key['r1c3'].placeholder, by_key['r2c3'].placeholder) == \
        ('R1C3', 'R2C3')
    fields = make_grid_fields('matrix', 2, 3)
    by_key = {f.key: f for f in fields}
    assert (by_key['r1c3'].placeholder, by_key['r2c3'].placeholder) == \
        ('5', '6')


def test_grid_add_row_source():
    from editor.symbol_registry import build_source
    assert build_source('table', _grid_values(3, 2)) == \
        "*table(v11 ; v12 | v21 ; v22 | v31 ; v32)"
    assert build_source('matrix', _grid_values(3, 2)) == \
        "*matrix(v11 ; v12 | v21 ; v22 | v31 ; v32)"


def test_grid_add_cell_source():
    from editor.symbol_registry import build_source
    assert build_source('table', _grid_values(2, 3)) == \
        "*table(v11 ; v12 ; v13 | v21 ; v22 ; v23)"
    assert build_source('matrix', _grid_values(2, 3)) == \
        "*matrix(v11 ; v12 ; v13 | v21 ; v22 ; v23)"


def test_grid_multi_ops_source():
    from editor.symbol_registry import build_source, grid_shape_of_values
    # Row, row, cell from 2x2 -> 4x3.
    values = _grid_values(4, 3)
    assert grid_shape_of_values(values) == (4, 3)
    assert build_source('table', values) == (
        "*table(v11 ; v12 ; v13 | v21 ; v22 ; v23 | "
        "v31 ; v32 ; v33 | v41 ; v42 ; v43)")
    assert build_source('matrix', values) == (
        "*matrix(v11 ; v12 ; v13 | v21 ; v22 ; v23 | "
        "v31 ; v32 ; v33 | v41 ; v42 ; v43)")


def test_grid_extended_source_compiles(tmp_path, monkeypatch, capsys):
    from editor.symbol_registry import build_source
    ok, typ, err = compile_text(
        tmp_path, monkeypatch, capsys,
        build_source('table', _grid_values(3, 2)) + "\n")
    assert ok is True, err
    assert "#table(columns: 2," in typ
    ok, typ, err = compile_text(
        tmp_path, monkeypatch, capsys,
        "*matrix(a ; b ; c | d ; e ; f)\n")
    assert ok is True, err
    assert "$mat(a, b, c; d, e, f)$" in typ


def test_grid_extended_validation_still_required():
    import pytest as _pytest
    from editor.symbol_registry import build_source
    values = _grid_values(3, 2)
    values['r3c1'] = '  '
    with _pytest.raises(ValueError):
        build_source('table', values)
    with _pytest.raises(ValueError):
        build_source('matrix', values)


def test_grid_fields_validation_flags_new_cells():
    from dataclasses import replace as _replace
    from editor.symbol_registry import (
        get_symbol, make_grid_fields, validate_fields,
    )
    sym = _replace(get_symbol('table'),
                   fields=make_grid_fields('table', 3, 2))
    values = _grid_values(3, 2)
    assert validate_fields(sym, values) == []
    values['r3c2'] = ''
    errors = validate_fields(sym, values)
    assert any('Row 3 Col 2' in e for e in errors)
