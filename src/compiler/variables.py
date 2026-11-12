"""Variable (<name>) and define (bare-word) substitution."""

import re

from .diagnostics import report, source_col_for

#: Maximum length of one expanded variable value (256 KiB). A few doubling
#: defines (``a = <b><b>`` chains) would otherwise expand exponentially and
#: hang or OOM the compiler; anything past this cap is left unexpanded
#: with a warning instead.
_EXPANSION_CAP = 256 * 1024


def _is_operand_char(ch):
    return bool(ch) and (ch.isalnum() or ch == '_')


def _looks_like_comparison(text, s, e):
    """True when a ``<token>`` match sits glued between two operands.

    ``0<x>1`` (and ``a<b>c``) read as chained comparisons, not variable
    references: both neighbours of the ``<x>`` token are operand
    characters. A variable alone on either side (``calc(<x>+1)``) stays
    a variable — only a both-sides-glued token is treated as an
    operator. Spaced comparisons (``x < y``) never match anyway.
    """
    before = text[s - 1] if s > 0 else ''
    after = text[e] if e < len(text) else ''
    return _is_operand_char(before) and _is_operand_char(after)


def _expand_single_var(ctx, name, _stack, _depth=0):
    """Recursively expand one variable value; None on cycle."""
    if _depth > 100:
        report(
            'WARNING', None,
            f'Variable expansion too deep (possible long chain): <{name}>. '
            f'Leaving unexpanded.',
        )
        return None
    if name in _stack:
        report(
            'WARNING', None,
            f'Circular variable reference detected: <{name}>. '
            f'Leaving unexpanded.',
        )
        return None
    if name not in ctx.variables:
        return None
    # Memoize per compile: sibling tokens and repeated references reuse
    # the same expansion instead of re-walking the tree every time.
    # Entries are keyed by the variable's current raw value, so a
    # redefined variable is never served from a stale expansion.
    cache = getattr(ctx, '_expansion_cache', None)
    if cache is None:
        cache = ctx._expansion_cache = {}
    else:
        cached = cache.get(name)
        if cached is not None and cached[0] == str(ctx.variables[name]):
            return cached[1]
    _stack.add(name)
    try:
        val = str(ctx.variables[name])

        def _inner(m):
            inner = m.group(1).strip()
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', inner):
                return m.group(0)
            if inner in _stack:
                report(
                    'WARNING', None,
                    f'Circular variable reference detected: <{inner}>. '
                    f'Leaving unexpanded.',
                )
                return m.group(0)
            if inner not in ctx.variables:
                return m.group(0)
            expanded = _expand_single_var(ctx, inner, _stack, _depth + 1)
            return expanded if expanded is not None else m.group(0)

        # Guard << >> operator adjacency inside values as well.
        # Use a single pass over the original value so offsets stay valid.
        parts = []
        var_inner_pat = re.compile(r'<\s*([A-Za-z_][A-Za-z0-9_]*)\s*>')
        for m in var_inner_pat.finditer(val):
            s, e = m.start(), m.end()
            if (s > 0 and val[s - 1] == '<') or (e < len(val) and val[e] == '>'):
                continue
            if _looks_like_comparison(val, s, e):
                continue
            parts.append((m, _inner(m)))
        # Apply replacements back-to-front so offsets stay valid.
        result = val
        for m, rep in reversed(parts):
            result = result[:m.start()] + rep + result[m.end():]
            if len(result) > _EXPANSION_CAP:
                report(
                    'WARNING', None,
                    f'Variable <{name}> expands beyond '
                    f'{_EXPANSION_CAP} bytes — leaving it unexpanded.',
                )
                cache[name] = (str(ctx.variables[name]), None)
                return None
        cache[name] = (str(ctx.variables[name]), result)
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
        if _looks_like_comparison(text, s, e):
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
    replacements = []
    seen = set()
    occurrences = {}
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
        if _looks_like_comparison(original, match.start(), match.end()):
            continue
        # Idempotency for nested pipelines (e.g. table cells re-run
        # the full text pipeline): <name> inside an already-emitted
        # [UNDEFINED: <name>] placeholder must not warn twice.
        if match.start() >= 12 and original[match.start() - 12:match.start()] == '[UNDEFINED: ':
            if match.end() < len(original) and original[match.end()] == ']':
                continue
        stripped = name.strip()
        # Defined (even if circular and left unexpanded) is not undefined.
        if ctx is not None and stripped in ctx.variables:
            continue
        if ctx is not None and stripped in ctx.defines:
            continue
        token_occurrence = occurrences.get(stripped, 0)
        occurrences[stripped] = token_occurrence + 1
        if stripped not in seen:
            seen.add(stripped)
            occurrence = token_occurrence
            # Caret on the raw source line: the transformed text offsets
            # are not valid anchors, so find the token by regex there.
            pattern = r'<\s*' + re.escape(stripped) + r'\s*>'
            col, end_col = source_col_for(line_no, pattern, occurrence)
            report(
                'Error', line_no, f'undefined variable <{stripped}>',
                col=col, end_col=end_col,
            )
        replacements.append((match.start(), match.end(), stripped))
    for start, end, stripped in reversed(replacements):
        text = text[:start] + f'[UNDEFINED: <{stripped}>]' + text[end:]
    return text
