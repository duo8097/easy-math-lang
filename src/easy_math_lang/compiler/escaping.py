"""Typst escaping and math-block helpers (outside-math only)."""

import re


def escape_typst_outside_math(content):
    tokens = re.split(r'(\$.*?\$)', content)
    for i, token in enumerate(tokens):
        if not (token.startswith('$') and token.endswith('$') and len(token) >= 2):
            tokens[i] = (
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
    return ''.join(tokens)


def merge_math(t):
    t = re.sub(r'\$([^\$]+)\$', lambda m: '$' + m.group(1).replace('$', '') + '$', t)
    return t


def index_replacer(match):
    base = match.group(1)
    index = match.group(2)
    if len(index) == 1:
        return f'${base}_{index}$'
    return f'${base}_("{index}")$'
