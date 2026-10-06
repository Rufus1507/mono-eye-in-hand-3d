# PROMPT: Giai đoạn 4 - Pixel to 3D Projection (VIẾT CODE)

## Mục tiêu
Viết `mono_eye/projection.py` hoàn chỉnh: từ pixel (u, v) → tọa độ 3D (x, y, z) trên mặt bàn.

## Ngữ cảnh

### Input
```python
# Từ G03: CameraPose
pose = CameraPose(
    valid=True,
    rvec=np.array([...]),  # Rotation vector
    tvec=np.array([...]),  # Translation vector (mm)
    ...
)

# Từ mono_eye/camera_io.py
cam = load_camera_yaml("data/calib/camera.yaml")
# cam.K: [[fx, 0, cx], [0, fy, cy], [0, 0, 1]]
# cam.dist: [k1, k2, p1, p2, k3]
```

### Output
```python
# Kết quả: tọa độ 3D trong world frame (mm)
point_3d = np.array([x, y, z])  # z ≈ 0 (trên mặt bàn)
```

---

## Lý thuyết: Ray-Plane Intersection

### Bước 1: Undistort pixel
```python
# Điểm ảnh bị méo → điểm ảnh "lý tưởng"
pixel_undist = cv2.undistortPoints(
    pixel, K, dist, P=K
).reshape(-1)
# pixel_undist = [u, v]
```

### Bước 2: Tạo tia trong camera frame
```python
# Pixel (u, v) → Ray direction trong camera frame
# Giả định: camera là pinhole model

# Từ pixel → normalized coordinates
fx, fy = K[0, 0], K[1, 1]
cx, cy = K[0, 2], K[1, 2]

# Direction từ camera center qua pixel
ray_cam = np.array([
    (pixel_undist[0] - cx) / fx,
    (pixel_undist[1] - cy) / fy,
    1.0
])
```

### Bước 3: Transform ray sang world frame
```python
# R: rotation matrix từ rvec
R, _ = cv2.Rodrigues(rvec)

# Transform direction: world = R.T @ camera
# (R.T = R^-1 vì R là orthogonal)
ray_world = R.T @ ray_cam

# Camera center trong world frame
C = -R.T @ tvec
```

### Bước 4: Giao với mặt phẳng z = plane_z
```python
# Ray: P(t) = C + t * ray_world
# Plane: z = plane_z

# Solve: C[2] + t * ray_world[2] = plane_z
# t = (plane_z - C[2]) / ray_world[2]

t = (plane_z - C[2]) / ray_world[2]

# Nếu t < 0: điểm nằm sau camera
if t < 0:
    return None  # Invalid

# Intersection point
P = C + t * ray_world
# P = [x, y, z] trong world frame
```

---

## Yêu cầu code

### File: `mono_eye/projection.py`

