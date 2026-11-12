"""Feature + adversarial tests for geometry marks.

Covers *angle, *arc, *label, *length, *angle-value and infinite lines,
plus hostile combinations. All assertions are on the generated Typst
(no PDF compilation) except where noted.
"""

import math
import os
import re
import sys

import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "src")
)

import geometry
from geometry import parse_draw_block


def numbers(output):
    return [float(v) for v in re.findall(r"-?\d+\.\d+", output)]


def code_lines(output):
    """Executable Typst lines (diagnostic `//` comments carry raw text)."""
    return [
        l for l in output.splitlines()
        if l.strip() and not l.strip().startswith("//") and not l.startswith("#import")
    ]


def assert_all_finite(output):
    code = "\n".join(code_lines(output))
    assert "nan" not in code.lower()
    for v in numbers(code):
        assert math.isfinite(v)
    # No fake-infinity coordinates in executable output.
    assert not re.search(r"\b1e[6789]\b", code)
    assert "inf" not in code.lower()


# ------------------------------------------------------------------
# *angle
# ------------------------------------------------------------------

def test_angle_right():
    out = parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 4, 0)\n*point(C = 4, 3)\n*angle(A ; B ; C)"
    )
    assert "arc(" in out
    assert "radius: 0.400" in out
    assert "GeometryError" not in out


def test_angle_acute_obtuse():
    acute = parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 4, 0)\n*point(C = 5, 1)\n*angle(A ; B ; C)"
    )
    assert "arc(" in acute
    obtuse = parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 4, 0)\n*point(C = 0, 1)\n*angle(A ; B ; C)"
    )
    assert "arc(" in obtuse
    # Interior (minor) arc: sweep must be <= 180deg.
    for out in (acute, obtuse):
        m = re.search(r"start: ([\d.]+)deg, stop: ([\d.]+)deg", out)
        assert m is not None
        assert float(m.group(2)) - float(m.group(1)) <= 180.0 + 1e-6


def test_angle_with_label():
    out = parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 4, 0)\n*point(C = 4, 3)\n*angle(A ; B ; C ; 90°)"
    )
    assert "90°" in out
    assert "content(" in out


def test_angle_reversed_order_same_marker():
    fwd = parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 4, 0)\n*point(C = 4, 3)\n*angle(A ; B ; C)"
    )
    rev = parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 4, 0)\n*point(C = 4, 3)\n*angle(C ; B ; A)"
    )
    assert "arc(" in fwd and "arc(" in rev


def test_angle_degenerate_inputs():
    # Coincident vertex and arm.
    out = parse_draw_block(
        "*point(A = 1, 1)\n*point(B = 1, 1)\n*point(C = 2, 2)\n*angle(A ; B ; C)"
    )
    assert "coincident" in out
    assert_all_finite(out)
    # Zero-length arm via identical points.
    out = parse_draw_block("*angle(A ; A ; B)")
    assert "GeometryError" in out
    assert_all_finite(out)
    # Undefined point.
    out = parse_draw_block("*angle(A ; B ; ZZZ)")
    # Draw-only commands auto-create points (coordinates optional), so
    # this draws fine instead of erroring.
    assert "arc(" in out
    assert_all_finite(out)
    # Wrong arity.
    out = parse_draw_block("*angle(A ; B)")
    assert "requires 3 args" in out


# ------------------------------------------------------------------
# *arc
# ------------------------------------------------------------------

def test_arc_quarter():
    out = parse_draw_block(
        "*point(O = 0, 0)\n*point(A = 3, 0)\n*point(B = 0, 3)\n*arc(O ; A ; B)"
    )
    assert "arc((0.000, 0.000), start: 0.00deg, stop: 90.00deg" in out
    assert "radius: 3.000" in out


def test_arc_reversed_is_ccw():
    out = parse_draw_block(
        "*point(O = 0, 0)\n*point(A = 0, 3)\n*point(B = 3, 0)\n*arc(O ; A ; B)"
    )
    m = re.search(r"start: ([\d.]+)deg, stop: ([\d.]+)deg", out)
    assert m is not None
    assert float(m.group(2)) > float(m.group(1))  # counterclockwise


def test_arc_degenerate():
    # A and B on the same ray from O: zero sweep.
    out = parse_draw_block(
        "*point(O = 0, 0)\n*point(A = 2, 0)\n*point(B = 5, 0)\n*arc(O ; A ; B)"
    )
    assert "degenerate" in out
    assert "arc((" not in out
    assert_all_finite(out)
    # Center == start: zero radius.
    out = parse_draw_block(
        "*point(O = 1, 1)\n*point(B = 2, 2)\n*arc(O ; O ; B)"
    )
    assert "coincide" in out
    # Fresh names are auto-created (coordinates optional).
    out = parse_draw_block("*arc(O ; A ; ZZZ)")
    assert "arc(" in out
    assert_all_finite(out)
    assert "requires 3 args" in parse_draw_block("*arc(O ; A)")


