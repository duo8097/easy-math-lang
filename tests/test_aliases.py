"""Friendly math aliases (MATH_ALIASES) — equivalence and docs sync.

Every alias in compiler.math_commands.MATH_ALIASES must produce the
same Typst as its canonical command, be advertised by the LSP
(completion/hover), and be documented in rule.txt.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from compiler import pipeline as _pipeline  # noqa: E402
from compiler.math_commands import MATH_ALIASES  # noqa: E402
from lsp.builtins import MATH_DOCS  # noqa: E402

# A representative call per alias, with its canonical twin.
ALIAS_CALLS = {
    'fraction': '*fraction(2 ; 3)',
    'power': '*power(x ; 2)',
    'squareroot': '*squareroot(16)',
    'square-root': '*square-root(16)',
    'cuberoot': '*cuberoot(27)',
    'cube-root': '*cube-root(27)',
    'absolute': '*absolute(3 - 5)',
    'summation': '*summation(i = 1 ; n ; i)',
    'product': '*product(i = 1 ; n ; i)',
    'limit': '*limit(x -> 0 ; sin(x) / x)',
    'integral': '*integral(0 ; 1 ; x^2)',
}


def _compile_typ(tmp_path, monkeypatch, text):
    """Compile *text* with a stubbed Typst; return the .typ body."""
    from compiler import compile_ezmath
    src = tmp_path / "doc.ezmath"
    src.write_text(text, encoding="utf-8")

    def _fake_compile(typ_file, out_file, **kwargs):
        parent = os.path.dirname(os.path.abspath(out_file))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as h:
            h.write("fake")
        return None

    stub = type("_TypstStub", (), {"compile": staticmethod(_fake_compile)})()
    monkeypatch.setattr(_pipeline, "typst", stub)
    assert compile_ezmath(str(src), str(tmp_path / "doc.pdf")) is True
    return (tmp_path / "doc.typ").read_text(encoding="utf-8")


def _body_lines(typ):
    return [line for line in typ.splitlines()
            if line and not line.startswith("#")]


# ----------------------------------------------------------------------
# Table completeness: every alias has a test call and sane targets
# ----------------------------------------------------------------------

def test_alias_table_covers_math_aliases():
    # Identity entries (cbrt -> cbrt) need no separate call.
    expected = {a for a in MATH_ALIASES if a != MATH_ALIASES[a]}
    assert expected == set(ALIAS_CALLS), (
        "ALIAS_CALLS must cover every non-identity MATH_ALIASES entry")


def test_alias_targets_are_known_commands():
    from compiler.diagnostics import KNOWN_COMMANDS
    for alias, target in MATH_ALIASES.items():
        assert target in KNOWN_COMMANDS, (alias, target)


# ----------------------------------------------------------------------
# Equivalence: alias output == canonical output
# ----------------------------------------------------------------------

@pytest.mark.parametrize("alias", sorted(ALIAS_CALLS))
def test_alias_matches_canonical_output(alias, tmp_path, monkeypatch):
    alias_call = ALIAS_CALLS[alias]
    canonical_call = alias_call.replace(f"*{alias}", f"*{MATH_ALIASES[alias]}")
    got = _body_lines(_compile_typ(tmp_path, monkeypatch, alias_call + "\n"))
    want = _body_lines(_compile_typ(tmp_path, monkeypatch,
                                    canonical_call + "\n"))
    assert got == want, f"{alias_call} -> {got} != {canonical_call} -> {want}"


def test_alias_inside_inline_math(tmp_path, monkeypatch):
    typ = _compile_typ(tmp_path, monkeypatch,
                       "\\ v = *squareroot(16) \\\n")
    assert "$v = sqrt(16)$" in typ


def test_alias_hyphenated_inside_math_command(tmp_path, monkeypatch):
    got = _body_lines(_compile_typ(tmp_path, monkeypatch,
                                   "*frac(*square-root(16) ; 2)\n"))
    want = _body_lines(_compile_typ(tmp_path, monkeypatch,
                                    "*frac(*sqrt(16) ; 2)\n"))
    assert got == want


# ----------------------------------------------------------------------
# LSP: aliases are advertised (completion / hover)
# ----------------------------------------------------------------------

def test_every_alias_in_lsp_math_docs():
    missing = [a for a in sorted(MATH_ALIASES) if a not in MATH_DOCS]
    assert not missing, f"aliases missing from LSP builtins: {missing}"


def test_alias_docs_say_they_are_aliases():
    for alias, target in sorted(MATH_ALIASES.items()):
        if alias == target:
            continue
        signature, description = MATH_DOCS[alias]
        assert alias in signature, alias
        # "alias of *frac" / "alias of *cbrt" style microcopy.
        assert target in description, (alias, description)


def test_alias_completion_offered():
    from lsp import analysis
    items = analysis.complete("Show summa\n", 0, 10)
    labels = [item['label'] for item in items]
    assert 'summation' in labels


# ----------------------------------------------------------------------
# Docs: aliases documented in rule.txt and the user guides
# ----------------------------------------------------------------------

def _read(relpath):
    path = os.path.join(os.path.dirname(__file__), "..", relpath)
    with open(path, encoding="utf-8") as h:
        return h.read()


@pytest.mark.parametrize("alias", sorted(ALIAS_CALLS))
def test_alias_documented_in_rule_txt(alias):
    assert f"*{alias}" in _read("rule.txt"), alias


@pytest.mark.parametrize("alias", sorted(ALIAS_CALLS))
def test_alias_documented_in_guides(alias):
    guides = _read("docs/algebra.md") + _read("docs/cheatsheet.md")
    assert alias in guides, alias
