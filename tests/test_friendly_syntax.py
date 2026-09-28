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
