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
            if not inner.isdigit():
                return False, (
                    'invalid placeholder "{" + inner + "}" in typst template; '
                    'only {N} is allowed')
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
            if not inner.isdigit():
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


def load_mod_text(text, *, allow_builtin=False, source_name='<mod>'):
    """Parse *text* as a mod file and return a list of CommandSpec.

    Diagnostics are reported through the diagnostics system. Returns an
    empty list on a hard parse failure.
    """
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        lineno = getattr(exc, 'lineno', None)
        report('Error', lineno,
               f'invalid mod file {source_name}: {exc}')
        return []
    except Exception as exc:  # pragma: no cover - defensive
        report('Error', None, f'invalid mod file {source_name}: {exc}')
        return []

    if not isinstance(data, dict):
        report('Error', None, f'invalid mod file {source_name}: top level must be a table')
        return []

    entries = data.get('commands', None)
    if entries is None:
        # Allow a bare list under "commands"? tomllib needs key.
        if 'command' in data:
            entries = data['command']
        else:
            report('Error', None,
                   f'invalid mod file {source_name}: missing "commands" array')
            return []
    if not isinstance(entries, list):
        report('Error', None,
               f'invalid mod file {source_name}: "commands" must be an array of tables')
        return []

    specs = []
    seen_names = set()
    seen_aliases = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            report('Error', None,
                   f'invalid mod file {source_name}: entry {index} is not a table')
            continue
        # Unknown / forbidden keys.
        unknown = set(entry) - _ALLOWED_KEYS
        if unknown:
            # Forbidden keys are a subset of unknown from the allowed set's
            # point of view; report a clearer message for them.
            forbidden = set(entry) & _FORBIDDEN_KEYS
            if forbidden:
                report('Error', None,
                       f'invalid mod file {source_name}: forbidden key '
                       f'{sorted(forbidden)!r} (handler/builtin kinds are not '
                       f'allowed in user mods)')
                continue
            report('Error', None,
                   f'invalid mod file {source_name}: unknown key(s) '
                   f'{sorted(unknown)!r}')
            continue

        name = entry.get('name')
        if not isinstance(name, str) or not name.strip():
            report('Error', None,
                   f'invalid mod file {source_name}: entry {index} missing "name"')
            continue
        name = name.strip()

        args = entry.get('args')
        if not isinstance(args, int) or isinstance(args, bool) or args < 1:
            report('Error', None,
                   f'invalid mod file {source_name}: command {name!r} has '
                   f'invalid "args" (must be a positive integer)')
            continue

        aliases = entry.get('aliases', [])
        if aliases is None:
            aliases = []
        if not isinstance(aliases, list) or any(not isinstance(a, str) for a in aliases):
            report('Error', None,
                   f'invalid mod file {source_name}: command {name!r} has '
                   f'invalid "aliases" (must be an array of strings)')
            continue
        aliases = [a.strip() for a in aliases]

        kind = entry.get('kind', _TEMPLATE_KIND)
        if not isinstance(kind, str) or kind not in _ALLOWED_KINDS:
            report('Error', None,
                   f'invalid mod file {source_name}: command {name!r} has '
                   f'unknown kind {kind!r}')
            continue

        typst = entry.get('typst', None)
        if typst is not None and not isinstance(typst, str):
            report('Error', None,
                   f'invalid mod file {source_name}: command {name!r} has '
                   f'invalid "typst" (must be a string)')
            continue

        # Determine effective kind.
        if kind == _BUILTIN_KIND:
            if typst is not None:
                report('Error', None,
                       f'invalid mod file {source_name}: command {name!r} '
                       f'cannot declare both kind="builtin" and "typst"')
                continue
            if not allow_builtin:
                report('Error', None,
                       f'invalid mod file {source_name}: command {name!r} '
                       f'uses kind="builtin", which is not allowed in user mods')
                continue
        else:
            # template kind
            if typst is None:
                report('Error', None,
                       f'invalid mod file {source_name}: command {name!r} '
                       f'missing "typst" template')
                continue
            if not allow_builtin and kind == _BUILTIN_KIND:
                pass
            ok, msg = _validate_template(typst, args, None)
            if not ok:
                report('Error', None,
                       f'invalid mod file {source_name}: command {name!r}: {msg}')
                continue

        usage = entry.get('usage', '')
        doc = entry.get('doc', '')
        if not isinstance(usage, str):
            usage = ''
        if not isinstance(doc, str):
            doc = ''

        # Duplicate names / aliases within one file.
        if name in seen_names:
            report('Error', None,
                   f'invalid mod file {source_name}: duplicate command name '
                   f'{name!r}')
            continue
        dup_alias = [a for a in aliases if a in seen_aliases or a in seen_names]
        # also collision with a canonical name in this file
        collides = False
        for a in aliases:
            if a in seen_names or a in seen_aliases:
                collides = True
                break
        if collides:
            report('Error', None,
                   f'invalid mod file {source_name}: duplicate alias in '
                   f'command {name!r}')
            continue

        # User mods may not override builtin kinds or aliases? Overriding is
        # handled by the caller (registry merge); here we just build specs.
        seen_names.add(name)
        seen_aliases.update(aliases)
        specs.append(CommandSpec(
            name=name, args=args, aliases=aliases, typst=typst,
            usage=usage, doc=doc, kind=kind, source=source_name,
        ))

    return specs


def load_mod_file(path, *, allow_builtin=False):
    """Load a mod file from *path*; report and return [] on any error."""
    try:
        with open(path, 'rb') as fh:
            raw = fh.read()
        text = raw.decode('utf-8')
    except OSError as exc:
        report('Error', None, f'cannot read mod file {path}: {exc}')
        return []
    return load_mod_text(text, allow_builtin=allow_builtin, source_name=path)


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
    # pad (should not happen: replace_math_call slices)
    while len(cleaned) < spec.args:
        cleaned.append('')
    return render_template(spec.typst, cleaned)