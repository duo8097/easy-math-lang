"""Analytic point constructions for ``*point(NAME = ...)``.

A construction computes a point directly from its inputs — no solver
guesswork::

    *point(M = midpoint(A ; B))
    *point(H = foot(A ; line(B ; C)))
    *point(A2 = reflect(A ; line(B ; C)))
    *point(P = intersect(line(A ; B) ; line(C ; D)))
    *point(P = intersect(line(A ; B) ; circle(O ; 3) ; 1))
    *point(P = intersect(circle(O ; 3) ; circle(Q ; A) ; 2))

Constructor calls may nest inside other constructors (the restriction
to ``*point`` right-hand sides is about *commands*, see
docs/geometry.md), e.g. ``foot(A ; line(B ; intersect(line(C ; D) ;
line(E ; F))))``.

Static errors (unknown name, wrong arity, bad argument types, bad k)
are raised at parse time by :func:`parse_construction`; errors that
depend on positions (degenerate lines, no intersection, …) surface
when the construction is evaluated during solving.

Intersection ordering (deterministic, documented in docs/geometry.md):

- ``intersect(line ; line)`` is unique; passing k is an error.
- ``intersect(line ; circle ; k)``: k=1 is the intersection reached
  first walking from A toward B (smaller line parameter), k=2 the
  second. k is required.
- ``intersect(circle ; circle ; k)``: k=1 lies on the left
  (counterclockwise) side of the O1->O2 direction, k=2 on the right.
  k is required.
"""

import difflib
import math
import re

from .commands import parse_numeric_arg
from .errors import GeometryError

#: Every valid constructor name (sorted suggestion source).
CONSTRUCTION_NAMES = (
    'centroid', 'circumcenter', 'foot', 'incenter', 'intersect',
    'midpoint', 'orthocenter', 'reflect',
)

#: (min, max) argument counts per constructor.
_ARITY = {
    'midpoint': (2, 2),
    'foot': (2, 2),
    'reflect': (2, 2),
    'intersect': (2, 3),
    'centroid': (3, 3),
    'circumcenter': (3, 3),
    'incenter': (3, 3),
    'orthocenter': (3, 3),
}

_USAGE = {
    'midpoint': 'midpoint(A ; B)',
    'foot': 'foot(P ; line(A ; B))',
    'reflect': 'reflect(P ; line(A ; B)) or reflect(P ; O)',
    'intersect': 'intersect(line(A ; B) ; line(C ; D)) or '
                 'intersect(line/circle ; line/circle ; k)',
    'centroid': 'centroid(A ; B ; C)',
    'circumcenter': 'circumcenter(A ; B ; C)',
    'incenter': 'incenter(A ; B ; C)',
    'orthocenter': 'orthocenter(A ; B ; C)',
}

#: Degeneracy / no-intersection tolerance (scale-relative where it
#: matters). Matches the solver's 1e-9 degenerate-segment guard.
_EPS = 1e-9

_CALL_RE = re.compile(r'([A-Za-z][A-Za-z0-9_]*)\s*\(')
_IDENT_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]*$')


class Construction:
    """A parsed construction: dependencies plus an analytic evaluator.

    ``compute(pts)`` takes the solver's ``name -> np.array([x, y])``
    mapping and returns the constructed point as ``np.array([x, y])``.
    """

    __slots__ = ('name', 'deps', 'compute', 'text')

    def __init__(self, name, deps, compute, text):
        self.name = name
        self.deps = frozenset(deps)
        self.compute = compute
        self.text = text


# ----------------------------------------------------------------------
# AST nodes
# ----------------------------------------------------------------------

class _Node:
    label = '...'

    def deps(self):
        return set()

    def eval(self, pts):
        raise NotImplementedError


