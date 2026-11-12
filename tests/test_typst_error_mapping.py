"""Typst-failure diagnostics mapped back to the .ezmath source
(compiler.typst_errors.try_report_typst_error)."""

import os
import sys

import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "src")
)

from compiler import compile_ezmath
from compiler import pipeline as _pipeline


def test_typst_error_with_position_maps_back_to_eml(tmp_path, monkeypatch, capsys):
    src = tmp_path / "case.ezmath"
    src.write_text("first line\nsecond line\n", encoding="utf-8")

    class FakeTypstError(Exception):
        pass

    def fake_compile(typ, out, **kwargs):
        from compiler.source_map import TypstSourceMap, default_map_path
        smap = TypstSourceMap.load(default_map_path(typ))
        entry = next(e for e in smap.entries if e.typ_start.line >= 5)
        err = FakeTypstError("unclosed delimiter")
        err.diagnostic = (
            "error: unclosed delimiter\n"
            f"  ┌─ {typ}:{entry.typ_start.line + 1}:0\n"
            "  │\n"
        )
        raise err

    stub = type(
        "_Stub", (),
        {"compile": staticmethod(fake_compile), "TypstError": FakeTypstError},
    )()
    monkeypatch.setattr(_pipeline, "typst", stub)
    ok = compile_ezmath(str(src), str(tmp_path / "case.pdf"))
    assert ok is False
    err = capsys.readouterr().err
    assert "[ERROR] Typst compilation failed: unclosed delimiter" in err
    assert f'  File "{src}", line 1' in err
    assert "    first line" in err


def test_typst_error_unmapped_position_keeps_legacy_output(tmp_path, monkeypatch, capsys):
    src = tmp_path / "case.ezmath"
    src.write_text("first line\nsecond line\n", encoding="utf-8")

    class FakeTypstError(Exception):
        pass

    def fake_compile(typ, out, **kwargs):
        err = FakeTypstError("unclosed delimiter")
        # A position that does not resolve in the source map
        # (the first header line is never mapped).
        err.diagnostic = (
            "error: unclosed delimiter\n"
            f"  ┌─ {typ}:1:0\n"
            "  │\n"
        )
        raise err

    stub = type(
        "_Stub", (),
        {"compile": staticmethod(fake_compile), "TypstError": FakeTypstError},
    )()
    monkeypatch.setattr(_pipeline, "typst", stub)
    ok = compile_ezmath(str(src), str(tmp_path / "case.pdf"))
    assert ok is False
    err = capsys.readouterr().err
    assert "[ERROR] Typst compilation failed: unclosed delimiter" in err
    assert "  File " not in err


def test_typst_error_without_position_keeps_legacy_output(tmp_path, monkeypatch, capsys):
    src = tmp_path / "case.ezmath"
    src.write_text("first line\n", encoding="utf-8")

    class FakeTypstError(Exception):
        pass

    def fake_compile(typ, out, **kwargs):
        raise FakeTypstError("something bad without a location")

    stub = type(
        "_Stub", (),
        {"compile": staticmethod(fake_compile), "TypstError": FakeTypstError},
    )()
    monkeypatch.setattr(_pipeline, "typst", stub)
    ok = compile_ezmath(str(src), str(tmp_path / "case.pdf"))
    assert ok is False
    err = capsys.readouterr().err
    assert "[ERROR] Typst compilation failed: something bad without a location" in err
    assert "  File " not in err


