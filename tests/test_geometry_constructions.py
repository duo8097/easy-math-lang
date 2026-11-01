"""Construction points: *point(NAME = constructor(...)).

Covers the parser (geometry.constructions.parse_construction), the
solver's derived-point machinery, the whole pipeline through
parse_draw_block (generated Typst carries exact coordinates), the
documented intersection-ordering rules, every documented error case,
backward compatibility of the 3-argument *midpoint constraint, and the
LSP not flagging constructed points as undefined.
"""

import math
import os
import re
import sys

import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "src")
)

import numpy as np

from geometry import parse_draw_block
from geometry.constructions import CONSTRUCTION_NAMES, parse_construction
from geometry.errors import GeometryError


def point_coords(output, name):
    """(x, y) of the drawn circle named `name`, from the generated Typst."""
    m = re.search(
        r'circle\(\((-?[\d.]+), (-?[\d.]+)\), radius: [\d.]+, fill: black, '
        rf'name: "{name}"',
        output,
    )
    assert m is not None, f'point {name} not drawn:\n{output}'
    return float(m.group(1)), float(m.group(2))


def assert_close(got, want, tol=1e-6):
    assert abs(got[0] - want[0]) < tol and abs(got[1] - want[1]) < tol, \
        f'got {got}, want {want}'


def compute(text, points):
    """parse_construction(text).compute(points) as plain floats."""
    con = parse_construction(text)
    out = con.compute({k: np.asarray(v, dtype=float)
                       for k, v in points.items()})
    return float(out[0]), float(out[1])


# ----------------------------------------------------------------------
# The 8 constructors — exact coordinates
# ----------------------------------------------------------------------

def test_midpoint_exact():
    assert_close(compute('midpoint(A ; B)',
                         {'A': (0, 0), 'B': (4, 6)}), (2, 3))


def test_foot_exact():
    # P=(4,3) on line y=x through (0,0)-(6,6): foot is (3.5, 3.5).
    assert_close(compute('foot(P ; line(A ; B))',
                         {'P': (4, 3), 'A': (0, 0), 'B': (6, 6)}),
                 (3.5, 3.5))


def test_reflect_line_exact():
    # P=(4,3) reflected across the x-axis.
    assert_close(compute('reflect(P ; line(A ; B))',
                         {'P': (4, 3), 'A': (0, 0), 'B': (1, 0)}),
                 (4, -3))


def test_reflect_point_exact():
    assert_close(compute('reflect(P ; O)',
                         {'P': (4, 3), 'O': (1, 1)}), (-2, -1))


def test_intersect_line_line_exact():
    # y=x and y=-x+8 meet at (4,4).
    assert_close(compute('intersect(line(A ; B) ; line(C ; D))',
                         {'A': (0, 0), 'B': (6, 6),
                          'C': (0, 8), 'D': (8, 0)}), (4, 4))


def test_intersect_line_circle_ordering():
    pts = {'A': (0, 0), 'B': (10, 0), 'O': (5, 0)}
    # A->B direction along +x: k=1 is (3,0)? radius 3 around (5,0) on
    # the x-axis: intersections at x=2 and x=8 — first along A->B is
    # x=2.
    assert_close(compute('intersect(line(A ; B) ; circle(O ; 3) ; 1)', pts),
                 (2, 0))
    assert_close(compute('intersect(line(A ; B) ; circle(O ; 3) ; 2)', pts),
                 (8, 0))
    # Reversing the line flips which solution is "first".
    flipped = {'A': (10, 0), 'B': (0, 0), 'O': (5, 0)}
    assert_close(compute('intersect(line(A ; B) ; circle(O ; 3) ; 1)',
                         flipped), (8, 0))
    assert_close(compute('intersect(line(A ; B) ; circle(O ; 3) ; 2)',
                         flipped), (2, 0))


