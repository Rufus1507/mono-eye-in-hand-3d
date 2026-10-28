"""Ánh xạ kết quả nhận diện quân cờ từ YOLO sang các Instance hình học 3D trong Scene."""
from __future__ import annotations

import numpy as np

from mono_eye.viewer3d.board_transform import board_mm_to_scene, square_to_scene_center
from mono_eye.viewer3d.obj_loader import ObjData

# 1. Ánh xạ 12 lớp quân cờ của YOLO sang tên Mesh Group đại diện trong OBJ
PIECE_MESH_BY_CLASS: dict[str, str] = {
    # Quân trắng
    "white_king": "sah_Cylinder.006",
    "white_queen": "vezir_Cylinder.007",
    "white_bishop": "fil_Cylinder",
    "white_knight": "at_Cylinder.004",
    "white_rook": "kale_Cylinder.002",
    "white_pawn": "piyon_single",
    # Quân đen
    "black_king": "sah.001_Cylinder.014",
    "black_queen": "vezir.001_Cylinder.015",
    "black_bishop": "fil.002_Cylinder.011",
    "black_knight": "at.002_Cylinder.010",
    "black_rook": "kale.002_Cylinder.012",
    "black_pawn": "piyon.001_single",
}

# 2. Tập hợp tất cả các nhóm quân cờ tĩnh và mesh quân cờ (để tính pivot và ẩn tĩnh)
PIECE_GROUP_NAMES: set[str] = {
    # Quân chốt đơn động
    "piyon_single",
    "piyon.001_single",
    # Quân trắng tĩnh trong OBJ
    "at_Cylinder.004",
    "fil_Cylinder",
    "kale_Cylinder.002",
    "piyon_Cylinder.001",
    "sah_Cylinder.006",
    "vezir_Cylinder.007",
    "fil.001_Cylinder.005",
    "at.001_Cylinder.008",
    "kale.001_Cylinder.009",
    # Quân đen tĩnh trong OBJ
    "at.002_Cylinder.010",
    "at.003_Cylinder.017",
    "fil.002_Cylinder.011",
    "fil.003_Cylinder.016",
    "kale.002_Cylinder.012",
    "kale.003_Cylinder.018",
    "piyon.001_Cylinder.013",
    "sah.001_Cylinder.014",
    "vezir.001_Cylinder.015",
}


def calculate_piece_pivots(obj_data: ObjData) -> dict[str, np.ndarray]:
    """Tính toán tâm hình học X-Z và đáy Y gốc của từng mesh quân cờ."""
    pivots: dict[str, np.ndarray] = {}
    for group in obj_data.groups:
        if group.name in PIECE_GROUP_NAMES:
            verts = obj_data.vertices[group.indices]
            cx = float((verts[:, 0].min() + verts[:, 0].max()) / 2.0)
            cz = float((verts[:, 2].min() + verts[:, 2].max()) / 2.0)
            base_y = float(verts[:, 1].min())
            pivots[group.name] = np.array([cx, base_y, cz], dtype=np.float32)
    return pivots


def square_to_index(square: str) -> tuple[int, int] | None:
    """Chuyển ký hiệu ô cờ sang chỉ số (cột, hàng) [0..7]. Ví dụ 'a1' -> (0, 0); 'e4' -> (4, 3).
    
    Trả về None nếu ký hiệu không hợp lệ hoặc nằm ngoài bàn cờ 8x8.
    """
    if not square or len(square) < 2:
        return None
    col = square[0].lower()
    rank = square[1]
    if col < "a" or col > "h" or rank < "1" or rank > "8":
        return None
    c_idx = ord(col) - ord("a")
    r_idx = int(rank) - 1
    return (c_idx, r_idx)


def square_to_board_center_mm(square: str, square_size_mm: float = 40.0) -> tuple[float, float] | None:
    """Tính toán tọa độ tâm ô cờ (mm) trong hệ tọa độ ChArUco 8x8.
    
    Quy ước chuẩn ChArUco 8x8:
    - Cột a..h: X_center = (c_idx + 0.5) * square_size_mm
    - Hàng 1..8: Y_center = (r_idx + 0.5) * square_size_mm
    """
    idx = square_to_index(square)
    if idx is None:
        return None
    c_idx, r_idx = idx
    x_mm = (c_idx + 0.5) * square_size_mm
    y_mm = (r_idx + 0.5) * square_size_mm
    return (x_mm, y_mm)


def build_piece_instances(
    detected_pieces: list[dict],
    group_index_by_name: dict[str, int],
    pivots: dict[str, np.ndarray],
    snap_to_squares: bool = True,
) -> list[tuple[int, np.ndarray]]:
    """Chuyển đổi danh sách quân cờ phát hiện được từ camera sang danh sách instance hình học 3D.
    
    Quy tắc:
    - CHỈ sinh instance cho các quân cờ thực sự có mặt trên bàn (square khác None và hợp lệ).
    - Snap quân cờ vào chính giữa tâm ô cờ (square center) của model OBJ, loại bỏ chiều cao z_mm.
    - Các quân cờ không được phát hiện hoặc nằm ngoài bàn cờ sẽ hoàn toàn KHÔNG xuất hiện.
    """
    instances: list[tuple[int, np.ndarray]] = []

    for piece in detected_pieces:
        pos_3d = piece.get("position_3d")
        square = piece.get("square")
        class_name = piece.get("class_name")

        # Chỉ cần có ô cờ (square) hợp lệ và tên lớp
        if square is None or not class_name:
            continue

        # Định vị đích trong 3D Scene:
        # Khi snap_to_squares=True: đặt 100% tại tâm ô cờ chính xác tuyệt đối của model OBJ
        if snap_to_squares:
            idx = square_to_index(square)
            if idx is None:
                continue
            target_scene = square_to_scene_center(*idx)
        elif pos_3d is not None:
            target_scene = board_mm_to_scene(float(pos_3d[0]), float(pos_3d[1]), 0.0)
        else:
            continue

        mesh_name = PIECE_MESH_BY_CLASS.get(class_name)
        if not mesh_name or mesh_name not in group_index_by_name:
            continue

        group_idx = group_index_by_name[mesh_name]
        pivot = pivots.get(mesh_name, np.zeros(3, dtype=np.float32))

        # Ma trận biến đổi: Dịch từ pivot gốc trong OBJ tới vị trí đích trên bàn cờ
        translation = target_scene - pivot
        M = np.eye(4, dtype=np.float32)
        M[0, 3] = translation[0]
        M[1, 3] = translation[1]
        M[2, 3] = translation[2]

        instances.append((group_idx, M))

    return instances
