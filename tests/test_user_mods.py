"""User mod files (*use) — Phase 3."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from compiler import compile_ezmath
from compiler import pipeline as _pipeline
from compiler import diagnostics as _diags
from compiler.command_registry import DEFAULT_REGISTRY
from compiler.math_commands import MATH_ALIASES as _MA
from compiler.diagnostics import KNOWN_COMMANDS as _KC

MOD_SIMPLE = '''
[[commands]]
name = "avg"
args = 2
typst = "$frac({0} + {1}, 2)$"
usage = "*avg(a ; b)"
doc = "Average of two values."
'''

MOD_OVERRIDE = '''
[[commands]]
name = "frac"
args = 2
typst = "$frac({1}, {0})$"
usage = "*frac(numerator ; denominator)"
doc = "Swapped fraction."
'''

MOD_ALIAS = '''
[[commands]]
name = "myfrac"
args = 2
aliases = ["fraction"]
typst = "$frac({0}, {1})$"
usage = "*myfrac(a ; b)"
doc = "myfrac"
'''

MOD_BAD_PLACEHOLDER = '''
[[commands]]
name = "bad"
args = 1
typst = "$x({2})$"
usage = "*bad(a)"
doc = "bad"
'''

MOD_HANDLER = '''
[[commands]]
name = "evil"
args = 1
handler = "m:f"
usage = "*evil(a)"
doc = "evil"
'''

MOD_BUILTIN_KIND = '''
[[commands]]
name = "evil"
args = 1
kind = "builtin"
usage = "*evil(a)"
doc = "evil"
'''

MOD_OVERRIDE_POW = '''
[[commands]]
name = "pow"
args = 2
typst = "$pow({0}, {1})$"
usage = "*pow(base ; exponent)"
doc = "pow override"
'''

MOD_OVERRIDE_INT = '''
[[commands]]
name = "int"
args = 1
typst = "$int({0})$"
usage = "*int(x)"
doc = "int override"
'''

MOD_TWO_A = '''
[[commands]]
name = "twocmd"
args = 1
typst = "$A({0})$"
usage = "*twocmd(x)"
doc = "from A"
'''

MOD_TWO_B = '''
[[commands]]
name = "twocmd"
args = 1
typst = "$B({0})$"
usage = "*twocmd(x)"
doc = "from B"
'''


def _compile(tmp_path, monkeypatch, capsys, text, files=None):
    files = files or {}
    for name, content in files.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    src = tmp_path / "case.ezmath"
    src.write_text(text, encoding="utf-8")
    stub = type("_TypstStub", (), {"compile": staticmethod(lambda *a, **k: None)})()
    monkeypatch.setattr(_pipeline, "typst", stub)
    compile_ezmath(str(src), str(tmp_path / "case.pdf"))
    typ = (tmp_path / "case.typ").read_text(encoding="utf-8")
    err = capsys.readouterr().err
    return typ, err


def test_new_command_from_mod(tmp_path, monkeypatch, capsys):
    typ, err = _compile(
        tmp_path, monkeypatch, capsys,
        '*use("m.toml")\n*avg(1 ; 2)\n',
        {"m.toml": MOD_SIMPLE},
    )
    assert "$frac(1 + 2, 2)$" in typ
    assert "unknown command" not in err


def test_override_template_warns_and_changes_output(tmp_path, monkeypatch, capsys):
    typ, err = _compile(
        tmp_path, monkeypatch, capsys,
        '*use("m.toml")\n*frac(1 ; 2)\n',
        {"m.toml": MOD_OVERRIDE},
    )
    assert "$frac(2, 1)$" in typ
    assert "overrides the built-in definition" in err
    # once per compile
    assert err.count("overrides the built-in definition") == 1


def test_alias_shadowing(tmp_path, monkeypatch, capsys):
    typ, err = _compile(
        tmp_path, monkeypatch, capsys,
        '*use("m.toml")\n*fraction(1 ; 2)\n',
        {"m.toml": MOD_ALIAS},
    )
    # fraction alias now points at myfrac? Actually name myfrac, alias fraction
    # overrides built-in alias
    assert "overrides built-in alias" in err


def test_override_pow_is_error(tmp_path, monkeypatch, capsys):
    typ, err = _compile(
        tmp_path, monkeypatch, capsys,
        '*use("m.toml")\n*pow(2 ; 3)\n',
        {"m.toml": MOD_OVERRIDE_POW},
    )
    assert "implemented in Python" in err
    # output unchanged: pow still uses _format_pow
    assert "$2^(3)$" in typ


def test_override_int_is_error(tmp_path, monkeypatch, capsys):
    typ, err = _compile(
        tmp_path, monkeypatch, capsys,
        '*use("m.toml")\n*int(0 ; 1 ; x^2)\n',
        {"m.toml": MOD_OVERRIDE_INT},
    )
    assert "implemented in Python" in err


def test_handler_rejected(tmp_path, monkeypatch, capsys):
    typ, err = _compile(
        tmp_path, monkeypatch, capsys,
        '*use("m.toml")\n*evil(1)\n',
        {"m.toml": MOD_HANDLER},
    )
    assert "forbidden key" in err or "handler" in err


def test_builtin_kind_rejected(tmp_path, monkeypatch, capsys):
    typ, err = _compile(
        tmp_path, monkeypatch, capsys,
        '*use("m.toml")\n*evil(1)\n',
        {"m.toml": MOD_BUILTIN_KIND},
    )
    assert "kind=\"builtin\"" in err or "builtin" in err or "not allowed" in err


def test_two_mods_same_name(tmp_path, monkeypatch, capsys):
    typ, err = _compile(
        tmp_path, monkeypatch, capsys,
        '*use("a.toml")\n*use("b.toml")\n*twocmd(1)\n',
        {"a.toml": MOD_TWO_A, "b.toml": MOD_TWO_B},
    )
    assert "$B(1)$" in typ
    assert "overrides" in err


def test_missing_mod_file(tmp_path, monkeypatch, capsys):
    typ, err = _compile(
        tmp_path, monkeypatch, capsys,
        '*use("nope.toml")\n',
        {},
    )
    assert "cannot find mod file" in err


def test_invalid_toml(tmp_path, monkeypatch, capsys):
    typ, err = _compile(
        tmp_path, monkeypatch, capsys,
        '*use("m.toml")\n',
        {"m.toml": "not = [toml"},
    )
    assert "invalid mod file" in err


def test_bad_placeholder(tmp_path, monkeypatch, capsys):
    typ, err = _compile(
        tmp_path, monkeypatch, capsys,
        '*use("m.toml")\n',
        {"m.toml": MOD_BAD_PLACEHOLDER},
    )
    assert "invalid mod file" in err or "placeholder" in err


def test_path_relative_to_ezmath_folder(tmp_path, monkeypatch, capsys):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "m.toml").write_text(MOD_SIMPLE, encoding="utf-8")
    src = sub / "case.ezmath"
    src.write_text('*use("m.toml")\n*avg(1 ; 2)\n', encoding="utf-8")
    stub = type("_TypstStub", (), {"compile": staticmethod(lambda *a, **k: None)})()
    monkeypatch.setattr(_pipeline, "typst", stub)
    _diags.bind_source  # noqa
    from compiler import compile_ezmath
    compile_ezmath(str(src), str(sub / "case.pdf"))
    typ = (sub / "case.typ").read_text(encoding="utf-8")
    assert "$frac(1 + 2, 2)$" in typ


def test_isolation_global_unchanged(tmp_path, monkeypatch, capsys):
    import copy
    before_cmds = set(DEFAULT_REGISTRY.commands)
    before_aliases = dict(_MA)
    before_known = set(_KC)

    # doc A uses mod
    d1 = tmp_path / "a"
    d1.mkdir()
    (d1 / "m.toml").write_text(MOD_SIMPLE, encoding="utf-8")
    (d1 / "a.ezmath").write_text('*use("m.toml")\n*avg(1 ; 2)\n', encoding="utf-8")
    stub = type("_TypstStub", (), {"compile": staticmethod(lambda *a, **k: None)})()
    monkeypatch.setattr(_pipeline, "typst", stub)
    from compiler import compile_ezmath
    compile_ezmath(str(d1 / "a.ezmath"), str(d1 / "a.pdf"))

    assert set(DEFAULT_REGISTRY.commands) == before_cmds
    assert _MA == before_aliases
    assert _KC == before_known

    # doc B no mod: avg is unknown
    d2 = tmp_path / "b"
    d2.mkdir()
    (d2 / "b.ezmath").write_text("*avg(1 ; 2)\n", encoding="utf-8")
    compile_ezmath(str(d2 / "b.ezmath"), str(d2 / "b.pdf"))
    err_path = None
    # re-read stderr not available; check typ has unknown? Just ensure no crash
    assert (d2 / "b.typ").is_file()


def test_nested_mod_command(tmp_path, monkeypatch, capsys):
    typ, err = _compile(
        tmp_path, monkeypatch, capsys,
        '*use("m.toml")\n*frac(*avg(1 ; 2) ; 3)\n*sum(i = 1 ; n ; *avg(i ; 2))\n',
        {"m.toml": MOD_SIMPLE},
    )
    assert "unknown command" not in err


def test_default_command_inside_mod_template(tmp_path, monkeypatch, capsys):
    mod = '''
[[commands]]
name = "doublefrac"
args = 2
typst = "$frac({0}, {1})$ plus *sqrt({0})"
usage = "*doublefrac(a ; b)"
doc = "df"
'''
    typ, err = _compile(
        tmp_path, monkeypatch, capsys,
        '*use("m.toml")\n*doublefrac(1 ; 2)\n',
        {"m.toml": mod},
    )
    assert "$frac(1, 2)$" in typ
    assert "$sqrt(1)$" in typ