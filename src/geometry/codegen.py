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
    """Single-line comment-safe rendering of an error message.

    Also redacts non-finite/absurd numeric literals (nan/inf, |v| >= 1e9)
    so `//` diagnostic comments never trip output-hygiene scans; the
    full text is still printed to stderr.
    """
    s = re.sub(r'\s+', ' ', str(text)).replace('"', "'")[:500]
    s = re.sub(r'(?i)\b(nan|inf|infinity)\b', '?', s)

    def _redact_big(m):
        try:
            v = float(m.group(0))
        except ValueError:
            return m.group(0)
        return '>1e9' if abs(v) >= 1e9 else m.group(0)

    return re.sub(r'-?\d[\d_]*(\.\d+)?([eE][+-]?\d+)?', _redact_big, s)


def _safe_text(text, limit=200):
    """Escape free-form label text for a Typst string ([#\"...\"]).

    Emitted via ``content(pos, [#"text"])`` so only backslash and the
    quote need escaping. Truncated to keep canvases sane.
    """
    return (
        re.sub(r'\s+', ' ', str(text))[:limit].replace('\\', '\\\\').replace('"', '\\"')
    )


def _fmt_num(x):
    """Compact number for measurement labels (5 not 5.000)."""
    s = f'{float(x):.3f}'
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s if s not in ('-0', '') else '0'


def _vec_angle_deg(v):
    """Direction of v as degrees in [0, 360) (standard math convention)."""
    import math as _math

    return _math.degrees(_math.atan2(float(v[1]), float(v[0]))) % 360.0


def _minor_angle_deg(v1, v2):
    """Smaller angle between v1 and v2 in [0, 180]; NaN-safe inputs assumed finite."""
    import math as _math

    n1, n2 = float(_norm(v1)), float(_norm(v2))
    if not (_math.isfinite(n1) and _math.isfinite(n2)) or n1 < 1e-9 or n2 < 1e-9:
        raise GeometryError("zero-length vector has no angle")
    cosang = float((v1 @ v2) / (n1 * n2))
    cosang = max(-1.0, min(1.0, cosang))  # clamp fp rounding out of acos domain
    return _math.degrees(_math.acos(cosang))


def _clip_line_to_box(px, py, dx, dy, xmin, ymin, xmax, ymax):
    """Clip infinite line p + t*d to the box (Liang–Barsky).

    Returns ((x1, y1), (x2, y2)) finite endpoints or None when the line
    misses the box. Inputs must be finite; the direction must be nonzero.
    """
    import math as _math

    t0, t1 = -_math.inf, _math.inf
    for p, q in (
        (-dx, px - xmin), (dx, xmax - px),
        (-dy, py - ymin), (dy, ymax - py),
    ):
        if abs(p) < 1e-12:
            if q < 0:
                return None
        else:
            t = q / p
            if p < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
    if t0 > t1 or not (_math.isfinite(t0) and _math.isfinite(t1)):
        return None
    return (
        (px + t0 * dx, py + t0 * dy),
        (px + t1 * dx, py + t1 * dy),
    )


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

    # Compute scene bounds for ray extension / infinite-line clipping:
    # finite points plus arc-circle cardinal extremes (an arc's curve can
    # reach `radius` beyond its endpoints in x/y).
    finite_pts = {
        p: c for p, c in solver.points.items() if p not in non_finite_set
    }
    extra = []
    for cmd, args in solver.draw_commands:
        if cmd == 'arc' and len(args) >= 3:
            a = [x.strip() for x in args[:3]]
            if all(x in finite_pts for x in a):
                try:
                    import math as _math

                    ox, oy = float(finite_pts[a[0]][0]), float(finite_pts[a[0]][1])
                    ax, ay = float(finite_pts[a[1]][0]), float(finite_pts[a[1]][1])
                    r = _math.hypot(ax - ox, ay - oy)
                    if _math.isfinite(r) and r > 1e-9:
                        extra.extend([(ox - r, oy), (ox + r, oy), (ox, oy - r), (ox, oy + r)])
                except (TypeError, ValueError, IndexError):
                    pass
    if finite_pts or extra:
        try:
            xs = [c[0] for c in finite_pts.values()] + [p[0] for p in extra]
            ys = [c[1] for c in finite_pts.values()] + [p[1] for p in extra]
            xmin, ymin, xmax, ymax = min(xs), min(ys), max(xs), max(ys)
        except (ValueError, TypeError, ArithmeticError):
            xmin, ymin, xmax, ymax = -5, -5, 5, 5
    else:
        xmin, ymin, xmax, ymax = -5, -5, 5, 5
    # Margin so clipped lines overshoot the outermost dots slightly.
    clip = (xmin - 0.5, ymin - 0.5, xmax + 0.5, ymax + 0.5)

    annotations = getattr(solver, 'draw_annotations', {})
    for idx, (cmd, args) in enumerate(solver.draw_commands):
        try:
            _generate_command(
                lines, solver, cmd, args, xmin, ymin, xmax, ymax,
                clip, annotations.get(idx, ''),
            )
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


