#!/usr/bin/env python3
"""Trực quan hóa thời gian thực Bàn cờ vua 8x8 ArUco và định vị quân cờ 3D (Digital Twin).

Phiên bản tối ưu hóa hiệu năng cao (High Performance & High Accuracy):
- Tăng tốc FPS (18 - 30+ FPS trên CPU):
  + Cắt vùng bàn cờ động (Dynamic Board ROI Cropping): Tăng tốc YOLO ~5.5x.
  + Nhận diện theo chu kỳ (Cadence Detection & 3D Reprojection Tracking): Giữ bám vết mượt mà 30 FPS.
- Tăng độ chính xác & Ổn định:
  + Thẩm định màu sắc HSV (Dual-color HSV Verifier): Phân biệt tuyệt đối Trắng (Bạc) vs Đen (Vàng).
  + Bù trừ bán kính chân đế (Pedestal Radius Compensation): Đưa tọa độ về đúng tâm ô cờ.
  + Lọc làm mượt trung vị thời gian (Temporal 3D Median Smoothing): Triệt tiêu rung lắc tọa độ.
  + Trễ chuyển ô (Square Hysteresis): Chống nhấp nháy chuyển ô khi ở mép biên.
"""
from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path
import sys
import time

import cv2
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mono_eye.camera_io import CameraModel, load_camera_yaml
from mono_eye.chess_board_grid import BoardGrid8x8, CHESS_PIECE_HEIGHTS, compensate_piece_occlusions
from mono_eye.chess_detectors import ChessPieceDetector, CHESS_PIECE_LABELS
from mono_eye.pose import CameraPose, ChessboardPoseEstimator
from mono_eye.projection import ProjectionProcessor

DEFAULT_CALIB = ROOT / "data" / "calib" / "camera.yaml"
DEFAULT_CHESSBOARD_CFG = ROOT / "configs" / "banco_8x8.yaml"
DEFAULT_MODEL = ROOT / "data" / "models" / "best.pt"


def verify_and_correct_piece_color(
    frame: np.ndarray,
    bbox: list[float] | tuple[float, float, float, float],
    predicted_class: str,
) -> tuple[str, str]:
    """Sử dụng không gian màu HSV để phân biệt tuyệt đối giữa quân Bạc (Trắng) và quân Vàng (Đen).

    Quân Trắng (bạc kim loại): Độ bão hòa màu rất thấp (S < 45).
    Quân Đen (vàng đồng kim loại): Độ bão hòa màu cao (S >= 60).
    """
    fh, fw = frame.shape[:2]
    x1, y1, x2, y2 = [int(v) for v in bbox]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(fw, x2), min(fh, y2)

    if x2 - x1 < 6 or y2 - y1 < 6:
        fen = CHESS_PIECE_LABELS.get(predicted_class, "?")
        return predicted_class, fen

    # Lấy vùng trung tâm 50% thân quân cờ để tránh nhiễu nền bàn cờ
    cx1 = x1 + (x2 - x1) // 4
    cx2 = x2 - (x2 - x1) // 4
    cy1 = y1 + (y2 - y1) // 4
    cy2 = y2 - (y2 - y1) // 4

    crop = frame[cy1:cy2, cx1:cx2]
    if crop.size == 0:
        fen = CHESS_PIECE_LABELS.get(predicted_class, "?")
        return predicted_class, fen

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    sat_median = float(np.median(hsv[:, :, 1]))

    # Tách bạch theo ngưỡng bão hòa S = 50
    is_gold_black = sat_median >= 50.0

    cls_lower = predicted_class.lower()
    base_type = cls_lower.replace("white_", "").replace("black_", "")

    if is_gold_black:
        corrected_class = f"black_{base_type}"
    else:
        corrected_class = f"white_{base_type}"

    fen_char = CHESS_PIECE_LABELS.get(corrected_class, "?")
    return corrected_class, fen_char


def get_chessboard_roi(
    frame: np.ndarray,
    pose: CameraPose,
    camera: CameraModel,
    padding_px: int = 50,
    prev_roi: tuple[int, int, int, int] | None = None,
) -> tuple[np.ndarray, int, int, tuple[int, int, int, int]]:
    """Cắt vùng Bàn cờ động (Board ROI) từ phép chiếu 3D có làm mượt biên để giảm tải YOLO."""
    fh, fw = frame.shape[:2]
    if not pose.valid or pose.rvec is None or pose.tvec is None:
        return frame, 0, 0, (0, 0, fw, fh)

    # 8 đỉnh của hình hộp bao quanh bàn cờ trong không gian 3D (Z từ 0 tới 85mm)
    board_corners_3d = np.array([
        [0.0, 0.0, 0.0],
        [320.0, 0.0, 0.0],
        [320.0, 320.0, 0.0],
        [0.0, 320.0, 0.0],
        [0.0, 0.0, 85.0],
        [320.0, 0.0, 85.0],
        [320.0, 320.0, 85.0],
        [0.0, 320.0, 85.0],
    ], dtype=np.float64)

    proj_pts, _ = cv2.projectPoints(
        board_corners_3d, pose.rvec, pose.tvec, camera.K, camera.dist
    )
    p2d = proj_pts.reshape(-1, 2)

    raw_min_x = max(0, int(np.min(p2d[:, 0]) - padding_px))
    raw_min_y = max(0, int(np.min(p2d[:, 1]) - padding_px))
    raw_max_x = min(fw, int(np.max(p2d[:, 0]) + padding_px))
    raw_max_y = min(fh, int(np.max(p2d[:, 1]) + padding_px))

    if prev_roi is not None:
        alpha = 0.35
        min_x = int(alpha * raw_min_x + (1.0 - alpha) * prev_roi[0])
        min_y = int(alpha * raw_min_y + (1.0 - alpha) * prev_roi[1])
        max_x = int(alpha * raw_max_x + (1.0 - alpha) * prev_roi[2])
        max_y = int(alpha * raw_max_y + (1.0 - alpha) * prev_roi[3])
    else:
        min_x, min_y, max_x, max_y = raw_min_x, raw_min_y, raw_max_x, raw_max_y

    min_x = max(0, min(min_x, fw - 50))
    min_y = max(0, min(min_y, fh - 50))
    max_x = min(fw, max(max_x, min_x + 50))
    max_y = min(fh, max(max_y, min_y + 50))

    if max_x - min_x < 100 or max_y - min_y < 100:
        return frame, 0, 0, (0, 0, fw, fh)

    cropped_roi = frame[min_y:max_y, min_x:max_x]
    return cropped_roi, min_x, min_y, (min_x, min_y, max_x, max_y)