def test_intersect_circle_circle_ordering():
    # Radius-2 circles at (-1,0) and (1,0): d=2 < 4, intersections at
    # (0, sqrt(3)) and (0, -sqrt(3)).
    # O1->O2 points +x; left (counterclockwise) side is +y.
    line = 'intersect(circle(O1 ; 2) ; circle(O2 ; 2)'
    pts = {'O1': (-1, 0), 'O2': (1, 0)}
    assert_close(compute(f'{line} ; 1)', pts), (0, math.sqrt(3)))
    assert_close(compute(f'{line} ; 2)', pts), (0, -math.sqrt(3)))


def test_centroid_exact():
    assert_close(compute('centroid(A ; B ; C)',
                         {'A': (0, 0), 'B': (3, 0), 'C': (0, 3)}), (1, 1))


def test_circumcenter_right_triangle_is_hypotenuse_midpoint():
    # Right angle at A=(0,0): circumcenter is the midpoint of BC.
    assert_close(compute('circumcenter(A ; B ; C)',
                         {'A': (0, 0), 'B': (4, 0), 'C': (0, 6)}), (2, 3))


def test_incenter_exact():
    # Right triangle 3-4-5: incenter at (1,1).
    assert_close(compute('incenter(A ; B ; C)',
                         {'A': (0, 0), 'B': (3, 0), 'C': (0, 4)}), (1, 1))


def test_orthocenter_right_triangle_is_the_right_angle_vertex():
    assert_close(compute('orthocenter(A ; B ; C)',
                         {'A': (0, 0), 'B': (4, 0), 'C': (0, 6)}), (0, 0))


# ----------------------------------------------------------------------
# Pipeline: *point(... = ctor(...)) end to end
# ----------------------------------------------------------------------

def test_pipeline_draws_constructed_point_at_exact_coordinates():
    out = parse_draw_block(
        '*point(A = 0, 0)\n'
        '*point(B = 4, 6)\n'
        '*point(M = midpoint(A ; B))\n'
        '*line(A ; M)'
    )
    assert '[GeometryError]' not in out
    assert_close(point_coords(out, 'M'), (2, 3))


def test_pipeline_auto_creates_referenced_points():
    # A/B never given coordinates: still no error, M is drawn.
    out = parse_draw_block('*point(M = midpoint(A ; B))\n*line(A ; M)')
    assert '[GeometryError]' not in out
    x, y = point_coords(out, 'M')
    assert math.isfinite(x) and math.isfinite(y)


def test_comma_separator_also_splits_constructor_args():
    out = parse_draw_block(
        '*point(A = 0, 0)\n'
        '*point(B = 4, 6)\n'
        '*point(M = midpoint(A, B))\n'
        '*line(A ; M)'
    )
    assert '[GeometryError]' not in out
    assert_close(point_coords(out, 'M'), (2, 3))


def test_constructed_point_usable_in_every_command():
    # line/triangle/angle/right-angle/length/label all resolve a
    # constructed point like any other.
    out = parse_draw_block(
        '*point(A = 0, 0)\n'
        '*point(B = 4, 0)\n'
        '*point(C = 0, 3)\n'
        '*point(M = midpoint(B ; C))\n'
        '*triangle(A ; B ; C)\n'
        '*line(A ; M)\n'
        '*right-angle(B ; A ; C)\n'
        '*length(A ; B)\n'
        '*label(M ; M)\n'
        '*angle(A ; B ; C)'
    )
    assert '[GeometryError]' not in out
    assert '[GeometryWarning]' not in out
    assert_close(point_coords(out, 'M'), (2, 1.5), tol=2e-3)


def test_nesting_constructors_inside_constructors():
    # Midpoint of the segment from A to the midpoint of B,C.
    out = parse_draw_block(
        '*point(A = 0, 0)\n'
        '*point(B = 4, 0)\n'
        '*point(C = 0, 4)\n'
        '*point(M = midpoint(A ; midpoint(B ; C)))\n'
        '*line(A ; M)'
    )
    assert '[GeometryError]' not in out
    assert_close(point_coords(out, 'M'), (1, 1))


