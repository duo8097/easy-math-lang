"""Friendly-syntax tests: commas, aliases, let/var, headings/lists, ==."""

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
    compile_ezmath(str(src), str(tmp_path / "case.pdf"))
    typ = (tmp_path / "case.typ").read_text(encoding="utf-8")
    err = capsys.readouterr().err
    return typ, err


def test_comma_separator_frac(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(tmp_path, monkeypatch, capsys, "*frac(2,3)\n")
    assert "$frac(2, 3)$" in typ


def test_comma_separator_pow_sum(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(tmp_path, monkeypatch, capsys, "*pow(x,2)\n")
    assert "$x^(2)$" in typ
    typ, _ = compile_text(tmp_path, monkeypatch, capsys, "*sum(i = 1, n, i)\n")
    assert "sum_(i = 1)" in typ


def test_semicolon_wins_over_comma_for_thousands(tmp_path, monkeypatch, capsys):
    # 100,000 must stay one number when ';' is present.
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "*define(big = 100,000)\nbig\n"
    )
    assert "100,000" in typ


def test_fraction_alias(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(tmp_path, monkeypatch, capsys, "*fraction(2 ; 3)\n")
    assert "$frac(2, 3)$" in typ


def test_power_alias(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(tmp_path, monkeypatch, capsys, "*power(x ; 2)\n")
    assert "$x^(2)$" in typ


def test_cbrt_command(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(tmp_path, monkeypatch, capsys, "*cbrt(x + 1)\n")
    assert "$root(3," in typ


def test_let_assignment(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(tmp_path, monkeypatch, capsys, "let x = 5\nValue <x>\n")
    assert "Value 5" in typ


def test_var_assignment_bare_name(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(tmp_path, monkeypatch, capsys, "var y = 7\nShow <y>\n")
    assert "Show 7" in typ


def test_define_without_parens(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "*define zed = 42\nVal zed\n"
    )
    assert "Val 42" in typ


def test_markdown_heading(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(tmp_path, monkeypatch, capsys, "# My Title\n")
    assert "= My Title" in typ


def test_markdown_subheading(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(tmp_path, monkeypatch, capsys, "## Sub\n")
    assert "== Sub" in typ


def test_bullet_list(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(tmp_path, monkeypatch, capsys, "- item one\n")
    assert "- item one" in typ
    # Must not be escaped to \- .
    assert r"\- item" not in typ


def test_enumeration(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(tmp_path, monkeypatch, capsys, "1. first step\n")
    assert "1. first step" in typ


def test_double_equals_becomes_single(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(tmp_path, monkeypatch, capsys, "a == b\n")
    assert "a = b" in typ
    assert "==" not in typ.replace("===", "")


def test_comma_geometry_line(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys,
        "*draw(\n*point(A = 0, 0)\n*point(B = 4, 0)\n*line(A, B)\n)\n",
    )
    assert 'line("A", "B")' in typ


def test_unknown_command_suggests(tmp_path, monkeypatch, capsys):
    _, err = compile_text(tmp_path, monkeypatch, capsys, "*fract(1 ; 2)\n")
    assert "Did you mean" in err or "unknown command" in err


def compile_real_pdf(tmp_path, text, out_name="case.pdf"):
    """Compile `text` with the real Typst backend; return the PDF path."""
    import pytest as _pytest

    _pytest.importorskip("typst")
    # Bypass the monkeypatched stub: use the real backend directly.
    from compiler import pipeline as _pipe

    src = tmp_path / "case.ezmath"
    src.write_text(text, encoding="utf-8")
    out = tmp_path / out_name
    assert _pipe.compile_ezmath(str(src), str(out)) is True
    assert out.is_file() and out.stat().st_size > 0
    return out


def test_frac_comma_variants_emit_canonical_separator(
    tmp_path, monkeypatch, capsys
):
    for src in ("*frac(3,5)\n", "*frac(3;5)\n"):
        typ, _ = compile_text(tmp_path, monkeypatch, capsys, src)
        assert "$frac(3, 5)$" in typ


def test_thousands_comma_escaped_in_math_output(
    tmp_path, monkeypatch, capsys
):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "*frac(100,000; 7)\n"
    )
    # Bare "100,000" would make Typst read a third argument
    # ("unexpected argument"); the escaped form compiles.
    assert r"100\,000" in typ
    assert "100,000" not in typ.replace(r"100\,000", "")


def test_nested_thousands_comma_escaped(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "*frac(*frac(1,2); 1,000)\n"
    )
    assert r"1\,000" in typ
    assert "frac(1, 2)" in typ


def test_thousands_comma_frac_compiles_to_pdf(tmp_path):
    compile_real_pdf(tmp_path, "*frac(100,000; 7)\n", "frac-big.pdf")


def test_frac_comma_variants_compile_to_pdf(tmp_path):
    compile_real_pdf(tmp_path, "*frac(3,5)\n", "frac-comma.pdf")
    compile_real_pdf(tmp_path, "*frac(3;5)\n", "frac-semi.pdf")


def test_nested_thousands_comma_compiles_to_pdf(tmp_path):
    compile_real_pdf(
        tmp_path, "*frac(*frac(1,2); 1,000)\n", "frac-nested.pdf"
    )


def test_lsp_does_not_flag_thousands_comma():
    from lsp import analysis

    result = analysis.analyze_text("*frac(100,000; 7)\n")
    assert not [d for d in result.diagnostics if d.severity == "error"]


def test_geometry_accepts_thousands_radius():
    import geometry

    out = geometry.parse_draw_block(
        "*point(O = 0, 0)\n*circle(O ; 1,000)"
    )
    assert "radius: 1000.000" in out


def test_geometry_accepts_thousands_distance():
    import geometry

    out = geometry.parse_draw_block(
        "*point(A = 0, 0)\n*point(B)\n*distance(A ; B ; 1,000)"
    )
    assert "must be numeric" not in out
    assert "did not converge" not in out


def test_geometry_rejects_decimal_comma_radius():
    import geometry

    out = geometry.parse_draw_block("*point(O = 0, 0)\n*circle(O ; 3,5)")
    assert "must be numeric" in out


def test_calc_decimal_comma(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "<a> = 3,5\n<b> = calc(<a> * 2)\n<b>\n"
    )
    assert "7 \\" in typ


def test_calc_decimal_comma_fraction(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(tmp_path, monkeypatch, capsys, "calc(0,25 * 4)\n")
    assert "1 \\" in typ


def test_calc_thousands_comma(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(tmp_path, monkeypatch, capsys, "calc(100,000 + 1)\n")
    assert "100001 \\" in typ
    typ, _ = compile_text(tmp_path, monkeypatch, capsys, "calc(1,000 * 2)\n")
    assert "2000 \\" in typ


def test_calc_ambiguous_comma_reads_as_thousands(
    tmp_path, monkeypatch, capsys
):
    # 3,500 matches the thousands pattern (1 digit + exactly 3 digits),
    # so it reads as 3500. Write 3.5 for three-and-a-half.
    typ, _ = compile_text(tmp_path, monkeypatch, capsys, "calc(3,500)\n")
    assert "3500 \\" in typ


def test_calc_mixed_decimal_and_thousands(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "calc(3,5 * 2 + 1,000)\n"
    )
    assert "1007 \\" in typ


def test_calc_decimal_comma_unsupported_keeps_clear_error(
    tmp_path, monkeypatch, capsys
):
    typ, err = compile_text(tmp_path, monkeypatch, capsys, "calc(a, b)\n")
    assert "[Calc Error:" in typ
    assert "Line 1" in err


def test_lsp_calc_decimal_comma_no_error():
    from lsp import analysis

    result = analysis.analyze_text("<a> = 3,5\n<b> = calc(<a> * 2)\n")
    assert not [d for d in result.diagnostics if d.severity == "error"]
