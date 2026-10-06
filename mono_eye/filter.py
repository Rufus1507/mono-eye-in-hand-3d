"""Giai đoạn 8 - Improvements, Filtering, Temporal Smoothing & Multi-view Triangulation."""
from __future__ import annotations

from collections import deque
from typing import Optional, Sequence
import numpy as np


def filter_parallel_ray(ray_world: np.ndarray, min_z_abs: float = 0.1) -> bool:
    """Kiểm tra xem tia chiếu có hợp lệ đối với mặt phẳng bàn z = const không.

    Loại bỏ các tia chiếu gần song song với mặt bàn (|v_z| < min_z_abs)
    vì ở góc chiếu quá nông, một sai số pixel cực nhỏ trên ảnh sẽ bị phóng đại
    thành sai số tọa độ mặt bàn khổng lồ.

    Args:
        ray_world: Vector hướng tia trong world frame (shape (3,)).
        min_z_abs: Ngưỡng tối thiểu của |v_z| (mặc định 0.1, ~5.7 độ).

    Returns:
        True nếu tia đủ dốc để giao cắt đáng tin cậy, False nếu quá nông.
    """
    v = np.asarray(ray_world, dtype=np.float64).reshape(-1)
    norm = np.linalg.norm(v)
    if norm < 1e-9:
        return False
    unit_v = v / norm
    return bool(abs(unit_v[2]) >= min_z_abs)


def aggregate_observations(
    positions: Sequence[np.ndarray],
    method: str = "median",
) -> Optional[np.ndarray]:
    """Tổng hợp một tập hợp các quan sát tọa độ 3D của cùng một đối tượng.

    Args:
        positions: Danh sách hoặc mảng các điểm 3D [x, y, z].
        method: Phương pháp tổng hợp ("median" hoặc "mean").

    Returns:
        Tọa độ tổng hợp shape (3,) hoặc None nếu danh sách rỗng.
    """
    if not positions:
        return None

    pts = np.asarray(positions, dtype=np.float64)
    if len(pts) == 0:
        return None

    if method == "mean":
        return np.mean(pts, axis=0)
    return np.median(pts, axis=0)


def triangulate_two_views(
    origin1: np.ndarray,
    dir1: np.ndarray,
    origin2: np.ndarray,
    dir2: np.ndarray,
    max_skew_distance: float = 50.0,
) -> tuple[bool, Optional[np.ndarray], float]:
    """Định vị 3D qua tam giác đạc từ hai góc nhìn camera (không cần giả định z=0).

    Tìm đoạn vuông góc chung ngắn nhất giữa hai tia 3D trong không gian:
    tia 1: r1(t1) = origin1 + t1 * dir1
    tia 2: r2(t2) = origin2 + t2 * dir2

    Args:
        origin1: Vị trí camera 1 (C1).
        dir1: Hướng tia nhìn từ camera 1 (đã chuẩn hóa hoặc chưa).
        origin2: Vị trí camera 2 (C2).
        dir2: Hướng tia nhìn từ camera 2.
        max_skew_distance: Khoảng cách lệch tối đa giữa 2 tia cho phép (mm).

    Returns:
        tuple (success, point_3d, skew_distance):
        - success: True nếu hai tia giao nhau/gần nhau hợp lệ và nằm phía trước cả 2 camera.
        - point_3d: Trung điểm của đoạn vuông góc chung (mm), hoặc None nếu thất bại.
        - skew_distance: Khoảng cách ngắn nhất giữa hai tia (mm).
    """
    p1 = np.asarray(origin1, dtype=np.float64).reshape(3)
    d1 = np.asarray(dir1, dtype=np.float64).reshape(3)
    p2 = np.asarray(origin2, dtype=np.float64).reshape(3)
    d2 = np.asarray(dir2, dtype=np.float64).reshape(3)

    norm1 = np.linalg.norm(d1)
    norm2 = np.linalg.norm(d2)
    if norm1 < 1e-9 or norm2 < 1e-9:
        return False, None, float("inf")

    u1 = d1 / norm1
    u2 = d2 / norm2

    # Vector nối hai gốc
    dp = p1 - p2
    a = float(np.dot(u1, u1))  # = 1.0
    b = float(np.dot(u1, u2))
    c = float(np.dot(u2, u2))  # = 1.0
    d = float(np.dot(u1, dp))
    e = float(np.dot(u2, dp))

    denom = a * c - b * b  # 1 - cos^2(theta) = sin^2(theta)
    if abs(denom) < 1e-6:
        # Hai tia song song hoặc gần song song
        return False, None, float("inf")

    # Tham số t1, t2 sao cho khoảng cách giữa hai điểm nhỏ nhất
    t1 = (b * e - c * d) / denom
    t2 = (a * e - b * d) / denom

    # Điểm phải nằm PHÍA TRƯỚC cả hai camera (t1 > 0 và t2 > 0)
    if t1 <= 0.0 or t2 <= 0.0:
        return False, None, float("inf")

    pt1 = p1 + t1 * u1
    pt2 = p2 + t2 * u2

    skew_dist = float(np.linalg.norm(pt1 - pt2))
    midpoint = (pt1 + pt2) / 2.0

    success = bool(skew_dist <= max_skew_distance)
    return success, (midpoint if success else None), skew_dist


