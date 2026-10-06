from __future__ import annotations

import cv2


def draw(frame, obs, status, count, target, mirror=True):
    view = cv2.flip(frame, 1) if mirror else frame.copy()
    if obs is not None:
        w = frame.shape[1]
        for x, y in obs.corners.reshape(-1, 2):
            xx = w - 1 - int(x) if mirror else int(x)
            cv2.circle(view, (xx, int(y)), 3, (0, 255, 255), -1, cv2.LINE_AA)
    panel = 88
    canvas = cv2.copyMakeBorder(view, panel, 28, 0, 0, cv2.BORDER_CONSTANT, value=(18,18,18))
    color = (80, 220, 80) if status.startswith("Da luu") else (50, 200, 240)
    cv2.putText(canvas, f"ANH: {count}/{target}", (14, 27), cv2.FONT_HERSHEY_SIMPLEX, .7, (240,240,240), 2)
    cv2.putText(canvas, status, (14, 58), cv2.FONT_HERSHEY_SIMPLEX, .65, color, 2)
    if obs is not None:
        cv2.putText(canvas, f"goc {len(obs.ids)} | Qxy {obs.quality:.1f} ({obs.quality_x:.0f}/{obs.quality_y:.0f})",
                    (14, 81), cv2.FONT_HERSHEY_SIMPLEX, .48, (180,180,180), 1)
    cv2.putText(canvas, "Q huy | ENTER tinh | SPACE force | R xoay 90 | M mirror", (12, canvas.shape[0]-8),
                cv2.FONT_HERSHEY_SIMPLEX, .45, (200,200,200), 1)
    return canvas