def test_dependency_order_forward_reference():
    # N is defined *before* the M it depends on: still fine (the
    # solver sorts constructions topologically).
    out = parse_draw_block(
        '*point(A = 0, 0)\n'
        '*point(B = 6, 0)\n'
        '*point(N = midpoint(M ; B))\n'
        '*point(M = midpoint(A ; B))\n'
        '*line(A ; N)'
    )
    assert '[GeometryError]' not in out
    assert_close(point_coords(out, 'N'), (4.5, 0), tol=2e-3)


def test_constraints_on_constructed_points_recompute():
    # distance(A;C;3) pins |AC|=3 while distance(B;midpoint(A;C);5)
    # pins the midpoint of AC at distance 5 from B — the solver moves
    # the FREE point C; the constructed midpoint tracks it every step.
    # (Feasible: |BM| ranges over [|AB|-1.5, |AB|+1.5] = [4.5, 7.5].)
    out = parse_draw_block(
        '*point(A = 0, 0)\n'
        '*point(B = 6, 0)\n'
        '*point(C)\n'
        '*point(M = midpoint(A ; C))\n'
        '*distance(A ; C ; 3)\n'
        '*distance(B ; M ; 5)'
    )
    assert '[GeometryError]' not in out
    a = np.asarray(point_coords(out, 'A'))
    c = np.asarray(point_coords(out, 'C'))
    m = np.asarray(point_coords(out, 'M'))
    b = np.asarray(point_coords(out, 'B'))
    assert abs(np.linalg.norm(c - a) - 3.0) < 2e-2
    assert abs(np.linalg.norm(m - b) - 5.0) < 2e-2
    # And M really is the midpoint of the *solved* A,C (coordinates
    # render at 3 decimals, hence the 1e-3 tolerance).
    assert_close(tuple(m), tuple((a + c) / 2.0), tol=1e-3)


def test_free_points_stay_free_and_derived_never_move_independently():
    # *perp is a solver constraint between free points; M follows.
    out = parse_draw_block(
        '*point(A = 0, 0)\n'
        '*point(B = 4, 0)\n'
        '*point(C = 0, 4)\n'
        '*point(M = midpoint(A ; B))\n'
        '*perp(A ; B ; A ; C)\n'
        '*distance(A ; M ; 2)'
    )
    assert '[GeometryError]' not in out
    a = np.asarray(point_coords(out, 'A'))
    m = np.asarray(point_coords(out, 'M'))
    assert abs(np.linalg.norm(m - a) - 2.0) < 2e-3


# ----------------------------------------------------------------------
# Triangle centers end to end
# ----------------------------------------------------------------------

def test_orthocenter_via_two_altitude_feet():
    # Right angle at A: both feet coincide with A, so the orthocenter
    # is A itself.
    out = parse_draw_block(
        '*point(A = 0, 0)\n'
        '*point(B = 4, 0)\n'
        '*point(C = 0, 3)\n'
        '*point(Ha = foot(A ; line(B ; C)))\n'
        '*point(Hb = foot(B ; line(A ; C)))\n'
        '*point(H = intersect(line(A ; Ha) ; line(B ; Hb)))\n'
        '*triangle(A ; B ; C)\n'
        '*line(A ; Ha)\n'
        '*line(B ; Hb)\n'
        '*label(H ; H)'
    )
    assert '[GeometryError]' not in out
    # A is the right angle: Ha (foot of A on BC) sits on the hypotenuse
    # at (1.44, 1.92); Hb (foot of B on AC) is A itself; the two
    # altitudes meet at the right-angle vertex A.
    assert_close(point_coords(out, 'Ha'), (1.44, 1.92), tol=2e-3)
    assert_close(point_coords(out, 'Hb'), (0, 0), tol=2e-3)
    assert_close(point_coords(out, 'H'), (0, 0), tol=2e-3)


