"""Registration of geometry commands into the solver."""

import re

import numpy as np

from .errors import GeometryError
from .vectors import _cross2d, _norm

POINT_NAME_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]*$')


def _check_point_name(name):
    if not POINT_NAME_RE.match(name):
        raise GeometryError(f"invalid point name {name!r} — use letters, digits, '_' starting with a letter")
    return name


def _seg_cost(P, A, B, fn):
    """Cost with degenerate-segment guard: coincident points cost 1.0."""
    if _norm(P[B] - P[A]) < 1e-9:
        return 1.0
    return fn()

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
        if len(args) > 1:
            raise GeometryError(f"*point() takes 1 argument, got {len(args)}: {'; '.join(args)}")
        if '=' in args[0]:
            name, coords = args[0].split('=', 1)
            name = name.strip()
            _check_point_name(name)
            try:
                x_str, y_str = coords.split(',', 1)
                solver.add_point(name, float(x_str.strip()), float(y_str.strip()))
            except (ValueError, TypeError) as e:
                raise GeometryError(f"invalid coordinates: {e}")
        else:
            name = args[0].strip()
            _check_point_name(name)
            solver.add_point(name)

    elif cmd == 'distance':
        if len(args) != 3:
            raise GeometryError(f"*distance requires 3 arguments: A ; B ; distance (got {len(args)})")
        A, B = args[0].strip(), args[1].strip()
        _check_point_name(A)
        _check_point_name(B)
        try:
            d = float(args[2].strip())
        except ValueError:
            raise GeometryError(f"distance value must be numeric, got: {args[2]!r}")
        import math as _math

        if not _math.isfinite(d):
            raise GeometryError(f"distance must be finite, got: {args[2]!r}")
        if d < 0:
            raise GeometryError(f"distance must be non-negative, got: {args[2]!r}")
        solver.add_point(A)
        solver.add_point(B)
        if A == B and d > 1e-9:
            raise GeometryError(f"*distance({A} ; {B} ; {d}): same point cannot have non-zero distance")
        solver.add_constraint(
            f"distance({A},{B}={d})",
            lambda P, a=A, b=B, dv=d: (_norm(P[a] - P[b]) - dv) ** 2
        )

    elif cmd == 'perp':
        if len(args) == 4:
            A, B, C, D = [a.strip() for a in args]
            for pt in [A, B, C, D]:
                _check_point_name(pt)
                solver.add_point(pt)
            solver.add_constraint(
                f"perp({A}{B},{C}{D})",
                lambda P, a=A, b=B, c=C, d=D: _seg_cost(
                    P, a, b,
                    lambda: _seg_cost(
                        P, c, d,
                        lambda: np.dot(P[b] - P[a], P[d] - P[c]) ** 2,
                    ),
                )
            )
        elif len(args) == 3:
            A, B, C = [a.strip() for a in args]
            for pt in [A, B, C]:
                _check_point_name(pt)
                solver.add_point(pt)
            solver.add_constraint(
                f"perp({A}{B},{B}{C})",
                lambda P, a=A, b=B, c=C: _seg_cost(
                    P, a, b,
                    lambda: _seg_cost(
                        P, b, c,
                        lambda: np.dot(P[b] - P[a], P[c] - P[b]) ** 2,
                    ),
                )
            )
        else:
            raise GeometryError("*perp requires 3 or 4 arguments")

    elif cmd == 'parallel':
        if len(args) != 4:
            raise GeometryError(f"*parallel requires 4 arguments: A ; B ; C ; D (got {len(args)})")
        A, B, C, D = [a.strip() for a in args[:4]]
        for pt in [A, B, C, D]:
            _check_point_name(pt)
            solver.add_point(pt)
        solver.add_constraint(
            f"parallel({A}{B},{C}{D})",
            lambda P, a=A, b=B, c=C, d=D: _seg_cost(
                P, a, b,
                lambda: _seg_cost(
                    P, c, d,
                    lambda: _cross2d(P[b] - P[a], P[d] - P[c]) ** 2,
                ),
            )
        )

    elif cmd == 'on-line':
        if len(args) != 3:
            raise GeometryError(f"*on-line requires 3 arguments: A ; B ; C (got {len(args)})")
        A, B, C = [a.strip() for a in args[:3]]
        for pt in [A, B, C]:
            _check_point_name(pt)
            solver.add_point(pt)
        solver.add_constraint(
            f"on-line({C} on {A}{B})",
            lambda P, a=A, b=B, c=C: _seg_cost(
                P, a, b,
                lambda: _cross2d(P[b] - P[a], P[c] - P[a]) ** 2,
            )
        )

    elif cmd == 'on-circle':
        if len(args) != 3:
            raise GeometryError(f"*on-circle requires 3 arguments: O ; r ; A (got {len(args)})")
        O, r_str, A = args[0].strip(), args[1].strip(), args[2].strip()
        _check_point_name(O)
        _check_point_name(A)
        try:
            r = float(r_str)
        except ValueError:
            raise GeometryError(f"radius must be numeric, got: {r_str!r}")
        import math as _math2

        if not _math2.isfinite(r):
            raise GeometryError(f"radius must be finite, got: {r_str!r}")
        if r <= 0:
            raise GeometryError(f"radius must be positive, got: {r_str!r}")
        for pt in [O, A]:
            solver.add_point(pt)
        solver.add_constraint(
            f"on-circle({A} on circle({O},{r}))",
            lambda P, o=O, rv=r, a=A: (_norm(P[a] - P[o]) - rv) ** 2
        )

    elif cmd == 'equal-length':
        if len(args) != 4:
            raise GeometryError(f"*equal-length requires 4 arguments: A ; B ; C ; D (got {len(args)})")
        A, B, C, D = [a.strip() for a in args[:4]]
        for pt in [A, B, C, D]:
            _check_point_name(pt)
            solver.add_point(pt)
        solver.add_constraint(
            f"equal-length({A}{B}={C}{D})",
            lambda P, a=A, b=B, c=C, d=D: (_norm(P[b] - P[a]) - _norm(P[d] - P[c])) ** 2
        )

    elif cmd == 'midpoint':
        if len(args) != 3:
            raise GeometryError(f"*midpoint requires 3 arguments: A ; B ; C (got {len(args)})")
        A, B, C = [a.strip() for a in args[:3]]
        for pt in [A, B, C]:
            _check_point_name(pt)
            solver.add_point(pt)
        solver.add_constraint(
            f"midpoint({C} of {A}{B})",
            lambda P, a=A, b=B, c=C: _norm(P[c] - (P[a] + P[b]) / 2) ** 2
        )

    elif cmd == 'intersection':
        if len(args) != 3:
            raise GeometryError(f"*intersection requires 3 arguments: name ; line(A;B) ; line(D;E) (got {len(args)})")
        C = args[0].strip()
        _check_point_name(C)

        def _parse_line_arg(s):
            m = re.match(r'line\s*\(\s*(.*?)\s*;\s*(.*?)\s*\)\s*$', s.strip())
            if not m:
                raise GeometryError(f"expected line(P;Q), got: {s!r}")
            p, q = m.group(1).strip(), m.group(2).strip()
            _check_point_name(p)
            _check_point_name(q)
            if p == q:
                raise GeometryError(f"intersection: line({p};{q}) is degenerate (same point twice)")
            return p, q

        A, B = _parse_line_arg(args[1])
        D, E = _parse_line_arg(args[2])
        for pt in [A, B, C, D, E]:
            solver.add_point(pt)
        solver.add_constraint(
            f"intersection({C} on {A}{B})",
            lambda P, a=A, b=B, c=C: _seg_cost(
                P, a, b,
                lambda: _cross2d(P[b] - P[a], P[c] - P[a]) ** 2,
            )
        )
        solver.add_constraint(
            f"intersection({C} on {D}{E})",
            lambda P, d=D, e=E, c=C: _seg_cost(
                P, d, e,
                lambda: _cross2d(P[e] - P[d], P[c] - P[d]) ** 2,
            )
        )

    # Draw-only commands — just register for the draw pass
    elif cmd in ('line', 'ray', 'triangle', 'circle', 'right-angle', 'angle',
                 'equal-angle', 'arc', 'label', 'length', 'angle-value'):
        # Auto-create referenced points so simple drawings work without
        # explicit *point() (per spec: coordinates are optional).
        for i, arg in enumerate(args):
            a = arg.strip()
            # *triangle(A ; B ; C ; labels): 4th arg is a keyword, not a point.
            if cmd == 'triangle' and i == 3 and a.lower() == 'labels':
                continue
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
