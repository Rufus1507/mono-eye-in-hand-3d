"""Kiểm thử bộ lọc ổn định quân cờ thời gian thực (PieceStabilizer)."""
from __future__ import annotations

import pytest

from mono_eye.viewer3d.piece_stabilizer import PieceStabilizer, square_distance


def test_square_distance():
    """Kiểm tra tính khoảng cách Chebyshev giữa các ô cờ."""
    assert square_distance("e3", "e4") == 1  # Liền kề theo hàng
    assert square_distance("d4", "e4") == 1  # Liền kề theo cột
    assert square_distance("d3", "e4") == 1  # Liền kề theo đường chéo
    assert square_distance("e3", "e5") == 2  # Cách 2 ô (không liền kề)
    assert square_distance("a1", "h8") == 7


def test_piece_stabilizer_confirmation_delay():
    """Kiểm tra loại bỏ nhiễu ngẫu nhiên 1 frame (chống nhảy cờ)."""
    stabilizer = PieceStabilizer(persist_frames=5, min_hits=2)

    noise_piece = {"class_name": "black_knight", "square": "c3", "confidence": 0.60}

    # Frame 0: Chỉ xuất hiện 1 frame đơn lẻ do nhiễu -> CHƯA ĐƯỢC HIỂN THỊ
    res0 = stabilizer.feed([noise_piece])
    assert len(res0) == 0, "Nhiễu 1 frame không được phép xuất hiện ngay"

    # Frame 1: Xuất hiện lần thứ 2 -> XÁC NHẬN VÀ HIỂN THỊ
    res1 = stabilizer.feed([noise_piece])
    assert len(res1) == 1
    assert res1[0]["square"] == "c3"


def test_piece_stabilizer_spatial_dedup():
    """Kiểm tra khử bóng ma trùng lặp giữa 2 ô liền kề (ví dụ do nhiễu ranh giới giữa e3 và e4)."""
    stabilizer = PieceStabilizer(persist_frames=5, min_hits=2)

    pawn_e3 = {"class_name": "black_pawn", "square": "e3", "confidence": 0.55}
    pawn_e4 = {"class_name": "black_pawn", "square": "e4", "confidence": 0.75}

    # Frame 0: e3 xuất hiện
    stabilizer.feed([pawn_e3])
    # Frame 1: e3 xuất hiện lần 2 -> xác nhận
    res = stabilizer.feed([pawn_e3])
    assert len(res) == 1
    assert res[0]["square"] == "e3"

    # Frame 2: Do nhiễu góc quay, detection nhảy sang e4 (với confidence cao hơn 0.75)
    # Frame 3: e4 tiếp tục xuất hiện
    stabilizer.feed([pawn_e4])
    res3 = stabilizer.feed([pawn_e4])

    # Nhờ Spatial Dedup: CHỈ CÓ ĐÚNG 1 QUÂN CHỐT ĐƯỢC HIỂN THỊ (không thể có cả e3 và e4 cùng lúc)
    assert len(res3) == 1
    assert res3[0]["square"] == "e4"


def test_piece_stabilizer_persistence():
    """Kiểm tra tính năng duy trì quân cờ khi detection bị mất tạm thời (flicker prevention)."""
    stabilizer = PieceStabilizer(persist_frames=5, min_hits=2, debounce_frames=3)

    pawn_e4 = {
        "class_name": "white_pawn",
        "square": "e4",
        "position_3d": [180.0, 140.0, 0.0],
        "confidence": 0.85,
    }

    # Frame 0 - 2: Quân cờ xuất hiện 3 frame liên tiếp
    for f in range(3):
        res = stabilizer.feed([pawn_e4])
    assert len(res) == 1
    assert res[0]["square"] == "e4"
    assert res[0]["class_name"] == "white_pawn"

    # Frame 3 - 5: Tạm thời mất detection (ví dụ YOLO bị drop 3 frame)
    for f in range(3, 6):
        res = stabilizer.feed([])
        # Nhờ có persist_frames=5, quân cờ vẫn ĐƯỢC DUY TRÌ, KHÔNG BỊ NHẤP NHÁY
        assert len(res) == 1, f"Frame {f} bị mất quân cờ e4"
        assert res[0]["square"] == "e4"

    # Frame 6 - 8: Tiếp tục không thấy -> quá 5 frame không có detection -> quân cờ bị xóa
    for f in range(6, 9):
        res = stabilizer.feed([])

    # Sau 5 frame liên tiếp mất detection, quân cờ biến mất hoàn toàn
    assert len(res) == 0


def test_piece_stabilizer_class_debounce():
    """Kiểm tra bộ lọc chống nhảy loại quân cờ bất thường giữa các frame."""
    stabilizer = PieceStabilizer(persist_frames=6, min_hits=1, debounce_frames=3)

    pawn_e4 = {"class_name": "white_pawn", "square": "e4", "confidence": 0.80}
    noise_bishop = {"class_name": "white_bishop", "square": "e4", "confidence": 0.45}

    # 4 frames liên tiếp là white_pawn
    for _ in range(4):
        res = stabilizer.feed([pawn_e4])
        assert res[0]["class_name"] == "white_pawn"

    # 1 frame nhiễu nhận diện nhầm thành white_bishop
    res = stabilizer.feed([noise_bishop])
    # Nhờ majority vote / debounce, lớp quân cờ vẫn được giữ nguyên là white_pawn
    assert res[0]["class_name"] == "white_pawn"

    # Frame tiếp theo quay lại white_pawn
    res = stabilizer.feed([pawn_e4])
    assert res[0]["class_name"] == "white_pawn"


def test_piece_stabilizer_reset():
    """Kiểm tra tính năng reset bộ nhớ bám vết."""
    stabilizer = PieceStabilizer(persist_frames=6, min_hits=1)
    pawn_d5 = {"class_name": "black_pawn", "square": "d5", "confidence": 0.90}

    stabilizer.feed([pawn_d5])
    assert len(stabilizer.tracks) == 1

    stabilizer.reset()
    assert len(stabilizer.tracks) == 0

    # Sau khi reset, feed rỗng sẽ không còn track nào
    res = stabilizer.feed([])
    assert len(res) == 0
