"""Kiểm thử logic chuyển đổi tọa độ và ánh xạ quân cờ động (Piece Mapper Tests)."""
from __future__ import annotations

import numpy as np
import pytest

from mono_eye.viewer3d.board_transform import (
    BOARD_HALF_MM,
    PIECE_BASE_Y,
    board_mm_to_scene,
)
from mono_eye.viewer3d.obj_loader import load_scene_cached
from mono_eye.viewer3d.paths import DEFAULT_OBJ
from mono_eye.viewer3d.piece_mapper import (
    PIECE_GROUP_NAMES,
    PIECE_MESH_BY_CLASS,
    build_piece_instances,
    calculate_piece_pivots,
)


def test_board_mm_to_scene_transform():
    """Kiểm tra độ chính xác của phép biến đổi tọa độ mm sang scene unit."""
    # Tâm bàn cờ (160mm, 160mm) -> X=0, Z=0 trong Scene
    center = board_mm_to_scene(160.0, 160.0, 0.0)
    assert abs(center[0]) < 1e-5
    assert abs(center[1] - PIECE_BASE_Y) < 1e-5
    assert abs(center[2]) < 1e-5

    # Góc a1 (gần gốc 0, 0) -> X âm, Z dương (Rank 1 ở Z dương theo Scene)
    a1_scene = board_mm_to_scene(20.0, 20.0, 0.0)
    assert a1_scene[0] < 0.0
    assert a1_scene[2] > 0.0

    # Góc h8 (gần 300mm, 300mm) -> X dương, Z âm
    h8_scene = board_mm_to_scene(300.0, 300.0, 0.0)
    assert h8_scene[0] > 0.0
    assert h8_scene[2] < 0.0


def test_piece_mapper_classes_and_groups():
    """Đảm bảo 12 lớp quân cờ YOLO đều được ánh xạ tới các mesh group hợp lệ."""
    assert len(PIECE_MESH_BY_CLASS) == 12

    obj_data = load_scene_cached(DEFAULT_OBJ)
    group_names = {g.name for g in obj_data.groups}

    for cls_name, mesh_name in PIECE_MESH_BY_CLASS.items():
        assert mesh_name in group_names, f"Mesh {mesh_name} của {cls_name} không có trong OBJ!"

    # 18 group quân cờ tĩnh đều phải có trong tập nhóm của OBJ
    for gname in PIECE_GROUP_NAMES:
        assert gname in group_names, f"Nhóm {gname} không tồn tại trong OBJ!"


def test_build_piece_instances_rules():
    """Kiểm tra quy tắc sinh instance: CHỈ sinh instance cho quân cờ được phát hiện hợp lệ."""
    obj_data = load_scene_cached(DEFAULT_OBJ)
    group_index_by_name = {g.name: i for i, g in enumerate(obj_data.groups)}
    pivots = calculate_piece_pivots(obj_data)

    detected = [
        # Quân hợp lệ 1: Tốt trắng ở a2
        {
            "class_name": "white_pawn",
            "position_3d": [20.0, 60.0, 0.0],
            "square": "a2",
            "confidence": 0.88,
        },
        # Quân hợp lệ 2: Vua đen ở e8
        {
            "class_name": "black_king",
            "position_3d": [180.0, 300.0, 0.0],
            "square": "e8",
            "confidence": 0.95,
        },
        # Quân KHÔNG hợp lệ: Bị nhấc lên khỏi bàn (square=None) -> PHẢI BỊ ẨN
        {
            "class_name": "white_knight",
            "position_3d": [60.0, 20.0, 50.0],
            "square": None,
            "confidence": 0.70,
        },
        # Quân có square="a8" hợp lệ dù position_3d=None -> VẪN XUẤT HIỆN đúng tâm ô
        {
            "class_name": "black_rook",
            "position_3d": None,
            "square": "a8",
            "confidence": 0.65,
        },
    ]

    instances = build_piece_instances(detected, group_index_by_name, pivots)

    # CẢ 3 QUÂN CÓ SQUARE HỢP LỆ ĐỀU XUẤT HIỆN TRÊN BÀN 3D (quân square=None bị ẩn)
    assert len(instances) == 3, f"Kỳ vọng 3 instance, nhận được {len(instances)}"

    # Kiểm tra ma trận biến đổi Model 4x4 hợp lệ và đáy quân cờ chạm đúng mặt bàn (Y translation ~ 0)
    for g_idx, M in instances:
        assert M.shape == (4, 4)
        assert M[3, 3] == 1.0
        assert abs(M[1, 3]) < 1e-4, f"Quân cờ bị nâng độ cao: Y={M[1, 3]}"


