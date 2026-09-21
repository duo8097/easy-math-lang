"""Comment stripping (// comments, with URL protection)."""

import re

from .inline_math import find_unescaped


def _math_ranges(line_prot):
    """Ranges covered by ``\\ ... \\`` math on one line (never comments).

    Balanced pairs protect the whole ``\\...\\`` span; a trailing
    unclosed opener (multiline math) protects through end of line,
    mirroring the pipeline's buffering.
    """
    positions = find_unescaped(line_prot)
    ranges = []
    for i in range(0, len(positions) - 1, 2):
        ranges.append((positions[i], positions[i + 1] + 1))
    if len(positions) % 2 == 1:
        ranges.append((positions[-1], len(line_prot)))
    return ranges


def _balanced_spans(line, opener):
    """Yield (start, end) spans of balanced opener(...) on one line."""
    pat_len = len(opener)
    pos = 0
    while True:
        s = line.find(opener, pos)
        if s == -1:
            return
        # calc( inside mycalc( is not a call; skip it.
        if opener == 'calc(' and s > 0 and (line[s - 1].isalnum() or line[s - 1] == '_'):
            pos = s + pat_len
            continue
        depth = 1
        i = s + pat_len
        while i < len(line) and depth > 0:
            if line[i] == '(':
                depth += 1
            elif line[i] == ')':
                depth -= 1
            i += 1
        if depth != 0:
            return
        yield (s, i)
        pos = i


def _protected_ranges(line):
    """Ranges where // must not start a comment.

    Covers calc(...), *p(...), any other balanced *command(...) span,
    while \\...\\ math is handled separately in strip_comments.
    """
    ranges = []
    for opener in ('calc(', '*p('):
        ranges.extend(_balanced_spans(line, opener))
    for m in re.finditer(r'\*[A-Za-z][A-Za-z0-9_]*\(', line):
        ranges.extend(_balanced_spans(line, m.group(0)))
    return ranges


def _find_comment_start(line_prot, protected):
    idx = line_prot.find('//')
    while idx != -1:
        if any(s <= idx < e for s, e in protected):
            idx = line_prot.find('//', idx + 2)
            continue
        return idx
    return -1


def strip_comments(text):
    cleaned_lines = []
    for raw_line in text.splitlines():
        # Protect full URLs (scheme://host/path...) from // comment
        # stripping — the old scheme-only shield let a later // in the
        # path start a bogus comment (https://example.com/a//b).
        placeholder = '\x00URLSLASH\x00'
        line_prot = re.sub(
            r'([A-Za-z][A-Za-z0-9+.-]*://\S*)',
            lambda m: m.group(1).replace('/', placeholder),
            raw_line,
        )
        protected = _protected_ranges(line_prot)
        protected.extend(_math_ranges(line_prot))
        idx = _find_comment_start(line_prot, protected)
        if idx != -1:
            line_prot = line_prot[:idx]
        line = line_prot.replace(placeholder, '/')
        cleaned_lines.append(line)
    return '\n'.join(cleaned_lines)