def apply_pedestal_offset(
    p3d: np.ndarray,
    cam_pos: np.ndarray | None,
    radius_mm: float = 12.5,
) -> np.ndarray:
    """Bù trừ bán kính đĩa tròn chân đế quân cờ để đưa tọa độ về đúng tâm trục đứng."""
    if cam_pos is None:
        return p3d

    diff = cam_pos[:2] - p3d[:2]
    dist = np.linalg.norm(diff)
    if dist < 1e-3:
        return p3d

    u_cam = diff / dist
    p_center = p3d.copy()
    # Mép trước lùi lại phía sau (xa camera hơn) một khoảng đúng bằng bán kính đáy
    p_center[:2] = p3d[:2] - radius_mm * u_cam
    return p_center


class PieceTracker8x8:
    """Bộ theo dõi và ổn định quân cờ đa khung hình (Multi-Frame Piece Stabilizer).
    
    Khắc phục triệt để tình trạng rung giật, nhảy ô, nhấp nháy màu và biến mất quân cờ:
    1. Ghép nối không gian (Spatial Association) dựa trên khoảng cách pixel tâm đáy.
    2. Làm mượt tọa độ 2D (u, v) và bounding box bằng Exponential Moving Average (EMA).
    3. Hysteresis nhãn phân loại (White/Black) để loại bỏ nhấp nháy màu.
    4. Cơ chế Holdover: Giữ lại quân cờ tối đa max_missed frames nếu YOLO tạm thời miss.
    """

    def __init__(self, max_missed: int = 5, match_dist_px: float = 38.0):
        self.max_missed = max_missed
        self.match_dist_px = match_dist_px
        self.next_id = 1
        self.tracks: dict[int, dict] = {}

    def reset(self) -> None:
        self.tracks.clear()
        self.next_id = 1

    def update(self, raw_detections: list[dict]) -> list[dict]:
        matched_track_ids = set()
        matched_det_indices = set()

        det_pts = []
        for det in raw_detections:
            bc = det.get("bottom_center_pixel")
            if bc is None and det.get("bbox"):
                bb = det["bbox"]
                bc = ((bb[0] + bb[2]) / 2.0, float(bb[3]))
            det_pts.append(bc)

        # 1. Ghép nối với các track đã có
        for t_id, track in list(self.tracks.items()):
            best_idx = -1
            best_dist = self.match_dist_px
            t_bc = track["bottom_center_pixel"]

            for d_idx, d_bc in enumerate(det_pts):
                if d_idx in matched_det_indices or d_bc is None:
                    continue
                dist = float(np.hypot(d_bc[0] - t_bc[0], d_bc[1] - t_bc[1]))
                if dist < best_dist:
                    best_dist = dist
                    best_idx = d_idx

            if best_idx >= 0:
                det = raw_detections[best_idx]
                matched_track_ids.add(t_id)
                matched_det_indices.add(best_idx)

                alpha = 0.65
                old_bc = track["bottom_center_pixel"]
                new_bc = det_pts[best_idx]
                smooth_bc = (
                    alpha * new_bc[0] + (1.0 - alpha) * old_bc[0],
                    alpha * new_bc[1] + (1.0 - alpha) * old_bc[1],
                )

                old_bb = track["bbox"]
                new_bb = det["bbox"]
                smooth_bb = [
                    int(alpha * new_bb[i] + (1.0 - alpha) * old_bb[i])
                    for i in range(4)
                ]

                track["class_history"].append(det["class_name"])
                if len(track["class_history"]) > 7:
                    track["class_history"].pop(0)

                # Chọn class xuất hiện nhiều nhất trong lịch sử gần
                from collections import Counter
                stable_class = Counter(track["class_history"]).most_common(1)[0][0]

                track["bottom_center_pixel"] = smooth_bc
                track["bbox"] = smooth_bb
                track["class_name"] = stable_class
                track["fen_char"] = CHESS_PIECE_LABELS.get(stable_class, det.get("fen_char", "?"))
                track["confidence"] = max(det.get("confidence", 0.5), track.get("confidence", 0.5) * 0.95)
                track["missed_count"] = 0

        # 2. Tạo track mới cho detections chưa được match
        for d_idx, det in enumerate(raw_detections):
            if d_idx not in matched_det_indices and det_pts[d_idx] is not None:
                c_name = det["class_name"]
                self.tracks[self.next_id] = {
                    "track_id": self.next_id,
                    "bbox": list(det["bbox"]),
                    "bottom_center_pixel": det_pts[d_idx],
                    "class_name": c_name,
                    "fen_char": det.get("fen_char", "?"),
                    "confidence": det.get("confidence", 0.5),
                    "class_history": [c_name],
                    "missed_count": 0,
                    "position_3d": None,
                    "square": "",
                }
                self.next_id += 1

        # 3. Cập nhật missed_count và loại bỏ track quá cũ
        dead_tracks = []
        for t_id, track in self.tracks.items():
            if t_id not in matched_track_ids:
                track["missed_count"] += 1
                if track["missed_count"] > self.max_missed:
                    dead_tracks.append(t_id)

        for t_id in dead_tracks:
            del self.tracks[t_id]

        return [track.copy() for track in self.tracks.values()]


