"""Text/document commands: styling, page breaks, images.

- ``*bold(text)`` / ``*italic(text)`` / ``*underline(text)`` (short
  aliases ``*b`` / ``*i`` / ``*u``) render Typst ``#strong`` /
  ``#emph`` / ``#underline``. The whole inner text is the content
  (``,``/``;`` stay literal), so nesting, variables and ``calc()``
  work via the caller's cleaner.
- ``*newpage`` (alias ``*pagebreak``), bare or ``*newpage()``, emits
  a Typst page break.
- ``*image(path)`` / ``*image(path ; width)`` embeds an image file.
  Relative paths resolve from the ``.ezmath`` file's folder; the
  ``.typ`` embeds the typdir-relative path so the build stays
  relocatable (same discipline as plots/vecs, which embed basenames).
  Missing files and bad widths emit ``[Image Error: ...]`` inline
  plus an ``[Error]`` diagnostic without aborting the build.

All three expand to placeholder-protected Typst (``#`` must survive
the text escaper), restored by the pipeline after escaping — the
same protocol as plots/vecs.
"""

import os
import re
import sys

STYLE_NAMES = ('bold', 'italic', 'underline')

STYLE_ALIASES = {
    'b': 'bold',
    'i': 'italic',
    'u': 'underline',
}

# Typst function backing each style (verified to compile, including
# nested and inside math).
STYLE_TAGS = {
    'bold': 'strong',
    'italic': 'emph',
    'underline': 'underline',
}

PAGEBREAK_NAMES = ('newpage', 'pagebreak')

_IMAGE_CALL_RE = re.compile(r'\*image\s*\(')
_STYLE_CALL_RE = re.compile(r'\*(bold|italic|underline)\s*\(')
_PAGEBREAK_CALL_RE = re.compile(r'\*(newpage|pagebreak)\s*\(')
_PAGEBREAK_BARE_RE = re.compile(
    r'(?<![A-Za-z0-9_*\\])\*(newpage|pagebreak)(?![A-Za-z0-9_\-])(?!\s*\()'
)

#: Placeholder marker for text-command Typst (plots use \x06, tables
#: \x07, vecs \x0e; \x09 is free).
PLACEHOLDER_FMT = '\x09{}\x09'

_IMAGE_WIDTH_RE = re.compile(r'^(\d+(?:\.\d+)?)\s*(%|pt|mm|cm|in|em)?$')


def normalize_text_aliases(text):
    """Rewrite ``*b(``/``*i(``/``*u(`` to canonical ``*bold(`` etc."""
    for alias, canon in STYLE_ALIASES.items():
        text = re.sub(
            r'\*' + re.escape(alias) + r'\s*\(',
            f'*{canon}(',
            text,
        )
    return text


def _scan_balanced(text, open_end):
    """End index (exclusive) of the ')' matching text[open_end-1]=='('.

    Quote-aware for ``"..."``. Returns None when unclosed.
    """
    depth = 1
    i = open_end
    in_quote = False
    while i < len(text) and depth > 0:
        ch = text[i]
        if ch == '"' and (i == 0 or text[i - 1] != '\\'):
            in_quote = not in_quote
        elif not in_quote:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
        i += 1
    return i if depth == 0 else None


