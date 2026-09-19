"""Registration of geometry commands into the solver."""

import re

import numpy as np

from .errors import GeometryError
from .vectors import _cross2d, _norm

KNOWN_GEOMETRY_COMMANDS = {
    'point', 'line', 'ray', 'circle', 'triangle', 'right-angle', 'angle',
    'equal-angle', 'equal-length', 'parallel', 'perp', 'on-line', 'on-circle',
    'distance', 'midpoint', 'intersection', 'arc', 'label',
    'length', 'angle-value',
}


def _process_command(solver, cmd, args):
    """Register a geometry command into the solver."""

    if cmd not in KNOWN_GEOMETRY_COMMANDS:
        raise GeometryError(f"unknown geometry command *{cmd} — ignored")

    if cmd == 'point':
        if not args or not args[0]:
            raise GeometryError("*point() requires a name argument")
        if '=' in args[0]:
            name, coords = args[0].split('=', 1)
            name = name.strip()
            try:
                x_str, y_str = coords.split(',', 1)
                solver.add_point(name, float(x_str.strip()), float(y_str.strip()))
            except (ValueError, TypeError) as e:
                raise GeometryError(f"invalid coordinates: {e}")
        else:
            name = args[0].strip()
            solver.add_point(name)

    elif cmd == 'distance':
        if len(args) < 3:
            raise GeometryError("*distance requires 3 arguments: A ; B ; distance")
        A, B = args[0].strip(), args[1].strip()
        try:
            d = float(args[2].strip())
        except ValueError:
            raise GeometryError(f"distance value must be numeric, got: {args[2]!r}")
        solver.add_point(A)
        solver.add_point(B)
        solver.add_constraint(
            f"distance({A},{B}={d})",
            lambda P, a=A, b=B, dv=d: (_norm(P[a] - P[b]) - dv) ** 2
        )

    elif cmd == 'perp':
        if len(args) == 4:
            A, B, C, D = [a.strip() for a in args]
            for pt in [A, B, C, D]:
                solver.add_point(pt)
            solver.add_constraint(
                f"perp({A}{B},{C}{D})",
                lambda P, a=A, b=B, c=C, d=D: np.dot(P[b] - P[a], P[d] - P[c]) ** 2
            )
        elif len(args) == 3:
            A, B, C = [a.strip() for a in args]
            for pt in [A, B, C]:
                solver.add_point(pt)
            solver.add_constraint(
                f"perp({A}{B},{B}{C})",
                lambda P, a=A, b=B, c=C: np.dot(P[b] - P[a], P[c] - P[b]) ** 2
            )
        else:
            raise GeometryError("*perp requires 3 or 4 arguments")

    elif cmd == 'parallel':
        if len(args) < 4:
            raise GeometryError("*parallel requires 4 arguments: A ; B ; C ; D")
        A, B, C, D = [a.strip() for a in args[:4]]
        for pt in [A, B, C, D]:
            solver.add_point(pt)
        solver.add_constraint(
            f"parallel({A}{B},{C}{D})",
            lambda P, a=A, b=B, c=C, d=D: _cross2d(P[b] - P[a], P[d] - P[c]) ** 2
        )

    elif cmd == 'on-line':
        if len(args) < 3:
            raise GeometryError("*on-line requires 3 arguments: A ; B ; C")
        A, B, C = [a.strip() for a in args[:3]]
        for pt in [A, B, C]:
            solver.add_point(pt)
        solver.add_constraint(
            f"on-line({C} on {A}{B})",
            lambda P, a=A, b=B, c=C: _cross2d(P[b] - P[a], P[c] - P[a]) ** 2
        )

    elif cmd == 'on-circle':
        if len(args) < 3:
            raise GeometryError("*on-circle requires 3 arguments: O ; r ; A")
        O, r_str, A = args[0].strip(), args[1].strip(), args[2].strip()
        try:
            r = float(r_str)
        except ValueError:
            raise GeometryError(f"radius must be numeric, got: {r_str!r}")
        for pt in [O, A]:
            solver.add_point(pt)
        solver.add_constraint(
            f"on-circle({A} on circle({O},{r}))",
            lambda P, o=O, rv=r, a=A: (_norm(P[a] - P[o]) - rv) ** 2
        )

    elif cmd == 'equal-length':
        if len(args) < 4:
            raise GeometryError("*equal-length requires 4 arguments: A ; B ; C ; D")
        A, B, C, D = [a.strip() for a in args[:4]]
        for pt in [A, B, C, D]:
            solver.add_point(pt)
        solver.add_constraint(
            f"equal-length({A}{B}={C}{D})",
            lambda P, a=A, b=B, c=C, d=D: (_norm(P[b] - P[a]) - _norm(P[d] - P[c])) ** 2
        )

    elif cmd == 'midpoint':
        if len(args) < 3:
            raise GeometryError("*midpoint requires 3 arguments: A ; B ; C")
        A, B, C = [a.strip() for a in args[:3]]
        for pt in [A, B, C]:
            solver.add_point(pt)
        solver.add_constraint(
            f"midpoint({C} of {A}{B})",
            lambda P, a=A, b=B, c=C: _norm(P[c] - (P[a] + P[b]) / 2) ** 2
        )

    elif cmd == 'intersection':
        if len(args) < 3:
            raise GeometryError("*intersection requires 3 arguments: name ; line(A;B) ; line(D;E)")
        C = args[0].strip()

        def _parse_line_arg(s):
            m = re.match(r'line\s*\(\s*(.*?)\s*;\s*(.*?)\s*\)', s.strip())
            if not m:
                raise GeometryError(f"expected line(P;Q), got: {s!r}")
            return m.group(1).strip(), m.group(2).strip()

        A, B = _parse_line_arg(args[1])
        D, E = _parse_line_arg(args[2])
        for pt in [A, B, C, D, E]:
            solver.add_point(pt)
        solver.add_constraint(
            f"intersection({C} on {A}{B})",
            lambda P, a=A, b=B, c=C: _cross2d(P[b] - P[a], P[c] - P[a]) ** 2
        )
        solver.add_constraint(
            f"intersection({C} on {D}{E})",
            lambda P, d=D, e=E, c=C: _cross2d(P[e] - P[d], P[c] - P[d]) ** 2
        )

    # Draw-only commands — just register for the draw pass
    elif cmd in ('line', 'ray', 'triangle', 'circle', 'right-angle', 'angle',
                 'equal-angle', 'arc', 'label', 'length', 'angle-value'):
        # Auto-create referenced points so simple drawings work without
        # explicit *point() (per spec: coordinates are optional).
        for arg in args:
            a = arg.strip()
            if a.lower() == 'infinite':
                continue
            if re.match(r'^[A-Za-z][A-Za-z0-9_]*$', a):
                try:
                    float(a)
                except ValueError:
                    solver.add_point(a)
                    continue
            # circle(O ; r-or-point): second arg may be a point name
            if cmd == 'circle':
                try:
                    float(a)
                except ValueError:
                    if re.match(r'^[A-Za-z][A-Za-z0-9_]*$', a):
                        solver.add_point(a)
    # (parallel/perp as constraint-only — don't add draw command separately)

    solver.draw_commands.append((cmd, args))