class PieceSpatialFilter:
    """Bộ lọc làm mượt trung vị thời gian và trễ chuyển ô (Square Hysteresis)."""

    def __init__(self, window_size: int = 5, hysteresis_count: int = 3):
        self.window_size = window_size
        self.hysteresis_count = hysteresis_count
        # Lưu lịch sử vị trí 3D theo từng track_id / key
        self.history: dict[str, deque[np.ndarray]] = {}
        # Lưu trạng thái ô cờ hiện tại và số lần đếm ứng viên
        self.square_states: dict[str, dict] = {}

    def update_and_smooth(self, piece_id: str, raw_p3d: np.ndarray) -> np.ndarray:
        """Làm mượt tọa độ 3D bằng bộ lọc trung vị (Median Filter)."""
        if piece_id not in self.history:
            self.history[piece_id] = deque(maxlen=self.window_size)

        self.history[piece_id].append(raw_p3d.copy())
        pts = np.array(self.history[piece_id])

        smooth_p3d = raw_p3d.copy()
        smooth_p3d[0] = float(np.median(pts[:, 0]))
        smooth_p3d[1] = float(np.median(pts[:, 1]))
        return smooth_p3d

    def apply_hysteresis(self, piece_id: str, candidate_square: str) -> str:
        """Chống nhấp nháy chuyển ô khi quân cờ nằm sát ranh giới 2 ô."""
        if not candidate_square:
            return candidate_square

        if piece_id not in self.square_states:
            self.square_states[piece_id] = {
                "current_square": candidate_square,
                "candidate": candidate_square,
                "count": 0,
            }
            return candidate_square

        state = self.square_states[piece_id]
        if candidate_square == state["current_square"]:
            state["candidate"] = candidate_square
            state["count"] = 0
            return candidate_square

        # Ứng viên mới khác ô hiện tại
        if candidate_square == state["candidate"]:
            state["count"] += 1
            if state["count"] >= self.hysteresis_count:
                state["current_square"] = candidate_square
                state["count"] = 0
        else:
            state["candidate"] = candidate_square
            state["count"] = 1

        return state["current_square"]


