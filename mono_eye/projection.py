"""Giai đoạn 4 - Pixel to 3D projection bằng ray-plane intersection."""
from __future__ import annotations

from typing import Optional, Sequence, Tuple
import cv2
import numpy as np

from mono_eye.camera_io import CameraModel
from mono_eye.pose import CameraPose


def undistort_pixel(
    pixel: tuple[float, float] | Sequence[float] | np.ndarray,
    K: np.ndarray,
    dist: np.ndarray,
) -> np.ndarray:
    """Khử méo tọa độ điểm ảnh pixel (u, v).

    Args:
        pixel: Tọa độ pixel (u, v).
        K: Ma trận camera 3x3.
        dist: Hệ số méo (5 phần tử).

    Returns:
        Tọa độ pixel sau khi khử méo [u_undist, v_undist] dạng numpy array shape (2,).
    """
    pt = np.asarray(pixel, dtype=np.float32).reshape(1, 1, 2)
    K_mat = np.asarray(K, dtype=np.float64)
    dist_coeffs = (
        np.asarray(dist, dtype=np.float64)
        if dist is not None
        else np.zeros(5, dtype=np.float64)
    )

    # cv2.undistortPoints với P=K trả về tọa độ pixel trong cùng hệ trục ảnh gốc
    pt_undist = cv2.undistortPoints(pt, K_mat, dist_coeffs, P=K_mat).reshape(-1)
    return pt_undist.astype(np.float64)


def pixel_to_ray(
    pixel: tuple[float, float] | Sequence[float] | np.ndarray,
    K: np.ndarray,
) -> np.ndarray:
    """Chuyển tọa độ pixel đã khử méo thành vector hướng tia trong hệ tọa độ camera.

    Args:
        pixel: Tọa độ pixel (u, v).
        K: Ma trận camera 3x3.

    Returns:
        Vector hướng tia đã chuẩn hóa (unit vector), shape (3,), hướng dọc trục +Z_cam.
    """
    fx, fy = float(K[0, 0]), float(K[1, 1])
    cx, cy = float(K[0, 2]), float(K[1, 2])

    u, v = float(pixel[0]), float(pixel[1])
    ray = np.array(
        [
            (u - cx) / fx,
            (v - cy) / fy,
            1.0,
        ],
        dtype=np.float64,
    )

    norm = np.linalg.norm(ray)
    if norm > 0:
        ray = ray / norm
    return ray


def ray_plane_intersection(
    ray_origin: np.ndarray,
    ray_direction: np.ndarray,
    plane_z: float = 0.0,
) -> tuple[bool, Optional[np.ndarray]]:
    """Giao tia với mặt phẳng nằm ngang z = plane_z trong hệ tọa độ thế giới.

    Phương trình tia: P(t) = ray_origin + t * ray_direction.
    Phương trình mặt phẳng: z = plane_z.

    Args:
        ray_origin: Điểm gốc của tia (tâm camera C trong world frame), shape (3,).
        ray_direction: Vector hướng của tia trong world frame (unit vector), shape (3,).
        plane_z: Tọa độ Z của mặt phẳng bàn (mặc định 0.0 mm).

    Returns:
        (success, point_3d) với point_3d = [x, y, z] (mm) hoặc None nếu vô nghiệm/sau camera.
    """
    origin = np.asarray(ray_origin, dtype=np.float64).reshape(3)
    direction = np.asarray(ray_direction, dtype=np.float64).reshape(3)

    d_z = direction[2]

    # Tia song song hoặc gần song song với mặt phẳng bàn
    if abs(d_z) < 1e-7:
        return False, None

    t = (plane_z - origin[2]) / d_z

    # t <= 0: điểm giao nằm sau camera hoặc tại tâm camera
    if t <= 0:
        return False, None

    # Tọa độ giao điểm 3D
    x = origin[0] + t * direction[0]
    y = origin[1] + t * direction[1]
    point = np.array([x, y, float(plane_z)], dtype=np.float64)

    return True, point