class _PointRef(_Node):
    """A bare point name (leaf)."""

    def __init__(self, name):
        self.name = name
        self.label = name

    def deps(self):
        return {self.name}

    def eval(self, pts):
        if self.name not in pts:
            raise GeometryError(f"undefined point '{self.name}'")
        import numpy as np
        return np.asarray(pts[self.name], dtype=float)


class _Num(_Node):
    """A numeric literal (circle radius or intersect k)."""

    def __init__(self, value, text):
        self.value = float(value)
        self.text = text
        self.label = text

    def eval(self, pts):
        return self.value


class _Line(_Node):
    """``line(P ; Q)`` descriptor — only valid as a constructor argument."""

    def __init__(self, p, q):
        self.p = p
        self.q = q
        self.label = f'line({p.label} ; {q.label})'

    def deps(self):
        return self.p.deps() | self.q.deps()

    def eval(self, pts):
        import numpy as np
        from .vectors import _norm

        A = np.asarray(self.p.eval(pts), dtype=float)
        B = np.asarray(self.q.eval(pts), dtype=float)
        try:
            n = float(_norm(B - A))
        except (TypeError, ValueError):
            n = float('nan')
        if not math.isfinite(n) or n < _EPS:
            raise GeometryError(
                f"line({self.p.label} ; {self.q.label}) is degenerate "
                f"(same point twice)"
            )
        return A, B


class _Circle(_Node):
    """``circle(O ; r-or-point)`` descriptor (same radius rules as *circle)."""

    def __init__(self, center, radius):
        self.center = center
        self.radius = radius  # _Num or point-valued node
        self.label = f'circle({center.label} ; {radius.label})'

    def deps(self):
        return self.center.deps() | self.radius.deps()

    def eval(self, pts):
        import numpy as np
        from .vectors import _norm

        O = np.asarray(self.center.eval(pts), dtype=float)
        if isinstance(self.radius, _Num):
            r = self.radius.value
        else:
            P = np.asarray(self.radius.eval(pts), dtype=float)
            r = float(_norm(P - O))
            if not math.isfinite(r):
                raise GeometryError(f'{self.label}: non-finite radius')
            if r < _EPS:
                raise GeometryError(
                    f'{self.label} has radius zero — the points coincide'
                )
        if r > 1e6:
            raise GeometryError(
                f'{self.label}: radius exceeds the canvas limit (1e6)'
            )
        return O, r


class _Call(_Node):
    """A constructor call (point-valued)."""

    def __init__(self, name, args):
        self.name = name
        self.args = args
        self.label = f'{name}({", ".join(a.label for a in args)})'

    def deps(self):
        out = set()
        for a in self.args:
            out |= a.deps()
        return out

    def eval(self, pts):
        fn = _EVALUATORS[self.name]
        return fn(self.args, pts)


# ----------------------------------------------------------------------
# Math (lazy NumPy, like geometry.commands)
# ----------------------------------------------------------------------

def _cross2d(v1, v2):
    return float(v1[0] * v2[1] - v1[1] * v2[0])


def _eval_midpoint(args, pts):
    import numpy as np

    A = np.asarray(args[0].eval(pts), dtype=float)
    B = np.asarray(args[1].eval(pts), dtype=float)
    return (A + B) / 2.0


def _eval_foot(args, pts):
    import numpy as np

    P = np.asarray(args[0].eval(pts), dtype=float)
    A, B = args[1].eval(pts)
    d = B - A
    t = float((P - A) @ d) / float(d @ d)
    return A + t * d


def _eval_reflect(args, pts):
    import numpy as np

    P = np.asarray(args[0].eval(pts), dtype=float)
    target = args[1]
    if isinstance(target, _Line):
        A, B = target.eval(pts)
        d = B - A
        t = float((P - A) @ d) / float(d @ d)
        return 2.0 * (A + t * d) - P
    O = np.asarray(target.eval(pts), dtype=float)
    return 2.0 * O - P


