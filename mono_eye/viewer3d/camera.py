"""Hệ thống Camera Phối cảnh 3D và Bộ điều khiển Tương tác Chuột (Orbit Controller)."""
from __future__ import annotations

import math
import numpy as np


class OrbitCamera:
    """Camera phối cảnh 3D xoay quanh tâm (Orbit / Turntable Camera)."""

    def __init__(
        self,
        target: np.ndarray | None = None,
        distance: float = 1.35,
        azimuth: float = 45.0,     # Độ (quay quanh trục Y)
        elevation: float = 38.0,   # Độ (góc nâng nhìn từ trên xuống)
        fov_y: float = 45.0,       # Độ (Field of View trục dọc)
        near: float = 0.05,
        far: float = 50.0,
    ) -> None:
        self.target = np.array([0.0, 0.15, 0.0], dtype=np.float32) if target is None else np.asarray(target, dtype=np.float32)
        self.distance = float(distance)
        self.azimuth = float(azimuth)
        self.elevation = float(elevation)
        self.fov_y = float(fov_y)
        self.near = float(near)
        self.far = float(far)

    @property
    def eye(self) -> np.ndarray:
        """Tính toán vị trí thực tế của camera trong không gian thế giới."""
        rad_az = math.radians(self.azimuth)
        rad_el = math.radians(self.elevation)

        x = self.target[0] + self.distance * math.cos(rad_el) * math.sin(rad_az)
        y = self.target[1] + self.distance * math.sin(rad_el)
        z = self.target[2] + self.distance * math.cos(rad_el) * math.cos(rad_az)
        return np.array([x, y, z], dtype=np.float32)

    def view_matrix(self) -> np.ndarray:
        """Tạo ma trận View (LookAt) 4x4 theo chuẩn OpenGL (column-major)."""
        eye = self.eye
        target = self.target
        up = np.array([0.0, 1.0, 0.0], dtype=np.float32)

        forward = target - eye
        forward_norm = np.linalg.norm(forward)
        if forward_norm < 1e-6:
            forward = np.array([0.0, 0.0, -1.0], dtype=np.float32)
        else:
            forward = forward / forward_norm

        right = np.cross(forward, up)
        right_norm = np.linalg.norm(right)
        if right_norm < 1e-6:
            right = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        else:
            right = right / right_norm

        real_up = np.cross(right, forward)

        # Ma trận View 4x4
        V = np.eye(4, dtype=np.float32)
        V[0, 0:3] = right
        V[1, 0:3] = real_up
        V[2, 0:3] = -forward
        V[0, 3] = -np.dot(right, eye)
        V[1, 3] = -np.dot(real_up, eye)
        V[2, 3] = np.dot(forward, eye)
        return V

    def projection_matrix(self, aspect: float) -> np.ndarray:
        """Tạo ma trận Phối cảnh Perspective 4x4."""
        rad_fov = math.radians(self.fov_y)
        tan_half = math.tan(rad_fov / 2.0)
        f = 1.0 / tan_half

        P = np.zeros((4, 4), dtype=np.float32)
        P[0, 0] = f / aspect
        P[1, 1] = f
        P[2, 2] = -(self.far + self.near) / (self.far - self.near)
        P[2, 3] = -(2.0 * self.far * self.near) / (self.far - self.near)
        P[3, 2] = -1.0
        return P

    def frame_bounds(self, points: np.ndarray) -> None:
        """Tự động tính toán target và khoảng cách camera để bao quát tập điểm."""
        pts = np.asarray(points)
        if len(pts) == 0:
            return
        if pts.shape[1] == 2:
            # Mặt phẳng X-Z
            min_pt = np.array([pts[:, 0].min(), 0.14, pts[:, 1].min()])
            max_pt = np.array([pts[:, 0].max(), 0.14, pts[:, 1].max()])
        else:
            min_pt = pts.min(axis=0)
            max_pt = pts.max(axis=0)

        self.target = ((min_pt + max_pt) / 2.0).astype(np.float32)
        diag = float(np.linalg.norm(max_pt - min_pt))
        self.distance = max(diag * 1.3, 0.8)


