"""Math command registry loaded from a TOML "mod" file.

A registry is the single source of truth for the *names*, *aliases*,
*minimum argument counts*, *usage* and *documentation* of math commands.
Simple commands also carry a ``typst`` template that is rendered by
substituting the already-cleaned arguments ``{0}``, ``{1}``, ... into it.
Complex commands (int, diff, cases, ...) keep their Python logic and are
registered with ``kind = "builtin"`` (name/args/aliases/usage/doc only).

The default registry is built from ``commands.toml`` next to this module.
User-supplied mod files are loaded with :func:`load_mod_text` /
:func:`load_mod_file` with ``allow_builtin=False``, so they can only add or
override *template* commands.
"""
from __future__ import annotations

import os
import sys
import tomllib

from .diagnostics import report

# Keys a mod entry may contain. ``handler`` is deliberately absent: it is
# never accepted (not even in the default file).
_ALLOWED_KEYS = frozenset(
    {'name', 'args', 'aliases', 'typst', 'usage', 'doc', 'kind'}
)

# Kinds an entry may declare.
_TEMPLATE_KIND = 'template'
_BUILTIN_KIND = 'builtin'
_ALLOWED_KINDS = frozenset({_TEMPLATE_KIND, _BUILTIN_KIND})

# Keys that are forbidden in every mod file (including the default one).
_FORBIDDEN_KEYS = frozenset({'handler'})


class CommandSpec:
    """One command entry from a mod file."""

    __slots__ = ('name', 'args', 'aliases', 'typst', 'usage', 'doc', 'kind',
                 'source')

    def __init__(self, name, args, aliases, typst, usage, doc, kind, source):
        self.name = name
        self.args = args
        self.aliases = list(aliases or [])
        self.typst = typst
        self.usage = usage or ''
        self.doc = doc or ''
        self.kind = kind
        self.source = source  # path/label of the mod file

    @property
    def is_template(self):
        return self.kind == _TEMPLATE_KIND

    @property
    def is_builtin(self):
        return self.kind == _BUILTIN_KIND


class Registry:
    """A collection of command specs plus derived alias map."""

    def __init__(self, specs, source_label='default'):
        self.source_label = source_label
        # canonical name -> spec
        self.commands = {}
        # alias -> canonical
        self.aliases = {}
        for spec in specs:
            self.commands[spec.name] = spec
            for alias in spec.aliases:
                self.aliases[alias] = spec.name

    def all_command_names(self):
        return set(self.commands) | set(self.aliases)

    def template_specs(self):
        return [s for s in self.commands.values() if s.is_template]

    def builtin_specs(self):
        return [s for s in self.commands.values() if s.is_builtin]


def _validate_template(template, args, line_hint):
    """Tokenize *template*; return (ok, message).

    Accepts only ``{N}``, ``{{`` and ``}}``. Every ``{N}`` must satisfy
    ``N < args``.
    """
    i = 0
    n = len(template)
    while i < n:
        ch = template[i]
        if ch == '{':
            if i + 1 < n and template[i + 1] == '{':
                i += 2
                continue
            end = template.find('}', i)
            if end == -1:
                return False, 'unclosed "{" in typst template'
            inner = template[i + 1:end]
            if not (inner.isascii() and inner.isdigit()):
                return False, (
                    f'invalid placeholder "{{{inner}}}" in typst template; '
                    f'only {{N}} is allowed')
            idx = int(inner)
            if idx >= args:
                return False, (
                    f'typst template references {{{idx}}} but command has '
                    f'only {args} argument(s)')
            i = end + 1
        elif ch == '}':
            if i + 1 < n and template[i + 1] == '}':
                i += 2
                continue
            return False, 'unescaped "}" in typst template'
        else:
            i += 1
    return True, ''


