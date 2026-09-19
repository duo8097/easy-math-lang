"""Unit tests for the LSP analysis layer (no server, no GUI)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from easy_math_lang.lsp import analysis
from easy_math_lang.lsp.document import DocumentStore


def test_valid_document_has_no_diagnostics():
    result = analysis.analyze_text("<w> = 5\nArea: <w>\n")
    assert result.diagnostics == []


def test_syntax_error_unclosed_calc():
    result = analysis.analyze_text("Total: calc(2 + 3\n")
    assert result.diagnostics, "expected a diagnostic for unclosed calc("
    diag = result.diagnostics[0]
    assert diag.severity == 'error'
    assert diag.line == 0
    assert 'calc' in diag.message.lower()


def test_undefined_identifier_with_suggestion():
    result = analysis.analyze_text("*define(width = 10)\nShow <widt>\n")
    errors = [d for d in result.diagnostics if d.severity == 'error']
    assert len(errors) == 1
    assert errors[0].line == 1
    assert '<widt>' in errors[0].message
    assert "Did you mean 'width'?" in errors[0].message


def test_undefined_identifier_positions():
    text = "ok\nUse <foo> here\n"
    result = analysis.analyze_text(text)
    assert len(result.diagnostics) == 1
    diag = result.diagnostics[0]
    assert (diag.line, diag.start, diag.end) == (1, 4, 9)


def test_unknown_command_warning():
    result = analysis.analyze_text("*foobar(1 ; 2)\n")
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].severity == 'warning'
    assert '*foobar' in result.diagnostics[0].message


def test_calc_division_by_zero():
    result = analysis.analyze_text("calc(1 / 0)\n")
    assert any(d.severity == 'error' and 'division by zero' in d.message
               for d in result.diagnostics)


def test_geometry_malformed_block():
    result = analysis.analyze_text("*draw(\n*point(A\n)\n")
    assert any('unclosed parentheses' in d.message
               for d in result.diagnostics)


def test_completion_of_defined_variable():
    text = "*define(width = 10)\n*define(height = 5)\n<area> = calc(<width> * 2)\nShow wid\n"
    items = analysis.complete(text, 3, len("Show wid"))
    labels = [item['label'] for item in items]
    assert 'width' in labels
    assert 'height' in labels


def test_completion_includes_builtins():
    items = analysis.complete("*frac(1 ; 2)\n", 0, 0)
    labels = [item['label'] for item in items]
    assert 'frac' in labels
    assert 'define' in labels
    assert 'calc' in labels


def test_hover_variable_value():
    text = "*define(width = 10)\n<area> = calc(<width> * 2)\n"
    line = "<area> = calc(<width> * 2)"
    found = analysis.hover(text, 1, line.index('width') + 1)
    assert found is not None
    assert 'width' in found['value']
    assert '10' in found['value']


def test_hover_builtin():
    found = analysis.hover("*frac(1 ; 2)\n", 0, 2)
    assert found is not None
    assert 'frac' in found['value']


def test_hover_unknown_returns_none():
    assert analysis.hover("hello world\n", 0, 2) is None


def test_document_symbols():
    text = "*define(width = 10)\n<area> = calc(<width> * 2)\n*draw(*triangle(A ; B ; C))\n"
    symbols = analysis.document_symbols(text)
    by_name = {name: kind for name, kind, *_ in symbols}
    assert by_name.get('width') == 'define'
    assert by_name.get('area') == 'variable'
    assert by_name.get('draw') == 'draw'


def test_document_store():
    store = DocumentStore()
    store.open('file:///a.ezmath', 'v1', version=1)
    assert store.get('file:///a.ezmath') == 'v1'
    store.update('file:///a.ezmath', 'v2', version=2)
    assert store.get('file:///a.ezmath') == 'v2'
    assert store.version('file:///a.ezmath') == 2
    store.close('file:///a.ezmath')
    assert store.get('file:///a.ezmath') is None
