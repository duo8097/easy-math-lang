"""Typst / CeTZ code generation from a solved geometry scene."""

import re
import sys

from .errors import GeometryError
from .labels import _label_anchors
from .vectors import (
    _bounding_box,
    _norm,
    _normalize,
    _ray_bbox_intersect,
)

_POINT_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]*$')


def _q(name):
    """Quote a point name for CeTZ; reject unsafe identifiers."""
    if not _POINT_RE.match(name):
        raise GeometryError(f"invalid point name {name!r}")
    return f'"{name}"'


def _safe_err(text):
    """Single-line comment-safe rendering of an error message."""
    return re.sub(r'\s+', ' ', str(text)).replace('"', "'")[:500]


def generate_typst(solver, errors=None):
    lines = []
    lines.append('#import "@preview/cetz:0.4.2"')
    lines.append('#align(center)[#cetz.canvas({')
    lines.append('  import cetz.draw: *')

    # Embed any geometry errors as comments
    for err in (errors or []):
        lines.append(f'  // {_safe_err(err)}')

    # Non-finite solver output must never reach CeTZ: emit a comment and
    # fall back to point dots at finite locations only.
    import math as _math

    non_finite = []
    for p, coord in solver.points.items():
        try:
            if not (_math.isfinite(float(coord[0])) and _math.isfinite(float(coord[1]))):
                non_finite.append(p)
        except (TypeError, ValueError, IndexError):
            non_finite.append(p)
    if non_finite:
        lines.append(f'  // [GeometryError] non-finite coordinates for: {_safe_err(", ".join(non_finite))}')
        print(
            f"[GeometryError] non-finite coordinates for {', '.join(non_finite)} — "
            f"omitting affected points/edges",
            file=sys.stderr,
        )

    # Draw point dots + labels (labels auto-placed away from edges)
    anchors = _label_anchors(solver)
    non_finite_set = set(non_finite)
    for p, coord in solver.points.items():
        if p in non_finite_set:
            continue
        try:
            q = _q(p)
        except GeometryError as e:
            lines.append(f'  // [GeometryError] bad point name: {_safe_err(e)}')
            print(f"[GeometryError] bad point name {p!r}: {e}", file=sys.stderr)
            continue
        lines.append(
            f'  circle(({coord[0]:.3f}, {coord[1]:.3f}), radius: 0.05, '
            f'fill: black, name: {q})'
        )
        lines.append(
            f'  content({q}, [{p}], anchor: "{anchors.get(p, "south-west")}", '
            f'padding: 0.12)'
        )

    # Compute bounding box for ray extension (finite points only)
    finite_pts = {
        p: c for p, c in solver.points.items() if p not in non_finite_set
    }
    if finite_pts:
        try:
            xmin, ymin, xmax, ymax = _bounding_box(finite_pts)
        except (ValueError, TypeError, ArithmeticError):
            xmin, ymin, xmax, ymax = -5, -5, 5, 5
    else:
        xmin, ymin, xmax, ymax = -5, -5, 5, 5

    for cmd, args in solver.draw_commands:
        try:
            _generate_command(lines, solver, cmd, args, xmin, ymin, xmax, ymax)
        except GeometryError as e:
            lines.append(f'  // [GeometryError] *{_safe_err(cmd)}: {_safe_err(e)}')
            print(f"[GeometryError] *{cmd}({'; '.join(args)}): {e}", file=sys.stderr)
        except (ValueError, ArithmeticError) as e:
            lines.append(f'  // [GeometryError] *{_safe_err(cmd)}: {_safe_err(e)}')
            print(f"[GeometryError] *{cmd}({'; '.join(args)}): {e}", file=sys.stderr)
        except Exception as e:
            # Never let one malformed command abort the whole canvas.
            lines.append(f'  // [GeometryError] *{_safe_err(cmd)}: {_safe_err(e)}')
            print(f"[GeometryError] *{cmd}({'; '.join(args)}): {e}", file=sys.stderr)

    lines.append('})]')
    return '\n'.join(lines)


