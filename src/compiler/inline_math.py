"""Inline math mode: \\ ... \\  ->  Typst $ ... $.

Structural scanner (not a global string replace). Rules:

- ``\\\\`` is an escaped literal backslash and never toggles math mode.
- An unescaped ``\\`` toggles math mode (open -> close -> open ...).
- Whitespace just inside the delimiters is trimmed.
- Content is processed with the existing pipeline pieces (vars/defines
  are applied by the caller beforehand or inside; math commands,
  ``*pi``/``*infinity`` and ``replace_symbol_shortcuts`` are applied
  inside so ASCII/shortcut syntax keeps working).
- Empty ``\\ \\`` warns and emits nothing.
"""

import re
import sys

BS_PLACEHOLDER = '\x00BS\x00'


def mask_escaped(text):
    """Replace ``\\\\`` runs with placeholders so they never toggle math."""
    return text.replace('\\\\', BS_PLACEHOLDER)


def unmask_escaped(text):
    """Restore literal backslashes (Typst-escaped)."""
    return text.replace(BS_PLACEHOLDER, '\\\\')


def find_unescaped(text):
    """Positions of unescaped ``\\`` in text (``\\\\`` ignored)."""
    masked = mask_escaped(text)
    return [m.start() for m in re.finditer(r'\\', masked)]


def split_first_pair(text):
    """Split ``head \\ inner \\ tail`` on the first balanced pair.

    Returns (head, inner, tail) or None when there is no closing
    delimiter. ``\\\\`` sequences never count as delimiters.
    """
    masked = mask_escaped(text)
    first = masked.find('\\')
    if first == -1:
        return None
    second = masked.find('\\', first + 1)
    if second == -1:
        return None
    head = text[:first]
    inner = text[first + 1:second]
    tail = text[second + 1:]
    # Map masked offsets back: placeholder differs in length from '\\\\',
    # so recompute on the raw string with an escape-aware scan for safety.
    return _split_raw(text)


def _split_raw(text):
    """Escape-aware first-pair split on the raw string."""
    i, n = 0, len(text)
    # find opening unescaped backslash
    open_idx = -1
    while i < n:
        if text[i] == '\\':
            if i + 1 < n and text[i + 1] == '\\':
                i += 2
                continue
            open_idx = i
            break
        i += 1
    if open_idx == -1:
        return None
    j = open_idx + 1
    while j < n:
        if text[j] == '\\':
            if j + 1 < n and text[j + 1] == '\\':
                j += 2
                continue
            return text[:open_idx], text[open_idx + 1:j], text[j + 1:]
        j += 1
    return None


def process_math_inner(ctx, inner_raw, line_no=None):
    """Convert raw math content to Typst ``$...$`` (no surrounding text).

    Applies math commands, ``*pi``/``*infinity`` and the existing
    symbol-shortcut table (source of truth stays in ``symbols.py``).
    Returns the wrapped string, or '' for empty content (with warning).
    """
    from .math_commands import math_call_specs, replace_math_call
    from .symbols import replace_symbol_shortcuts

    inner = inner_raw.strip()
    if not inner:
        print(
            f'[WARNING] Line {line_no}: empty math expression '
            f'\\ \\ — emitting nothing.',
            file=sys.stderr,
        ) if line_no else None
        return ''
    for fn_name, fn_min, fn_fmt in math_call_specs(ctx):
        inner = replace_math_call(inner, fn_name, fn_min, fn_fmt)
    inner = re.sub(r'\*pi\b', '$pi$', inner)
    inner = re.sub(r'\*infinity\b', '$infinity$', inner)
    # Strip the temporary $ wrappers from *pi so the outer wrap stays clean:
    # '$pi$' inside becomes 'pi' inside the final '$...$'.
    inner = inner.replace('$pi$', 'pi').replace('$infinity$', 'infinity')
    inner = replace_symbol_shortcuts(inner)
    inner = inner.replace(BS_PLACEHOLDER, '\\\\')
    return f'${inner}$'
