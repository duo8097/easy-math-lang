"""Export format alias: typst == typ (CLI and editor)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from compiler import pipeline as _pipeline
from compiler.pipeline import infer_export_format


def test_infer_typst_alias():
    assert infer_export_format("a.typst", None) == "typ"
    assert infer_export_format("a.typ", None) == "typ"
    assert infer_export_format("a.pdf", "typst") == "typ"
    assert infer_export_format("a.pdf", "TYPST") == "typ"
    assert infer_export_format("a.pdf", ".typst") == "typ"


def _compile(tmp_path, monkeypatch, capsys, text, out_name, **kw):
    from compiler import compile_ezmath
    src = tmp_path / "doc.ezmath"
    src.write_text(text, encoding="utf-8")
    calls = []

    def _fake_compile(typ_file, out_file, **kwargs):
        calls.append((typ_file, out_file, kwargs))
        parent = os.path.dirname(os.path.abspath(out_file))
        if parent:
            os.makedirs(parent, exist_ok=True)
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


def test_compile_to_typst_extension(tmp_path, monkeypatch, capsys):
    ok, out, calls, _ = _compile(tmp_path, monkeypatch, capsys, "hello\n", "doc.typst")
    assert ok and out.is_file()
    assert calls == []  # typst source copy, no typst.compile call
    assert "hello" in out.read_text(encoding="utf-8")


def test_compile_explicit_typst_format(tmp_path, monkeypatch, capsys):
    ok, out, calls, _ = _compile(
        tmp_path, monkeypatch, capsys, "hello\n", "doc.bin", format="typst")
    assert ok
    assert calls == []
    assert "hello" in out.read_text(encoding="utf-8")


def test_cli_format_typst(monkeypatch, capsys, tmp_path):
    import pytest
    src = tmp_path / "in.ezmath"
    src.write_text("hello\n", encoding="utf-8")
    out = tmp_path / "cli.typst"
    stub = type("_TypstStub", (), {"compile": staticmethod(lambda *a, **k: None)})()
    monkeypatch.setattr(_pipeline, "typst", stub)
    monkeypatch.setattr(
        sys, "argv",
        ["easy-math-lang", "--format", "typst", str(src), "-o", str(out)])
    with pytest.raises(SystemExit) as exc:
        _pipeline.main()
    assert exc.value.code == 0
    assert out.is_file()
    assert "hello" in out.read_text(encoding="utf-8")


def test_editor_export_typst_format(tmp_path):
    from editor.preview import export_source_to_file
    out = str(tmp_path / "ed.typst")
    res = export_source_to_file("hello\n", out, format="typst")
    assert res.get("ok") is True
    assert res.get("format") == "typ"
    with open(res["output"], encoding="utf-8") as h:
        assert "hello" in h.read()