def test_arc_tiny_radius():
    out = parse_draw_block(
        "*point(O = 0, 0)\n*point(A = 0.001, 0)\n*point(B = 0, 0.001)\n*arc(O ; A ; B)"
    )
    assert "arc(" in out
    assert_all_finite(out)


# ------------------------------------------------------------------
# *label
# ------------------------------------------------------------------

def test_label_basic():
    out = parse_draw_block("*point(A = 0, 0)\n*label(A ; hello)")
    assert '[#"hello"]' in out
    # The text must not auto-create a stray point.
    assert out.count("radius: 0.05") == 1


def test_label_long_and_special_chars():
    out = parse_draw_block('*point(A = 0, 0)\n*label(A ; a#b [c] "d" \\ e)')
    assert '[#"a#b [c] \\"d\\" \\\\ e"]' in out
    long_text = "x" * 500
    out = parse_draw_block(f"*point(A = 0, 0)\n*label(A ; {long_text})")
    m = re.search(r'\[#"(x+)"\]', out)
    assert m is not None and len(m.group(1)) == 200  # truncated to limit


def test_label_errors():
    assert "requires 2 args" in parse_draw_block("*label(A)")
    # Fresh point names are auto-created (coordinates optional).
    out = parse_draw_block("*label(ZZZ ; hi)")
    assert '[#"hi"]' in out
    assert_all_finite(out)


# ------------------------------------------------------------------
# *length
# ------------------------------------------------------------------

def test_length_values():
    h = parse_draw_block("*point(A = 0, 0)\n*point(B = 4, 0)\n*length(A ; B)")
    assert '[#"4"]' in h
    v = parse_draw_block("*point(A = 0, 0)\n*point(B = 0, 2.5)\n*length(A ; B)")
    assert '[#"2.5"]' in v
    d = parse_draw_block("*point(A = 0, 0)\n*point(B = 3, 4)\n*length(A ; B)")
    assert '[#"5"]' in d


def test_length_annotation_wins():
    out = parse_draw_block("*point(A = 0, 0)\n*point(B = 4, 0)\n*length(A ; B) = 4 cm")
    assert '[#"4 cm"]' in out


def test_length_errors():
    out = parse_draw_block("*point(A = 1, 1)\n*point(B = 1, 1)\n*length(A ; B)")
    assert "zero-length" in out
    # Fresh names auto-create; the typo-radius rule applies to circles only.
    out = parse_draw_block("*length(A ; ZZZ)")
    assert "content(" in out
    assert_all_finite(out)
    assert "requires 2 args" in parse_draw_block("*length(A)")


# ------------------------------------------------------------------
# *angle-value
# ------------------------------------------------------------------

def test_angle_value_right():
    out = parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 4, 0)\n*point(C = 4, 3)\n*angle-value(A ; B ; C)"
    )
    assert '[#"90°"]' in out
    assert "arc(" in out


def test_angle_value_landmarks():
    cases = [
        ("*point(A = 1, 0)\n*point(B = 0, 0)\n*point(C = -1, 0)\n*angle-value(A ; B ; C)", "180°"),
        ("*point(A = 1, 0)\n*point(B = 0, 0)\n*point(C = 1, 1)\n*angle-value(A ; B ; C)", "45°"),
        ("*point(A = 1, 0)\n*point(B = 0, 0)\n*point(C = -1, 1)\n*angle-value(A ; B ; C)", "135°"),
    ]
    for block, expected in cases:
        out = parse_draw_block(block)
        assert f'[#"{expected}"]' in out, (block, out)


def test_angle_value_reversed_same():
    kw = dict(
        block="*point(A = 0, 0)\n*point(B = 4, 0)\n*point(C = 4, 3)\n*angle-value({})"
    )
    fwd = parse_draw_block(kw["block"].format("A ; B ; C"))
    rev = parse_draw_block(kw["block"].format("C ; B ; A"))
    assert '[#"90°"]' in fwd and '[#"90°"]' in rev


def test_angle_value_degenerate():
    out = parse_draw_block("*angle-value(A ; A ; B)")
    assert "GeometryError" in out
    assert_all_finite(out)
    # Reflex configuration still yields the minor angle, never crashes.
    out = parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 1, 0)\n*point(C = 1, 1)\n*angle-value(A ; B ; C)"
    )
    assert '[#"90°"]' in out
    # Nearly parallel vectors stay finite.
    out = parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 1, 0)\n*point(C = 2, 1e-12)\n*angle-value(A ; B ; C)"
    )
    assert_all_finite(out)


