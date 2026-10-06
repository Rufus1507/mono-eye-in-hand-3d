# PROMPT: Giai đoạn 3 - Camera Pose Estimation (VIẾT CODE)

## Mục tiêu
Viết `mono_eye/pose.py` hoàn chỉnh: từ khung hình → camera pose (vị trí & hướng).

## Ngữ cảnh

### Module đã có
```python
# fov_tool/board.py - đã có sẵn
from fov_tool.board import load_board
spec, board, detector = load_board("bang_calib_A4.yaml")
# board: cv2.aruco.CharucoBoard
# detector: cv2.aruco.CharucoDetector

# mono_eye/camera_io.py - đã có sẵn
from mono_eye.camera_io import CameraModel, load_camera_yaml
cam = load_camera_yaml("data/calib/camera.yaml")
# cam.K: np.ndarray (3x3)
# cam.dist: np.ndarray (5,)

# mono_eye/config.py - đã có sẵn
from mono_eye.config import load_config
config = load_config()
# config['board']['file']
# config['camera']['index']
# config['quality_gate']['min_charuco_corners']
# config['quality_gate']['max_reprojection_error_px']
```

### Input/Output mong đợi
```python
# Input: frame (numpy array từ camera)
# Output: CameraPose dataclass

@dataclass
class CameraPose:
    valid: bool                    # Có phát hiện được không
    rvec: np.ndarray               # Rotation vector (Rodrigues) - 3 phần tử
    tvec: np.ndarray               # Translation vector (mm) - 3 phần tử
    num_corners: int               # Số góc phát hiện được
    reproj_error_px: float        # Sai số tái chiếu (pixel)
    timestamp: float               # Thời gian (từ perf_counter)
```

---

## Yêu cầu code

### 1. Tạo file `mono_eye/pose.py` với:

```python
"""Giai đoạn 3 - Camera pose estimation từ ChArUco board."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from fov_tool.board import load_board
from mono_eye.camera_io import CameraModel


@dataclass
class CameraPose:
    """Camera pose từ ChArUco board.
    
    Attributes:
        valid: True nếu phát hiện đủ góc và pose hợp lệ.
        rvec: Rotation vector (Rodrigues), shape (3,).
        tvec: Translation vector (mm), shape (3,).
              Transform từ object (board) → camera.
              Camera center: C = -R^T @ tvec
        num_corners: Số ChArUco corners phát hiện được.
        reproj_error_px: RMS reprojection error (pixel).
        timestamp: Thời gian khi capture (perf_counter).
    """
    valid: bool
    rvec: Optional[np.ndarray] = None
    tvec: Optional[np.ndarray] = None
    num_corners: int = 0
    reproj_error_px: float = float('inf')
    timestamp: float = 0.0
    
    @property
    def rotation_matrix(self) -> Optional[np.ndarray]:
        """Convert rvec → R matrix."""
        if self.rvec is None:
            return None
        return cv2.Rodrigues(self.rvec)[0]
    
    @property
    def camera_center(self) -> Optional[np.ndarray]:
        """Camera center trong world frame: C = -R^T @ tvec.
        
        Returns:
            Camera position (mm) trong world frame, hoặc None nếu invalid.
        """
        if self.rvec is None or self.tvec is None:
            return None
        R = self.rotation_matrix
        return -R.T @ self.tvec
    
    @property
    def euler_degrees(self) -> Optional[tuple[float, float, float]]:
        """Extract Euler angles (pitch, yaw, roll) in degrees.
        
        Giả định: intrinsic X-Y-Z rotation order (OpenCV convention).
        """
        if self.rvec is None:
            return None
        R = self.rotation_matrix
        # Roll (X-axis rotation)
        r_x = np.arctan2(R[2, 1], R[2, 2])
        # Pitch (Y-axis rotation)
        r_y = np.arctan2(-R[2, 0], np.sqrt(R[2, 1]**2 + R[2, 2]**2))
        # Yaw (Z-axis rotation)
        r_z = np.arctan2(R[1, 0], R[0, 0])
        return np.degrees([r_x, r_y, r_z])


class PoseEstimator:
    """Camera pose estimator từ ChArUco board."""
    
    def __init__(
        self,
        camera: CameraModel,
        board_config: str = "bang_calib_A4.yaml",
        min_corners: int = 6,
        max_reproj_error_px: float = 1.5,
    ):
        """Khởi tạo PoseEstimator.
        
        Args:
            camera: CameraModel với K và dist.
            board_config: Đường dẫn file cấu hình bảng.
            min_corners: Số góc tối thiểu để accept pose.
            max_reproj_error_px: Sai số tái chiếu tối đa (px).
        """
        self.camera = camera
        self.min_corners = min_corners
        self.max_reproj_error = max_reproj_error_px
        
        # Load board và detector từ fov_tool
        self.spec, self.board, self.detector = load_board(board_config)
        
        # Object points cho ChArUco board (tính từ board dimensions)
        # Tính toán từ spec
        # TODO: Tính object points từ board dimensions
        
    def estimate(self, frame: np.ndarray) -> CameraPose:
        """Ước lượng camera pose từ frame.
        
        Args:
            frame: BGR image từ camera (numpy array).
            
        Returns:
            CameraPose object.
        """
        # 1. Kiểm tra frame size
        try:
            self.camera.check_frame(frame)
        except ValueError:
            return CameraPose(valid=False, timestamp=time.perf_counter())
        
        # 2. Phát hiện ChArUco corners
        charuco_corners, charuco_ids, marker_corners, marker_ids = \
            self.detector.detectBoard(frame)
        
        # 3. Quality gate: số góc
        if charuco_corners is None or len(charuco_corners) < self.min_corners:
            return CameraPose(
                valid=False, 
                num_corners=0 if charuco_corners is None else len(charuco_corners),
                timestamp=time.perf_counter()
            )
        
        # 4. Refine corners (tùy chọn)
        # charuco_corners = cv2.cornerSubPix(...)
        
        # 5. Interpolate ChArUco pose
        # Lấy object points cho các corners đã phát hiện
        # object_points = self.board.getChessboardCorners()[charuco_ids.flatten()]
        
        # 6. solvePnP
        # ... (viết code ở đây)
        
        # 7. Tính reprojection error
        # projected, _ = cv2.projectPoints(...)
        # error = RMS(projected - image_points)
        
        # 8. Quality gate: reprojection error
        # if reproj_error > self.max_reproj_error:
        #     return CameraPose(valid=False, ...)
        
        # 9. Return success
        return CameraPose(
            valid=True,
            rvec=rvec,
            tvec=tvec,
            num_corners=len(charuco_corners),
            reproj_error_px=reproj_error,
            timestamp=time.perf_counter()
        )
```

