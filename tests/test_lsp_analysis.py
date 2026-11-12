"""Unit tests for the LSP analysis layer (no server, no GUI)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from lsp import analysis
from lsp.document import DocumentStore


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
    assert any('unclosed command' in d.message
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


def test_unclosed_block_warning_not_crash():
    result = analysis.analyze_text("*(\n<a> = 1\n")
    assert len(result.diagnostics) == 1
    diag = result.diagnostics[0]
    assert diag.severity == 'error'
    assert diag.line == 0
    assert 'Unclosed block' in diag.message


def test_duplicate_undefined_each_gets_range():
    result = analysis.analyze_text("Use <oops> and <oops>\n")
    assert [(d.start, d.end) for d in result.diagnostics] == [(4, 10), (15, 21)]


def test_indented_block_symbol_positions():
    result = analysis.analyze_text("*(\n    <a> = 1\n)\n")
    assert [(d.name, d.line, d.start, d.end) for d in result.definitions] == [
        ('a', 1, 4, 7)
    ]


def test_document_store():
    store = DocumentStore()
    store.open('file:///a.ezmath', 'v1', version=1)
    assert store.get('file:///a.ezmath') == 'v1'
    store.update('file:///a.ezmath', 'v2', version=2)
    assert store.get('file:///a.ezmath') == 'v2'
    assert store.version('file:///a.ezmath') == 2
    store.close('file:///a.ezmath')
    assert store.get('file:///a.ezmath') is None


def test_completion_includes_new_symbols():
    items = analysis.complete("*ze", 0, 3)
    labels = [item['label'] for item in items]
    assert '*zeta' in labels


def test_hover_new_symbol():
    found = analysis.hover("*Phi", 0, 2)
    assert found is not None
    assert 'Φ' in found['value']


def test_define_backslash_values_never_raise():
    # Mirrors the compiler crash: backslash-heavy define values must not
    # raise re.error out of analyze_text (which must never raise).
    for value in ("\\1", "C:\\path\\to", "foo\\", "\\g<0>", "a\\\\b"):
        result = analysis.analyze_text(f"*define(FOO = {value})\nhello FOO world\n")
        assert isinstance(result.diagnostics, list)


def test_multiline_math_closes_at_first_delimiter():
    # Mirrors compiler/pipeline.py: the first unescaped backslash on a
    # continuation line closes multiline math; the tail is normal text.
    # The unclosed-math diagnostic must point at the reopened math on
    # line 1, not at the original opener on line 0.
    result = analysis.analyze_text("start \\open\nline with \\pair\\ inside\ntail\n")
    unclosed = [d for d in result.diagnostics if 'Unclosed math' in d.message]
    assert len(unclosed) == 1
    assert unclosed[0].line == 1


def test_equal_angle_block_has_no_diagnostics():
    # *equal-angle is fully implemented (constraint + marks): a valid
    # block must not produce a single LSP diagnostic — it used to carry
    # a "not yet implemented" GeometryError.
    text = (
        "*draw(\n"
        "    *point(A = 0, 0)\n"
        "    *point(B = 4, 0)\n"
        "    *point(C = 2, 3)\n"
        "    *point(D = 7, 0)\n"
        "    *point(E = 11, 0)\n"
        "    *point(F = 9, 3)\n"
        "    *triangle(A ; B ; C)\n"
        "    *triangle(D ; E ; F)\n"
        "    *equal-angle(A ; B ; C ; D ; E ; F)\n"
        ")\n"
    )
    result = analysis.analyze_text(text)
    assert result.diagnostics == []


def test_equal_angle_completion():
    # The command is advertised with its full signature (hover splits
    # hyphenated names into words, like every other geometry command).
    items = analysis.complete("", 0, 0)
    equal_angle = [i for i in items if i['label'] == 'equal-angle']
    assert len(equal_angle) == 1
    assert 'A ; B ; C ; D ; E ; F' in equal_angle[0]['detail']


# --- Audit 6.0.0 regressions (math-delimiter handling, blocks, parity) ---

def test_math_closing_line_anchors_tail_diagnostics():
    # Line 1 closes multiline math at column 2; the tail is normal text.
    result = analysis.analyze_text("\\\nx \\ <undef_var>\n")
    assert [(d.line, d.start, d.end) for d in result.diagnostics] == [(1, 4, 15)]


def test_math_closing_line_definition_anchor():
    # Definition on the tail of a math-closing line gets exact columns.
    result = analysis.analyze_text("\\\nx \\ <tailvar> = 3\n")
    assert [(d.name, d.line, d.start, d.end) for d in result.definitions] == [
        ('tailvar', 1, 4, 13),
    ]


def test_math_closing_line_head_is_checked():
    # The math head of a closing line is part of the math body: an
    # undefined variable there is an error (compiler parity).
    result = analysis.analyze_text("\\\nfoo <head_var> bar \\\n")
    diags = [d for d in result.diagnostics if d.severity == 'error']
    assert diags and all(d.start == 4 for d in diags)
    assert any('head_var' in d.message for d in diags)


def test_eof_unclosed_math_reports_tail_column():
    # Math reopened in the tail of a closing line: EOF points at the
    # reopening delimiter, not at the head's backslash.
    result = analysis.analyze_text("\\\nclose \\ tail \\\n")
    unclosed = [d for d in result.diagnostics
                if 'Unclosed math delimiter' in d.message]
    assert unclosed and unclosed[0].start == 13


def test_matrix_row_stray_backslash_does_not_swallow_file():
    result = analysis.analyze_text("*matrix(\n1 \\\n2\n)\n<zach> = 3\n<zach>\n")
    assert result.diagnostics == []


def test_cases_block_is_recognized():
    result = analysis.analyze_text("*cases(\na = 1 \\\nb = 2\n)\n<a> = 3\n<a>\n")
    assert result.diagnostics == []


def test_vec_block_is_recognized():
    result = analysis.analyze_text("*vec(\nx\ny\n)\n<w> = 3\n<w>\n")
    assert result.diagnostics == []


def test_empty_math_warning_still_fires_with_blocks():
    result = analysis.analyze_text("*table(\n\\ \\\n)\n")
    assert any('Empty math' in d.message for d in result.diagnostics)


def test_calc_call_not_flagged_as_unknown_command():
    result = analysis.analyze_text("*calc(\n")
    assert not any('Unknown command' in d.message for d in result.diagnostics)
    assert any(d.severity == 'error' for d in result.diagnostics)


def test_unknown_command_inside_math_warns():
    result = analysis.analyze_text("\\ *boguscmd(x) \\\n")
    assert any('*boguscmd' in d.message and d.severity == 'warning'
               for d in result.diagnostics)


def test_matrix_cells_silent_like_compiler():
    result = analysis.analyze_text("*matrix(*bogus(x) ; 1)\n")
    assert not any('*bogus' in d.message for d in result.diagnostics)


def test_table_cells_warn_like_compiler():
    result = analysis.analyze_text("*table(*bogus(x) | 1)\n")
    assert any('*bogus' in d.message for d in result.diagnostics)


def test_calc_error_in_assignment_becomes_diagnostic():
    result = analysis.analyze_text("<x> = calc(1/0)\n")
    assert any(d.severity == 'error' and 'division by zero' in d.message
               for d in result.diagnostics)


def test_calc_error_value_not_stored_as_truth():
    result = analysis.analyze_text("<x> = calc(1/0)\n")
    assert result.values['x'][1] is None


def test_plot_arity_error():
    result = analysis.analyze_text("*plot(1 ; 2)\n")
    assert any('*plot(...)' in d.message and d.severity == 'error'
               for d in result.diagnostics)


def test_plot_bounds_error():
    result = analysis.analyze_text("*plot(sin(x) ; 2 ; 1)\n")
    assert any('xmin < xmax' in d.message for d in result.diagnostics)


def test_image_arity_error():
    result = analysis.analyze_text("*image(a ; b ; c)\n")
    assert any('*image(...)' in d.message for d in result.diagnostics)


def test_image_empty_path_error():
    result = analysis.analyze_text("*image()\n")
    assert any(d.severity == 'error' for d in result.diagnostics)


def test_image_inside_math_warns():
    result = analysis.analyze_text("\\ *image(a.png) \\\n")
    assert any('text mode' in d.message and d.severity == 'warning'
               for d in result.diagnostics)


def test_unclosed_styling_call_errors():
    result = analysis.analyze_text("*bold(x\n")
    assert any('Unclosed *bold(' in d.message for d in result.diagnostics)


def test_midline_draw_message_not_self_referential():
    result = analysis.analyze_text("text *draw(\n")
    assert not any('draw(...) is only valid inside *draw(...)' in d.message
                   for d in result.diagnostics)


def test_geometry_error_not_duplicated():
    text = "*draw(\n*point(A = 0, 0)\n*point(B = A)\n)\n"
    result = analysis.analyze_text(text)
    diags = [d for d in result.diagnostics if d.severity == 'error']
    assert len(diags) == len(set((d.line, d.start, d.end, d.message) for d in diags))


def test_hover_word_at_end_of_identifier():
    text = "*define(width = 10)\nwidth\n"
    # Cursor exactly at the end of the word (client convention).
    assert analysis.hover(text, 1, len("width")) is not None


def test_vt_nel_does_not_create_phantom_lines():
    # VT (\x0b) is not an LSP line separator; splitlines() would split.
    result = analysis.analyze_text("<a> = 1\x0b<nope> = 2\n<nope> <zzz>\n")
    # No diagnostic on the phantom line; zzz flags on the real line 1.
    diags = [(d.line, d.message) for d in result.diagnostics]
    assert not any('zzz' in m and line != 1 for line, m in diags)