class OrbitController:
    """Bộ điều khiển chuột tương tác thời gian thực cho OrbitCamera."""

    def __init__(self, camera: OrbitCamera) -> None:
        self.camera = camera
        self.is_dragging_orbit = False
        self.is_dragging_pan = False
        self.last_x = 0.0
        self.last_y = 0.0

    def on_mouse_press(self, button: int, x: float, y: float, shift_pressed: bool = False) -> None:
        self.last_x = x
        self.last_y = y
        # button 0: Trái, button 1: Phải, button 2: Giữa
        if button == 0 and not shift_pressed:
            self.is_dragging_orbit = True
        elif button == 1 or (button == 0 and shift_pressed) or button == 2:
            self.is_dragging_pan = True

    def on_mouse_release(self, button: int) -> None:
        if button == 0:
            self.is_dragging_orbit = False
        if button in (0, 1, 2):
            self.is_dragging_pan = False

    def on_mouse_move(self, x: float, y: float) -> None:
        dx = x - self.last_x
        dy = y - self.last_y
        self.last_x = x
        self.last_y = y

        if self.is_dragging_orbit:
            sensitivity = 0.35
            self.camera.azimuth += dx * sensitivity
            self.camera.elevation = max(5.0, min(85.0, self.camera.elevation + dy * sensitivity))

        elif self.is_dragging_pan:
            pan_speed = 0.0015 * self.camera.distance
            # Tính hướng pan theo mặt phẳng camera
            rad_az = math.radians(self.camera.azimuth)
            right_dir = np.array([math.cos(rad_az), 0.0, -math.sin(rad_az)], dtype=np.float32)
            up_dir = np.array([0.0, 1.0, 0.0], dtype=np.float32)
            self.camera.target -= (right_dir * dx - up_dir * dy) * pan_speed

    def on_scroll(self, y_offset: float) -> None:
        zoom_factor = 0.90 if y_offset > 0 else 1.11
        self.camera.distance = max(0.2, min(10.0, self.camera.distance * zoom_factor))


class PoseCamera:
    """Camera phối cảnh 3D đặt theo tư thế pose thực tế (Extrinsics rvec/tvec) từ camera OpenCV."""

    def __init__(
        self,
        eye: np.ndarray,
        R_cam_world: np.ndarray,
        fov_y_deg: float,
        near: float = 0.05,
        far: float = 50.0,
    ) -> None:
        self._eye = np.asarray(eye, dtype=np.float32).reshape(3)
        self.R_cam_world = np.asarray(R_cam_world, dtype=np.float32).reshape(3, 3)
        self.fov_y = float(fov_y_deg)
        self.near = float(near)
        self.far = float(far)

    @property
    def eye(self) -> np.ndarray:
        return self._eye

    def view_matrix(self) -> np.ndarray:
        """Tạo ma trận View 4x4 từ ma trận hướng R_cam_world và vị trí eye."""
        R = self.R_cam_world
        right = R[:, 0]
        up = R[:, 1]
        back = R[:, 2]  # Trục Z của camera hướng ra sau (theo chuẩn camera OpenGL)

        V = np.eye(4, dtype=np.float32)
        V[0, 0:3] = right
        V[1, 0:3] = up
        V[2, 0:3] = back
        V[0, 3] = -float(np.dot(right, self._eye))
        V[1, 3] = -float(np.dot(up, self._eye))
        V[2, 3] = -float(np.dot(back, self._eye))
        return V

    def projection_matrix(self, aspect: float) -> np.ndarray:
        """Tạo ma trận Phối cảnh Perspective 4x4."""
        rad_fov = math.radians(self.fov_y)
        tan_half = math.tan(rad_fov / 2.0)
        f = 1.0 / tan_half

        P = np.zeros((4, 4), dtype=np.float32)
        P[0, 0] = f / max(float(aspect), 1e-4)
        P[1, 1] = f
        P[2, 2] = -(self.far + self.near) / (self.far - self.near)
        P[2, 3] = -(2.0 * self.far * self.near) / (self.far - self.near)
        P[3, 2] = -1.0
        return P

