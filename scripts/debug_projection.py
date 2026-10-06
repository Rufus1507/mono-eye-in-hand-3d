"""Debug script cho module projection (Pixel to 3D)."""
from pathlib import Path
import numpy as np

from mono_eye.pose import CameraPose
from mono_eye.projection import pixel_to_3d


def create_debug_visualization():
    """Tạo synthetic scene để kiểm tra projection."""
    K = np.array(
        [[1000.0, 0.0, 640.0], [0.0, 1000.0, 360.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    dist = np.zeros(5, dtype=np.float64)

    # Giả lập camera đặt ở độ cao Z=500 mm trên mặt bàn, nhìn thẳng chúc xuống bàn (z=0):
    # Quay 180 độ quanh trục X để +Z_cam hướng theo -Z_world
    rvec = np.array([np.pi, 0.0, 0.0], dtype=np.float64)
    tvec = np.array([0.0, 0.0, 500.0], dtype=np.float64)

    pose = CameraPose(
        valid=True,
        rvec=rvec,
        tvec=tvec,
        num_corners=20,
        reproj_error_px=0.5,
    )

    # Pixel trung tâm (640, 360) -> điểm (0, 0, 0) trên mặt bàn
    pixel = (640.0, 360.0)
    success, point = pixel_to_3d(pixel, pose, K, dist, plane_z=0.0)

    print("=== Debug Projection ===")
    print(f"Camera center C: {pose.camera_center}")
    print(f"Center pixel: {pixel}")
    print(f"Point 3D: {point} (Success: {success})")
    print("Expected: [0. 0. 0.]")

    test_pixels = [
        (640.0, 360.0),  # Center
        (540.0, 360.0),  # Left (-100 px -> -50 mm)
        (740.0, 360.0),  # Right (+100 px -> +50 mm)
        (640.0, 260.0),  # Up (-100 px -> +50 mm)
        (640.0, 460.0),  # Down (+100 px -> -50 mm)
    ]

    print("\nTest various pixels:")
    points_3d = []
    for p in test_pixels:
        ok, pt = pixel_to_3d(p, pose, K, dist, plane_z=0.0)
        points_3d.append(pt)
        print(f"  Pixel {p} -> 3D {pt} (Success: {ok})")

    return points_3d


if __name__ == "__main__":
    create_debug_visualization()
