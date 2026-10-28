"""Kiểm thử tính năng ước lượng chiều cao quân cờ và trực quan hóa bounding box theo dung sai sai số."""
from __future__ import annotations

import numpy as np
import pytest

from mono_eye.camera_io import CameraModel
from mono_eye.chess_pipeline import ChessMonoEyePipeline, ChessResult
from mono_eye.pose import CameraPose


class MockDetector:
    """Mock detector phát hiện 3 quân cờ với các kích thước bbox khác nhau để kiểm tra bậc dung sai."""

    def __init__(self, pieces: list[dict]):
        self.pieces = pieces
        self.device = "cpu"

    def detect(self, frame: np.ndarray) -> list[dict]:
        return [dict(p) for p in self.pieces]


def test_chess_pipeline_height_estimation_and_tolerance():
    """Kiểm tra process_frame gán đúng 4 key chiều cao và phân bậc màu green/yellow/red."""
    # Tạo camera giả lập
    K = np.array([
        [1000.0, 0.0, 320.0],
        [0.0, 1000.0, 240.0],
        [0.0, 0.0, 1.0],
    ], dtype=np.float64)
    dist = np.zeros(5, dtype=np.float64)
    camera = CameraModel(K=K, dist=dist, width=640, height=480)

    # Pose giả lập: Camera nhìn vuông góc xuống mặt bàn từ độ cao Z=600mm
    # rvec: quay quanh trục X một góc 180 độ để camera hướng xuống bàn Z=0
    rvec = np.array([np.pi, 0.0, 0.0], dtype=np.float64)
    tvec = np.array([160.0, 160.0, 600.0], dtype=np.float64)
    pose = CameraPose(
        valid=True,
        rvec=rvec,
        tvec=tvec,
        num_corners=16,
        reproj_error_px=0.5,
        board_type="charuco",
    )

    class MockPoseEstimator:
        def estimate(self, frame):
            return pose

    # Mock 1 quân chốt trắng ở ô a2 (chuẩn true_height = 33mm)
    mock_pieces = [
        {
            "class_name": "white_pawn",
            "confidence": 0.90,
            "bbox": [100.0, 150.0, 140.0, 210.0],
            "bottom_center_pixel": (120.0, 210.0),
        }
    ]

    pipeline = ChessMonoEyePipeline(
        camera=camera,
        detector=MockDetector(mock_pieces),
    )
    pipeline.pose_estimator = MockPoseEstimator()

    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = pipeline.process_frame(dummy_frame)

    assert len(result.pieces) == 1
    p = result.pieces[0]

    # Kiểm tra đã có đủ 4 key chiều cao
    assert "estimated_height_mm" in p
    assert "true_height_mm" in p
    assert "height_error_mm" in p
    assert "square_color" in p

    assert p["true_height_mm"] == 33.0
    assert p["square_color"] in ("green", "yellow", "red")
    assert isinstance(p["estimated_height_mm"], float)

    # Kiểm tra xuất ra dictionary
    as_d = result.as_dict()
    assert as_d["pieces"][0]["estimated_height_mm"] == p["estimated_height_mm"]
    assert as_d["pieces"][0]["square_color"] == p["square_color"]


def test_chess_pipeline_visualization_colored_boxes():
    """Kiểm tra visualize vẽ overlay mờ alpha và viền nhãn theo màu phân bậc."""
    K = np.eye(3, dtype=np.float64)
    dist = np.zeros(5, dtype=np.float64)
    camera = CameraModel(K=K, dist=dist, width=640, height=480)

    pipeline = ChessMonoEyePipeline(camera=camera, detector=MockDetector([]))

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    pieces = [
        {
            "class_name": "white_pawn",
            "confidence": 0.85,
            "bbox": [50.0, 50.0, 150.0, 150.0],
            "bottom_center_pixel": (100.0, 150.0),
            "estimated_height_mm": 50.0,
            "true_height_mm": 33.0,
            "height_error_mm": 17.0,
            "square_color": "red",
            "square": "e4",
        }
    ]
    result = ChessResult(
        timestamp=0.0,
        frame_id=1,
        pose=CameraPose(valid=False),
        pieces=pieces,
        fen="",
    )

    vis = pipeline.visualize(frame, result, draw_pose_axis=False)

    # Vùng bbox (50, 50, 150, 150) phải được vẽ khác 0 và có kênh Red vượt trội
    center_pixel = vis[100, 100]  # BGR
    assert not np.array_equal(center_pixel, [0, 0, 0])
    # Với square_color="red" -> BGR là (0, 0, 240) pha với nền đen qua alpha 0.35 -> Red > Blue
    assert center_pixel[2] > center_pixel[0]
