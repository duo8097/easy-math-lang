"""Bare unknown commands (*foo with no parens) warn like *cmd(...) does."""

import os
import sys

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


def test_bare_unknown_warns_and_builds(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(tmp_path, monkeypatch, capsys, "*foo\n")
    assert ok is True
    assert "[Warning] Line 1: unknown command *foo — treated as plain text." in err
    assert "\\*foo" in typ


def test_bare_unknown_mid_line(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "x *bogus y\n"
    )
    assert ok is True
    assert "[Warning] Line 1: unknown command *bogus — treated as plain text." in err
    assert "\\*bogus" in typ


def test_bare_typo_suggests(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(tmp_path, monkeypatch, capsys, "*frcc\n")
    assert ok is True
    assert "unknown command *frcc" in err
    assert "Did you mean '*frac(...)'?" in err


def test_bare_unrelated_gets_no_suggestion(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(tmp_path, monkeypatch, capsys, "x *bogus y\n")
    assert ok is True
    assert "unknown command *bogus" in err
    assert "Did you mean" not in err


def test_bare_geometry_warns_draw_only(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(tmp_path, monkeypatch, capsys, "*point\n")
    assert ok is True
    assert "*point is only valid inside *draw(...)" in err


def test_bare_draw_warns_malformed(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(tmp_path, monkeypatch, capsys, "*draw\n")
    assert ok is True
    assert "unclosed or malformed *draw(...)" in err


def test_known_symbol_keywords_stay_silent(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "*alpha *pi *infinity *quad *theta\n",
    )
    assert ok is True
    assert "unknown command" not in err.lower()


def test_known_command_bare_stays_silent(tmp_path, monkeypatch, capsys):
    # *frac without parens is not valid, but it is a known command:
    # existing behavior (silent literal) is preserved.
    ok, typ, err, out = _compile(tmp_path, monkeypatch, capsys, "*frac\n")
    assert ok is True
    assert "unknown command" not in err.lower()
    assert "\\*frac" in typ


def test_multiplication_stays_silent(tmp_path, monkeypatch, capsys):
    for text in ("2 * 3\n", "2*3\n", "a*b\n", "2 ** 3\n", "* (2)\n"):
        ok, typ, err, out = _compile(tmp_path, monkeypatch, capsys, text)
        assert ok is True, text
        assert "unknown command" not in err.lower(), text


def test_raw_p_content_stays_silent(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*p(*foo and *bogus)\n"
    )
    assert ok is True
    assert "unknown command" not in err.lower()


def test_calc_content_stays_silent(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "calc(2*3)\n*plot(2*x ; -5 ; 5)\n"
    )
    assert ok is True
    assert "unknown command" not in err.lower()


def test_comment_stays_silent(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "// *foo *bogus\nhello\n"
    )
    assert ok is True
    assert "unknown command" not in err.lower()


def test_escaped_asterisk_no_unknown_warning(tmp_path, monkeypatch, capsys):
    # A literal backslash (\\) never opens math; the star after it is
    # escaped, not a command.
    ok, typ, err, out = _compile(tmp_path, monkeypatch, capsys, "\\\\*foo\n")
    assert ok is True
    assert "unknown command" not in err.lower()


def test_math_arg_multiplication_stays_silent(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*frac(a*b ; c)\n"
    )
    assert ok is True
    assert "unknown command" not in err.lower()
    assert "$frac(a*b, c)$" in typ


def test_bare_unknown_inside_inline_math_warns(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "\\ *bogus \\\n"
    )
    assert ok is True
    assert "unknown command *bogus" in err


def test_inline_math_multiplication_stays_silent(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "\\ 2 * 3 \\\n\\ a*b \\\n"
    )
    assert ok is True
    assert "unknown command" not in err.lower()


def test_paren_form_warns_once(tmp_path, monkeypatch, capsys):
    # *cmd(...) must not also trigger the bare-word path (no *frac-style
    # partial, no double diagnostic for one typo).
    ok, typ, err, out = _compile(tmp_path, monkeypatch, capsys, "*fract(1 ; 2)\n")
    assert ok is True
    assert err.lower().count("unknown command") == 1
    assert "Did you mean '*frac(...)'?" in err


def test_bare_lsp_warning():
    from lsp import analysis
    result = analysis.analyze_text("*foo\n")
    assert any("Unknown command *foo" in d.message
               for d in result.diagnostics)
    result = analysis.analyze_text("x *bogus y\n")
    assert any("*bogus" in d.message for d in result.diagnostics)


def test_bare_lsp_silence():
    from lsp import analysis
    for snippet in ("*alpha\n", "*pi\n", "2 * 3\n", "2*x\n",
                    "*p(*foo)\n", "calc(2*3)\n", "*frac(a*b ; c)\n",
                    "*frac\n", "// *foo\n"):
        result = analysis.analyze_text(snippet)
        assert not any("unknown command" in d.message.lower()
                       for d in result.diagnostics), snippet
