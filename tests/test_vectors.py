"""Tests for *vec(...) vector diagrams (NumPy + Matplotlib -> SVG -> Typst).

Same backend as *plot: numerical evaluation, Matplotlib Agg rendering to
``<stem>-vec-<n>.svg`` next to the .typ, embedded as ``#image``.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from compiler import pipeline as _pipeline  # noqa: E402
from compiler import vectors as _vecs  # noqa: E402
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


def _svg(tmp_path, n=1):
    return tmp_path / f"doc-vec-{n}.svg"


# ----------------------------------------------------------------------
# Happy paths
# ----------------------------------------------------------------------

def test_vec_basic(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys, "*vec(3 ; 4)\n")
    assert ok is True, err.err
    svg = _svg(tmp_path)
    assert svg.is_file()
    assert '#image("doc-vec-1.svg"' in typ
    assert "$vec(" not in typ
    assert "arrow(" not in typ


def test_vec_comma_syntax(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys, "*vec(3, 4)\n")
    assert ok is True, err.err
    assert _svg(tmp_path).is_file()
    assert '#image("doc-vec-1.svg"' in typ


def test_vec_thousands_comma_kept(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(
        tmp_path, monkeypatch, capsys, "*vec(100,000 ; 2)\n")
    assert ok is True, err.err
    assert _svg(tmp_path).is_file()
    assert '#image("doc-vec-1.svg"' in typ


def test_vec_variables_and_calc(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(
        tmp_path, monkeypatch, capsys,
        "<a> = 2\n*vec(<a> ; calc(<a> * 3))\n")
    assert ok is True, err.err
    assert _svg(tmp_path).is_file()
    assert '#image("doc-vec-1.svg"' in typ


def test_vec_math_function_components(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(
        tmp_path, monkeypatch, capsys, "*vec(*sin(0) ; *sqrt(4))\n")
    assert ok is True, err.err
    assert _svg(tmp_path).is_file()


def test_vec_negative_and_zero(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(
        tmp_path, monkeypatch, capsys, "*vec(-2 ; -5)\n")
    assert ok is True, err.err
    assert _svg(tmp_path, 1).is_file()
    ok, typ, err = _compile(
        tmp_path, monkeypatch, capsys, "*vec(0 ; 0)\n")
    assert ok is True, err.err


def test_vec_multiple_numbering(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(
        tmp_path, monkeypatch, capsys, "*vec(3 ; 4)\n*vec(-2 ; 5)\n")
    assert ok is True, err.err
    assert _svg(tmp_path, 1).is_file()
    assert _svg(tmp_path, 2).is_file()
    assert '#image("doc-vec-1.svg"' in typ
    assert '#image("doc-vec-2.svg"' in typ


def test_vec_and_plot_counters_independent(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(
        tmp_path, monkeypatch, capsys,
        "*plot(x ; -5 ; 5)\n*vec(3 ; 4)\n")
    assert ok is True, err.err
    assert (tmp_path / "doc-plot-1.svg").is_file()
    assert (tmp_path / "doc-vec-1.svg").is_file()
    assert '#image("doc-plot-1.svg"' in typ
    assert '#image("doc-vec-1.svg"' in typ


# ----------------------------------------------------------------------
# SVG content (structural only — never image comparison)
# ----------------------------------------------------------------------

def test_vec_svg_is_svg_with_text(tmp_path, monkeypatch, capsys):
    ok, _, err = _compile(tmp_path, monkeypatch, capsys, "*vec(3 ; 4)\n")
    assert ok is True, err.err
    content = _svg(tmp_path).read_text(encoding="utf-8")
    assert "<svg" in content
    # svg.fonttype == "none": labels stay <text>, not paths.
    assert "<text" in content


def test_vec_typ_references_relative_svg(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys, "*vec(3 ; 4)\n")
    assert ok is True, err.err
    assert '#image("doc-vec-1.svg", width: 80%)' in typ
    assert "/tmp" not in typ and tmp_path.name not in typ.replace(
        "doc-vec-1.svg", "")


def test_vec_svg_sidecar_copied_for_typ_export(tmp_path, monkeypatch,
                                               capsys):
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
    assert (srcdir / "doc-vec-1.svg").is_file()
    assert (dstdir / "doc-vec-1.svg").is_file()


# ----------------------------------------------------------------------
# Error handling (build continues, diagnostic on stderr + inline)
# ----------------------------------------------------------------------

def test_vec_wrong_arity_is_error(tmp_path, monkeypatch, capsys):
    for text in ("*vec(3)\n", "*vec(1 ; 2 ; 3)\n",
                 "*vec(1 ; 2 ; 3 ; 4 ; 5)\n", "*vec()\n"):
        ok, typ, err = _compile(tmp_path, monkeypatch, capsys, text)
        assert ok is True, text
        assert "Vec Error" in typ, text
        assert "needs 2 arguments" in err.err, text
        assert '#image("doc-vec-' not in typ, text


def test_vec_symbolic_components_are_error(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys, "*vec(x ; y)\n")
    assert ok is True
    assert "Vec Error" in typ
    assert "invalid components" in err.err
    assert not _svg(tmp_path).exists()


def test_vec_unknown_name_is_error(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys, "*vec(a ; b)\n")
    assert ok is True
    assert "Vec Error" in typ
    assert "unknown name" in err.err
    assert not _svg(tmp_path).exists()


def test_vec_empty_component_is_error(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys, "*vec(1 ; )\n")
    assert ok is True
    assert "Vec Error" in typ
    assert "numeric x and y" in err.err
    assert not _svg(tmp_path).exists()


def test_vec_nonfinite_is_error(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys, "*vec(1/0 ; 2)\n")
    assert ok is True
    assert "Vec Error" in typ
    assert not _svg(tmp_path).exists()


def test_vec_unclosed_parenthesis(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys, "*vec(3 ; 4\n")
    assert ok is True
    assert "unclosed *vec" in err.err
    assert "#image(" not in typ
    assert not _svg(tmp_path).exists()


def test_vec_in_inline_math_warns(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(
        tmp_path, monkeypatch, capsys, "\\ v = *vec(3 ; 4) \\\n")
    assert ok is True
    assert "text mode" in err.err
    assert "*vec" in typ
    assert "#image(" not in typ
    assert not _svg(tmp_path).exists()


def test_vec_in_matrix_warns(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(
        tmp_path, monkeypatch, capsys, "*matrix(*vec(3 ; 4) ; 2 | 3 ; 4)\n")
    assert ok is True
    assert "text mode" in err.err


# ----------------------------------------------------------------------
# Unit-level evaluation checks
# ----------------------------------------------------------------------

def test_vec_evaluate_operators_and_consts():
    ctx = CompileContext()
    assert _vecs.evaluate_vec_component(ctx, "1+2*3") == pytest.approx(7.0)
    assert _vecs.evaluate_vec_component(ctx, "2^3") == pytest.approx(8.0)
    assert _vecs.evaluate_vec_component(ctx, "100,000") == pytest.approx(100000.0)
    assert _vecs.evaluate_vec_component(ctx, "sin(pi)") == pytest.approx(0.0, abs=1e-12)
    assert _vecs.evaluate_vec_component(ctx, "-2.5") == pytest.approx(-2.5)


def test_vec_evaluate_rejects_raw_eval_vectors():
    ctx = CompileContext()
    with pytest.raises(ValueError):
        _vecs.evaluate_vec_component(ctx, "__import__('os').system('x')")
    with pytest.raises(ValueError):
        _vecs.evaluate_vec_component(ctx, "x")
    with pytest.raises(ValueError):
        _vecs.evaluate_vec_component(ctx, "foo(1)")
    with pytest.raises(ValueError):
        _vecs.evaluate_vec_component(ctx, "1/0")


def test_vec_filename():
    assert _vecs.vec_filename("doc", 1) == "doc-vec-1.svg"
    assert _vecs.vec_filename("doc", 12) == "doc-vec-12.svg"


def test_vec_render_writes_svg(tmp_path):
    ctx = CompileContext()
    out = tmp_path / "t-vec-1.svg"
    label = _vecs.render_vec_svg(ctx, 3.0, 4.0, str(out))
    assert out.is_file()
    assert label == "vec(3, 4)"
    content = out.read_text(encoding="utf-8")
    assert "<svg" in content


def test_vec_render_zero_vector(tmp_path):
    ctx = CompileContext()
    out = tmp_path / "t-vec-0.svg"
    _vecs.render_vec_svg(ctx, 0.0, 0.0, str(out))
    assert out.is_file()


def test_vec_render_nonfinite_rejected(tmp_path):
    ctx = CompileContext()
    with pytest.raises(ValueError):
        _vecs.render_vec_svg(ctx, float("inf"), 1.0, str(tmp_path / "x.svg"))


# ----------------------------------------------------------------------
# Symbol palette (Insert Vec dialog)
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
    assert _svg(tmp_path).is_file()
    assert '#image("doc-vec-1.svg"' in typ


def test_vec_real_pdf_compile(tmp_path):
    """Real Typst compile (no stub) for a vector diagram."""
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
        assert os.path.isfile(os.path.join(work, "v-vec-1.svg"))
    finally:
        shutil.rmtree(work, ignore_errors=True)
        # Never leave .typ/.pdf in the repo: workdir is a temp dir.
