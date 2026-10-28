"""Unit test cho tính năng đo kích thước chiều cao quân cờ 3D và dung sai màu sắc."""
import cv2
import numpy as np
import pytest

from mono_eye.chess_board_grid import (
    CHESS_PIECE_HEIGHTS,
    get_piece_true_height,
)
from mono_eye.pose import CameraPose
from mono_eye.projection import ProjectionProcessor


def test_get_piece_true_height():
    """Kiểm tra chiều cao chuẩn của các quân cờ đen và trắng theo yêu cầu người dùng."""
    assert get_piece_true_height("white_pawn") == 33.0
    assert get_piece_true_height("black_pawn") == 33.0
    assert get_piece_true_height("white_queen") == 57.0
    assert get_piece_true_height("black_queen") == 57.0
    assert get_piece_true_height("white_bishop") == 47.0
    assert get_piece_true_height("black_bishop") == 47.0
    assert get_piece_true_height("white_rook") == 37.0
    assert get_piece_true_height("black_rook") == 37.0
    assert get_piece_true_height("white_knight") == 41.0
    assert get_piece_true_height("black_knight") == 41.0
    assert get_piece_true_height("white_king") == 65.0
    assert get_piece_true_height("black_king") == 65.0


def test_compute_piece_height_synthetic():
    """Kiểm tra độ chính xác thuật toán giao cắt tia 3D với trục đứng ở góc camera tùy biến."""
    # Camera ma trận chuẩn fx=fy=1000, cx=640, cy=360
    K = np.array([
        [1000.0, 0.0, 640.0],
        [0.0, 1000.0, 360.0],
        [0.0, 0.0, 1.0],
    ], dtype=np.float64)
    dist = np.zeros(5, dtype=np.float64)
    processor = ProjectionProcessor(K, dist, plane_z=0.0)

    # Đặt camera tại góc nghiêng 45 độ, cao Z=400mm, nhìn vào bàn cờ
    # rvec quay quanh trục X một góc khoảng 135 độ (hoặc 45 độ chúc xuống)
    rvec = np.array([2.2, 0.0, 0.0], dtype=np.float64)
    tvec = np.array([0.0, 100.0, 500.0], dtype=np.float64)
    pose = CameraPose(
        rvec=rvec,
        tvec=tvec,
        num_corners=32,
        reproj_error_px=0.5,
        valid=True,
    )

    # Giả sử quân chốt đặt tại tâm ô e4 (X=140mm, Y=140mm), chiều cao thực tế 33.0mm
    base_3d = np.array([140.0, 140.0, 0.0], dtype=np.float64)
    top_3d = np.array([140.0, 140.0, 33.0], dtype=np.float64)

    # Chiếu 3D xuống pixel ảnh để giả lập bounding box từ camera
    pts_3d = np.vstack([base_3d, top_3d])
    proj_pts, _ = cv2.projectPoints(pts_3d, rvec, tvec, K, dist)
    bot_px = tuple(proj_pts[0, 0])
    top_px = tuple(proj_pts[1, 0])

    # Gọi hàm tính chiều cao
    measured_h = processor.compute_piece_height(bot_px, top_px, pose, base_3d=base_3d)

    assert measured_h is not None
    # Sai số đo hình học phải < 0.5 mm
    assert abs(measured_h - 33.0) < 0.5
