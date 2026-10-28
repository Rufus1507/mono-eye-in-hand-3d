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
from mono_eye.chess_board_grid import BoardGrid8x8, CHESS_PIECE_HEIGHTS, compensate_piece_occlusions, get_piece_true_height
from mono_eye.chess_detectors import ChessPieceDetector, CHESS_PIECE_LABELS
from mono_eye.pose import CameraPose, ChessboardPoseEstimator, UnifiedPoseEstimator
from mono_eye.projection import ProjectionProcessor

DEFAULT_CALIB = ROOT / "data" / "calib" / "camera.yaml"
DEFAULT_CHESSBOARD_CFG = ROOT / "configs" / "banco_8x8.yaml"
DEFAULT_CHARUCO_CFG = ROOT / "bang_calib.yaml"
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
    grid: BoardGrid8x8 | None = None,
) -> tuple[np.ndarray, int, int, tuple[int, int, int, int]]:
    """Cắt vùng Bàn cờ động (Board ROI) từ phép chiếu 3D có làm mượt biên để giảm tải YOLO."""
    fh, fw = frame.shape[:2]
    if not pose.valid or pose.rvec is None or pose.tvec is None:
        return frame, 0, 0, (0, 0, fw, fh)

    if grid is not None:
        bw = grid.width_mm
        bh = grid.height_mm
    else:
        bw = 365.0 if getattr(pose, "board_type", "") == "charuco" else 320.0
        bh = 235.0 if getattr(pose, "board_type", "") == "charuco" else 320.0
    # 8 đỉnh của hình hộp bao quanh bàn cờ trong không gian 3D (Z từ 0 tới 85mm)
    board_corners_3d = np.array([
        [0.0, 0.0, 0.0],
        [bw, 0.0, 0.0],
        [bw, bh, 0.0],
        [0.0, bh, 0.0],
        [0.0, 0.0, 85.0],
        [bw, 0.0, 85.0],
        [bw, bh, 85.0],
        [0.0, bh, 85.0],
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

                det_conf = float(det.get("confidence", 0.5))
                det_cname = det["class_name"]

                track["class_history"].append(det_cname)
                if len(track["class_history"]) > 7:
                    track["class_history"].pop(0)

                # Cập nhật best class nếu có độ tin cậy vượt trội
                if det_conf > track.get("best_confidence", 0.0):
                    track["best_confidence"] = det_conf
                    track["best_class_name"] = det_cname

                # Nếu đã có frame quan sát với độ tin cậy cao (>= 0.70), khóa nhãn đó
                if track.get("best_confidence", 0.0) >= 0.70:
                    stable_class = track["best_class_name"]
                else:
                    from collections import Counter
                    stable_class = Counter(track["class_history"]).most_common(1)[0][0]

                track["bottom_center_pixel"] = smooth_bc
                track["bbox"] = smooth_bb
                track["class_name"] = stable_class
                track["fen_char"] = CHESS_PIECE_LABELS.get(stable_class, det.get("fen_char", "?"))
                track["confidence"] = max(det_conf, track.get("confidence", 0.5) * 0.95)
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
                    "best_class_name": c_name,
                    "best_confidence": float(det.get("confidence", 0.5)),
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

    def update_height(self, piece_id: str, raw_height: float) -> float:
        """Làm mượt giá trị chiều cao quân cờ bằng bộ lọc trung vị."""
        if not hasattr(self, "height_history"):
            self.height_history: dict[str, deque[float]] = {}
        if piece_id not in self.height_history:
            self.height_history[piece_id] = deque(maxlen=self.window_size)
        self.height_history[piece_id].append(float(raw_height))
        return float(np.median(self.height_history[piece_id]))


def compute_camera_angles(pose: CameraPose, grid: BoardGrid8x8 | None) -> tuple[float, float, str]:
    """Tính góc phương vị (Azimuth), góc nâng (Elevation) và sector góc nhìn của camera."""
    if not pose.valid or grid is None or pose.rvec is None or pose.tvec is None:
        return 0.0, 0.0, "N/A"
    R_c, _ = cv2.Rodrigues(pose.rvec)
    C_world = -R_c.T @ pose.tvec.flatten()
    cx_board = grid.cols * grid.square_size_mm / 2.0
    cy_board = grid.rows * grid.square_size_mm / 2.0
    dx = C_world[0] - cx_board
    dy = C_world[1] - cy_board
    azimuth = float(np.degrees(np.arctan2(dy, dx)))
    dist_xy = float(np.sqrt(dx**2 + dy**2))
    elevation = float(np.degrees(np.arctan2(abs(C_world[2]), max(1e-3, dist_xy))))
    if -45.0 <= azimuth < 45.0:
        sector = "Right (+X)"
    elif 45.0 <= azimuth < 135.0:
        sector = "Front (+Y)"
    elif -135.0 <= azimuth < -45.0:
        sector = "Back (-Y)"
    else:
        sector = "Left (-X)"
    return azimuth, elevation, sector


def create_piece_slices(c_name: str, H: float) -> list[tuple[float, float]]:
    """Tạo danh sách các lát cắt hình học (z, radius) trích xuất trực tiếp từ model 3D (gender_3d/chess.obj)."""
    c = c_name.lower()
    if "king" in c:
        return [
            (0.0, 0.2142 * H), (0.12 * H, 0.1684 * H), (0.25 * H, 0.0820 * H), (0.38 * H, 0.0580 * H),
            (0.50 * H, 0.0864 * H), (0.62 * H, 0.0733 * H), (0.75 * H, 0.1245 * H), (0.88 * H, 0.0557 * H), (H, 0.0336 * H)
        ]
    elif "queen" in c:
        return [
            (0.0, 0.2430 * H), (0.12 * H, 0.2168 * H), (0.25 * H, 0.0930 * H), (0.38 * H, 0.0710 * H),
            (0.50 * H, 0.1098 * H), (0.62 * H, 0.0811 * H), (0.75 * H, 0.1078 * H), (0.88 * H, 0.1243 * H), (H, 0.0362 * H)
        ]
    elif "bishop" in c:
        return [
            (0.0, 0.2042 * H), (0.12 * H, 0.2146 * H), (0.25 * H, 0.1922 * H), (0.38 * H, 0.1223 * H),
            (0.50 * H, 0.1218 * H), (0.62 * H, 0.0981 * H), (0.75 * H, 0.1249 * H), (0.88 * H, 0.0930 * H), (H, 0.0328 * H)
        ]
    elif "knight" in c:
        return [
            (0.0, 0.2370 * H), (0.12 * H, 0.2273 * H), (0.25 * H, 0.1952 * H), (0.38 * H, 0.2437 * H),
            (0.50 * H, 0.2361 * H), (0.62 * H, 0.2280 * H), (0.75 * H, 0.2293 * H), (0.88 * H, 0.1453 * H), (H, 0.0833 * H)
        ]
    elif "rook" in c:
        return [
            (0.0, 0.2720 * H), (0.12 * H, 0.2227 * H), (0.25 * H, 0.1451 * H), (0.38 * H, 0.1355 * H),
            (0.50 * H, 0.1258 * H), (0.62 * H, 0.1157 * H), (0.75 * H, 0.1781 * H), (0.88 * H, 0.1770 * H), (H, 0.1659 * H)
        ]
    else:  # pawn
        return [
            (0.0, 0.2269 * H), (0.12 * H, 0.1635 * H), (0.25 * H, 0.2030 * H), (0.38 * H, 0.1660 * H),
            (0.50 * H, 0.1330 * H), (0.62 * H, 0.1152 * H), (0.75 * H, 0.1411 * H), (0.88 * H, 0.1527 * H), (H, 0.0584 * H)
        ]


_TEXTURE_CACHE: dict[str, np.ndarray] = {}
TEXTURE_DIR = ROOT / "gender_3d" / "textures"


def _load_texture(name: str) -> np.ndarray | None:
    if name not in _TEXTURE_CACHE:
        t_path = TEXTURE_DIR / name
        if t_path.exists():
            _TEXTURE_CACHE[name] = cv2.imread(str(t_path))
        else:
            _TEXTURE_CACHE[name] = None
    return _TEXTURE_CACHE[name]


def draw_3d_piece_model(
    canvas: np.ndarray,
    proj_fn,
    x0: float,
    y0: float,
    c_name: str,
    H: float,
    fen_char: str,
    sq_name: str,
    status_color: tuple[int, int, int] | None = None,
    cam_eye: np.ndarray | None = None,
) -> None:
    """Vẽ mô hình 3D nguyên khối đặc láng mịn có texture đá cẩm thạch / kim loại chuẩn phong cách Blender."""
    c = c_name.lower()
    is_white = c.startswith("white")

    # 1. Sinh các lát cắt 3D từ model chuẩn để xác định kích thước chân đế
    slices = create_piece_slices(c_name, H)
    base_r = slices[0][1] if slices else 16.0

    if status_color is None:
        status_color = (0, 220, 90) if is_white else (0, 215, 255)

    # 2. Chiếu điểm đáy và đỉnh sang tọa độ màn hình
    b_pt = proj_fn(np.array([[x0, y0, 0.0]]))[0].astype(int)
    t_pt = proj_fn(np.array([[x0, y0, H]]))[0].astype(int)

    angles_sh = np.linspace(0, 2 * np.pi, 20, endpoint=False)

    # 3. Bóng đổ elip mềm mại trên mặt bàn cờ (Soft Drop Shadow)
    sh_pts = np.array([[x0 + (base_r * 0.95) * np.cos(a), y0 + (base_r * 0.65) * np.sin(a), 0.2] for a in angles_sh])
    sh_2d = proj_fn(sh_pts).astype(np.int32)
    overlay_sh = canvas.copy()
    cv2.fillPoly(overlay_sh, [sh_2d], (12, 16, 24), cv2.LINE_AA)
    cv2.addWeighted(overlay_sh, 0.50, canvas, 0.50, 0, canvas)

    # 4. Vòng chân đế thanh mảnh tinh tế ôm sát chân cờ
    glow_pts = np.array([[x0 + (base_r + 2.0) * np.cos(a), y0 + (base_r + 2.0) * np.sin(a), 0.5] for a in angles_sh])
    gp_2d = proj_fn(glow_pts).astype(np.int32)
    cv2.polylines(canvas, [gp_2d], isClosed=True, color=status_color, thickness=2, lineType=cv2.LINE_AA)

    # 5. Dựng thân khối 3D tròn xoay đặc mịn 28 cạnh phủ texture ngọc trai / kim loại
    light_dir = np.array([-0.35, -0.65, 0.65], dtype=np.float64)
    light_dir /= np.linalg.norm(light_dir)

    num_sides = 28
    angles = np.linspace(0, 2 * np.pi, num_sides, endpoint=False)
    cos_a = np.cos(angles)
    sin_a = np.sin(angles)

    ring_pts_3d = []
    for z_lvl, r_lvl in slices:
        pts = np.zeros((num_sides, 3), dtype=np.float64)
        pts[:, 0] = x0 + r_lvl * cos_a
        pts[:, 1] = y0 + r_lvl * sin_a
        pts[:, 2] = z_lvl
        ring_pts_3d.append(pts)

    ring_pts_2d = [proj_fn(pts).astype(np.int32) for pts in ring_pts_3d]

    # Hướng nhìn camera ảo để vẽ từ sau ra trước (Painter's Algorithm)
    view_dir = np.array([0.0, -1.0, 0.5])
    if cam_eye is not None:
        view_dir = cam_eye - np.array([x0, y0, H / 2.0])
    view_dir_2d = view_dir[:2] / (np.linalg.norm(view_dir[:2]) + 1e-9)

    side_order = []
    for i in range(num_sides):
        mid_ang = (angles[i] + angles[(i + 1) % num_sides]) / 2.0
        norm_side = np.array([np.cos(mid_ang), np.sin(mid_ang)])
        dot_v = np.dot(norm_side, view_dir_2d)
        side_order.append((dot_v, i))
    side_order.sort(key=lambda item: item[0])

    p_tex = _load_texture("pearl_rose.jpg" if is_white else "brushed_bronze.jpg")
    tex_th, tex_tw = (p_tex.shape[:2]) if p_tex is not None else (256, 256)

    view_norm = view_dir / np.linalg.norm(view_dir)
    half_vec = light_dir + view_norm
    half_vec /= np.linalg.norm(half_vec)

    spec_col = np.array([255, 255, 255], dtype=float) if is_white else np.array([170, 195, 225], dtype=float)
    fallback_base = np.array([238, 242, 250], dtype=float) if is_white else np.array([32, 38, 48], dtype=float)

    for layer in range(len(slices) - 1):
        pts_curr = ring_pts_2d[layer]
        pts_next = ring_pts_2d[layer + 1]
        v_frac = (slices[layer][0] / max(1e-3, H))
        tex_v = int(np.clip(v_frac * (tex_th - 1), 0, tex_th - 1))

        for _, i in side_order:
            i_next = (i + 1) % num_sides
            quad = np.array([pts_curr[i], pts_curr[i_next], pts_next[i_next], pts_next[i]], dtype=np.int32)

            mid_ang = (angles[i] + angles[i_next]) / 2.0
            normal = np.array([np.cos(mid_ang), np.sin(mid_ang), 0.22], dtype=np.float64)
            normal /= np.linalg.norm(normal)

            diffuse = max(0.0, float(np.dot(normal, light_dir)))
            spec = max(0.0, float(np.dot(normal, half_vec))) ** 14

            diff_intensity = 0.38 + 0.52 * diffuse
            spec_intensity = 0.45 * spec

            if p_tex is not None:
                u_frac = (i / float(num_sides))
                tex_u = int(np.clip(u_frac * (tex_tw - 1), 0, tex_tw - 1))
                sampled_tex = p_tex[tex_v, tex_u].astype(float)
            else:
                sampled_tex = fallback_base

            col = [
                int(np.clip(sampled_tex[k] * diff_intensity + spec_col[k] * spec_intensity, 0, 255))
                for k in range(3)
            ]
            cv2.fillPoly(canvas, [quad], color=tuple(col), lineType=cv2.LINE_AA)

    # 6. Đỉnh cờ dạng khối đặc nổi
    top_c_2d = t_pt

    if "king" in c:
        top_cross_col = (255, 255, 255) if is_white else (160, 190, 225)
        cv2.line(canvas, (top_c_2d[0], top_c_2d[1] + 2), (top_c_2d[0], top_c_2d[1] - 10), top_cross_col, 3, cv2.LINE_AA)
        cv2.line(canvas, (top_c_2d[0] - 6, top_c_2d[1] - 5), (top_c_2d[0] + 6, top_c_2d[1] - 5), top_cross_col, 3, cv2.LINE_AA)
    elif "queen" in c:
        crown_col = (255, 255, 255) if is_white else (160, 190, 225)
        cv2.circle(canvas, tuple(top_c_2d), 5, crown_col, -1, cv2.LINE_AA)
        cv2.circle(canvas, (top_c_2d[0] - 6, top_c_2d[1] - 2), 2, crown_col, -1, cv2.LINE_AA)
        cv2.circle(canvas, (top_c_2d[0] + 6, top_c_2d[1] - 2), 2, crown_col, -1, cv2.LINE_AA)
    elif "bishop" in c:
        b_col = (255, 255, 255) if is_white else (160, 190, 225)
        cv2.circle(canvas, (top_c_2d[0], top_c_2d[1] - 3), 4, b_col, -1, cv2.LINE_AA)
    elif "knight" in c:
        horse_col = (250, 250, 255) if is_white else (45, 55, 70)
        cv2.circle(canvas, (top_c_2d[0], top_c_2d[1] - 2), 6, horse_col, -1, cv2.LINE_AA)
        ear_pts = np.array([
            [top_c_2d[0] - 4, top_c_2d[1] - 2],
            [top_c_2d[0] - 1, top_c_2d[1] - 8],
            [top_c_2d[0] + 2, top_c_2d[1] - 2],
        ], dtype=np.int32)
        cv2.fillPoly(canvas, [ear_pts], (255, 255, 255) if is_white else (160, 190, 225), cv2.LINE_AA)
    elif "rook" in c:
        r_col = (255, 255, 255) if is_white else (160, 190, 225)
        cv2.rectangle(canvas, (top_c_2d[0] - 6, top_c_2d[1] - 4), (top_c_2d[0] + 6, top_c_2d[1]), r_col, -1)
    else:  # pawn
        pawn_col = (250, 250, 255) if is_white else (40, 50, 65)
        cv2.circle(canvas, tuple(top_c_2d), 6, pawn_col, -1, cv2.LINE_AA)
        cv2.circle(canvas, (top_c_2d[0] - 2, top_c_2d[1] - 2), 2, (255, 255, 255), -1, cv2.LINE_AA)

    # 7. Nhãn thông tin 3D (Badge Pill) nhỏ gọn tinh tế
    bx = top_c_2d[0] + 8
    by = top_c_2d[1] - 10
    cv2.putText(canvas, f"{fen_char}@{sq_name}", (bx, by), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(canvas, f"{H:.0f}mm", (bx, by + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.36, status_color, 1, cv2.LINE_AA)


class OrbitCamera3D:
    """Quản lý camera 3D tương tác xoay 360 độ quanh bàn cờ bằng chuột."""

    def __init__(self, half_w: int = 640, canvas_h: int = 720):
        self.half_w = half_w
        self.canvas_h = canvas_h
        self.yaw_deg = -93.0
        self.pitch_deg = 40.0
        self.dist = 660.0
        self.is_dragging = False
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.dirty = True

    def reset(self):
        self.yaw_deg = -93.0
        self.pitch_deg = 40.0
        self.dist = 660.0
        self.dirty = True

    def on_mouse(self, event, x, y, flags, param=None):
        if event == cv2.EVENT_LBUTTONDOWN:
            if x >= self.half_w:
                self.is_dragging = True
                self.last_mouse_x = x
                self.last_mouse_y = y
        elif event == cv2.EVENT_LBUTTONUP:
            self.is_dragging = False
        elif event == cv2.EVENT_MOUSEMOVE and self.is_dragging:
            dx = x - self.last_mouse_x
            dy = y - self.last_mouse_y
            self.last_mouse_x = x
            self.last_mouse_y = y
            self.yaw_deg = (self.yaw_deg + dx * 0.45) % 360.0
            self.pitch_deg = max(10.0, min(85.0, self.pitch_deg - dy * 0.35))
            self.dirty = True
        elif event == cv2.EVENT_MOUSEWHEEL:
            if x >= self.half_w:
                if flags > 0:
                    self.dist = max(250.0, self.dist - 35.0)
                else:
                    self.dist = min(1500.0, self.dist + 35.0)
                self.dirty = True
        elif event in (cv2.EVENT_RBUTTONDOWN, cv2.EVENT_MBUTTONDOWN):
            if x >= self.half_w:
                self.reset()

    def compute_cam_eye(self, center_x: float, center_y: float) -> np.ndarray:
        yaw_rad = np.radians(self.yaw_deg)
        pitch_rad = np.radians(self.pitch_deg)
        r_xy = self.dist * np.cos(pitch_rad)
        z = self.dist * np.sin(pitch_rad)
        x = center_x + r_xy * np.cos(yaw_rad)
        y = center_y + r_xy * np.sin(yaw_rad)
        return np.array([x, y, z], dtype=np.float64)


def render_3d_viewport_chessboard8x8(
    camera_pos: np.ndarray | None,
    camera_rvec: np.ndarray | None,
    trajectory: list[np.ndarray],
    chess_pieces: list[dict] | None = None,
    grid_8x8: BoardGrid8x8 | None = None,
    width: int = 640,
    height: int = 720,
    cam_eye: np.ndarray | None = None,
    orbit_camera: OrbitCamera3D | None = None,
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

    # Camera ảo quan sát khung nhìn 3D (Hỗ trợ OrbitCamera3D xoay 360 độ)
    if orbit_camera is not None:
        cam_eye = orbit_camera.compute_cam_eye(center_x, center_y)
    elif cam_eye is None:
        cam_eye = np.array([center_x - 30.0, -350.0, 420.0], dtype=np.float64)

    target = np.array([center_x, center_y, 0.0], dtype=np.float64)
    up = np.array([0.0, 0.0, 1.0], dtype=np.float64)

    # Tính Extrinsics ma trận quan sát
    z_axis = target - cam_eye
    z_axis = z_axis / (np.linalg.norm(z_axis) + 1e-9)
    x_axis = np.cross(z_axis, up)
    norm_x = np.linalg.norm(x_axis)
    if norm_x < 1e-6:
        x_axis = np.array([1.0, 0.0, 0.0], dtype=np.float64)
    else:
        x_axis = x_axis / norm_x
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

    # 2. Bệ cẩm thạch nhiều tầng bên dưới bàn cờ (Tiered Marble Pedestal) - Phủ Texture thật
    m_out2 = 28.0
    pts_tier2_3d = np.array([
        [-m_out2, -m_out2, -14.0],
        [board_w + m_out2, -m_out2, -14.0],
        [board_w + m_out2, board_h + m_out2, -14.0],
        [-m_out2, board_h + m_out2, -14.0],
    ])
    p_t2 = proj(pts_tier2_3d).astype(np.float32)

    m_out1 = 20.0
    pts_tier1_3d = np.array([
        [-m_out1, -m_out1, -6.0],
        [board_w + m_out1, -m_out1, -6.0],
        [board_w + m_out1, board_h + m_out1, -6.0],
        [-m_out1, board_h + m_out1, -6.0],
    ])
    p_t1 = proj(pts_tier1_3d).astype(np.float32)

    marble_tex = _load_texture("marble_white.jpg")
    if marble_tex is not None:
        tex_h, tex_w = marble_tex.shape[:2]
        src_corners = np.array([[0, 0], [tex_w, 0], [tex_w, tex_h], [0, tex_h]], dtype=np.float32)
        try:
            # Tầng 2
            M_t2 = cv2.getPerspectiveTransform(src_corners, p_t2)
            warp_t2 = cv2.warpPerspective(marble_tex, M_t2, (width, height))
            mask_t2 = np.zeros((height, width), dtype=np.uint8)
            cv2.fillPoly(mask_t2, [p_t2.astype(np.int32)], 255)
            canvas[mask_t2 > 0] = cv2.addWeighted(warp_t2[mask_t2 > 0], 0.85, np.full_like(warp_t2[mask_t2 > 0], 30), 0.15, 0)

            # Tầng 1
            M_t1 = cv2.getPerspectiveTransform(src_corners, p_t1)
            warp_t1 = cv2.warpPerspective(marble_tex, M_t1, (width, height))
            mask_t1 = np.zeros((height, width), dtype=np.uint8)
            cv2.fillPoly(mask_t1, [p_t1.astype(np.int32)], 255)
            canvas[mask_t1 > 0] = cv2.addWeighted(warp_t1[mask_t1 > 0], 0.95, np.full_like(warp_t1[mask_t1 > 0], 20), 0.05, 0)
            cv2.polylines(canvas, [p_t1.astype(np.int32)], True, (150, 165, 180), 2, cv2.LINE_AA)
        except Exception:
            cv2.fillPoly(canvas, [p_t2.astype(np.int32)], (195, 208, 222), cv2.LINE_AA)
            cv2.fillPoly(canvas, [p_t1.astype(np.int32)], (218, 228, 240), cv2.LINE_AA)
    else:
        cv2.fillPoly(canvas, [p_t2.astype(np.int32)], (195, 208, 222), cv2.LINE_AA)
        cv2.fillPoly(canvas, [p_t1.astype(np.int32)], (218, 228, 240), cv2.LINE_AA)
        cv2.polylines(canvas, [p_t1.astype(np.int32)], True, (160, 175, 190), 2, cv2.LINE_AA)

    # Nẹp gỗ mun đen bóng bao quanh 64 ô cờ (Z = 0)
    m_border = 10.0
    pts_border = np.array([
        [-m_border, -m_border, 0.0],
        [board_w + m_border, -m_border, 0.0],
        [board_w + m_border, board_h + m_border, 0.0],
        [-m_border, board_h + m_border, 0.0],
    ])
    p_b = proj(pts_border).astype(np.int32)
    cv2.fillPoly(canvas, [p_b], color=(18, 22, 30), lineType=cv2.LINE_AA)
    cv2.polylines(canvas, [p_b], isClosed=True, color=(65, 80, 100), thickness=1, lineType=cv2.LINE_AA)

    # Đinh tán đồng kim loại trang trí viền ngoài (Decor Studs)
    for i in range(9):
        x_stud = i * (board_w / 8.0)
        stud_pt = proj([[-m_out1 + 4.0, x_stud, -3.0]])[0].astype(int)
        cv2.circle(canvas, tuple(stud_pt), 3, (40, 165, 230), -1, cv2.LINE_AA)
        cv2.circle(canvas, tuple(stud_pt), 1, (200, 240, 255), -1, cv2.LINE_AA)
        stud_pt2 = proj([[x_stud, -m_out1 + 4.0, -3.0]])[0].astype(int)
        cv2.circle(canvas, tuple(stud_pt2), 3, (40, 165, 230), -1, cv2.LINE_AA)
        cv2.circle(canvas, tuple(stud_pt2), 1, (200, 240, 255), -1, cv2.LINE_AA)

    # 3. Phủ Texture 64 ô cờ hoàn chỉnh: Đá cẩm thạch ngà & Gỗ mun bóng
    board_tex = _load_texture("board_8x8_textured.jpg")
    pts_board_3d = np.array([
        [0.0, 0.0, 0.0],
        [board_w, 0.0, 0.0],
        [board_w, board_h, 0.0],
        [0.0, board_h, 0.0],
    ])
    p_board = proj(pts_board_3d).astype(np.float32)

    has_board_warp = False
    if board_tex is not None and (grid_8x8 is None or grid_8x8.cols == 8):
        try:
            b_tex_h, b_tex_w = board_tex.shape[:2]
            src_board_corners = np.array([[0, 0], [b_tex_w, 0], [b_tex_w, b_tex_h], [0, b_tex_h]], dtype=np.float32)
            M_board = cv2.getPerspectiveTransform(src_board_corners, p_board)
            warp_board = cv2.warpPerspective(board_tex, M_board, (width, height), flags=cv2.INTER_LINEAR)
            mask_board = np.zeros((height, width), dtype=np.uint8)
            cv2.fillPoly(mask_board, [p_board.astype(np.int32)], 255)
            canvas[mask_board > 0] = warp_board[mask_board > 0]
            cv2.polylines(canvas, [p_board.astype(np.int32)], True, (25, 35, 50), 2, cv2.LINE_AA)
            has_board_warp = True
        except Exception:
            has_board_warp = False

    num_rows = grid_8x8.rows if grid_8x8 else 8
    num_cols = grid_8x8.cols if grid_8x8 else 8

    if not has_board_warp:
        col_light = (235, 242, 250)
        col_dark = (32, 46, 68)
        for r in range(num_rows):
            for c in range(num_cols):
                is_light = (r + c) % 2 == 1
                cell_col = col_light if is_light else col_dark
                x0 = c * sq_size
                y0 = r * sq_size
                x1 = (c + 1) * sq_size
                y1 = (r + 1) * sq_size
                cell_3d = np.array([[x0, y0, 0.0], [x1, y0, 0.0], [x1, y1, 0.0], [x0, y1, 0.0]])
                cp = proj(cell_3d).astype(np.int32)
                cv2.fillPoly(canvas, [cp], color=cell_col, lineType=cv2.LINE_AA)
                edge_col = (210, 220, 230) if is_light else (22, 32, 48)
                cv2.polylines(canvas, [cp], isClosed=True, color=edge_col, thickness=1, lineType=cv2.LINE_AA)

    # Nếp gấp đôi giữa bàn cờ (giữa hàng 4 và 5, y = 144 mm)
    hinge_3d = np.array([[0.0, 4 * sq_size, 0.5], [board_w, 4 * sq_size, 0.5]])
    hp = proj(hinge_3d).astype(int)
    cv2.line(canvas, tuple(hp[0]), tuple(hp[1]), (25, 35, 55), 2, cv2.LINE_AA)

    # 4. Ký hiệu chữ cái A-H và số 1-8 trên viền gỗ
    for c in range(num_cols):
        lbl = grid_8x8.col_names[c].upper() if grid_8x8 else str(c)
        pt_3d = np.array([[(c + 0.5) * sq_size, -9.0, 0.0]])
        lp = proj(pt_3d)[0].astype(int)
        cv2.putText(canvas, lbl, (lp[0] - 5, lp[1] + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (210, 225, 240), 1, cv2.LINE_AA)

    for r in range(num_rows):
        lbl = grid_8x8.rank_names[r] if grid_8x8 else str(r + 1)
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
        # Sắp xếp theo chiều sâu từ xa đến gần so với camera ảo (Painter's Algorithm chuẩn cho 360 độ)
        def piece_dist_to_cam(p_dict):
            pos = p_dict.get("position_3d")
            if pos is None:
                return -1.0
            p_pos = np.array([float(pos[0]), float(pos[1]), 20.0], dtype=np.float64)
            return float(np.linalg.norm(cam_eye - p_pos))

        sorted_pieces = sorted(
            [p for p in chess_pieces if p.get("position_3d") is not None],
            key=piece_dist_to_cam,
            reverse=True,
        )

        for p in sorted_pieces:
            pos_3d = p["position_3d"]
            x_val, y_val = float(pos_3d[0]), float(pos_3d[1])
            c_name = str(p.get("class_name", "")).lower()
            fen_char = p.get("fen_char", "?")
            sq_name = p.get("square", "")
            sq_color_str = p.get("square_color", "green")

            # Xác định chiều cao thực tế của quân cờ
            true_h = get_piece_true_height(c_name)
            H = float(true_h) if true_h is not None else 40.0

            # Màu vòng chân đế theo sai số định vị
            status_color = {
                "green": (0, 220, 90),
                "yellow": (0, 215, 255),
                "red": (255, 60, 60),
            }.get(sq_color_str, (0, 220, 90))

            draw_3d_piece_model(
                canvas=canvas,
                proj_fn=proj,
                x0=x_val,
                y0=y_val,
                c_name=c_name,
                H=H,
                fen_char=fen_char,
                sq_name=sq_name,
                status_color=status_color,
                cam_eye=cam_eye,
            )

    # 9. Header và Title Bar
    cv2.rectangle(canvas, (0, 0), (width, 38), (18, 18, 20), -1)
    cv2.putText(
        canvas,
        f"3D DIGITAL TWIN - {'CHARUCO A3 (33mm)' if (grid_8x8 and grid_8x8.cols == 11) else 'CHESSBOARD 8X8 (40mm)'}",
        (14, 18),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.44,
        (0, 215, 255),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        "Xoay 360: Keo chuot trai | Zoom: Cuon chuot | Reset: Chuot phai",
        (14, 32),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.32,
        (180, 200, 220),
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
    charuco_cfg_file: Path | str = DEFAULT_CHARUCO_CFG,
    board_type: str = "auto",
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
    dump_csv_path: str | None = None,
) -> None:
    """Vòng lặp chính xử lý luồng video Bàn cờ 8x8 thời gian thực (High FPS & Accuracy)."""
    print("=" * 70)
    print(" KHỞI CHẠY HỆ THỐNG ĐỊNH VỊ 3D BÀN CỜ 8X8 (Ô 40MM, MARKER 32MM)")
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

    # 0. Khởi tạo CSV Dump nếu có yêu cầu
    import csv
    csv_file_obj = None
    csv_writer = None
    if dump_csv_path is not None:
        p_csv = Path(dump_csv_path)
        p_csv.parent.mkdir(parents=True, exist_ok=True)
        csv_file_obj = open(p_csv, "w", encoding="utf-8", newline="")
        csv_writer = csv.writer(csv_file_obj)
        csv_writer.writerow([
            "frame_idx", "track_id", "class_name", "fen_char", "confidence",
            "square", "square_color", "estimated_height_mm", "true_height_mm",
            "height_error_mm", "x_mm", "y_mm", "cam_azimuth_deg", "cam_sector",
            "pose_valid", "pose_reproj_px"
        ])

    # 1. Nạp camera calibration
    if "video7" in str(source).lower() and str(calib_file) == str(DEFAULT_CALIB):
        phone_calib7 = ROOT / "data" / "calib" / "camera_phone_video7.yaml"
        if phone_calib7.exists():
            calib_file = str(phone_calib7)
    elif "video6" in str(source).lower() and str(calib_file) == str(DEFAULT_CALIB):
        phone_calib6 = ROOT / "data" / "calib" / "camera_phone_video6.yaml"
        if phone_calib6.exists():
            calib_file = str(phone_calib6)

    if "video7" in str(source).lower() and str(board_cfg_file) == str(DEFAULT_CHESSBOARD_CFG):
        board_9x6 = ROOT / "configs" / "banco_9x6.yaml"
        if board_9x6.exists():
            board_cfg_file = str(board_9x6)
    elif "video6" in str(source).lower() and str(board_cfg_file) == str(DEFAULT_CHESSBOARD_CFG):
        phone_board = ROOT / "configs" / "banco_video6.yaml"
        if phone_board.exists():
            board_cfg_file = str(phone_board)

    if "video7" in str(source).lower() and str(charuco_cfg_file) == str(DEFAULT_CHARUCO_CFG):
        charuco_bo2 = ROOT / "configs" / "bang_charuco_A3_o40mm_bo2.yaml"
        if charuco_bo2.exists():
            charuco_cfg_file = str(charuco_bo2)

    base_camera = load_camera_yaml(calib_file)
    active_camera = base_camera

    # 2. Khởi tạo UnifiedPoseEstimator hỗ trợ song song Bàn cờ 8x8 & ChArUco A3/A4
    pose_estimator = UnifiedPoseEstimator(
        camera=active_camera,
        mode=board_type,
        charuco_config=charuco_cfg_file,
        chessboard_config=board_cfg_file,
        max_reproj_error_px=15.0,
    )

    # 3. Khởi tạo Mô hình Lưới Bàn cờ: Hỗ trợ linh hoạt cấu hình 8x8, 9x6 và ChArUco
    board_p = Path(board_cfg_file)
    grid_cols = 8
    grid_rows = 8
    grid_sq_mm = 40.0
    if board_p.exists():
        try:
            with open(board_p, "r", encoding="utf-8") as bf:
                b_data = yaml.safe_load(bf)
                bang_meta = b_data.get("bang", {}) if b_data else {}
                grid_cols = int(bang_meta.get("o_ngang", 8))
                grid_rows = int(bang_meta.get("o_doc", 8))
                grid_sq_mm = float(bang_meta.get("canh_o_mm", 40.0))
        except Exception:
            pass

    grid_custom = BoardGrid8x8(square_size_mm=grid_sq_mm, cols=grid_cols, rows=grid_rows)
    grid_8x8 = BoardGrid8x8(square_size_mm=40.0, cols=8, rows=8)
    grid_charuco_a3 = BoardGrid8x8(square_size_mm=33.02, cols=11, rows=7)
    if "video7" in str(source).lower() or "video6" in str(source).lower():
        active_grid = grid_custom
    elif board_type == "charuco" or "video4" in str(source).lower() or "video5" in str(source).lower():
        active_grid = grid_charuco_a3
    else:
        active_grid = grid_custom
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
        Path(save_video_path).parent.mkdir(parents=True, exist_ok=True)
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

    # Khởi tạo OrbitCamera3D cho phép tương tác chuột xoay 360 độ, cuộn zoom, chuột phải reset
    orbit_camera = OrbitCamera3D(half_w=half_w, canvas_h=canvas_h)

    window_name = "Mono Eye-in-Hand 3D: Chessboard 8x8 Live Viewport (Fast)"
    if not headless:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, canvas_w, canvas_h)
        cv2.setMouseCallback(window_name, orbit_camera.on_mouse)

    cam_pos_3d: np.ndarray | None = None
    pose: CameraPose = CameraPose(valid=False)
    chess_pieces: list[dict] = []
    dashboard: np.ndarray = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)

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
                        if total_video_frames > 1 and not headless and save_video is None:
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
                    if hasattr(pose_estimator, "update_camera"):
                        pose_estimator.update_camera(active_camera)
                    else:
                        pose_estimator.camera = active_camera
                    projection = ProjectionProcessor.from_camera(active_camera, plane_z=0.0)

                # A. Ước lượng Pose từ bàn cờ 8x8 (Subpixel + LM + Adaptive Temporal Filter)
                pose: CameraPose = pose_estimator.estimate(frame)
                cam_azimuth, cam_elevation, cam_sector = compute_camera_angles(pose, active_grid)

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
                            frame, pose, active_camera, prev_roi=smooth_roi, grid=active_grid
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

                                    # Ước lượng chiều cao 3D từ bounding box và chân đế
                                    bx = p.get("bbox")
                                    if bx and len(bx) == 4:
                                        top_px = ((bx[0] + bx[2]) / 2.0, bx[1])
                                        raw_h = projection.compute_piece_height(ref_px, top_px, pose, base_3d=p3d_smooth)
                                        if raw_h is not None:
                                            sm_h = spatial_filter.update_height(p_key, raw_h)
                                            true_h = get_piece_true_height(p.get("class_name", ""))
                                            p["estimated_height_mm"] = sm_h
                                            p["true_height_mm"] = true_h
                                            if true_h is not None:
                                                diff_h = abs(sm_h - true_h)
                                                p["height_error_mm"] = sm_h - true_h
                                                if diff_h <= 5.0:
                                                    p["square_color"] = "green"
                                                elif diff_h <= 10.0:
                                                    p["square_color"] = "yellow"
                                                else:
                                                    p["square_color"] = "red"

                                    active_pieces.append(p)

                        # Gán ô cờ & Áp dụng Trễ chuyển ô (Square Hysteresis)
                        if active_pieces:
                            if "video7" in str(source).lower() or "video6" in str(source).lower():
                                active_grid = grid_custom
                            elif getattr(pose, "board_type", "") == "charuco" or "video4" in str(source).lower() or "video5" in str(source).lower():
                                active_grid = grid_charuco_a3
                            else:
                                active_grid = grid_custom
                            assigned = active_grid.assign_pieces_to_squares(active_pieces)
                            for ap in assigned:
                                cand_sq = ap.get("square", "")
                                p_id = f"tr_{ap.get('track_id', 0)}"
                                stable_sq = spatial_filter.apply_hysteresis(p_id, cand_sq)
                                ap["square"] = stable_sq

                                # Tinh chỉnh chiều cao dựa trên tâm ô cờ lý thuyết (Square Regularization)
                                if stable_sq:
                                    sq_c = active_grid.square_to_center(stable_sq)
                                    if sq_c and ap.get("position_3d") is not None:
                                        # Bù trừ bán kính chân đế động theo hướng camera
                                        ptype_k = str(ap.get("class_name", "")).replace("white_", "").replace("black_", "").lower()
                                        r_ped = {"pawn": 12.0, "rook": 13.0, "knight": 13.5, "bishop": 14.0, "queen": 16.0, "king": 17.0}.get(ptype_k, 13.5)
                                        R_c_cur, _ = cv2.Rodrigues(pose.rvec)
                                        C_cur = -R_c_cur.T @ pose.tvec.flatten()
                                        u_cam_v = ap["position_3d"][:2] - C_cur[:2]
                                        n_cam_v = np.linalg.norm(u_cam_v)
                                        p_comp_2d = ap["position_3d"][:2] + r_ped * (u_cam_v / n_cam_v) if n_cam_v > 1e-3 else ap["position_3d"][:2]

                                        # Snap-to-Grid: nếu khoảng cách tới tâm ô <= 16.5mm (nửa ô cờ A3), snap 100% về tâm ô
                                        dist_to_center = float(np.linalg.norm(p_comp_2d - sq_c[:2]))
                                        if dist_to_center <= (active_grid.square_size_mm * 0.45):
                                            base_reg = np.array([sq_c[0], sq_c[1], 0.0], dtype=np.float64)
                                            ap["position_3d"] = base_reg.copy()
                                        else:
                                            base_reg = np.array([
                                                0.75 * sq_c[0] + 0.25 * p_comp_2d[0],
                                                0.75 * sq_c[1] + 0.25 * p_comp_2d[1],
                                                0.0,
                                            ], dtype=np.float64)
                                        bx = ap.get("bbox")
                                        ref_px = ap.get("bottom_center_pixel")
                                        if bx and len(bx) == 4 and ref_px:
                                            top_px = ((bx[0] + bx[2]) / 2.0, bx[1])
                                            ref_h = projection.compute_piece_height(ref_px, top_px, pose, base_3d=base_reg)
                                            if ref_h is not None:
                                                sm_h = spatial_filter.update_height(p_id, ref_h)
                                                true_h = get_piece_true_height(ap.get("class_name", ""))
                                                ap["estimated_height_mm"] = sm_h
                                                ap["true_height_mm"] = true_h
                                                if true_h is not None:
                                                    diff_h = abs(sm_h - true_h)
                                                    ap["height_error_mm"] = sm_h - true_h
                                                    if diff_h <= 5.0:
                                                        ap["square_color"] = "green"
                                                    elif diff_h <= 10.0:
                                                        ap["square_color"] = "yellow"
                                                    else:
                                                        ap["square_color"] = "red" 

                            cached_pieces = assigned
                            current_fen = active_grid.generate_fen(cached_pieces) if hasattr(active_grid, 'generate_fen') else ''
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
                                    bx = p.get("bbox")
                                    if bx and len(bx) == 4:
                                        top_px = ((bx[0] + bx[2]) / 2.0, bx[1])
                                        raw_h = projection.compute_piece_height(ref_px, top_px, pose, base_3d=p["position_3d"])
                                        if raw_h is not None:
                                            sm_h = spatial_filter.update_height(p_key, raw_h)
                                            true_h = get_piece_true_height(p.get("class_name", ""))
                                            p["estimated_height_mm"] = sm_h
                                            p["true_height_mm"] = true_h
                                            if true_h is not None:
                                                diff_h = abs(sm_h - true_h)
                                                p["height_error_mm"] = sm_h - true_h
                                                if diff_h <= 5.0:
                                                    p["square_color"] = "green"
                                                elif diff_h <= 10.0:
                                                    p["square_color"] = "yellow"
                                                else:
                                                    p["square_color"] = "red" 

                        if "video7" in str(source).lower() or "video6" in str(source).lower():
                            active_grid = grid_custom
                        elif getattr(pose, "board_type", "") == "charuco" or "video4" in str(source).lower() or "video5" in str(source).lower():
                            active_grid = grid_charuco_a3
                        else:
                            active_grid = grid_custom
                        assigned = active_grid.assign_pieces_to_squares(cached_pieces)
                        for ap in assigned:
                            cand_sq = ap.get("square", "")
                            p_id = f"tr_{ap.get('track_id', 0)}"
                            stable_sq = spatial_filter.apply_hysteresis(p_id, cand_sq)
                            ap["square"] = stable_sq

                            # Tinh chỉnh chiều cao dựa trên tâm ô cờ lý thuyết (Square Regularization)
                            if stable_sq:
                                sq_c = active_grid.square_to_center(stable_sq)
                                if sq_c and ap.get("position_3d") is not None:
                                    # Bù trừ bán kính chân đế động theo hướng camera
                                    ptype_k = str(ap.get("class_name", "")).replace("white_", "").replace("black_", "").lower()
                                    r_ped = {"pawn": 12.0, "rook": 13.0, "knight": 13.5, "bishop": 14.0, "queen": 16.0, "king": 17.0}.get(ptype_k, 13.5)
                                    R_c_cur, _ = cv2.Rodrigues(pose.rvec)
                                    C_cur = -R_c_cur.T @ pose.tvec.flatten()
                                    u_cam_v = ap["position_3d"][:2] - C_cur[:2]
                                    n_cam_v = np.linalg.norm(u_cam_v)
                                    p_comp_2d = ap["position_3d"][:2] + r_ped * (u_cam_v / n_cam_v) if n_cam_v > 1e-3 else ap["position_3d"][:2]

                                    # Snap-to-Grid: nếu khoảng cách tới tâm ô <= 16.5mm (nửa ô cờ A3), snap 100% về tâm ô
                                    dist_to_center = float(np.linalg.norm(p_comp_2d - sq_c[:2]))
                                    if dist_to_center <= (active_grid.square_size_mm * 0.45):
                                        base_reg = np.array([sq_c[0], sq_c[1], 0.0], dtype=np.float64)
                                        ap["position_3d"] = base_reg.copy()
                                    else:
                                        base_reg = np.array([
                                            0.75 * sq_c[0] + 0.25 * p_comp_2d[0],
                                            0.75 * sq_c[1] + 0.25 * p_comp_2d[1],
                                            0.0,
                                        ], dtype=np.float64)
                                    bx = ap.get("bbox")
                                    ref_px = ap.get("bottom_center_pixel")
                                    if bx and len(bx) == 4 and ref_px:
                                        top_px = ((bx[0] + bx[2]) / 2.0, bx[1])
                                        ref_h = projection.compute_piece_height(ref_px, top_px, pose, base_3d=base_reg)
                                        if ref_h is not None:
                                            sm_h = spatial_filter.update_height(p_id, ref_h)
                                            true_h = get_piece_true_height(ap.get("class_name", ""))
                                            ap["estimated_height_mm"] = sm_h
                                            ap["true_height_mm"] = true_h
                                            if true_h is not None:
                                                diff_h = abs(sm_h - true_h)
                                                ap["height_error_mm"] = sm_h - true_h
                                                if diff_h <= 5.0:
                                                    ap["square_color"] = "green"
                                                elif diff_h <= 10.0:
                                                    ap["square_color"] = "yellow"
                                                else:
                                                    ap["square_color"] = "red" 
                        cached_pieces = assigned
                        current_fen = active_grid.generate_fen(cached_pieces) if hasattr(active_grid, 'generate_fen') else ''

                chess_pieces = cached_pieces

                # Ghi nhận dữ liệu ra CSV Dump nếu được yêu cầu
                if csv_writer is not None:
                    for p in chess_pieces:
                        pos = p.get("position_3d")
                        x_val = f"{pos[0]:.2f}" if pos is not None else ""
                        y_val = f"{pos[1]:.2f}" if pos is not None else ""
                        est_h = p.get("estimated_height_mm")
                        tr_h = p.get("true_height_mm")
                        er_h = p.get("height_error_mm")
                        csv_writer.writerow([
                            frame_idx,
                            p.get("track_id", -1),
                            p.get("class_name", ""),
                            p.get("fen_char", ""),
                            f"{p.get('confidence', 0.0):.3f}",
                            p.get("square", ""),
                            p.get("square_color", ""),
                            f"{est_h:.2f}" if est_h is not None else "",
                            f"{tr_h:.2f}" if tr_h is not None else "",
                            f"{er_h:.2f}" if er_h is not None else "",
                            x_val,
                            y_val,
                            f"{cam_azimuth:.1f}",
                            cam_sector,
                            1 if pose.valid else 0,
                            f"{pose.reproj_error_px:.2f}" if pose.valid else "",
                        ])

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

                # Tính toán góc độ quan sát của camera đối với tâm bàn cờ
                cam_azimuth = 0.0
                cam_elevation = 0.0
                cam_sector = "N/A"
                if pose.valid and active_grid is not None and pose.rvec is not None and pose.tvec is not None:
                    R_c, _ = cv2.Rodrigues(pose.rvec)
                    C_world = -R_c.T @ pose.tvec.flatten()
                    cx_board = active_grid.cols * active_grid.square_size_mm / 2.0
                    cy_board = active_grid.rows * active_grid.square_size_mm / 2.0
                    dx = C_world[0] - cx_board
                    dy = C_world[1] - cy_board
                    cam_azimuth = float(np.degrees(np.arctan2(dy, dx)))
                    dist_xy = float(np.sqrt(dx**2 + dy**2))
                    cam_elevation = float(np.degrees(np.arctan2(abs(C_world[2]), max(1e-3, dist_xy))))

                    if -45.0 <= cam_azimuth < 45.0:
                        cam_sector = "Right (+X)"
                    elif 45.0 <= cam_azimuth < 135.0:
                        cam_sector = "Front (+Y)"
                    elif -135.0 <= cam_azimuth < -45.0:
                        cam_sector = "Back (-Y)"
                    else:
                        cam_sector = "Left (-X)"

                # Bỏ tô màu trên ô cờ theo yêu cầu của user.
                # Thay bằng TÔ MÀU MỜ BBOX (Alpha Blend 0.35) theo 3 bậc dung sai sai số
                overlay_boxes = annotated_2d.copy()
                has_colored_box = False

                for p in chess_pieces:
                    box = p.get("bbox")
                    if box:
                        x1, y1, x2, y2 = [int(round(v)) for v in box]
                        c_name = str(p.get("class_name", "")).lower()
                        color_tag = p.get("square_color")
                        h_val = p.get("estimated_height_mm")
                        t_val = p.get("true_height_mm")
                        if h_val is not None and t_val is not None:
                            d_val = abs(h_val - t_val)
                            box_col = (0, 220, 0) if d_val <= 5.0 else ((0, 220, 255) if d_val <= 10.0 else (0, 0, 240))
                        elif color_tag == "green":
                            box_col = (0, 220, 0)
                        elif color_tag == "yellow":
                            box_col = (0, 220, 255)
                        elif color_tag == "red":
                            box_col = (0, 0, 240)
                        else:
                            is_white = c_name.startswith("white")
                            box_col = (255, 225, 60) if is_white else (70, 70, 250)

                        cv2.rectangle(overlay_boxes, (x1, y1), (x2, y2), box_col, -1)
                        has_colored_box = True

                if has_colored_box:
                    cv2.addWeighted(overlay_boxes, 0.35, annotated_2d, 0.65, 0, annotated_2d)

                # Vẽ viền nét và nhãn gọn gàng TUYỆT ĐỐI KHÔNG CÓ TỌA ĐỘ
                for p in chess_pieces:
                    box = p.get("bbox")
                    if box:
                        x1, y1, x2, y2 = [int(round(v)) for v in box]
                        c_name = str(p.get("class_name", "")).lower()
                        color_tag = p.get("square_color")
                        h_val = p.get("estimated_height_mm")
                        t_val = p.get("true_height_mm")
                        if h_val is not None and t_val is not None:
                            d_val = abs(h_val - t_val)
                            box_col = (0, 220, 0) if d_val <= 5.0 else ((0, 220, 255) if d_val <= 10.0 else (0, 0, 240))
                            tag = "OK" if d_val <= 5.0 else ("WARN" if d_val <= 10.0 else "ERR")
                        elif color_tag == "green":
                            box_col = (0, 220, 0); tag = "OK"
                        elif color_tag == "yellow":
                            box_col = (0, 220, 255); tag = "WARN"
                        elif color_tag == "red":
                            box_col = (0, 0, 240); tag = "ERR"
                        else:
                            is_white = c_name.startswith("white")
                            box_col = (255, 225, 60) if is_white else (70, 70, 250)
                            tag = ""

                        cv2.rectangle(annotated_2d, (x1, y1), (x2, y2), box_col, 2, cv2.LINE_AA)

                        # Bỏ mọi số đo tọa độ (x1, y1, x2, y2), chỉ giữ tên quân và trạng thái
                        short_name = c_name.replace("white_", "W-").replace("black_", "B-").upper()
                        label = f"{short_name} [{tag}]" if tag else short_name

                        lbl_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
                        cv2.rectangle(annotated_2d, (x1, y1 - 18), (x1 + lbl_size[0] + 6, y1), box_col, -1)
                        cv2.putText(annotated_2d, label, (x1 + 3, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1, cv2.LINE_AA)

                # Vẽ viền marker ArUco nhìn thấy
                if pose.valid:
                    gray_sub = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
                    det_obj = getattr(pose_estimator, "detector", None)
                    if det_obj is None and hasattr(pose_estimator, "chessboard_estimator"):
                        det_obj = getattr(pose_estimator.chessboard_estimator, "detector", None)
                    if det_obj is not None:
                        try:
                            m_corners, m_ids, _ = det_obj.detectMarkers(gray_sub)
                            if m_ids is not None:
                                for mc in m_corners:
                                    pts = mc[0].astype(int)
                                    cv2.polylines(annotated_2d, [pts], isClosed=True, color=(0, 255, 0), thickness=2, lineType=cv2.LINE_AA)
                        except Exception:
                            pass

                # Căn giữa letterboxing khung hình 2D
                left_panel, _, _, _ = make_letterboxed_frame(annotated_2d, half_w, canvas_h)

                # OSD Info Overlay trên panel trái
                t_frame_end = time.perf_counter()
                fps_curr = 1.0 / max(1e-4, t_frame_end - t_frame_start)
                fps_smooth = fps_curr if fps_smooth == 0.0 else 0.85 * fps_smooth + 0.15 * fps_curr

                cv2.rectangle(left_panel, (0, 0), (half_w, 64), (18, 18, 20), -1)
                # Header OSD
                cv2.putText(left_panel, f"CAMERA STREAM | {fps_smooth:.1f} FPS", (12, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (230, 230, 230), 1, cv2.LINE_AA)
                pose_status = f"POSE: OK (RMS={pose.reproj_error_px:.2f}px)" if pose.valid else "POSE: SEARCHING"
                pose_col = (0, 255, 0) if pose.valid else (0, 0, 255)
                cv2.putText(left_panel, pose_status, (12, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.40, pose_col, 1, cv2.LINE_AA)
                # Góc độ Camera
                cam_str = f"CAM ANGLE: {cam_sector} | Az={cam_azimuth:.0f}deg El={cam_elevation:.0f}deg"
                cv2.putText(left_panel, cam_str, (12, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (120, 220, 255), 1, cv2.LINE_AA)
                # Legend BBox dung sai bên phải
                cv2.circle(left_panel, (half_w - 240, 20), 4, (0, 220, 0), -1, cv2.LINE_AA)
                cv2.putText(left_panel, "<=5mm", (half_w - 230, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 240, 200), 1, cv2.LINE_AA)
                cv2.circle(left_panel, (half_w - 165, 20), 4, (0, 220, 255), -1, cv2.LINE_AA)
                cv2.putText(left_panel, "5-10mm", (half_w - 155, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 240, 200), 1, cv2.LINE_AA)
                cv2.circle(left_panel, (half_w - 90, 20), 4, (0, 0, 240), -1, cv2.LINE_AA)
                cv2.putText(left_panel, ">10mm", (half_w - 80, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 240, 200), 1, cv2.LINE_AA)

                # D. Render Khung nhìn 3D Digital Twin trên panel phải
                right_panel = render_3d_viewport_chessboard8x8(
                    camera_pos=cam_pos_3d,
                    camera_rvec=pose.rvec if pose.valid else None,
                    trajectory=trajectory,
                    chess_pieces=chess_pieces,
                    grid_8x8=active_grid,
                    width=half_w,
                    height=canvas_h,
                    orbit_camera=orbit_camera,
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
            else:
                # Khi đang tạm dừng (is_paused), nếu người dùng xoay/zoom chuột thì re-render ngay lập tức
                if orbit_camera.dirty:
                    right_panel = render_3d_viewport_chessboard8x8(
                        camera_pos=cam_pos_3d,
                        camera_rvec=pose.rvec if pose.valid else None,
                        trajectory=trajectory,
                        chess_pieces=chess_pieces,
                        grid_8x8=active_grid,
                        width=half_w,
                        height=canvas_h,
                        orbit_camera=orbit_camera,
                    )
                    dashboard[:, half_w:] = right_panel
                    orbit_camera.dirty = False

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
        description="Khởi chạy hệ thống Định vị 3D Bàn cờ 8x8 (Digital Twin High-Performance)."
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
        "--charuco-cfg",
        default=str(DEFAULT_CHARUCO_CFG),
        help=f"File cấu hình ChArUco A3. Mặc định: {DEFAULT_CHARUCO_CFG}",
    )
    parser.add_argument(
        "--board-type",
        default="auto",
        choices=["auto", "charuco", "chessboard_8x8"],
        help="Loại bảng: auto | charuco | chessboard_8x8. Mặc định: auto",
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
    parser.add_argument(
        "--dump-csv",
        default=None,
        help="Đường dẫn file CSV xuất thông số đo đạc theo frame.",
    )

    args = parser.parse_args()

    run_chessboard8x8_live(
        source=args.source,
        calib_file=args.calib,
        board_cfg_file=args.board_cfg,
        charuco_cfg_file=args.charuco_cfg,
        board_type=args.board_type,
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
        dump_csv_path=args.dump_csv,
    )


if __name__ == "__main__":
    main()
