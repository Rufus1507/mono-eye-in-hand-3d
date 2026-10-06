# Giai đoạn 6: 3D Visualization - Báo cáo

## Ngày: 2026-10-06

## Trạng thái: ✅ HOÀN THÀNH

---

## 1. Module Implementation

### `mono_eye/viz.py`
- **Các Dataclass cốt lõi**:
  - `SceneObject`: Biểu diễn vật thể trong không gian 3D với tên nhãn, tọa độ `position` $[x, y, z]$ (mm), màu sắc RGB, kích thước `size`, và kiểu hình học (`sphere`, `box`, `mesh`).
  - `TablePlane`: Cấu hình mặt phẳng bàn làm việc với biên độ tọa độ `bounds` $(x_{min}, x_{max}, y_{min}, y_{max}, z)$, màu sắc và độ trong suốt `alpha`.
  - `CameraView`: Cấu hình tư thế góc nhìn camera với tọa độ tâm camera `position`, vector quay `rotation` (rvec Rodrigues), và góc mở `fov`.
- **`SimpleVisualizer` class**:
  - Hỗ trợ Matplotlib 3D (`Axes3D`) với khả năng tương thích cao, đồng thời tích hợp lớp fallback mock (`DummyAxes3D`, `DummyFigure`) khi môi trường chưa cài matplotlib nhằm tránh crash trong các bài unit test tự động.
  - Các hàm hiển thị chuyên biệt:
    - `draw_table(x_range, y_range, z)`: Vẽ mặt bàn 3D và khung dây lưới (wireframe).
    - `draw_board_outline(corners, z, color)`: Vẽ khung chữ nhật đường biên của tấm chuẩn ChArUco.
    - `draw_camera(position, rotation, scale, color)`: Vẽ marker camera hình nón/chóp cùng tia chỉ hướng quang học $+Z_{cam}$ chiếu sang hệ tọa độ thế giới ($R^T [0, 0, 1]^T$).
    - `draw_object(position, name, color, size)`: Vẽ điểm đánh dấu vật thể và tên nhãn tương ứng.
    - `draw_trajectory(positions, color, alpha)`: Vẽ quỹ đạo đường bay của camera qua thời gian.
    - `clear()`, `add_text()`, `pause()`, `show()`, `save()`: Phục vụ tương tác và tạo animation thời gian thực.
- **`Open3DVisualizer` class**:
  - Tích hợp Open3D renderer với hình học 3D chất lượng cao (hệ trục tọa độ RGB, khối hộp mặt bàn mỏng, quả cầu biểu diễn vật thể).
- **Hàm khởi tạo linh hoạt `create_visualizer(backend)`**:
  - Chuyển đổi giữa backend `"matplotlib"` và `"open3d"`.

### `scripts/realtime_viz.py`
- Tích hợp hiển thị 2D webcam và cửa sổ 3D đồng bộ.
- Tự động chuyển sang chế độ mô phỏng trực quan (`--demo` synthetic trajectory) khi chưa kết nối webcam vật lý hoặc chưa có file cân chỉnh camera.

---

## 2. Unit Tests

### `tests/test_viz.py`
- `test_import_visualizer`: Kiểm tra việc import đầy đủ các thành phần từ `mono_eye.viz`.
- `test_scene_object_dataclass`: Kiểm tra khởi tạo và các trường dữ liệu của `SceneObject`.
- `test_table_plane_dataclass`: Kiểm tra cấu hình biên và thuộc tính của `TablePlane`.
- `test_camera_view_dataclass`: Kiểm tra vị trí `position`, góc quay `rotation` và `fov` của `CameraView`.
- `test_create_visualizer_factory`: Kiểm tra factory function cho cả backend `matplotlib` và `open3d`.
- `test_simple_visualizer_init`: Kiểm tra việc tạo figure, axes 3D và các tham số kích thước.
- `test_simple_visualizer_draw_methods`: Kiểm tra đầy đủ các phương thức vẽ `draw_table`, `draw_board_outline`, `draw_camera`, `draw_object`, `draw_trajectory`, `add_text`, và `clear`.

---

## 3. Tiêu chí hoàn thành

- [x] `mono_eye/viz.py` viết hoàn chỉnh
- [x] `SimpleVisualizer` class hoạt động
- [x] `Open3DVisualizer` class (bonus)
- [x] Methods: `draw_table`, `draw_camera`, `draw_object`, `draw_trajectory`
- [x] Realtime update support
- [x] `tests/test_viz.py` viết đầy đủ (7 bài test)
- [x] Script `scripts/realtime_viz.py` chạy được (hỗ trợ cả camera thực và `--demo`)