def test_orthocenter_via_constructor_on_an_acute_triangle():
    # A=(0,0) B=(6,0) C=(2,4): orthocenter by the A+B+C-2O identity.
    out = parse_draw_block(
        '*point(A = 0, 0)\n'
        '*point(B = 6, 0)\n'
        '*point(C = 2, 4)\n'
        '*point(H = orthocenter(A ; B ; C))\n'
        '*triangle(A ; B ; C)\n'
        '*label(H ; H)'
    )
    assert '[GeometryError]' not in out
    # H = A+B+C-2O with O=(3,1) → (2,2).
    assert_close(point_coords(out, 'H'), (2, 2), tol=2e-3)


def test_circumcenter_incenter_centroid_pipeline():
    out = parse_draw_block(
        '*point(A = 0, 0)\n'
        '*point(B = 6, 0)\n'
        '*point(C = 0, 8)\n'
        '*point(G = centroid(A ; B ; C))\n'
        '*point(O = circumcenter(A ; B ; C))\n'
        '*point(I = incenter(A ; B ; C))\n'
        '*triangle(A ; B ; C)\n'
        '*label(G ; G)\n'
        '*label(O ; O)\n'
        '*label(I ; I)'
    )
    assert '[GeometryError]' not in out
    assert_close(point_coords(out, 'G'), (2, 8 / 3), tol=2e-3)
    # Right triangle: circumcenter is the hypotenuse midpoint.
    assert_close(point_coords(out, 'O'), (3, 4), tol=2e-3)
    # 6-8-10: incenter at (2,2).
    assert_close(point_coords(out, 'I'), (2, 2), tol=2e-3)


# ----------------------------------------------------------------------
# Errors
# ----------------------------------------------------------------------

def test_unknown_construction_suggests_closest_name():
    with pytest.raises(GeometryError) as exc:
        parse_construction('midpint(A ; B)')
    assert "unknown construction 'midpint'" in str(exc.value)
    assert "did you mean 'midpoint'?" in str(exc.value)


def test_unknown_construction_lists_all_valid_names():
    with pytest.raises(GeometryError) as exc:
        parse_construction('tangent(A ; B)')
    for name in CONSTRUCTION_NAMES:
        assert name in str(exc.value)


def test_wrong_arity_reports_usage():
    with pytest.raises(GeometryError) as exc:
        parse_construction('midpoint(A)')
    assert 'midpoint requires 2 arguments' in str(exc.value)
    assert 'midpoint(A ; B)' in str(exc.value)
    with pytest.raises(GeometryError):
        parse_construction('centroid(A ; B)')
    with pytest.raises(GeometryError):
        parse_construction('centroid(A ; B ; C ; D)')


def test_bad_k_values():
    with pytest.raises(GeometryError) as exc:
        parse_construction(
            'intersect(line(A ; B) ; circle(O ; 3) ; 3)')
    assert 'k must be 1 or 2' in str(exc.value)
    with pytest.raises(GeometryError) as exc:
        parse_construction(
            'intersect(line(A ; B) ; circle(O ; 3))')
    assert 'two solutions' in str(exc.value)
    with pytest.raises(GeometryError) as exc:
        parse_construction(
            'intersect(circle(O ; 3) ; circle(P ; A))')
    assert 'two solutions' in str(exc.value)


def test_k_rejected_for_line_line_intersection():
    with pytest.raises(GeometryError) as exc:
        parse_construction(
            'intersect(line(A ; B) ; line(C ; D) ; 1)')
    assert 'unique intersection' in str(exc.value)


def test_foot_requires_a_line():
    with pytest.raises(GeometryError) as exc:
        parse_construction('foot(A ; B)')
    assert 'second argument must be line' in str(exc.value)


def test_intersect_requires_line_or_circle():
    with pytest.raises(GeometryError) as exc:
        parse_construction('intersect(A ; B)')
    assert 'expected line(...) or circle(...)' in str(exc.value)


