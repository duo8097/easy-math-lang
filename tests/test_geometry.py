"""Geometry tests for easy-math-lang."""

import os
import re
import sys

import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "src")
)

from easy_math_lang import geometry


def shape_circles(output, name):
    """Count shape circles for center `name` (excludes point dots)."""
    return [
        line
        for line in output.splitlines()
        if f'circle("{name}"' in line
    ]


def test_basic_point():
    out = geometry.parse_draw_block("*point(A = 1, 2)")
    assert "circle((1.000, 2.000)" in out
    assert 'name: "A"' in out


def test_cetz_version_pin():
    # Generated canvases must import a CeTZ release verified to compile
    # with the array-coordinate syntax we emit (0.3.1 mispanics on
    # typst ≥ 0.15: "Failed to resolve coordinate").
    out = geometry.parse_draw_block("*point(A = 1, 2)")
    assert '#import "@preview/cetz:0.4.2"' in out
    assert "cetz:0.3.1" not in out


def test_line():
    out = geometry.parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 4, 0)\n*line(A ; B)"
    )
    assert 'line("A", "B")' in out


def test_circle_numeric_radius():
    out = geometry.parse_draw_block(
        "*point(O = 0, 0)\n*circle(O ; 3)"
    )
    circles = shape_circles(out, "O")
    assert len(circles) == 1
    assert "radius: 3.000" in circles[0]


def test_circle_point_radius_single_circle():
    # Regression test: *circle(O ; A) must emit exactly ONE shape circle
    # with the computed numeric radius, not two circles.
    out = geometry.parse_draw_block(
        "*point(O = 0, 0)\n*point(A = 3, 4)\n*circle(O ; A)"
    )
    circles = shape_circles(out, "O")
    assert len(circles) == 1
    assert "radius: 5.000" in circles[0]


def test_nested_geometry_arguments():
    # Nested line(...) args must not terminate at the first ')'.
    out = geometry.parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 4, 4)\n"
        "*point(D = 0, 4)\n*point(E = 4, 0)\n"
        "*intersection(C ; line(A ; B) ; line(D ; E))"
    )
    # Diagonals of the square meet at (2, 2); the iterative solver
    # lands within a small tolerance.
    match = re.search(
        r'circle\(\((\-?\d+\.\d+),\s*(\-?\d+\.\d+)\), radius: 0\.05, '
        r'fill: black, name: "C"\)',
        out,
    )
    assert match is not None
    assert float(match.group(1)) == pytest.approx(2.0, abs=0.01)
    assert float(match.group(2)) == pytest.approx(2.0, abs=0.01)


def test_intersection():
    out = geometry.parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 4, 0)\n"
        "*point(D = 2, -2)\n*point(E = 2, 2)\n"
        "*intersection(C ; line(A ; B) ; line(D ; E))"
    )
    match = re.search(
        r'circle\(\((\-?\d+\.\d+),\s*(\-?\d+\.\d+)\), radius: 0\.05, '
        r'fill: black, name: "C"\)',
        out,
    )
    assert match is not None
    assert float(match.group(1)) == pytest.approx(2.0, abs=0.01)
    assert float(match.group(2)) == pytest.approx(0.0, abs=0.01)


def test_right_angle_generation():
    out = geometry.parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 4, 0)\n*point(C = 0, 3)\n"
        "*right-angle(B ; A ; C)"
    )
    markers = [
        line for line in out.splitlines() if line.strip().startswith("line((")
    ]
    # One L-shaped marker drawn from A toward B and C.
    assert len(markers) == 1
    assert markers[0].count("(") >= 3


def test_ray_extension():
    out = geometry.parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 1, 0)\n*ray(A ; B)"
    )
    ray_lines = [line for line in out.splitlines() if 'mark: (end: ">")' in line]
    assert len(ray_lines) == 1
    nums = [float(v) for v in re.findall(r"-?\d+\.\d+", ray_lines[0])]
    # Ray starts at A (0,0) and ends beyond B (x > 1).
    assert nums[0] == pytest.approx(0.0)
    assert nums[2] > 1.0


def test_auto_positioning_without_explicit_points():
    # Coordinates are optional: bare triangle must not raise undefined-point.
    out = geometry.parse_draw_block("*triangle(A ; B ; C)")
    assert 'line("A", "B", "C", close: true)' in out
    assert "undefined point" not in out


def test_missing_point_args():
    out = geometry.parse_draw_block("*line(A)")
    assert "requires 2 point args" in out


def test_invalid_constraint():
    out = geometry.parse_draw_block("*distance(A ; B)")
    assert "requires 3 arguments" in out


