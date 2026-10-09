"""Honest compile status + --strict tests."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from compiler import pipeline as _pipeline


def _stub_typst(monkeypatch):
    stub = type(
        "_TypstStub", (), {"compile": staticmethod(lambda *a, **k: None)}
    )()
    monkeypatch.setattr(_pipeline, "typst", stub)
    # Reset lazy-import failure flag so the stub is honored.
    monkeypatch.setattr(_pipeline, "_typst_import_failed", False)
    return stub


def _write(tmp_path, name, text):
    src = tmp_path / name
    src.write_text(text, encoding="utf-8")
    return str(src)


def test_clean_file_reports_success_and_exit_zero(tmp_path, monkeypatch, capsys):
    _stub_typst(monkeypatch)
    src = _write(tmp_path, "clean.ezmath", "Hello *frac(2 ; 3)\n")
    out = str(tmp_path / "clean.pdf")
    ok = _pipeline.compile_ezmath(src, out)
    assert ok is True
    captured = capsys.readouterr()
    assert "Successfully compiled" in captured.out
    assert "error(s)" not in captured.out


def test_clean_file_strict_still_exit_zero(tmp_path, monkeypatch, capsys):
    _stub_typst(monkeypatch)
    src = _write(tmp_path, "clean.ezmath", "Hello *frac(2 ; 3)\n")
    out = str(tmp_path / "clean.pdf")
    ok = _pipeline.compile_ezmath(src, out, strict=True)
    assert ok is True
    captured = capsys.readouterr()
    assert "Successfully compiled" in captured.out


def test_error_file_default_exit_zero_with_honest_message(
    tmp_path, monkeypatch, capsys
):
    _stub_typst(monkeypatch)
    src = _write(tmp_path, "bad.ezmath", "Need <foo> here\n")
    out = str(tmp_path / "bad.pdf")
    ok = _pipeline.compile_ezmath(src, out)
    # Default keeps backward compat: True (exit 0) even with errors.
    assert ok is True
    captured = capsys.readouterr()
    assert "Successfully compiled" not in captured.out
    assert "Compiled " in captured.out
    assert "1 error(s), 0 warning(s)" in captured.out
    # PDF may still be written (stubbed backend counts as success).
    assert (tmp_path / "bad.typ").exists()


def test_error_file_strict_fails_but_pdf_written(tmp_path, monkeypatch, capsys):
    _stub_typst(monkeypatch)
    src = _write(tmp_path, "bad.ezmath", "Need <foo> here\n")
    out = str(tmp_path / "bad.pdf")
    ok = _pipeline.compile_ezmath(src, out, strict=True)
    assert ok is False
    captured = capsys.readouterr()
    assert "1 error(s), 0 warning(s)" in captured.out
    assert (tmp_path / "bad.typ").exists()


def test_calc_division_by_zero_counts_as_error(tmp_path, monkeypatch, capsys):
    _stub_typst(monkeypatch)
    src = _write(tmp_path, "calc.ezmath", "calc(1 / 0)\n")
    out = str(tmp_path / "calc.pdf")
    assert _pipeline.compile_ezmath(src, out) is True
    out_text = capsys.readouterr().out
    assert "1 error(s)" in out_text
    assert _pipeline.compile_ezmath(src, out, strict=True) is False


def test_warning_only_keeps_success_message(tmp_path, monkeypatch, capsys):
    _stub_typst(monkeypatch)
    src = _write(tmp_path, "warn.ezmath", "*foobar(1 ; 2)\n")
    out = str(tmp_path / "warn.pdf")
    assert _pipeline.compile_ezmath(src, out) is True
    assert "Successfully compiled" in capsys.readouterr().out
    # Warnings never trigger strict failure.
    assert _pipeline.compile_ezmath(src, out, strict=True) is True


def _run_main(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as exc:
        _pipeline.main()
    return exc.value.code


def test_cli_clean_exit_zero(tmp_path, monkeypatch, capsys):
    _stub_typst(monkeypatch)
    src = _write(tmp_path, "clean.ezmath", "Hello\n")
    out = str(tmp_path / "clean.pdf")
    code = _run_main(monkeypatch, ["easy-math-lang", src, out])
    assert code == 0
    assert "Successfully compiled" in capsys.readouterr().out


def test_cli_error_default_exit_zero(tmp_path, monkeypatch, capsys):
    _stub_typst(monkeypatch)
    src = _write(tmp_path, "bad.ezmath", "Need <foo> here\n")
    out = str(tmp_path / "bad.pdf")
    code = _run_main(monkeypatch, ["easy-math-lang", src, out])
    assert code == 0
    captured = capsys.readouterr()
    assert "1 error(s)" in captured.out


def test_cli_error_strict_exit_nonzero(tmp_path, monkeypatch, capsys):
    _stub_typst(monkeypatch)
    src = _write(tmp_path, "bad.ezmath", "Need <foo> here\n")
    out = str(tmp_path / "bad.pdf")
    code = _run_main(
        monkeypatch, ["easy-math-lang", "--strict", src, "-o", out]
    )
    assert code != 0
    captured = capsys.readouterr()
    assert "1 error(s)" in captured.out
    # PDF may still be written (stubbed backend).
    assert (tmp_path / "bad.typ").exists()
