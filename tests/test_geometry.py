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
