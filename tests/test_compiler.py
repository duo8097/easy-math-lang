"""Compiler tests for easy-math-lang.

Each test compiles a small .ezmath snippet (Typst compilation is stubbed
out) and asserts on the generated .typ content and/or diagnostics.
"""

import os
import subprocess
import sys

import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "src")
)

from compiler import compile_ezmath


def compile_text(tmp_path, monkeypatch, capsys, text):
    """Compile `text` as .ezmath; return (typ_content, captured_stderr)."""
    src = tmp_path / "case.ezmath"
    src.write_text(text, encoding="utf-8")
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: None
    )
    compile_ezmath(str(src), str(tmp_path / "case.pdf"))
    typ = (tmp_path / "case.typ").read_text(encoding="utf-8")
    err = capsys.readouterr().err
    return typ, err


def test_basic_define(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys,
        "*define(tmp1 = 100 000 000)\ntmp1\n",
    )
    assert "100 000 000" in typ


def test_variable_substitution(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys,
        "<a> = 5\nValue: <a>\n",
    )
    assert "Value: 5" in typ


def test_nested_variables(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys,
        "<a> = 2\n<b> = <a>\nShow <b> here\n",
    )
    assert "Show 2 here" in typ


def test_circular_variable_reference_warns(tmp_path, monkeypatch, capsys):
    typ, err = compile_text(
        tmp_path, monkeypatch, capsys,
        "<a> = <b>\n<b> = <a>\nSee <a>\n",
    )
    assert "Circular variable reference" in err
    # Compilation still finishes instead of hanging.
    assert "See " in typ


def test_undefined_variable(tmp_path, monkeypatch, capsys):
    typ, err = compile_text(
        tmp_path, monkeypatch, capsys, "Need <foo> here\n"
    )
    assert "[Error] Line 1: undefined variable <foo>" in err
    assert "[UNDEFINED:" in typ
    assert "<foo>" not in typ.replace("[UNDEFINED: \\<foo\\>]", "")


def test_calc_basic(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "calc(2 + 3 * 4)\n"
    )
    assert "14 \\" in typ


def test_calc_nested_parentheses(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "calc((2 + 3) * (4 - 1))\n"
    )
    assert "15 \\" in typ


def test_calc_division_by_zero(tmp_path, monkeypatch, capsys):
    typ, err = compile_text(
        tmp_path, monkeypatch, capsys, "calc(1 / 0)\n"
    )
    assert "[Calc Error: division by zero]" in typ
    assert "division by zero" in err


def test_calc_invalid_expression(tmp_path, monkeypatch, capsys):
    typ, err = compile_text(
        tmp_path, monkeypatch, capsys, "calc(foo)\n"
    )
    assert "[Calc Error:" in typ
    assert "Line 1" in err


def test_frac(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "*frac(2 ; 3)\n"
    )
    assert "$frac(2, 3)$" in typ


def test_abs(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "*abs(x - 5)\n"
    )
    assert "$abs(x - 5)$" in typ


def test_sin_cos_tan(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys,
        "*sin(x)\n*cos(x)\n*tan(x)\n",
    )
    assert "$sin(x)$" in typ
    assert "$cos(x)$" in typ
    assert "$tan(x)$" in typ


def test_pow(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "*pow(x ; 2)\n"
    )
    assert "$x^(2)$" in typ


def test_root(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "*root(3 ; x + 1)\n"
    )
    assert "$root(3, {x + 1})$" in typ


def test_sum(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "*sum(i = 1 ; n ; i)\n"
    )
    assert "$display(sum_(i = 1)^(n) (i))$" in typ


def test_prod(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "*prod(i = 1 ; n ; i)\n"
    )
    assert "$display(product_(i = 1)^(n) (i))$" in typ


def test_lim(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "*lim(x -> 0 ; sin(x) / x)\n"
    )
    assert "$lim_(x → 0) (sin(x) / x)$" in typ


def test_nested_math_commands(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "*pow(*frac(1 ; 2) ; 2)\n"
    )
    assert "frac(1, 2)" in typ
    assert "^(2)" in typ
    assert "*frac" not in typ


def test_symbol_shortcuts(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "=> <=> <= >= !=\n"
    )
    for sym in ("⇒", "⇔", "≤", "≥", "≠"):
        assert sym in typ