def pixel_to_3d(
    pixel: tuple[float, float] | Sequence[float] | np.ndarray,
    pose: CameraPose,
    K: np.ndarray,
    dist: np.ndarray,
    plane_z: float = 0.0,
) -> tuple[bool, Optional[np.ndarray]]:
    """Chiếu điểm ảnh pixel (u, v) sang tọa độ thế giới 3D (x, y, z) trên mặt bàn.

    Quy trình:
    1. Khử méo pixel bằng cv2.undistortPoints (với P=K).
    2. Chuyển pixel sang vector hướng tia trong hệ camera.
    3. Biến đổi tia sang hệ thế giới qua R^T: ray_world = R^T @ ray_cam.
    4. Xác định tâm camera trong hệ thế giới: C = -R^T @ tvec.
    5. Giao tia với mặt phẳng bàn z = plane_z.

    Args:
        pixel: (u, v) tọa độ pixel trên ảnh.
        pose: CameraPose hợp lệ từ PoseEstimator.
        K: Ma trận camera 3x3.
        dist: Hệ số méo camera.
        plane_z: Tọa độ z của mặt bàn (mặc định 0.0 mm).

    Returns:
        (success, point_3d) với point_3d = [x, y, z] (mm) hoặc (False, None).
    """
    if not pose.valid or pose.rotation_matrix is None or pose.camera_center is None:
        return False, None

    # Bước 1: Khử méo pixel
    pixel_undist = undistort_pixel(pixel, K, dist)

    # Bước 2: Tạo tia trong camera frame
    ray_cam = pixel_to_ray(pixel_undist, K)

    # Bước 3: Biến đổi hướng tia sang world frame
    R = pose.rotation_matrix
    ray_world = R.T @ ray_cam
    ray_world = ray_world / np.linalg.norm(ray_world)

    # Bước 4: Lấy tâm camera
    C = pose.camera_center

    # Bước 5: Tìm giao điểm với mặt phẳng bàn z = plane_z
    return ray_plane_intersection(C, ray_world, plane_z=plane_z)


