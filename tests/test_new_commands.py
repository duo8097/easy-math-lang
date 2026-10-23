"""New math commands: integrals, cases, vectors, binomials, trig."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from compiler import pipeline as _pipeline


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


def test_int_indefinite(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(tmp_path, monkeypatch, capsys, "*int(x^2)\n")
    assert ok is True
    assert "$integral x^2$" in typ
    assert "unknown command" not in err.lower()


def test_int_definite_with_dif(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*int(0 ; 1 ; x^2 ; x)\n"
    )
    assert ok is True
    assert "$integral_(0)^(1) x^2 dif x$" in typ


def test_int_comma_separators(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*int(0, 1, x^2)\n"
    )
    assert ok is True
    assert "$integral_(0)^(1) x^2$" in typ


def test_oint_contour(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*oint(C ; F ; l)\n"
    )
    assert ok is True
    assert "integral.cont" in typ


def test_cases_two_rows(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*cases(x + y = 3 | x - y = 1)\n"
    )
    assert ok is True
    assert "$cases(x + y = 3, x - y = 1)$" in typ


def test_cases_block_form(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "*cases(\n    x + y = 3\n    x - y = 1\n)\n",
    )
    assert ok is True
    assert "$cases(x + y = 3, x - y = 1)$" in typ


def test_cases_semicolon_cells_piecewise(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "*cases(x ; x > 0 | 0 ; x <= 0)\n",
    )
    assert ok is True
    assert "$cases(x & x > 0, 0 & x ≤ 0)$" in typ
    assert "unknown command" not in err.lower()


def test_cases_cells_comma_friendly(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "*cases(x, x > 0 | 0, x <= 0)\n",
    )
    assert ok is True
    assert "$cases(x & x > 0, 0 & x ≤ 0)$" in typ


def test_cases_mixed_single_and_double_cells(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "*cases(x ; x > 0 | 0)\n",
    )
    assert ok is True
    assert "$cases(x & x > 0, 0)$" in typ


def test_cases_block_form_with_cells(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "*cases(\n    x ; x > 0\n    0 ; x <= 0\n)\n",
    )
    assert ok is True
    assert "$cases(x & x > 0, 0 & x ≤ 0)$" in typ


def test_cases_piecewise_real_pdf():
    """Real Typst compile for the piecewise repro (no stub)."""
    import pytest as _pytest
    _pytest.importorskip("typst")
    import shutil
    import tempfile
    from compiler.pipeline import compile_ezmath
    work = tempfile.mkdtemp(prefix="easymath-cases-")
    try:
        src = os.path.join(work, "pw.ezmath")
        out = os.path.join(work, "pw.pdf")
        with open(src, "w", encoding="utf-8") as f:
            f.write("*cases(x ; x > 0 | 0 ; x <= 0)\n")
        assert compile_ezmath(src, out) is True
        assert os.path.isfile(out)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_vec_column_vector(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(tmp_path, monkeypatch, capsys, "*vec(3 ; 4)\n")
    assert ok is True
    assert "$vec(3, 4)$" in typ
    assert not list(tmp_path.glob("case-vec-*.svg"))
    assert "#image(" not in typ


def test_vec_comma_and_thousands(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(tmp_path, monkeypatch, capsys, "*vec(3, 4)\n")
    assert ok is True
    assert "$vec(3, 4)$" in typ
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*vec(100,000 ; 2)\n"
    )
    assert ok is True
    assert "100\\,000" in typ


def test_vec_variables_and_calc(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "<a> = 2\n*vec(<a> ; calc(<a> * 3))\n",
    )
    assert ok is True
    assert "$vec(2, 6)$" in typ


def test_vec_too_few_components_warns(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(tmp_path, monkeypatch, capsys, "*vec(3)\n")
    assert ok is True
    assert "at least 2 components" in err
    assert "$vec(" not in typ


def test_vec_three_components_ok(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*vec(x ; y ; z)\n"
    )
    assert ok is True
    assert "$vec(x, y, z)$" in typ
    assert "#image(" not in typ


def test_vec_unclosed_warns(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*vec(3 ; 4\n"
    )
    assert "[Warning] Line 1: unclosed *vec(... — missing closing parenthesis" in err
    assert "#image(" not in typ


def test_vec_inline_math_ok(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "\\ v = *vec(3 ; 4) \\\n"
    )
    assert ok is True
    assert "text mode" not in err
    assert "$v = vec(3, 4)$" in typ
    assert "#image(" not in typ


def test_binom(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*binom(n ; k)\n"
    )
    assert ok is True
    assert "$binom(n, k)$" in typ


def test_trig_hyperbolic(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "*cot(x)\n*sec(x)\n*csc(x)\n*arcsin(x)\n*arccos(x)\n"
        "*arctan(x)\n*sinh(x)\n*cosh(x)\n*tanh(x)\n*coth(x)\n",
    )
    assert ok is True
    for fn in ("cot", "sec", "csc", "arcsin", "arccos", "arctan",
               "sinh", "cosh", "tanh", "coth"):
        assert f"${fn}(x)$" in typ, fn
    assert "unknown command" not in err.lower()


def test_nesting_frac_int(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*frac(*int(0;1;x) ; 2)\n"
    )
    assert ok is True
    assert "integral" in typ
    assert "frac" in typ
    assert "*int" not in typ


def test_variables_and_calc_inside_args(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "<a> = 2\n*int(0 ; <a> ; x^2)\n*binom(calc(<a> + 1) ; 2)\n",
    )
    assert ok is True
    assert "$integral_(0)^(2) x^2$" in typ
    assert "$binom(3, 2)$" in typ


def test_new_commands_no_lsp_unknown_warning():
    from lsp import analysis
    for snippet in ("*int(0 ; 1 ; x)\n", "*cases(a | b)\n", "*vec(3 ; 4)\n",
                    "*binom(n ; k)\n", "*cot(x)\n", "*sinh(x)\n"):
        result = analysis.analyze_text(snippet)
        assert not any("unknown command" in d.message.lower()
                       for d in result.diagnostics), snippet


def test_new_commands_no_unknown_command_stderr(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "*int(x)\n*cases(a | b)\n*vec(3 ; 4)\n*binom(n ; k)\n*cot(x)\n",
    )
    assert ok is True
    assert "unknown command" not in err.lower()


def test_plot_new_trig(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*plot(*cot(x) ; 1 ; 2)\n"
    )
    assert ok is True
    assert "[Plot Error" not in typ


def test_real_pdf_compile(tmp_path):
    """Real Typst compile (no stub) for every new command family."""
    pytest.importorskip("typst")
    import shutil
    import tempfile
    from compiler.pipeline import compile_ezmath
    work = tempfile.mkdtemp(prefix="easymath-newcmd-")
    try:
        src = os.path.join(work, "new.ezmath")
        out = os.path.join(work, "new.pdf")
        with open(src, "w", encoding="utf-8") as f:
            f.write(
                "*int(0 ; 1 ; x^2 ; x)\n"
                "*cases(a | b)\n"
                "*vec(3 ; 4)\n"
                "*binom(5 ; 2)\n"
                "*cot(x)\n*sinh(x)\n"
            )
        assert compile_ezmath(src, out) is True
        assert os.path.isfile(out)
    finally:
        shutil.rmtree(work, ignore_errors=True)
        # Never leave .typ/.pdf in the repo: workdir is a temp dir.
