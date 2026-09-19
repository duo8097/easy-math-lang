import re
import math
import sys
import hashlib
import numpy as np

# ---------------------------------------------------------------------------
# Argument splitting (depth-aware, handles nested parentheses)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Geometry errors
# ---------------------------------------------------------------------------

class GeometryError(Exception):
    pass

class GeometryWarning(Exception):
    pass


# ---------------------------------------------------------------------------
# Constraint-based solver
# ---------------------------------------------------------------------------

class GeometrySolver:
    def __init__(self):
        self.points = {}        # name -> np.array([x, y])
        self.fixed = set()
        self.constraints = []   # list of (label, lambda P: cost)
        self.draw_commands = [] # list of (cmd, args)

    def add_point(self, name, x=None, y=None):
        if x is not None and y is not None:
            # Explicit coordinates always win, even if the point was
            # previously auto-created by a constraint.
            self.points[name] = np.array([float(x), float(y)])
            self.fixed.add(name)
        elif name not in self.points:
            # Deterministic layout (no RNG): spread points on a circle
            # based on a stable hash of the name so repeated runs
            # (including across processes) are identical.
            h = int(hashlib.md5(name.encode('utf-8')).hexdigest(), 16) % 360
            r = 3.0
            ang = math.radians(h)
            self.points[name] = np.array([r * math.cos(ang), r * math.sin(ang)])

    def add_constraint(self, label, fn):
        self.constraints.append((label, fn))

    def validate(self):
        """Check for undefined points before solving."""
        for cmd, args in self.draw_commands:
            for arg in args:
                arg = arg.strip()
                if arg.lower() == 'infinite':
                    continue
                # point names are single tokens that look like identifiers
                if re.match(r'^[A-Za-z][A-Za-z0-9_]*$', arg) and arg not in self.points:
                    # Could be a numeric value or keyword — only flag if it looks like a point ref
                    # We accept it if no point with that name exists AND it's not numeric
                    try:
                        float(arg)
                    except ValueError:
                        # It's not numeric — check draw-relevant commands
                        point_using_cmds = {
                            'line', 'ray', 'triangle', 'circle', 'right-angle',
                            'angle', 'equal-length', 'parallel', 'perp',
                            'on-line', 'on-circle', 'distance', 'midpoint',
                            'intersection', 'equal-angle',
                        }
                        if cmd in point_using_cmds:
                            raise GeometryError(
                                f"undefined point '{arg}' referenced in *{cmd}({'; '.join(args)})"
                            )

    def solve(self):
        lr = 0.01
        momentum = 0.9
        velocity = {p: np.zeros(2) for p in self.points if p not in self.fixed}

        def eval_constraints(pts):
            total = 0.0
            for _label, fn in self.constraints:
                total += fn(pts)
            return total

        for _step in range(5000):
            eps = 1e-5
            base_cost = eval_constraints(self.points)
            if base_cost < 1e-4:
                break

            grads = {p: np.zeros(2) for p in self.points if p not in self.fixed}
            for p in self.points:
                if p in self.fixed:
                    continue
                orig = self.points[p].copy()

                self.points[p][0] += eps
                cx = eval_constraints(self.points)
                self.points[p][0] = orig[0]

                self.points[p][1] += eps
                cy = eval_constraints(self.points)
                self.points[p][1] = orig[1]

                grads[p][0] = (cx - base_cost) / eps
                grads[p][1] = (cy - base_cost) / eps

            for p in self.points:
                if p not in self.fixed:
                    velocity[p] = momentum * velocity[p] - lr * grads[p]
                    self.points[p] += velocity[p]

        final_cost = eval_constraints(self.points)

        # Check per-constraint residuals to distinguish conflict from non-convergence
        if final_cost > 1e-2:
            residuals = [(label, fn(self.points)) for label, fn in self.constraints]
            conflicting = [(lbl, r) for lbl, r in residuals if r > 1e-2]

            if len(conflicting) > 1:
                labels = ', '.join(lbl for lbl, _ in conflicting)
                raise GeometryError(
                    f"constraint conflict — these constraints cannot be satisfied simultaneously: {labels}"
                )
            else:
                label = conflicting[0][0] if conflicting else "unknown"
                raise GeometryWarning(
                    f"solver did not converge (cost={final_cost:.4f}) "
                    f"near constraint '{label}' — diagram may be incorrect"
                )


