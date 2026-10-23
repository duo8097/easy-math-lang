"""calc() functions: shared whitelist (sin/sqrt/..., pi/e) + old guards."""

import io
import os
import sys
import contextlib

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from compiler import pipeline as _pipeline
from compiler.calc import evaluate_calc
from compiler.state import CompileContext


def _eval(expr, ctx=None):
    ctx = ctx or CompileContext()
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        res = evaluate_calc(ctx, expr, line_no=1)
    return res, err.getvalue()


def _compile(tmp_path, monkeypatch, capsys, text):
    src = tmp_path / "case.ezmath"
    src.write_text(text, encoding="utf-8")
    stub = type(
        "_TypstStub", (), {"compile": staticmethod(lambda *a, **k: None)}
    )()
    monkeypatch.setattr(_pipeline, "typst", stub)
    monkeypatch.setattr(_pipeline, "_typst_import_failed", False)
    ok = _pipeline.compile_ezmath(str(src), str(tmp_path / "case.pdf"))
    captured = capsys.readouterr()
    typ = (tmp_path / "case.typ").read_text(encoding="utf-8")
    return ok, typ, captured.err, captured.out


def test_cbrt_exact_cubes_snap():
    # Some libm builds return 3.0000000000000004 for cbrt(27); the
    # scalar helper snaps exact cubes back to ints. Non-cubes keep
    # full float precision.
    import math as _math
    for expr, want in (("cbrt(27)", "3"), ("cbrt(-8)", "-2"),
                       ("cbrt(64)", "4"), ("cbrt(0)", "0"),
                       ("cbrt(1)", "1")):
        res, err = _eval(expr)
        assert (res, err) == (want, ""), expr
    res, err = _eval("cbrt(2)")
    assert err == ""
    assert float(res) == pytest.approx(_math.cbrt(2))
    assert "." in res  # a normal float, never snapped to int


def test_cbrt_snaps_wobbly_libm(monkeypatch):
    # Simulate a libm that returns 3.0000000000000004 for cbrt(27):
    # calc must still print 3.
    import math as _math
    monkeypatch.setattr(_math, "cbrt", lambda x: 3.0000000000000004)
    res, err = _eval("cbrt(27)")
    assert (res, err) == ("3", "")


def test_functions_exact_ints():
    # Exact results stay ints (4, not 4.0).
    for expr, want in (("sqrt(16)", "4"), ("cbrt(27)", "3"),
                       ("sin(0)", "0"), ("cos(0)", "1"),
                       ("log(100)", "2"), ("ln(e)", "1"),
                       ("exp(0)", "1"), ("abs(0 - 5)", "5"),
                       ("tan(0)", "0")):
        res, err = _eval(expr)
        assert res == want, expr
        assert err == "", expr


def test_full_whitelist_evaluates():
    import math as _math
    cases = {
        'sin': ('sin(1)', _math.sin(1)),
        'cos': ('cos(1)', _math.cos(1)),
        'tan': ('tan(1)', _math.tan(1)),
        'cot': ('cot(1)', 1.0 / _math.tan(1)),
        'sec': ('sec(1)', 1.0 / _math.cos(1)),
        'csc': ('csc(1)', 1.0 / _math.sin(1)),
        'arcsin': ('arcsin(0.5)', _math.asin(0.5)),
        'arccos': ('arccos(0.5)', _math.acos(0.5)),
        'arctan': ('arctan(1)', _math.atan(1)),
        'sinh': ('sinh(1)', _math.sinh(1)),
        'cosh': ('cosh(1)', _math.cosh(1)),
        'tanh': ('tanh(1)', _math.tanh(1)),
        'coth': ('coth(1)', 1.0 / _math.tanh(1)),
        'sqrt': ('sqrt(2)', _math.sqrt(2)),
        'cbrt': ('cbrt(2)', _math.cbrt(2)),
        'log': ('log(3)', _math.log10(3)),
        'ln': ('ln(3)', _math.log(3)),
        'abs': ('abs(0 - 3.5)', 3.5),
        'exp': ('exp(2)', _math.exp(2)),
    }
    assert set(cases) == {'sin', 'cos', 'tan', 'cot', 'sec', 'csc',
                          'arcsin', 'arccos', 'arctan', 'sinh', 'cosh',
                          'tanh', 'coth', 'sqrt', 'cbrt', 'log', 'ln',
                          'abs', 'exp'}
    for name, (expr, want) in cases.items():
        res, err = _eval(expr)
        assert err == "", (name, err)
        assert float(res) == pytest.approx(want), name