def test_square_to_board_center_mm():
    """Kiểm tra ánh xạ ký hiệu ô cờ sang tọa độ tâm mm (ChArUco 8x8 ô 40mm)."""
    from mono_eye.viewer3d.piece_mapper import square_to_board_center_mm

    # a1 (cột 0, hàng 0) -> X=20mm, Y=20mm
    assert square_to_board_center_mm("a1") == (20.0, 20.0)
    # e4 (cột 4, hàng 3) -> X=180mm, Y=140mm
    assert square_to_board_center_mm("e4") == (180.0, 140.0)
    # h8 (cột 7, hàng 7) -> X=300mm, Y=300mm
    assert square_to_board_center_mm("h8") == (300.0, 300.0)

    # Đầu vào không hợp lệ -> None
    assert square_to_board_center_mm("") is None
    assert square_to_board_center_mm("x9") is None
    assert square_to_board_center_mm(None) is None


def test_square_to_scene_center_matches_obj_tiles():
    """Kiểm tra tâm ô cờ Scene khớp chính xác 4 góc lưới model OBJ."""
    from mono_eye.viewer3d.board_transform import square_to_scene_center

    # a1 (cột 0, hàng 0) -> X âm nhất, Z dương nhất
    a1 = square_to_scene_center(0, 0)
    assert abs(a1[0] - (-0.42505)) < 1e-3
    assert abs(a1[2] - 0.42505) < 1e-3
    assert abs(a1[1] - 0.14921) < 1e-4

    # h8 (cột 7, hàng 7) -> X dương nhất, Z âm nhất
    h8 = square_to_scene_center(7, 7)
    assert abs(h8[0] - 0.42505) < 1e-3
    assert abs(h8[2] - (-0.42505)) < 1e-3


def test_build_piece_instances_snaps_to_obj_tile_center():
    """Kiểm tra quân cờ có square luôn snap chuẩn vào tâm ô cờ OBJ dù position_3d sai."""
    from mono_eye.viewer3d.obj_loader import load_scene_cached
    from mono_eye.viewer3d.paths import DEFAULT_OBJ
    from mono_eye.viewer3d.piece_mapper import (
        build_piece_instances,
        calculate_piece_pivots,
        square_to_index,
    )
    from mono_eye.viewer3d.board_transform import square_to_scene_center

    obj_data = load_scene_cached(DEFAULT_OBJ)
    group_index_by_name = {g.name: i for i, g in enumerate(obj_data.groups)}
    pivots = calculate_piece_pivots(obj_data)

    detected = [
        {
            "class_name": "white_pawn",
            "square": "a2",
            "position_3d": [9999.0, -9999.0, 500.0],  # Tọa độ camera lệch cực lớn
            "confidence": 0.90,
        }
    ]

    instances = build_piece_instances(detected, group_index_by_name, pivots, snap_to_squares=True)
    assert len(instances) == 1
    g_idx, M = instances[0]

    # Vị trí đích thực tế của a2 trong Scene
    idx = square_to_index("a2")
    target_expected = square_to_scene_center(*idx)
    pivot = pivots["piyon_single"]
    expected_trans = target_expected - pivot

    assert abs(M[0, 3] - expected_trans[0]) < 1e-4
    assert abs(M[1, 3] - expected_trans[1]) < 1e-4
    assert abs(M[2, 3] - expected_trans[2]) < 1e-4


def test_square_to_index_invalid():
    """Kiểm tra square_to_index xử lý đúng định dạng hợp lệ và không hợp lệ."""
    from mono_eye.viewer3d.piece_mapper import square_to_index

    assert square_to_index("a1") == (0, 0)
    assert square_to_index("h8") == (7, 7)
    assert square_to_index("e4") == (4, 3)
    assert square_to_index("x9") is None
    assert square_to_index("") is None
    assert square_to_index(None) is None