```python
"""Giai đoạn 4 - Pixel to 3D projection bằng ray-plane intersection."""
from __future__ import annotations

import numpy as np
import cv2

from mono_eye.pose import CameraPose


def undistort_pixel(
    pixel: tuple[float, float],
    K: np.ndarray,
    dist: np.ndarray
) -> np.ndarray:
    """Undistort pixel coordinates.
    
    Args:
        pixel: (u, v) pixel coordinates.
        K: Camera matrix 3x3.
        dist: Distortion coefficients (5 elements).
        
    Returns:
        Undistorted pixel coordinates [u, v].
    """
    pt = np.array(pixel, dtype=np.float32).reshape(1, 1, 2)
    pt_undist = cv2.undistortPoints(
        pt, K, dist, P=K
    ).reshape(-1)
    return pt_undist


def pixel_to_ray(
    pixel: tuple[float, float],
    K: np.ndarray
) -> np.ndarray:
    """Convert pixel to ray direction in camera frame.
    
    Args:
        pixel: (u, v) pixel coordinates.
        K: Camera matrix 3x3.
        
    Returns:
        Ray direction vector (normalized), shape (3,).
    """
    fx, fy = K[0, 0], K[1, 1]
    cx, cy = K[0, 2], K[1, 2]
    
    u, v = pixel
    
    ray = np.array([
        (u - cx) / fx,
        (v - cy) / fy,
        1.0
    ], dtype=np.float64)
    
    # Normalize
    return ray / np.linalg.norm(ray)


def ray_plane_intersection(
    ray_origin: np.ndarray,      # C: camera center in world
    ray_direction: np.ndarray,   # d: ray direction (normalized)
    plane_z: float = 0.0         # z of table plane
) -> tuple[bool, np.ndarray | None]:
    """Intersect ray with horizontal plane z = plane_z.
    
    Args:
        ray_origin: Origin point of ray (camera center).
        ray_direction: Direction vector (normalized).
        plane_z: z-coordinate of plane (default 0.0 for table).
        
    Returns:
        (success, point_3d) where point_3d is [x, y, z] or None if invalid.
    """
    # Ray: P(t) = origin + t * direction
    # Plane: z = plane_z
    # Solve: origin[2] + t * direction[2] = plane_z
    
    d_z = ray_direction[2]
    
    # Check if ray is parallel to plane (or pointing away)
    if abs(d_z) < 1e-6:
        return False, None  # Ray is parallel to plane
    
    t = (plane_z - ray_origin[2]) / d_z
    
    # t < 0 means intersection is behind camera
    if t < 0:
        return False, None
    
    # Calculate intersection point
    point = ray_origin + t * ray_direction
    
    return True, point


def pixel_to_3d(
    pixel: tuple[float, float],
    pose: CameraPose,
    K: np.ndarray,
    dist: np.ndarray,
    plane_z: float = 0.0
) -> tuple[bool, np.ndarray | None]:
    """Convert pixel to 3D point on horizontal plane.
    
    Main function: pixel → ray → intersection with plane.
    
    Args:
        pixel: (u, v) pixel coordinates.
        pose: CameraPose from estimate().
        K: Camera matrix 3x3.
        dist: Distortion coefficients.
        plane_z: z-coordinate of plane (default 0.0 for table).
        
    Returns:
        (success, point_3d) where point_3d = [x, y, z] in mm, or None.
    """
    if not pose.valid:
        return False, None
    
    # Step 1: Undistort pixel
    pixel_undist = undistort_pixel(pixel, K, dist)
    
    # Step 2: Get ray direction in camera frame
    ray_cam = pixel_to_ray(pixel_undist, K)
    
    # Step 3: Transform ray to world frame
    R = pose.rotation_matrix
    ray_world = R.T @ ray_cam  # R.T = R^-1 for orthogonal matrix
    
    # Step 4: Get camera center
    C = pose.camera_center
    
    # Step 5: Intersect with plane
    success, point = ray_plane_intersection(C, ray_world, plane_z)
    
    return success, point


class ProjectionProcessor:
    """Processor cho pixel → 3D projection với caching."""
    
    def __init__(
        self,
        K: np.ndarray,
        dist: np.ndarray,
        plane_z: float = 0.0
    ):
        """Initialize processor.
        
        Args:
            K: Camera matrix.
            dist: Distortion coefficients.
            plane_z: z-coordinate of table plane.
        """
        self.K = K
        self.dist = dist
        self.plane_z = plane_z
    
    def project(
        self,
        pixel: tuple[float, float],
        pose: CameraPose
    ) -> tuple[bool, np.ndarray | None]:
        """Project pixel to 3D.
        
        Args:
            pixel: (u, v) pixel coordinates.
            pose: CameraPose.
            
        Returns:
            (success, point_3d).
        """
        return pixel_to_3d(pixel, pose, self.K, self.dist, self.plane_z)
    
    def project_batch(
        self,
        pixels: list[tuple[float, float]],
        pose: CameraPose
    ) -> list[tuple[bool, np.ndarray | None]]:
        """Project multiple pixels.
        
        Args:
            pixels: List of (u, v) coordinates.
            pose: CameraPose.
            
        Returns:
            List of (success, point_3d) for each pixel.
        """
        return [self.project(p, pose) for p in pixels]
```