def test_pi_and_e():
    import math as _math
    res, err = _eval("pi")
    assert err == "" and float(res) == pytest.approx(_math.pi)
    res, err = _eval("e")
    assert err == "" and float(res) == pytest.approx(_math.e)
    res, err = _eval("2 * pi")
    assert err == "" and float(res) == pytest.approx(2 * _math.pi)
    # *spellings match plots.
    res, err = _eval("*sin(0)")
    assert (res, err) == ("0", "")
    res, err = _eval("*pi")
    assert err == "" and float(res) == pytest.approx(_math.pi)


def test_functions_compose_and_nest():
    res, err = _eval("sqrt(9) + sin(0)")
    assert (res, err) == ("3", "")
    res, err = _eval("sin(calc(0))")
    assert (res, err) == ("0", "")
    res, err = _eval("calc(sqrt(16))")
    assert (res, err) == ("4", "")


def test_variables_inside_functions():
    ctx = CompileContext()
    ctx.variables["a"] = "2"
    res, err = _eval("sqrt(<a> * 8)", ctx)
    assert (res, err) == ("4", "")


def test_bad_function_calls_are_calc_errors():
    for expr in ("foo(1)", "sin(1, 2)", "sqrt()", "sin(1 ; 2)",
                 "sqrt(0 - 1)", "log(0 - 1)", "x", "2*x"):
        res, err = _eval(expr)
        assert res.startswith("[Calc Error"), expr
        assert "[Error]" in err, expr


def test_old_guards_kept():
    res, err = _eval("1/0")
    assert res == "[Calc Error: division by zero]"
    res, err = _eval("9 ** 9 ** 9")
    assert "exponent too large" in res
    res, err = _eval("100,000 + 1")
    assert (res, err) == ("100001", "")
    res, err = _eval("3.5 * 2")
    assert (res, err) == ("7", "")
    res, err = _eval("3,5")
    assert "calc only supports numbers and math operators" in res
    ctx = CompileContext()
    ctx.mult_sym = "."
    res, err = _eval("2 . 3", ctx)
    assert (res, err) == ("6", "")


def test_calc_functions_in_document(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "<a> = 4\ncalc(sqrt(16)) and calc(sin(0)) and <a>.\n",
    )
    assert ok is True
    assert "4 and 0 and 4." in typ
    assert "[Calc Error" not in typ


def test_calc_functions_inside_math_commands(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*frac(calc(sqrt(16)) ; 2)\n"
    )
    assert ok is True
    assert "$frac(4, 2)$" in typ


def test_lookalike_words_not_evaluated(tmp_path, monkeypatch, capsys):
    # Prose merely containing func names is untouched.
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "since 1990, a sine wave\n"
    )
    assert ok is True
    assert "since 1990, a sine wave" in typ
    assert "[Calc Error" not in typ
    assert "unknown command" not in err.lower()
    # *since(x) is an unknown command, not sin.
    ok, typ, err, out = _compile(tmp_path, monkeypatch, capsys, "*since(x)\n")
    assert ok is True
    assert "unknown command *since" in err


def test_plot_mult_before_func_fixed(tmp_path, monkeypatch, capsys):
    # 2*sin(x) used to collapse to 2sin(x) (parse error); the shared
    # preprocessor keeps the multiplication.
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*plot(2*sin(x) ; -5 ; 5)\n"
    )
    assert ok is True
    assert "[Plot Error" not in typ
    assert "#image(" in typ


def test_vec_mult_before_const_fixed(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*vec(2*pi ; 1)\n"
    )
    assert ok is True
    # The preprocessor keeps the multiplication (Typst reads 2pi as 2·pi).
    assert "$vec(2pi, 1)$" in typ
    assert "[Vec Error" not in typ
