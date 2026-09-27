"""Typst escaping and math-block helpers (outside-math only)."""

import re


def escape_typst_outside_math(content, escape_dollar=False):
    tokens = re.split(r'(\$.*?\$)', content)
    for i, token in enumerate(tokens):
        if not (token.startswith('$') and token.endswith('$') and len(token) >= 2):
            token = (
                token
                .replace('\\', r'\\')
                .replace('*', r'\*')
                .replace('_', r'\_')
                .replace('<', r'\<')
                .replace('>', r'\>')
                .replace('#', r'\#')
                .replace('@', r'\@')
                .replace('`', r'\`')
                # NOTE: '/' is escaped because Typst treats a leading '/' as a
                # definition-list term.  This is intentional and has been kept
                # unchanged pending a concrete regression report.
                .replace('/', r'\/')
            )
            if escape_dollar:
                # Lone '$' left over after $...$ math spans are split out
                # is a literal dollar, not math: escape for Typst.
                # Callers holding raw Typst (e.g. *p passthrough) must opt
                # out by leaving this False.
                token = token.replace('$', r'\$')
            tokens[i] = token
    out = ''.join(tokens)
    # Neutralize line-leading Typst block markup (= headings, - / + lists,
    # 1. enumerations): bare words are normal text per spec, so escape the
    # marker to keep it literal.
    lines = out.split('\n')
    for li, ln in enumerate(lines):
        m = re.match(r'^(\s*)(=|-|\+)(\s)', ln)
        if m:
            lines[li] = f"{m.group(1)}\\{m.group(2)}{m.group(3)}{ln[m.end():]}"
            continue
        if re.match(r'^\s*\d+\.\s', ln):
            idx = len(ln) - len(ln.lstrip())
            lines[li] = ln[:idx] + '\\' + ln[idx:]
    return '\n'.join(lines)


def merge_math(t):
    """Merge directly adjacent math spans ($a$$b$ / $a$ $b$) into one.

    Repeatedly collapses `$...$` pairs separated only by whitespace.
    Non-adjacent spans are left untouched.
    """
    prev = None
    while prev != t:
        prev = t
        t = re.sub(r'\$([^\$]+)\$\s*\$([^\$]+)\$', r'$\1 \2$', t)
    return t


def index_replacer(match):
    base = match.group(1)
    index = match.group(2)
    if len(index) == 1:
        return f'${base}_{index}$'
    return f'${base}_("{index}")$'
