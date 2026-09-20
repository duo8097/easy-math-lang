"""Comment stripping (// comments, with URL protection)."""

import re


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
    """Ranges where // must not start a comment: calc(...), *p(...)."""
    ranges = []
    for opener in ('calc(', '*p('):
        ranges.extend(_balanced_spans(line, opener))
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
        # Protect URL schemes (https://, http://, ftp://) from // comment stripping
        placeholder = '\x00URLSLASH\x00'
        line_prot = re.sub(r'([A-Za-z][A-Za-z0-9+.-]*://)', lambda m: m.group(1).replace('/', placeholder), raw_line)
        protected = _protected_ranges(line_prot)
        idx = _find_comment_start(line_prot, protected)
        if idx != -1:
            line_prot = line_prot[:idx]
        line = line_prot.replace(placeholder, '/')
        cleaned_lines.append(line)
    return '\n'.join(cleaned_lines)
