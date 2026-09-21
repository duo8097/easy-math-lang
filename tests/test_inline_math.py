"""Inline math mode (\\ ... \\) tests for easy-math-lang."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from compiler import compile_ezmath
from compiler import pipeline as _pipeline
from lsp import analysis


def compile_text(tmp_path, monkeypatch, capsys, text):
    src = tmp_path / "case.ezmath"
    src.write_text(text, encoding="utf-8")
    _stub = type(
        "_TypstStub", (), {"compile": staticmethod(lambda *a, **k: None)}
    )()
    monkeypatch.setattr(_pipeline, "typst", _stub)
    compile_ezmath(str(src), str(tmp_path / "case.pdf"))
    typ = (tmp_path / "case.typ").read_text(encoding="utf-8")
    err = capsys.readouterr().err
    return typ, err


def test_basic_math(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(tmp_path, monkeypatch, capsys, "\\ x + y \\\n")
    assert "$x + y$" in typ


def test_power_expression(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "\\ a^2 + b^2 = c^2 \\\n"
    )
    assert "$a^2 + b^2 = c^2$" in typ


def test_comparisons(tmp_path, monkeypatch, capsys):
    for src, glyph in [
        ("\\ x <= y \\\n", "≤"),
        ("\\ x >= y \\\n", "≥"),
        ("\\ x != y \\\n", "≠"),
    ]:
        typ, _ = compile_text(tmp_path, monkeypatch, capsys, src)
        assert glyph in typ
        assert "$" in typ
    # === and !== ordering must not regress inside math.
    typ, _ = compile_text(tmp_path, monkeypatch, capsys, "\\ a === b \\\n")
    assert "≡" in typ
    typ, _ = compile_text(tmp_path, monkeypatch, capsys, "\\ a !== b \\\n")
    assert "≢" in typ
    typ, _ = compile_text(tmp_path, monkeypatch, capsys, "\\ x == y \\\n")
    assert "=" in typ


def test_arrows(tmp_path, monkeypatch, capsys):
    for src, glyph in [
        ("\\ x -> y \\\n", "→"),
        ("\\ A <-> B \\\n", "↔"),
        ("\\ x => y \\\n", "⇒"),
    ]:
        typ, _ = compile_text(tmp_path, monkeypatch, capsys, src)
        assert glyph in typ


def test_greek_keywords_inside_math(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "\\ *alpha + *beta = *gamma \\\n"
    )
    assert "α" in typ and "β" in typ and "γ" in typ
    assert "$" in typ


def test_mixed_text_and_math(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "The value of \\ x \\ is positive.\n"
    )
    assert "$x$" in typ
    assert "The value of" in typ


def test_multiple_math_expressions(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "\\ x + y \\ and \\ a + b \\\n"
    )
    assert "$x + y$" in typ
    assert "$a + b$" in typ


def test_multiline_math(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "\\\nx + y = 10\na + b = 20\n\\\n"
    )
    assert "$" in typ
    assert "x + y = 10" in typ
    assert "a + b = 20" in typ


def test_whitespace_trimmed(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(tmp_path, monkeypatch, capsys, "\\   x   \\\n")
    assert "$x$" in typ


def test_escaped_backslash_is_literal(tmp_path, monkeypatch, capsys):
    typ, err = compile_text(tmp_path, monkeypatch, capsys, "a \\\\ b\n")
    assert "$" not in typ  # no math mode opened
    assert "unclosed" not in err.lower()


def test_missing_closing_delimiter(tmp_path, monkeypatch, capsys):
    typ, err = compile_text(tmp_path, monkeypatch, capsys, "\\ x + y\n")
    assert "unclosed" in err.lower()


def test_empty_math_expression(tmp_path, monkeypatch, capsys):
    typ, err = compile_text(tmp_path, monkeypatch, capsys, "\\  \\\n")
    assert "empty" in err.lower()


def test_adjacent_math_expressions(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "\\ x \\ \\ y \\\n"
    )
    assert "$x$" in typ
    assert "$y$" in typ


def test_math_with_existing_syntax(tmp_path, monkeypatch, capsys):
    # Variables and calc work inside math mode.
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "<a> = 5\nSee \\ <a> + 1 \\\n"
    )
    assert "$5 + 1$" in typ
    # Existing math commands still work outside math mode.
    typ, _ = compile_text(tmp_path, monkeypatch, capsys, "*frac(2 ; 3)\n")
    assert "$frac(2, 3)$" in typ


def test_lsp_unclosed_math_diagnostic():
    result = analysis.analyze_text("\\ x + y\n")
    assert any("Unclosed math" in d.message for d in result.diagnostics)


def test_lsp_valid_math_has_no_math_diagnostic():
    result = analysis.analyze_text("See \\ x + y \\ here\n")
    assert not any("Unclosed math" in d.message for d in result.diagnostics)


def test_lsp_multiline_math_no_false_unclosed():
    result = analysis.analyze_text("\\\nx + y\n\\\n")
    assert not any("Unclosed math" in d.message for d in result.diagnostics)


def test_highlighter_math_spans():
    from editor.syntax_highlighter import math_pattern, math_spans

    assert math_pattern().search("\\ x \\")
    assert math_spans("\\ x \\ and \\ y \\") == [(0, 5), (10, 15)]
    assert math_spans("no math") == []
