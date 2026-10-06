# Giai đoạn 4: Pixel to 3D Projection - Báo cáo

## Ngày: 2026-10-06

## Trạng thái: ✅ HOÀN THÀNH

---

## 1. Module Implementation

### `mono_eye/projection.py`
- **`undistort_pixel(pixel, K, dist)`**: Khử méo điểm ảnh sang hệ tọa độ chuẩn bằng `cv2.undistortPoints(..., P=K)`.
- **`pixel_to_ray(pixel, K)`**: Chuyển tọa độ pixel đã khử méo sang vector tia chuẩn hóa (unit ray vector) trong hệ camera:
  $$\mathbf{d}_{cam} = \frac{\left[\frac{u - c_x}{f_x}, \frac{v - c_y}{f_y}, 1\right]^T}{\left\|\left[\frac{u - c_x}{f_x}, \frac{v - c_y}{f_y}, 1\right]\right\|}$$
- **`ray_plane_intersection(ray_origin, ray_direction, plane_z=0.0)`**:
  - Giao tia $P(t) = C + t \cdot \mathbf{d}_{world}$ với mặt phẳng bàn $z = \text{plane\_z}$.
  - Giải $t = \frac{\text{plane\_z} - C_z}{d_z}$.
  - Kiểm tra điều kiện song song ($|d_z| < 10^{-7}$) và điều kiện điểm nằm sau camera ($t \le 0$).
- **`pixel_to_3d(pixel, pose, K, dist, plane_z=0.0)`**:
  - Hàm tích hợp toàn diện: pixel $\to$ khử méo $\to$ tia camera $\to$ xoay sang world ($\mathbf{d}_{world} = R^T \mathbf{d}_{cam}$) $\to$ lấy tâm $C$ từ pose $\to$ giao mặt bàn $z = \text{plane\_z}$.
- **`ProjectionProcessor` class**:
  - Đóng gói các tham số camera ($K$, dist, plane_z).
  - Khởi tạo trực tiếp từ ma trận hoặc từ `CameraModel.from_camera()`.
  - Cung cấp phương thức `project(pixel, pose)` và `project_batch(pixels, pose)`.

### `scripts/debug_projection.py`
- Script kiểm thử trực quan độc lập chiếu pixel trung tâm và các điểm lân cận sang không gian 3D.

---

## 2. Unit Tests

### `tests/test_projection.py`
```
====================================== 11 passed in 0.21s =======================================
```
- `test_undistort_pixel`: Kiểm tra khử méo điểm ảnh với hệ số méo khác 0.

- `test_pixel_to_ray`: Kiểm tra pixel tâm cho ra vector tia quang học $[0, 0, 1]^T$ đã chuẩn hóa.
- `test_ray_plane_intersection`: Kiểm tra giao tia thẳng đứng với mặt bàn $z=0$ cho ra $[0, 0, 0]$.
- `test_ray_plane_intersection_slanted`: Kiểm tra giao tia nghiêng 45 độ với mặt bàn $z=0$.
- `test_ray_parallel_to_plane`: Kiểm tra tia song song mặt bàn ($d_z = 0$) trả về `(False, None)`.
- `test_ray_behind_camera`: Kiểm tra tia hướng ngược ra sau camera ($t \le 0$) trả về `(False, None)`.
- `test_pixel_to_3d_integration`: Tích hợp đầy đủ từ pixel qua CameraPose đến tọa độ 3D.
- `test_pixel_to_3d_downward_camera`: Kiểm tra trường hợp thực tế camera nhìn chúc xuống bàn.
- `test_projection_processor`: Kiểm tra class `ProjectionProcessor` và hàm `project_batch`.
- `test_projection_processor_from_camera`: Kiểm tra khởi tạo từ `CameraModel`.
- `test_pixel_to_3d_invalid_pose`: Kiểm tra xử lý an toàn khi pose không hợp lệ.

---

## 3. Tiêu chí hoàn thành

- [x] `mono_eye/projection.py` viết hoàn chỉnh
- [x] `undistort_pixel()` hoạt động đúng
- [x] `pixel_to_ray()` hoạt động đúng
- [x] `ray_plane_intersection()` hoạt động đúng
- [x] `pixel_to_3d()` integration đúng
- [x] `ProjectionProcessor` class hoạt động
- [x] `tests/test_projection.py` viết đầy đủ (11 bài test)
- [x] Debug visualization `scripts/debug_projection.py` chạy được
