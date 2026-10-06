# NAVIGATION - Danh sách Tasks cho Antigravity

## Thứ tự thực hiện

```
✅ G00 - Setup (HOÀN THÀNH)
✅ G01 - Test & Verify (HOÀN THÀNH)
✅ G02 - Calibration (HOÀN THÀNH)
✅ G03 - Pose (HOÀN THÀNH)
✅ G04 - Projection (HOÀN THÀNH)
✅ G05 - YOLO & Pipeline (HOÀN THÀNH)
✅ G06 - Visualization (HOÀN THÀNH)
✅ G07 - Analysis & Logging (HOÀN THÀNH)
✅ G08 - Improvements (HOÀN THÀNH)
⬜ G09 - Robot Integration (Dự kiến) ← TIẾP THEO
```

---

## Giai đoạn 3: Viết pose.py (Không cần bảng)

**File:** [TASKS/G03_POSE.md](G03_POSE.md)

**Mục tiêu:** Camera pose estimation từ ChArUco

**Output:**
- `mono_eye/pose.py` hoàn chỉnh
- `tests/test_pose.py`

---

## Giai đoạn 4: Viết projection.py (Không cần bảng)

**File:** [TASKS/G04_PROJECTION.md](G04_PROJECTION.md)

**Mục tiêu:** Pixel → 3D bằng ray-plane intersection

**Output:**
- `mono_eye/projection.py` hoàn chỉnh
- `tests/test_projection.py`

---

## Giai đoạn 5: Viết detect.py & pipeline.py (Không cần bảng)

**File:** [TASKS/G05_YOLO.md](G05_YOLO.md)

**Mục tiêu:** YOLO detection, tracking, và pipeline integration

**Output:**
- `mono_eye/detect.py` hoàn chỉnh
- `mono_eye/pipeline.py` hoàn chỉnh
- `tests/test_detect.py`

---

## Giai đoạn 6: Viết viz.py (Không cần bảng)

**File:** [TASKS/G06_VISUALIZATION.md](G06_VISUALIZATION.md)

**Mục tiêu:** 3D visualization (matplotlib/Open3D)

**Output:**
- `mono_eye/viz.py` hoàn chỉnh
- `tests/test_viz.py`
- `scripts/realtime_viz.py`

---

## Giai đoạn 7: Viết evaluate.py (Không cần bảng)

**File:** [TASKS/G07_ANALYSIS.md](G07_ANALYSIS.md)

**Mục tiêu:** Error analysis và logging infrastructure

**Output:**
- `mono_eye/evaluate.py` hoàn chỉnh
- `tests/test_evaluate.py`
- `scripts/run_evaluation.py`

---

## Giai đoạn 8: Improvements (HOÀN THÀNH)

**File:** [TASKS/G08_IMPROVEMENTS.md](G08_IMPROVEMENTS.md)

**Mục tiêu:** Lọc tia dốc, Kalman Filter, Temporal Smoothing, Triangulation từ 2 góc nhìn

**Output:**
- `mono_eye/filter.py` hoàn chỉnh
- `tests/test_filter.py`
- Tích hợp `TemporalSmoother` vào `mono_eye/pipeline.py`
- `docs/G08_REPORT.md`

---

## Giai đoạn 2: Calibration (HOÀN THÀNH)

**File:** [TASKS/G02_CALIBRATION.md](G02_CALIBRATION.md)

**Mục tiêu:** Calibrate camera (K, D)

**Output:**
- `data/calib/camera.yaml` hoàn chỉnh
- `configs/mono3d.yaml` cập nhật số đo bảng
- `scripts/calibrate_camera.py`
- `docs/G02_REPORT.md`

---

## Commands tổng hợp

```bash
# Test tất cả modules
uv run pytest tests/ -v

# Import tất cả modules
uv run python -c "
from mono_eye.pose import PoseEstimator, CameraPose
from mono_eye.projection import pixel_to_3d, ProjectionProcessor
from mono_eye.detect import ObjectDetector, DetectionResult
from mono_eye.pipeline import MonoEyePipeline
from mono_eye.viz import SimpleVisualizer, create_visualizer
from mono_eye.evaluate import ErrorAnalyzer, GroundTruthLoader
from mono_eye.filter import KalmanTracker3D, TemporalSmoother, triangulate_two_views
print('✅ All modules imported successfully')
"
```

---

## Trạng thái modules

| Module | File | Status | Tests |
|--------|------|--------|-------|
| pose.py | mono_eye/ | ✅ Đã viết | test_pose.py |
| projection.py | mono_eye/ | ✅ Đã viết | test_projection.py |
| detect.py | mono_eye/ | ✅ Đã viết | test_detect.py |
| pipeline.py | mono_eye/ | ✅ Đã viết | test_detect.py |
| viz.py | mono_eye/ | ✅ Đã viết | test_viz.py |
| evaluate.py | mono_eye/ | ✅ Đã viết | test_evaluate.py |
| filter.py | mono_eye/ | ✅ Đã viết | test_filter.py |

---

## Checklist cho Antigravity

### G03 - Pose
- [x] Đọc TASKS/G03_POSE.md
- [x] Viết mono_eye/pose.py hoàn chỉnh
- [x] Viết tests/test_pose.py
- [x] Chạy pytest → passed
- [x] Tạo docs/G03_REPORT.md


### G04 - Projection
- [x] Đọc TASKS/G04_PROJECTION.md
- [x] Viết mono_eye/projection.py hoàn chỉnh
- [x] Viết tests/test_projection.py
- [x] Chạy pytest → passed
- [x] Tạo docs/G04_REPORT.md


### G05 - YOLO & Pipeline
- [x] Đọc TASKS/G05_YOLO.md
- [x] Viết mono_eye/detect.py hoàn chỉnh
- [x] Viết mono_eye/pipeline.py hoàn chỉnh
- [x] Viết tests/test_detect.py
- [x] Chạy pytest → passed
- [x] Tạo docs/G05_REPORT.md


### G06 - Visualization
- [x] Đọc TASKS/G06_VISUALIZATION.md
- [x] Viết mono_eye/viz.py hoàn chỉnh
- [x] Viết tests/test_viz.py
- [x] Chạy pytest → passed
- [x] Tạo docs/G06_REPORT.md

### G07 - Analysis
- [x] Đọc TASKS/G07_ANALYSIS.md
- [x] Viết mono_eye/evaluate.py hoàn chỉnh
- [x] Viết tests/test_evaluate.py
- [x] Chạy pytest → passed
- [x] Tạo docs/G07_REPORT.md

### G08 - Improvements
- [x] Đọc TASKS/G08_IMPROVEMENTS.md
- [x] Viết mono_eye/filter.py hoàn chỉnh
- [x] Tích hợp TemporalSmoother vào pipeline
- [x] Viết tests/test_filter.py
- [x] Chạy pytest → passed
- [x] Tạo docs/G08_REPORT.md

---

## Sau khi hoàn thành G00-G08

1. **Tổng hợp tất cả tests:** `uv run pytest tests/ -v` (82 tests passed 100%)
2. **Integration test:** Chạy full pipeline demo hoặc với webcam
3. **Sẵn sàng cho G09:** Tích hợp Robot (FR5 / ROS / Eye-in-Hand kinematics)
