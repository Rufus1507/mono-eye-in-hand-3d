"""Unit tests cho mono_eye modules (không cần hardware)."""
from pathlib import Path
import cv2
import numpy as np
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_config_loading():
    """Test load config."""
    config_path = ROOT / "configs" / "mono3d.yaml"
    assert config_path.exists(), "mono3d.yaml not found"

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    assert config["units"] == "mm"
    assert "camera" in config
    assert "board" in config


def test_logging_schema():
    """Test logging schema is defined."""
    config_path = ROOT / "configs" / "mono3d.yaml"
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    assert "logging" in config
    assert config["logging"]["enabled"] is True
    assert "columns" in config["logging"]

    expected_columns = [
        "timestamp",
        "frame_id",
        "num_charuco_corners",
        "camera_x_mm",
        "camera_y_mm",
        "camera_z_mm",
    ]
    for col in expected_columns:
        assert col in config["logging"]["columns"], f"Missing column: {col}"


def test_board_config_exists():
    """Test board config file exists."""
    config_path = ROOT / "configs" / "mono3d.yaml"
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    board_file = ROOT / config["board"]["file"]
    assert board_file.exists(), f"Board config {board_file} not found"


def test_camera_matrix_structure():
    """Test camera calibration file structure (if exists)."""
    calib_file = ROOT / "data" / "calib" / "camera.yaml"

    if not calib_file.exists():
        pytest.skip("camera.yaml not yet created (Giai đoạn 2)")

    with open(calib_file, encoding="utf-8") as f:
        content = f.read()

    assert "camera_matrix:" in content
    assert "distortion_coefficients:" in content


def test_numpy_operations():
    """Test numpy operations used in mono_eye."""
    rvec = np.array([0.1, 0.2, 0.3])
    R, _ = cv2.Rodrigues(rvec)
    assert R.shape == (3, 3)

    tvec = np.array([100, 50, 200])
    C = -R.T @ tvec
    assert C.shape == (3,)


def test_ray_plane_intersection():
    """Test ray-plane intersection logic."""
    camera_center = np.array([0, 0, 500])
    ray_direction = np.array([0.1, 0.1, -1], dtype=np.float64)
    ray_direction = ray_direction / np.linalg.norm(ray_direction)

    plane_z = 0.0
    t = (plane_z - camera_center[2]) / ray_direction[2]
    intersection = camera_center + t * ray_direction

    assert abs(intersection[2] - plane_z) < 0.001, f"z={intersection[2]} != {plane_z}"
