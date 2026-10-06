# Giai đoạn 5: YOLO Detection, Tracking & Pipeline - Báo cáo

## Ngày: 2026-10-06

## Trạng thái: ✅ HOÀN THÀNH

---

## 1. Module Implementation

### `mono_eye/detect.py`
- **`Detection` dataclass**:
  - `track_id`: ID theo dõi duy nhất từ tracker (`int` hoặc `None`).
  - `class_id`, `class_name`: Mã và tên lớp đối tượng.
  - `bbox`: Tọa độ bounding box $[x_1, y_1, x_2, y_2]$ trên ảnh (pixels).
  - `confidence`: Điểm số tin cậy.
  - `reference_pixel`: Tọa độ $(u, v)$ điểm chân vật/mặt bàn.
  - `position_3d`: Tọa độ thế giới $(x, y, z)$ trên mặt bàn (mm), tự động tính bằng `pixel_to_3d`.
- **`DetectionResult` dataclass**:
  - `timestamp`, `frame_id`, danh sách `detections`, và `pose` camera liên quan.
- **`ObjectDetector` class**:
  - Tích hợp YOLO (hỗ trợ lazy import khi cài nhóm `detect`, tránh lỗi import khi chạy test cơ bản).
  - Hỗ trợ tracking đa đối tượng (`persist=True`).
  - Hàm `get_reference_pixel(bbox)`: Tự động tính điểm giữa của cạnh dưới (`bottom_center`: $((x_1+x_2)/2, y_2)$) tiếp xúc với mặt bàn $z=0$.
  - Hàm `detect(...)`: Chạy model $\to$ trích xuất box $\to$ lấy điểm tham chiếu $\to$ kết hợp với `CameraPose` và `pixel_to_3d` để sinh tọa độ thế giới 3D.

### `mono_eye/pipeline.py`
- **`MonoEyePipeline` class**:
  - Khởi tạo đầy đủ và tích hợp 3 trụ cột: `PoseEstimator` (ChArUco), `ProjectionProcessor` (3D Ray Intersection), và `ObjectDetector` (YOLO).
  - `process_frame(frame)`: Xử lý 1 khung hình từ camera, ước lượng pose và định vị 3D vật thể cùng lúc.
  - `process_video(video_path, output_path)`: Xử lý video offline, tự động vẽ trục tọa độ 3D (`drawFrameAxes`), bounding boxes, và nhãn tọa độ $(X, Y)$ mm lên video xuất.

---

## 2. Unit Tests

### `tests/test_detect.py`
```
======================================= 7 passed in 0.21s =======================================
```
- `test_reference_pixel_bottom_center`: Kiểm tra tính điểm chạm bàn $((x_1+x_2)/2, y_2)$.

- `test_reference_pixel_center`: Kiểm tra tính điểm tâm box.
- `test_reference_pixel_top_center`: Kiểm tra tính điểm cạnh trên.
- `test_detection_result_dataclass`: Kiểm tra cấu trúc dữ liệu `Detection` và `DetectionResult`.
- `test_detection_with_mock_yolo`: Kiểm tra `ObjectDetector` với Mock YOLO, đảm bảo tọa độ 3D được tính toán chuẩn xác từ mốc điểm ảnh.
- `test_pipeline_initialization`: Kiểm tra khởi tạo pipeline an toàn với `CameraModel`.
- `test_pipeline_process_frame`: Kiểm tra xử lý khung hình tích hợp end-to-end.

---

## 3. Tiêu chí hoàn thành

- [x] `mono_eye/detect.py` viết hoàn chỉnh
- [x] `Detection` và `DetectionResult` dataclasses
- [x] `ObjectDetector` class với:
  - [x] YOLO integration (lazy loading)
  - [x] Tracking support
  - [x] Reference pixel selection
- [x] `mono_eye/pipeline.py` viết hoàn chỉnh
- [x] `MonoEyePipeline` class
- [x] `tests/test_detect.py` viết đầy đủ (7 bài test)
- [x] Code có docstrings rõ ràng
