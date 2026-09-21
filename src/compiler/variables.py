"""Variable (<name>) and define (bare-word) substitution."""

import re
import sys


def replace_vars(ctx, text, _visited=None):
    """Expand <var> tokens; circular references are left unexpanded."""
    if _visited is None:
        _visited = set()
    while True:
        changed = False
        for var, val in ctx.variables.items():
            token = f'<{var}>'
            if token in text:
                if var in _visited:
                    print(
                        f'[WARNING] Circular variable reference detected: <{var}>. '
                        f'Leaving unexpanded.',
                        file=sys.stderr,
                    )
                    continue
                _visited.add(var)
                text = text.replace(token, str(val))
                changed = True
        if not changed:
            break
    return text


def replace_defines(ctx, text):
    """Expand bare-word defines, recursively (up to 10 passes)."""
    for _ in range(10):
        changed = False
        for k, v in ctx.defines.items():
            # Never rewrite *command names (e.g. a define named 'pi'
            # must not turn *pi into *3). Bare words only.
            new_text = re.sub(rf'(?<!\*)\b{re.escape(k)}\b', v, text)
            if new_text != text:
                changed = True
                text = new_text
        if not changed:
            break
    return text


def check_undefined_vars(text, line_no):
    """Report identifier-like <name> tokens with no definition (hard error)."""
    seen = set()
    for match in re.finditer(r'<([^<>]+)>', text):
        name = match.group(1)
        # Only flag identifier-like names (tmp1, width). Symbol
        # shortcuts such as <=> / -> / => contain non-identifier
        # chars and are handled later by replace_symbol_shortcuts.
        if not re.fullmatch(r'\s*[A-Za-z_][A-Za-z0-9_]*\s*', name):
            continue
        # Skip matches touching another angle bracket: those belong to
        # multi-char ASCII operators (<< B >>) handled later by
        # replace_symbol_shortcuts, not to variables.
        if match.start() > 0 and text[match.start() - 1] == '<':
            continue
        if match.end() < len(text) and text[match.end()] == '>':
            continue
        if name in seen:
            continue
        seen.add(name)
        print(
            f'[Error] Line {line_no}: undefined variable <{name}>',
            file=sys.stderr,
        )
        text = text.replace(f'<{name}>', f'[UNDEFINED: <{name}>]')
    return text