def replace_styling_calls(text, ctx, line_no, cleaner, _depth=0,
                          placeholders=None):
    """Expand ``*bold/*italic/*underline(...)`` via *cleaner*.

    *cleaner* maps raw inner text to Typst (text pipeline for body
    text, math cleaning for math arguments). The whole parenthesized
    span is the content — ``,``/``;`` stay literal. Idempotent and
    nesting-safe (depth-guarded like the math passes). When
    *placeholders* (a dict) is given, the ``#``-markup is stashed
    behind a placeholder (text pipeline: the escaper must not see
    it); otherwise it is emitted inline (math pipeline: no escaper
    runs there).
    """
    if _depth > 20:
        print('[Warning] text styling nested too deep — leaving as-is',
              file=sys.stderr)
        return text
    loc = f'Line {line_no}: ' if line_no is not None else ''
    pos = 0
    out = []
    while True:
        match = _STYLE_CALL_RE.search(text, pos)
        if not match:
            out.append(text[pos:])
            break
        name = match.group(1)
        out.append(text[pos:match.start()])
        end = _scan_balanced(text, match.end())
        if end is None:
            print(
                f'[Warning] {loc}unclosed *{name}(... — '
                f'missing closing parenthesis',
                file=sys.stderr,
            )
            out.append(text[match.start():match.end()])
            pos = match.end()
            continue
        inner = text[match.end():end - 1]
        if not inner.strip():
            print(
                f'[Warning] {loc}*{name}(...) is empty — '
                f'leaving as-is',
                file=sys.stderr,
            )
            out.append(text[match.start():end])
            pos = end
            continue
        try:
            clean = cleaner(inner)
        except RecursionError:
            print('[Warning] text styling nested too deep — leaving as-is',
                  file=sys.stderr)
            out.append(text[match.start():end])
            pos = end
            continue
        styled = f'#{STYLE_TAGS[name]}[{clean}]'
        if placeholders is None:
            out.append(styled)
        else:
            ph = PLACEHOLDER_FMT.format(len(placeholders))
            placeholders[ph] = styled
            out.append(ph)
        pos = end
    return ''.join(out)


def _replace_pagebreak_calls(text, line_no, placeholders):
    """Expand ``*newpage(...)`` / ``*pagebreak(...)`` (0-arg calls)."""
    pos = 0
    out = []
    idx = len(placeholders)
    while True:
        match = _PAGEBREAK_CALL_RE.search(text, pos)
        if not match:
            out.append(text[pos:])
            break
        name = match.group(1)
        out.append(text[pos:match.start()])
        end = _scan_balanced(text, match.end())
        if end is None:
            print(
                f'[Warning] Line {line_no}: unclosed *{name}(... — '
                f'missing closing parenthesis',
                file=sys.stderr,
            )
            out.append(text[match.start():match.end()])
            pos = match.end()
            continue
        inner = text[match.end():end - 1]
        if inner.strip():
            print(
                f'[Warning] Line {line_no}: *{name}(...) takes no '
                f'arguments — extra content ignored',
                file=sys.stderr,
            )
        ph = PLACEHOLDER_FMT.format(idx)
        idx += 1
        placeholders[ph] = '#pagebreak()'
        out.append(ph)
        pos = end
    return ''.join(out)


def find_next_image_call(text, start=0):
    """Locate the next ``*image(`` call at/after *start*.

    Returns ``(call_start, inner_start, call_end, inner_raw)`` with
    depth-aware paren matching (quote-aware for ``"..."``), or None
    when no opener remains. Unclosed openers return an ``('unclosed',
    ...)`` marker so callers can warn without looping.
    """
    m = _IMAGE_CALL_RE.search(text, start)
    if not m:
        return None
    call_start = m.start()
    inner_start = m.end()
    end = _scan_balanced(text, inner_start)
    if end is None:
        return ('unclosed', call_start, inner_start, None, None)
    return (call_start, inner_start, end, text[inner_start:end - 1])


