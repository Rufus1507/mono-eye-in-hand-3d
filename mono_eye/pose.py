"""Giai đoạn 3 - Camera pose estimation từ ChArUco board."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Optional

import cv2
import numpy as np

from fov_tool.board import BoardSpec, load_board
from mono_eye.camera_io import CameraModel
from mono_eye.config import ROOT


@dataclass
class CameraPose:
    """Camera pose từ ChArUco board.

    Attributes:
        valid: True nếu phát hiện đủ góc và pose hợp lệ (đạt quality gate).
        rvec: Rotation vector (Rodrigues), shape (3,). Transform từ object (board) → camera.
        tvec: Translation vector (mm), shape (3,). Transform từ object (board) → camera.
        num_corners: Số ChArUco corners phát hiện được.
        reproj_error_px: RMS reprojection error (pixel).
        timestamp: Thời gian khi capture (perf_counter).
    """

    valid: bool
    rvec: Optional[np.ndarray] = None
    tvec: Optional[np.ndarray] = None
    num_corners: int = 0
    reproj_error_px: float = float("inf")
    timestamp: float = 0.0

    @property
    def rotation_matrix(self) -> Optional[np.ndarray]:
        """Convert rvec → R matrix (3x3)."""
        if self.rvec is None:
            return None
        return cv2.Rodrigues(self.rvec)[0]

    @property
    def camera_center(self) -> Optional[np.ndarray]:
        """Camera center trong world frame: C = -R^T @ tvec.

        Returns:
            Camera position (mm) trong world frame (shape (3,)), hoặc None nếu invalid.
        """
        if self.rvec is None or self.tvec is None:
            return None
        R = self.rotation_matrix
        return (-R.T @ self.tvec).reshape(-1)

    @property
    def euler_degrees(self) -> Optional[tuple[float, float, float]]:
        """Extract Euler angles (roll, pitch, yaw) in degrees.

        Thứ tự quay X-Y-Z theo quy ước OpenCV.
        """
        if self.rvec is None:
            return None
        R = self.rotation_matrix
        # Roll (X-axis rotation)
        r_x = np.arctan2(R[2, 1], R[2, 2])
        # Pitch (Y-axis rotation)
        r_y = np.arctan2(-R[2, 0], np.sqrt(R[2, 1] ** 2 + R[2, 2] ** 2))
        # Yaw (Z-axis rotation)
        r_z = np.arctan2(R[1, 0], R[0, 0])
        return tuple(float(deg) for deg in np.degrees([r_x, r_y, r_z]))

    @property
    def camera_x_mm(self) -> Optional[float]:
        """Tọa độ X (mm) của camera trong world frame."""
        c = self.camera_center
        return float(c[0]) if c is not None else None

    @property
    def camera_y_mm(self) -> Optional[float]:
        """Tọa độ Y (mm) của camera trong world frame."""
        c = self.camera_center
        return float(c[1]) if c is not None else None

    @property
    def camera_z_mm(self) -> Optional[float]:
        """Tọa độ Z (mm) của camera trong world frame (độ cao so với mặt bàn)."""
        c = self.camera_center
        return float(c[2]) if c is not None else None

    @property
    def pitch_deg(self) -> Optional[float]:
        """Góc pitch (độ)."""
        e = self.euler_degrees
        return e[1] if e is not None else None

    @property
    def yaw_deg(self) -> Optional[float]:
        """Góc yaw (độ)."""
        e = self.euler_degrees
        return e[2] if e is not None else None

    @property
    def roll_deg(self) -> Optional[float]:
        """Góc roll (độ)."""
        e = self.euler_degrees
        return e[0] if e is not None else None


class PoseEstimator:
    """Camera pose estimator từ ChArUco board."""

    def __init__(
        self,
        camera: CameraModel,
        board_config: str | Path = "bang_calib_A4.yaml",
        square_size_mm: Optional[float] = None,
        min_corners: int = 6,
        max_reproj_error_px: float = 1.5,
        solve_pnp_flags: int = cv2.SOLVEPNP_ITERATIVE,
    ):
        """Khởi tạo PoseEstimator.

        Args:
            camera: CameraModel với K và dist.
            board_config: Đường dẫn file cấu hình bảng.
            square_size_mm: Kích thước cạnh ô thật (mm). Nếu None, đọc từ spec.
            min_corners: Số góc tối thiểu để chấp nhận pose.
            max_reproj_error_px: Sai số tái chiếu RMS tối đa (px).
            solve_pnp_flags: Cờ phương pháp solvePnP (mặc định SOLVEPNP_ITERATIVE).
        """
        self.camera = camera
        self.min_corners = min_corners
        self.max_reproj_error = max_reproj_error_px
        self.solve_pnp_flags = solve_pnp_flags

        # Resolve board config path
        board_path = Path(board_config)
        if not board_path.is_file():
            alt_path = ROOT / board_config
            if alt_path.is_file():
                board_path = alt_path

        self.spec: BoardSpec
        self.board: cv2.aruco.CharucoBoard
        self.detector: cv2.aruco.CharucoDetector
        self.spec, self.board, self.detector = load_board(board_path)

        if square_size_mm is not None:
            self.square_size_mm = float(square_size_mm)
        elif self.spec.square_mm is not None:
            self.square_size_mm = float(self.spec.square_mm)
        else:
            self.square_size_mm = 1.0

    def _get_charuco_object_points(self, charuco_ids: np.ndarray) -> np.ndarray:
        """Lấy object points 3D (mm) cho các ChArUco corners đã phát hiện.

        ChArUco board origin nằm ở góc trên-trái, mặt phẳng bảng ở z = 0.
        """
        all_corners = self.board.getChessboardCorners().reshape(-1, 3)
        ids = charuco_ids.flatten()
        points = all_corners[ids] * self.square_size_mm
        return points.astype(np.float64)

    def _compute_reproj_error(
        self,
        object_points: np.ndarray,
        image_points: np.ndarray,
        rvec: np.ndarray,
        tvec: np.ndarray,
    ) -> float:
        """Tính RMS reprojection error (pixel)."""
        projected, _ = cv2.projectPoints(
            objectPoints=object_points,
            rvec=rvec,
            tvec=tvec,
            cameraMatrix=self.camera.K,
            distCoeffs=self.camera.dist,
        )
        proj_2d = projected.reshape(-1, 2)
        img_2d = image_points.reshape(-1, 2)
        errors = np.linalg.norm(proj_2d - img_2d, axis=1)
        return float(np.sqrt(np.mean(errors ** 2)))

    def estimate_from_corners(
        self,
        charuco_corners: np.ndarray,
        charuco_ids: np.ndarray,
        timestamp: Optional[float] = None,
    ) -> CameraPose:
        """Ước lượng camera pose trực tiếp từ tập góc và ID ChArUco đã phát hiện."""
        t0 = time.perf_counter() if timestamp is None else timestamp

        if (
            charuco_corners is None
            or charuco_ids is None
            or len(charuco_corners) < self.min_corners
        ):
            num = 0 if charuco_corners is None else len(charuco_corners)
            return CameraPose(valid=False, num_corners=num, timestamp=t0)

        object_points = self._get_charuco_object_points(charuco_ids)
        image_points = charuco_corners.astype(np.float64)

        success, rvec, tvec = cv2.solvePnP(
            objectPoints=object_points,
            imagePoints=image_points,
            cameraMatrix=self.camera.K,
            distCoeffs=self.camera.dist,
            flags=self.solve_pnp_flags,
        )

        if not success or rvec is None or tvec is None:
            return CameraPose(
                valid=False,
                num_corners=len(charuco_corners),
                timestamp=t0,
            )

        reproj_error = self._compute_reproj_error(object_points, image_points, rvec, tvec)
        rvec_flat = rvec.reshape(-1)
        tvec_flat = tvec.reshape(-1)
        valid = reproj_error <= self.max_reproj_error

        return CameraPose(
            valid=valid,
            rvec=rvec_flat,
            tvec=tvec_flat,
            num_corners=len(charuco_corners),
            reproj_error_px=reproj_error,
            timestamp=t0,
        )

    def estimate(self, frame: np.ndarray, timestamp: Optional[float] = None) -> CameraPose:
        """Ước lượng camera pose từ khung hình camera.

        Args:
            frame: Ảnh numpy array (BGR hoặc Grayscale).
            timestamp: Mốc thời gian (tùy chọn).

        Returns:
            CameraPose đối tượng chứa rvec, tvec, tâm camera và chất lượng ước lượng.
        """
        t0 = time.perf_counter() if timestamp is None else timestamp

        if frame is None:
            return CameraPose(valid=False, timestamp=t0)

        # 1. Kiểm tra kích thước khung hình
        try:
            self.camera.check_frame(frame)
        except ValueError:
            return CameraPose(valid=False, timestamp=t0)

        # 2. Chuyển sang ảnh xám nếu cần
        if frame.ndim == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame

        # 3. Phát hiện ChArUco corners
        charuco_corners, charuco_ids, _, _ = self.detector.detectBoard(gray)

        # 4. Ước lượng pose từ corners đã phát hiện
        return self.estimate_from_corners(charuco_corners, charuco_ids, timestamp=t0)