def render_template(template, values):
    """Render *template* with *values* (already-cleaned arg strings).

    Only ``{N}``, ``{{`` and ``}}`` are interpreted; everything else is
    literal. Raises ValueError on malformed input (callers validate first).
    """
    out = []
    i = 0
    n = len(template)
    while i < n:
        ch = template[i]
        if ch == '{':
            if i + 1 < n and template[i + 1] == '{':
                out.append('{')
                i += 2
                continue
            end = template.find('}', i)
            if end == -1:
                raise ValueError('unclosed "{" in typst template')
            inner = template[i + 1:end]
            if not (inner.isascii() and inner.isdigit()):
                raise ValueError('invalid placeholder in typst template')
            idx = int(inner)
            if idx >= len(values):
                raise ValueError('placeholder index out of range')
            out.append(values[idx])
            i = end + 1
        elif ch == '}':
            if i + 1 < n and template[i + 1] == '}':
                out.append('}')
                i += 2
                continue
            raise ValueError('unescaped "}" in typst template')
        else:
            out.append(ch)
            i += 1
    return ''.join(out)


def load_mod_text(text, *, allow_builtin=False, source_name='<mod>',
                  line_no=None):
    """Parse *text* as a mod file and return a list of CommandSpec.

    Diagnostics are reported through the diagnostics system. Returns an
    empty list on a hard parse failure.
    """
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        lineno = getattr(exc, 'lineno', None)
        detail = f'invalid mod file {source_name}: {exc}'
        if lineno is not None:
            detail += f' (line {lineno})'
        report('Error', line_no, detail)
        return []
    except Exception as exc:  # pragma: no cover - defensive
        report('Error', line_no, f'invalid mod file {source_name}: {exc}')
        return []

    if not isinstance(data, dict):
        report('Error', line_no, f'invalid mod file {source_name}: top level must be a table')
        return []

    entries = data.get('commands', None)
    if entries is None:
        # Allow a bare list under "commands"? tomllib needs key.
        if 'command' in data:
            entries = data['command']
        else:
            report('Error', line_no,
                   f'invalid mod file {source_name}: missing "commands" array')
            return []
    if not isinstance(entries, list):
        report('Error', line_no,
               f'invalid mod file {source_name}: "commands" must be an array of tables')
        return []

    specs = []
    seen_names = set()
    seen_aliases = set()

    def _one(entry, index):
        nonlocal specs
        if not isinstance(entry, dict):
            report('Error', line_no,
                   f'invalid mod file {source_name}: entry {index} is not a table')
            return
        # Unknown / forbidden keys.
        unknown = set(entry) - _ALLOWED_KEYS
        if unknown:
            forbidden = set(entry) & _FORBIDDEN_KEYS
            if forbidden:
                report('Error', line_no,
                       f'invalid mod file {source_name}: forbidden key '
                       f'{sorted(forbidden)!r} (handler/builtin kinds are not '
                       f'allowed in user mods)')
                return
            report('Error', line_no,
                   f'invalid mod file {source_name}: unknown key(s) '
                   f'{sorted(unknown)!r}')
            return

        name = entry.get('name')
        if not isinstance(name, str) or not name.strip():
            report('Error', line_no,
                   f'invalid mod file {source_name}: entry {index} missing "name"')
            return
        name = name.strip()

        args = entry.get('args')
        if not isinstance(args, int) or isinstance(args, bool) or args < 1:
            report('Error', line_no,
                   f'invalid mod file {source_name}: command {name!r} has '
                   f'invalid "args" (must be a positive integer)')
            return

        aliases = entry.get('aliases', [])
        if aliases is None:
            aliases = []
        if not isinstance(aliases, list) or any(not isinstance(a, str) for a in aliases):
            report('Error', line_no,
                   f'invalid mod file {source_name}: command {name!r} has '
                   f'invalid "aliases" (must be an array of strings)')
            return
        aliases = [a.strip() for a in aliases]

        kind = entry.get('kind', _TEMPLATE_KIND)
        if not isinstance(kind, str) or kind not in _ALLOWED_KINDS:
            report('Error', line_no,
                   f'invalid mod file {source_name}: command {name!r} has '
                   f'unknown kind {kind!r}')
            return

        typst = entry.get('typst', None)
        if typst is not None and not isinstance(typst, str):
            report('Error', line_no,
                   f'invalid mod file {source_name}: command {name!r} has '
                   f'invalid "typst" (must be a string)')
            return

        if kind == _BUILTIN_KIND:
            if typst is not None:
                report('Error', line_no,
                       f'invalid mod file {source_name}: command {name!r} '
                       f'cannot declare both kind="builtin" and "typst"')
                return
            if not allow_builtin:
                report('Error', line_no,
                       f'invalid mod file {source_name}: command {name!r} '
                       f'uses kind="builtin", which is not allowed in user mods')
                return
        else:
            if typst is None:
                report('Error', line_no,
                       f'invalid mod file {source_name}: command {name!r} '
                       f'missing "typst" template')
                return
            ok, msg = _validate_template(typst, args, None)
            if not ok:
                report('Error', line_no,
                       f'invalid mod file {source_name}: command {name!r}: {msg}')
                return

        usage = entry.get('usage', '')
        doc = entry.get('doc', '')
        if not isinstance(usage, str):
            usage = ''
        if not isinstance(doc, str):
            doc = ''

        if name in seen_names:
            report('Error', line_no,
                   f'invalid mod file {source_name}: duplicate command name '
                   f'{name!r}')
            return
        collides = any(a in seen_names or a in seen_aliases for a in aliases)
        if collides:
            report('Error', line_no,
                   f'invalid mod file {source_name}: duplicate alias in '
                   f'command {name!r}')
            return

        seen_names.add(name)
        seen_aliases.update(aliases)
        specs.append(CommandSpec(
            name=name, args=args, aliases=aliases, typst=typst,
            usage=usage, doc=doc, kind=kind, source=source_name,
        ))

    for index, entry in enumerate(entries):
        try:
            _one(entry, index)
        except Exception as exc:  # never crash the build
            report('Error', line_no,
                   f'invalid mod file {source_name}: entry {index}: {exc}')

    return specs


