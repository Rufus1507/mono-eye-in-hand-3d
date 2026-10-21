"""Unit tests cho Chessboard 8x8 Pose Estimator, BoardGrid8x8 và Dual Board Pipeline."""
from pathlib import Path
from unittest.mock import MagicMock
import cv2
import numpy as np
import pytest

from mono_eye.camera_io import CameraModel
from mono_eye.chess_board_grid import BoardGrid8x8, compensate_piece_occlusions
from mono_eye.chess_pipeline import ChessMonoEyePipeline, ChessResult
from mono_eye.config import ROOT
from mono_eye.pose import (
    CameraPose,
    ChessboardPoseEstimator,
    PoseEstimator,
    UnifiedPoseEstimator,
)


@pytest.fixture
def dummy_camera() -> CameraModel:
    """Tạo CameraModel chuẩn 1280x720."""
    K = np.array(
        [[900.0, 0.0, 640.0], [0.0, 900.0, 360.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    dist = np.zeros(5, dtype=np.float64)
    return CameraModel(K=K, dist=dist, width=1280, height=720)


@pytest.fixture
def phone_camera() -> CameraModel:
    """Tạo CameraModel cho ảnh dọc 1440x2560."""
    K = np.array(
        [[1500.0, 0.0, 720.0], [0.0, 1500.0, 1280.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    dist = np.zeros(5, dtype=np.float64)
    return CameraModel(K=K, dist=dist, width=1440, height=2560)


def test_chessboard_config_loading(dummy_camera):
    """Kiểm tra việc nạp file cấu hình configs/banco_8x8.yaml và sinh điểm 3D."""
    cfg_file = ROOT / "configs" / "banco_8x8.yaml"
    assert cfg_file.is_file(), f"File {cfg_file} không tồn tại!"

    estimator = ChessboardPoseEstimator(
        camera=dummy_camera,
        board_config=cfg_file,
    )

    assert estimator.square_size_mm == 40.0
    assert estimator.marker_size_mm == 24.0
    assert len(estimator.marker_3d_map) == 32

    # Kiểm tra mỗi marker có đúng 4 góc 3D
    for mid, pts in estimator.marker_3d_map.items():
        assert pts.shape == (4, 3)
        assert np.all(pts[:, 2] == 0.0)  # Mặt phẳng Z = 0


def test_board_grid_coord_to_square():
    """Kiểm tra ánh xạ tọa độ (X, Y) sang tên ô cờ."""
    grid = BoardGrid8x8(square_size_mm=40.0)

    # Ô A1: X in [0, 40], Y in [0, 40]
    assert grid.coord_to_square(20.0, 20.0) == "a1"

    # Ô H1: X in [280, 320], Y in [0, 40]
    assert grid.coord_to_square(300.0, 20.0) == "h1"

    # Ô A8: X in [0, 40], Y in [280, 320]
    assert grid.coord_to_square(20.0, 300.0) == "a8"

    # Ô H8: X in [280, 320], Y in [280, 320]
    assert grid.coord_to_square(300.0, 300.0) == "h8"

    # Ô E4: Col E (index 4: X in [160, 200]), Row 4 (index 3: Y in [120, 160])
    assert grid.coord_to_square(180.0, 140.0) == "e4"

    # Nằm ngoài bàn cờ
    assert grid.coord_to_square(-50.0, 20.0) is None
    assert grid.coord_to_square(400.0, 20.0) is None


def test_board_grid_square_to_center():
    """Kiểm tra tính tọa độ tâm ô cờ từ tên ô."""
    grid = BoardGrid8x8(square_size_mm=40.0)

    center_a1 = grid.square_to_center("a1")
    assert center_a1 == (20.0, 20.0)

    center_h1 = grid.square_to_center("h1")
    assert center_h1 == (300.0, 20.0)

    center_e4 = grid.square_to_center("e4")
    assert center_e4 == (180.0, 140.0)

    assert grid.square_to_center("invalid") is None


def test_assign_pieces_to_squares():
    """Kiểm tra gán ô cờ cho danh sách quân cờ phát hiện và xử lý xung đột."""
    grid = BoardGrid8x8(square_size_mm=40.0)

    # Kịch bản 1: Hai quân cờ ở 2 ô riêng biệt
    pieces = [
        {
            "class_name": "white_king",
            "fen_char": "K",
            "confidence": 0.95,
            "position_3d": np.array([180.0, 140.0, 0.0]),  # Ô e4
        },
        {
            "class_name": "black_queen",
            "fen_char": "q",
            "confidence": 0.90,
            "position_3d": np.array([140.0, 180.0, 0.0]),  # Ô d5
        },
    ]

    assigned = grid.assign_pieces_to_squares(pieces)
    assert assigned[0]["square"] == "e4"
    assert assigned[1]["square"] == "d5"


def test_assign_pieces_conflict_resolution():
    """Kiểm tra xử lý xung đột: 2 quân cờ bị chiếu rơi gần cùng 1 ô."""
    grid = BoardGrid8x8(square_size_mm=40.0)

    # 2 quân cờ đều gần ô e4 (tâm e4 là 180, 140)
    pieces = [
        {
            "class_name": "white_pawn",
            "fen_char": "P",
            "confidence": 0.90,
            "position_3d": np.array([181.0, 140.0, 0.0]),
        },
        {
            "class_name": "black_pawn",
            "fen_char": "p",
            "confidence": 0.85,
            "position_3d": np.array([195.0, 140.0, 0.0]),
        },
    ]

    assigned = grid.assign_pieces_to_squares(pieces)
    # Quân 1 chiếm ô e4
    assert assigned[0]["square"] == "e4"
    # Quân 2 được phân xử gán sang ô lân cận trống
    assert assigned[1]["square"] != "e4"
    assert assigned[1]["square"] is not None


def test_fen_generation():
    """Kiểm tra sinh chuỗi FEN từ các quân cờ đã gán ô."""
    grid = BoardGrid8x8(square_size_mm=40.0)

    # Đặt Vua Trắng ở e1 (K) và Vua Đen ở e8 (k)
    pieces = [
        {"square": "e1", "fen_char": "K"},
        {"square": "e8", "fen_char": "k"},
    ]

    fen = grid.generate_fen(pieces)
    # Hàng 8: e8 có 'k' -> 4k3
    # Hàng 7..2: 8/8/8/8/8/8
    # Hàng 1: e1 có 'K' -> 4K3
    expected_fen = "4k3/8/8/8/8/8/8/4K3"
    assert fen == expected_fen


def test_compensate_piece_occlusions():
    """Kiểm tra thuật toán bù che khuất theo độ sâu."""
    # Quân 1 (phía trước, y2=400): White Pawn
    # Quân 2 (phía sau, y2=320, chân đế nằm trong bbox của quân 1): Black Bishop
    pieces = [
        {
            "class_name": "white_pawn",
            "bbox": [100.0, 250.0, 150.0, 400.0],
            "bottom_center_pixel": (125.0, 400.0),
        },
        {
            "class_name": "black_bishop",
            "bbox": [105.0, 200.0, 145.0, 270.0],
            "bottom_center_pixel": (125.0, 270.0),
        },
    ]

    compensated = compensate_piece_occlusions(pieces)
    # Quân 1 phía trước không bị che
    p_front = [p for p in compensated if p["class_name"] == "white_pawn"][0]
    assert not p_front.get("is_occluded", False)

    # Quân 2 phía sau bị che bởi quân 1
    p_back = [p for p in compensated if p["class_name"] == "black_bishop"][0]
    assert p_back.get("is_occluded", False)


def test_chessboard_pose_estimator_synthetic(dummy_camera):
    """Kiểm tra ChessboardPoseEstimator giải tư thế đúng với tập điểm giả lập."""
    cfg_file = ROOT / "configs" / "banco_8x8.yaml"
    estimator = ChessboardPoseEstimator(camera=dummy_camera, board_config=cfg_file)

    # Đặt camera giả lập ở (160, 160, 450) nhìn thẳng xuống bàn (quay 180 quanh trục X)
    R_true = np.diag([1.0, -1.0, -1.0]).astype(np.float64)
    rvec_true, _ = cv2.Rodrigues(R_true)
    tvec_true = np.array([-160.0, 160.0, 450.0], dtype=np.float64)

    # Chiếu các góc của 4 marker (ID 17, 16, 15, 5) lên ảnh 2D
    test_ids = [17, 16, 15, 5]
    obj_pts = np.vstack([estimator.marker_3d_map[mid] for mid in test_ids])
    img_pts, _ = cv2.projectPoints(obj_pts, rvec_true, tvec_true, dummy_camera.K, dummy_camera.dist)
    img_pts = img_pts.reshape(-1, 2)

    # Khởi tạo frame đen và vẽ marker corners tương ứng
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    # Mock detector object trả về các điểm này
    mock_corners = [img_pts[i * 4:(i + 1) * 4].reshape(1, 4, 2).astype(np.float32) for i in range(len(test_ids))]
    mock_ids = np.array([[mid] for mid in test_ids], dtype=np.int32)
    mock_detector = MagicMock()
    mock_detector.detectMarkers.return_value = (mock_corners, mock_ids, [])
    estimator.detector = mock_detector

    pose = estimator.estimate(frame)
    assert pose.valid
    assert pose.board_type == "chessboard_8x8"
    assert pose.reproj_error_px < 0.1
    c = pose.camera_center
    assert pytest.approx(c[0], abs=1.0) == 160.0
    assert pytest.approx(c[1], abs=1.0) == 160.0
    assert pytest.approx(c[2], abs=1.0) == 450.0


def test_unified_pose_estimator_auto_mode(dummy_camera):
    """Kiểm tra UnifiedPoseEstimator chuyển đổi chế độ chính xác."""
    unified = UnifiedPoseEstimator(camera=dummy_camera, mode="auto")

    # Mock cả 2 estimator
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    # Khi chessboard hợp lệ còn charuco không hợp lệ
    unified.chessboard_estimator.estimate = MagicMock(
        return_value=CameraPose(valid=True, reproj_error_px=0.8, board_type="chessboard_8x8")
    )
    unified.charuco_estimator.estimate = MagicMock(
        return_value=CameraPose(valid=False, board_type="charuco")
    )

    pose = unified.estimate(frame)
    assert pose.valid
    assert pose.board_type == "chessboard_8x8"

    # Khi charuco hợp lệ còn chessboard không hợp lệ
    unified.chessboard_estimator.estimate = MagicMock(
        return_value=CameraPose(valid=False, board_type="chessboard_8x8")
    )
    unified.charuco_estimator.estimate = MagicMock(
        return_value=CameraPose(valid=True, reproj_error_px=0.5, board_type="charuco")
    )

    pose2 = unified.estimate(frame)
    assert pose2.valid
    assert pose2.board_type == "charuco"


def test_chessboard_real_image_detection(phone_camera):
    """Kiểm tra phát hiện và giải Pose trên ảnh thật picchess/banco.jpg."""
    img_path = ROOT / "picchess" / "banco.jpg"
    if not img_path.is_file():
        pytest.skip("Không tìm thấy ảnh banco.jpg")

    frame = cv2.imread(str(img_path))
    if frame is None:
        pytest.skip("Không thể đọc ảnh banco.jpg")

    estimator = ChessboardPoseEstimator(
        camera=phone_camera,
        board_config=ROOT / "configs" / "banco_8x8.yaml",
        min_markers=2,
        max_reproj_error_px=10.0,
    )

    pose = estimator.estimate(frame)
    assert pose.valid
    assert pose.board_type == "chessboard_8x8"
    assert pose.num_corners >= 16  # Tìm thấy ít nhất 4 marker (16 corners)
    assert pose.reproj_error_px < 10.0