def test_full_greek_alphabet(tmp_path, monkeypatch, capsys):
    lower = (
        "*alpha *beta *gamma *delta *epsilon *zeta *eta *theta "
        "*iota *kappa *lambda *mu *nu *xi *omicron *pi *rho "
        "*sigma *tau *upsilon *phi *chi *psi *omega\n"
    )
    typ, _ = compile_text(tmp_path, monkeypatch, capsys, lower)
    for glyph in "αβγδεζηθικλμνξορστυφχψω":
        assert glyph in typ
    # *pi renders as Typst math (pre-existing behavior), not a literal.
    assert "$pi$" in typ
    upper = "*Gamma *Delta *Theta *Lambda *Xi *Pi *Sigma *Upsilon *Phi *Psi *Omega\n"
    typ, _ = compile_text(tmp_path, monkeypatch, capsys, upper)
    for glyph in "ΓΔΘΛΞΠΣΥΦΨΩ":
        assert glyph in typ


def test_extended_symbol_keywords(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys,
        "*equiv *sim *ll *gg *prec *succeq *mid *ni\n"
        "*oplus *otimes *circ *bullet *cap *cup *setminus\n"
        "*to *gets *implies *iff *uparrow *downarrow *mapsto\n"
        "*ldots *cdots *vdots *ddots\n"
        "*langle *rangle *lfloor *rfloor *lceil *rceil\n"
        "*partial *nabla *aleph *hbar *ell *Re *Im *prime\n"
        "*square *diamond *top *bot *vdash *dashv *bowtie\n",
    )
    for glyph in ("≡", "∼", "≪", "≫", "≺", "⪰", "∣", "∋",
                  "⊕", "⊗", "∘", "•", "∩", "∪", "∖",
                  "→", "←", "⇒", "⇔", "↑", "↓", "↦",
                  "…", "⋯", "⋮", "⋱",
                  "⟨", "⟩", "⌊", "⌋", "⌈", "⌉",
                  "∂", "∇", "ℵ", "ℏ", "ℓ", "ℜ", "ℑ", "′",
                  "□", "◇", "⊤", "⊥", "⊢", "⊣", "⋈"):
        assert glyph in typ


def test_extended_ascii_symbols(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "A << B >> C === D !== E <== F ==> G |- H -| I\n"
    )
    for sym in ("≪", "≫", "≡", "≢", "⇐", "⇒", "⊢", "⊣"):
        assert sym in typ


def test_symbol_prefix_collisions(tmp_path, monkeypatch, capsys):
    # New short words must not swallow existing longer ones.
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys,
        "*theta *to *tan(x) *tau *notin *ni *alpha\n",
    )
    for glyph in ("θ", "→", "∉", "∋", "α", "τ"):
        assert glyph in typ
    # *tan is a math command, not a bare symbol: left for the math pass.
    assert "$tan(x)$" in typ
    # *infinity renders as Typst math (pre-existing behavior).
    typ, _ = compile_text(tmp_path, monkeypatch, capsys, "*infinity\n")
    assert "$infinity$" in typ


def test_typst_escaping(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys,
        "my_file costs #1 for 5 * 3 listen https://example.com/x see a/b\n",
    )
    assert "my\\_file" in typ
    assert "\\#1" in typ
    assert "\\*" in typ
    # URL and path survive comment stripping; '/' is escaped for Typst.
    assert "example.com" in typ
    assert "a\\/b" in typ


def test_p_command(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "*p(frac(2; 3))\n"
    )
    assert "frac(2; 3)" in typ
    assert "$frac" not in typ


def test_multiline_draw(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys,
        "*draw(\n*triangle(A ; B ; C)\n)\n",
    )
    assert "cetz" in typ
    assert 'line("A", "B", "C", close: true)' in typ


def test_single_line_draw(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "*draw(*triangle(A ; B ; C))\n"
    )
    assert "cetz" in typ
    assert 'line("A", "B", "C", close: true)' in typ


def test_unknown_command_warning(tmp_path, monkeypatch, capsys):
    _, err = compile_text(
        tmp_path, monkeypatch, capsys, "*foobar(1 ; 2)\n"
    )
    assert "Line 1" in err
    assert "*foobar" in err


def test_error_locations_for_undefined_and_calc(
    tmp_path, monkeypatch, capsys
):
    _, err = compile_text(
        tmp_path, monkeypatch, capsys,
        "ok line\nUse <missing> here\ncalc(1 / 0)\n",
    )
    assert "[Error] Line 2: undefined variable <missing>" in err
    assert "[Error] Line 3:" in err