def test_numbers_where_points_required():
    with pytest.raises(GeometryError) as exc:
        parse_construction('midpoint(A ; 3)')
    assert 'expected a point name, got number 3' in str(exc.value)


def test_circle_radius_must_be_positive():
    with pytest.raises(GeometryError) as exc:
        parse_construction(
            'intersect(line(A ; B) ; circle(O ; 0) ; 1)')
    assert 'radius must be positive' in str(exc.value)


def test_parallel_lines_error_at_evaluation():
    con = parse_construction('intersect(line(A ; B) ; line(C ; D))')
    with pytest.raises(GeometryError) as exc:
        con.compute({'A': np.array([0., 0.]), 'B': np.array([4., 0.]),
                     'C': np.array([0., 1.]), 'D': np.array([4., 1.])})
    assert 'parallel or coincident' in str(exc.value)


def test_line_misses_circle_error_at_evaluation():
    con = parse_construction(
        'intersect(line(A ; B) ; circle(O ; 1) ; 1)')
    with pytest.raises(GeometryError) as exc:
        con.compute({'A': np.array([0., 5.]), 'B': np.array([10., 5.]),
                     'O': np.array([0., 0.])})
    assert 'does not intersect' in str(exc.value)


def test_disjoint_circles_error_at_evaluation():
    con = parse_construction(
        'intersect(circle(O1 ; 1) ; circle(O2 ; A) ; 1)')
    with pytest.raises(GeometryError) as exc:
        con.compute({'O1': np.array([0., 0.]), 'O2': np.array([10., 0.]),
                     'A': np.array([10., 2.])})   # r2 = 2, d = 10 > 3
    assert 'do not intersect' in str(exc.value)


def test_coincident_circles_error_at_evaluation():
    con = parse_construction(
        'intersect(circle(O1 ; 3) ; circle(O1 ; 3) ; 1)')
    with pytest.raises(GeometryError) as exc:
        con.compute({'O1': np.array([0., 0.])})
    assert 'coincident circles' in str(exc.value)


def test_degenerate_line_error_at_evaluation():
    con = parse_construction('foot(P ; line(A ; B))')
    with pytest.raises(GeometryError) as exc:
        con.compute({'P': np.array([1., 1.]), 'A': np.array([2., 2.]),
                     'B': np.array([2., 2.])})
    assert 'degenerate' in str(exc.value)


def test_collinear_triangle_centers_error_at_evaluation():
    for name in ('circumcenter', 'orthocenter'):
        con = parse_construction(f'{name}(A ; B ; C)')
        with pytest.raises(GeometryError) as exc:
            con.compute({'A': np.array([0., 0.]), 'B': np.array([1., 0.]),
                         'C': np.array([2., 0.])})
        assert 'collinear' in str(exc.value), name


def test_non_construction_right_hand_side_rejected():
    with pytest.raises(GeometryError) as exc:
        parse_construction('A + B')
    assert 'expected a point name' in str(exc.value)


# ----------------------------------------------------------------------
# Solver-level errors (through parse_draw_block)
# ----------------------------------------------------------------------

def test_cycle_reports_path():
    out = parse_draw_block(
        '*point(A = 0, 0)\n'
        '*point(B = 4, 0)\n'
        '*point(M = midpoint(N ; A))\n'
        '*point(N = midpoint(M ; B))'
    )
    assert '[GeometryError]' in out
    assert 'construction cycle' in out
    assert 'M -> N -> M' in out or 'N -> M -> N' in out


def test_self_reference_is_a_cycle():
    out = parse_draw_block('*point(M = midpoint(M ; A))')
    assert '[GeometryError]' in out
    assert 'construction cycle' in out
    assert 'M -> M' in out


def test_constructed_point_cannot_also_have_coordinates():
    out = parse_draw_block(
        '*point(A = 0, 0)\n'
        '*point(B = 4, 0)\n'
        '*point(M = midpoint(A ; B))\n'
        '*point(M = 1, 2)'
    )
    assert '[GeometryError]' in out
    assert 'is constructed by' in out