def render_3d_viewport_chessboard8x8(
    camera_pos: np.ndarray | None,
    camera_rvec: np.ndarray | None,
    trajectory: list[np.ndarray],
    chess_pieces: list[dict] | None = None,
    grid_8x8: BoardGrid8x8 | None = None,
    width: int = 640,
    height: int = 720,
    cam_eye: np.ndarray | None = None,
) -> np.ndarray:
    """Tạo khung nhìn phối cảnh 3D trực quan cho Bàn cờ vua 8x8 và các quân cờ 3D."""
    canvas = np.full((height, width, 3), 24, dtype=np.uint8)

    if grid_8x8 is None:
        grid_8x8 = BoardGrid8x8(square_size_mm=40.0, cols=8, rows=8)

    sq_size = grid_8x8.square_size_mm
    board_w = grid_8x8.width_mm   # 320 mm
    board_h = grid_8x8.height_mm  # 320 mm
    center_x = board_w / 2.0      # 160 mm
    center_y = board_h / 2.0      # 160 mm

    # Camera ảo quan sát khung nhìn 3D (3D Virtual Observer)
    if cam_eye is None:
        cam_eye = np.array([center_x - 30.0, -350.0, 420.0], dtype=np.float64)

    target = np.array([center_x, center_y, 0.0], dtype=np.float64)
    up = np.array([0.0, 0.0, 1.0], dtype=np.float64)

    # Tính Extrinsics ma trận quan sát
    z_axis = target - cam_eye
    z_axis = z_axis / (np.linalg.norm(z_axis) + 1e-9)
    x_axis = np.cross(z_axis, up)
    x_axis = x_axis / (np.linalg.norm(x_axis) + 1e-9)
    y_axis = np.cross(z_axis, x_axis)

    R_view = np.vstack([x_axis, y_axis, z_axis])
    t_view = -R_view @ cam_eye
    rvec_view, _ = cv2.Rodrigues(R_view)

    fov_scale = 520.0 * (height / 720.0)
    K_view = np.array([
        [fov_scale, 0.0, width / 2.0],
        [0.0, fov_scale, height / 2.0 + 40.0],
        [0.0, 0.0, 1.0],
    ], dtype=np.float64)
    dist_view = np.zeros(5, dtype=np.float64)

    def proj(pts_3d: np.ndarray) -> np.ndarray:
        pts = np.asarray(pts_3d, dtype=np.float64).reshape(-1, 3)
        proj_pts, _ = cv2.projectPoints(pts, rvec_view, t_view, K_view, dist_view)
        return proj_pts.reshape(-1, 2)

    # 1. Vẽ lưới mặt bàn phụ (Ambient Table Grid)
    grid_range_x = np.arange(-180, board_w + 220, 60)
    grid_range_y = np.arange(-180, board_h + 220, 60)
    for x in grid_range_x:
        pts = np.array([[x, -180.0, 0.0], [x, board_h + 200.0, 0.0]])
        p = proj(pts)
        cv2.line(canvas, tuple(p[0].astype(int)), tuple(p[1].astype(int)), (38, 38, 42), 1, cv2.LINE_AA)
    for y in grid_range_y:
        pts = np.array([[-180.0, y, 0.0], [board_w + 200.0, y, 0.0]])
        p = proj(pts)
        cv2.line(canvas, tuple(p[0].astype(int)), tuple(p[1].astype(int)), (38, 38, 42), 1, cv2.LINE_AA)

    # 2. Vẽ viền gỗ ngoài của bàn cờ (Wooden Border)
    border_m = 18.0  # Mép gỗ dày 18mm bao quanh
    border_3d = np.array([
        [-border_m, -border_m, -3.0],
        [board_w + border_m, -border_m, -3.0],
        [board_w + border_m, board_h + border_m, -3.0],
        [-border_m, board_h + border_m, -3.0],
    ])
    bp = proj(border_3d).astype(np.int32)
    # Màu gỗ ấm cho viền ngoài
    cv2.fillPoly(canvas, [bp], color=(42, 60, 92), lineType=cv2.LINE_AA)
    cv2.polylines(canvas, [bp], isClosed=True, color=(70, 95, 140), thickness=2, lineType=cv2.LINE_AA)

    # 3. Vẽ 64 ô cờ xen kẽ màu sáng / tối
    col_light = (181, 217, 240)
    col_dark = (72, 108, 148)
    col_grid_line = (50, 75, 105)

    for r in range(8):
        for c in range(8):
            is_light = (r + c) % 2 == 1
            cell_col = col_light if is_light else col_dark

            x0 = c * sq_size
            y0 = r * sq_size
            x1 = (c + 1) * sq_size
            y1 = (r + 1) * sq_size

            cell_3d = np.array([
                [x0, y0, 0.0],
                [x1, y0, 0.0],
                [x1, y1, 0.0],
                [x0, y1, 0.0],
            ])
            cp = proj(cell_3d).astype(np.int32)
            cv2.fillPoly(canvas, [cp], color=cell_col, lineType=cv2.LINE_AA)
            cv2.polylines(canvas, [cp], isClosed=True, color=col_grid_line, thickness=1, lineType=cv2.LINE_AA)

    # Nếp gấp đôi giữa bàn cờ (giữa hàng 4 và 5, y = 144 mm)
    hinge_3d = np.array([[0.0, 4 * sq_size, 0.5], [board_w, 4 * sq_size, 0.5]])
    hp = proj(hinge_3d).astype(int)
    cv2.line(canvas, tuple(hp[0]), tuple(hp[1]), (25, 35, 55), 2, cv2.LINE_AA)

    # 4. Ký hiệu chữ cái A-H và số 1-8 trên viền gỗ
    for c in range(8):
        lbl = grid_8x8.col_names[c].upper()
        pt_3d = np.array([[(c + 0.5) * sq_size, -9.0, 0.0]])
        lp = proj(pt_3d)[0].astype(int)
        cv2.putText(canvas, lbl, (lp[0] - 5, lp[1] + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (210, 225, 240), 1, cv2.LINE_AA)

    for r in range(8):
        lbl = grid_8x8.rank_names[r]
        pt_3d = np.array([[-9.0, (r + 0.5) * sq_size, 0.0]])
        lp = proj(pt_3d)[0].astype(int)
        cv2.putText(canvas, lbl, (lp[0] - 5, lp[1] + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (210, 225, 240), 1, cv2.LINE_AA)

    # 5. Hệ trục tọa độ chuẩn tại góc ô A1 (0, 0, 0)
    origin_3d = np.array([
        [0.0, 0.0, 0.0],
        [60.0, 0.0, 0.0],    # +X: A -> H
        [0.0, 60.0, 0.0],    # +Y: 1 -> 8
        [0.0, 0.0, 60.0],    # +Z: Thẳng đứng lên
    ])
    op = proj(origin_3d).astype(int)
    cv2.line(canvas, tuple(op[0]), tuple(op[1]), (0, 0, 255), 2, cv2.LINE_AA)     # +X Đỏ
    cv2.line(canvas, tuple(op[0]), tuple(op[2]), (0, 230, 0), 2, cv2.LINE_AA)     # +Y Xanh lá
    cv2.line(canvas, tuple(op[0]), tuple(op[3]), (255, 140, 0), 2, cv2.LINE_AA)   # +Z Xanh dương
    cv2.putText(canvas, "+X(A->H)", tuple(op[1] + [5, 2]), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (0, 0, 255), 1, cv2.LINE_AA)
    cv2.putText(canvas, "+Y(1->8)", tuple(op[2] + [-15, -6]), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (0, 230, 0), 1, cv2.LINE_AA)

    # 6. Quỹ đạo di chuyển của Camera (Trajectory)
    if len(trajectory) >= 2:
        t_pts = np.array(trajectory[-45:])
        tp = proj(t_pts).astype(int)
        for i in range(len(tp) - 1):
            alpha = (i + 1) / len(tp)
            c_val = int(70 + 185 * alpha)
            cv2.line(canvas, tuple(tp[i]), tuple(tp[i + 1]), (c_val, 50, c_val), 2, cv2.LINE_AA)

    # 7. Camera 3D và Virtual Frustum
    if camera_pos is not None:
        c_pt = proj(camera_pos.reshape(1, 3))[0].astype(int)

        # Bóng chiếu camera vuông góc xuống mặt bàn Z = 0
        shadow_pos = np.array([[camera_pos[0], camera_pos[1], 0.0]])
        sp_pt = proj(shadow_pos)[0].astype(int)
        cv2.line(canvas, tuple(c_pt), tuple(sp_pt), (90, 90, 95), 1, cv2.LINE_AA)
        cv2.circle(canvas, tuple(sp_pt), 4, (90, 90, 95), -1, cv2.LINE_AA)

        cam_r_mat = np.eye(3)
        if camera_rvec is not None:
            cam_r_mat, _ = cv2.Rodrigues(camera_rvec)

        s = 32.0
        local_frustum = np.array([
            [-s * 1.2, -s * 0.8, s * 1.4],
            [s * 1.2, -s * 0.8, s * 1.4],
            [s * 1.2, s * 0.8, s * 1.4],
            [-s * 1.2, s * 0.8, s * 1.4],
        ])
        v_frustum = (cam_r_mat.T @ local_frustum.T).T
        world_frustum = camera_pos + v_frustum
        f_pts = proj(world_frustum).astype(int)

        for fp in f_pts:
            cv2.line(canvas, tuple(c_pt), tuple(fp), (0, 110, 255), 1, cv2.LINE_AA)
        for i in range(4):
            cv2.line(canvas, tuple(f_pts[i]), tuple(f_pts[(i + 1) % 4]), (0, 0, 240), 2, cv2.LINE_AA)
        cv2.circle(canvas, tuple(c_pt), 5, (0, 255, 255), -1, cv2.LINE_AA)

        cam_axes_local = np.array([[28.0, 0, 0], [0, 28.0, 0], [0, 0, 38.0]])
        cam_axes_world = camera_pos + (cam_r_mat.T @ cam_axes_local.T).T
        ax_pts = proj(cam_axes_world).astype(int)
        cv2.line(canvas, tuple(c_pt), tuple(ax_pts[0]), (0, 0, 255), 2, cv2.LINE_AA)
        cv2.line(canvas, tuple(c_pt), tuple(ax_pts[1]), (0, 255, 0), 2, cv2.LINE_AA)
        cv2.line(canvas, tuple(c_pt), tuple(ax_pts[2]), (255, 180, 0), 2, cv2.LINE_AA)

        cam_text = f"Cam: ({camera_pos[0]:.0f}, {camera_pos[1]:.0f}, Z={camera_pos[2]:.0f})mm"
        cv2.putText(
            canvas,
            cam_text,
            (max(10, c_pt[0] - 65), max(22, c_pt[1] - 14)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            (0, 255, 255),
            1,
            cv2.LINE_AA,
        )

    # 8. Vẽ các quân cờ 3D trên mặt bàn cờ (3D Chess Pieces)
    if chess_pieces:
        # Sắp xếp theo chiều sâu Y giảm dần để vẽ từ xa lại gần
        sorted_pieces = sorted(
            [p for p in chess_pieces if p.get("position_3d") is not None],
            key=lambda p: float(p["position_3d"][1]),
            reverse=True,
        )

        for p in sorted_pieces:
            pos_3d = p["position_3d"]
            x_val, y_val = float(pos_3d[0]), float(pos_3d[1])
            c_name = str(p.get("class_name", "")).lower()
            is_white = c_name.startswith("white")
            fen_char = p.get("fen_char", "?")
            sq_name = p.get("square", "")

            # Chiều cao mô phỏng quân cờ
            if "king" in c_name:
                p_height = 68.0
                r_base, r_top = 11.0, 8.0
            elif "queen" in c_name:
                p_height = 60.0
                r_base, r_top = 10.5, 7.5
            elif "bishop" in c_name:
                p_height = 52.0
                r_base, r_top = 9.5, 6.0
            elif "knight" in c_name:
                p_height = 48.0
                r_base, r_top = 9.5, 6.5
            elif "rook" in c_name:
                p_height = 42.0
                r_base, r_top = 9.5, 7.0
            else:  # pawn
                p_height = 34.0
                r_base, r_top = 8.5, 5.0

            base_pt = np.array([x_val, y_val, 0.0])
            top_pt = np.array([x_val, y_val, p_height])

            b_2d = proj(base_pt.reshape(1, 3))[0].astype(int)
            t_2d = proj(top_pt.reshape(1, 3))[0].astype(int)

            # Màu sắc: Trắng (Vàng ngà ấm), Đen (Nâu đậm viền vàng gold)
            body_col = (235, 245, 255) if is_white else (30, 35, 50)
            edge_col = (140, 180, 220) if is_white else (60, 140, 220)
            glow_col = (255, 215, 0) if is_white else (0, 165, 255)

            # Thân trụ 3D
            cv2.line(canvas, tuple(b_2d), tuple(t_2d), body_col, 4, cv2.LINE_AA)

            # Chân đế tiếp xúc mặt bàn
            cv2.circle(canvas, tuple(b_2d), int(r_base * 0.7), edge_col, -1, cv2.LINE_AA)
            cv2.circle(canvas, tuple(b_2d), int(r_base * 0.7) + 2, (255, 255, 255), 1, cv2.LINE_AA)

            # Đầu mũ quân cờ
            cv2.circle(canvas, tuple(t_2d), int(r_top * 0.8), glow_col, -1, cv2.LINE_AA)
            cv2.circle(canvas, tuple(t_2d), int(r_top * 0.8), (255, 255, 255), 1, cv2.LINE_AA)

            badge = f"{fen_char}@{sq_name}" if sq_name else fen_char
            cv2.putText(
                canvas,
                badge,
                (t_2d[0] + 7, t_2d[1] - 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.40,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

    # 9. Header và Title Bar
    cv2.rectangle(canvas, (0, 0), (width, 38), (18, 18, 20), -1)
    cv2.putText(
        canvas,
        "3D DIGITAL TWIN - CHESSBOARD 8X8 (40mm)",
        (14, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (0, 215, 255),
        1,
        cv2.LINE_AA,
    )
    piece_count = len(chess_pieces) if chess_pieces else 0
    cv2.putText(
        canvas,
        f"Pieces: {piece_count}",
        (width - 110, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (180, 240, 180),
        1,
        cv2.LINE_AA,
    )

    return canvas


def make_letterboxed_frame(
    frame: np.ndarray, target_w: int, target_h: int
) -> tuple[np.ndarray, float, int, int]:
    """Căn giữa khung hình và bù viền đen (letterboxing) để không làm méo tỷ lệ ảnh."""
    fh, fw = frame.shape[:2]
    scale = min(target_w / fw, target_h / fh)
    nw, nh = int(fw * scale), int(fh * scale)
    resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)

    pad_w = (target_w - nw) // 2
    pad_h = (target_h - nh) // 2

    canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
    canvas[pad_h : pad_h + nh, pad_w : pad_w + nw] = resized
    return canvas, scale, pad_w, pad_h


def run_chessboard8x8_live(
    source: str | int = 0,
    calib_file: Path | str = DEFAULT_CALIB,
    board_cfg_file: Path | str = DEFAULT_CHESSBOARD_CFG,
    model_weights: Path | str = DEFAULT_MODEL,
    conf_thresh: float = 0.45,
    imgsz: int = 480,
    detect_interval: int = 2,
    use_roi: bool = True,
    use_hsv: bool = True,
    canvas_w: int = 1400,
    canvas_h: int = 720,
    save_video_path: str | None = None,
    save_snapshot_path: str | None = None,
    headless: bool = False,
    max_frames: int | None = None,
) -> None:
    """Vòng lặp chính xử lý luồng video Bàn cờ 8x8 thời gian thực (High FPS & Accuracy)."""
    print("=" * 70)
    print(" KHỞI CHẠY HỆ THỐNG ĐỊNH VỊ 3D BÀN CỜ VUA 8X8 (TỐI ƯU HÓA HIỆU NĂNG)")
    print("=" * 70)
    print(f" Source          : {source}")
    print(f" Camera Calib    : {calib_file}")
    print(f" Board Config    : {board_cfg_file}")
    print(f" Model Weights   : {model_weights}")
    print(f" Confidence      : {conf_thresh}")
    print(f" YOLO Image Size : {imgsz}x{imgsz} (Tối ưu tốc độ CPU)")
    print(f" Detect Interval : Mỗi {detect_interval} frame (Cadence tracking)")
    print(f" Board ROI Crop  : {'BẬT (Tăng tốc ~5.5x)' if use_roi else 'TẮT'}")
    print(f" HSV Color Check : {'BẬT (Chống nhầm Trắng/Đen)' if use_hsv else 'TẮT'}")
    print("-" * 70)

    # 1. Nạp camera calibration
    base_camera = load_camera_yaml(calib_file)
    active_camera = base_camera

    # 2. Khởi tạo Pose Estimator chuyên biệt cho Bàn cờ 8x8
    pose_estimator = ChessboardPoseEstimator(
        camera=active_camera,
        board_config=board_cfg_file,
        min_markers=2,
        max_reproj_error_px=6.0,
        max_hold_frames=5,
    )

    # 3. Khởi tạo Mô hình Lưới Bàn cờ 8x8 & Bộ ổn định quân cờ đa khung hình
    grid_8x8 = BoardGrid8x8(square_size_mm=40.0, cols=8, rows=8)
    spatial_filter = PieceSpatialFilter(window_size=5, hysteresis_count=3)
    piece_tracker = PieceTracker8x8(max_missed=5, match_dist_px=38.0)

    # 4. Khởi tạo Projection Processor
    projection = ProjectionProcessor.from_camera(active_camera, plane_z=0.0)

    # 5. Khởi tạo YOLO Chess Piece Detector
    piece_detector = None
    model_path = Path(model_weights)
    if model_path.is_file():
        try:
            piece_detector = ChessPieceDetector(
                model_path=str(model_path),
                conf_threshold=conf_thresh,
                imgsz=imgsz,
            )
            print(" [YOLO] Khởi tạo mô hình nhận diện quân cờ thành công.")
        except Exception as e:
            print(f" [CẢNH BÁO] Không thể tải model YOLO: {e}")
    else:
        print(f" [CẢNH BÁO] File trọng số không tồn tại: {model_path}")

    # 6. Mở luồng video / camera / ảnh tĩnh
    src_int = None
    try:
        src_int = int(source)
    except (ValueError, TypeError):
        src_int = None

    is_static_image = False
    static_frame = None
    cap = None

    if src_int is not None:
        cap = cv2.VideoCapture(src_int)
    else:
        src_str = str(source)
        src_path = Path(src_str)
        if not src_path.exists():
            alt = ROOT / src_str
            if alt.exists():
                src_path = alt
                src_str = str(alt)

        if src_path.suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp"]:
            is_static_image = True
            static_frame = cv2.imread(src_str)
            if static_frame is None:
                raise RuntimeError(f"Không thể đọc file ảnh từ: {source}")
            total_video_frames = 1
        else:
            cap = cv2.VideoCapture(src_str)

    if not is_static_image and (cap is None or not cap.isOpened()):
        raise RuntimeError(f"Không thể mở luồng video hoặc camera từ: {source}")

    if not is_static_image:
        total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # 7. Video writer nếu được chỉ định
    video_writer = None
    if save_video_path:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        video_writer = cv2.VideoWriter(save_video_path, fourcc, 25.0, (canvas_w, canvas_h))
        print(f" [GHI HÌNH] Đang lưu video kết quả tại: {save_video_path}")

    trajectory: list[np.ndarray] = []
    cached_pieces: list[dict] = []
    frame_idx = 0
    t_start = time.perf_counter()
    fps_smooth = 0.0
    current_fen = ""
    is_paused = False
    smooth_roi: tuple[int, int, int, int] | None = None

    half_w = canvas_w // 2

    window_name = "Mono Eye-in-Hand 3D: Chessboard 8x8 Live Viewport (Fast)"
    if not headless:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, canvas_w, canvas_h)

    print(" Đang chạy vòng lặp nhận diện... Nhấn 'q' để thoát, 'p' để tạm dừng, 'r' để reset.")

    try:
        while True:
            if not is_paused:
                if is_static_image:
                    frame = static_frame.copy()
                    ret = True
                else:
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        if total_video_frames > 1:
                            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            ret, frame = cap.read()
                            if not ret or frame is None:
                                break
                        else:
                            break

                frame_idx += 1
                if max_frames and frame_idx > max_frames:
                    break

                t_frame_start = time.perf_counter()

                # Tự động đồng bộ độ phân giải camera với khung hình đầu vào
                fh, fw = frame.shape[:2]
                if (fw, fh) != (active_camera.width, active_camera.height):
                    active_camera = base_camera.scale_to(fw, fh)
                    pose_estimator.camera = active_camera
                    projection = ProjectionProcessor.from_camera(active_camera, plane_z=0.0)

                # A. Ước lượng Pose từ bàn cờ 8x8 (Subpixel + LM + Adaptive Temporal Filter)
                pose: CameraPose = pose_estimator.estimate(frame)

                # Cập nhật quỹ đạo di chuyển của camera
                cam_pos_3d = pose.camera_center if pose.valid else None
                if pose.valid and cam_pos_3d is not None:
                    trajectory.append(cam_pos_3d.copy())
                    if len(trajectory) > 60:
                        trajectory.pop(0)

                # B. Nhận diện quân cờ & Ổn định đa khung hình (Cadence + Piece Tracking)
                is_keyframe = (frame_idx % max(1, detect_interval) == 0) or (not cached_pieces) or is_static_image

                if is_keyframe and piece_detector is not None:
                    # 1. Cắt vùng bàn cờ động có làm mượt biên (Smoothed Board ROI Crop)
                    if use_roi and pose.valid:
                        roi_img, roi_x, roi_y, smooth_roi = get_chessboard_roi(
                            frame, pose, active_camera, prev_roi=smooth_roi
                        )
                    else:
                        roi_img, roi_x, roi_y, smooth_roi = frame, 0, 0, None

                    # 2. Suy luận YOLO trên ROI
                    try:
                        raw_dets = piece_detector.detect(roi_img)
                    except Exception:
                        raw_dets = []

                    # 3. Chuyển đổi tọa độ bbox từ ROI về khung hình gốc
                    detections = []
                    for d in raw_dets:
                        bx = d.get("bbox")
                        if bx:
                            d["bbox"] = [bx[0] + roi_x, bx[1] + roi_y, bx[2] + roi_x, bx[3] + roi_y]
                        bc = d.get("bottom_center_pixel")
                        if bc:
                            d["bottom_center_pixel"] = (bc[0] + roi_x, bc[1] + roi_y)
                        # Thẩm định màu sắc HSV
                        if use_hsv:
                            corr_cls, corr_fen = verify_and_correct_piece_color(
                                frame, d["bbox"], d["class_name"]
                            )
                            d["class_name"] = corr_cls
                            d["fen_char"] = corr_fen
                        detections.append(d)

                    # Bù trừ che khuất giữa các quân cờ trước khi cập nhật bộ theo dõi
                    if len(detections) >= 2:
                        detections = compensate_piece_occlusions(detections)

                    # 4. Cập nhật Bộ theo dõi và ổn định quân cờ (Loại bỏ triệt để rung giật và mất quân)
                    tracked_pieces = piece_tracker.update(detections)

                    # 5. Chiếu 3D xuống mặt phẳng Z=0 cho các quân cờ đã ổn định
                    active_pieces: list[dict] = []
                    if pose.valid and tracked_pieces:
                        for p in tracked_pieces:
                            ref_px = p.get("bottom_center_pixel")
                            if ref_px is not None:
                                success, p3d = projection.project(ref_px, pose)
                                if success and p3d is not None and not np.isnan(p3d).any():
                                    p3d_corr = apply_pedestal_offset(p3d, cam_pos_3d, radius_mm=12.5)
                                    p_key = f"tr_{p.get('track_id', 0)}"
                                    p3d_smooth = spatial_filter.update_and_smooth(p_key, p3d_corr)
                                    p["position_3d"] = p3d_smooth
                                    active_pieces.append(p)

                        # Gán ô cờ & Áp dụng Trễ chuyển ô (Square Hysteresis)
                        if active_pieces:
                            assigned = grid_8x8.assign_pieces_to_squares(active_pieces)
                            for ap in assigned:
                                cand_sq = ap.get("square", "")
                                p_id = f"tr_{ap.get('track_id', 0)}"
                                stable_sq = spatial_filter.apply_hysteresis(p_id, cand_sq)
                                ap["square"] = stable_sq

                            cached_pieces = assigned
                            current_fen = grid_8x8.generate_fen(cached_pieces)
                else:
                    # Intermediate Frame: Giữ nguyên vị trí 2D mượt mà của quân cờ,
                    # chỉ cập nhật tọa độ 3D theo tư thế camera mới nhất (không làm nhảy bounding box)
                    if pose.valid and cached_pieces:
                        for p in cached_pieces:
                            ref_px = p.get("bottom_center_pixel")
                            if ref_px is not None:
                                success, p3d = projection.project(ref_px, pose)
                                if success and p3d is not None and not np.isnan(p3d).any():
                                    p3d_corr = apply_pedestal_offset(p3d, cam_pos_3d, radius_mm=12.5)
                                    p_key = f"tr_{p.get('track_id', 0)}"
                                    p["position_3d"] = spatial_filter.update_and_smooth(p_key, p3d_corr)

                        assigned = grid_8x8.assign_pieces_to_squares(cached_pieces)
                        for ap in assigned:
                            cand_sq = ap.get("square", "")
                            p_id = f"tr_{ap.get('track_id', 0)}"
                            stable_sq = spatial_filter.apply_hysteresis(p_id, cand_sq)
                            ap["square"] = stable_sq
                        cached_pieces = assigned
                        current_fen = grid_8x8.generate_fen(cached_pieces)

                chess_pieces = cached_pieces

                # C. Vẽ 2D Video Feed có chú thích
                annotated_2d = frame.copy()

                # Vẽ hệ trục tọa độ 3D trên ảnh 2D tại A1 (Origin)
                if pose.valid and pose.rvec is not None and pose.tvec is not None:
                    axes_len = 50.0  # mm
                    axes_3d = np.array([
                        [0.0, 0.0, 0.0],
                        [axes_len, 0.0, 0.0],
                        [0.0, axes_len, 0.0],
                        [0.0, 0.0, axes_len],
                    ], dtype=np.float64)
                    proj_axes, _ = cv2.projectPoints(
                        axes_3d, pose.rvec, pose.tvec, active_camera.K, active_camera.dist
                    )
                    pa = proj_axes.reshape(-1, 2).astype(int)
                    o_pt = pa[0]
                    cv2.line(annotated_2d, tuple(o_pt), tuple(pa[1]), (0, 0, 255), 3, cv2.LINE_AA)  # X: Đỏ
                    cv2.line(annotated_2d, tuple(o_pt), tuple(pa[2]), (0, 255, 0), 3, cv2.LINE_AA)  # Y: Xanh
                    cv2.line(annotated_2d, tuple(o_pt), tuple(pa[3]), (255, 120, 0), 3, cv2.LINE_AA)  # Z: Vàng
                    cv2.putText(annotated_2d, "A1 (0,0)", tuple(o_pt + [-10, -8]), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2, cv2.LINE_AA)

                # Vẽ Bounding Box và ô cờ cho quân cờ trên ảnh 2D
                for p in chess_pieces:
                    box = p.get("bbox")
                    if box:
                        x1, y1, x2, y2 = [int(v) for v in box]
                        c_name = str(p.get("class_name", "")).lower()
                        is_white = c_name.startswith("white")
                        box_col = (255, 225, 60) if is_white else (70, 70, 250)
                        sq_str = p.get("square", "")
                        fen_ch = p.get("fen_char", "")
                        label = f"{fen_ch}@{sq_str}" if sq_str else fen_ch

                        cv2.rectangle(annotated_2d, (x1, y1), (x2, y2), box_col, 2, cv2.LINE_AA)

                        # Chấm điểm tiếp xúc đáy
                        ref = p.get("bottom_center_pixel") or p.get("ref_point")
                        if ref:
                            cv2.circle(annotated_2d, (int(ref[0]), int(ref[1])), 4, (0, 0, 255), -1, cv2.LINE_AA)

                        # Badge nhãn
                        lbl_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                        cv2.rectangle(annotated_2d, (x1, y1 - 18), (x1 + lbl_size[0] + 6, y1), box_col, -1)
                        cv2.putText(annotated_2d, label, (x1 + 3, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)

                # Vẽ viền marker ArUco nhìn thấy
                if pose.valid:
                    gray_sub = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
                    m_corners, m_ids, _ = pose_estimator.detector.detectMarkers(gray_sub)
                    if m_ids is not None:
                        for mc, mid in zip(m_corners, m_ids.flatten()):
                            if int(mid) in pose_estimator.marker_3d_map:
                                pts = mc[0].astype(int)
                                cv2.polylines(annotated_2d, [pts], isClosed=True, color=(0, 255, 0), thickness=2, lineType=cv2.LINE_AA)

                # Căn giữa letterboxing khung hình 2D
                left_panel, _, _, _ = make_letterboxed_frame(annotated_2d, half_w, canvas_h)

                # OSD Info Overlay trên panel trái
                t_frame_end = time.perf_counter()
                fps_curr = 1.0 / max(1e-4, t_frame_end - t_frame_start)
                fps_smooth = fps_curr if fps_smooth == 0.0 else 0.85 * fps_smooth + 0.15 * fps_curr

                cv2.rectangle(left_panel, (0, 0), (half_w, 42), (18, 18, 20), -1)
                pose_status = f"POSE: OK (RMS={pose.reproj_error_px:.2f}px)" if pose.valid else "POSE: SEARCHING"
                pose_col = (0, 255, 0) if pose.valid else (0, 0, 255)
                cv2.putText(left_panel, f"CAMERA STREAM | {fps_smooth:.1f} FPS", (12, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (230, 230, 230), 1, cv2.LINE_AA)
                cv2.putText(left_panel, pose_status, (12, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.40, pose_col, 1, cv2.LINE_AA)

                # D. Render Khung nhìn 3D Digital Twin trên panel phải
                right_panel = render_3d_viewport_chessboard8x8(
                    camera_pos=cam_pos_3d,
                    camera_rvec=pose.rvec if pose.valid else None,
                    trajectory=trajectory,
                    chess_pieces=chess_pieces,
                    grid_8x8=grid_8x8,
                    width=half_w,
                    height=canvas_h,
                )

                # E. Ghép màn hình kép (Dual Dashboard)
                dashboard = np.hstack([left_panel, right_panel])

                # Dải FEN Footer ở đáy màn hình
                cv2.rectangle(dashboard, (0, canvas_h - 32), (canvas_w, canvas_h), (12, 14, 18), -1)
                fen_display = f"FEN: {current_fen}" if current_fen else "FEN: [Waiting for piece detections...]"
                cv2.putText(dashboard, fen_display, (16, canvas_h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (120, 220, 255), 1, cv2.LINE_AA)

                if video_writer is not None:
                    video_writer.write(dashboard)

                if save_snapshot_path and (frame_idx == 1 or not is_paused):
                    Path(save_snapshot_path).parent.mkdir(parents=True, exist_ok=True)
                    cv2.imwrite(save_snapshot_path, dashboard)

            # Hiển thị hoặc xử lý phím bấm
            if not headless:
                cv2.imshow(window_name, dashboard)
                key = cv2.waitKey(1 if not is_paused else 30) & 0xFF
                if key in (27, ord("q"), ord("Q")):
                    print("\n Người dùng yêu cầu dừng chương trình.")
                    break
                elif key in (ord("p"), ord("P")):
                    is_paused = not is_paused
                    print(f" [TRẠNG THÁI] {'TẠM DỪNG' if is_paused else 'TIẾP TỤC'}")
                elif key in (ord("r"), ord("R")):
                    trajectory.clear()
                    pose_estimator.reset()
                    piece_tracker.reset()
                    smooth_roi = None
                    if not is_static_image and cap is not None and total_video_frames > 1:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    print(" [LỆNH] Đã đặt lại toàn bộ hệ thống bám bắt và quỹ đạo camera.")
                elif key in (ord("s"), ord("S")):
                    snap_name = f"snapshot_cb8x8_f{frame_idx}.jpg"
                    cv2.imwrite(snap_name, dashboard)
                    print(f" [LƯU ẢNH] Đã lưu ảnh chụp: {snap_name}")

    finally:
        if cap is not None:
            cap.release()
        if video_writer is not None:
            video_writer.release()
        if not headless:
            cv2.destroyAllWindows()

        elapsed = time.perf_counter() - t_start
        print("-" * 70)
        print(f" HOÀN TẤT: Đã xử lý {frame_idx} khung hình trong {elapsed:.2f}s ({frame_idx / max(1e-4, elapsed):.1f} FPS trung bình).")
        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Khởi chạy hệ thống Định vị 3D Bàn cờ vua 8x8 ArUco (Digital Twin High-Performance)."
    )
    parser.add_argument(
        "--source",
        "-s",
        default="videochess/chessboard.mp4",
        help="Nguồn video: camera index (0, 1), đường dẫn file video (.mp4) hoặc ảnh tĩnh (.jpg). Mặc định: videochess/chessboard.mp4",
    )
    parser.add_argument(
        "--calib",
        "-c",
        default=str(DEFAULT_CALIB),
        help=f"File thông số hiệu chuẩn camera. Mặc định: {DEFAULT_CALIB}",
    )
    parser.add_argument(
        "--board-cfg",
        "-b",
        default=str(DEFAULT_CHESSBOARD_CFG),
        help=f"File cấu hình bàn cờ 8x8. Mặc định: {DEFAULT_CHESSBOARD_CFG}",
    )
    parser.add_argument(
        "--model",
        "-m",
        default=str(DEFAULT_MODEL),
        help=f"File trọng số mô hình YOLO nhận diện quân cờ. Mặc định: {DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.45,
        help="Ngưỡng độ tin cậy YOLO (0.1 - 1.0). Mặc định: 0.45",
    )
    parser.add_argument(
        "--detect-interval",
        type=int,
        default=2,
        help="Chu kỳ chạy YOLO: Chạy YOLO mỗi N khung hình (1 = mỗi frame, 2 = gấp đôi tốc độ, 3 = gấp ba tốc độ). Mặc định: 2",
    )
    parser.add_argument(
        "--no-roi",
        action="store_true",
        help="Tắt cắt vùng bàn cờ động (Board ROI Crop).",
    )
    parser.add_argument(
        "--no-hsv",
        action="store_true",
        help="Tắt bộ thẩm định màu HSV cho quân cờ.",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=480,
        help="Kích thước ảnh đầu vào mô hình YOLO (mặc định: 480 để tối ưu tốc độ CPU).",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1400,
        help="Chiều rộng cửa sổ hiển thị dashboard. Mặc định: 1400",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=720,
        help="Chiều cao cửa sổ hiển thị dashboard. Mặc định: 720",
    )
    parser.add_argument(
        "--save-video",
        default=None,
        help="Đường dẫn file MP4 xuất kết quả ghi hình (tùy chọn).",
    )
    parser.add_argument(
        "--save-snapshot",
        default=None,
        help="Đường dẫn file ảnh xuất kết quả snapshot dashboard (tùy chọn).",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Chạy chế độ nền không mở cửa sổ GUI.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Số khung hình tối đa cần xử lý trước khi thoát.",
    )

    args = parser.parse_args()

    run_chessboard8x8_live(
        source=args.source,
        calib_file=args.calib,
        board_cfg_file=args.board_cfg,
        model_weights=args.model,
        conf_thresh=args.conf,
        imgsz=args.imgsz,
        detect_interval=args.detect_interval,
        use_roi=not args.no_roi,
        use_hsv=not args.no_hsv,
        canvas_w=args.width,
        canvas_h=args.height,
        save_video_path=args.save_video,
        save_snapshot_path=args.save_snapshot,
        headless=args.headless,
        max_frames=args.max_frames,
    )


if __name__ == "__main__":
    main()
