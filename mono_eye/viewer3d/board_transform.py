"""Chuyển đổi hệ tọa độ giữa Bàn cờ thực tế (ChArUco Frame mm) và Không gian 3D Scene."""
from __future__ import annotations

import math
import numpy as np

# Tỷ lệ chuyển đổi giữa Scene Unit và Milimet thực tế (mm)
UNIT_TO_MM = 373.9645
MM_TO_UNIT = 1.0 / UNIT_TO_MM

# Kích thước bàn cờ 8x8 (8 ô x 40mm = 320mm)
BOARD_CELLS_MM = 320.0
BOARD_HALF_MM = 160.0

# Cao độ trục Y trong Scene
PIECE_BASE_Y = 0.14921    # Đáy quân cờ đặt trên mặt bàn
BOARD_PLANE_Y = 0.137120  # Mặt bàn cờ đá

# Thông số hình học chính xác của lưới 64 ô cờ trong model OBJ (Cube.001_Cube.003)
SQUARE_SIZE_SCENE = 0.1214425  # 0.97154 / 8.0 — kích thước ô thật trong OBJ
HALF_GRID_SCENE = 0.48577      # (0.97154 / 2.0) — bán cạnh lưới OBJ


def square_to_scene_center(c: int, r: int) -> np.ndarray:
    """Tính toán tọa độ Scene 3D chính xác tuyệt đối tại tâm ô cờ (c, r).
    
    Quy ước lưới 64 ô cờ trong model OBJ (Cube.001_Cube.003):
    - Cột c (0..7 ứng với a..h): chạy từ -X sang +X
    - Hàng r (0..7 ứng với 1..8): chạy từ +Z sang -Z
    - Cao độ Y: PIECE_BASE_Y (đáy quân cờ chạm đúng mặt trên của ô cờ)
    """
    scene_x = -HALF_GRID_SCENE + (float(c) + 0.5) * SQUARE_SIZE_SCENE
    scene_z = HALF_GRID_SCENE - (float(r) + 0.5) * SQUARE_SIZE_SCENE
    scene_y = PIECE_BASE_Y
    return np.array([scene_x, scene_y, scene_z], dtype=np.float32)


def board_mm_to_scene(x_mm: float, y_mm: float, z_mm: float = 0.0) -> np.ndarray:
    """Chuyển đổi tọa độ (x_mm, y_mm, z_mm) từ ChArUco Board Frame sang Scene Frame.
    
    Quy ước:
    - Gốc (0, 0) của ChArUco Board là góc trên bên trái của lưới 8x8.
    - Tâm bàn cờ ở (160mm, 160mm).
    - Scene Frame có tâm ở (0, 0, 0), trục X sang phải, trục Y hướng lên trên trời, trục Z hướng theo rank.
    """
    sx = (float(x_mm) - BOARD_HALF_MM) * MM_TO_UNIT
    sz = -(float(y_mm) - BOARD_HALF_MM) * MM_TO_UNIT
    sy = PIECE_BASE_Y + float(z_mm) * MM_TO_UNIT
    return np.array([sx, sy, sz], dtype=np.float32)


def board_to_scene_rotation() -> np.ndarray:
    """Ma trận biến đổi trực giao chuyển hệ trục từ Board (Z hướng xuống bàn hoặc vuông góc) sang Scene (Y lên trời)."""
    # X_scene = X_board
    # Y_scene = Z_board
    # Z_scene = -Y_board
    return np.array([
        [1.0,  0.0,  0.0],
        [0.0,  0.0,  1.0],
        [0.0, -1.0,  0.0],
    ], dtype=np.float32)


def rodrigues_np(rvec: np.ndarray) -> np.ndarray:
    """Chuyển đổi vector quay rvec sang ma trận quay R 3x3 (thuần numpy, không phụ thuộc cv2)."""
    r = np.asarray(rvec, dtype=np.float64).flatten()
    theta = np.linalg.norm(r)
    if theta < 1e-12:
        return np.eye(3, dtype=np.float32)
    u = r / theta
    K = np.array([
        [0.0, -u[2], u[1]],
        [u[2], 0.0, -u[0]],
        [-u[1], u[0], 0.0],
    ], dtype=np.float64)
    R = np.eye(3) + np.sin(theta) * K + (1.0 - np.cos(theta)) * (K @ K)
    return R.astype(np.float32)


def scene_cam_from_pose(rvec: np.ndarray, tvec: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Tính toán vị trí mắt camera (eye_scene) và ma trận quay camera trong Scene từ rvec, tvec của ChArUco.
    
    Trong camera pipeline: X_cam = R_board2cam * X_board + tvec
    Do đó tâm camera trong Board Frame: C_board = -R_board2cam.T @ tvec
    """
    R_b2c = rodrigues_np(rvec)
    t = np.asarray(tvec, dtype=np.float32).flatten()
    C_board = -R_b2c.T @ t

    # Vị trí mắt camera trong Scene Frame
    eye_scene = board_mm_to_scene(C_board[0], C_board[1], C_board[2])

    # Hướng nhìn của camera trong Scene:
    # R_cam2board = R_b2c.T
    # R_cam_scene = R_board2scene @ R_cam2board
    R_b2s = board_to_scene_rotation()
    R_cam_scene = R_b2s @ R_b2c.T

    return eye_scene, R_cam_scene


def fov_y_from_K(K: np.ndarray, image_height: int) -> float:
    """Tính góc mở dọc FOV_y (độ) từ ma trận nội suy camera K và chiều cao khung hình."""
    f_y = float(K[1, 1])
    fov_y_rad = 2.0 * math.atan((float(image_height) / 2.0) / f_y)
    return float(math.degrees(fov_y_rad))
