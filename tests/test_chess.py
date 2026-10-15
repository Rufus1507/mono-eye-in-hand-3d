"""Unit tests cho chess_detectors.py và chess_pipeline.py."""
from pathlib import Path
from unittest.mock import MagicMock
import cv2
import numpy as np
import pytest

from mono_eye.camera_io import CameraModel
from mono_eye.chess_detectors import CHESS_PIECE_LABELS, ChessPieceDetector
from mono_eye.chess_pipeline import ChessMonoEyePipeline, ChessResult
from mono_eye.config import ROOT
from mono_eye.pose import CameraPose


@pytest.fixture
def dummy_camera() -> CameraModel:
    """Tạo CameraModel chuẩn 1280x720 với fx=fy=900, cx=640, cy=360."""
    K = np.array(
        [[900.0, 0.0, 640.0], [0.0, 900.0, 360.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    dist = np.zeros(5, dtype=np.float64)
    return CameraModel(K=K, dist=dist, width=1280, height=720)


@pytest.fixture
def sample_pose() -> CameraPose:
    """Camera ở độ cao 500 mm nhìn thẳng xuống bàn (rvec=[0,0,0], tvec=[0, 0, 500])."""
    return CameraPose(
        valid=True,
        rvec=np.zeros(3, dtype=np.float64),
        tvec=np.array([0.0, 0.0, 500.0], dtype=np.float64),
        num_corners=20,
        reproj_error_px=0.45,
    )


def test_chess_piece_labels():
    """Kiểm tra nhãn lớp và ký tự FEN của 12 loại quân cờ."""
    expected_labels = {
        "white_pawn": "P",
        "white_knight": "N",
        "white_bishop": "B",
        "white_rook": "R",
        "white_queen": "Q",
        "white_king": "K",
        "black_pawn": "p",
        "black_knight": "n",
        "black_bishop": "b",
        "black_rook": "r",
        "black_queen": "q",
        "black_king": "k",
    }
    assert len(CHESS_PIECE_LABELS) == 12
    for name, fen in expected_labels.items():
        assert CHESS_PIECE_LABELS.get(name) == fen


def test_chess_detector_empty_frame():
    """Kiểm tra xử lý ảnh trống hoặc không có quân cờ."""
    mock_model = MagicMock()
    # Mock kết quả trả về không có boxes
    mock_res = MagicMock()
    mock_res.boxes = []
    mock_model.return_value = [mock_res]

    detector = ChessPieceDetector(model=mock_model, conf_threshold=0.5)
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    pieces = detector.detect(frame)

    assert isinstance(pieces, list)
    assert len(pieces) == 0


def test_chess_detector_mock_detections():
    """Kiểm tra tính toán bottom_center_pixel và lọc ngưỡng độ tin cậy."""
    mock_model = MagicMock()
    mock_res = MagicMock()

    # Tạo 2 box: 1 box conf=0.85 (pass) và 1 box conf=0.30 (bị lọc)
    mock_boxes = MagicMock()
    mock_boxes.xyxy = np.array([
        [100.0, 200.0, 150.0, 300.0],
        [200.0, 300.0, 260.0, 420.0],
    ])
    mock_boxes.conf = np.array([0.85, 0.30])
    mock_boxes.cls = np.array([8, 0])  # 8: white_knight, 0: black_bishop

    mock_res.boxes = mock_boxes
    mock_res.names = {8: "white_knight", 0: "black_bishop"}
    mock_model.return_value = [mock_res]

    detector = ChessPieceDetector(model=mock_model, conf_threshold=0.5)
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    pieces = detector.detect(frame)

    assert len(pieces) == 1
    piece = pieces[0]
    assert piece["class_name"] == "white_knight"
    assert piece["fen_char"] == "N"
    assert np.isclose(piece["confidence"], 0.85)
    assert np.allclose(piece["bbox"], [100.0, 200.0, 150.0, 300.0])
    # bottom_center = ((100 + 150) / 2, 300) = (125.0, 300.0)
    assert np.allclose(piece["bottom_center_pixel"], (125.0, 300.0))


def test_chess_detector_visualization():
    """Kiểm tra phương thức visualize của ChessPieceDetector."""
    detector = ChessPieceDetector(model=MagicMock())
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    pieces = [{
        "class_name": "white_queen",
        "fen_char": "Q",
        "confidence": 0.92,
        "bbox": [200, 300, 250, 400],
        "bottom_center_pixel": (225.0, 400.0),
    }]

    vis = detector.visualize(frame, pieces)
    assert vis.shape == frame.shape
    assert vis.dtype == frame.dtype
    # Kiểm tra frame gốc không bị thay đổi tại chỗ
    assert not np.array_equal(vis, frame)


def test_chess_pipeline_with_mock(dummy_camera, sample_pose):
    """Kiểm tra ChessMonoEyePipeline ước lượng 3D khi có pose hợp lệ."""
    mock_pose_estimator = MagicMock()
    mock_pose_estimator.estimate.return_value = sample_pose

    mock_detector = MagicMock()
    # Quân cờ có bottom_center ngay tại tâm quang học (640, 360)
    mock_detector.detect.return_value = [{
        "class_name": "white_king",
        "fen_char": "K",
        "confidence": 0.98,
        "bbox": [610.0, 300.0, 670.0, 360.0],
        "bottom_center_pixel": (640.0, 360.0),
    }]

    pipeline = ChessMonoEyePipeline(
        camera=dummy_camera,
        detector=mock_detector,
        plane_z=0.0,
    )
    pipeline.pose_estimator = mock_pose_estimator

    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    result = pipeline.process_frame(frame)

    assert isinstance(result, ChessResult)
    assert result.pose.valid is True
    assert result.num_pieces == 1
    assert len(result.valid_pieces) == 1

    p = result.pieces[0]
    pos_3d = p["position_3d"]
    assert pos_3d is not None
    # Điểm ngay tâm quang học nhìn thẳng xuống z=0 phải có x=0, y=0, z=0 (mm)
    assert np.allclose(pos_3d, [0.0, 0.0, 0.0], atol=1e-3)


def test_chess_pipeline_invalid_pose(dummy_camera):
    """Kiểm tra khi mất góc ChArUco (pose.valid = False)."""
    invalid_pose = CameraPose(valid=False)

    mock_pose_estimator = MagicMock()
    mock_pose_estimator.estimate.return_value = invalid_pose

    mock_detector = MagicMock()
    mock_detector.detect.return_value = [{
        "class_name": "black_knight",
        "fen_char": "n",
        "confidence": 0.88,
        "bbox": [100.0, 100.0, 140.0, 180.0],
        "bottom_center_pixel": (120.0, 180.0),
    }]

    pipeline = ChessMonoEyePipeline(
        camera=dummy_camera,
        detector=mock_detector,
    )
    pipeline.pose_estimator = mock_pose_estimator

    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    result = pipeline.process_frame(frame)

    assert result.pose.valid is False
    assert result.num_pieces == 1
    assert len(result.valid_pieces) == 0
    assert result.pieces[0]["position_3d"] is None


def test_chess_result_as_dict(sample_pose):
    """Kiểm tra hàm as_dict của ChessResult."""
    result = ChessResult(
        timestamp=123456.78,
        frame_id=42,
        pose=sample_pose,
        pieces=[{
            "class_name": "white_rook",
            "fen_char": "R",
            "confidence": 0.91,
            "bbox": [50.0, 60.0, 100.0, 150.0],
            "bottom_center_pixel": (75.0, 150.0),
            "position_3d": np.array([25.4, -12.3, 0.0]),
        }],
    )

    d = result.as_dict()
    assert d["frame_id"] == 42
    assert d["pose_valid"] is True
    assert len(d["pieces"]) == 1
    assert d["pieces"][0]["class_name"] == "white_rook"
    assert d["pieces"][0]["position_3d"] == [25.4, -12.3, 0.0]


def test_chess_pipeline_visualization(dummy_camera, sample_pose):
    """Kiểm tra visualization của ChessMonoEyePipeline."""
    pipeline = ChessMonoEyePipeline(
        camera=dummy_camera,
        detector=MagicMock(),
    )
    result = ChessResult(
        timestamp=1.0,
        frame_id=1,
        pose=sample_pose,
        pieces=[{
            "class_name": "white_pawn",
            "fen_char": "P",
            "confidence": 0.85,
            "bbox": [100, 100, 140, 180],
            "bottom_center_pixel": (120.0, 180.0),
            "position_3d": np.array([10.0, 20.0, 0.0]),
        }],
    )

    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    vis = pipeline.visualize(frame, result)
    assert vis.shape == (720, 1280, 3)
    assert not np.array_equal(vis, frame)


def test_real_weights_loading():
    """Kiểm tra tải trọng số thực best.pt từ data/models."""
    weights_path = ROOT / "data" / "models" / "best.pt"
    if not weights_path.is_file():
        pytest.skip("Chưa có file best.pt")

    try:
        detector = ChessPieceDetector(model_path=weights_path)
        model = detector.model
    except ImportError:
        pytest.skip("Chưa cài đặt ultralytics")
    assert model is not None
    assert len(model.names) == 12
    # Thử chạy trên ảnh đen
    frame = np.zeros((640, 640, 3), dtype=np.uint8)
    pieces = detector.detect(frame)
    assert isinstance(pieces, list)


def test_detector_device_selection():
    """Kiểm tra cấu hình device cho ChessPieceDetector (cpu, auto, cuda)."""
    import torch

    det_cpu = ChessPieceDetector(model_path=None, device="cpu")
    assert det_cpu.device == "cpu"

    det_auto = ChessPieceDetector(model_path=None, device="auto")
    expected = "cuda:0" if torch.cuda.is_available() else "cpu"
    assert det_auto.device == expected


def test_pipeline_device_propagation(dummy_camera):
    """Kiểm tra ChessMonoEyePipeline truyền device xuống ChessPieceDetector."""
    pipeline = ChessMonoEyePipeline(
        camera=dummy_camera,
        piece_model_path=None,
        device="cpu",
    )
    assert pipeline.detector.device == "cpu"


def test_render_3d_viewport_chess():
    """Kiểm tra render_3d_viewport_chess tạo canvas 3D chứa quân cờ."""
    from scripts.realtime_chess_viz import render_3d_viewport_chess

    cam_pos = np.array([120.0, 80.0, -400.0])
    cam_rvec = np.array([0.1, 0.0, 0.0])
    traj = [cam_pos]
    pieces = [
        {
            "class_name": "white_knight",
            "fen_char": "N",
            "confidence": 0.88,
            "position_3d": np.array([50.0, 60.0, 0.0]),
        },
        {
            "class_name": "black_pawn",
            "fen_char": "p",
            "confidence": 0.75,
            "position_3d": np.array([100.0, 80.0, 0.0]),
        },
    ]

    canvas = render_3d_viewport_chess(
        camera_pos=cam_pos,
        camera_rvec=cam_rvec,
        trajectory=traj,
        chess_pieces=pieces,
        width=640,
        height=480,
    )

    assert canvas.shape == (480, 640, 3)
    assert canvas.dtype == np.uint8
    # Canvas không được trống rỗng/toàn màu đen
    assert canvas.mean() > 20.0


