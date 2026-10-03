"""Variable (<name>) and define (bare-word) substitution."""

import re
import sys


def _expand_single_var(ctx, name, _stack):
    """Recursively expand one variable value; None on cycle."""
    if name in _stack:
        print(
            f'[WARNING] Circular variable reference detected: <{name}>. '
            f'Leaving unexpanded.',
            file=sys.stderr,
        )
        return None
    if name not in ctx.variables:
        return None
    _stack.add(name)
    try:
        val = str(ctx.variables[name])

        def _inner(m):
            inner = m.group(1).strip()
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', inner):
                return m.group(0)
            if inner in _stack:
                print(
                    f'[WARNING] Circular variable reference detected: <{inner}>. '
                    f'Leaving unexpanded.',
                    file=sys.stderr,
                )
                return m.group(0)
            if inner not in ctx.variables:
                return m.group(0)
            expanded = _expand_single_var(ctx, inner, _stack)
            return expanded if expanded is not None else m.group(0)

        # Guard << >> operator adjacency inside values as well.
        # Use a single pass over the original value so offsets stay valid.
        parts = []
        var_inner_pat = re.compile(r'<\s*([A-Za-z_][A-Za-z0-9_]*)\s*>')
        for m in var_inner_pat.finditer(val):
            s, e = m.start(), m.end()
            if (s > 0 and val[s - 1] == '<') or (e < len(val) and val[e] == '>'):
                continue
            parts.append((m, _inner(m)))
        # Apply replacements back-to-front so offsets stay valid.
        result = val
        for m, rep in reversed(parts):
            result = result[:m.start()] + rep + result[m.end():]
        return result
    finally:
        _stack.discard(name)


def replace_vars(ctx, text, _visited=None):
    """Expand <var> tokens; circular references are left unexpanded."""
    # _visited kept for backwards compatibility; expansion now uses a
    # per-occurrence recursion stack so sibling tokens never poison
    # each other.
    _ = _visited
    var_pat = re.compile(r'<\s*([A-Za-z_][A-Za-z0-9_]*)\s*>')
    matches = list(var_pat.finditer(text))
    if not matches:
        return text
    replacements = []
    for m in matches:
        s, e = m.start(), m.end()
        # Skip << B >> style operators: a match touching another
        # angle bracket belongs to a multi-char symbol, not a variable.
        if (s > 0 and text[s - 1] == '<') or (e < len(text) and text[e] == '>'):
            continue
        name = m.group(1).strip()
        if name not in ctx.variables:
            continue
        expanded = _expand_single_var(ctx, name, set())
        if expanded is None:
            continue
        replacements.append((s, e, expanded))
    result = text
    for s, e, rep in reversed(replacements):
        result = result[:s] + rep + result[e:]
    return result


def replace_defines(ctx, text):
    """Brackets-only rule: bare words are text, never expanded.

    Only ``<name>`` references expand (handled by :func:`replace_vars`,
    since defines are also stored in ``ctx.variables``). Bare words
    without ``<>`` stay literal text, so ordinary prose like
    "the width is large" is never corrupted by a define named
    ``width``. Kept as a no-op for backward compatibility with
    callers; all expansion flows through ``replace_vars``.
    """
    return text


def check_undefined_vars(text, line_no, ctx=None):
    """Report identifier-like <name> tokens with no definition (hard error)."""
    original = text
    matches = list(re.finditer(r'<([^<>]+)>', original))
    # Collect distinct undefined names first; apply replacements after
    # the loop so match offsets (from the original string) stay valid.
    undefined = []
    seen = set()
    for match in matches:
        name = match.group(1)
        # Only flag identifier-like names (tmp1, width). Symbol
        # shortcuts such as <=> / -> / => contain non-identifier
        # chars and are handled later by replace_symbol_shortcuts.
        if not re.fullmatch(r'\s*[A-Za-z_][A-Za-z0-9_]*\s*', name):
            continue
        # Skip matches touching another angle bracket: those belong to
        # multi-char ASCII operators (<< B >>) handled later by
        # replace_symbol_shortcuts, not to variables.
        if match.start() > 0 and original[match.start() - 1] == '<':
            continue
        if match.end() < len(original) and original[match.end()] == '>':
            continue
        stripped = name.strip()
        # Defined (even if circular and left unexpanded) is not undefined.
        if ctx is not None and stripped in ctx.variables:
            continue
        if ctx is not None and stripped in ctx.defines:
            continue
        key = f'<{name}>'
        if key in seen:
            continue
        seen.add(key)
        undefined.append((key, stripped))
    for key, stripped in undefined:
        print(
            f'[Error] Line {line_no}: undefined variable <{stripped}>',
            file=sys.stderr,
        )
        text = text.replace(key, f'[UNDEFINED: <{stripped}>]')
    return text
