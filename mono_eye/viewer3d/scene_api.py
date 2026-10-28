"""API điều khiển trạng thái không gian 3D của Bàn cờ và Quân cờ (Chess3DScene).

Sẵn sàng nhận dữ liệu vị trí quân cờ từ camera, thuật toán YOLO hoặc nước đi cờ vua.
"""
from __future__ import annotations

from pathlib import Path
import numpy as np

from mono_eye.viewer3d.obj_loader import ObjData, load_scene_cached
from mono_eye.viewer3d.paths import DEFAULT_OBJ
from mono_eye.viewer3d.semantics import STARTING_POSITIONS, BoardGrid, detect_board_grid, square_to_world_coords

# Hệ số quy đổi tỷ lệ giữa đơn vị không gian mô hình (Scene Unit) và Milimet thực tế (mm)
# Bàn cờ thực tế tiêu chuẩn 8x8 là ~320mm đến 400mm (mỗi ô ~40mm - 50mm)
# Trong scene, square_size ≈ 0.106962, nếu ô thực tế là 40mm thì 1 scene unit ≈ 374mm.
UNIT_TO_MM = 373.9645
MM_TO_UNIT = 1.0 / UNIT_TO_MM


class Chess3DScene:
    """Quản lý vị trí, ma trận biến đổi (Transforms) và trạng thái các quân cờ trên bàn."""

    def __init__(self, obj_path: Path | None = None, use_cache: bool = True) -> None:
        self.grid = detect_board_grid()
        self.obj_data: ObjData = load_scene_cached(obj_path or DEFAULT_OBJ, force_rebuild=not use_cache)

        # Ánh xạ tên vai trò quân cờ sang index của mesh group trong obj_data
        self.piece_group_indices: dict[str, int] = {}
        self._init_piece_mapping()

        # Lưu ma trận 4x4 (Model Matrix) cho từng quân cờ
        self.transforms: dict[str, np.ndarray] = {}
        self.reset_to_starting_positions()

    def _init_piece_mapping(self) -> None:
        """Nhận diện index nhóm lưới của từng quân cờ từ danh sách tên groups."""
        for i, group in enumerate(self.obj_data.groups):
            g_name = group.name.lower()
            if "kale" in g_name:
                if "bayaz" in group.material or "bayaz" in g_name:
                    if "kale.001" in g_name:
                        self.piece_group_indices["white_rook_2"] = i
                    else:
                        self.piece_group_indices["white_rook_1"] = i
                else:
                    if "kale.003" in g_name:
                        self.piece_group_indices["black_rook_2"] = i
                    else:
                        self.piece_group_indices["black_rook_1"] = i
            elif "at" in g_name:
                if "bayaz" in group.material or "bayaz" in g_name:
                    if "at.001" in g_name:
                        self.piece_group_indices["white_knight_2"] = i
                    else:
                        self.piece_group_indices["white_knight_1"] = i
                else:
                    if "at.003" in g_name:
                        self.piece_group_indices["black_knight_2"] = i
                    else:
                        self.piece_group_indices["black_knight_1"] = i
            elif "fil" in g_name:
                if "bayaz" in group.material or "bayaz" in g_name:
                    if "fil.001" in g_name:
                        self.piece_group_indices["white_bishop_2"] = i
                    else:
                        self.piece_group_indices["white_bishop_1"] = i
                else:
                    if "fil.003" in g_name:
                        self.piece_group_indices["black_bishop_2"] = i
                    else:
                        self.piece_group_indices["black_bishop_1"] = i
            elif "sah" in g_name:
                if "bayaz" in group.material or "bayaz" in g_name:
                    self.piece_group_indices["white_king"] = i
                else:
                    self.piece_group_indices["black_king"] = i
            elif "vezir" in g_name:
                if "bayaz" in group.material or "bayaz" in g_name:
                    self.piece_group_indices["white_queen"] = i
                else:
                    self.piece_group_indices["black_queen"] = i

    def reset_to_starting_positions(self) -> None:
        """Đặt lại tất cả các quân về vị trí FEN khởi đầu chuẩn."""
        for role, sq in STARTING_POSITIONS.items():
            self.set_piece_square(role, sq)

    def set_piece_square(self, role: str, square_name: str) -> None:
        """Di chuyển một quân cờ đến tâm của ô cờ tương ứng (ví dụ 'e4')."""
        target_pos = square_to_world_coords(square_name, self.grid)
        T = np.eye(4, dtype=np.float32)
        T[0, 3] = target_pos[0]
        T[1, 3] = target_pos[1]
        T[2, 3] = target_pos[2]
        self.transforms[role] = T

    def set_piece_position_mm(self, role: str, x_mm: float, y_mm: float, z_mm: float) -> None:
        """Di chuyển quân cờ bằng tọa độ milimet thực tế từ camera pipeline."""
        x_scene = x_mm * MM_TO_UNIT
        # Tọa độ Y trong scene là trục đứng thẳng đứng, Z là trục nằm ngang mặt bàn
        y_scene = y_mm * MM_TO_UNIT + self.grid.y_top
        z_scene = z_mm * MM_TO_UNIT

        T = np.eye(4, dtype=np.float32)
        T[0, 3] = x_scene
        T[1, 3] = y_scene
        T[2, 3] = z_scene
        self.transforms[role] = T

    def piece_transforms(self) -> dict[str, np.ndarray]:
        """Trả về toàn bộ ma trận biến đổi của các quân cờ đang quản lý."""
        return self.transforms
