"""Math features: number sets, accents, diff, det, set, align."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from compiler import pipeline as _pipeline


def _compile(tmp_path, monkeypatch, capsys, text, name="case"):
    src = tmp_path / f"{name}.ezmath"
    src.write_text(text, encoding="utf-8")
    stub = type(
        "_TypstStub", (), {"compile": staticmethod(lambda *a, **k: None)}
    )()
    monkeypatch.setattr(_pipeline, "typst", stub)
    monkeypatch.setattr(_pipeline, "_typst_import_failed", False)
    ok = _pipeline.compile_ezmath(str(src), str(tmp_path / f"{name}.pdf"))
    captured = capsys.readouterr()
    typ = (tmp_path / f"{name}.typ").read_text(encoding="utf-8")
    return ok, typ, captured.err, captured.out


# --- 3a: number sets ----------------------------------------------------

def test_number_sets_text(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "*reals *naturals *integers *rationals *complex\n"
        "*RR *NN *ZZ *QQ *CC\n",
    )
    assert ok is True
    for glyph in ("ℝ", "ℕ", "ℤ", "ℚ", "ℂ"):
        assert glyph in typ
    assert "unknown command" not in err.lower()


def test_number_sets_math_and_cells(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "\\ x *isin *RR \\\n"
        "*matrix(*NN ; 2 | 3 ; *ZZ)\n"
        "*cases(x ; x *isin *reals | 0 ; x *notin *complex)\n",
    )
    assert ok is True
    assert "$x ∈ ℝ$" in typ
    assert "$mat(ℕ, 2; 3, ℤ)$" in typ
    assert "$cases(x & x ∈ ℝ, 0 & x ∉ ℂ)$" in typ
    assert "unknown command" not in err.lower()


def test_number_set_lookalikes(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "real numbers\n*real\n*RRx\n"
    )
    assert ok is True
    assert "real numbers" in typ
    assert "unknown command *real" in err
    # *RRx is a different (unknown) word, not RR + x.
    assert "unknown command *RRx" in err
    assert "ℝ" not in typ


# --- 3b: accents ----------------------------------------------------------

def test_accents(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "*hat(x)\n*bar(y)\n*overline(AB)\n*tilde(z)\n*dot(w)\n",
    )
    assert ok is True
    assert "$hat(x)$" in typ
    assert "$bar(y)$" in typ
    assert "$overline(A B)$" in typ
    assert "$tilde(z)$" in typ
    assert "$dot(w)$" in typ
    assert "unknown command" not in err.lower()


def test_accents_nested_vars(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "<a> = x\n*hat(*bar(<a>))\n*tilde(calc(1 + 1))\n",
    )
    assert ok is True
    assert "$hat($bar(x)$)$" in typ or "$hat(bar(x))$" in typ
    assert "$tilde(2)$" in typ


def test_accents_bad_args(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(tmp_path, monkeypatch, capsys, "*hat()\n")
    assert ok is True
    assert "empty argument" in err
    assert "$hat" not in typ


def test_accents_lookalikes(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "a hat today\n*hat\n"
    )
    assert ok is True
    assert "a hat today" in typ
    assert "unknown command" not in err.lower()
    assert "$hat" not in typ


# --- 3c: diff -------------------------------------------------------------

def test_diff_basic(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*diff(f ; x)\n"
    )
    assert ok is True
    assert "$frac(dif f, dif x)$" in typ


def test_diff_nth(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*diff(f ; x ; 2)\n"
    )
    assert ok is True
    assert "$frac(dif^2 f, dif x^2)$" in typ


def test_pdiff(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "*pdiff(f ; x)\n*pdiff(f ; x ; 3)\n",
    )
    assert ok is True
    assert "$frac(partial f, partial x)$" in typ
    assert "$frac(partial^3 f, partial x^3)$" in typ


def test_diff_vars_calc_comma(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "<a> = 2\n*diff(x^<a> ; x)\n*diff(f, x)\n",
    )
    assert ok is True
    assert "$frac(dif x^2, dif x)$" in typ
    assert "$frac(dif f, dif x)$" in typ


def test_diff_bad_args(tmp_path, monkeypatch, capsys):
    for text in ("*diff(f)\n", "*diff()\n", "*diff(f ; x ; 2 ; y)\n"):
        ok, typ, err, out = _compile(tmp_path, monkeypatch, capsys, text)
        assert ok is True, text
        assert "Warning" in err, text
    ok, typ, err, out = _compile(tmp_path, monkeypatch, capsys, "*diff(f)\n")
    assert "$frac(dif" not in typ


def test_diff_nested_in_frac(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*frac(*diff(f ; x) ; 2)\n"
    )
    assert ok is True
    assert "dif f" in typ and "frac" in typ


# --- 3d: det --------------------------------------------------------------

def test_det_grid(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*det(1 ; 2 | 3 ; 4)\n"
    )
    assert ok is True
    assert "$det(mat(1, 2; 3, 4))$" in typ


def test_det_matrix_arg(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*det(*matrix(1 ; 2 | 3 ; 4))\n"
    )
    assert ok is True
    assert "$det(mat(1, 2; 3, 4))$" in typ


def test_det_comma_and_vars(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "<a> = 2\n*det(1, <a> | 3, 4)\n*det(*mat(1 ; 2 | 3 ; 4))\n",
    )
    assert ok is True
    assert "$det(mat(1, 2; 3, 4))$" in typ


def test_det_ragged_pads_and_empty_warns(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*det(1 ; 2 | 3)\n"
    )
    assert ok is True
    assert "different lengths" in err
    assert "$det(mat(1, 2; 3, 0))$" in typ
    ok, typ, err, out = _compile(tmp_path, monkeypatch, capsys, "*det()\n")
    assert ok is True
    assert "*det(...) is empty" in err
    assert "$det" not in typ


def test_det_unclosed_warns(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*det(1 ; 2\n"
    )
    assert "unclosed *det(..." in err
    assert "$det" not in typ


def test_det_in_math(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "\\ *det(1 ; 2 | 3 ; 4) = 0 \\\n"
    )
    assert ok is True
    assert "det(mat(1, 2; 3, 4))" in typ
    assert "unknown command" not in err.lower()


# --- 3e: set --------------------------------------------------------------

def test_set_builder(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*set(x ; x > 0)\n"
    )
    assert ok is True
    assert "$ {x | x > 0} $" in typ


def test_set_listing(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "*set(1 ; 2 ; 3)\n*set(a, b)\n*set(x)\n",
    )
    assert ok is True
    assert "$ {1, 2, 3} $" in typ
    assert "$ {a, b} $" in typ
    assert "$ {x} $" in typ


def test_set_thousands_and_quoted_semi(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*set(100,000 ; 2 ; 3)\n"
    )
    assert ok is True
    assert "100\\,000" in typ
    assert "unknown command" not in err.lower()


def test_set_empty_warns(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*set(x ; )\n"
    )
    assert ok is True
    assert "empty argument" in err
    assert "{x |" not in typ


def test_set_lookalikes(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "a set of rules\n*set\n"
    )
    assert ok is True
    assert "a set of rules" in typ
    assert "unknown command" not in err.lower()


# --- 3f: align ------------------------------------------------------------

def test_align_basic(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*align(x = 1 | y = 2)\n"
    )
    assert ok is True
    assert "$ x & 1 \\\\ y & 2 $" in typ


def test_align_block_form(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "*align(\n    x = 1\n    y = 2\n)\n",
    )
    assert ok is True
    assert "$ x & 1 \\\\ y & 2 $" in typ


def test_align_no_equals_no_crash(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*align(x = 1 | just words here)\n"
    )
    assert ok is True
    assert "&" in typ
    assert "[Error]" not in err


def test_align_first_equals_wins(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*align(a == b | x = y = z)\n"
    )
    assert ok is True
    assert "$ a & b \\\\ x & y = z $" in typ


def test_align_sum_parens_safe(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "*align(*sum(i = 1 ; n ; i) = x | y = 2)\n",
    )
    assert ok is True
    assert "sum_(i = 1)" in typ
    assert typ.count("&") == 2


def test_align_empty_warns(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(tmp_path, monkeypatch, capsys, "*align()\n")
    assert ok is True
    assert "*align(...) is empty" in err


def test_align_vars_calc(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "<a> = 2\n*align(x = <a> | y = calc(<a> + 1))\n",
    )
    assert ok is True
    assert "$ x & 2 \\\\ y & 3 $" in typ


# --- LSP + registry --------------------------------------------------------

def test_new_commands_no_lsp_unknown_warning():
    from lsp import analysis
    for snippet in ("*hat(x)\n", "*overline(AB)\n", "*diff(f ; x)\n",
                    "*pdiff(f ; x)\n", "*det(1 ; 2)\n", "*set(x ; y)\n",
                    "*align(x = 1)\n", "x *isin *RR\n"):
        result = analysis.analyze_text(snippet)
        assert not any("unknown command" in d.message.lower()
                       for d in result.diagnostics), snippet


def test_new_commands_lsp_completion_hover():
    from lsp import analysis
    items = analysis.complete("*di", 0, 3)
    labels = {i["label"] for i in items}
    assert {"diff", "pdiff", "det"} <= labels
    hov = analysis.hover("*diff(f ; x)\n", 0, 2)
    assert hov is not None and "Derivative" in hov["value"]
    hov = analysis.hover("*align(x = 1)\n", 0, 2)
    assert hov is not None and "aligned" in hov["value"].lower()
    hov = analysis.hover("x *isin *RR\n", 0, 9)
    assert hov is not None and hov["value"].strip().endswith("ℝ")


def test_new_commands_symbol_registry():
    from editor.symbol_registry import build_source, get_symbol
    assert build_source('hat', {'expression': 'x'}) == '*hat(x)'
    assert build_source('overline', {'expression': 'AB'}) == '*overline(AB)'
    assert build_source(
        'diff', {'function': 'x^2', 'variable': 'x'}) == '*diff(x^2 ; x)'
    assert build_source(
        'diff', {'function': 'x^2', 'variable': 'x', 'order': '2'}) == \
        '*diff(x^2 ; x ; 2)'
    assert build_source(
        'det', {'r1c1': '1', 'r1c2': '2', 'r2c1': '3', 'r2c2': '4'}) == \
        '*det(1 ; 2 | 3 ; 4)'
    assert build_source(
        'set', {'element': 'x', 'condition': 'x > 0'}) == '*set(x ; x > 0)'
    assert build_source(
        'align', {'row1': 'x = 1', 'row2': 'y = 2'}) == '*align(x = 1 | y = 2)'
    assert get_symbol('det').category == 'Math'


def test_real_pdf_compile():
    """Real Typst compile (no stub) for every Phase 3 family."""
    pytest.importorskip("typst")
    import shutil
    import tempfile
    from compiler.pipeline import compile_ezmath
    work = tempfile.mkdtemp(prefix="easymath-mathfeat-")
    try:
        src = os.path.join(work, "m.ezmath")
        out = os.path.join(work, "m.pdf")
        with open(src, "w", encoding="utf-8") as f:
            f.write(
                "x *isin *RR and *naturals\n"
                "*hat(x) + *overline(AB)\n"
                "*diff(f ; x) = *pdiff(f ; x)\n"
                "*det(1 ; 2 | 3 ; 4)\n"
                "*set(x ; x > 0) and *set(1 ; 2 ; 3)\n"
                "*align(x = 1 | y = 2)\n"
            )
        assert compile_ezmath(src, out) is True
        assert os.path.isfile(out)
    finally:
        shutil.rmtree(work, ignore_errors=True)
