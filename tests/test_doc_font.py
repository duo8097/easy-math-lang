"""Tests for *doc_font(...) (document font family + size)."""

import os
import sys

import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "src")
)

from compiler import compile_ezmath
from compiler import pipeline as _pipeline


def compile_text(tmp_path, monkeypatch, capsys, text):
    """Compile `text` as .ezmath; return (typ_content, captured_stderr)."""
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


def test_default_header_unchanged(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(tmp_path, monkeypatch, capsys, "Hello\n")
    assert "#set text(size: 12pt)" in typ
    assert "font:" not in typ


def test_family_only(tmp_path, monkeypatch, capsys):
    typ, err = compile_text(
        tmp_path, monkeypatch, capsys, "*doc_font(DejaVu Sans)\nHello\n")
    assert '#set text(font: ("DejaVu Sans",), size: 12pt)' in typ
    assert "*doc_font" not in typ  # consumed control line
    assert "Warning" not in err


def test_family_and_size(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "*doc_font(DejaVu Sans ; 14pt)\nHi\n")
    assert '#set text(font: ("DejaVu Sans",), size: 14pt)' in typ


def test_bare_number_means_points(tmp_path, monkeypatch, capsys):
    typ, _ = compile_text(
        tmp_path, monkeypatch, capsys, "*doc_font(DejaVu Sans ; 14)\nHi\n")
    assert "size: 14pt" in typ


def test_aliases(tmp_path, monkeypatch, capsys):
    for alias in ("doc-font", "docfont"):
        typ, _ = compile_text(
            tmp_path, monkeypatch, capsys, f"*{alias}(DejaVu Sans)\nHi\n")
        assert '#set text(font: ("DejaVu Sans",), size: 12pt)' in typ


def test_comma_in_family_survives(tmp_path, monkeypatch, capsys):
    # Only ';' separates args, so commas stay part of the name... but a
    # comma makes the name invalid, which must warn and keep the default.
    typ, err = compile_text(
        tmp_path, monkeypatch, capsys, "*doc_font(Foo, Bar)\nHi\n")
    assert "#set text(size: 12pt)" in typ
    assert "invalid *doc_font" in err


def test_invalid_family_ignored(tmp_path, monkeypatch, capsys):
    typ, err = compile_text(
        tmp_path, monkeypatch, capsys, "*doc_font(Bad;Font!)\nHi\n")
    assert "#set text(size: 12pt)" in typ
    assert "invalid *doc_font" in err


@pytest.mark.parametrize("size", ["0", "-5", "0pt", "big", "12 px"])
def test_invalid_size_ignored(tmp_path, monkeypatch, capsys, size):
    typ, err = compile_text(
        tmp_path, monkeypatch, capsys, f"*doc_font(DejaVu Sans ; {size})\nHi\n")
    assert "#set text(size: 12pt)" in typ
    assert "invalid *doc_font" in err


def test_empty_uses_default(tmp_path, monkeypatch, capsys):
    typ, err = compile_text(
        tmp_path, monkeypatch, capsys, "*doc_font()\nHi\n")
    assert "#set text(size: 12pt)" in typ
    assert "empty" in err


def test_last_wins(tmp_path, monkeypatch, capsys):
    typ, err = compile_text(
        tmp_path, monkeypatch, capsys,
        "*doc_font(DejaVu Sans)\n*doc_font(Liberation Serif ; 16pt)\nHi\n")
    assert 'font: ("Liberation Serif",), size: 16pt' in typ
    assert "multiple *doc_font" in err


def test_unclosed_warns_and_falls_through(tmp_path, monkeypatch, capsys):
    typ, err = compile_text(
        tmp_path, monkeypatch, capsys, "*doc_font(DejaVu Sans\n")
    assert "unclosed *doc_font" in err
    assert "#set text(size: 12pt)" in typ  # default kept


def test_lsp_consumes_doc_font():
    from lsp import analysis
    result = analysis.analyze_text("*doc_font(DejaVu Sans ; 14pt)\nHi\n")
    assert result.diagnostics == []


def test_lsp_empty_doc_font_warns():
    from lsp import analysis
    result = analysis.analyze_text("*doc_font()\nHi\n")
    assert any(d.severity == 'warning' and 'empty' in d.message
               for d in result.diagnostics)


def test_lsp_completion_and_hover_know_doc_font():
    from lsp import analysis, builtins
    assert 'doc_font' in builtins.KEYWORD_DOCS
    items = analysis.complete("*doc_fo", 0, len("*doc_fo"))
    assert any(i['label'] == 'doc_font' for i in items)


def test_symbol_registry_builds_doc_font():
    from editor.symbol_registry import build_source
    assert build_source('doc-font', {'family': 'DejaVu Sans', 'size': ''}) == \
        '*doc_font(DejaVu Sans)'
    assert build_source('doc-font', {'family': 'DejaVu Sans', 'size': '14pt'}) == \
        '*doc_font(DejaVu Sans ; 14pt)'
    with pytest.raises(ValueError):
        build_source('doc-font', {'family': '', 'size': ''})