def _eval_intersect(args, pts):
    import numpy as np

    a, b = args[0], args[1]
    k = int(args[2].value) if len(args) == 3 else None

    if isinstance(a, _Line) and isinstance(b, _Line):
        A, B = a.eval(pts)
        C, D = b.eval(pts)
        d1, d2 = B - A, D - C
        den = _cross2d(d1, d2)
        n1, n2 = float(np.linalg.norm(d1)), float(np.linalg.norm(d2))
        if abs(den) <= _EPS * n1 * n2:
            raise GeometryError(
                f'intersect: {a.label} and {b.label} are parallel or '
                f'coincident — no unique intersection'
            )
        t = _cross2d(C - A, d2) / den
        return A + t * d1

    if isinstance(a, _Line) and isinstance(b, _Circle):
        line, circle = a, b
    elif isinstance(a, _Circle) and isinstance(b, _Line):
        line, circle = b, a
    else:  # both circles (parse-time validated)
        O1, r1 = a.eval(pts)
        O2, r2 = b.eval(pts)
        dv = O2 - O1
        d = float(np.linalg.norm(dv))
        if d < _EPS:
            if abs(r1 - r2) < _EPS:
                raise GeometryError(
                    f'intersect: {a.label} and {b.label} are coincident '
                    f'circles — infinitely many intersections'
                )
            raise GeometryError(
                f'intersect: {a.label} and {b.label} have the same center '
                f'— no intersection'
            )
        if d > r1 + r2 + _EPS or d < abs(r1 - r2) - _EPS:
            raise GeometryError(
                f'intersect: {a.label} and {b.label} do not intersect'
            )
        x = (r1 * r1 - r2 * r2 + d * d) / (2.0 * d)
        h = math.sqrt(max(r1 * r1 - x * x, 0.0))
        u = dv / d
        base = O1 + x * u
        left = base + h * np.array([-u[1], u[0]])  # left of O1->O2
        right = base - h * np.array([-u[1], u[0]])
        return left if k == 1 else right

    # line-circle, ordered along the line's A->B direction.
    A, B = line.eval(pts)
    O, r = circle.eval(pts)
    d = B - A
    f = A - O
    qa = float(d @ d)
    qb = 2.0 * float(f @ d)
    qc = float(f @ f) - r * r
    disc = qb * qb - 4.0 * qa * qc
    tol = _EPS * (qb * qb + abs(4.0 * qa * qc) + 1.0)
    if disc < -tol:
        raise GeometryError(
            f'intersect: {line.label} does not intersect {circle.label}'
        )
    sq = math.sqrt(max(disc, 0.0))
    t1 = (-qb - sq) / (2.0 * qa)
    t2 = (-qb + sq) / (2.0 * qa)
    return A + (t1 if k == 1 else t2) * d


def _eval_centroid(args, pts):
    import numpy as np

    A = np.asarray(args[0].eval(pts), dtype=float)
    B = np.asarray(args[1].eval(pts), dtype=float)
    C = np.asarray(args[2].eval(pts), dtype=float)
    return (A + B + C) / 3.0


def _eval_circumcenter(args, pts):
    import numpy as np

    A = np.asarray(args[0].eval(pts), dtype=float)
    B = np.asarray(args[1].eval(pts), dtype=float)
    C = np.asarray(args[2].eval(pts), dtype=float)
    M = np.array([
        [2.0 * (B[0] - A[0]), 2.0 * (B[1] - A[1])],
        [2.0 * (C[0] - A[0]), 2.0 * (C[1] - A[1])],
    ])
    rhs = np.array([
        float(B @ B - A @ A),
        float(C @ C - A @ A),
    ])
    try:
        return np.linalg.solve(M, rhs)
    except np.linalg.LinAlgError:
        raise GeometryError(
            f'{args[0].label}, {args[1].label}, {args[2].label} are '
            f'collinear — no circumcenter'
        )