def test_angle_value_annotation():
    out = parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 4, 0)\n*point(C = 4, 3)\n*angle-value(A ; B ; C) = 60°"
    )
    assert '[#"60°"]' in out


# ------------------------------------------------------------------
# infinite lines
# ------------------------------------------------------------------

def test_infinite_horizontal_vertical_diagonal():
    h = parse_draw_block("*point(A = 0, 0)\n*point(B = 4, 0)\n*line(A ; B ; infinite)")
    assert "planned" not in h
    m = re.search(r"line\(\((-?[\d.]+), (-?[\d.]+)\), \((-?[\d.]+), (-?[\d.]+)\)\)", h)
    assert m is not None
    (x1, y1, x2, y2) = map(float, m.groups())
    assert y1 == pytest.approx(0.0) and y2 == pytest.approx(0.0)
    assert x1 < 0 < 4 < x2  # overshoots both points

    v = parse_draw_block("*point(A = 2, 1)\n*point(B = 2, 5)\n*line(A ; B ; infinite)")
    m = re.search(r"line\(\((-?[\d.]+), (-?[\d.]+)\), \((-?[\d.]+), (-?[\d.]+)\)\)", v)
    (x1, y1, x2, y2) = map(float, m.groups())
    assert x1 == pytest.approx(2.0) and x2 == pytest.approx(2.0)
    assert y1 < 1 and y2 > 5

    d = parse_draw_block("*point(A = 0, 0)\n*point(B = 1, 1)\n*line(A ; B ; infinite)")
    assert_all_finite(d)
    for num in numbers(d):
        assert abs(num) < 1e4


def test_infinite_near_vertical_and_case():
    out = parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 0.000001, 5)\n*line(A ; B ; INFINITE)"
    )
    assert "planned" not in out
    assert_all_finite(out)


def test_infinite_degenerate():
    out = parse_draw_block("*point(A = 1, 1)\n*point(B = 1, 1)\n*line(A ; B ; infinite)")
    assert "zero-length" in out
    assert_all_finite(out)


def test_infinite_auto_points_scene():
    # No explicit coordinates: solver places points, line still clips finite.
    out = parse_draw_block("*line(A ; B ; infinite)")
    assert "planned" not in out
    assert_all_finite(out)


# ------------------------------------------------------------------
# adversarial combinations
# ------------------------------------------------------------------

def test_coincident_points_plus_angle():
    out = parse_draw_block("*point(A = 2, 2)\n*point(B = 2, 2)\n*angle(A ; B ; A)")
    assert "GeometryError" in out
    assert_all_finite(out)


def test_zero_length_plus_angle_value():
    out = parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 0, 0)\n*point(C = 1, 1)\n*angle-value(A ; B ; C)"
    )
    assert "GeometryError" in out
    assert_all_finite(out)


def test_malformed_arc_huge_coords():
    out = parse_draw_block(
        "*point(O = 1e6, -1e6)\n*point(A = 1e6, -1e6)\n*point(B = 0, 0)\n*arc(O ; A ; B)"
    )
    assert "GeometryError" in out
    assert_all_finite(out)


def test_infinite_line_tiny_canvas():
    out = parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 0.001, 0.001)\n*line(A ; B ; infinite)"
    )
    assert_all_finite(out)


def test_label_undefined_point_only():
    # Fresh names auto-create, so even a lone label yields a valid canvas.
    out = parse_draw_block("*label(ZZZ ; hello)")
    assert '[#"hello"]' in out
    assert "cetz.canvas" in out  # still a valid canvas
    assert_all_finite(out)


def test_extreme_coords_bbox_finite():
    out = parse_draw_block(
        "*point(A = -1e6, -1e6)\n*point(B = 1e6, 1e6)\n*line(A ; B ; infinite)"
    )
    assert_all_finite(out)


def test_nan_point_plus_marks():
    import numpy as np

    from geometry.solver import GeometrySolver

    s = GeometrySolver()
    s.points["A"] = np.array([float("nan"), 0.0])
    s.points["B"] = np.array([0.0, 0.0])
    s.draw_commands = [
        ("angle", ["A", "B", "A"]),
        ("arc", ["A", "B", "A"]),
        ("length", ["A", "B"]),
        ("angle-value", ["A", "B", "A"]),
        ("label", ["A", "x"]),
        ("line", ["A", "B", "infinite"]),
    ]
    out = geometry.codegen.generate_typst(s, [])
    assert "cetz.canvas" in out
    assert_all_finite(out)


def test_multiple_degenerate_one_doc():
    out = parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 0, 0)\n"
        "*line(A ; B)\n*line(A ; B ; infinite)\n*angle(A ; B ; A)\n"
        "*length(A ; B)\n*angle-value(A ; B ; A)\n*arc(A ; A ; B)\n"
        "*label(ZZZ ; hi)\n*line(A ; B)"
    )
    assert out.count("GeometryError") >= 5
    assert "cetz.canvas" in out
    assert_all_finite(out)


