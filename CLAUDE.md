# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Dự án **mono-eye-in-hand-3D** gồm hai phần chính:
1. **`fov_tool/`** - Công cụ đo FOV và hiệu chuẩn camera bằng ChArUco board (repo gốc: camera-fov-charuco)
2. **`mono_eye/`** - Mở rộng: từ một camera monocular, ước lượng tọa độ 3D của vật trên mặt bàn

**Mục tiêu cuối:** Camera gắn trên tay robot, dùng tấm ChArUco làm mốc, đổi pixel (từ YOLO detection) thành tọa độ 3D.

---

## Commands

### Setup & Environment
```powershell
uv sync                    # Cài tất cả dependencies cơ bản
uv run python scripts/check_env.py           # Kiểm tra môi trường
uv run python scripts/check_env.py --camera 0 # Thêm kiểm tra camera
```

### Development Dependencies
```powershell
uv sync --group detect     # Giai đoạn 5: ultralytics (YOLO, PyTorch)
uv sync --group viz        # Giai đoạn 6: rerun-sdk (3D visualization)
uv sync --group analysis   # Giai đoạn 7-8: pandas, matplotlib, scipy
```

### Tests
```powershell
uv run pytest tests/ -v                    # Tất cả tests
uv run pytest tests/test_mono_eye.py -v    # Tests mono_eye
uv run pytest tests/test_fov.py -v         # Tests fov_tool
```

### Calibration (fov_tool)
```powershell
.\run_fov.ps1 capture --camera 0 --name my_session --width 1280 --height 720
.\run_fov.ps1 analyze sessions\<id> --bootstrap 100
.\run_fov.ps1 export sessions\<id> --name "my_camera"
```

---

## Architecture

### Module Structure

```
mono_eye/           # Phần mở rộng (đơn vị: mm)
├── config.py       # Đọc configs/mono3d.yaml
├── camera_io.py    # Đọc camera.yaml (K, D) từ do_fov.py export
├── board_scale.py # Tính cạnh ô thật từ số đo thước
├── pose.py         # Giai đoạn 3: Camera pose từ ChArUco + solvePnP
├── projection.py   # Giai đoạn 4: Pixel → 3D (ray-plane intersection)
├── detect.py       # Giai đoạn 5: YOLO detection + tracking
├── filter.py       # Giai đoạn 8: Kalman, Temporal Smoothing, Triangulation
├── viz.py          # Giai đoạn 6: 3D visualization (matplotlib/Open3D)
├── evaluate.py     # Giai đoạn 7: Error analysis, CSV logging
└── pipeline.py     # Full pipeline orchestration

fov_tool/          # Phần hiệu chuẩn gốc (đơn vị: 1.0)
├── board.py       # Đọc cấu hình bảng, tạo CharucoBoard + Detector
├── camera.py      # Mở camera, freeze controls
├── observations.py # Phát hiện góc ChArUco, chấm chất lượng
├── acquisition.py # Auto-capture state machine
├── calibration.py # fit K, D, bootstrap error, hold-out validation
├── geometry.py    # pixel↔ray, FOV computation
├── export.py      # camera.yaml, camera.json, report.html
└── session.py     # Immutable sessions, runs
```

### Pipeline Flow

```
Camera Frame (BGR)
    │
    ▼
┌─────────────┐
│ PoseEstimator │ ← ChArUco corners + solvePnP → rvec, tvec
└─────────────┘
    │
    ▼
┌─────────────┐
│ObjectDetector│ ← YOLO: bbox → reference pixel (bottom_center)
└─────────────┘
    │
    ▼
┌─────────────┐
│ Projection   │ ← pixel + pose → (x, y, z) trên mặt bàn
└─────────────┘
    │
    ▼
3D Position (mm) → Optional: TemporalSmoother / KalmanFilter
```

---

## Key Conventions

### Units
- **mm everywhere** - Tất cả tọa độ 3D, kích thước bảng, khoảng cách đều dùng milimét

### Coordinate System
- **World frame**: gắn với tấm ChArUco, z = 0 là mặt bàn
- **Camera pose**: `rvec, tvec` từ solvePnP biến tấm → camera
- **Camera center**: `C = -R^T @ tvec`

### ChArUco Board
- **Một nguồn sự thật**: File `bang_calib_*.yaml` từ `tao_bang.py`, không lặp lại thông số trong `mono_eye`
- **Cạnh ô thật**: Đo bằng thước thép → `configs/mono3d.yaml` → `mono_eye.board_scale`
- **OpenCV version**: Giữ 4.13.x cho cả sinh bảng lẫn detection

### Camera Settings
- **Một độ phân giải cố định**: K chỉ đúng cho chế độ lúc calibrate
- **`CameraModel.check_frame`**: Từ chối frame khác kích thư�ộc thước

### Quality Gates
- `min_charuco_corners: 6` (trong configs/mono3d.yaml)
- `max_reprojection_error_px: 1.5`

---

## Data Files

| File | Mục đích |
|------|-----------|
| `configs/mono3d.yaml` | Cấu hình chung (camera, board, world_frame) |
| `configs/ground_truth_points.csv` | Tọa độ điểm chuẩn (x_mm, y_mm, z_mm) |
| `data/calib/camera.yaml` | Ma trận K, D (copy từ fov_tool export) |
| `bang_calib_A4.yaml` | Cấu hình bảng ChArUco |
| `sessions/<id>/` | Phiên hiệu chuẩn fov_tool |

---

## Phase Status (Roadmap)

| Phase | Module | Status |
|-------|--------|--------|
| G00-G02 | Setup, Physical, Calibration | ✅ Hoàn thành |
| G03-G07 | Pose, Projection, YOLO, Viz, Analysis | ✅ Hoàn thành (38 tests) |
| G08 | Improvements (Kalman, Smoothing, Triangulation) | ✅ Hoàn thành (6 tests) |
| G09 | Robot Integration (FR5) | 📋 Dự kiến |

**Total Tests:** 82 passed, 0 failed

---

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| `cv2 has no attribute 'aruco'` | opencv-python thay vì opencv-contrib-python | `uv sync --reinstall-package opencv-contrib-python` |
| Camera index thay đổi | USB re-plug | Thử `--camera 1`, `--backend dshow` |
| UTF-8 BOM issues | PowerShell 5.1 đọc file có dấu | Dùng file ASCII hoặc thêm BOM |
| Board anisotropy > 1.5% | Máy in co giãn không đều | In lại bảng |
| Pose = NaN | solvePnP không hội tụ | Tăng số góc, kiểm tra K/D |

---

## Important Notes

1. **Không bao giờ đánh giá độ chính xác trên các góc ChArUco đã dùng để giải pose**
2. **fov_tool dùng cạnh ô = 1.0** (K không phụ thuộc thang đo), nhưng **mono_eye cần cạnh ô thật** (tọa độ 3D phụ thuộc thang đo)
3. **Bootstrap error từ fov_tool là độ chụm** (precision), không phải độ đúng (accuracy). Chỉ mốc độc lập mới nói được độ đúng.