def _eval_incenter(args, pts):
    import numpy as np
    from .vectors import _norm

    A = np.asarray(args[0].eval(pts), dtype=float)
    B = np.asarray(args[1].eval(pts), dtype=float)
    C = np.asarray(args[2].eval(pts), dtype=float)
    a = float(_norm(B - C))
    b = float(_norm(A - C))
    c = float(_norm(A - B))
    total = a + b + c
    if not math.isfinite(total) or total < _EPS:
        raise GeometryError(
            f'{args[0].label}, {args[1].label}, {args[2].label} are '
            f'degenerate — no incenter'
        )
    return (a * A + b * B + c * C) / total


def _eval_orthocenter(args, pts):
    import numpy as np

    A = np.asarray(args[0].eval(pts), dtype=float)
    B = np.asarray(args[1].eval(pts), dtype=float)
    C = np.asarray(args[2].eval(pts), dtype=float)
    try:
        O = _eval_circumcenter(args, pts)
    except GeometryError:
        raise GeometryError(
            f'{args[0].label}, {args[1].label}, {args[2].label} are '
            f'collinear — no orthocenter'
        )
    return A + B + C - 2.0 * O


_EVALUATORS = {
    'midpoint': _eval_midpoint,
    'foot': _eval_foot,
    'reflect': _eval_reflect,
    'intersect': _eval_intersect,
    'centroid': _eval_centroid,
    'circumcenter': _eval_circumcenter,
    'incenter': _eval_incenter,
    'orthocenter': _eval_orthocenter,
}


# ----------------------------------------------------------------------
# Parsing
# ----------------------------------------------------------------------

def _unknown_construction(name):
    close = difflib.get_close_matches(name, CONSTRUCTION_NAMES, n=1, cutoff=0.6)
    msg = f"unknown construction {name!r}"
    if close:
        msg += f" — did you mean {close[0]!r}?"
    return GeometryError(msg + f" (valid: {', '.join(CONSTRUCTION_NAMES)})")


def _split_call(s):
    """``name(...)`` -> (name, inner text); raises on bad shape."""
    m = _CALL_RE.match(s)
    if not m:
        raise GeometryError(
            f"expected a construction like midpoint(A ; B), got: {s!r}"
        )
    name = m.group(1)
    depth = 0
    close = None
    for i in range(m.end() - 1, len(s)):
        if s[i] == '(':
            depth += 1
        elif s[i] == ')':
            depth -= 1
            if depth == 0:
                close = i
                break
    if close is None:
        raise GeometryError(f"unclosed parenthesis in construction: {s!r}")
    trailing = s[close + 1:].strip()
    if trailing:
        raise GeometryError(
            f"unexpected text after {name}(...): {trailing!r}"
        )
    return name, s[m.end():close]


def _split_args(inner):
    """Split constructor args: ';' wins at depth 0, else ',' (like *cmd)."""
    # Lazy import: geometry.parsing imports geometry.commands which
    # imports this module — only safe at call time.
    from .parsing import split_args
    return [a for a in (part.strip() for part in split_args(inner)) if a]


def _require_point(name, arg):
    if isinstance(arg, (_PointRef, _Call)):
        return arg
    if isinstance(arg, _Num):
        raise GeometryError(
            f"{name}: expected a point name, got number {arg.text}"
        )
    raise GeometryError(
        f"{name}: expected a point, got {arg.label}"
    )


