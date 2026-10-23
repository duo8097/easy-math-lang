"""Tests for *vec(...) — math-mode column vectors (Typst ``vec(...)``).

*vec(a ; b [; c ...]) emits ``$vec(a, b, ...)$``. Components use the
same friendly splitting and math conversion as *matrix/*det cells, so
variables, calc(), nested commands, ``\\ ... \\`` math and *matrix
cells all work. Fewer than 2 components, empty components or an
unclosed call warn and leave the source as-is.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from compiler import pipeline as _pipeline  # noqa: E402
from compiler.math_commands import replace_vec_calls  # noqa: E402
from compiler.state import CompileContext  # noqa: E402


def _compile(tmp_path, monkeypatch, capsys, text, out_name="doc.pdf",
             **kw):
    from compiler import compile_ezmath
    src = tmp_path / "doc.ezmath"
    src.write_text(text, encoding="utf-8")

    def _fake_compile(typ_file, out_file, **kwargs):
        parent = os.path.dirname(os.path.abspath(out_file))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as h:
            h.write("fake")
        return None

    stub = type("_TypstStub", (), {"compile": staticmethod(_fake_compile)})()
    monkeypatch.setattr(_pipeline, "typst", stub)
    out = tmp_path / out_name
    ok = compile_ezmath(str(src), str(out), **kw)
    typ = (tmp_path / "doc.typ").read_text(encoding="utf-8")
    err = capsys.readouterr()
    return ok, typ, err


# ----------------------------------------------------------------------
# Happy paths
# ----------------------------------------------------------------------

def test_vec_basic(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys, "*vec(3 ; 4)\n")
    assert ok is True, err.err
    assert "$vec(3, 4)$" in typ
    # No diagram sidecar is written anymore.
    assert not list(tmp_path.glob("doc-vec-*.svg"))
    assert "#image(" not in typ


def test_vec_comma_syntax(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys, "*vec(3, 4)\n")
    assert ok is True, err.err
    assert "$vec(3, 4)$" in typ


def test_vec_thousands_comma_kept(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(
        tmp_path, monkeypatch, capsys, "*vec(100,000 ; 2)\n")
    assert ok is True, err.err
    # Friendly comma is escaped as a thin space inside the component.
    assert "100\\,000" in typ
    assert "$vec(100\\,000, 2)$" in typ


def test_vec_variables_and_calc(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(
        tmp_path, monkeypatch, capsys,
        "<a> = 2\n*vec(<a> ; calc(<a> * 3))\n")
    assert ok is True, err.err
    assert "$vec(2, 6)$" in typ


def test_vec_math_function_components(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(
        tmp_path, monkeypatch, capsys, "*vec(*sin(0) ; *sqrt(4))\n")
    assert ok is True, err.err
    assert "$vec(" in typ


def test_vec_nested_command_component(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(
        tmp_path, monkeypatch, capsys, "*vec(*frac(1 ; 2) ; 3)\n")
    assert ok is True, err.err
    assert "$vec(frac(1, 2), 3)$" in typ


def test_vec_variables_work(tmp_path, monkeypatch, capsys):
    # Symbolic components are fine now (unlike the old diagram backend).
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys, "*vec(a ; b)\n")
    assert ok is True, err.err
    assert "$vec(a, b)$" in typ


def test_vec_three_components(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(
        tmp_path, monkeypatch, capsys, "*vec(1 ; 2 ; 3)\n")
    assert ok is True, err.err
    assert "$vec(1, 2, 3)$" in typ


def test_vec_multiple_vectors(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(
        tmp_path, monkeypatch, capsys, "*vec(3 ; 4)\n*vec(-2 ; 5)\n")
    assert ok is True, err.err
    assert "$vec(3, 4)$" in typ
    assert "$vec(-2, 5)$" in typ


def test_vec_no_sidecars_next_to_plot(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(
        tmp_path, monkeypatch, capsys,
        "*plot(x ; -5 ; 5)\n*vec(3 ; 4)\n")
    assert ok is True, err.err
    assert (tmp_path / "doc-plot-1.svg").is_file()
    assert '#image("doc-plot-1.svg"' in typ
    # *vec emits math, not a diagram.
    assert "$vec(3, 4)$" in typ
    assert not list(tmp_path.glob("doc-vec-*.svg"))


def test_vec_in_inline_math(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(
        tmp_path, monkeypatch, capsys, "\\ v = *vec(3 ; 4) \\\n")
    assert ok is True, err.err
    assert "$v = vec(3, 4)$" in typ
    # No "text mode" warning anymore.
    assert "text mode" not in err.err


def test_vec_in_matrix(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(
        tmp_path, monkeypatch, capsys,
        "*matrix(*vec(1 ; 2) ; 3 | 4 ; 5)\n")
    assert ok is True, err.err
    assert "$mat(vec(1, 2), 3; 4, 5)$" in typ
    assert "text mode" not in err.err


def test_vec_block_form(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(
        tmp_path, monkeypatch, capsys, "*vec(\n  1\n  2\n)\n")
    assert ok is True, err.err
    assert "$vec(1, 2)$" in typ


def test_vec_export_typ_leaves_no_sidecars(tmp_path, monkeypatch, capsys):
    from compiler import compile_ezmath
    srcdir = tmp_path / "a"
    dstdir = tmp_path / "b"
    srcdir.mkdir()
    src = srcdir / "doc.ezmath"
    src.write_text("*vec(3 ; 4)\n", encoding="utf-8")

    def _fake_compile(typ_file, out_file, **kwargs):
        parent = os.path.dirname(os.path.abspath(out_file))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as h:
            h.write("fake")
        return None

    stub = type("_TypstStub", (), {"compile": staticmethod(_fake_compile)})()
    monkeypatch.setattr(_pipeline, "typst", stub)
    ok = compile_ezmath(str(src), str(dstdir / "doc.typ"), format="typ")
    capsys.readouterr()
    assert ok is True
    assert not list(srcdir.glob("doc-vec-*.svg"))
    assert not list(dstdir.glob("doc-vec-*.svg"))


# ----------------------------------------------------------------------
# Error handling (build continues, warning on stderr, source kept as-is)
# ----------------------------------------------------------------------

def test_vec_too_few_components_warns(tmp_path, monkeypatch, capsys):
    for text in ("*vec(3)\n", "*vec()\n"):
        ok, typ, err = _compile(tmp_path, monkeypatch, capsys, text)
        assert ok is True, text
        assert "expects at least 2 components" in err.err, text
        assert "Line 1" in err.err, text
        assert "$vec(" not in typ, text


def test_vec_empty_component_warns(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys, "*vec(1 ; )\n")
    assert ok is True
    assert "empty component(s)" in err.err
    assert "Line 1" in err.err
    assert "$vec(" not in typ


def test_vec_unclosed_parenthesis_warns(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys, "*vec(3 ; 4\n")
    assert ok is True
    assert "unclosed *vec" in err.err
    assert "$vec(" not in typ


# ----------------------------------------------------------------------
# Unit-level: replace_vec_calls
# ----------------------------------------------------------------------

def test_replace_vec_calls_basic():
    ctx = CompileContext()
    assert replace_vec_calls("*vec(3 ; 4)", ctx) == "$vec(3, 4)$"
    assert replace_vec_calls("*vec(3, 4)", ctx) == "$vec(3, 4)$"
    assert replace_vec_calls("*vec(1 ; 2 ; 3)", ctx) == "$vec(1, 2, 3)$"


def test_replace_vec_calls_line_number_in_warning(capsys):
    ctx = CompileContext()
    replace_vec_calls("*vec(1)", ctx, line_no=7)
    err = capsys.readouterr()
    assert "Line 7" in err.err
    assert "at least 2 components" in err.err


def test_replace_vec_calls_leaves_text_alone():
    ctx = CompileContext()
    text = "the vector *vec is mentioned, no call here"
    assert replace_vec_calls(text, ctx) == text


def test_replace_vec_calls_multiple_calls():
    ctx = CompileContext()
    out = replace_vec_calls("*vec(1 ; 2) and *vec(3 ; 4)", ctx)
    assert out == "$vec(1, 2)$ and $vec(3, 4)$"


# ----------------------------------------------------------------------
# LSP builtins (completion / hover)
# ----------------------------------------------------------------------

def test_vec_lsp_builtin_present():
    from lsp import builtins
    doc = builtins.MATH_DOCS['vec'][0]
    assert doc.startswith("*vec(")
    assert "column vector" in builtins.MATH_DOCS['vec'][1].lower()


def test_vec_lsp_completion_and_hover():
    from lsp import analysis
    items = analysis.complete("*v\n", 0, 2)
    labels = [item['label'] for item in items]
    assert 'vec' in labels
    found = analysis.hover("*vec(3 ; 4)\n", 0, 2)
    assert found is not None
    assert 'vec' in found['value']


# ----------------------------------------------------------------------
# Symbol palette (Insert Vector dialog)
# ----------------------------------------------------------------------

def test_vec_palette_builds_source():
    from editor.symbol_registry import build_source, get_symbol
    sym = get_symbol("vec")
    assert sym.requires_dialog is True
    assert sym.command == "vec"
    assert sym.category == "Math"
    assert build_source("vec", {"x1": "3", "x2": "4"}) == "*vec(3 ; 4)"


def test_vec_palette_requires_both_fields():
    from editor.symbol_registry import get_symbol, validate_fields
    sym = get_symbol("vec")
    assert validate_fields(sym, {"x1": "", "x2": "4"}) != []
    assert validate_fields(sym, {"x1": "3", "x2": ""}) != []
    assert validate_fields(sym, {"x1": "3", "x2": "4"}) == []


def test_vec_palette_source_compiles(tmp_path, monkeypatch, capsys):
    from editor.symbol_registry import build_source
    src = build_source("vec", {"x1": "3", "x2": "4"}) + "\n"
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys, src)
    assert ok is True, err.err
    assert "$vec(3, 4)$" in typ


def test_vec_real_pdf_compile(tmp_path):
    """Real Typst compile (no stub) for a column vector."""
    pytest.importorskip("typst")
    import shutil
    import tempfile
    from compiler.pipeline import compile_ezmath
    work = tempfile.mkdtemp(prefix="easymath-vec-")
    try:
        src = os.path.join(work, "v.ezmath")
        out = os.path.join(work, "v.pdf")
        with open(src, "w", encoding="utf-8") as f:
            f.write("*vec(3 ; 4)\n")
        assert compile_ezmath(src, out) is True
        assert os.path.isfile(out)
        # No SVG diagram sidecar is produced.
        assert not os.path.isfile(os.path.join(work, "v-vec-1.svg"))
    finally:
        shutil.rmtree(work, ignore_errors=True)
        # Never leave .typ/.pdf in the repo: workdir is a temp dir.
