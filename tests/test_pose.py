"""Unit tests cho mono_eye/pose.py (Camera Pose Estimation)."""
from pathlib import Path
import cv2
import numpy as np
import pytest

from mono_eye.camera_io import CameraModel
from mono_eye.config import ROOT
from mono_eye.pose import CameraPose, PoseEstimator

BOARD_CONFIG = ROOT / "bang_calib_A4.yaml"


@pytest.fixture
def dummy_camera():
    """Tạo CameraModel chuẩn 1280x720 với fx=fy=900, cx=640, cy=360."""
    K = np.array(
        [[900.0, 0.0, 640.0], [0.0, 900.0, 360.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    dist = np.zeros(5, dtype=np.float64)
    return CameraModel(K=K, dist=dist, width=1280, height=720)


def test_camera_pose_rotation_matrix():
    """Test Rodrigues conversion và tính chất trực giao của ma trận R."""
    rvec = np.array([0.1, 0.2, 0.3], dtype=np.float64)
    pose = CameraPose(valid=True, rvec=rvec, tvec=np.zeros(3))

    R = pose.rotation_matrix
    assert R is not None
    assert R.shape == (3, 3)
    # R * R^T = I
    assert np.allclose(R @ R.T, np.eye(3), atol=1e-6)
    # det(R) = 1 (proper rotation)
    assert np.isclose(np.linalg.det(R), 1.0)


def test_camera_pose_center():
    """Test tính toán tâm camera trong world frame: C = -R^T @ tvec."""
    # Trường hợp 1: Không quay (R = I), camera ở độ cao 100 mm nhìn xuống
    pose_simple = CameraPose(
        valid=True,
        rvec=np.zeros(3),
        tvec=np.array([0.0, 0.0, -100.0]),
    )
    C_simple = pose_simple.camera_center
    assert C_simple is not None
    assert np.allclose(C_simple, [0.0, 0.0, 100.0])

    # Trường hợp 2: Góc quay bất kỳ và vị trí camera bất kỳ
    target_center = np.array([150.0, -80.0, 450.0], dtype=np.float64)
    rand_rvec = np.array([0.25, -0.15, 0.40], dtype=np.float64)
    R_rand, _ = cv2.Rodrigues(rand_rvec)
    t_rand = -R_rand @ target_center

    pose_arbitrary = CameraPose(valid=True, rvec=rand_rvec, tvec=t_rand)
    C_calc = pose_arbitrary.camera_center
    assert np.allclose(C_calc, target_center, atol=1e-5)


def test_camera_pose_euler_degrees_and_helpers():
    """Test trích xuất góc Euler (roll, pitch, yaw) và tọa độ vị trí."""
    rvec = np.zeros(3, dtype=np.float64)
    tvec = np.array([12.0, 34.0, 56.0], dtype=np.float64)
    pose = CameraPose(valid=True, rvec=rvec, tvec=tvec)

    eulers = pose.euler_degrees
    assert eulers is not None
    assert len(eulers) == 3
    assert np.allclose(eulers, [0.0, 0.0, 0.0])

    assert pose.roll_deg == pytest.approx(0.0)
    assert pose.pitch_deg == pytest.approx(0.0)
    assert pose.yaw_deg == pytest.approx(0.0)

    # C = -I @ [12, 34, 56] = [-12, -34, -56]
    assert pose.camera_x_mm == pytest.approx(-12.0)
    assert pose.camera_y_mm == pytest.approx(-34.0)
    assert pose.camera_z_mm == pytest.approx(-56.0)


def test_camera_pose_invalid_returns_none():
    """Test CameraPose không có rvec/tvec thì các properties trả về None."""
    pose = CameraPose(valid=False)
    assert pose.rotation_matrix is None
    assert pose.camera_center is None
    assert pose.euler_degrees is None
    assert pose.camera_x_mm is None
    assert pose.camera_y_mm is None
    assert pose.camera_z_mm is None
    assert pose.pitch_deg is None


def test_pose_estimator_init(dummy_camera):
    """Test khởi tạo PoseEstimator với config bảng."""
    estimator = PoseEstimator(
        dummy_camera,
        board_config=BOARD_CONFIG,
        min_corners=6,
        max_reproj_error_px=1.5,
    )

    assert estimator.camera is dummy_camera
    assert estimator.min_corners == 6
    assert estimator.max_reproj_error == 1.5
    assert estimator.square_size_mm == pytest.approx(21.421, rel=1e-3)
    assert estimator.board.getChessboardCorners().shape[0] == 60


def test_frame_size_check(dummy_camera):
    """Test PoseEstimator từ chối khung hình sai kích thước chuẩn."""
    estimator = PoseEstimator(dummy_camera, board_config=BOARD_CONFIG)

    wrong_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    pose = estimator.estimate(wrong_frame)
    assert not pose.valid


def test_quality_gate_min_corners(dummy_camera):
    """Test khung hình đen/trống (không có góc) trả về invalid pose."""
    estimator = PoseEstimator(dummy_camera, board_config=BOARD_CONFIG)

    blank_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    pose = estimator.estimate(blank_frame)
    assert not pose.valid
    assert pose.num_corners == 0


def test_synthetic_corners_pose_recovery(dummy_camera):
    """Kiểm tra khôi phục pose hoàn hảo từ điểm chiếu giả lập (synthetic)."""
    estimator = PoseEstimator(dummy_camera, board_config=BOARD_CONFIG)

    # Camera ở độ cao Z=400 mm nhìn xuống mặt bàn:
    # Trục quang học +Z_cam hướng về phía mặt bàn (-Z_world),
    # tương ứng với phép quay ~180 độ (np.pi) quanh trục X kèm độ nghiêng nhẹ.
    true_C = np.array([100.0, 80.0, 400.0], dtype=np.float64)
    true_rvec = np.array([np.pi - 0.1, 0.05, 0.0], dtype=np.float64)
    true_R, _ = cv2.Rodrigues(true_rvec)
    true_tvec = -true_R @ true_C

    # Lấy toàn bộ 60 object points thật của bảng ChArUco (mm)
    all_obj_pts = estimator.board.getChessboardCorners().reshape(-1, 3) * estimator.square_size_mm
    all_ids = np.arange(len(all_obj_pts), dtype=np.int32).reshape(-1, 1)

    # Chiếu sang mặt phẳng ảnh bằng camera matrix K và dist=0
    proj_pts, _ = cv2.projectPoints(
        all_obj_pts,
        true_rvec,
        true_tvec,
        dummy_camera.K,
        dummy_camera.dist,
    )

    # Ước lượng pose qua estimate_from_corners
    pose = estimator.estimate_from_corners(proj_pts, all_ids)

    assert pose.valid is True
    assert pose.num_corners == 60
    assert pose.reproj_error_px < 0.05  # Sai số cực nhỏ trên dữ liệu chuẩn
    assert np.allclose(pose.rvec, true_rvec, atol=1e-3)
    assert np.allclose(pose.tvec, true_tvec, atol=1e-2)
    assert np.allclose(pose.camera_center, true_C, atol=1e-2)


def test_quality_gate_reproj_error_rejection(dummy_camera):
    """Kiểm tra từ chối pose khi nhiễu góc ảnh vượt quá max_reproj_error_px."""
    estimator = PoseEstimator(
        dummy_camera,
        board_config=BOARD_CONFIG,
        max_reproj_error_px=1.5,
    )

    true_C = np.array([100.0, 80.0, 400.0], dtype=np.float64)
    true_rvec = np.array([np.pi - 0.1, 0.05, 0.0], dtype=np.float64)
    true_R, _ = cv2.Rodrigues(true_rvec)
    true_tvec = -true_R @ true_C

    all_obj_pts = estimator.board.getChessboardCorners().reshape(-1, 3) * estimator.square_size_mm
    all_ids = np.arange(len(all_obj_pts), dtype=np.int32).reshape(-1, 1)

    proj_pts, _ = cv2.projectPoints(
        all_obj_pts,
        true_rvec,
        true_tvec,
        dummy_camera.K,
        dummy_camera.dist,
    )

    # Thêm nhiễu lớn (±15 pixels ngẫu nhiên) vào góc ảnh
    rng = np.random.default_rng(42)
    noisy_pts = proj_pts + rng.normal(0.0, 15.0, proj_pts.shape)

    pose = estimator.estimate_from_corners(noisy_pts, all_ids)
    assert not pose.valid
    assert pose.reproj_error_px > 1.5

