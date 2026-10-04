"""Depth-aware parsing of *draw(...) block contents."""

import sys

from .codegen import generate_typst
from .commands import _process_command
from .errors import GeometryError, GeometryWarning
from .solver import GeometrySolver


def split_args(args_str):
    """Split a semicolon-separated argument string, respecting nested ().

    Friendly: ',' works like ';' when no top-level ';' is present, so
    ``*line(A, B)`` equals ``*line(A ; B)``. When ';' is present it wins
    (so ``*point(A = 0, 0)`` — whose single arg contains a comma — never
    splits). ``*point`` is never comma-split: its ``x, y`` coordinates
    contain a comma by design. Separators inside "..." are ignored so
    ``*label(A ; "a;b")`` keeps the label intact.
    """
    # Decide separator set: ';' wins when present at depth 0 (outside quotes).
    has_semi = False
    _depth = 0
    _q = False
    for _ch in args_str:
        if _ch == '"':
            _q = not _q
            continue
        if _q:
            continue
        if _ch == '(':
            _depth += 1
        elif _ch == ')':
            if _depth > 0:
                _depth -= 1
            else:
                _depth = 0
        elif _ch == ';' and _depth == 0:
            has_semi = True
            break
    seps = (';',) if has_semi else (';', ',')
    parts = []
    current = []
    depth = 0
    in_q = False
    for char in args_str:
        if char == '"':
            in_q = not in_q
            current.append(char)
            continue
        if in_q:
            current.append(char)
            continue
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
            if depth < 0:
                # Unbalanced ')': do not let depth go negative and merge
                # the rest into one confusing arg; clamp and keep splitting.
                depth = 0
        if char in seps and depth == 0:
            parts.append(''.join(current).strip())
            current = []
        else:
            current.append(char)
    parts.append(''.join(current).strip())
    return parts


def split_args_for(cmd, args_str):
    """Command-aware split: ``*point`` never splits on ',' (x, y coords)."""
    if cmd == 'point':
        # Point takes a single "name" or "name = x, y" arg: always ';' only.
        parts = []
        current = []
        depth = 0
        for char in args_str:
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
                if depth < 0:
                    depth = 0
            if char == ';' and depth == 0:
                parts.append(''.join(current).strip())
                current = []
            else:
                current.append(char)
        parts.append(''.join(current).strip())
        return parts
    return split_args(args_str)


def _parse_commands(block_text):
    """
    Yield (cmd_name, args_str, annotation) for each *cmd(...) in block_text,
    handling nested parentheses correctly.

    ``annotation`` is an optional trailing ``= value`` on the same line
    (e.g. ``*length(A ; B) = 5``) used by measurement labels; it is '' when
    absent. The ``=`` must follow the closing paren (optionally separated
    by spaces/tabs) so ``==``/``=>`` inside later text is never consumed.
    """
    import re as _re

    i = 0
    while i < len(block_text):
        # Find next *
        star = block_text.find('*', i)
        if star == -1:
            break

        # Read command name (letters, digits, hyphens, underscores)
        j = star + 1
        while j < len(block_text) and (block_text[j].isalnum() or block_text[j] in '-_'):
            j += 1

        if j == star + 1:
            # Not a valid command — skip the *
            i = star + 1
            continue
        # Allow whitespace between command name and '(' (e.g. *point (A)).
        name_end = j
        k_scan = j
        while k_scan < len(block_text) and block_text[k_scan] in ' \t\n\r':
            k_scan += 1
        if k_scan >= len(block_text) or block_text[k_scan] != '(':
            # Not a valid command — skip the *
            i = star + 1
            continue
        j = k_scan

        cmd_name = block_text[star + 1:name_end]
        # j now points to '('
        depth = 1
        k = j + 1
        in_quote = False
        while k < len(block_text) and depth > 0:
            ch = block_text[k]
            if ch == '"' and (k == 0 or block_text[k - 1] != '\\'):
                in_quote = not in_quote
            elif not in_quote:
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
            k += 1

        if depth != 0:
            print(
                f"[GeometryError] unclosed parentheses in *{cmd_name}(...) — skipping",
                file=sys.stderr,
            )
            # Skip only this broken command so later valid commands
            # in the same block are still parsed.
            i = star + 1
            continue

        args_str = block_text[j + 1:k - 1]
        annot = ''
        annot_end = k
        m = _re.match(r'[ \t]*=(?![=>])[ \t]*([^\n]*)', block_text[k:])
        if m:
            # A value never contains a new command: stop at `*name(`
            # so `= 2*3` survives but a following command does not leak in.
            annot = _re.sub(r'\*[A-Za-z][A-Za-z0-9_\-]*\s*\(.*$', '', m.group(1)).strip()
            # Advance past the whole annotation so an embedded *cmd(
            # inside it is not re-parsed as a real command.
            annot_end = k + m.end()
        yield cmd_name, args_str, annot
        i = annot_end


def parse_draw_block(block_text):
    solver = GeometrySolver()
    errors = []  # collect non-fatal geometry errors as strings

    for cmd, args_str, annot in _parse_commands(block_text):
        try:
            args = split_args_for(cmd, args_str)
            _process_command(solver, cmd, args)
        except GeometryError as e:
            msg = f"[GeometryError] *{cmd}({args_str}): {e}"
            print(msg, file=sys.stderr)
            errors.append(msg)
        except Exception as e:
            msg = f"[GeometryError] *{cmd}({args_str}): unexpected error: {e}"
            print(msg, file=sys.stderr)
            errors.append(msg)
        else:
            # Store only on success: indexing by len() before the call
            # would leak this annotation to the next command on failure.
            if annot:
                solver.draw_annotations[len(solver.draw_commands) - 1] = annot

    try:
        solver.validate()
    except GeometryError as e:
        msg = f"[GeometryError] {e}"
        print(msg, file=sys.stderr)
        errors.append(msg)

    try:
        solver.solve()
    except GeometryError as e:
        msg = f"[GeometryError] {e}"
        print(msg, file=sys.stderr)
        errors.append(msg)
    except GeometryWarning as e:
        msg = f"[GeometryWarning] {e}"
        print(msg, file=sys.stderr)
        errors.append(msg)
    except Exception as e:
        # Belts and braces: never crash the caller on solver internals
        # (numpy errors, etc.) — return a degraded canvas instead.
        msg = f"[GeometryError] solver failed: {e}"
        print(msg, file=sys.stderr)
        errors.append(msg)

    try:
        return generate_typst(solver, errors)
    except Exception as e:
        msg = f"[GeometryError] code generation failed: {e}"
        print(msg, file=sys.stderr)
        errors.append(msg)
        try:
            return generate_typst(GeometrySolver(), errors)
        except Exception:
            return '#import "@preview/cetz:0.4.2"\n#align(center)[#cetz.canvas({\n  import cetz.draw: *\n})]'