---

## Cần hoàn thiện

### 1. Tính object points cho ChArUco

```python
def _get_charuco_object_points(self, charuco_ids: np.ndarray) -> np.ndarray:
    """Lấy object points (3D) cho các ChArUco corners.
    
    ChArUco board origin ở góc trái-trên của grid.
    Object points có z=0 (flat on board plane).
    """
    # Lấy internal chessboard corners từ board
    # board.getChessboardCorners() trả về tọa độ 3D của các corner
    # Chỉ lấy những corner có trong charuco_ids
    pass
```

### 2. solvePnP

```python
# Thử các flags:
# cv2.SOLVEPNP_ITERATIVE - mặc định, iterative refinement
# cv2.SOLVEPNP_SQPNP - mới hơn, stable hơn

success, rvec, tvec = cv2.solvePnP(
    objectPoints=object_points,
    imagePoints=image_points,
    cameraMatrix=self.camera.K,
    distCoeffs=self.camera.dist,
    rvec=None,
    tvec=None,
    useExtrinsicGuess=False,
    flags=cv2.SOLVEPNP_ITERATIVE
)
```

### 3. Reprojection error

```python
def _compute_reproj_error(
    self, 
    object_points: np.ndarray, 
    image_points: np.ndarray,
    rvec: np.ndarray,
    tvec: np.ndarray
) -> float:
    """Tính RMS reprojection error."""
    projected, _ = cv2.projectPoints(
        objectPoints=object_points,
        rvec=rvec,
        tvec=tvec,
        cameraMatrix=self.camera.K,
        distCoeffs=self.camera.dist
    )
    # projected shape: (N, 1, 2)
    projected = projected.reshape(-1, 2)
    error = np.linalg.norm(projected - image_points.reshape(-1, 2), axis=1)
    return np.sqrt(np.mean(error**2))
```

---

## Unit tests cần viết

**File: `tests/test_pose.py`**

```python
"""Tests cho pose estimation (không cần camera thật)."""
import pytest
import numpy as np
import cv2


def test_camera_pose_rotation_matrix():
    """Test Rodrigues conversion."""
    rvec = np.array([0.1, 0.2, 0.3])
    R, _ = cv2.Rodrigues(rvec)
    # Verify R is orthogonal
    assert np.allclose(R @ R.T, np.eye(3), atol=1e-6)
    # det(R) = 1 (proper rotation, not reflection)
    assert np.isclose(np.linalg.det(R), 1.0)


def test_camera_pose_center():
    """Test camera center calculation: C = -R^T @ t."""
    # Setup
    rvec = np.array([0.0, 0.0, 0.0])  # No rotation
    tvec = np.array([0.0, 0.0, 100.0])  # 100mm in front
    
    R, _ = cv2.Rodrigues(rvec)
    C = -R.T @ tvec
    
    assert np.allclose(C, [0, 0, 100])


def test_pose_estimator_init():
    """Test PoseEstimator initialization."""
    from mono_eye.camera_io import CameraModel
    from mono_eye.pose import PoseEstimator
    
    # Fake camera K
    K = np.array([[1000, 0, 640], [0, 1000, 360], [0, 0, 1]], dtype=np.float64)
    dist = np.zeros(5, dtype=np.float64)
    cam = CameraModel(K=K, dist=dist, width=1280, height=720)
    
    estimator = PoseEstimator(cam, "bang_calib_A4.yaml")
    
    assert estimator.camera is cam
    assert estimator.min_corners == 6


def test_quality_gate_reproj_error():
    """Test quality gate với reprojection error."""
    # TODO: Test với synthetic frame
    pass
```

---

## Tiêu chí hoàn thành

- [x] `mono_eye/pose.py` viết hoàn chỉnh
- [x] Class `CameraPose` với properties
- [x] Class `PoseEstimator` hoạt động
- [x] `solvePnP` được gọi đúng
- [x] Reprojection error tính đúng
- [x] Quality gates hoạt động
- [x] `tests/test_pose.py` viết và pass
- [x] Code có docstrings rõ ràng

---

## Commands

```bash
# Chạy tests
uv run pytest tests/test_pose.py -v

# Import test
uv run python -c "from mono_eye.pose import PoseEstimator, CameraPose; print('OK')"

# Generate synthetic frame để test (tùy chọn)
uv run python -c "
from fov_tool.board import load_board
spec, board, detector = load_board('bang_calib_A4.yaml')
img = board.generateImage((1280, 720))
print(f'Board image: {img.shape}, dtype={img.dtype}')
"
```

---

## Output mong đợi

1. **File `mono_eye/pose.py`** viết hoàn chỉnh
2. **File `tests/test_pose.py`** với unit tests
3. **Kết quả tests:** `pytest tests/test_pose.py -v` → passed