def test_malformed_mixed_with_valid():
    out = parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 4, 0)\n*point(C = 2, 3)\n"
        "*bogus(A ; B)\n*triangle(A ; B ; C)\n*angle(A ; B)"
    )
    assert "unknown geometry command" in out
    assert 'line("A", "B", "C", close: true)' in out
    assert "requires 3 args" in out


def test_strict_arity_no_stray_dots():
    cases = [
        "*point(A = 0, 0)\n*point(B = 1, 0)\n*ray(A ; B ; extra)",
        "*point(O = 0, 0)\n*circle(O ; 3 ; extra)",
        "*point(A = 0, 0)\n*point(B = 1, 0)\n*point(C = 1, 1)\n*right-angle(A ; B ; C ; extra)",
        "*point(A = 0, 0)\n*point(B = 1, 0)\n*line(A ; B ; infinite ; extra)",
        "*point(A = 0, 0)\n*point(B = 1, 0)\n*length(A ; B ; extra)",
        "*point(O = 0, 0)\n*point(A = 1, 0)\n*point(B = 0, 1)\n*arc(O ; A ; B ; extra)",
    ]
    for block in cases:
        out = parse_draw_block(block)
        assert "GeometryError" in out, block
        # No stray dot/label for the rejected arg (it may still appear
        # inside the diagnostic echo, which is fine).
        assert 'name: "extra"' not in out, block
        assert_all_finite(out)


def test_line_third_arg_must_be_infinite():
    out = parse_draw_block("*point(A = 0, 0)\n*point(B = 1, 0)\n*line(A ; B ; infinit)")
    assert "optional 3rd: infinite" in out
    assert 'line("A", "B")' not in out
    # Over-arity point args leave no stray dots (C is past line's arity).
    out = parse_draw_block("*point(A = 0, 0)\n*point(B = 1, 0)\n*line(A ; B ; C ; D)")
    assert "GeometryError" in out
    assert 'name: "C"' not in out


def test_annotation_double_equals_ignored():
    out = parse_draw_block("*point(A = 0, 0)\n*point(B = 4, 0)\n*length(A ; B) == 5")
    assert '[#"4"]' in out  # computed value, not "= 5"


def test_annotation_with_multiplication():
    out = parse_draw_block("*point(A = 0, 0)\n*point(B = 4, 0)\n*length(A ; B) = 2*3")
    assert '[#"2*3"]' in out


def test_annotation_not_leaked_on_failure():
    out = parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 4, 0)\n"
        "*bogus(X) = LEAKED\n*length(A ; B)"
    )
    assert "LEAKED" not in out
    assert '[#"4"]' in out


def test_angle_label_not_validated_as_point():
    out = parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 4, 0)\n*point(C = 4, 3)\n*angle(A ; B ; C ; hello)"
    )
    assert "undefined point" not in out
    assert '[#"hello"]' in out


def test_triangle_extra_point_rejected():
    out = parse_draw_block("*triangle(A ; B ; C ; D)")
    assert "takes 3 points" in out
    # ... and D leaves no stray dot behind.
    assert out.count("radius: 0.05") == 3


def test_huge_fixed_coords_rejected():
    out = parse_draw_block("*point(A = 1000000000000000, 0)\n*point(B = 0, 0)\n*line(A ; B)")
    assert "canvas limit" in out
    assert_all_finite(out)


def test_huge_circle_radius_rejected():
    out = parse_draw_block("*point(O = 0, 0)\n*circle(O ; 1000000000)")
    assert "canvas limit" in out
    assert_all_finite(out)
    out = parse_draw_block("*point(O = 0, 0)\n*circle(O ; 3)")
    assert "radius: 3.000" in out


def test_huge_distance_rejected():
    out = parse_draw_block("*point(A = 0, 0)\n*point(B = 1, 0)\n*distance(A ; B ; 1000000000)")
    assert "canvas limit" in out
    assert_all_finite(out)


def test_error_comments_redacted():
    out = parse_draw_block("*point(A = nan, 0)")
    assert_all_finite(out)
    out = parse_draw_block("*point(A = 1000000000000000, 0)")
    assert_all_finite(out)


# ------------------------------------------------------------------
# *equal-angle (solver constraint + equality marks)
# ------------------------------------------------------------------

_CONGRUENT = (
    "*point(A = 0, 0)\n*point(B = 4, 0)\n*point(C = 2, 3)\n"
    "*point(D = 7, 0)\n*point(E = 11, 0)\n*point(F = 9, 3)\n"
    "*triangle(A ; B ; C)\n*triangle(D ; E ; F)\n"
    "*equal-angle(A ; B ; C ; D ; E ; F)"
)

