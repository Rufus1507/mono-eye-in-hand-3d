# Giai đoạn 7: Error Analysis & Logging - Báo cáo

## Ngày: 2026-10-06

## Trạng thái: ✅ HOÀN THÀNH

---

## 1. Module Implementation

### `mono_eye/evaluate.py`
- **`EvaluationResult` dataclass**:
  - Lưu trữ kết quả đo cho một điểm mốc: `timestamp`, `frame_id`, `point_id`, `estimated` $[x, y, z]$, `ground_truth` $[x, y, z]$.
  - Sai số Euclidean tổng thể: `error_total` $= \|\mathbf{p}_{est} - \mathbf{p}_{gt}\|_2$ (mm).
  - Sai số thành phần theo 3 trục: `error_x`, `error_y`, `error_z` (mm).
  - Metadata chất lượng đi kèm: `num_corners` (số góc ChArUco phát hiện), `reproj_error_px` (sai số chiếu lại), `camera_x`, `camera_y`, `camera_z` (tọa độ camera lúc đo).
  - Hàm `to_dict()`: Xuất bản ghi sang dạng từ điển tương thích với CSV.

- **`GroundTruthLoader` class**:
  - Nạp tọa độ mốc thực tế từ file CSV (`configs/ground_truth_points.csv`).
  - Tự động bỏ qua các dòng chú thích `#` và các dòng rỗng.
  - Các hàm: `get_point(point_id)`, `get_all_points()`.

- **`ErrorAnalyzer` class**:
  - Quản lý danh sách kết quả đo `results`.
  - Hàm `compute_error(point_id, estimated, metadata)`: Tính toán sai số 3D so với ground truth và lưu vào bộ nhớ.
  - Hàm `summary_statistics()`: Thống kê đầy đủ các chỉ số:
    - Tổng số mẫu `n_samples`.
    - Sai số tổng `error_total`: Mean, Median, Std, Min, Max, 95th Percentile (P95).
    - Sai số từng trục `error_x`, `error_y`, `error_z`: Mean, Std.
  - Hàm `get_dataframe()` & `group_by(column)`: Hỗ trợ Pandas DataFrame hoặc fallback `SimpleDataFrame` (khi chưa cài thư viện ngoài) để tránh phụ thuộc nặng.

- **`CSVLogger` class**:
  - Ghi nhận liên tục các bản ghi `EvaluationResult` ra file CSV.
  - Hỗ trợ Context Manager (`with CSVLogger(...) as logger:`), tự động tạo thư mục và ghi header.

- **`generate_error_report(csv_path, output_path, ground_truth_path)`**:
  - Tổng hợp dữ liệu từ file CSV log.
  - Xuất báo cáo Markdown chi tiết gồm:
    1. Bảng thống kê chung (Mean, Median, Std, P95, Min, Max).
    2. Bảng phân bố sai số theo từng điểm mốc (`point_id`).
    3. Bảng phân bố sai số theo chất lượng pose (`num_corners`).

### `scripts/run_evaluation.py`
- Script dòng lệnh đánh giá hệ thống:
  - Nạp file hiệu chuẩn camera, bảng ChArUco, và file ground truth.
  - Hỗ trợ cờ `--demo` tạo dữ liệu mô phỏng synthetic và tự động xuất file log CSV và báo cáo Markdown.

---

## 2. Unit Tests

### `tests/test_evaluate.py`
- `test_ground_truth_loader`: Kiểm tra nạp file CSV, bỏ qua comment `#`, lấy điểm theo ID và xử lý khi ID không tồn tại.
- `test_evaluation_result_to_dict`: Kiểm tra cấu trúc trường dữ liệu của `EvaluationResult`.
- `test_error_analyzer`: Kiểm tra tính toán sai số Euclidean, tính đúng khoảng cách hình học ($\sqrt{3^2+4^2}=5.0$), tổng hợp `summary_statistics()`.
- `test_csv_logger_and_report_generation`: Kiểm tra luồng ghi log CSV và sinh file báo cáo Markdown tự động.

---

## 3. Tiêu chí hoàn thành

- [x] `mono_eye/evaluate.py` viết hoàn chỉnh
- [x] `GroundTruthLoader` class
- [x] `ErrorAnalyzer` class
- [x] `CSVLogger` class
- [x] `EvaluationResult` dataclass
- [x] `generate_error_report()` function
- [x] `tests/test_evaluate.py` viết và pass
- [x] `scripts/run_evaluation.py` tạo hoàn chỉnh
