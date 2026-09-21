"""Constraint-based geometry solver."""

import hashlib
import math
import re
import sys

import numpy as np

from .errors import GeometryError, GeometryWarning
from .vectors import _cross2d, _norm


class GeometrySolver:
    def __init__(self):
        self.points = {}        # name -> np.array([x, y])
        self.fixed = set()
        self.constraints = []   # list of (label, lambda P: cost)
        self.draw_commands = []  # list of (cmd, args)

    def add_point(self, name, x=None, y=None):
        if x is not None and y is not None:
            import math as _math

            fx, fy = float(x), float(y)
            if not (_math.isfinite(fx) and _math.isfinite(fy)):
                raise GeometryError(f"invalid coordinates for point '{name}': ({x}, {y}) must be finite")
            new_pt = np.array([fx, fy])
            if name in self.fixed:
                old = self.points[name]
                if _norm(old - new_pt) > 1e-9:
                    raise GeometryError(
                        f"duplicate definition of point '{name}' with different coordinates"
                    )
                return
            # Explicit coordinates always win, even if the point was
            # previously auto-created by a constraint.
            self.points[name] = new_pt
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
            for i, arg in enumerate(args):
                arg = arg.strip()
                if arg.lower() == 'infinite':
                    continue
                if cmd == 'triangle' and i == 3 and arg.lower() == 'labels':
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

        import math as _math

        for _step in range(5000):
            eps = 1e-5
            base_cost = eval_constraints(self.points)
            if not _math.isfinite(base_cost):
                raise GeometryError(
                    "solver diverged (non-finite cost) — check constraints for degeneracy"
                )
            # Positions can go non-finite while cost stays finite.
            for _p, _c in self.points.items():
                try:
                    if not (_math.isfinite(float(_c[0])) and _math.isfinite(float(_c[1]))):
                        raise GeometryError(
                            "solver diverged (non-finite coordinates) — check constraints for degeneracy"
                        )
                except (TypeError, ValueError, IndexError):
                    raise GeometryError(
                        "solver diverged (invalid coordinates) — check constraints for degeneracy"
                    )
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
                    step = momentum * velocity[p] - lr * grads[p]
                    # Gradient clipping: a coincident-segment cliff can
                    # otherwise fling points to infinity in one step.
                    n = float(np.linalg.norm(step))
                    if _math.isfinite(n) and n > 1.0:
                        step = step * (1.0 / n)
                    velocity[p] = step
                    self.points[p] += velocity[p]
                    # Clamp to a sane canvas so one bad step cannot blow up.
                    # NOTE: max/min launders NaN (nan comparisons are False,
                    # so max(-1e6, min(1e6, nan)) == 1e6): check finiteness
                    # first so divergence is raised, not hidden.
                    for _axis in (0, 1):
                        _v = float(self.points[p][_axis])
                        if not _math.isfinite(_v):
                            raise GeometryError(
                                "solver diverged (non-finite coordinates) — check constraints for degeneracy"
                            )
                        self.points[p][_axis] = max(-1e6, min(1e6, _v))

        final_cost = eval_constraints(self.points)
        import math as _math2

        if not _math2.isfinite(final_cost):
            raise GeometryError(
                "solver diverged (non-finite final cost) — diagram coordinates invalid"
            )
        for _p, _c in self.points.items():
            try:
                if not (_math2.isfinite(float(_c[0])) and _math2.isfinite(float(_c[1]))):
                    raise GeometryError(
                        "solver diverged (non-finite final coordinates) — diagram coordinates invalid"
                    )
            except (TypeError, ValueError, IndexError):
                raise GeometryError(
                    "solver diverged (invalid final coordinates) — diagram coordinates invalid"
                )

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
                if conflicting:
                    label = conflicting[0][0]
                elif residuals:
                    # Many small residuals can sum past the threshold with
                    # none individually over it: report the worst one.
                    label = max(residuals, key=lambda t: t[1])[0]
                else:
                    label = "unknown"
                raise GeometryWarning(
                    f"solver did not converge (cost={final_cost:.4f}) "
                    f"near constraint '{label}' — diagram may be incorrect"
                )