---

## Visualization cho debug

### Script: `scripts/debug_projection.py`

```python
"""Debug visualization cho projection."""
import numpy as np
import cv2
import matplotlib.pyplot as plt

from mono_eye.camera_io import load_camera_yaml
from mono_eye.pose import CameraPose
from mono_eye.projection import pixel_to_3d


def create_debug_visualization():
    """Tạo synthetic scene để test projection."""
    # Fake camera
    K = np.array([
        [1000, 0, 640],
        [0, 1000, 360],
        [0, 0, 1]
    ], dtype=np.float64)
    dist = np.zeros(5)
    
    # Fake pose: camera ở (0, 0, 500), nhìn xuống z=0
    rvec = np.array([0.0, 0.0, 0.0])  # No rotation
    tvec = np.array([0.0, 0.0, 500.0])  # 500mm above table
    
    pose = CameraPose(
        valid=True,
        rvec=rvec,
        tvec=tvec,
        num_corners=20,
        reproj_error_px=0.5
    )
    
    # Test: pixel trung tâm (640, 360) → điểm nào?
    # Camera ở (0,0,500), center pixel → (0, 0, 0)
    
    pixel = (640, 360)
    success, point = pixel_to_3d(pixel, pose, K, dist, plane_z=0.0)
    
    print(f"Pixel: {pixel}")
    print(f"Point 3D: {point}")
    print(f"Expected: (0, 0, 0)")
    
    # Test various pixels
    test_pixels = [
        (640, 360),  # Center
        (540, 360),  # Left
        (740, 360),  # Right
        (640, 260),  # Up
        (640, 460),  # Down
    ]
    
    points_3d = []
    for p in test_pixels:
        success, pt = pixel_to_3d(p, pose, K, dist, plane_z=0.0)
        points_3d.append(pt)
        print(f"  {p} → {pt}")
    
    return points_3d


if __name__ == "__main__":
    create_debug_visualization()
```

---

## Unit tests

### File: `tests/test_projection.py`