# ---------------------------------------------------------------------------
# Vector helpers
# ---------------------------------------------------------------------------

def _norm(v):
    return np.linalg.norm(v)

def _cross2d(v1, v2):
    return v1[0] * v2[1] - v1[1] * v2[0]

def _normalize(v):
    n = _norm(v)
    if n < 1e-9:
        return v
    return v / n


# ---------------------------------------------------------------------------
# Bounding box helpers
# ---------------------------------------------------------------------------

def _bounding_box(points_dict):
    """Return (xmin, ymin, xmax, ymax) of all points."""
    xs = [p[0] for p in points_dict.values()]
    ys = [p[1] for p in points_dict.values()]
    return min(xs), min(ys), max(xs), max(ys)


def _ray_bbox_intersect(origin, direction, xmin, ymin, xmax, ymax, margin=0.5):
    """
    Find the largest t > 0 such that origin + t*direction is inside the
    bounding box (expanded by margin).  Returns t, or a fallback of 3.0.
    """
    ox, oy = origin
    dx, dy = direction
    xmin, ymin, xmax, ymax = xmin - margin, ymin - margin, xmax + margin, ymax + margin

    t_max = 3.0  # fallback
    candidates = []

    # intersect with each of the 4 planes
    if abs(dx) > 1e-9:
        for bx in (xmin, xmax):
            t = (bx - ox) / dx
            if t > 1e-6:
                iy = oy + t * dy
                if ymin <= iy <= ymax:
                    candidates.append(t)
    if abs(dy) > 1e-9:
        for by in (ymin, ymax):
            t = (by - oy) / dy
            if t > 1e-6:
                ix = ox + t * dx
                if xmin <= ix <= xmax:
                    candidates.append(t)

    if candidates:
        t_max = max(candidates)

    return t_max


# ---------------------------------------------------------------------------
# Depth-counting command parser
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

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


def _process_command(solver, cmd, args):
    """Register a geometry command into the solver."""

    KNOWN_GEOMETRY_COMMANDS = {
        'point', 'line', 'ray', 'circle', 'triangle', 'right-angle', 'angle',
        'equal-angle', 'equal-length', 'parallel', 'perp', 'on-line', 'on-circle',
        'distance', 'midpoint', 'intersection', 'arc', 'label',
        'length', 'angle-value',
    }

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


# ---------------------------------------------------------------------------
# Typst / CeTZ code generation
# ---------------------------------------------------------------------------

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
        n = _norm(d)
        if n < 1e-9:
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
        for cname, r in circles:
            if name == cname:
                continue
            dvec = pts[name] - pts[cname]
            d = _norm(dvec)
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
        sx = sum(v[0] for v in dirs)
        sy = sum(v[1] for v in dirs)
        if math.hypot(sx, sy) < 1e-9:
            anchors[name] = 'south-west'
            continue
        # Label sits opposite the incident edges; the anchor is the body
        # corner touching the point, i.e. the compass opposite.
        ang = math.degrees(math.atan2(-sy, -sx))
        anchors[name] = compass_anchor_for_sit_angle(ang)
    return anchors