def _generate_command(lines, solver, cmd, args, xmin, ymin, xmax, ymax,
                       clip=None, annot=''):
    pts = solver.points
    if clip is None:
        clip = (xmin - 0.5, ymin - 0.5, xmax + 0.5, ymax + 0.5)

    if cmd == 'triangle':
        if len(args) < 3:
            raise GeometryError("*triangle requires 3 point args")
        if len(args) > 4 or (len(args) == 4 and args[3].strip().lower() != 'labels'):
            raise GeometryError(f"*triangle takes 3 points (optional 4th: labels), got {len(args)}")
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
        if len(args) > 3 or (len(args) == 3 and args[2].strip().lower() != 'infinite'):
            raise GeometryError(
                f"*line takes 2 points (optional 3rd: infinite), got {len(args)}"
            )
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
            # Infinite line: clip both directions against the scene bounds
            # (finite endpoints only — never huge/inf coordinates).
            direction = _normalize(pts[B] - pts[A])
            seg = _clip_line_to_box(
                float(pts[A][0]), float(pts[A][1]),
                float(direction[0]), float(direction[1]),
                clip[0], clip[1], clip[2], clip[3],
            )
            if seg is None:
                raise GeometryError(f"*line({A} ; {B} ; infinite) misses the scene bounds — skipping")
            (x1, y1), (x2, y2) = seg
            lines.append(f'  line(({x1:.3f}, {y1:.3f}), ({x2:.3f}, {y2:.3f}))')
            return
        lines.append(f'  line({_q(A)}, {_q(B)})')

    elif cmd == 'ray':
        if len(args) != 2:
            raise GeometryError(f"*ray requires 2 args: start ; through (got {len(args)})")
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
        if len(args) != 2:
            raise GeometryError(f"*circle requires 2 args: center ; radius-or-point (got {len(args)})")
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
            if float(d) > 1e6:
                raise GeometryError(f"circle radius exceeds the canvas limit (1e6) — skipping")
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
            if r > 1e6:
                raise GeometryError(f"circle radius exceeds the canvas limit (1e6), got: {r_or_pt!r}")
            if r <= 0:
                raise GeometryError(f"circle radius must be positive, got: {r_or_pt!r}")
            lines.append(f'  circle({_q(center)}, radius: {r:.3f})')

    elif cmd == 'right-angle':
        # Convention: right-angle(B ; A ; C) → right angle at vertex A
        if len(args) != 3:
            raise GeometryError(f"*right-angle requires 3 args: B ; A ; C (got {len(args)})")
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

    elif cmd == 'arc':
        # Arc of the circle centered at O from A to B (counterclockwise).
        if len(args) != 3:
            raise GeometryError(f"*arc requires 3 args: center ; start ; end (got {len(args)})")
        O, A, B = [a.strip() for a in args[:3]]
        for pt in [O, A, B]:
            if pt not in pts:
                raise GeometryError(f"undefined point '{pt}'")
        _require_finite_pts(pts, [O, A, B])
        import math as _math

        ox, oy = float(pts[O][0]), float(pts[O][1])
        ax, ay = float(pts[A][0]), float(pts[A][1])
        r = _math.hypot(ax - ox, ay - oy)
        if not _math.isfinite(r) or r < 1e-9:
            raise GeometryError(f"*arc({O} ; {A} ; {B}): center and start coincide — skipping")
        a1 = _vec_angle_deg(pts[A] - pts[O])
        a2 = _vec_angle_deg(pts[B] - pts[O])
        sweep = (a2 - a1) % 360.0
        if sweep < 0.5 or sweep > 359.5:
            raise GeometryError(f"*arc({O} ; {A} ; {B}): degenerate (zero/full-circle) sweep — skipping")
        stop = a1 + sweep
        lines.append(
            f'  arc(({ax:.3f}, {ay:.3f}), start: {a1:.2f}deg, '
            f'stop: {stop:.2f}deg, radius: {r:.3f})'
        )

    elif cmd == 'angle':
        # Angle marker at vertex B (middle argument), arms toward A and C.
        if len(args) not in (3, 4):
            raise GeometryError(f"*angle requires 3 args: A ; B ; C (optional 4th: label) (got {len(args)})")
        A, B, C = [a.strip() for a in args[:3]]
        for pt in [A, B, C]:
            if pt not in pts:
                raise GeometryError(f"undefined point '{pt}'")
        _require_finite_pts(pts, [A, B, C])
        import math as _math

        v1, v2 = pts[A] - pts[B], pts[C] - pts[B]
        n1, n2 = float(_norm(v1)), float(_norm(v2))
        if not (_math.isfinite(n1) and _math.isfinite(n2)):
            raise GeometryError(f"*angle({A} ; {B} ; {C}): non-finite arms — skipping")
        if n1 < 1e-9 or n2 < 1e-9:
            raise GeometryError(f"*angle({A} ; {B} ; {C}): coincident points — skipping")
        a1 = _vec_angle_deg(v1)
        sweep = (_vec_angle_deg(v2) - a1) % 360.0
        if sweep > 180.0:
            # Marker shows the interior (minor) arc, not the reflex one.
            a1 = (a1 + sweep) % 360.0
            sweep = 360.0 - sweep
        bx, by = float(pts[B][0]), float(pts[B][1])
        ux, uy = float(v1[0]) / n1, float(v1[1]) / n1
        sx, sy = bx + 0.4 * ux, by + 0.4 * uy
        if sweep < 0.5 or sweep > 359.5:
            lines.append(f'  // [GeometryWarning] *angle({A} ; {B} ; {C}) is ~0°/180°/360° — no arc drawn')
        else:
            lines.append(
                f'  arc(({sx:.3f}, {sy:.3f}), start: {a1:.2f}deg, '
                f'stop: {a1 + sweep:.2f}deg, radius: 0.400)'
            )
        if len(args) == 4 and args[3].strip():
            mid = _math.radians(a1 + sweep / 2.0)
            lx, ly = bx + 0.68 * _math.cos(mid), by + 0.68 * _math.sin(mid)
            lines.append(f'  content(({lx:.3f}, {ly:.3f}), [#"{_safe_text(args[3].strip())}"])')

    elif cmd == 'label':
        # Custom text label attached to a point (beyond the auto label).
        if len(args) != 2:
            raise GeometryError(f"*label requires 2 args: point ; text (got {len(args)})")
        P, text = args[0].strip(), args[1].strip()
        if P not in pts:
            raise GeometryError(f"undefined point '{P}'")
        _require_finite_pts(pts, [P])
        if not text:
            raise GeometryError("*label requires non-empty text")
        lines.append(
            f'  content({_q(P)}, [#"{_safe_text(text)}"], '
            f'anchor: "{_label_anchors(solver).get(P, "south-west")}", padding: 0.35)'
        )

    elif cmd == 'length':
        # Measured length of AB as a label at the segment midpoint.
        if len(args) != 2:
            raise GeometryError(f"*length requires 2 args: A ; B (got {len(args)})")
        A, B = args[0].strip(), args[1].strip()
        for pt in [A, B]:
            if pt not in pts:
                raise GeometryError(f"undefined point '{pt}'")
        _require_finite_pts(pts, [A, B])
        import math as _math

        d = float(_norm(pts[B] - pts[A]))
        if not _math.isfinite(d):
            raise GeometryError(f"*length({A} ; {B}): non-finite segment — skipping")
        if d < 1e-9:
            raise GeometryError(f"*length({A} ; {B}): zero-length segment — skipping")
        shown = _safe_text(annot) if annot else _fmt_num(d)
        ax, ay = float(pts[A][0]), float(pts[A][1])
        bx, by = float(pts[B][0]), float(pts[B][1])
        mx, my = (ax + bx) / 2.0, (ay + by) / 2.0
        # Offset perpendicular to the segment so the text clears the line.
        px, py = -(by - ay) / d, (bx - ax) / d
        lines.append(
            f'  content(({mx + 0.18 * px:.3f}, {my + 0.18 * py:.3f}), [#"{shown}"])'
        )

    elif cmd == 'angle-value':
        # Measured angle ABC (vertex B) as an arc marker plus degrees label.
        if len(args) != 3:
            raise GeometryError(f"*angle-value requires 3 args: A ; B ; C (got {len(args)})")
        A, B, C = [a.strip() for a in args[:3]]
        for pt in [A, B, C]:
            if pt not in pts:
                raise GeometryError(f"undefined point '{pt}'")
        _require_finite_pts(pts, [A, B, C])
        import math as _math

        v1, v2 = pts[A] - pts[B], pts[C] - pts[B]
        deg = _minor_angle_deg(v1, v2)
        if not _math.isfinite(deg):
            raise GeometryError(f"*angle-value({A} ; {B} ; {C}): non-finite angle — skipping")
        a1 = _vec_angle_deg(v1)
        sweep = (_vec_angle_deg(v2) - a1) % 360.0
        if sweep > 180.0:
            # Marker shows the interior (minor) arc, not the reflex one.
            a1 = (a1 + sweep) % 360.0
            sweep = 360.0 - sweep
        bx, by = float(pts[B][0]), float(pts[B][1])
        n1 = float(_norm(v1))
        sx, sy = bx + 0.3 * float(v1[0]) / n1, by + 0.3 * float(v1[1]) / n1
        if sweep < 0.5 or sweep > 359.5:
            lines.append(f'  // [GeometryWarning] *angle-value({A} ; {B} ; {C}) is ~0°/180°/360° — no arc drawn')
        else:
            lines.append(
                f'  arc(({sx:.3f}, {sy:.3f}), start: {a1:.2f}deg, '
                f'stop: {a1 + sweep:.2f}deg, radius: 0.300)'
            )
        shown = _safe_text(annot) if annot else f'{_fmt_num(deg)}°'
        mid = _math.radians(a1 + sweep / 2.0)
        lx, ly = bx + 0.58 * _math.cos(mid), by + 0.58 * _math.sin(mid)
        lines.append(f'  content(({lx:.3f}, {ly:.3f}), [#"{shown}"])')

    elif cmd in ('equal-angle',):
        # Planned but not yet implemented
        lines.append(f'  // [planned] *{_safe_err(cmd)}({_safe_err("; ".join(args))}) not yet implemented')

    else:
        # Unknown — already warned during parse
        pass