```python
"""Tests cho projection module."""
import pytest
import numpy as np
import cv2


def test_undistort_pixel():
    """Test undistort pixel coordinates."""
    from mono_eye.projection import undistort_pixel
    
    K = np.array([[1000, 0, 640], [0, 1000, 360], [0, 0, 1]], dtype=np.float64)
    dist = np.array([0.1, 0.01, 0, 0, 0], dtype=np.float64)  # Some distortion
    
    pixel = (700, 400)
    pixel_undist = undistort_pixel(pixel, K, dist)
    
    assert pixel_undist.shape == (2,)
    assert pixel_undist.dtype == np.float64


def test_pixel_to_ray():
    """Test pixel to ray conversion."""
    from mono_eye.projection import pixel_to_ray
    
    K = np.array([[1000, 0, 640], [0, 1000, 360], [0, 0, 1]], dtype=np.float64)
    
    # Center pixel should give ray (0, 0, 1)
    ray = pixel_to_ray((640, 360), K)
    expected = np.array([0, 0, 1])
    assert np.allclose(ray, expected, atol=1e-6)
    
    # Ray should be normalized
    assert np.isclose(np.linalg.norm(ray), 1.0)


def test_ray_plane_intersection():
    """Test ray-plane intersection."""
    from mono_eye.projection import ray_plane_intersection
    
    # Camera at (0, 0, 500), looking down at z=0
    origin = np.array([0.0, 0.0, 500.0])
    direction = np.array([0.0, 0.0, -1.0])  # Straight down
    
    success, point = ray_plane_intersection(origin, direction, plane_z=0.0)
    
    assert success
    assert np.allclose(point, [0, 0, 0], atol=1e-6)


def test_ray_plane_intersection_slanted():
    """Test intersection with slanted ray."""
    from mono_eye.projection import ray_plane_intersection
    
    # Camera at (100, 0, 500), ray angled 45 degrees
    origin = np.array([0.0, 0.0, 500.0])
    
    # Ray at 45 degrees in X direction
    direction = np.array([1.0, 0.0, -1.0])
    direction = direction / np.linalg.norm(direction)
    
    success, point = ray_plane_intersection(origin, direction, plane_z=0.0)
    
    assert success
    # At t=500, P = (500, 0, 0)
    assert np.allclose(point[2], 0, atol=1e-6)


def test_ray_parallel_to_plane():
    """Test ray parallel to plane (should fail)."""
    from mono_eye.projection import ray_plane_intersection
    
    origin = np.array([0.0, 0.0, 100.0])
    direction = np.array([1.0, 0.0, 0.0])  # Horizontal
    
    success, point = ray_plane_intersection(origin, direction, plane_z=0.0)
    
    assert not success
    assert point is None


def test_ray_behind_camera():
    """Test ray pointing away from plane (t < 0)."""
    from mono_eye.projection import ray_plane_intersection
    
    origin = np.array([0.0, 0.0, -100.0])  # Below plane
    direction = np.array([0.0, 0.0, -1.0])  # Pointing down (away from plane)
    
    success, point = ray_plane_intersection(origin, direction, plane_z=0.0)
    
    assert not success


def test_pixel_to_3d_integration():
    """Integration test: full pixel → 3D."""
    from mono_eye.projection import pixel_to_3d
    from mono_eye.pose import CameraPose
    
    K = np.array([[1000, 0, 640], [0, 1000, 360], [0, 0, 1]], dtype=np.float64)
    dist = np.zeros(5)
    
    # Camera at (0, 0, 500), no rotation
    pose = CameraPose(
        valid=True,
        rvec=np.zeros(3),
        tvec=np.array([0.0, 0.0, 500.0]),
        num_corners=20,
        reproj_error_px=0.5
    )
    
    # Center pixel should map to (0, 0, 0)
    success, point = pixel_to_3d((640, 360), pose, K, dist)
    
    assert success
    assert np.allclose(point, [0, 0, 0], atol=1e-4)


def test_projection_processor():
    """Test ProjectionProcessor class."""
    from mono_eye.projection import ProjectionProcessor
    from mono_eye.pose import CameraPose
    
    K = np.array([[1000, 0, 640], [0, 1000, 360], [0, 0, 1]], dtype=np.float64)
    dist = np.zeros(5)
    
    processor = ProjectionProcessor(K, dist)
    
    pose = CameraPose(
        valid=True,
        rvec=np.zeros(3),
        tvec=np.array([0.0, 0.0, 500.0]),
    )
    
    success, point = processor.project((640, 360), pose)
    
    assert success
    assert np.allclose(point, [0, 0, 0], atol=1e-4)
```

---

## Tiêu chí hoàn thành

- [x] `mono_eye/projection.py` viết hoàn chỉnh
- [x] `undistort_pixel()` hoạt động đúng
- [x] `pixel_to_ray()` hoạt động đúng
- [x] `ray_plane_intersection()` hoạt động đúng
- [x] `pixel_to_3d()` integration đúng
- [x] `ProjectionProcessor` class hoạt động
- [x] `tests/test_projection.py` viết và pass
- [x] Debug visualization chạy được


---

## Commands

```bash
# Chạy tests
uv run pytest tests/test_projection.py -v

# Import test
uv run python -c "from mono_eye.projection import pixel_to_3d; print('OK')"

# Run debug visualization
uv run python scripts/debug_projection.py
```

---

## Output mong đợi

1. **File `mono_eye/projection.py`** viết hoàn chỉnh
2. **File `tests/test_projection.py`** với ≥ 7 tests
3. **Kết quả tests:** `pytest tests/test_projection.py -v` → all passed
