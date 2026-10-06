# PROMPT: Giai đoạn 8 - Improvements & Filtering (VIẾT CODE)

## Mục tiêu
Tối ưu hóa độ chính xác và độ ổn định của hệ thống định vị 3D:
1. Lọc tia chiếu dốc / gần song song mặt bàn (`ray_z` threshold).
2. Làm mượt chuỗi tọa độ 3D theo thời gian bằng Moving Average, Median Filter và Kalman Filter 3D.
3. Tổng hợp quan sát đa khung hình (`aggregate_observations`).
4. Định vị 3D qua tam giác đạc từ 2 góc nhìn camera (`triangulate_two_views`).
5. Tích hợp các bộ lọc trực tiếp vào `mono_eye/pipeline.py`.

---

## Yêu cầu module: `mono_eye/filter.py`

### 1. Hàm lọc tia chiếu góc cực hạn (`filter_parallel_ray`)
- Kiểm tra hướng tia chiếu trong hệ world frame.
- Loại bỏ các tia có $|v_z| < \text{threshold}$ (mặc định 0.1, tương đương góc $< \approx 5.7^\circ$ so với mặt bàn).

### 2. Bộ lọc Kalman 3D (`KalmanTracker3D`)
- Theo dõi trạng thái $\mathbf{x} = [x, y, z, \dot{x}, \dot{y}, \dot{z}]^T$.
- Mô hình vận tốc không đổi (Constant Velocity).
- Các hàm `predict()` và `update(measurement)`.

### 3. Bộ lọc mượt Moving Average & Median (`TemporalSmoother`)
- Lưu buffer $N$ khung hình gần nhất theo từng `track_id`.
- Hỗ trợ phương pháp `"mean"` và `"median"`.

### 4. Tam giác đạc 2 góc nhìn (`triangulate_two_views`)
- Nhận vào 2 cặp `(ray_origin_1, ray_dir_1)` và `(ray_origin_2, ray_dir_2)` hoặc ma trận chiếu $P_1, P_2$.
- Tính điểm giao nhau gần nhất trong không gian 3D (midpoint of shortest segment).

---

## Tiêu chí hoàn thành

- [x] `mono_eye/filter.py` viết hoàn chỉnh
- [x] Lớp `KalmanTracker3D` hoạt động chính xác
- [x] Lớp `TemporalSmoother` hỗ trợ đa đối tượng theo `track_id`
- [x] Hàm `filter_parallel_ray` loại bỏ tia lỗi
- [x] Hàm `triangulate_two_views` khôi phục tọa độ 3D chính xác
- [x] Tích hợp vào `mono_eye/pipeline.py`
- [x] `tests/test_filter.py` viết đầy đủ và pass
- [x] Tạo `docs/G08_REPORT.md`
