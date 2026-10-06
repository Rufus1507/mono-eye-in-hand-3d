"""Unit tests cho module Improvements & Filtering (Giai đoạn 8)."""
from __future__ import annotations

import numpy as np
import pytest

from mono_eye.camera_io import CameraModel
from mono_eye.detect import Detection, DetectionResult, ObjectDetector
from mono_eye.filter import (
    KalmanTracker3D,
    TemporalSmoother,
    aggregate_observations,
    filter_parallel_ray,
    triangulate_two_views,
)
from mono_eye.pipeline import MonoEyePipeline


def test_filter_parallel_ray():
    """Kiểm tra hàm lọc tia chiếu dốc / gần song song mặt bàn."""
    # Tia chiếu thẳng đứng xuống bàn
    assert filter_parallel_ray(np.array([0.0, 0.0, -1.0])) is True

    # Tia xiên 45 độ
    assert filter_parallel_ray(np.array([1.0, 0.0, -1.0]), min_z_abs=0.1) is True

    # Tia gần song song mặt bàn (vz rất bé)
    assert filter_parallel_ray(np.array([100.0, 0.0, 0.05]), min_z_abs=0.1) is False

    # Tia hoàn toàn nằm ngang
    assert filter_parallel_ray(np.array([1.0, 1.0, 0.0])) is False

    # Tia rỗng / vector 0
    assert filter_parallel_ray(np.array([0.0, 0.0, 0.0])) is False


def test_aggregate_observations():
    """Kiểm tra tổng hợp danh sách các phép đo tọa độ 3D."""
    # Tập hợp các điểm có một outlier lớn
    obs = [
        np.array([100.0, 200.0, 0.0]),
        np.array([101.0, 199.0, 0.0]),
        np.array([99.0, 201.0, 0.0]),
        np.array([100.0, 200.0, 0.0]),
        np.array([500.0, 800.0, 0.0]),  # Outlier
    ]

    # Median kháng outlier tốt
    med = aggregate_observations(obs, method="median")
    assert med is not None
    assert np.allclose(med, [100.0, 200.0, 0.0], atol=1.5)

    # Mean bị kéo lệch bởi outlier
    mean_val = aggregate_observations(obs, method="mean")
    assert mean_val is not None
    assert mean_val[0] > 150.0

    # Danh sách rỗng
    assert aggregate_observations([]) is None


def test_temporal_smoother():
    """Kiểm tra bộ làm mượt tọa độ 3D theo thời gian TemporalSmoother."""
    smoother = TemporalSmoother(window_size=3, method="mean")

    # Đối tượng track_id = 1
    p1 = smoother.update(1, np.array([10.0, 20.0, 0.0]))
    assert np.allclose(p1, [10.0, 20.0, 0.0])

    p2 = smoother.update(1, np.array([20.0, 40.0, 0.0]))
    assert np.allclose(p2, [15.0, 30.0, 0.0])

    p3 = smoother.update(1, np.array([30.0, 60.0, 0.0]))
    assert np.allclose(p3, [20.0, 40.0, 0.0])

    # Đối tượng track_id = 2 độc lập hoàn toàn
    p_other = smoother.update(2, np.array([100.0, 100.0, 0.0]))
    assert np.allclose(p_other, [100.0, 100.0, 0.0])

    # Reset smoother
    smoother.reset(1)
    p1_new = smoother.update(1, np.array([50.0, 50.0, 0.0]))
    assert np.allclose(p1_new, [50.0, 50.0, 0.0])


def test_kalman_tracker_3d():
    """Kiểm tra hoạt động của bộ lọc KalmanFilter 3D."""
    init_p = np.array([0.0, 0.0, 0.0])
    kf = KalmanTracker3D(initial_position=init_p, process_noise_std=0.5, measurement_noise_std=1.0)

    # Giả lập vật thể chuyển động thẳng đều với vận tốc 10 mm/s theo trục X
    true_vx = 10.0
    dt = 0.1
    for i in range(1, 20):
        true_x = i * dt * true_vx
        kf.predict(dt=dt)
        # Đo đạc có thêm chút nhiễu
        noisy_meas = np.array([true_x + 0.2 * np.sin(i), 0.0, 0.0])
        kf.update(noisy_meas)

    # Sau 20 bước, tọa độ ước lượng phải tiệm cận vị trí thực tế
    final_true_x = 20 * dt * true_vx
    kf.predict(dt=dt)
    assert pytest.approx(kf.position[0], abs=2.0) == final_true_x
    assert pytest.approx(kf.position[1], abs=1.0) == 0.0
    assert pytest.approx(kf.position[2], abs=1.0) == 0.0


def test_triangulate_two_views():
    """Kiểm tra tam giác đạc 3D từ hai góc nhìn camera."""
    # Điểm mục tiêu cần tái tạo trong không gian 3D
    target_3d = np.array([50.0, 80.0, 25.0])

    # Camera 1 đặt tại (0, -100, 400)
    c1 = np.array([0.0, -100.0, 400.0])
    dir1 = target_3d - c1

    # Camera 2 đặt tại (150, -50, 350)
    c2 = np.array([150.0, -50.0, 350.0])
    dir2 = target_3d - c2

    success, point_rec, skew = triangulate_two_views(c1, dir1, c2, dir2)

    assert success is True
    assert point_rec is not None
    assert np.allclose(point_rec, target_3d, atol=1e-4)
    assert skew < 1e-4

    # Trường hợp 2 tia song song
    parallel_dir = np.array([0.0, 0.0, -1.0])
    succ_par, pt_par, _ = triangulate_two_views(
        np.array([0, 0, 300]), parallel_dir,
        np.array([50, 0, 300]), parallel_dir,
    )
    assert succ_par is False
    assert pt_par is None

    # Trường hợp điểm nằm sau camera (hướng ngược)
    succ_behind, _, _ = triangulate_two_views(c1, -dir1, c2, -dir2)
    assert succ_behind is False


def test_pipeline_with_smoothing():
    """Kiểm tra tích hợp TemporalSmoother trong MonoEyePipeline."""
    dummy_cam = CameraModel(
        K=np.array([[900.0, 0, 640], [0, 900.0, 360], [0, 0, 1]], dtype=np.float64),
        dist=np.zeros(5, dtype=np.float64),
        width=1280,
        height=720,
    )

    class MockDetector:
        def detect(self, *args, **kwargs):
            det = Detection(
                track_id=1,
                class_id=0,
                class_name="bottle",
                bbox=np.array([100, 100, 200, 200]),
                confidence=0.9,
                reference_pixel=(150.0, 200.0),
                position_3d=np.array([50.0, 100.0, 0.0]),
            )
            return DetectionResult(
                timestamp=1.0,
                frame_id=kwargs.get("frame_id", 0),
                detections=[det],
            )

    pipe = MonoEyePipeline(
        camera=dummy_cam,
        detector=MockDetector(),
        enable_smoothing=True,
        smooth_window=3,
    )

    assert pipe.smoother is not None

    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    pose, det_res = pipe.process_frame(frame, detect_objects=True)
    assert det_res is not None
    assert len(det_res.detections) == 1
    assert np.allclose(det_res.detections[0].position_3d, [50.0, 100.0, 0.0])