def generate_typst(solver, errors=None):
    lines = []
    lines.append('#import "@preview/cetz:0.4.2"')
    lines.append('#align(center)[#cetz.canvas({')
    lines.append('  import cetz.draw: *')

    # Embed any geometry errors as comments
    for err in (errors or []):
        lines.append(f'  // {err}')

    # Draw point dots + labels (labels auto-placed away from edges)
    anchors = _label_anchors(solver)
    for p, coord in solver.points.items():
        lines.append(
            f'  circle(({coord[0]:.3f}, {coord[1]:.3f}), radius: 0.05, '
            f'fill: black, name: "{p}")'
        )
        lines.append(
            f'  content("{p}", [{p}], anchor: "{anchors.get(p, "south-west")}", '
            f'padding: 0.12)'
        )

    # Compute bounding box for ray extension
    if solver.points:
        xmin, ymin, xmax, ymax = _bounding_box(solver.points)
    else:
        xmin, ymin, xmax, ymax = -5, -5, 5, 5

    for cmd, args in solver.draw_commands:
        try:
            _generate_command(lines, solver, cmd, args, xmin, ymin, xmax, ymax)
        except GeometryError as e:
            lines.append(f'  // [GeometryError] *{cmd}: {e}')
            print(f"[GeometryError] *{cmd}({'; '.join(args)}): {e}", file=sys.stderr)

    lines.append('})]')
    return '\n'.join(lines)


def _generate_command(lines, solver, cmd, args, xmin, ymin, xmax, ymax):
    pts = solver.points

    if cmd == 'triangle':
        if len(args) < 3:
            raise GeometryError("*triangle requires 3 point args")
        A, B, C = [a.strip() for a in args[:3]]
        for pt in [A, B, C]:
            if pt not in pts:
                raise GeometryError(f"undefined point '{pt}'")
        lines.append(f'  line("{A}", "{B}", "{C}", close: true)')

    elif cmd == 'line':
        if len(args) < 2:
            raise GeometryError("*line requires 2 point args")
        A, B = args[0].strip(), args[1].strip()
        for pt in [A, B]:
            if pt not in pts:
                raise GeometryError(f"undefined point '{pt}'")
        if _norm(pts[A] - pts[B]) < 1e-9:
            raise GeometryError(f"zero-length line between {A} and {B}")
        lines.append(f'  line("{A}", "{B}")')

    elif cmd == 'ray':
        if len(args) < 2:
            raise GeometryError("*ray requires 2 point args: start ; through")
        A, B = args[0].strip(), args[1].strip()
        for pt in [A, B]:
            if pt not in pts:
                raise GeometryError(f"undefined point '{pt}'")
        diff = pts[B] - pts[A]
        if _norm(diff) < 1e-9:
            raise GeometryError(f"zero-length ray: A and B are the same point ({A})")
        direction = _normalize(diff)
        t_max = _ray_bbox_intersect(pts[A], direction, xmin, ymin, xmax, ymax)
        end = pts[A] + t_max * direction
        ax, ay = pts[A]
        ex, ey = end
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
        if r_or_pt in pts:
            # radius = distance from center to the given point
            d = _norm(pts[center] - pts[r_or_pt])
            lines.append(f'  circle("{center}", radius: {d:.3f})')
        else:
            try:
                r = float(r_or_pt)
            except ValueError:
                raise GeometryError(
                    f"circle radius must be numeric or an existing point name, got: {r_or_pt!r}"
                )
            lines.append(f'  circle("{center}", radius: {r:.3f})')

    elif cmd == 'right-angle':
        # Convention: right-angle(B ; A ; C) → right angle at vertex A
        if len(args) < 3:
            raise GeometryError("*right-angle requires 3 args: B ; A ; C")
        B, A, C = [a.strip() for a in args[:3]]
        for pt in [A, B, C]:
            if pt not in pts:
                raise GeometryError(f"undefined point '{pt}'")
        pA, pB, pC = pts[A], pts[B], pts[C]
        vAB = pB - pA
        vAC = pC - pA
        if _norm(vAB) < 1e-9:
            raise GeometryError(f"coincident points: {B} and {A} are the same point")
        if _norm(vAC) < 1e-9:
            raise GeometryError(f"coincident points: {C} and {A} are the same point")
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
                 'equal-length', 'midpoint', 'intersection', 'equal-angle'):
        # Constraint-only commands — nothing to draw
        pass

    elif cmd in ('arc', 'angle', 'label', 'length', 'angle-value'):
        # Planned but not yet implemented
        lines.append(f'  // [planned] *{cmd}({"; ".join(args)}) not yet implemented')

    else:
        # Unknown — already warned during parse
        pass
