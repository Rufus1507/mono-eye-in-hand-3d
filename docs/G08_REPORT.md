# Giai đoạn 8: Improvements, Filtering & Multi-view Triangulation - Báo cáo

## Ngày: 2026-10-06

## Trạng thái: ✅ HOÀN THÀNH

---

## 1. Module Implementation

### `mono_eye/filter.py`
Module cung cấp các giải pháp lọc nhiễu, làm mượt chuỗi thời gian và định vị 3D nâng cao:

1. **Lọc tia chiếu góc cực hạn (`filter_parallel_ray`)**:
   - Loại bỏ các vector tia chiếu có $|v_z| < 0.1$ (góc nghiêng tới mặt bàn nhỏ hơn $\approx 5.7^\circ$).
   - Tránh hiện tượng khuếch đại sai số pixel thành sai số mặt bàn hàng chục centimet khi camera nhìn từ góc quá lài.

2. **Tam giác đạc từ 2 góc nhìn (`triangulate_two_views`)**:
   - Tái tạo tọa độ 3D độc lập mà không cần giả định vật thể phải nằm trên mặt phẳng $Z = 0$.
   - Tính toán đoạn vuông góc chung ngắn nhất giữa 2 tia chiếu $r_1(t_1)$ và $r_2(t_2)$ từ 2 vị trí camera khác nhau ($C_1, C_2$).
   - Kiểm tra điều kiện hình học: $t_1 > 0, t_2 > 0$ (điểm nằm phía trước cả hai camera) và khoảng cách chéo $\text{skew\_distance} \le \text{max\_skew\_distance}$.

3. **Làm mượt cửa sổ trượt theo thời gian (`TemporalSmoother`)**:
   - Quản lý bộ đệm tọa độ 3D riêng biệt theo từng `track_id`.
   - Hỗ trợ phương pháp `"median"` (kháng ngoại lai mạnh mẽ) và `"mean"` (làm mượt dao động chuyển động).

4. **Bộ lọc Kalman 3D (`KalmanTracker3D`)**:
   - Trạng thái 6 chiều: $[x, y, z, \dot{x}, \dot{y}, \dot{z}]^T$.
   - Mô hình vận tốc không đổi (Constant Velocity).
   - Khử rung giật do nhiễu phát hiện bounding box từ YOLO và chuyển động rung của camera.

5. **Tổng hợp quan sát đa khung hình (`aggregate_observations`)**:
   - Lấy trung vị hoặc trung bình của một tập hợp các quan sát để sinh tọa độ tĩnh đáng tin cậy.

### `mono_eye/pipeline.py`
- Tích hợp trực tiếp `TemporalSmoother` vào luồng `process_frame`.
- Bổ sung các tham số cấu hình: `enable_smoothing: bool`, `smooth_window: int`, `min_ray_z: float`.

---

## 2. Unit Tests

### `tests/test_filter.py`
- `test_filter_parallel_ray`: Kiểm tra loại bỏ tia song song mặt bàn và chấp nhận tia dốc hợp lệ.
- `test_aggregate_observations`: Kiểm tra khả năng kháng ngoại lai của hàm tổng hợp trung vị.
- `test_temporal_smoother`: Kiểm tra làm mượt cửa sổ trượt và quản lý độc lập đa đối tượng theo `track_id`.
- `test_kalman_tracker_3d`: Kiểm tra chu trình `predict()` / `update()` của Kalman Filter 3D.
- `test_triangulate_two_views`: Kiểm tra tam giác đạc 3D chính xác từ 2 góc nhìn, xử lý trường hợp tia song song hoặc điểm phía sau camera.
- `test_pipeline_with_smoothing`: Kiểm tra tích hợp pipeline end-to-end với bộ làm mượt.

---

## 3. Tiêu chí hoàn thành

- [x] `mono_eye/filter.py` viết hoàn chỉnh
- [x] Lớp `KalmanTracker3D` hoạt động chính xác
- [x] Lớp `TemporalSmoother` hỗ trợ đa đối tượng theo `track_id`
- [x] Hàm `filter_parallel_ray` loại bỏ tia lỗi
- [x] Hàm `triangulate_two_views` khôi phục tọa độ 3D chính xác
- [x] Tích hợp vào `mono_eye/pipeline.py`
- [x] `tests/test_filter.py` viết đầy đủ (6 bài test)
- [x] Tạo `docs/G08_REPORT.md`