def load_mod_file(path, *, allow_builtin=False, line_no=None):
    """Load a mod file from *path*; report and return [] on any error."""
    try:
        with open(path, 'rb') as fh:
            raw = fh.read()
        text = raw.decode('utf-8')
    except OSError as exc:
        report('Error', line_no, f'cannot read mod file {path}: {exc}')
        return []
    return load_mod_text(text, allow_builtin=allow_builtin,
                         source_name=path, line_no=line_no)


def _default_toml_path():
    frozen = getattr(sys, '_MEIPASS', None)
    if frozen:
        for cand in (os.path.join(frozen, 'compiler', 'commands.toml'),
                     os.path.join(frozen, 'commands.toml')):
            if os.path.isfile(cand):
                return cand
    here = os.path.dirname(os.path.abspath(__file__))
    cand = os.path.join(here, 'commands.toml')
    return cand


_DEFAULT_TOML = _default_toml_path()


def _base_kind(commands, aliases, name):
    if name in commands:
        return commands[name].kind
    if name in aliases:
        canon = aliases[name]
        if canon in commands:
            return commands[canon].kind
    return None


def merge_registries(base, mods):
    """Layer user mods on top of *base*; return a NEW registry.

    *mods* is a list of ``(label, specs)`` pairs in load order. Warnings
    and errors are reported through the diagnostics system. The inputs are
    never mutated.
    """
    commands = {n: s for n, s in base.commands.items()}
    aliases = dict(base.aliases)
    origin = {}
    for name in commands:
        origin[name] = 'built-in'
    for alias in aliases:
        origin[alias] = 'built-in'

    for mod_label, specs in mods:
        for spec in specs:
            skip = False
            # Command-name collision.
            if spec.name in commands or spec.name in aliases:
                kind = _base_kind(commands, aliases, spec.name)
                if kind == _BUILTIN_KIND:
                    report('Error', None,
                           f"command '{spec.name}' is implemented in Python "
                           f"and cannot be overridden")
                    skip = True
                else:
                    if spec.name in aliases:
                        canon = aliases[spec.name]
                        if origin.get(spec.name) == 'built-in':
                            report('Warning', None,
                                   f"command '{spec.name}' overrides "
                                   f"built-in alias '{spec.name}' "
                                   f"(of *{canon})")
                        else:
                            report('Warning', None,
                                   f"command '{spec.name}' in {mod_label} "
                                   f"overrides {origin.get(spec.name)}")
                    else:
                        if origin.get(spec.name) == 'built-in':
                            report('Warning', None,
                                   f"command '{spec.name}' overrides the "
                                   f"built-in definition")
                        else:
                            report('Warning', None,
                                   f"command '{spec.name}' in {mod_label} "
                                   f"overrides {origin.get(spec.name)}")

            # Alias collisions.
            if not skip:
                for alias in spec.aliases:
                    if alias in commands or alias in aliases:
                        kind = _base_kind(commands, aliases, alias)
                        if kind == _BUILTIN_KIND:
                            report('Error', None,
                                   f"command '{spec.name}' is implemented "
                                   f"in Python and cannot be overridden")
                            skip = True
                            break
                        if alias in aliases:
                            canon = aliases[alias]
                            if origin.get(alias) == 'built-in':
                                report('Warning', None,
                                       f"overrides built-in alias "
                                       f"'{alias}' (of *{canon})")
                            else:
                                report('Warning', None,
                                       f"alias '{alias}' in {mod_label} "
                                       f"overrides {origin.get(alias)}")
                        else:
                            if origin.get(alias) == 'built-in':
                                report('Warning', None,
                                       f"command '{alias}' overrides the "
                                       f"built-in definition")
                            else:
                                report('Warning', None,
                                       f"command '{alias}' in {mod_label} "
                                       f"overrides {origin.get(alias)}")

            if skip:
                continue

            # Replace an existing command: drop its stale aliases.
            if spec.name in commands:
                old_spec = commands[spec.name]
                for a in old_spec.aliases:
                    if aliases.get(a) == spec.name and a not in spec.aliases:
                        del aliases[a]
                        origin.pop(a, None)

            commands[spec.name] = spec
            origin[spec.name] = mod_label
            for alias in spec.aliases:
                aliases[alias] = spec.name
                origin[alias] = mod_label

    reg = Registry.__new__(Registry)
    reg.source_label = 'layered'
    reg.commands = commands
    reg.aliases = aliases
    return reg


