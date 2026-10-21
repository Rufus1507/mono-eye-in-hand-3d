from __future__ import annotations

import cv2
import numpy as np


def _undistort_iter(p, K, D, criteria):
    if hasattr(cv2, "undistortPointsIter"):
        return cv2.undistortPointsIter(p, K, D, None, None, criteria)
    return cv2.undistortPoints(p, K, D, criteria=criteria)


def _ray(points, K, D):
    p = np.asarray(points, np.float64).reshape(-1, 1, 2)
    q = _undistort_iter(
        p, np.asarray(K, np.float64), np.asarray(D, np.float64),
        (cv2.TERM_CRITERIA_COUNT | cv2.TERM_CRITERIA_EPS, 100, 1e-12),
    ).reshape(-1, 2)
    rays = np.column_stack((q, np.ones(len(q))))
    return rays / np.linalg.norm(rays, axis=1, keepdims=True)


def angle_between(points, K, D):
    rays = _ray(points, K, D)
    dot = float(np.clip(rays[0] @ rays[1], -1.0, 1.0))
    return float(np.degrees(np.arccos(dot)))


def field_of_view(K, D, width: int, height: int) -> dict:
    """FOV of raw distorted image. Pixel centers are 0..N-1; edges are ±0.5."""
    K = np.asarray(K, np.float64)
    left, right, top, bottom = -0.5, width - 0.5, -0.5, height - 0.5
    cx, cy = float(K[0, 2]), float(K[1, 2])
    return {
        "horizontal_deg": angle_between(((left, cy), (right, cy)), K, D),
        "vertical_deg": angle_between(((cx, top), (cx, bottom)), K, D),
        "diagonal_tl_br_deg": angle_between(((left, top), (right, bottom)), K, D),
        "diagonal_tr_bl_deg": angle_between(((right, top), (left, bottom)), K, D),
        "definition": "raw-image rays through principal-point row/column; pixel edges -0.5..N-0.5",
    }


def pinhole_reference(K, width: int, height: int) -> dict:
    K = np.asarray(K, np.float64)
    fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]
    def span(size, c, f):
        return float(np.degrees(np.arctan((c + .5) / f) +
                                np.arctan((size - .5 - c) / f)))
    return {"horizontal_deg": span(width, cx, fx),
            "vertical_deg": span(height, cy, fy)}


def distortion_health(K, D, width: int, height: int, grid: int = 31) -> dict:
    xs = np.linspace(-.5, width - .5, grid)
    ys = np.linspace(-.5, height - .5, grid)
    pixels = np.array([(x, y) for y in ys for x in xs], np.float64).reshape(-1, 1, 2)
    rays = _undistort_iter(
        pixels, K, D,
        (cv2.TERM_CRITERIA_COUNT | cv2.TERM_CRITERIA_EPS, 100, 1e-12),
    )
    obj = np.column_stack((rays.reshape(-1, 2), np.ones(len(rays))))
    back, _ = cv2.projectPoints(obj, np.zeros(3), np.zeros(3), K, D)
    error = np.linalg.norm(back.reshape(-1, 2) - pixels.reshape(-1, 2), axis=1)
    finite = bool(np.isfinite(rays).all() and np.isfinite(error).all())
    q = rays.reshape(grid, grid, 2)
    dx = q[1:-1, 2:, :] - q[1:-1, :-2, :]
    dy = q[2:, 1:-1, :] - q[:-2, 1:-1, :]
    det = dx[..., 0] * dy[..., 1] - dx[..., 1] * dy[..., 0]
    orientation_ok = bool(np.isfinite(det).all() and np.all(det > 0))
    return {"finite": finite, "roundtrip_max_px": float(error.max()),
            "roundtrip_rms_px": float(np.sqrt(np.mean(error ** 2))), "grid": grid,
            "inverse_jacobian_min": float(det.min()),
            "inverse_jacobian_max": float(det.max()),
            "orientation_preserving": orientation_ok,
            "valid": finite and orientation_ok and float(error.max()) < 0.1}