_CONVERGES = (
    "*point(A = 0, 0)\n*point(B = 4, 0)\n*point(C = 2, 3)\n"
    "*point(D = 7, 0)\n*point(E = 11, 0)\n*point(F)\n"
    "*equal-angle(A ; B ; C ; D ; E ; F)\n*distance(E ; F ; 5)"
)


def _point_xy(output, name):
    """Solved position of *name* from the drawn point dot."""
    m = re.search(
        rf'circle\(\(([-\d.]+), ([-\d.]+)\), radius: 0\.05, '
        rf'fill: black, name: "{name}"\)', output)
    assert m, f'point {name} not drawn'
    return float(m.group(1)), float(m.group(2))


def _angle_deg(output, first, vertex, last):
    (x1, y1), (vx, vy), (x2, y2) = (
        _point_xy(output, first), _point_xy(output, vertex),
        _point_xy(output, last))
    v1, v2 = (x1 - vx, y1 - vy), (x2 - vx, y2 - vy)
    cross = abs(v1[0] * v2[1] - v1[1] * v2[0])
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    return math.degrees(math.atan2(cross, dot))


def test_equal_angle_draws_identical_marks():
    out = parse_draw_block(_CONGRUENT)
    assert_all_finite(out)
    arcs = re.findall(
        r'arc\(\(([-\d.]+), ([-\d.]+)\), start: ([\d.]+)deg, '
        r'stop: ([\d.]+)deg, radius: 0\.400\)', out)
    assert len(arcs) == 2, out
    # Same arc on both angles: identical start/stop/radius, one per vertex.
    (_x1, _y1, s1, e1), (_x2, _y2, s2, e2) = arcs
    assert (s1, e1) == (s2, e2)
    # One radial tick across each arc (the equality mark): the only
    # anonymous point-pair lines in this scene (named-point edges
    # render as line("A", "B", ...)).
    ticks = [l for l in code_lines(out)
             if l.strip().startswith('line((')]
    assert len(ticks) == 2
    assert "GeometryError" not in out and "GeometryWarning" not in out


def test_equal_angle_constraint_converges():
    # F is free: the solver must place it so angle DEF equals angle ABC.
    out = parse_draw_block(_CONVERGES)
    assert_all_finite(out)
    assert "GeometryError" not in out
    assert "did not converge" not in out
    deg_abc = _angle_deg(out, 'A', 'B', 'C')
    deg_def = _angle_deg(out, 'D', 'E', 'F')
    assert abs(deg_def - deg_abc) < 1.0, (deg_abc, deg_def)


def test_equal_angle_arity_error():
    out = parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 1, 0)\n*point(C = 0, 1)\n"
        "*point(D = 3, 0)\n*point(E = 4, 0)\n*equal-angle(A ; B ; C ; D ; E)")
    assert "requires 6 arguments" in out
    assert_all_finite(out)


def test_equal_angle_undefined_point():
    # *equal-angle is a constraint: its points are auto-created like
    # every other command's (coordinates optional).
    out = parse_draw_block("*equal-angle(A ; B ; C ; D ; E ; F)")
    assert "arc(" in out
    assert_all_finite(out)


def test_equal_angle_coincident_points():
    out = parse_draw_block(
        "*point(A = 1, 1)\n*point(C = 2, 3)\n"
        "*point(D = 7, 0)\n*point(E = 11, 0)\n*point(F = 9, 3)\n"
        "*equal-angle(A ; A ; C ; D ; E ; F)")
    assert "coincident points" in out
    assert_all_finite(out)


def test_equal_angle_mismatch_warns():
    # All six points fixed by hand with unequal angles: marks are still
    # drawn, with a warning (the solver cannot fix a fully-fixed scene).
    out = parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 4, 0)\n*point(C = 2, 3)\n"
        "*point(D = 7, 0)\n*point(E = 11, 0)\n*point(F = 9, 1)\n"
        "*equal-angle(A ; B ; C ; D ; E ; F)")
    assert re.search(
        r'// \[GeometryWarning\] \*equal-angle\(A ; B ; C ; D ; E ; F\): '
        r'[\d.]+° vs [\d.]+°', out)
    assert_all_finite(out)


def _draw_blocks_in(text):
    """Every *draw(...) block body, via the editor's pipeline-mirroring
    block finder (comments and single-line blocks handled)."""
    from editor.draw_catalog import draw_block_body, find_enclosing_draw_block
    blocks, pos = [], 0
    while True:
        idx = text.find('*draw(', pos)
        if idx == -1:
            return blocks
        span = find_enclosing_draw_block(text, idx)
        if span is None:
            pos = idx + 1
            continue
        start, end = span
        blocks.append(draw_block_body(text[start:end]))
        pos = end + 1


