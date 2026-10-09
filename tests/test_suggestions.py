"""Did-you-mean suggestion quality (no nonsense hints)."""

import io
import os
import sys
import contextlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from compiler.diagnostics import warn_unknown_commands


def _hint(cmd):
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        warn_unknown_commands(f"*{cmd}(1 ; 2)", 1)
    msg = err.getvalue()
    assert f"*{cmd}" in msg
    import re
    m = re.search(r"Did you mean '\*(.*?)\(", msg)
    return m.group(1) if m else None


def test_genuine_typos_still_hint():
    assert _hint("frcc") == "frac"
    assert _hint("sqt") == "sqrt"
    assert _hint("matrx") == "matrix"


def test_close_typos_hint():
    assert _hint("sumx") == "sum"
    assert _hint("tablle") == "table"
    assert _hint("cothh") == "coth"
    assert _hint("ointt") == "oint"


def test_unrelated_gets_no_suggestion():
    # Legitimate-but-unsupported words must not get nonsense hints.
    for cmd in ("equation", "derive", "vector", "foobar", "xyz"):
        assert _hint(cmd) is None, cmd


def test_old_nonsense_examples_fixed():
    # Pre-Task4 examples: *int suggested *point, *cot suggested *cos.
    # Both are real commands now, but the principle holds for similar
    # short pairs: unrelated short words get no hint instead of a wrong one.
    # (e.g. a made-up short command should not suggest a real one
    # with only 2/3 letters in common.)
    assert _hint("zzz") is None
    assert _hint("qqq") is None