def _typst_string(s):
    """Quote *s* as a Typst string literal."""
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def _expand_images(ctx, text, line_no, placeholders):
    """Expand ``*image(path [; width])`` to ``#image(...)``.

    Relative paths resolve from the ``.ezmath`` file's folder (see
    ``ctx.source_file``); the ``.typ`` embeds the typdir-relative
    path so the build stays relocatable. Failures never abort the
    build: an ``[Image Error: ...]`` literal is emitted and reported
    on stderr, mirroring ``*plot`` error UX. Used files are recorded
    on ``ctx.image_files`` so typ/html exports to other directories
    can carry them along (like plot/vec sidecars).
    """
    from .calc import apply_calc_in_string
    from .math_commands import split_top_level_args
    from .variables import replace_defines, replace_vars

    pos = 0
    out = []
    idx = len(placeholders)
    source = getattr(ctx, 'source_file', '') or ''
    try:
        base_dir = os.path.dirname(os.path.abspath(source)) or os.getcwd()
    except (TypeError, ValueError, OSError):
        base_dir = os.getcwd()
    typ_dir = getattr(ctx, 'plot_dir', None) or base_dir
    if not hasattr(ctx, 'image_files') or ctx.image_files is None:
        ctx.image_files = []
    while True:
        found = find_next_image_call(text, pos)
        if not found:
            out.append(text[pos:])
            break
        if found[0] == 'unclosed':
            _, call_start, inner_start, _, _ = found
            print(
                f'[Warning] Line {line_no}: unclosed *image(... — '
                f'missing closing parenthesis',
                file=sys.stderr,
            )
            out.append(text[pos:inner_start])
            pos = inner_start
            continue
        _call_start, _inner_start, call_end, inner_raw = found
        out.append(text[pos:_call_start])
        args = split_top_level_args(inner_raw)
        err = None
        if len(args) not in (1, 2):
            err = (f'*image(...) needs 1 or 2 arguments: path [; width] '
                   f'(got {len(args)})')
        elif not args[0].strip():
            err = '*image(...) needs a file path'
        width = None
        rel = None
        if err is None:
            raw_path = replace_vars(ctx, args[0].strip())
            raw_path = replace_defines(ctx, raw_path)
            abs_path = os.path.normpath(
                os.path.join(base_dir, raw_path))
            if not os.path.isfile(abs_path):
                err = (f'*image(...) file not found: {raw_path} '
                       f'(resolved from {base_dir})')
            else:
                try:
                    rel = os.path.relpath(abs_path, typ_dir)
                except (TypeError, ValueError):
                    rel = os.path.basename(abs_path)
                rel = rel.replace(os.sep, '/')
        if err is None and len(args) == 2:
            raw_width = replace_vars(ctx, args[1].strip())
            raw_width = replace_defines(ctx, raw_width)
            raw_width = apply_calc_in_string(ctx, raw_width, line_no=line_no)
            m = _IMAGE_WIDTH_RE.match(raw_width.strip())
            if m is None or not m.group(1):
                err = (f'*image(...) invalid width {args[1].strip()!r} — '
                       f'use like 50% or 6cm')
            else:
                width = f'{m.group(1)}{m.group(2) or "%"}'
        if err is not None:
            print(f'[Error] Line {line_no}: {err}', file=sys.stderr)
            out.append(f'[Image Error: {err}]')
            pos = call_end
            continue
        ctx.image_files.append((abs_path, rel))
        if width is not None:
            typ = f'#image({_typst_string(rel)}, width: {width})'
        else:
            typ = f'#image({_typst_string(rel)})'
        ph = PLACEHOLDER_FMT.format(idx)
        idx += 1
        placeholders[ph] = typ
        out.append(ph)
        pos = call_end
    return ''.join(out)


def expand_text_commands(ctx, text, line_no, cleaner, _depth=0):
    """Expand styling, page breaks and images in one pass.

    Runs AFTER vars/calc/inline-math/plots/vecs (like math commands)
    so ``<vars>`` holding styled text still expand; styling args
    re-render through *cleaner* (the full text pipeline) so
    variables, ``calc()``, math and nesting work inside. Returns
    ``(new_text, {placeholder: typst})`` — placeholders protect the
    generated ``#``-markup through the text escaper.
    """
    placeholders = {}
    text = normalize_text_aliases(text)
    text = _replace_pagebreak_calls(text, line_no, placeholders)
    text = _expand_images(ctx, text, line_no, placeholders)
    # Bare *newpage / *pagebreak (no parens) after the call forms so
    # '*newpage (' with a space still takes the call path above.
    def _bare_pagebreak(m):
        ph = PLACEHOLDER_FMT.format(len(placeholders))
        placeholders[ph] = '#pagebreak()'
        return ph

    text = _PAGEBREAK_BARE_RE.sub(_bare_pagebreak, text)
    if _depth <= 20:
        text = replace_styling_calls(text, ctx, line_no, cleaner, _depth,
                                     placeholders)
    return text, placeholders