class ProjectionProcessor:
    """Bộ xử lý chiếu pixel sang 3D với tham số camera cố định."""

    def __init__(
        self,
        K: np.ndarray,
        dist: np.ndarray,
        plane_z: float = 0.0,
    ):
        """Khởi tạo ProjectionProcessor.

        Args:
            K: Ma trận camera 3x3.
            dist: Hệ số méo ống kính.
            plane_z: Tọa độ cao của mặt bàn (mm, mặc định 0.0).
        """
        self.K = np.asarray(K, dtype=np.float64)
        self.dist = (
            np.asarray(dist, dtype=np.float64)
            if dist is not None
            else np.zeros(5, dtype=np.float64)
        )
        self.plane_z = float(plane_z)

    @classmethod
    def from_camera(
        cls,
        camera: CameraModel,
        plane_z: float = 0.0,
    ) -> ProjectionProcessor:
        """Tạo ProjectionProcessor trực tiếp từ CameraModel."""
        return cls(camera.K, camera.dist, plane_z=plane_z)

    def project(
        self,
        pixel: tuple[float, float] | Sequence[float] | np.ndarray,
        pose: CameraPose,
    ) -> tuple[bool, Optional[np.ndarray]]:
        """Chiếu một điểm ảnh sang 3D.

        Args:
            pixel: Tọa độ (u, v).
            pose: CameraPose của khung hình hiện tại.

        Returns:
            (success, point_3d).
        """
        return pixel_to_3d(pixel, pose, self.K, self.dist, self.plane_z)

    def project_batch(
        self,
        pixels: Sequence[tuple[float, float] | Sequence[float] | np.ndarray],
        pose: CameraPose,
    ) -> list[tuple[bool, Optional[np.ndarray]]]:
        """Chiếu một danh sách các điểm ảnh sang 3D.

        Args:
            pixels: Danh sách các tọa độ (u, v).
            pose: CameraPose của khung hình hiện tại.

        Returns:
            Danh sách các cặp (success, point_3d).
        """
    def project_batch(
        self,
        pixels: Sequence[tuple[float, float] | Sequence[float] | np.ndarray],
        pose: CameraPose,
    ) -> list[tuple[bool, Optional[np.ndarray]]]:
        """Chiếu một danh sách các điểm ảnh sang 3D.

        Args:
            pixels: Danh sách các tọa độ (u, v).
            pose: CameraPose của khung hình hiện tại.

        Returns:
            Danh sách các cặp (success, point_3d).
        """
        return [self.project(p, pose) for p in pixels]

    def compute_piece_height(
        self,
        bottom_px: tuple[float, float] | Sequence[float] | np.ndarray,
        top_px: tuple[float, float] | Sequence[float] | np.ndarray,
        pose: CameraPose,
        base_3d: Optional[np.ndarray] = None,
    ) -> Optional[float]:
        """Tính chiều cao quân cờ (mm) từ đáy và đỉnh bounding box trong không gian 3D.

        Quy trình cho góc nhìn camera không cố định (di chuyển tùy biến):
        1. Xác định vị trí chân đế (X_base, Y_base, 0) trên mặt bàn Z = plane_z.
        2. Tính vector tia 3D xuất phát từ tâm camera C qua pixel đỉnh top_px.
        3. Giao cắt tia đỉnh với trục thẳng đứng tại (X_base, Y_base) để suy ra chiều cao H (mm).

        Args:
            bottom_px: (u, v) pixel của đáy bounding box.
            top_px: (u, v) pixel của đỉnh bounding box.
            pose: CameraPose hợp lệ của khung hình.
            base_3d: Tọa độ 3D chân đế (tùy chọn).

        Returns:
            Chiều cao quân cờ tính bằng mm hoặc None nếu không hợp lệ.
        """
        if not pose.valid or pose.rvec is None or pose.tvec is None:
            return None

        # 1. Xác định vị trí chân đế 3D
        if base_3d is not None and not np.isnan(base_3d).any():
            p_base = np.asarray(base_3d, dtype=np.float64)
        else:
            success_b, p_base = self.project(bottom_px, pose)
            if not success_b or p_base is None:
                return None

        # 2. Tâm camera trong hệ tọa độ thế giới
        R, _ = cv2.Rodrigues(pose.rvec)
        C = -R.T @ pose.tvec.flatten()

        # 3. Vector hướng tia từ camera qua top_px trong hệ tọa độ thế giới
        top_undist = undistort_pixel(top_px, self.K, self.dist)
        ray_cam = pixel_to_ray(top_undist, self.K)
        ray_world = R.T @ ray_cam
        norm = np.linalg.norm(ray_world)
        if norm <= 1e-7:
            return None
        v = ray_world / norm

        # 4. Giao tia đỉnh với trục đứng đi qua (X_base, Y_base)
        # Trong mặt phẳng XY: C_xy + t * v_xy = P_base_xy
        v_xy_sq = v[0] ** 2 + v[1] ** 2
        if v_xy_sq < 1e-6:
            return None

        dx = p_base[0] - C[0]
        dy = p_base[1] - C[1]
        t = (dx * v[0] + dy * v[1]) / v_xy_sq

        if t <= 0:
            return None

        # Chiều cao Z tại điểm giao cắt
        h_raw = float(C[2] + t * v[2] - self.plane_z)
        cam_dir_z = 1.0 if (C[2] - self.plane_z) >= 0 else -1.0
        h_est = h_raw * cam_dir_z

        # Kiểm tra ngưỡng vật lý hợp lý (quân cờ thường từ 15mm đến 120mm)
        if 15.0 <= h_est <= 120.0:
            return round(h_est, 1)

        # Fallback nếu góc chiếu quá xiên
        success_t, p_top = self.project(top_px, pose)
        if success_t and p_top is not None:
            fallback_h = float(np.linalg.norm(p_top - p_base))
            if 15.0 <= fallback_h <= 120.0:
                return round(fallback_h, 1)

        if h_est > 0:
            return round(max(15.0, min(h_est, 100.0)), 1)
        return None

