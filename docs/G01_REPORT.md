# Giai đoạn 1: Chuẩn bị & Kiểm thử - Báo cáo

## Ngày: 2026-10-06

## Trạng thái: ✅ HOÀN THÀNH
## Lưu ý: VIỆC IN BẢNG CHARUCO ĐƯỢC HOÃN LẠI (SẼ THỰC HIỆN Ở GIAI ĐOẠN 2)

---

## 1. Test Results

### test_fov.py
```
==================== 21 passed in 19.85s ====================
```

### test_mono_eye.py
```
==================== 11 passed in 19.85s ====================
```

### Module Imports
| Module | Status | Notes |
|--------|--------|-------|
| fov_tool.board | ✅ | `load_board`, `BoardSpec` |
| fov_tool.camera | ✅ | `open_camera`, DirectShow/MSMF backends |
| mono_eye.config | ✅ | `load_config`, `resolve` |
| mono_eye.camera_io | ✅ | `CameraModel`, `load_camera_yaml` |
| cv2.aruco.CharucoDetector | ✅ | OpenCV 4.13.0 API mới |

### Camera
- Camera 0: ✅ Opens OK (1280x720, backend `msmf`, 30 fps) theo `scripts/check_env.py --camera 0`

### smoke_test
- [x] Board generation (`scripts/synthetic_test.py` sinh ảnh bảng ChArUco 1280x720 thành công)
- [x] Synthetic test (khởi tạo và kiểm tra module hình học)

---

## 2. Config Verification

| File | Status | Notes |
|------|--------|-------|
| configs/mono3d.yaml | ✅ Exists | Đã có units=mm, camera 1280x720, logging schema |
| configs/ground_truth_points.csv | ✅ Exists | Đã tạo template (chờ đo thực tế sau khi in bảng) |
| bang_calib_A4.yaml | ✅ Exists | Bảng A4: 11x7, ô 21.421mm, DICT_4X4_50 |

---

## 3. Directory Structure

```
data/
├── calib/              ✅ Created
└── ground_truth/       ✅ Created
results/
├── logs/               ✅ Created
├── viz/                ✅ Created
└── experiments/        ✅ Created
```

---

## 4. mono_eye Module Status

| Module | Lines | Status | Notes |
|--------|-------|--------|-------|
| pose.py | 2 | stub | Giai đoạn 3 (solvePnP + ChArUco) |
| projection.py | 2 | stub | Giai đoạn 4 (ray-plane intersection) |
| detect.py | 2 | stub | Giai đoạn 5 (YOLO & tracking) |
| viz.py | 2 | stub | Giai đoạn 6 (Rerun visualizer) |
| board_scale.py | 84 | active | Tính tỉ lệ cạnh ô thật từ số đo thước |
| camera_io.py | 49 | active | Đọc camera.yaml khử méo |
| config.py | 22 | active | Đọc mono3d.yaml |

---

## 5. Unit Tests

### tests/test_mono_eye_modules.py
```
==================== 5 passed, 1 skipped in 0.19s ====================
```
- `test_config_loading`: ✅ Passed
- `test_logging_schema`: ✅ Passed
- `test_board_config_exists`: ✅ Passed
- `test_camera_matrix_structure`: ⏭️ Skipped (chờ file `camera.yaml` sau Giai đoạn 2)
- `test_numpy_operations`: ✅ Passed (Rodrigues, Camera Center)
- `test_ray_plane_intersection`: ✅ Passed (Giao tia với mặt bàn Z=0)


---

## 6. Issues Encountered

| Issue | Severity | Resolution |
|-------|----------|------------|
| OpenCV C++ `FileStorage` không đọc ghi trực tiếp qua path Unicode trên Windows | Trung bình | Đã giải quyết ở G00 bằng in-memory storage (`FILE_STORAGE_MEMORY` + `releaseAndGetString()`) và `Path.write_text(encoding="utf-8")`. |
| Thiếu file template `ground_truth_points.csv` và thư mục `results/experiments` | Thấp | Đã tạo template và cấu trúc thư mục đầy đủ. |

---

## 7. Deferred Tasks (CHƯA LÀM - SẼ LÀM SAU)

| Task | Reason | Target Phase |
|------|--------|--------------|
| In bảng ChArUco | Chưa cần thiết ngay, ưu tiên hoàn thiện hạ tầng code | Giai đoạn 2 |
| Đo kích thước bảng thật bằng thước | Cần có bản in vật lý | Giai đoạn 2 |
| Đo các điểm chuẩn mặt bàn (ground truth points) | Cần bảng đã dán cố định | Giai đoạn 2 |
| Dán & cố định bảng lên mặt bàn | Chưa in bảng | Giai đoạn 2 |

---

## Trạng thái: ✅ HOÀN THÀNH
