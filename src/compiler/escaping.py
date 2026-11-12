"""Typst escaping and math-block helpers (outside-math only)."""

import re


_URL_RE = re.compile(r'[A-Za-z][A-Za-z0-9+.-]*://[^\s$]+')
# Sentence punctuation that trails a URL in prose but is not part of it.
_URL_TRAILING = '.,;:!?)]}\'"”’'


def mask_urls(text):
    """Mask bare URLs so text passes can't corrupt them.

    Returns ``(masked, {ph: escaped_url})``. URLs are the one construct
    users paste verbatim; symbol/subscript/undefined-var passes would
    otherwise turn ``\u2026``, ``->`` and ``<x>`` inside them into math.
    Placeholders are digit-only control-char spans (never tokenized).
    Restore with :func:`restore_urls` after the escape step.
    """
    placeholders = {}

    def _mask(m):
        url = m.group(0)
        trimmed = ''
        while url and url[-1] in _URL_TRAILING:
            trimmed = url[-1] + trimmed
            url = url[:-1]
        ph = f'\x0b{len(placeholders)}\x0b'
        placeholders[ph] = escape_typst_outside_math(url)
        return ph + trimmed

    return _URL_RE.sub(_mask, text), placeholders


def restore_urls(text, placeholders):
    """Swap URL placeholders back (already Typst-escaped)."""
    for ph, escaped in placeholders.items():
        text = text.replace(ph, escaped)
    return text


def escape_brackets_outside_math(content):
    """Escape ``[``/``]`` outside ``$...$`` so they stay literal.

    Generated markup spans — ``#ident[...]`` with balanced brackets,
    e.g. the ``#strong[...]`` a styling command emits — are left alone:
    the brackets are syntax there, not user text. Nested markup
    (``#strong[#emph[...]]``) is handled by balanced depth. An
    unbalanced ``#ident[`` span is treated as user text and escaped.
    """
    markup_open = re.compile(r'#[A-Za-z_][A-Za-z0-9_-]*\[')

    def escape_run(run):
        out = []
        pos = 0
        while pos < len(run):
            m = markup_open.search(run, pos)
            if m is None:
                out.append(run[pos:].replace('[', r'\[').replace(']', r'\]'))
                break
            out.append(run[pos:m.start()].replace('[', r'\[').replace(']', r'\]'))
            depth = 1
            j = m.end()
            while j < len(run) and depth:
                if run[j] == '[':
                    depth += 1
                elif run[j] == ']':
                    depth -= 1
                j += 1
            if depth == 0:
                out.append(run[m.start():j])
                pos = j
            else:
                # Unbalanced generated-looking span: escape it like text.
                out.append(run[m.start():].replace('[', r'\[').replace(']', r'\]'))
                pos = len(run)
        return ''.join(out)

    parts = re.split(r'(\$.*?\$)', content)
    for i, token in enumerate(parts):
        if not (token.startswith('$') and token.endswith('$') and len(token) >= 2):
            parts[i] = escape_run(token)
    return ''.join(parts)


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