def _require_finite_pts(pts, names):
    """Raise GeometryError if any named point has non-finite coordinates.

    NaN comparisons are always False, so length checks like
    ``_norm(...) < 1e-9`` silently pass NaN through; this explicit guard
    turns diverged coordinates into a caught per-command error instead of
    invalid ``nan``/``inf`` CeTZ literals (or edges referencing skipped points).
    """
    import math as _math

    for name in names:
        if name not in pts:
            continue  # caller raises the undefined-point error
        try:
            x, y = float(pts[name][0]), float(pts[name][1])
        except (TypeError, ValueError, IndexError):
            raise GeometryError(f"invalid coordinates for point '{name}'")
        if not (_math.isfinite(x) and _math.isfinite(y)):
            raise GeometryError(f"non-finite coordinates for point '{name}' — skipping")


def _generate_command(lines, solver, cmd, args, xmin, ymin, xmax, ymax):
    pts = solver.points

    if cmd == 'triangle':
        if len(args) < 3:
            raise GeometryError("*triangle requires 3 point args")
        A, B, C = [a.strip() for a in args[:3]]
        for pt in [A, B, C]:
            if pt not in pts:
                raise GeometryError(f"undefined point '{pt}'")
        _require_finite_pts(pts, [A, B, C])
        # Degenerate (collinear / zero-area) triangle check, scale-relative.
        import math as _math

        import numpy as _np
        area2 = abs(
            (pts[B][0] - pts[A][0]) * (pts[C][1] - pts[A][1])
            - (pts[C][0] - pts[A][0]) * (pts[B][1] - pts[A][1])
        )
        max_edge = max(
            _norm(pts[B] - pts[A]), _norm(pts[C] - pts[B]), _norm(pts[C] - pts[A])
        )
        if not (_math.isfinite(float(area2)) and _math.isfinite(float(max_edge))):
            raise GeometryError(f"non-finite triangle {A},{B},{C} — skipping")
        if max_edge < 1e-9 or area2 < 1e-9 * max_edge * max_edge:
            raise GeometryError(f"degenerate triangle {A},{B},{C} (collinear or coincident points)")
        lines.append(f'  line({_q(A)}, {_q(B)}, {_q(C)}, close: true)')

    elif cmd == 'line':
        if len(args) < 2:
            raise GeometryError("*line requires 2 point args")
        A, B = args[0].strip(), args[1].strip()
        for pt in [A, B]:
            if pt not in pts:
                raise GeometryError(f"undefined point '{pt}'")
        _require_finite_pts(pts, [A, B])
        import math as _math

        _d = float(_norm(pts[A] - pts[B]))
        if not _math.isfinite(_d):
            raise GeometryError(f"non-finite line between {A} and {B} — skipping")
        if _d < 1e-9:
            raise GeometryError(f"zero-length line between {A} and {B}")
        if len(args) >= 3 and args[2].strip().lower() == 'infinite':
            lines.append(f'  // [planned] *line({_safe_err("; ".join(args))}) infinite line not yet implemented')
            return
        lines.append(f'  line({_q(A)}, {_q(B)})')

    elif cmd == 'ray':
        if len(args) < 2:
            raise GeometryError("*ray requires 2 point args: start ; through")
        A, B = args[0].strip(), args[1].strip()
        for pt in [A, B]:
            if pt not in pts:
                raise GeometryError(f"undefined point '{pt}'")
        _require_finite_pts(pts, [A, B])
        import math as _math

        diff = pts[B] - pts[A]
        _dn = float(_norm(diff))
        if not _math.isfinite(_dn):
            raise GeometryError(f"non-finite ray {A} -> {B} — skipping")
        if _dn < 1e-9:
            raise GeometryError(f"zero-length ray: A and B are the same point ({A})")
        direction = _normalize(diff)
        t_max = _ray_bbox_intersect(pts[A], direction, xmin, ymin, xmax, ymax)
        if not _math.isfinite(float(t_max)):
            raise GeometryError(f"non-finite ray extension {A} -> {B} — skipping")
        end = pts[A] + t_max * direction
        ax, ay = pts[A]
        ex, ey = end
        if not all(_math.isfinite(float(v)) for v in (ax, ay, ex, ey)):
            raise GeometryError(f"non-finite ray endpoints {A} -> {B} — skipping")
        lines.append(
            f'  line(({ax:.3f}, {ay:.3f}), ({ex:.3f}, {ey:.3f}), '
            f'mark: (end: ">"))'
        )

    elif cmd == 'circle':
        if len(args) < 2:
            raise GeometryError("*circle requires 2 args: center ; radius-or-point")
        center = args[0].strip()
        r_or_pt = args[1].strip()
        if center not in pts:
            raise GeometryError(f"undefined point '{center}'")
        _require_finite_pts(pts, [center])
        if r_or_pt in pts:
            # radius = distance from center to the given point
            _require_finite_pts(pts, [r_or_pt])
            import math as _math

            d = _norm(pts[center] - pts[r_or_pt])
            if not _math.isfinite(float(d)):
                raise GeometryError(f"non-finite circle radius for {center} — skipping")
            if d < 1e-9:
                raise GeometryError(f"circle radius is zero: {center} and {r_or_pt} coincide")
            lines.append(f'  circle({_q(center)}, radius: {d:.3f})')
        else:
            try:
                r = float(r_or_pt)
            except ValueError:
                raise GeometryError(
                    f"circle radius must be numeric or an existing point name, got: {r_or_pt!r}"
                )
            import math as _math

            if not _math.isfinite(r):
                raise GeometryError(f"circle radius must be finite, got: {r_or_pt!r}")
            if r <= 0:
                raise GeometryError(f"circle radius must be positive, got: {r_or_pt!r}")
            lines.append(f'  circle({_q(center)}, radius: {r:.3f})')

    elif cmd == 'right-angle':
        # Convention: right-angle(B ; A ; C) → right angle at vertex A
        if len(args) < 3:
            raise GeometryError("*right-angle requires 3 args: B ; A ; C")
        B, A, C = [a.strip() for a in args[:3]]
        for pt in [A, B, C]:
            if pt not in pts:
                raise GeometryError(f"undefined point '{pt}'")
        _require_finite_pts(pts, [A, B, C])
        import math as _math

        pA, pB, pC = pts[A], pts[B], pts[C]
        vAB = pB - pA
        vAC = pC - pA
        _nAB, _nAC = float(_norm(vAB)), float(_norm(vAC))
        if not (_math.isfinite(_nAB) and _math.isfinite(_nAC)):
            raise GeometryError(f"non-finite right-angle at {A} — skipping")
        if _nAB < 1e-9:
            raise GeometryError(f"coincident points: {B} and {A} are the same point")
        if _nAC < 1e-9:
            raise GeometryError(f"coincident points: {C} and {A} are the same point")
        cosang = float((vAB @ vAC) / (_nAB * _nAC))
        if not _math.isfinite(cosang):
            raise GeometryError(f"non-finite right-angle at {A} — skipping")
        if abs(cosang) > 0.15:
            print(
                f"[GeometryWarning] *right-angle({B} ; {A} ; {C}) angle is not ~90° "
                f"(cos={cosang:.3f}) — marker may be misleading",
                file=sys.stderr,
            )
            lines.append(
                f'  // [GeometryWarning] right-angle at {A} is not 90° (cos={cosang:.3f})'
            )
        size = 0.2
        uAB = _normalize(vAB) * size
        uAC = _normalize(vAC) * size
        p1 = pA + uAB           # step toward B
        p2 = pA + uAB + uAC     # corner of the L
        p3 = pA + uAC           # step toward C
        lines.append(
            f'  line(({p1[0]:.3f}, {p1[1]:.3f}), '
            f'({p2[0]:.3f}, {p2[1]:.3f}), '
            f'({p3[0]:.3f}, {p3[1]:.3f}))'
        )

    elif cmd == 'point':
        # Points are already drawn above; skip
        pass

    elif cmd in ('distance', 'perp', 'parallel', 'on-line', 'on-circle',
                 'equal-length', 'midpoint', 'intersection'):
        # Constraint-only commands — nothing to draw
        pass

    elif cmd in ('arc', 'angle', 'equal-angle', 'label', 'length', 'angle-value'):
        # Planned but not yet implemented
        lines.append(f'  // [planned] *{_safe_err(cmd)}({_safe_err("; ".join(args))}) not yet implemented')

    else:
        # Unknown — already warned during parse
        pass
