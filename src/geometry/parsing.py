"""Depth-aware parsing of *draw(...) block contents."""

import sys

from .codegen import generate_typst
from .commands import _process_command
from .errors import GeometryError, GeometryWarning
from .solver import GeometrySolver


def split_args(args_str):
    """Split a semicolon-separated argument string, respecting nested ()."""
    parts = []
    current = []
    depth = 0
    for char in args_str:
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        if char == ';' and depth == 0:
            parts.append(''.join(current).strip())
            current = []
        else:
            current.append(char)
    parts.append(''.join(current).strip())
    return parts


def _parse_commands(block_text):
    """
    Yield (cmd_name, args_str) for each *cmd(...) in block_text,
    handling nested parentheses correctly.
    """
    i = 0
    while i < len(block_text):
        # Find next *
        star = block_text.find('*', i)
        if star == -1:
            break

        # Read command name (letters, digits, hyphens)
        j = star + 1
        while j < len(block_text) and (block_text[j].isalnum() or block_text[j] == '-'):
            j += 1

        if j == star + 1 or j >= len(block_text) or block_text[j] != '(':
            # Not a valid command — skip the *
            i = star + 1
            continue

        cmd_name = block_text[star + 1:j]
        # j now points to '('
        depth = 1
        k = j + 1
        while k < len(block_text) and depth > 0:
            if block_text[k] == '(':
                depth += 1
            elif block_text[k] == ')':
                depth -= 1
            k += 1

        if depth != 0:
            print(
                f"[GeometryError] unclosed parentheses in *{cmd_name}(...) — skipping",
                file=sys.stderr,
            )
            i = k
            continue

        args_str = block_text[j + 1:k - 1]
        yield cmd_name, args_str
        i = k


def parse_draw_block(block_text):
    solver = GeometrySolver()
    errors = []  # collect non-fatal geometry errors as strings

    for cmd, args_str in _parse_commands(block_text):
        try:
            args = split_args(args_str)
            _process_command(solver, cmd, args)
        except GeometryError as e:
            msg = f"[GeometryError] *{cmd}({args_str}): {e}"
            print(msg, file=sys.stderr)
            errors.append(msg)
        except Exception as e:
            msg = f"[GeometryError] *{cmd}({args_str}): unexpected error: {e}"
            print(msg, file=sys.stderr)
            errors.append(msg)

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

    return generate_typst(solver, errors)
