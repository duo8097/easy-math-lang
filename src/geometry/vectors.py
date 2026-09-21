"""Vector and bounding-box helpers for the geometry solver."""

import numpy as np


def _norm(v):
    return np.linalg.norm(v)


def _cross2d(v1, v2):
    return v1[0] * v2[1] - v1[1] * v2[0]


def _normalize(v):
    import math as _math

    n = _norm(v)
    try:
        n_f = float(n)
    except (TypeError, ValueError):
        raise ValueError("cannot normalize vector with non-numeric length")
    if not _math.isfinite(n_f) or n_f < 1e-9:
        raise ValueError("cannot normalize zero-length or non-finite vector")
    return v / n


def _bounding_box(points_dict):
    """Return (xmin, ymin, xmax, ymax) of all points."""
    if not points_dict:
        raise ValueError("cannot compute bounding box of empty point set")
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

    # Cap the extension at the scene diagonal: a near-axis-parallel ray
    # can otherwise yield t ~ 1e9 and an uncompilable CeTZ line.
    import math as _math

    diag = _math.hypot(xmax - xmin, ymax - ymin)
    if _math.isfinite(diag):
        t_max = min(t_max, diag + margin)

    return t_max
