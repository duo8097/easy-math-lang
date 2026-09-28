"""Export-format tests: pdf/png/svg/html/typ inference + CLI flags."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from compiler import pipeline as _pipeline
from compiler.pipeline import infer_export_format


def test_infer_format_from_extension():
    assert infer_export_format("a.pdf", None) == "pdf"
    assert infer_export_format("a.png", None) == "png"
    assert infer_export_format("a.svg", None) == "svg"
    assert infer_export_format("a.html", None) == "html"
    assert infer_export_format("a.htm", None) == "html"
    assert infer_export_format("a.typ", None) == "typ"


def test_infer_explicit_format_wins():
    assert infer_export_format("a.pdf", "png") == "png"
    assert infer_export_format("a.pdf", "SVG") == "svg"


def test_infer_invalid_format(capsys):
    assert infer_export_format("a.pdf", "docx") is None
    assert "unsupported export format" in capsys.readouterr().err


def _compile(tmp_path, monkeypatch, capsys, text, out_name, **kw):
    from compiler import compile_ezmath
    src = tmp_path / "doc.ezmath"
    src.write_text(text, encoding="utf-8")
    calls = []

    def _fake_compile(typ_file, out_file, **kwargs):
        calls.append((typ_file, out_file, kwargs))
        # Create the output file so pipeline reports success.
        # Multi-page simulation is covered separately with real typst.
        parent = os.path.dirname(os.path.abspath(out_file))
        if parent:
            os.makedirs(parent, exist_ok=True)
        # Handle {p} pattern by creating one page.
        if "{p}" in out_file:
            out_file = out_file.replace("{p}", "1")
        with open(out_file, "w", encoding="utf-8") as h:
            h.write("fake")
        return None

    stub = type("_TypstStub", (), {"compile": staticmethod(_fake_compile)})()
    monkeypatch.setattr(_pipeline, "typst", stub)
    out = tmp_path / out_name
    ok = compile_ezmath(str(src), str(out), **kw)
    return ok, out, calls, capsys.readouterr()


def test_export_pdf_default(tmp_path, monkeypatch, capsys):
    ok, out, calls, _ = _compile(tmp_path, monkeypatch, capsys, "hello\n", "doc.pdf")
    assert ok and out.is_file()
    assert calls and calls[0][2].get("format", "pdf") in (None, "pdf")


def test_export_png_from_extension(tmp_path, monkeypatch, capsys):
    ok, out, calls, _ = _compile(tmp_path, monkeypatch, capsys, "hello\n", "doc.png")
    assert ok and out.is_file()
    assert calls[0][2].get("format") == "png"


def test_export_svg_explicit_format(tmp_path, monkeypatch, capsys):
    ok, out, calls, _ = _compile(
        tmp_path, monkeypatch, capsys, "hello\n", "doc.bin", format="svg")
    assert ok
    assert calls[0][2].get("format") == "svg"


def test_export_html(tmp_path, monkeypatch, capsys):
    ok, out, calls, _ = _compile(tmp_path, monkeypatch, capsys, "hello\n", "doc.html")
    assert ok and out.is_file()
    assert calls[0][2].get("format") == "html"


def test_export_typ_copies_source(tmp_path, monkeypatch, capsys):
    ok, out, calls, _ = _compile(tmp_path, monkeypatch, capsys, "hello\n", "doc.typ")
    assert ok and out.is_file()
    assert calls == []  # no typst.compile for .typ
    assert "hello" in out.read_text(encoding="utf-8")


def test_export_ppi_passed_for_png(tmp_path, monkeypatch, capsys):
    ok, _, calls, _ = _compile(
        tmp_path, monkeypatch, capsys, "hello\n", "doc.png", ppi=300)
    assert ok
    assert calls[0][2].get("ppi") == 300


def test_export_invalid_ppi_fails(tmp_path, monkeypatch, capsys):
    ok, _, _, _ = _compile(
        tmp_path, monkeypatch, capsys, "hello\n", "doc.png", ppi="nope")
    assert ok is False


def test_cli_format_and_output_flags(monkeypatch, capsys, tmp_path):
    src = tmp_path / "in.ezmath"
    src.write_text("hello\n", encoding="utf-8")
    out = tmp_path / "cli.png"
    calls = []

    def _fake_compile(typ_file, out_file, **kwargs):
        calls.append((out_file, kwargs))
        with open(out_file, "w", encoding="utf-8") as h:
            h.write("x")

    stub = type("_TypstStub", (), {"compile": staticmethod(_fake_compile)})()
    monkeypatch.setattr(_pipeline, "typst", stub)
    monkeypatch.setattr(
        sys, "argv",
        ["easy-math-lang", "--format", "png", "--ppi", "200",
         str(src), "-o", str(out)])
    with pytest.raises(SystemExit) as exc:
        _pipeline.main()
    assert exc.value.code == 0
    assert out.is_file()
    assert calls[0][1].get("format") == "png"
    assert calls[0][1].get("ppi") == 200


def test_cli_list_formats(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["easy-math-lang", "--list-formats"])
    with pytest.raises(SystemExit) as exc:
        _pipeline.main()
    assert exc.value.code == 0
    assert "pdf" in capsys.readouterr().out