def test_examples_file_blocks_compile():
    """Every *draw block in examples/draw_test.ezmath (including the
    equal-angle one) solves and generates Typst without diagnostics."""
    path = os.path.join(
        os.path.dirname(__file__), '..', 'examples', 'draw_test.ezmath')
    with open(path, encoding='utf-8') as handle:
        blocks = _draw_blocks_in(handle.read())
    assert len(blocks) == 4
    for body in blocks:
        out = parse_draw_block(body)
        assert "GeometryError" not in out
        assert "GeometryWarning" not in out
        assert '#import "@preview/cetz' in out


def test_equal_angle_docs_example_compiles():
    """The example in docs/geometry.md's *equal-angle section solves and
    generates Typst without diagnostics."""
    path = os.path.join(
        os.path.dirname(__file__), '..', 'docs', 'geometry.md')
    from editor.draw_catalog import draw_block_body
    with open(path, encoding='utf-8') as handle:
        text = handle.read()
    start = text.index('### Two angles are equal')
    end = text.find('\n### ', start + 1)
    section = text[start:end if end != -1 else len(text)]
    # Doc examples live in ``` fenced blocks (the block finder treats
    # fences as documentation, not blocks — extract them directly).
    fenced, buf, in_fence = [], [], False
    for line in section.splitlines():
        if line.strip().startswith('```'):
            if in_fence and buf:
                fenced.append('\n'.join(buf))
            in_fence = not in_fence
            buf = []
            continue
        if in_fence:
            buf.append(line)
    blocks = [draw_block_body(b) for b in fenced
              if b.lstrip().startswith('*draw(')]
    assert len(blocks) == 1
    out = parse_draw_block(blocks[0])
    assert "GeometryError" not in out
    assert "GeometryWarning" not in out
    # The doc example leaves F free and the constraint satisfied.
    deg_abc = _angle_deg(out, 'A', 'B', 'C')
    deg_def = _angle_deg(out, 'D', 'E', 'F')
    assert abs(deg_def - deg_abc) < 1.0, (deg_abc, deg_def)


# ------------------------------------------------------------------
# Auto-positioned examples (solver-placed points)
# ------------------------------------------------------------------
#
# Every example that lets the solver place points is solved here and its
# stated constraints are asserted within a stated tolerance.
#
# Tolerances are measured, not guessed: the solver converges to
# cost < 1e-4, which on these figures means position errors <= 0.05
# (worst measured: 0.0497 on a 5-unit side) and length errors <= 0.01.
# The perpendicularity dot products sit on 3-5 unit vectors, where the
# measured worst was 0.12 -> tolerance 0.15. The 1-degree angle margin
# matches the solver's convergence threshold (~0.57 deg).

import contextlib as _contextlib
import io as _io

from editor.draw_catalog import CATALOG, draw_block_body as _body_of
from geometry.commands import _process_command as _process
from geometry.parsing import _parse_commands as _parse_cmds, split_args_for
from geometry.solver import GeometrySolver


def _solve(body):
    """Build and solve the solver for a draw-block body."""
    solver = GeometrySolver()
    with _contextlib.redirect_stderr(_io.StringIO()):
        for cmd, args_str, _annot in _parse_cmds(body):
            _process(solver, cmd, split_args_for(cmd, args_str))
        solver.validate()
        solver.solve()
    return solver


def _pts(solver):
    return {p: (float(c[0]), float(c[1])) for p, c in solver.points.items()}


def _dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def _dot(u, v):
    return u[0] * v[0] + u[1] * v[1]


def _sub(p, q):
    return (p[0] - q[0], p[1] - q[1])


def _dist_to_line(p, a, b):
    """Distance from p to the infinite line through a and b."""
    ab = _sub(b, a)
    n = _dist(a, b)
    assert n > 1e-9
    return abs(ab[0] * (p[1] - a[1]) - ab[1] * (p[0] - a[0])) / n


LEN_TOL = 0.05     # measured length error <= 0.0094
DOT_TOL = 0.15     # measured perpendicularity dot <= 0.12 on 3-5 unit arms
ANG_TOL = 1.0      # degrees; solver convergence is ~0.57 deg


def _check_right_triangle(P):
    # A=(0,0), B=(4,0) pinned; C auto with |AC|=3 and AC perpendicular AB.
    assert abs(_dist(P['A'], P['C']) - 3) <= LEN_TOL
    assert abs(_dot(_sub(P['B'], P['A']), _sub(P['C'], P['A']))) <= DOT_TOL
    return True