def _parse_arg(s):
    s = s.strip()
    if not s:
        raise GeometryError('empty construction argument')
    m = _CALL_RE.match(s)
    if m:
        cname, inner = _split_call(s)
        if cname in ('line', 'circle'):
            args = _split_args(inner)
            if len(args) != 2:
                raise GeometryError(
                    f"{cname}(...) takes 2 arguments "
                    f"({'center ; radius-or-point' if cname == 'circle' else 'P ; Q'}), "
                    f"got {len(args)}"
                )
            if cname == 'line':
                p = _require_point('line', _parse_arg(args[0]))
                q = _require_point('line', _parse_arg(args[1]))
                return _Line(p, q)
            center = _require_point('circle', _parse_arg(args[0]))
            rest = _parse_arg(args[1])
            if isinstance(rest, _Num):
                if not math.isfinite(rest.value) or rest.value <= 0:
                    raise GeometryError(
                        "circle(...) radius must be positive and finite, "
                        f"got {rest.text}"
                    )
                return _Circle(center, rest)
            return _Circle(center, _require_point('circle', rest))
        if cname not in _ARITY:
            raise _unknown_construction(cname)
        args = _split_args(inner)
        lo, hi = _ARITY[cname]
        if not (lo <= len(args) <= hi):
            count = str(lo) if lo == hi else f'{lo} or {hi}'
            raise GeometryError(
                f"{cname} requires {count} arguments: {_USAGE[cname]} "
                f"(got {len(args)})"
            )
        parsed = [_parse_arg(a) for a in args]
        return _build_call(cname, parsed)
    if _IDENT_RE.match(s):
        return _PointRef(s)
    try:
        value = parse_numeric_arg(s)
    except ValueError:
        raise GeometryError(f"expected a point name, got: {s!r}")
    return _Num(value, s)


def _build_call(name, args):
    if name == 'intersect':
        a, b = args[0], args[1]
        for desc in (a, b):
            if not isinstance(desc, (_Line, _Circle)):
                raise GeometryError(
                    f"intersect: expected line(...) or circle(...), "
                    f"got {desc.label}"
                )
        kinds = sorted(
            ('line' if isinstance(d, _Line) else 'circle') for d in (a, b)
        )
        shape = f"intersect({' ; '.join(kinds)})"
        two_line = kinds == ['line', 'line']
        if len(args) == 3:
            k = args[2]
            if not isinstance(k, _Num) or k.value not in (1.0, 2.0):
                text = getattr(k, 'text', k.label)
                raise GeometryError(
                    f"intersect: k must be 1 or 2, got {text}"
                )
            if two_line:
                raise GeometryError(
                    "intersect(line ; line) has a unique intersection — "
                    "remove k"
                )
        elif not two_line:
            raise GeometryError(
                f"{shape} has two solutions — add the solution number "
                f"k = 1 or k = 2"
            )
        return _Call(name, args)

    if name == 'foot':
        _require_point(name, args[0])
        if not isinstance(args[1], _Line):
            raise GeometryError(
                f"foot: second argument must be line(A ; B), "
                f"got {args[1].label}"
            )
        return _Call(name, args)

    if name == 'reflect':
        _require_point(name, args[0])
        target = args[1]
        if not isinstance(target, (_Line, _PointRef, _Call)):
            raise GeometryError(
                "reflect: second argument must be line(A ; B) or a "
                f"point O, got {target.label}"
            )
        return _Call(name, args)

    # Point-position constructors: every argument must be point-valued.
    for a in args:
        _require_point(name, a)
    return _Call(name, args)


def parse_construction(text):
    """Parse a ``*point`` right-hand side into a :class:`Construction`.

    Raises :class:`GeometryError` for static problems (unknown name,
    wrong arity, bad argument types, bad k).
    """
    s = (text or '').strip()
    node = _parse_arg(s)
    if not isinstance(node, _Call):
        raise GeometryError(
            f"expected a construction like midpoint(A ; B), got: {s!r}"
        )
    deps = node.deps()

    def compute(pts):
        import numpy as np

        val = node.eval(pts)
        x, y = float(val[0]), float(val[1])
        if not (math.isfinite(x) and math.isfinite(y)):
            raise GeometryError(
                f"construction {node.label} produced non-finite coordinates"
            )
        if abs(x) > 1e6 or abs(y) > 1e6:
            raise GeometryError(
                f"construction {node.label} result exceeds the canvas "
                f"limit (1e6)"
            )
        return np.array([x, y])

    return Construction(node.name, deps, compute, s)
