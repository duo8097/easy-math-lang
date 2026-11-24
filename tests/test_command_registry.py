"""Tests for the TOML command registry (Phase 1)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from compiler import command_registry as cr  # noqa: E402


def test_default_mod_file_is_present_and_loads():
    assert os.path.isfile(cr._DEFAULT_TOML), cr._DEFAULT_TOML
    assert cr.DEFAULT_REGISTRY.commands, "default registry is empty"
    # Every spec has usage and doc (Phase 2 will enforce, but check here too).
    for spec in cr.DEFAULT_REGISTRY.commands.values():
        assert spec.usage, spec.name
        assert spec.doc, spec.name


def test_template_brace_escaping_cbrt():
    # cbrt template must produce a single pair of braces around the arg.
    spec = cr.DEFAULT_REGISTRY.commands['cbrt']
    assert cr.render_template(spec.typst, ['x']) == "$root(3, {x})$"


def test_template_rejects_bad_placeholder():
    # {3} with only 2 args is an error.
    specs = cr.load_mod_text(
        '''
        [[commands]]
        name = "boom"
        args = 2
        typst = "$x({3})$"
        usage = "*boom(a ; b)"
        doc = "boom"
        ''',
        allow_builtin=False, source_name='t.toml')
    assert specs == []


def test_template_rejects_unicode_and_malformed_placeholders():
    for template in ('$x({²})$', '$x({٣})$', '$x({ 0 })$', '$x({-1})$',
                     '$x({})$'):
        specs = cr.load_mod_text(
            f'''
            [[commands]]
            name = "boom"
            args = 1
            typst = "{template}"
            usage = "*boom(a)"
            doc = "boom"
            ''',
            allow_builtin=False, source_name='t.toml')
        assert specs == [], template


def test_invalid_placeholder_message_names_offending_text(capsys):
    cr.load_mod_text(
        '''
        [[commands]]
        name = "boom"
        args = 2
        typst = "$x({3})$"
        usage = "*boom(a ; b)"
        doc = "boom"
        ''',
        allow_builtin=False, source_name='t.toml')
    err = capsys.readouterr().err
    assert "{3}" in err


def test_template_rejects_unknown_keys():
    specs = cr.load_mod_text(
        '''
        [[commands]]
        name = "boom"
        args = 1
        typst = "$x({0})$"
        usage = "*boom(a)"
        doc = "boom"
        bogus = 1
        ''',
        allow_builtin=False, source_name='t.toml')
    assert specs == []


def test_handler_key_rejected():
    specs = cr.load_mod_text(
        '''
        [[commands]]
        name = "boom"
        args = 1
        handler = "m:f"
        usage = "*boom(a)"
        doc = "boom"
        ''',
        allow_builtin=False, source_name='t.toml')
    assert specs == []


def test_builtin_kind_rejected_in_user_mod():
    specs = cr.load_mod_text(
        '''
        [[commands]]
        name = "boom"
        args = 1
        kind = "builtin"
        usage = "*boom(a)"
        doc = "boom"
        ''',
        allow_builtin=False, source_name='t.toml')
    assert specs == []


def test_duplicate_name_rejected():
    specs = cr.load_mod_text(
        '''
        [[commands]]
        name = "boom"
        args = 1
        typst = "$x({0})$"
        usage = "*boom(a)"
        doc = "boom"

        [[commands]]
        name = "boom"
        args = 1
        typst = "$y({0})$"
        usage = "*boom(a)"
        doc = "boom2"
        ''',
        allow_builtin=False, source_name='t.toml')
    assert len(specs) == 1


def test_invalid_toml_does_not_crash():
    specs = cr.load_mod_text('not = [toml', source_name='t.toml')
    assert specs == []