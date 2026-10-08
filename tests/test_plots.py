"""Tests for *plot(...) function plots (NumPy + Matplotlib -> SVG -> Typst)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from compiler import pipeline as _pipeline  # noqa: E402
from compiler import plots as _plots  # noqa: E402
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
    return tmp_path / f"doc-plot-{n}.svg"


# ----------------------------------------------------------------------
# Happy paths
# ----------------------------------------------------------------------

def test_plot_polynomial(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys,
                            "*plot(x^2; -5; 5)\n")
    assert ok is True, err.err
    svg = _svg(tmp_path)
    assert svg.is_file()
    assert '#image("doc-plot-1.svg"' in typ


def test_plot_trigonometric(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys,
                            "*plot(sin(x); -10; 10)\n")
    assert ok is True, err.err
    assert _svg(tmp_path).is_file()
    assert '#image("doc-plot-1.svg"' in typ


def test_plot_negative_decimal_bounds(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys,
                            "*plot(x; -2.5; 2.5)\n")
    assert ok is True, err.err
    assert _svg(tmp_path).is_file()


def test_plot_comma_syntax(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys,
                            "*plot(x^2, -5, 5)\n")
    assert ok is True, err.err
    assert _svg(tmp_path).is_file()


def test_plot_variable_bounds(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys,
                            "<a> = 5\n*plot(x; -<a>; <a>)\n")
    assert ok is True, err.err
    assert _svg(tmp_path).is_file()


def test_plot_multiple_numbering(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys,
                            "*plot(x; -5; 5)\n*plot(x^2; -5; 5)\n")
    assert ok is True, err.err
    assert _svg(tmp_path, 1).is_file()
    assert _svg(tmp_path, 2).is_file()
    assert '#image("doc-plot-1.svg"' in typ
    assert '#image("doc-plot-2.svg"' in typ


# ----------------------------------------------------------------------
# SVG content (structural only — never image comparison)
# ----------------------------------------------------------------------

def test_plot_svg_is_svg_with_text(tmp_path, monkeypatch, capsys):
    ok, _, err = _compile(tmp_path, monkeypatch, capsys,
                          "*plot(x^2; -5; 5)\n")
    assert ok is True, err.err
    content = _svg(tmp_path).read_text(encoding="utf-8")
    assert "<svg" in content
    # svg.fonttype == "none": labels stay <text>, not paths.
    assert "<text" in content


def test_plot_typ_references_relative_svg(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys,
                            "*plot(x^2; -5; 5)\n")
    assert ok is True, err.err
    assert '#image("doc-plot-1.svg", width: 80%)' in typ
    assert "/tmp" not in typ and tmp_path.name not in typ.replace(
        "doc-plot-1.svg", "")


# ----------------------------------------------------------------------
# Discontinuities
# ----------------------------------------------------------------------

def test_plot_discontinuity_compiles(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys,
                            "*plot(1/x; -10; 10)\n")
    assert ok is True, err.err
    assert _svg(tmp_path).is_file()
    assert '#image("doc-plot-1.svg"' in typ


def test_plot_segments_break_across_discontinuity():
    import numpy as _np
    ctx = CompileContext()
    xs = _np.linspace(-10, 10, 1000)
    ys = _plots.evaluate_on_grid(ctx, "1/x", xs)
    segments = _plots.split_plot_segments(xs, ys)
    assert len(segments) > 1
    # No single segment spans from negative to positive x.
    for sx, _sy in segments:
        assert not (float(sx[0]) < 0 < float(sx[-1]))


def test_plot_no_finite_values_is_error(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys,
                            "*plot(sqrt(x); -10; -1)\n")
    assert ok is True  # build continues with an inline error
    assert "Plot Error" in typ
    assert "no finite values" in err.err
    assert not _svg(tmp_path).exists()


# ----------------------------------------------------------------------
# Error handling (build continues, diagnostic on stderr + inline)
# ----------------------------------------------------------------------

def test_plot_missing_expression(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys,
                            "*plot(; -5; 5)\n")
    assert ok is True
    assert "Plot Error" in typ
    assert "expression" in err.err
    assert not _svg(tmp_path).exists()


def test_plot_missing_bounds(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys,
                            "*plot(x^2; 5)\n")
    assert ok is True
    assert "Plot Error" in typ
    assert "3 arguments" in err.err
    assert not _svg(tmp_path).exists()


def test_plot_non_numeric_bounds(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys,
                            "*plot(x; a; b)\n")
    assert ok is True
    assert "Plot Error" in typ
    assert "bounds" in err.err
    assert not _svg(tmp_path).exists()


def test_plot_xmin_gte_xmax(tmp_path, monkeypatch, capsys):
    for bounds in ("5; -5", "3; 3"):
        ok, typ, err = _compile(tmp_path, monkeypatch, capsys,
                                f"*plot(x; {bounds})\n")
        assert ok is True
        assert "Plot Error" in typ
        assert "xmin < xmax" in err.err


def test_plot_unsupported_function(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys,
                            "*plot(foo(x); -5; 5)\n")
    assert ok is True
    assert "Plot Error" in typ
    assert "unsupported function" in err.err
    assert not _svg(tmp_path).exists()


def test_plot_unknown_name(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys,
                            "*plot(y^2; -5; 5)\n")
    assert ok is True
    assert "Plot Error" in typ
    assert "unknown name" in err.err


def test_plot_unclosed_parenthesis(tmp_path, monkeypatch, capsys):
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys,
                            "*plot(x^2; -5; 5\n")
    assert ok is True
    assert "unclosed *plot" in err.err


# ----------------------------------------------------------------------
# Unit-level evaluation checks
# ----------------------------------------------------------------------

def test_plot_evaluate_operators_and_consts():
    import numpy as _np
    ctx = CompileContext()
    xs = _np.array([0.0, 1.0, 2.0])
    out = _plots.evaluate_on_grid(ctx, "x^2 + 2*x + 1", xs)
    assert list(out) == pytest.approx([1.0, 4.0, 9.0])
    out = _plots.evaluate_on_grid(ctx, "sin(pi)", xs)
    assert float(out[0]) == pytest.approx(0.0, abs=1e-12)
    out = _plots.evaluate_on_grid(ctx, "5", xs)
    assert list(out) == [5.0, 5.0, 5.0]


def test_plot_evaluate_rejects_raw_eval_vectors():
    import numpy as _np
    ctx = CompileContext()
    xs = _np.array([1.0])
    with pytest.raises(ValueError):
        _plots.evaluate_on_grid(ctx, "__import__('os').system('x')", xs)
    with pytest.raises(ValueError):
        _plots.evaluate_on_grid(ctx, "x(1)", xs)


# ----------------------------------------------------------------------
# Symbol palette (Insert Plot dialog)
# ----------------------------------------------------------------------

def test_plot_palette_builds_source():
    from editor.symbol_registry import build_source, get_symbol
    sym = get_symbol("plot")
    assert sym.requires_dialog is True
    assert sym.command == "plot"
    assert sym.category == "Math"
    assert build_source(
        "plot", {"expression": "x^2", "xmin": "-5", "xmax": "5"}
    ) == "*plot(x^2 ; -5 ; 5)"


def test_plot_palette_requires_all_fields():
    from editor.symbol_registry import get_symbol, validate_fields
    sym = get_symbol("plot")
    assert validate_fields(
        sym, {"expression": "", "xmin": "-5", "xmax": "5"}) != []
    assert validate_fields(
        sym, {"expression": "x", "xmin": "", "xmax": "5"}) != []
    assert validate_fields(
        sym, {"expression": "x", "xmin": "-5", "xmax": "5"}) == []


def test_plot_palette_source_compiles(tmp_path, monkeypatch, capsys):
    from editor.symbol_registry import build_source
    src = build_source("plot", {"expression": "sin(x)",
                                "xmin": "-10", "xmax": "10"}) + "\n"
    ok, typ, err = _compile(tmp_path, monkeypatch, capsys, src)
    assert ok is True, err.err
    assert _svg(tmp_path).is_file()
    assert '#image("doc-plot-1.svg"' in typ
