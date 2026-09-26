from __future__ import annotations

from dataclasses import dataclass
import time

import cv2
import numpy as np


@dataclass
class Observation:
    timestamp_ns: int
    ids: np.ndarray
    corners: np.ndarray
    quality: float
    quality_x: float
    quality_y: float
    contrast: float
    width: int
    height: int

    def as_json(self):
        return {"timestamp_ns": self.timestamp_ns, "ids": self.ids.reshape(-1).tolist(),
                "corners": self.corners.reshape(-1, 2).tolist(),
                "quality": self.quality, "quality_x": self.quality_x,
                "quality_y": self.quality_y, "contrast": self.contrast,
                "image_size": [self.width, self.height]}


def _corner_quality(gray, corners, radius=6):
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    values = []
    for x, y in corners.reshape(-1, 2):
        xi, yi = int(round(x)), int(round(y))
        x0, x1 = max(0, xi-radius), min(gray.shape[1], xi+radius+1)
        y0, y1 = max(0, yi-radius), min(gray.shape[0], yi+radius+1)
        if x1-x0 < 5 or y1-y0 < 5:
            continue
        px, py, patch = gx[y0:y1, x0:x1], gy[y0:y1, x0:x1], gray[y0:y1, x0:x1]
        values.append((float(np.percentile(np.abs(px), 90)),
                       float(np.percentile(np.abs(py), 90)), float(patch.std())))
    if not values:
        return 0.0, 0.0, 0.0, 0.0
    a = np.asarray(values)
    qx, qy, contrast = np.percentile(a, 20, axis=0)
    # Harmonic mean penalizes blur in either direction. Normalize by local
    # contrast so exposure/contrast changes do not dominate the threshold.
    directional = 2.0 * qx * qy / max(1e-9, qx + qy)
    score = directional / max(10.0, contrast)
    return float(score), float(qx), float(qy), float(contrast)


def detect(gray, detector, min_corners=12, timestamp_ns=None):
    corners, ids, _, _ = detector.detectBoard(gray)
    if corners is None or ids is None or len(corners) < min_corners:
        return None
    q, qx, qy, contrast = _corner_quality(gray, corners)
    h, w = gray.shape[:2]
    return Observation(time.monotonic_ns() if timestamp_ns is None else timestamp_ns,
                       ids.astype(np.int32),
                       corners.astype(np.float32), q, qx, qy, contrast, w, h)


def common_motion(a: Observation, b: Observation, min_common=8):
    ma = {int(i): p for i, p in zip(a.ids.reshape(-1), a.corners.reshape(-1, 2))}
    mb = {int(i): p for i, p in zip(b.ids.reshape(-1), b.corners.reshape(-1, 2))}
    ids = sorted(ma.keys() & mb.keys())
    if len(ids) < min_common:
        return None
    delta = np.asarray([mb[i] - ma[i] for i in ids])
    lengths = np.linalg.norm(delta, axis=1)
    return {"common": len(ids), "median_px": float(np.median(lengths)),
            "p90_px": float(np.percentile(lengths, 90))}


def pose_change(a: Observation, b: Observation, min_common=8):
    ma = {int(i): p for i, p in zip(a.ids.reshape(-1), a.corners.reshape(-1, 2))}
    mb = {int(i): p for i, p in zip(b.ids.reshape(-1), b.corners.reshape(-1, 2))}
    ids = sorted(ma.keys() & mb.keys())
    if len(ids) < min_common:
        return {"changed": False, "reason": "not-enough-common-corners"}
    src = np.asarray([ma[i] for i in ids], np.float32)
    dst = np.asarray([mb[i] for i in ids], np.float32)
    M, _ = cv2.estimateAffinePartial2D(src, dst, method=cv2.LMEDS)
    if M is None:
        return {"changed": True, "reason": "affine-fit-failed"}
    scale = float(np.hypot(M[0, 0], M[1, 0]))
    angle = float(abs(np.degrees(np.arctan2(M[1, 0], M[0, 0]))))
    translation = float(np.hypot(M[0, 2], M[1, 2]))
    predicted = cv2.transform(src.reshape(-1, 1, 2), M).reshape(-1, 2)
    shape_p90 = float(np.percentile(np.linalg.norm(predicted - dst, axis=1), 90))
    changed = (translation >= 35.0 or abs(scale - 1.0) >= .07 or angle >= 7.0
               or shape_p90 >= 4.0)
    return {"changed": changed, "translation_px": translation,
            "scale_ratio": scale, "rotation_deg": angle,
            "non_similarity_p90_px": shape_p90}
