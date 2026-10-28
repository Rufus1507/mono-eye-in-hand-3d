"""Giai đoạn 3 - Camera pose estimation từ ChArUco board."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Optional

import cv2
import numpy as np
import yaml

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
    board_type: str = "charuco"

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


class ChessboardPoseEstimator:
    """Camera pose estimator từ bàn cờ 8x8 với 32 ArUco markers (theo banco_8x8.yaml)."""

    def __init__(
        self,
        camera: CameraModel,
        board_config: str | Path = "configs/banco_8x8.yaml",
        min_markers: int = 2,
        max_reproj_error_px: float = 6.0,
        max_hold_frames: int = 5,
        solve_pnp_flags: int = cv2.SOLVEPNP_SQPNP,
    ):
        """Khởi tạo ChessboardPoseEstimator.

        Args:
            camera: CameraModel với K và dist.
            board_config: Đường dẫn file cấu hình YAML của bàn cờ 8x8.
            min_markers: Số marker tối thiểu để giải Pose (mặc định 2).
            max_reproj_error_px: Sai số tái chiếu tối đa (px).
            max_hold_frames: Số khung hình tối đa giữ lại Pose cũ khi bàn cờ bị che khuất.
            solve_pnp_flags: Cờ phương pháp solvePnPRansac.
        """
        self.camera = camera
        self.min_markers = min_markers
        self.max_reproj_error = max_reproj_error_px
        self.max_hold_frames = max_hold_frames
        self.solve_pnp_flags = solve_pnp_flags

        cfg_path = Path(board_config)
        if not cfg_path.is_file():
            alt_path = ROOT / board_config
            if alt_path.is_file():
                cfg_path = alt_path

        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        bang = cfg.get("bang", {})
        self.kieu = str(bang.get("kieu", "chessboard_8x8"))
        self.cols = int(bang.get("o_ngang", 8))
        self.rows = int(bang.get("o_doc", 8))
        self.square_size_mm = float(bang.get("canh_o_mm", 40.0))
        self.marker_size_mm = float(bang.get("marker_mm", 24.0))
        dict_name = "DICT_" + str(bang.get("tu_dien", "4X4_50"))

        if not hasattr(cv2.aruco, dict_name):
            raise ValueError(f"OpenCV không có từ điển {dict_name}")
        self.dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dict_name))
        self.detector_params = cv2.aruco.DetectorParameters()
        self.detector_params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        self.detector_params.cornerRefinementWinSize = 5
        self.detector_params.cornerRefinementMaxIterations = 30
        self.detector_params.cornerRefinementMinAccuracy = 0.05
        self.detector = cv2.aruco.ArucoDetector(self.dictionary, self.detector_params)

        # Tính toán tọa độ 3D danh nghĩa cho 4 góc của từng marker
        offset = (self.square_size_mm - self.marker_size_mm) / 2.0
        self.marker_3d_map: dict[int, np.ndarray] = {}
        self.marker_info: dict[int, dict] = {}

        raw_markers = cfg.get("markers", {})
        for mid, m_info in raw_markers.items():
            mid_int = int(mid)
            rot = int(m_info.get("rot_deg", 0))

            if "x_mm" in m_info and "y_mm" in m_info:
                cx = float(m_info["x_mm"])
                cy = float(m_info["y_mm"])
                h_m = self.marker_size_mm / 2.0
                canon = np.array([
                    [cx - h_m, cy + h_m, 0.0],
                    [cx + h_m, cy + h_m, 0.0],
                    [cx + h_m, cy - h_m, 0.0],
                    [cx - h_m, cy - h_m, 0.0],
                ], dtype=np.float64)
            else:
                c_idx = int(m_info["col_idx"])
                r_idx = int(m_info["row_idx"])
                sq_x = c_idx * self.square_size_mm
                sq_y = r_idx * self.square_size_mm
                canon = np.array([
                    [sq_x + offset, sq_y + offset + self.marker_size_mm, 0.0],
                    [sq_x + offset + self.marker_size_mm, sq_y + offset + self.marker_size_mm, 0.0],
                    [sq_x + offset + self.marker_size_mm, sq_y + offset, 0.0],
                    [sq_x + offset, sq_y + offset, 0.0],
                ], dtype=np.float64)

            shift = (rot // 90) % 4
            self.marker_3d_map[mid_int] = np.roll(canon, -shift, axis=0)
            self.marker_info[mid_int] = m_info

        self.last_valid_pose: Optional[CameraPose] = None
        self.hold_count: int = 0
        self.smooth_rvec: Optional[np.ndarray] = None
        self.smooth_tvec: Optional[np.ndarray] = None

    def reset(self) -> None:
        """Đặt lại bộ lọc làm mượt và bộ đếm giữ pose."""
        self.last_valid_pose = None
        self.hold_count = 0
        self.smooth_rvec = None
        self.smooth_tvec = None

    def estimate(self, frame: np.ndarray, timestamp: Optional[float] = None) -> CameraPose:
        """Ước lượng camera pose từ bàn cờ 8x8 với RANSAC + LM Refinement và Temporal Filter."""
        t0 = time.perf_counter() if timestamp is None else timestamp
        if frame is None or frame.size == 0:
            return CameraPose(valid=False, timestamp=t0, board_type="chessboard_8x8")

        # Tự động co giãn K nếu độ phân giải khung hình khác cấu hình camera
        fh, fw = frame.shape[:2]
        if (fw, fh) != (self.camera.width, self.camera.height):
            self.camera = self.camera.scale_to(fw, fh)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame

        corners, ids, _ = self.detector.detectMarkers(gray)

        if ids is not None and len(ids) > 0:
            obj_pts_list = []
            img_pts_list = []

            for i, mid in enumerate(ids.flatten()):
                mid_int = int(mid)
                if mid_int in self.marker_3d_map:
                    obj_pts_list.append(self.marker_3d_map[mid_int])
                    img_pts_list.append(corners[i][0])

            if len(obj_pts_list) >= self.min_markers:
                obj_pts = np.vstack(obj_pts_list).astype(np.float64)
                img_pts = np.vstack(img_pts_list).astype(np.float64)

                res_scale = max(1.0, float(self.camera.height) / 720.0)
                effective_thresh = max(6.0, self.max_reproj_error * res_scale)

                success, rvec, tvec, inliers = cv2.solvePnPRansac(
                    objectPoints=obj_pts,
                    imagePoints=img_pts,
                    cameraMatrix=self.camera.K,
                    distCoeffs=self.camera.dist,
                    flags=self.solve_pnp_flags,
                    reprojectionError=effective_thresh,
                )

                if (
                    success
                    and rvec is not None
                    and tvec is not None
                    and inliers is not None
                    and len(inliers) >= 4
                ):
                    inlier_idx = inliers.flatten()
                    obj_inliers = obj_pts[inlier_idx]
                    img_inliers = img_pts[inlier_idx]

                    # Tinh chỉnh phi tuyến Levenberg-Marquardt trên toàn bộ inliers
                    try:
                        rvec_ref, tvec_ref = cv2.solvePnPRefineLM(
                            obj_inliers,
                            img_inliers,
                            self.camera.K,
                            self.camera.dist,
                            rvec,
                            tvec,
                        )
                    except Exception:
                        rvec_ref, tvec_ref = rvec, tvec

                    rvec_flat = rvec_ref.reshape(-1)
                    tvec_flat = tvec_ref.reshape(-1)

                    # Bộ lọc làm mượt chuyển động thích ứng (Adaptive Temporal Pose Filter)
                    if self.smooth_rvec is None or self.smooth_tvec is None:
                        self.smooth_rvec = rvec_flat.copy()
                        self.smooth_tvec = tvec_flat.copy()
                    else:
                        d_t = float(np.linalg.norm(tvec_flat - self.smooth_tvec))
                        # Khi camera đứng yên hoặc di chuyển rất chậm: lọc mạnh (alpha=0.35) triệt tiêu rung giật
                        # Khi camera di chuyển nhanh: tăng alpha (lên tới 0.85) để bám bắt tức thời không trễ
                        if d_t < 15.0:
                            alpha = 0.35
                        elif d_t <= 60.0:
                            alpha = 0.35 + (d_t - 15.0) / 45.0 * 0.45
                        else:
                            alpha = 0.85

                        # Kiểm tra chống nhảy cực đoan (outlier jump) do nhiễu ánh sáng
                        if d_t > 90.0 and len(inliers) < 8:
                            # Giữ pose cũ, không cập nhật bước nhảy bất thường
                            rvec_flat = self.smooth_rvec
                            tvec_flat = self.smooth_tvec
                        else:
                            self.smooth_tvec = alpha * tvec_flat + (1.0 - alpha) * self.smooth_tvec
                            self.smooth_rvec = alpha * rvec_flat + (1.0 - alpha) * self.smooth_rvec

                    active_rvec = self.smooth_rvec
                    active_tvec = self.smooth_tvec

                    projected, _ = cv2.projectPoints(
                        obj_inliers, active_rvec, active_tvec, self.camera.K, self.camera.dist
                    )
                    errors = np.linalg.norm(
                        projected.reshape(-1, 2) - img_inliers.reshape(-1, 2), axis=1
                    )
                    reproj_error = float(np.sqrt(np.mean(errors ** 2)))

                    self.hold_count = 0
                    self.last_valid_pose = CameraPose(
                        valid=True,
                        rvec=active_rvec,
                        tvec=active_tvec,
                        num_corners=len(inlier_idx),
                        reproj_error_px=reproj_error,
                        timestamp=t0,
                        board_type=self.kieu,
                    )
                    return self.last_valid_pose

        # Pose Hold khi bị che khuất tạm thời bởi tay người hoặc quân cờ
        if self.last_valid_pose is not None and self.hold_count < self.max_hold_frames:
            self.hold_count += 1
            return CameraPose(
                valid=True,
                rvec=self.last_valid_pose.rvec,
                tvec=self.last_valid_pose.tvec,
                num_corners=self.last_valid_pose.num_corners,
                reproj_error_px=self.last_valid_pose.reproj_error_px,
                timestamp=t0,
                board_type=self.kieu,
            )

        return CameraPose(valid=False, num_corners=0, timestamp=t0, board_type=self.kieu)


class UnifiedPoseEstimator:
    """Bộ ước lượng Pose đa năng hỗ trợ song song cả Bảng ChArUco và Bàn cờ 8x8."""

    def __init__(
        self,
        camera: CameraModel,
        mode: str = "auto",
        charuco_config: str | Path = "bang_calib_A4.yaml",
        chessboard_config: str | Path = "configs/banco_8x8.yaml",
        max_reproj_error_px: float = 6.0,
    ):
        """Khởi tạo UnifiedPoseEstimator.

        Args:
            camera: CameraModel.
            mode: Chế độ nhận diện ('auto', 'charuco', 'chessboard').
            charuco_config: Đường dẫn file cấu hình ChArUco.
            chessboard_config: Đường dẫn file cấu hình Bàn cờ 8x8.
            max_reproj_error_px: Sai số tái chiếu tối đa (px).
        """
        self.camera = camera
        self.mode = str(mode).lower()
        self.max_reproj_error_px = max_reproj_error_px

        self.charuco_estimator = PoseEstimator(
            camera=camera,
            board_config=charuco_config,
            max_reproj_error_px=max_reproj_error_px,
        )

        self.chessboard_estimator = ChessboardPoseEstimator(
            camera=camera,
            board_config=chessboard_config,
            max_reproj_error_px=max_reproj_error_px,
        )

    def update_camera(self, camera: CameraModel) -> None:
        self.camera = camera
        if hasattr(self, "charuco_estimator"):
            self.charuco_estimator.camera = camera
        if hasattr(self, "chessboard_estimator"):
            self.chessboard_estimator.camera = camera

    def reset(self) -> None:
        if hasattr(self, "chessboard_estimator") and hasattr(self.chessboard_estimator, "reset"):
            self.chessboard_estimator.reset()

    def estimate(self, frame: np.ndarray, timestamp: Optional[float] = None) -> CameraPose:
        """Ước lượng Pose từ khung hình dựa trên chế độ cấu hình."""
        if self.mode in ("charuco", "charuco_board"):
            return self.charuco_estimator.estimate(frame, timestamp)

        if self.mode in ("chessboard", "chessboard_8x8", "banco"):
            return self.chessboard_estimator.estimate(frame, timestamp)

        # Chế độ "auto": Tự động phát hiện loại bảng trong khung hình
        chess_pose = self.chessboard_estimator.estimate(frame, timestamp)
        charuco_pose = self.charuco_estimator.estimate(frame, timestamp)

        if chess_pose.valid and not charuco_pose.valid:
            return chess_pose
        if charuco_pose.valid and not chess_pose.valid:
            return charuco_pose
        if chess_pose.valid and charuco_pose.valid:
            # Nếu cả 2 đều hợp lệ, chọn pose có sai số tái chiếu nhỏ hơn
            if chess_pose.reproj_error_px <= charuco_pose.reproj_error_px:
                return chess_pose
            return charuco_pose

        if chess_pose.num_corners > charuco_pose.num_corners:
            return chess_pose
        if charuco_pose.num_corners > chess_pose.num_corners:
            return charuco_pose

        return CameraPose(
            valid=False,
            timestamp=time.perf_counter() if timestamp is None else timestamp,
            board_type="unknown",
        )