def load_default_registry():
    specs = load_mod_file(_DEFAULT_TOML, allow_builtin=True)
    return Registry(specs, source_label='default')


# Module-level default registry, built once.
DEFAULT_REGISTRY = load_default_registry()


def render_spec(spec, ctx, args):
    """Render a template spec given cleaned args (raw args -> cleaned)."""
    from . import math_commands as _mc
    if not spec.is_template:
        return None
    cleaned = [_mc.clean_inner_math(ctx, a) for a in args[:spec.args]]
    while len(cleaned) < spec.args:
        cleaned.append('')
    rendered = render_template(spec.typst, cleaned)
    try:
        rendered = _mc.normalize_friendly_calls(
            rendered, getattr(ctx, 'registry', None))
        for fn_name, fn_min, fn_fmt in _mc.math_call_specs(ctx):
            rendered = _mc.replace_math_call(
                rendered, fn_name, fn_min, fn_fmt, line_no=None)
        rendered = _mc.replace_int_calls(rendered, ctx, line_no=None)
        rendered = _mc.replace_diff_calls(rendered, ctx, line_no=None)
        rendered = _mc.replace_cases_call(rendered, ctx, line_no=None)
        rendered = _mc.replace_det_calls(rendered, ctx, line_no=None)
        rendered = _mc.replace_set_calls(rendered, ctx, line_no=None)
        rendered = _mc.replace_align_calls(rendered, ctx, line_no=None)
        rendered = _mc.replace_vec_calls(rendered, ctx, line_no=None)
    except Exception:  # pragma: no cover - defensive
        pass
    return rendered