class TemporalSmoother:
    """Bộ làm mượt tọa độ 3D theo thời gian dựa trên cửa sổ trượt (Moving Window)."""

    def __init__(self, window_size: int = 5, method: str = "median"):
        """Khởi tạo smoother.

        Args:
            window_size: Kích thước cửa sổ trượt (số khung hình).
            method: 'median' (kháng ngoại lai) hoặc 'mean' (mượt mà).
        """
        self.window_size = max(1, window_size)
        self.method = method
        self._buffers: dict[int, deque[np.ndarray]] = {}

    def update(self, track_id: int, position_3d: np.ndarray) -> np.ndarray:
        """Cập nhật tọa độ mới cho đối tượng có track_id và trả về tọa độ đã làm mượt."""
        pos = np.asarray(position_3d, dtype=np.float64).reshape(3)
        if track_id not in self._buffers:
            self._buffers[track_id] = deque(maxlen=self.window_size)

        buf = self._buffers[track_id]
        buf.append(pos)

        arr = np.array(buf)
        if self.method == "mean":
            return np.mean(arr, axis=0)
        return np.median(arr, axis=0)

    def reset(self, track_id: Optional[int] = None):
        """Xóa buffer cho một track_id hoặc toàn bộ hệ thống."""
        if track_id is None:
            self._buffers.clear()
        elif track_id in self._buffers:
            del self._buffers[track_id]


class KalmanTracker3D:
    """Bộ lọc Kalman 3D cho đối tượng chuyển động với mô hình Constant Velocity.

    Trạng thái: [x, y, z, vx, vy, vz]^T (6 chiều)
    Quan sát:   [x, y, z]^T (3 chiều)
    """

    def __init__(
        self,
        initial_position: np.ndarray,
        process_noise_std: float = 1.0,
        measurement_noise_std: float = 2.0,
    ):
        """Khởi tạo Kalman Filter 3D.

        Args:
            initial_position: Tọa độ khởi tạo [x, y, z] (mm).
            process_noise_std: Độ lệch chuẩn nhiễu mô hình động học (q).
            measurement_noise_std: Độ lệch chuẩn nhiễu đo cảm biến (r).
        """
        # Vector trạng thái x: 6x1
        p = np.asarray(initial_position, dtype=np.float64).reshape(3)
        self.x = np.array([p[0], p[1], p[2], 0.0, 0.0, 0.0], dtype=np.float64)

        # Ma trận hiệp phương sai sai số P: 6x6
        self.P = np.eye(6, dtype=np.float64) * 10.0

        # Ma trận đo H: 3x6
        self.H = np.zeros((3, 6), dtype=np.float64)
        self.H[0, 0] = 1.0
        self.H[1, 1] = 1.0
        self.H[2, 2] = 1.0

        # Ma trận nhiễu đo R: 3x3
        r_var = measurement_noise_std ** 2
        self.R = np.eye(3, dtype=np.float64) * r_var

        # Ma trận nhiễu quá trình Q: 6x6
        q_var = process_noise_std ** 2
        self.Q = np.eye(6, dtype=np.float64) * q_var

    def predict(self, dt: float = 0.033) -> np.ndarray:
        """Dự đoán trạng thái sau khoảng thời gian dt (giây)."""
        # Ma trận chuyển trạng thái F: 6x6
        F = np.eye(6, dtype=np.float64)
        F[0, 3] = dt
        F[1, 4] = dt
        F[2, 5] = dt

        self.x = F @ self.x
        self.P = F @ self.P @ F.T + self.Q
        return self.x[:3].copy()

    def update(self, measurement: np.ndarray) -> np.ndarray:
        """Cập nhật ước lượng với phép đo 3D mới."""
        z = np.asarray(measurement, dtype=np.float64).reshape(3)

        # Sai số đo (innovation) y = z - H * x
        y = z - (self.H @ self.x)

        # Hiệp phương sai innovation S = H * P * H^T + R
        S = self.H @ self.P @ self.H.T + self.R

        # Hệ số Kalman K = P * H^T * inv(S)
        K = self.P @ self.H.T @ np.linalg.inv(S)

        # Cập nhật trạng thái và hiệp phương sai
        self.x = self.x + K @ y
        I = np.eye(6, dtype=np.float64)
        self.P = (I - K @ self.H) @ self.P

        return self.x[:3].copy()

    @property
    def position(self) -> np.ndarray:
        """Tọa độ 3D hiện tại [x, y, z]."""
        return self.x[:3].copy()

    @property
    def velocity(self) -> np.ndarray:
        """Vận tốc 3D hiện tại [vx, vy, vz]."""
        return self.x[3:].copy()
