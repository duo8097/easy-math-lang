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
    assert "arc((3.000, 0.000), start: 0.00deg, stop: 90.00deg" in out
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
