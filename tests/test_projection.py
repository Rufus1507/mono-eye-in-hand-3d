"""Unit tests cho mono_eye/projection.py (Pixel to 3D Projection)."""
import numpy as np
import pytest

from mono_eye.camera_io import CameraModel
from mono_eye.pose import CameraPose
from mono_eye.projection import (
    ProjectionProcessor,
    pixel_to_3d,
    pixel_to_ray,
    ray_plane_intersection,
    undistort_pixel,
)


def test_undistort_pixel():
    """Test khử méo tọa độ điểm ảnh."""
    K = np.array(
        [[1000.0, 0.0, 640.0], [0.0, 1000.0, 360.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    dist = np.array([0.1, 0.01, 0.0, 0.0, 0.0], dtype=np.float64)

    pixel = (700.0, 400.0)
    pixel_undist = undistort_pixel(pixel, K, dist)

    assert pixel_undist.shape == (2,)
    assert pixel_undist.dtype == np.float64
    # Với hệ số méo dương (barrel), điểm sau khi khử méo sẽ bị kéo ra xa tâm hơn
    assert not np.allclose(pixel_undist, pixel)


def test_pixel_to_ray():
    """Test chuyển pixel sang vector hướng tia trong hệ camera."""
    K = np.array(
        [[1000.0, 0.0, 640.0], [0.0, 1000.0, 360.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )

    # Pixel trung tâm quang học (cx, cy) -> tia hướng dọc trục +Z [0, 0, 1]
    ray_center = pixel_to_ray((640.0, 360.0), K)
    assert np.allclose(ray_center, [0.0, 0.0, 1.0], atol=1e-6)
    assert np.isclose(np.linalg.norm(ray_center), 1.0)

    # Pixel lệch sang phải (cx + 1000, cy) -> tia góc 45 độ (1, 0, 1) / sqrt(2)
    ray_right = pixel_to_ray((1640.0, 360.0), K)
    expected_right = np.array([1.0, 0.0, 1.0]) / np.sqrt(2.0)
    assert np.allclose(ray_right, expected_right, atol=1e-6)
    assert np.isclose(np.linalg.norm(ray_right), 1.0)


def test_ray_plane_intersection():
    """Test giao tia chiếu thẳng đứng với mặt phẳng z = 0."""
    origin = np.array([0.0, 0.0, 500.0])
    direction = np.array([0.0, 0.0, -1.0])  # Hướng thẳng xuống bàn

    success, point = ray_plane_intersection(origin, direction, plane_z=0.0)

    assert success is True
    assert point is not None
    assert np.allclose(point, [0.0, 0.0, 0.0], atol=1e-6)


def test_ray_plane_intersection_slanted():
    """Test giao tia nghiêng 45 độ với mặt phẳng z = 0."""
    origin = np.array([0.0, 0.0, 500.0])
    direction = np.array([1.0, 0.0, -1.0]) / np.sqrt(2.0)

    success, point = ray_plane_intersection(origin, direction, plane_z=0.0)

    assert success is True
    assert point is not None
    assert point[2] == pytest.approx(0.0)
    assert point[0] == pytest.approx(500.0)
    assert point[1] == pytest.approx(0.0)


def test_ray_parallel_to_plane():
    """Test tia song song với mặt bàn (không giao nhau)."""
    origin = np.array([0.0, 0.0, 100.0])
    direction = np.array([1.0, 0.0, 0.0])  # Tia nằm ngang song song mặt bàn

    success, point = ray_plane_intersection(origin, direction, plane_z=0.0)
    assert success is False
    assert point is None


def test_ray_behind_camera():
    """Test tia hướng ngược ra sau/xa khỏi mặt bàn (t < 0)."""
    origin = np.array([0.0, 0.0, 500.0])
    direction = np.array([0.0, 0.0, 1.0])  # Hướng lên trời, xa khỏi mặt bàn z=0

    success, point = ray_plane_intersection(origin, direction, plane_z=0.0)
    assert success is False
    assert point is None


def test_pixel_to_3d_integration():
    """Integration test: quy trình đầy đủ từ pixel sang 3D với CameraPose."""
    K = np.array(
        [[1000.0, 0.0, 640.0], [0.0, 1000.0, 360.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    dist = np.zeros(5, dtype=np.float64)

    # Pose 1: Camera đặt ở (0, 0, -500), tvec=[0, 0, 500], rvec=[0, 0, 0]
    # ray hướng +Z_cam -> giao tại (0, 0, 0)
    pose = CameraPose(
        valid=True,
        rvec=np.zeros(3),
        tvec=np.array([0.0, 0.0, 500.0]),
        num_corners=20,
        reproj_error_px=0.5,
    )

    success, point = pixel_to_3d((640.0, 360.0), pose, K, dist, plane_z=0.0)
    assert success is True
    assert point is not None
    assert np.allclose(point, [0.0, 0.0, 0.0], atol=1e-4)


def test_pixel_to_3d_downward_camera():
    """Kiểm tra camera thực tế đặt trên bàn nhìn chúc xuống z=0."""
    K = np.array(
        [[1000.0, 0.0, 640.0], [0.0, 1000.0, 360.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    dist = np.zeros(5, dtype=np.float64)

    # Camera ở vị trí (150, 200, 400) mm, nhìn thẳng chúc xuống bàn (+Z_cam -> -Z_world)
    true_C = np.array([150.0, 200.0, 400.0], dtype=np.float64)
    rvec = np.array([np.pi, 0.0, 0.0], dtype=np.float64)
    R, _ = cv2_import_rodrigues(rvec)
    tvec = -R @ true_C

    pose = CameraPose(valid=True, rvec=rvec, tvec=tvec, num_corners=25)

    # Điểm ảnh tâm (640, 360) phải rơi trúng ngay vị trí (150, 200, 0)
    success, point = pixel_to_3d((640.0, 360.0), pose, K, dist, plane_z=0.0)
    assert success is True
    assert point is not None
    assert np.allclose(point, [150.0, 200.0, 0.0], atol=1e-4)


def test_projection_processor():
    """Test ProjectionProcessor và phương thức project / project_batch."""
    K = np.array(
        [[1000.0, 0.0, 640.0], [0.0, 1000.0, 360.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    dist = np.zeros(5, dtype=np.float64)

    processor = ProjectionProcessor(K, dist, plane_z=0.0)

    pose = CameraPose(
        valid=True,
        rvec=np.zeros(3),
        tvec=np.array([0.0, 0.0, 500.0]),
    )

    success, point = processor.project((640.0, 360.0), pose)
    assert success is True
    assert point is not None
    assert np.allclose(point, [0.0, 0.0, 0.0], atol=1e-4)

    # Batch projection
    pixels = [(640.0, 360.0), (740.0, 360.0)]
    results = processor.project_batch(pixels, pose)
    assert len(results) == 2
    assert results[0][0] is True
    assert results[1][0] is True


def test_projection_processor_from_camera():
    """Test khởi tạo ProjectionProcessor từ CameraModel."""
    K = np.eye(3, dtype=np.float64)
    dist = np.zeros(5, dtype=np.float64)
    cam = CameraModel(K=K, dist=dist, width=1280, height=720)

    processor = ProjectionProcessor.from_camera(cam, plane_z=10.0)
    assert np.allclose(processor.K, K)
    assert processor.plane_z == 10.0


def test_pixel_to_3d_invalid_pose():
    """Test khi CameraPose không hợp lệ trả về (False, None)."""
    K = np.eye(3)
    dist = np.zeros(5)
    pose = CameraPose(valid=False)

    success, point = pixel_to_3d((100.0, 100.0), pose, K, dist)
    assert success is False
    assert point is None


def cv2_import_rodrigues(rvec):
    import cv2
    return cv2.Rodrigues(rvec)