def test_coordinates_first_then_constructed_is_also_an_error():
    out = parse_draw_block(
        '*point(A = 0, 0)\n'
        '*point(B = 4, 0)\n'
        '*point(M = 1, 2)\n'
        '*point(M = midpoint(A ; B))'
    )
    assert '[GeometryError]' in out
    assert 'already has coordinates' in out


def test_parallel_lines_in_pipeline_reports_error():
    out = parse_draw_block(
        '*point(A = 0, 0)\n'
        '*point(B = 4, 0)\n'
        '*point(C = 0, 1)\n'
        '*point(D = 4, 1)\n'
        '*point(P = intersect(line(A ; B) ; line(C ; D)))'
    )
    assert '[GeometryError]' in out
    assert 'parallel or coincident' in out


# ----------------------------------------------------------------------
# Backward compatibility
# ----------------------------------------------------------------------

def test_three_argument_midpoint_constraint_unchanged():
    # The solver *constraint *midpoint(A ; B ; M) still works and M is
    # a FREE point there (not constructed).
    out = parse_draw_block(
        '*point(A = 0, 0)\n'
        '*point(B = 4, 6)\n'
        '*point(M)\n'
        '*midpoint(A ; B ; M)'
    )
    assert '[GeometryError]' not in out
    assert_close(point_coords(out, 'M'), (2, 3), tol=1e-2)


def test_plain_coordinate_points_unaffected():
    out = parse_draw_block(
        '*point(A = 0, 0)\n'
        '*point(B = 1,000, 2)\n'
        '*line(A ; B)'
    )
    assert '[GeometryError]' not in out
    assert_close(point_coords(out, 'B'), (1000, 2))


def test_point_without_equals_still_a_free_variable():
    out = parse_draw_block(
        '*point(A = 0, 0)\n'
        '*point(B = 4, 0)\n'
        '*point(M)\n'
        '*distance(A ; M ; 2)\n'
        '*distance(B ; M ; 2)'
    )
    assert '[GeometryError]' not in out
    m = np.asarray(point_coords(out, 'M'))
    assert abs(np.linalg.norm(m - np.array([0., 0.])) - 2.0) < 5e-3
    assert abs(np.linalg.norm(m - np.array([4., 0.])) - 2.0) < 5e-3


# ----------------------------------------------------------------------
# LSP integration: no false "undefined point" diagnostics
# ----------------------------------------------------------------------

def test_lsp_does_not_flag_constructed_points():
    from lsp.analysis import analyze_text

    src = (
        '*draw(\n'
        '    *point(A = 0, 0)\n'
        '    *point(B = 4, 6)\n'
        '    *point(M = midpoint(A ; B))\n'
        '    *point(F = foot(B ; line(A ; M)))\n'
        '    *line(A ; M)\n'
        '    *label(F ; F)\n'
        ')'
    )
    analysis = analyze_text(src)
    undefined = [d for d in analysis.diagnostics
                 if 'undefined point' in d.message]
    assert undefined == [], undefined


def test_lsp_completion_offers_constructions_in_point_rhs():
    from lsp.analysis import complete

    src = '*draw(\n    *point(M = )\n)'
    line = 1
    character = src.splitlines()[line].index(')')
    items = complete(src, line, character)
    labels = {item['label'] for item in items}
    assert 'midpoint' in labels
    assert 'orthocenter' in labels


def test_lsp_hover_explains_a_construction():
    from lsp.analysis import hover

    # 'foot' is construction-only (no *foot command), so hover must
    # reach the construction docs.  ('midpoint' is both a constraint
    # command and a construction; the command doc wins — accepted.)
    src = '*draw(\n    *point(F = foot(A ; line(B ; C)))\n)'
    info = hover(src, 1, src.splitlines()[1].index('foot') + 2)
    assert info is not None
    assert 'foot' in info['value']
    assert 'Geometry construction' in info['value']
