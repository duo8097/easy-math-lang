"""Constraint-based geometry solver."""

import hashlib
import math
import re
import sys

from .errors import GeometryError, GeometryWarning
from .vectors import _norm


class _DerivedPoint:
    """A constructed point: computed analytically, never a free variable.

    ``compute(pts)`` maps the solver's points to the new position (see
    ``geometry.constructions.Construction``); ``deps`` are the point
    names it reads, used to order the computations.
    """

    __slots__ = ('deps', 'compute', 'label')

    def __init__(self, deps, compute, label):
        self.deps = frozenset(deps)
        self.compute = compute
        self.label = label


class GeometrySolver:
    def __init__(self):
        self.points = {}        # name -> np.array([x, y])
        self.fixed = set()
        self.derived = {}       # name -> _DerivedPoint (constructed points)
        # list of (label, fn, deps): deps are the point names the
        # constraint reads, used to skip constraints that reference a
        # construction that failed.
        self.constraints = []
        self.draw_commands = []  # list of (cmd, args)
        self.draw_annotations = {}  # draw_commands index -> trailing "= value" text
        self.solve_errors = []   # construction failures found by solve()

    def _is_free(self, name):
        """True when the solver may move *name* (not fixed, not constructed)."""
        return name not in self.fixed and name not in self.derived

    def add_point(self, name, x=None, y=None):
        # Local import: keeps `import geometry` free of NumPy until the
        # solver actually runs (editor/LSP startup stays light). Kept at
        # function top (not inside a branch) so every path below sees it.
        import numpy as np
        if (x is None) != (y is None):
            raise GeometryError(
                f"point '{name}': both coordinates required, got x={x!r} y={y!r}"
            )
        if x is not None and y is not None:
            import math as _math

            if name in self.derived:
                raise GeometryError(
                    f"point '{name}' is constructed by *point({name} = ...) — "
                    f"remove the extra coordinates (a constructed point is "
                    f"computed, not free)"
                )
            fx, fy = float(x), float(y)
            if not (_math.isfinite(fx) and _math.isfinite(fy)):
                raise GeometryError(f"invalid coordinates for point '{name}': ({x}, {y}) must be finite")
            # Canvas limit (matches the solver's ±1e6 clamp on free points):
            # absurd magnitudes would emit unrenderable coordinates.
            if abs(fx) > 1e6 or abs(fy) > 1e6:
                raise GeometryError(
                    f"coordinates for point '{name}' exceed the canvas limit (±1e6): ({x}, {y})"
                )
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
            # Deterministic layout (no RNG): spread points on a golden-angle
            # spiral keyed by a stable hash so repeated runs (including
            # across processes) are identical and collisions are rare.
            digest = hashlib.md5(name.encode('utf-8')).hexdigest()
            h = int(digest[:8], 16)
            h2 = int(digest[8:16], 16)
            ang = math.radians(h % 360) + (h2 % 100) * 0.01
            r = 3.0 + (h2 % 200) * 0.02
            self.points[name] = np.array([r * math.cos(ang), r * math.sin(ang)])

    def add_constraint(self, label, fn, deps=()):
        self.constraints.append((label, fn, tuple(deps)))

    def add_derived_point(self, name, deps, compute, label=None):
        """Register a constructed point (computed analytically).

        The point is seeded with the usual deterministic placeholder so
        validation and codegen always see it, but it is never a free
        variable: every cost evaluation recomputes it from *deps* in
        dependency order (see :meth:`_derived_order`).
        """
        if name in self.fixed:
            raise GeometryError(
                f"point '{name}' already has coordinates — it cannot also "
                f"be constructed"
            )
        if name in self.derived:
            raise GeometryError(
                f"constructed point '{name}' is defined twice"
            )
        self.add_point(name)  # placeholder position until solve()
        self.derived[name] = _DerivedPoint(
            deps, compute, label or f'point {name}'
        )

    def _derived_order(self):
        """Topological order of constructed points (dependencies first).

        Reports self-references and cycles — a construction that needs
        itself (directly or through other constructions) can never be
        computed, i.e. it is a use-before-define paradox.
        """
        order = []
        state = {}   # name -> True while visiting, False once done
        stack = []

        def visit(name):
            st = state.get(name)
            if st is False:
                return
            if st is True:
                cycle = stack[stack.index(name):] + [name]
                raise GeometryError(
                    "construction cycle: "
                    + " -> ".join(cycle)
                    + " — a constructed point cannot depend on itself"
                )
            state[name] = True
            stack.append(name)
            for dep in sorted(self.derived[name].deps):
                if dep in self.derived:
                    visit(dep)
            stack.pop()
            state[name] = False
            order.append(name)

        for name in sorted(self.derived):
            visit(name)
        return order

    def validate(self):
        """Check for undefined points before solving."""
        # Arity for point-position args; anything past is malformed and
        # reported by codegen, not as a misleading 'undefined point'.
        _arity = {
            'triangle': 3, 'line': 2, 'ray': 2, 'circle': 2,
            'right-angle': 3, 'arc': 3, 'length': 2, 'angle-value': 3,
            'label': 1, 'angle': 3, 'equal-angle': 6,
        }
        _keywords = {
            'infinite', 'labels', 'line', 'ray', 'circle', 'point',
            'triangle', 'arc', 'distance', 'midpoint', 'intersection',
        }
        for cmd, args in self.draw_commands:
            max_pts = _arity.get(cmd)
            for i, arg in enumerate(args):
                arg = arg.strip()
                if max_pts is not None and i >= max_pts:
                    continue
                if arg.lower() in _keywords:
                    continue
                # *circle(O ; r): the radius slot must be numeric or a
                # point name — but it is NOT a point reference, so report
                # it as such instead of "undefined point".
                if cmd == 'circle' and i == 1:
                    if arg in self.points:
                        continue
                    from .commands import parse_numeric_arg
                    try:
                        parse_numeric_arg(arg)
                        continue
                    except ValueError:
                        raise GeometryError(
                            f"circle radius must be numeric or an existing point name, "
                            f"got: {arg!r} in *circle({'; '.join(args)})"
                        )
                # Nested refs like line(A;B) / line(D;Typo): validate the
                # inner identifiers so typos don't become phantom points.
                if '(' in arg or ';' in arg:
                    for tok in re.findall(r'[A-Za-z][A-Za-z0-9_]*', arg):
                        if tok.lower() in _keywords:
                            continue
                        if tok not in self.points:
                            try:
                                float(tok)
                                continue
                            except ValueError:
                                pass
                            point_using_cmds = {
                                'line', 'ray', 'triangle', 'circle', 'right-angle',
                                'angle', 'equal-length', 'parallel', 'perp',
                                'on-line', 'on-circle', 'distance', 'midpoint',
                                'intersection', 'equal-angle', 'arc', 'label',
                                'length', 'angle-value',
                            }
                            if cmd in point_using_cmds:
                                raise GeometryError(
                                    f"undefined point '{tok}' referenced in *{cmd}({'; '.join(args)})"
                                )
                    continue
                if cmd == 'triangle' and i == 3 and arg.lower() == 'labels':
                    continue
                # Text (not point) args: *label(P ; text), *angle(A;B;C;label).
                if cmd == 'label' and i >= 1:
                    continue
                if cmd == 'angle' and i >= 3:
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
                            'intersection', 'equal-angle', 'arc', 'label',
                            'length', 'angle-value',
                        }
                        if cmd in point_using_cmds:
                            raise GeometryError(
                                f"undefined point '{arg}' referenced in *{cmd}({'; '.join(args)})"
                            )

    def solve(self):
        # Local import: keeps `import geometry` free of NumPy until the
        # solver actually runs (editor/LSP startup stays light).
        import numpy as np

        lr = 0.01
        momentum = 0.9
        derived_order = self._derived_order()
        velocity = {p: np.zeros(2) for p in self.points if self._is_free(p)}

        def eval_derived(pts):
            """Recompute constructed points; return {name: msg} failures.

            Never raises: one failing construction (its line misses a
            circle, its triangle is degenerate, …) must not abort the
            whole solve nor poison unrelated constraints/constructions.
            Dependents of a failed construction are marked failed too.
            """
            failed = {}
            for pname in derived_order:
                entry = self.derived[pname]
                bad_deps = [d for d in entry.deps if d in failed]
                if bad_deps:
                    failed[pname] = (
                        f"depends on {', '.join(sorted(bad_deps))}, "
                        f"which could not be constructed")
                    continue
                try:
                    val = entry.compute(pts)
                except GeometryError as e:
                    failed[pname] = str(e)
                    continue
                except Exception as e:
                    failed[pname] = (
                        f"construction for point '{pname}' "
                        f"({entry.label}) failed: {e}")
                    continue
                pts[pname] = np.asarray(val, dtype=float)
            return failed

        def eval_constraints(pts):
            # Constructed points track their inputs: recompute them
            # before every cost evaluation so gradients flow *through*
            # them to the free points they depend on. pts is always
            # self.points (constraints index it by name at call time).
            failed = eval_derived(pts)
            total = 0.0
            for _label, fn, deps in self.constraints:
                if any(d in failed for d in deps):
                    # A constraint that reads a failed construction is
                    # meaningless against placeholder coordinates; it
                    # must not move the surviving points.
                    continue
                try:
                    r = fn(pts)
                except Exception:
                    # A constraint that cannot be evaluated here
                    # contributes nothing — it must not mask the
                    # residuals of the rest.
                    continue
                if isinstance(r, (int, float)) and math.isfinite(r):
                    total += r
            return total, failed

        import math as _math
        for _step in range(5000):
            eps = 1e-5
            base_cost, _ = eval_constraints(self.points)
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

            grads = {p: np.zeros(2) for p in self.points if self._is_free(p)}
            for p in self.points:
                if not self._is_free(p):
                    continue
                orig = self.points[p].copy()

                self.points[p][0] += eps
                cx, _ = eval_constraints(self.points)
                self.points[p][0] = orig[0]

                self.points[p][1] += eps
                cy, _ = eval_constraints(self.points)
                self.points[p][1] = orig[1]

                grads[p][0] = (cx - base_cost) / eps
                grads[p][1] = (cy - base_cost) / eps

            for p in self.points:
                if self._is_free(p):
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

        final_cost, final_failures = eval_constraints(self.points)
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

        # Constructions that failed at the end are reported and their
        # points are removed so placeholder coordinates are never drawn
        # as if they were real; everything else still renders.
        self.solve_errors = []
        if final_failures:
            for pname in sorted(final_failures):
                msg = f"[GeometryError] *point({pname} = ...): {final_failures[pname]}"
                print(msg, file=sys.stderr)
                self.solve_errors.append(msg)
            for pname in final_failures:
                self.points.pop(pname, None)

        # Check per-constraint residuals to distinguish conflict from non-convergence
        if final_cost > 1e-2 and not final_failures:
            residuals = [
                (label, fn(self.points))
                for label, fn, deps in self.constraints
                if not any(d in final_failures for d in deps)
            ]
            conflicting = [(lbl, r) for lbl, r in residuals if r > 1e-2]

            if len(conflicting) > 1:
                labels = ', '.join(lbl for lbl, _ in conflicting)
                raise GeometryError(
                    f"constraint conflict or non-convergence — these "
                    f"constraints could not all be satisfied: {labels}"
                )
            else:
                worst = max([r for _, r in residuals] or [final_cost])
                # Gross single-constraint miss (orders of magnitude off) is
                # a hard error, not a silent warning with an authoritative
                # diagram.
                if worst > 1e9:
                    lbl = conflicting[0][0] if conflicting else (
                        max(residuals, key=lambda t: t[1])[0] if residuals else "unknown"
                    )
                    raise GeometryError(
                        f"solver failed near constraint '{lbl}' (residual={worst:.2e}) — "
                        f"diagram would be incorrect"
                    )
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
