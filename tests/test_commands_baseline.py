"""Golden baseline for math command output (Phase 1).

Captured from untouched main. Phase 1 must keep the generated Typst
output byte-identical to this golden file.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from compiler import compile_ezmath
from compiler import pipeline as _pipeline

INPUT = os.path.join(os.path.dirname(__file__), "data", "baseline_commands.ezmath")
GOLDEN = os.path.join(os.path.dirname(__file__), "data", "commands_baseline.typ")


def test_commands_output_matches_baseline(tmp_path, monkeypatch):
    src = tmp_path / "case.ezmath"
    src.write_text(open(INPUT, encoding="utf-8").read(), encoding="utf-8")
    _stub = type("_TypstStub", (), {"compile": staticmethod(lambda *a, **k: None)})()
    monkeypatch.setattr(_pipeline, "typst", _stub)
    compile_ezmath(str(src), str(tmp_path / "case.pdf"))
    actual = (tmp_path / "case.typ").read_text(encoding="utf-8")
    expected = open(GOLDEN, encoding="utf-8").read()
    assert actual == expected, "generated Typst drifted from baseline"