def test_unknown_geometry_command():
    out = geometry.parse_draw_block("*foobar(A ; B)")
    assert "unknown geometry command" in out


def test_conflicting_constraints():
    out = geometry.parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 1, 0)\n"
        "*distance(A ; B ; 5)\n*distance(A ; B ; 7)"
    )
    assert "constraint conflict" in out


def test_solver_non_convergence_warning():
    out = geometry.parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 1, 0)\n*distance(A ; B ; 5)"
    )
    assert "did not converge" in out


def test_malformed_geometry_syntax(capsys):
    out = geometry.parse_draw_block("*point(A")
    captured = capsys.readouterr()
    assert "unclosed parentheses" in captured.err
    assert out  # still returns a (possibly empty) canvas


def test_zero_length_line():
    out = geometry.parse_draw_block(
        "*point(A = 1, 1)\n*point(B = 1, 1)\n*line(A ; B)"
    )
    assert "zero-length" in out


def test_zero_length_ray():
    out = geometry.parse_draw_block(
        "*point(A = 2, 2)\n*point(B = 2, 2)\n*ray(A ; B)"
    )
    assert "zero-length" in out


def test_deterministic_placement():
    block = "*triangle(A ; B ; C)"
    assert geometry.parse_draw_block(block) == geometry.parse_draw_block(block)


def _content_lines(output):
    return [
        line.strip()
        for line in output.splitlines()
        if line.strip().startswith("content(")
    ]


def test_label_anchors_line_endpoints():
    out = geometry.parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 4, 0)\n*line(A ; B)"
    )
    lines = _content_lines(out)
    assert 'content("A", [A], anchor: "east", padding: 0.12)' in lines
    assert 'content("B", [B], anchor: "west", padding: 0.12)' in lines


def test_label_anchors_triangle_vertices():
    # Labels sit outside the triangle, opposite the incident sides.
    out = geometry.parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 4, 0)\n*point(C = 0, 3)\n"
        "*triangle(A ; B ; C)"
    )
    lines = _content_lines(out)
    assert 'content("A", [A], anchor: "north-east", padding: 0.12)' in lines
    assert 'content("B", [B], anchor: "west", padding: 0.12)' in lines
    assert 'content("C", [C], anchor: "south-east", padding: 0.12)' in lines


def test_label_anchor_isolated_point_default():
    out = geometry.parse_draw_block("*point(Z)")
    lines = _content_lines(out)
    assert 'content("Z", [Z], anchor: "south-west", padding: 0.12)' in lines


def test_label_anchor_circle_point_outward():
    # On-circle label goes outward, away from the center.
    out = geometry.parse_draw_block(
        "*point(O = 0, 0)\n*point(P = 3, 0)\n*circle(O ; P)"
    )
    lines = _content_lines(out)
    assert 'content("O", [O], anchor: "south-west", padding: 0.12)' in lines
    assert 'content("P", [P], anchor: "west", padding: 0.12)' in lines


def test_label_anchor_near_circle_tangent_endpoint():
    # Q sits ~0.001 off the circle outline (tangent endpoint): it must be
    # labeled along the outward normal, not along the segment hugging
    # the circle.
    out = geometry.parse_draw_block(
        "*point(O = 0, 0)\n*point(P = -2.71, -1.28)\n"
        "*point(Q = -2.63, -1.44)\n"
        "*circle(O ; 3)\n*line(O ; P)\n*line(P ; Q)"
    )
    lines = _content_lines(out)
    assert 'content("Q", [Q], anchor: "north-east", padding: 0.12)' in lines


def test_label_anchor_far_from_circle_uses_edges():
    # A point well clear of the circumference ignores the circle.
    out = geometry.parse_draw_block(
        "*point(O = 0, 0)\n*circle(O ; 3)\n"
        "*point(F = 0, 5)\n*point(G = 4, 5)\n*line(F ; G)"
    )
    lines = _content_lines(out)
    assert 'content("F", [F], anchor: "east", padding: 0.12)' in lines


def test_label_anchors_use_valid_compass_set():
    out = geometry.parse_draw_block(
        "*point(A = 0, 0)\n*point(B = 4, 0)\n*point(C)\n"
        "*distance(A ; C ; 3)\n*perp(A ; B ; A ; C)\n"
        "*triangle(A ; B ; C)\n*right-angle(B ; A ; C)"
    )
    valid = {
        "north", "north-east", "east", "south-east",
        "south", "south-west", "west", "north-west",
    }
    found = re.findall(r'content\("[^"]+", \[[^\]]+\], anchor: "([^"]+)"', out)
    assert found
    assert set(found) <= valid
