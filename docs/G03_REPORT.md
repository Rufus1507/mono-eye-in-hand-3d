# Giai đoạn 3: Camera Pose Estimation - Báo cáo

## Ngày: 2026-10-06

## Trạng thái: ✅ HOÀN THÀNH

---

## 1. Module Implementation

### `mono_eye/pose.py`
- **`CameraPose` dataclass**:
  - `valid`: boolean (True nếu đạt quality gate)
  - `rvec`, `tvec`: Vector quay (Rodrigues) và tịnh tiến (mm)
  - `num_corners`: Số góc ChArUco phát hiện được
  - `reproj_error_px`: RMS sai số tái chiếu (pixels)
  - Properties: `rotation_matrix` ($R = \text{Rodrigues}(rvec)$), `camera_center` ($C = -R^T t$), `euler_degrees` (roll, pitch, yaw), `camera_x_mm`, `camera_y_mm`, `camera_z_mm`, `pitch_deg`, `yaw_deg`, `roll_deg`.
- **`PoseEstimator` class**:
  - Tải board và detector thông qua `fov_tool.board.load_board`.
  - Tính object points 3D (mm) theo cạnh ô thực tế.
  - Sử dụng `cv2.solvePnP` ước lượng tư thế camera.
  - Tính RMS reprojection error bằng `cv2.projectPoints`.
  - Quality gates: kiểm tra độ phân giải camera, số góc tối thiểu (`min_corners >= 6`), sai số tái chiếu tối đa (`max_reproj_error_px <= 1.5`).
  - Cung cấp hai phương thức: `estimate(frame)` và `estimate_from_corners(corners, ids)`.

---

## 2. Unit Tests

### `tests/test_pose.py`
```
======================================= 9 passed in 0.25s =======================================
```
- `test_camera_pose_rotation_matrix`: Kiểm tra tính trực giao của ma trận $R$ ($R R^T = I$) và $\det(R) = 1$.

- `test_camera_pose_center`: Kiểm tra công thức $C = -R^T t$ cho cả trường hợp quay chuẩn và quay bất kỳ.
- `test_camera_pose_euler_degrees_and_helpers`: Kiểm tra góc Euler và các accessor tọa độ $X, Y, Z$.
- `test_camera_pose_invalid_returns_none`: Đảm bảo khi invalid, các properties trả về `None`.
- `test_pose_estimator_init`: Kiểm tra nạp tham số bảng ChArUco A4.
- `test_frame_size_check`: Từ chối các khung hình sai độ phân giải.
- `test_quality_gate_min_corners`: Từ chối khung hình thiếu góc hoặc không có marker.
- `test_synthetic_corners_pose_recovery`: Khôi phục vị trí camera chuẩn xác trên dữ liệu điểm chiếu giả lập với sai số tái chiếu $< 0.05$ px.
- `test_quality_gate_reproj_error_rejection`: Từ chối pose khi dữ liệu bị nhiễu vượt ngưỡng reprojection error.

---

## 3. Tiêu chí hoàn thành

- [x] `mono_eye/pose.py` viết hoàn chỉnh
- [x] Class `CameraPose` với properties
- [x] Class `PoseEstimator` hoạt động
- [x] `solvePnP` được gọi đúng
- [x] Reprojection error tính đúng
- [x] Quality gates hoạt động
- [x] `tests/test_pose.py` viết đầy đủ
- [x] Code có docstrings rõ ràng
