"""Kiểm thử tính đúng đắn của logic lưới bàn cờ và ngữ nghĩa quân cờ (Semantics)."""
from __future__ import annotations

import pytest
import numpy as np

from mono_eye.viewer3d.semantics import (
    IGNORE_OBJECTS,
    STARTING_POSITIONS,
    detect_board_grid,
    square_to_world_coords,
)


def test_board_grid_geometry():
    """Kiểm tra kích thước lưới ô vuông 8x8."""
    grid = detect_board_grid()
    assert abs(grid.square_size - 0.106962) < 1e-4
    assert abs(grid.y_top - 0.137120) < 1e-4
    assert len(grid.file_coords) == 8
    assert len(grid.rank_coords) == 8

    # Kiểm tra khoảng cách đều đặn giữa các ô
    for i in range(7):
        diff_file = grid.file_coords[i + 1] - grid.file_coords[i]
        assert abs(diff_file - grid.square_size) < 1e-5


def test_starting_positions_semantics():
    """Đảm bảo 32 quân khởi đầu không quân nào trùng vị trí ô."""
    assert len(STARTING_POSITIONS) == 32
    occupied_squares = set(STARTING_POSITIONS.values())
    assert len(occupied_squares) == 32, "Có quân cờ bị trùng ô khởi đầu!"

    grid = detect_board_grid()
    for role, sq in STARTING_POSITIONS.items():
        coords = square_to_world_coords(sq, grid)
        assert len(coords) == 3
        # Rank 1 và 2 (quân trắng) ở Z dương
        if role.startswith("white"):
            assert coords[2] > 0.0
        # Rank 7 và 8 (quân đen) ở Z âm
        elif role.startswith("black"):
            assert coords[2] < 0.0


def test_ignore_junk_objects():
    """Kiểm tra bộ lọc loại bỏ các vật thể rác ngoài cảnh."""
    assert "Cylinder_Cylinder.003" in IGNORE_OBJECTS
