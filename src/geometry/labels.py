"""Automatic point-label placement (labels avoid incident edges)."""

import math

from .vectors import _norm

# Compass directions (canvas is y-up, like solver coordinates).
_COMPASS = (
    'east', 'north-east', 'north', 'north-west',
    'west', 'south-west', 'south', 'south-east',
)


def _label_anchors(solver):
    """Compute a label anchor per point, avoiding incident edges.

    For every drawn edge touching a point (line, ray, triangle sides,
    angle/right-angle/arc arms, circle outlines), collect the unit
    direction *away* from the point along that edge.  The label is placed
    opposite to the summed direction, i.e. away from the figure.

    Exception: a point lying essentially on a drawn circle's circumference
    (e.g. a tangent endpoint solved onto the outline) is labeled along the
    outward normal, ignoring other edges — otherwise the label can end up
    hugging the circle.

    Returns a dict mapping point name -> CeTZ content anchor.  The anchor
    names the body corner touching the point, so it is the compass
    opposite of where the label sits.  Points with no (or symmetric)
    incident edges keep the legacy "south-west" default.
    """
    pts = solver.points
    edge_dirs = {name: [] for name in pts}

    def away(frm, to):
        if frm not in edge_dirs or to not in pts:
            return None
        d = pts[to] - pts[frm]
        import math as _math

        # Non-finite coordinates (NaN/inf from a diverged solver) must
        # never propagate into anchor math: atan2/int(NaN) would crash
        # the whole canvas. Skip the edge; the point keeps its default.
        try:
            if not (_math.isfinite(float(d[0])) and _math.isfinite(float(d[1]))):
                return None
        except (TypeError, ValueError, IndexError):
            return None
        n = _norm(d)
        import math as _math2

        if not _math2.isfinite(n) or n < 1e-9:
            return None
        return d / n

    def add_arm(vertex, end1, end2):
        for end in (end1, end2):
            v = away(vertex, end)
            if v is not None:
                edge_dirs[vertex].append(v)

    # Resolved drawn circles: (center_name, radius).
    circles = []
    for cmd, args in solver.draw_commands:
        a = [x.strip() for x in args]
        if cmd == 'circle' and len(a) >= 2 and a[0] in pts:
            r = None
            if a[1] in pts:
                r = _norm(pts[a[1]] - pts[a[0]])
            else:
                try:
                    r = float(a[1])
                except ValueError:
                    r = None
            if r is not None and r > 1e-9:
                circles.append((a[0], r))

    def compass_anchor_for_sit_angle(ang):
        """CeTZ anchor for a label sitting at compass angle `ang`."""
        idx = int((ang % 360 + 22.5) // 45) % 8
        return _COMPASS[(idx + 4) % 8]

    for cmd, args in solver.draw_commands:
        a = [x.strip() for x in args]
        if cmd == 'line' and len(a) >= 2:
            v = away(a[0], a[1])
            if v is not None:
                edge_dirs[a[0]].append(v)
                edge_dirs[a[1]].append(-v)
        elif cmd == 'ray' and len(a) >= 2:
            v = away(a[0], a[1])
            if v is not None:
                # The ray leaves A toward B and continues past B.
                edge_dirs[a[0]].append(v)
                edge_dirs[a[1]].append(v)
        elif cmd == 'triangle' and len(a) >= 3:
            corners = a[:3]
            if all(c in pts for c in corners):
                for i in range(3):
                    add_arm(corners[i], corners[(i + 1) % 3], corners[(i + 2) % 3])
        elif cmd in ('angle', 'right-angle') and len(a) >= 3:
            # Convention: the middle argument is the vertex.
            if a[1] in pts:
                add_arm(a[1], a[0], a[2])
        elif cmd == 'arc' and len(a) >= 3:
            # arc(center ; start ; end): arms leave the center.
            if a[0] in pts:
                add_arm(a[0], a[1], a[2])
        elif cmd == 'circle' and len(a) >= 2:
            if a[0] in pts and a[1] in pts:
                # Label the on-circle point along the outward normal.  The
                # pipeline places labels opposite the summed dirs, so store
                # the negated center->point vector.  The center itself is
                # surrounded: keep the default.
                v = away(a[0], a[1])
                if v is not None:
                    edge_dirs[a[1]].append(-v)

    anchors = {}
    for name, dirs in edge_dirs.items():
        # Near-circle override: label along the outward normal.
        outward = None
        try:
            pvec = pts[name]
            pfinite = bool(
                math.isfinite(float(pvec[0])) and math.isfinite(float(pvec[1]))
            )
        except (TypeError, ValueError, IndexError):
            pfinite = False
        if not pfinite:
            anchors[name] = 'south-west'
            continue
        for cname, r in circles:
            if name == cname:
                continue
            try:
                cvec = pts[cname]
                if not (math.isfinite(float(cvec[0])) and math.isfinite(float(cvec[1]))):
                    continue
                if not math.isfinite(float(r)):
                    continue
            except (TypeError, ValueError, IndexError):
                continue
            dvec = pvec - cvec
            d = _norm(dvec)
            if not math.isfinite(d):
                continue
            if d > 1e-9 and abs(d - r) < min(0.25, 0.5 * r):
                outward = dvec / d
                break
        if outward is not None:
            ang = math.degrees(math.atan2(outward[1], outward[0]))
            anchors[name] = compass_anchor_for_sit_angle(ang)
            continue
        if not dirs:
            anchors[name] = 'south-west'
            continue
        # Filter non-finite edge dirs (can arise from NaN/inf points).
        fdirs = []
        for v in dirs:
            try:
                if math.isfinite(float(v[0])) and math.isfinite(float(v[1])):
                    fdirs.append(v)
            except (TypeError, ValueError, IndexError):
                continue
        if not fdirs:
            anchors[name] = 'south-west'
            continue
        sx = sum(v[0] for v in fdirs)
        sy = sum(v[1] for v in fdirs)
        if not (math.isfinite(sx) and math.isfinite(sy)):
            anchors[name] = 'south-west'
            continue
        if math.hypot(sx, sy) < 1e-9:
            anchors[name] = 'south-west'
            continue
        # Label sits opposite the incident edges; the anchor is the body
        # corner touching the point, i.e. the compass opposite.
        ang = math.degrees(math.atan2(-sy, -sx))
        anchors[name] = compass_anchor_for_sit_angle(ang)
    return anchors
