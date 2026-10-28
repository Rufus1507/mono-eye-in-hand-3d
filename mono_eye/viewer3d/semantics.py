"""Phân tích ngữ nghĩa bàn cờ và quân cờ (Board Grid & Chess Semantics)."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass
class BoardGrid:
    """Thông số hình học của lưới bàn cờ 8x8."""
    square_size: float
    center: np.ndarray  # [x, y, z]
    y_top: float
    bounds_x: tuple[float, float]
    bounds_z: tuple[float, float]
    file_coords: list[float]  # a -> h (8 giá trị X)
    rank_coords: list[float]  # 1 -> 8 (8 giá trị Z)


# Các object rác ngoài cảnh cần loại bỏ hoàn toàn khỏi quy trình render
IGNORE_OBJECTS = {"Cylinder_Cylinder.003"}

# Quy ước file a..h -> chỉ mục 0..7
FILES = ["a", "b", "c", "d", "e", "f", "g", "h"]
# Quy ước rank 1..8 -> chỉ mục 0..7
RANKS = ["1", "2", "3", "4", "5", "6", "7", "8"]


def detect_board_grid() -> BoardGrid:
    """Xác định thông số lưới ô vuông chuẩn của bàn cờ dựa trên mô hình OBJ."""
    # Mặt bàn chuẩn Cube_Cube.001 có bounds [-0.534809, 0.534809]
    # và lưới ô vuông hữu dụng có square_size xấp xỉ 0.106962
    square_size = 0.106962
    y_top = 0.137120
    center = np.array([0.0, y_top, 0.0], dtype=np.float32)

    # 8 ô được căn đều quanh tâm x=0, z=0
    # Tâm ô thứ i (0..7): (i - 3.5) * square_size
    file_coords = [(i - 3.5) * square_size for i in range(8)]
    # Rank 1 ở Z dương (quân trắng), Rank 8 ở Z âm (quân đen)
    rank_coords = [(3.5 - j) * square_size for j in range(8)]

    half_span = 4.0 * square_size
    bounds_x = (-half_span, half_span)
    bounds_z = (-half_span, half_span)

    return BoardGrid(
        square_size=square_size,
        center=center,
        y_top=y_top,
        bounds_x=bounds_x,
        bounds_z=bounds_z,
        file_coords=file_coords,
        rank_coords=rank_coords,
    )


def square_to_world_coords(square_name: str, grid: BoardGrid | None = None) -> np.ndarray:
    """Chuyển đổi tên ô (ví dụ 'e4', 'a1') thành tọa độ không gian [x, y, z]."""
    if grid is None:
        grid = detect_board_grid()

    sq = square_name.lower().strip()
    if len(sq) != 2:
        raise ValueError(f"Tên ô không hợp lệ: {square_name}")

    file_char, rank_char = sq[0], sq[1]
    file_idx = ord(file_char) - ord("a")
    rank_idx = int(rank_char) - 1

    if not (0 <= file_idx < 8 and 0 <= rank_idx < 8):
        raise ValueError(f"Tên ô nằm ngoài bàn cờ 8x8: {square_name}")

    x = grid.file_coords[file_idx]
    z = grid.rank_coords[rank_idx]
    y = grid.y_top
    return np.array([x, y, z], dtype=np.float32)


# Bảng vị trí khởi đầu FEN tiêu chuẩn cho 32 quân
STARTING_POSITIONS: dict[str, str] = {
    # Quân trắng (Rank 1 & Rank 2)
    "white_rook_1": "a1",
    "white_knight_1": "b1",
    "white_bishop_1": "c1",
    "white_queen": "d1",
    "white_king": "e1",
    "white_bishop_2": "f1",
    "white_knight_2": "g1",
    "white_rook_2": "h1",
    "white_pawn_1": "a2",
    "white_pawn_2": "b2",
    "white_pawn_3": "c2",
    "white_pawn_4": "d2",
    "white_pawn_5": "e2",
    "white_pawn_6": "f2",
    "white_pawn_7": "g2",
    "white_pawn_8": "h2",
    # Quân đen (Rank 7 & Rank 8)
    "black_rook_1": "a8",
    "black_knight_1": "b8",
    "black_bishop_1": "c8",
    "black_queen": "d8",
    "black_king": "e8",
    "black_bishop_2": "f8",
    "black_knight_2": "g8",
    "black_rook_2": "h8",
    "black_pawn_1": "a7",
    "black_pawn_2": "b7",
    "black_pawn_3": "c7",
    "black_pawn_4": "d7",
    "black_pawn_5": "e7",
    "black_pawn_6": "f7",
    "black_pawn_7": "g7",
    "black_pawn_8": "h7",
}