def _check_isosceles(P, a, b, c):
    # Base a-b pinned; apex auto with |ac| = |bc| and |ac| = 5.
    assert abs(_dist(P[a], P[c]) - 5) <= LEN_TOL
    assert abs(_dist(P[a], P[c]) - _dist(P[b], P[c])) <= LEN_TOL
    return True


def _check_tangent(P, o, p, q):
    # o=(0,0), p=(3,0) pinned; q auto on the tangent through p, |pq| = 2.
    assert abs(_dist(P[o], P[p]) - 3) <= LEN_TOL
    assert abs(_dist(P[p], P[q]) - 2) <= LEN_TOL
    assert abs(_dot(_sub(P[p], P[o]), _sub(P[q], P[p]))) <= DOT_TOL
    return True


def _check_equal_angles(P, a, b, c, d, e, f):
    def deg(x, y, z):
        v1, v2 = _sub(P[x], P[y]), _sub(P[z], P[y])
        return math.degrees(math.atan2(
            abs(v1[0] * v2[1] - v1[1] * v2[0]), _dot(v1, v2)))
    assert abs(deg(a, b, c) - deg(d, e, f)) <= ANG_TOL
    return True


def _catalog_body(entry_id):
    entry = next(e for e in CATALOG if e.id == entry_id)
    return _body_of(entry.example)


@pytest.mark.parametrize('entry_id,check', [
    ('point', lambda P: (
        abs(_dist(P['A'], P['C']) - 3) <= LEN_TOL
        and abs(_dist(P['B'], P['C']) - 4) <= LEN_TOL)),
    ('distance', lambda P: abs(_dist(P['A'], P['B']) - 5) <= LEN_TOL),
    ('parallel', lambda P: (
        abs(_dist(P['C'], P['D']) - 5) <= LEN_TOL
        and abs(_sub(P['B'], P['A'])[0] * _sub(P['D'], P['C'])[1]
                - _sub(P['B'], P['A'])[1] * _sub(P['D'], P['C'])[0])
        / 25 <= 0.02)),
    ('perp', _check_right_triangle),
    ('on-line', lambda P: (
        _dist_to_line(P['C'], P['A'], P['B']) <= LEN_TOL
        and abs(_dist(P['B'], P['C']) - 3) <= LEN_TOL)),
    ('on-circle', lambda P: abs(_dist(P['O'], P['A']) - 3) <= LEN_TOL),
    ('equal-length', lambda P: _check_isosceles(P, 'A', 'B', 'C')),
    ('midpoint', lambda P: _dist(
        P['M'],
        ((P['A'][0] + P['B'][0]) / 2, (P['A'][1] + P['B'][1]) / 2),
    ) <= LEN_TOL),
])
def test_gallery_auto_examples_satisfy_constraints(entry_id, check):
    """Every gallery card that lets the solver place a point produces a
    figure whose stated constraints hold (within the measured solver
    tolerance)."""
    assert check(_pts(_solve(_catalog_body(entry_id))))


def test_example_files_auto_examples_satisfy_constraints():
    """The example files' solver-placed points satisfy their constraints."""
    exdir = os.path.join(os.path.dirname(__file__), '..', 'examples')
    with open(os.path.join(exdir, 'draw_test.ezmath'), encoding='utf-8') as h:
        blocks = {i: b for i, b in enumerate(_draw_blocks_in(h.read()))}
    assert len(blocks) == 4
    P = _pts(_solve(blocks[0]))
    _check_right_triangle(P)                    # right triangle at A
    _check_isosceles(_pts(_solve(blocks[1])), 'D', 'E', 'F')
    _check_tangent(_pts(_solve(blocks[2])), 'O', 'P', 'Q')
    _check_equal_angles(_pts(_solve(blocks[3])), 'A', 'B', 'C', 'D', 'E', 'F')

    # example_3.ezmath: right triangle clone + the pinned on-circle demo.
    with open(os.path.join(exdir, 'example_3.ezmath'), encoding='utf-8') as h:
        ex3 = _draw_blocks_in(h.read())
    _check_right_triangle(_pts(_solve(ex3[0])))
    P = _pts(_solve(ex3[1]))
    assert P['P'] == (3.0, 0.0)                 # pinned points never move
    assert abs(_dist(P['O'], P['P']) - 3) <= LEN_TOL

    # example_2.ezmath: D, E, F are solver-placed on the cevians.
    with open(os.path.join(exdir, 'example_2.ezmath'), encoding='utf-8') as h:
        ex2 = _draw_blocks_in(h.read())
    P = _pts(_solve(ex2[0]))
    assert _dist_to_line(P['D'], P['A'], P['M']) <= LEN_TOL
    assert _dist_to_line(P['D'], P['B'], P['C']) <= LEN_TOL
    assert _dist_to_line(P['E'], P['B'], P['M']) <= LEN_TOL
    assert _dist_to_line(P['E'], P['C'], P['A']) <= LEN_TOL
    assert _dist_to_line(P['F'], P['C'], P['M']) <= LEN_TOL
    assert _dist_to_line(P['F'], P['A'], P['B']) <= LEN_TOL


def _docs_draw_blocks(path):
    """Fenced ``` blocks of a docs file that are complete *draw examples."""
    with open(path, encoding='utf-8') as h:
        text = h.read()
    fenced, buf, in_fence = [], [], False
    for line in text.splitlines():
        if line.strip().startswith('```'):
            if in_fence and buf:
                joined = '\n'.join(buf)
                if joined.lstrip().startswith('*draw('):
                    fenced.append(_body_of(joined))
            in_fence = not in_fence
            buf = []
            continue
        if in_fence:
            buf.append(line)
    return fenced


def test_docs_auto_examples_satisfy_constraints():
    """Every complete *draw example in the docs satisfies its constraints."""
    docs = os.path.join(os.path.dirname(__file__), '..', 'docs')
    bodies = (_docs_draw_blocks(os.path.join(docs, 'geometry.md'))
              + _docs_draw_blocks(os.path.join(docs, 'cheatsheet.md')))
    assert len(bodies) == 7   # 6 in geometry.md + 1 in cheatsheet.md
    checked = 0
    for body in bodies:
        P = _pts(_solve(body))
        if '*distance(A ; C ; 3)' in body and '*perp(A ; B ; A ; C)' in body:
            _check_right_triangle(P)            # Example 1 + cheat sheet
            checked += 1
        elif '*equal-length(A ; C ; B ; C)' in body:
            _check_isosceles(P, 'A', 'B', 'C')  # Example 2
            checked += 1
        elif '*perp(O ; A ; A ; B)' in body:
            _check_tangent(P, 'O', 'A', 'B')    # Example 3 (converted)
            checked += 1
        elif '*equal-angle(A ; B ; C ; D ; E ; F)' in body:
            _check_equal_angles(P, 'A', 'B', 'C', 'D', 'E', 'F')
            checked += 1
    assert checked == 5, 'docs examples changed — update the matchers'


def test_draw_examples_not_underconstrained():
    """Guard against under-constrained examples: every solver-placed
    point must be referenced by at least one constraint, and the solved
    figure must have no near-coincident points (the bare auto triangle
    collapses to A-C ~0.3 apart, which this catches)."""
    root = os.path.join(os.path.dirname(__file__), '..')
    bodies = []
    for name in ('draw_test.ezmath', 'example_2.ezmath', 'example_3.ezmath',
                 'construction_points.ezmath'):
        with open(os.path.join(root, 'examples', name),
                  encoding='utf-8') as h:
            bodies.extend((name, b) for b in _draw_blocks_in(h.read()))
    for entry in CATALOG:
        bodies.append((f'catalog:{entry.id}',
                       _body_of(entry.example)))
    for name in ('geometry.md', 'cheatsheet.md'):
        bodies.extend(
            (f'docs:{name}', b)
            for b in _docs_draw_blocks(os.path.join(root, 'docs', name)))
    assert len(bodies) >= 35

    for label, body in bodies:
        solver = _solve(body)
        points = _pts(solver)
        auto = [p for p in solver.points
                if p not in solver.fixed and p not in solver.derived]
        for p in auto:
            referenced = any(
                p in constraint_label
                for constraint_label, _fn, *rest in solver.constraints)
            assert referenced, (
                f'{label}: auto point {p} is not referenced by any constraint'
            )
        names = sorted(points)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                gap = _dist(points[a], points[b])
                assert gap >= 0.5, (
                    f'{label}: solved points {a} and {b} are only '
                    f'{gap:.3f} apart — the figure is degenerate'
                )


def test_solving_is_deterministic():
    """Solving the same example twice yields identical coordinates —
    in-process, through the whole pipeline, and across processes (the
    auto-point start guess is a name hash, not randomness)."""
    bodies = [
        _catalog_body('perp'),
        _catalog_body('on-circle'),
        _draw_blocks_in(open(os.path.join(
            os.path.dirname(__file__), '..', 'examples', 'draw_test.ezmath'),
            encoding='utf-8').read())[2],
    ]
    for body in bodies:
        first = _pts(_solve(body))
        second = _pts(_solve(body))
        assert first == second
        # Whole-pipeline determinism: identical generated Typst.
        assert parse_draw_block(body) == parse_draw_block(body)

    # Cross-process pin: fresh interpreters land on the same spot for the
    # right triangle's auto point C. Update the constant if the solver's
    # seeding or convergence changes on purpose.
    out = parse_draw_block(_catalog_body('perp'))
    x, y = _point_xy(out, 'C')
    assert (round(x, 3), round(y, 3)) == (0.030, 3.000)
