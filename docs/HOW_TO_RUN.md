# HƯỚNG DẪN CHẠY HỆ THỐNG

## Tổng quan luồng chạy

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CÁCH CHẠY HỆ THỐNG                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  LẦN ĐẦU (1 lần):                                               │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  1. Setup môi trường (G00)                                │    │
│  │  2. Chuẩn bị vật lý (G01) - In bảng, đo                │    │
│  │  3. Calibrate camera (G02) - Tạo camera.yaml              │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  MỖI LẦN CHẠY:                                                   │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  4. Chạy Pipeline (Realtime hoặc Video)                   │    │
│  │  5. Xem kết quả (3D Viz + CSV Log)                      │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## PHẦN 1: LẦN ĐẦU (Chỉ làm 1 lần)

### Bước 1.1: Setup môi trường

```powershell
# Di chuyển vào thư mục repo
cd D:\Desktop\5\DPL302m\mono-eye-in-hand-3d

# Cài đặt dependencies
uv sync

# Kiểm tra môi trường
uv run python scripts/check_env.py
```

**Kết quả mong đợi:**
```
✅ Python: 3.12
✅ OpenCV: 4.13.0.92
✅ Camera: 0 (1280x720)
✅ Board config: OK
```

---

### Bước 1.2: In và chuẩn bị bảng ChArUco

**1. In bảng:**
```powershell
# Mở file này và in ở 100%
D:\Desktop\5\DPL302m\mono-eye-in-hand-3d\bang_charuco_A4.pdf
```

**2. Đo kích thước bằng thước thép:**
- Chiều ngang: mép ngoài ô đen trái → phải
- Chiều dọc: mép ngoài ô đen trên → dưới
- Đo 3 lần, tính trung bình

**3. Cập nhật config:**
```yaml
# File: configs/mono3d.yaml
board:
  measured:
    board_width_mm: XXX.XX   # ← Số đo thực tế
    board_height_mm: XXX.XX  # ← Số đo thực tế
```

**4. Dán bảng lên bìa cứng và cố định lên bàn**

---

### Bước 1.3: Calibrate Camera

```powershell
# 1. Cố định camera settings (tắt autofocus, đặt 1280x720)

# 2. Capture ảnh
cd D:\Desktop\5\DPL302m\mono-eye-in-hand-3d
.\run_fov.ps1 capture --camera 0 --name calib_session --width 1280 --height 720 --freeze-focus 1
```
- Chụp 30-40 ảnh với các góc đa dạng
- Nghiêng 20-45°, phủ 4 góc frame

```powershell
# 3. Analyze với bootstrap
.\run_fov.ps1 analyze sessions\calib_session --bootstrap 100

# 4. Export
.\run_fov.ps1 export sessions\calib_session --name "my_camera"

# 5. Copy camera.yaml
copy sessions\calib_session\runs\<run_id>\export\camera.yaml data\calib\camera.yaml
```

---

## PHẦN 2: CHẠY HỆ THỐNG (Mỗi lần)

### Cách 1: Realtime Camera (Khuyến nghị)

```powershell
cd D:\Desktop\5\DPL302m\mono-eye-in-hand-3d

# Chạy với visualization 3D
uv run python scripts/realtime_viz.py
```

**Kết quả:**
- Cửa sổ 1: Camera feed với debug overlay
- Cửa sổ 2: 3D visualization (matplotlib)

**Phím điều khiển:**
- `Q`: Thoát
- `SPACE`: Pause

---

### Cách 2: Realtime Camera (Không có camera)

```powershell
# Chạy demo mode (synthetic trajectory)
uv run python scripts/realtime_viz.py --demo
```

**Kết quả:** Hiển thị 3D với camera di chuyển synthetic

---

### Cách 3: Xử lý Video

```powershell
# Xử lý video đã quay
uv run python scripts/realtime_viz.py --video path\to\video.mp4 --output path\to\output.mp4
```

---

## PHẦN 3: XEM KẾT QUẢ

### 3.1 Output trên Terminal/Console

```
Frame: 150
├── Pose:
│   ├── Position: (45.2, -23.1, 287.5) mm
│   ├── Rotation: pitch=15.2°, yaw=-3.1°, roll=2.3°
│   ├── Corners: 20
│   └── Reproj Error: 0.45 px
│
├── Detections:
│   ├── ID: 5, Class: box, Position: (125.5, 80.3, 0.0) mm
│   └── ID: 7, Class: cylinder, Position: (-45.2, 120.8, 0.0) mm
│
└── FPS: 28.5
```

---

### 3.2 CSV Log File

```bash
# Log được lưu tại:
results/logs/detections_YYYYMMDD_HHMMSS.csv
```

**Cấu trúc CSV:**
```csv
timestamp,frame_id,track_id,class_name,x_mm,y_mm,z_mm,error_mm,camera_x,camera_y,camera_z
2026-10-06T10:30:15.123,150,5,box,125.5,80.3,0.0,1.2,45.2,-23.1,287.5
2026-10-06T10:30:15.123,150,7,cylinder,-45.2,120.8,0.0,0.8,45.2,-23.1,287.5
```

---

### 3.3 3D Visualization

```
┌─────────────────────────────────────────────────────────────────────┐
│                        3D VISUALIZATION                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│                              Z                                      │
│                              ↑                                      │
│                              │      📷 Camera                      │
│                              │       ▲                              │
│                              │      /│\                             │
│                              │     / │ \                            │
│                              │    /  │  \                          │
│                              │   /   │   \                         │
│                              │  /    │    \                        │
│                              │ 📦     │     📦                     │
│                              │(box)   │    (cylinder)             │
│                              │                                       │
│                              └──────────────────────────────→ X       │
│                                                                      │
│  Đỏ: Camera trajectory                                            │
│  Xanh lá: Vật đứng yên                                           │
│  Vàng: Bàn                                                        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 3.4 Error Report

```powershell
# Tạo báo cáo sai số
uv run python scripts/run_evaluation.py --ground-truth configs/ground_truth_points.csv --output results/logs/evaluation.csv

# Output: results/logs/evaluation_report.md
```

**Nội dung báo cáo:**
```markdown
# Error Analysis Report

## Summary
- Total samples: 500
- Mean error: 1.2 mm
- Median error: 0.9 mm
- 95th percentile: 2.8 mm
- Max error: 4.5 mm

## Error by Distance
| Camera Height | Mean Error |
|--------------|-----------|
| 300mm       | 0.8 mm   |
| 500mm       | 1.5 mm   |
| 700mm       | 3.1 mm   |
```

---

## PHẦN 4: CÁC SCRIPTS

### Scripts có sẵn

| Script | Mục đích | Lệnh |
|--------|-----------|-------|
| `realtime_viz.py` | Realtime visualization | `python scripts/realtime_viz.py` |
| `run_evaluation.py` | Tạo báo cáo sai số | `python scripts/run_evaluation.py` |
| `debug_projection.py` | Debug projection | `python scripts/debug_projection.py` |
| `check_env.py` | Kiểm tra môi trường | `python scripts/check_env.py` |

### Ví dụ sử dụng

```powershell
# Kiểm tra môi trường
uv run python scripts/check_env.py

# Kiểm tra môi trường + camera
uv run python scripts/check_env.py --camera 0

# Chạy visualization với camera thật
uv run python scripts/realtime_viz.py

# Chạy demo mode (không cần camera)
uv run python scripts/realtime_viz.py --demo

# Tạo báo cáo sai số
uv run python scripts/run_evaluation.py --ground-truth configs/ground_truth_points.csv --demo

# Xử lý video
uv run python scripts/realtime_viz.py --video input.mp4 --output output.mp4
```

---

## PHẦN 5: CẤU TRÚC OUTPUT

```
D:\Desktop\5\DPL302m\mono-eye-in-hand-3d\
├── results/
│   ├── logs/
│   │   ├── detections_YYYYMMDD_HHMMSS.csv   # Log chi tiết
│   │   └── evaluation_report.md               # Báo cáo sai số
│   └── viz/
│       └── screenshots/                         # Ảnh capture
├── data/
│   └── calib/
│       └── camera.yaml                        # Calibration data
└── sessions/
    └── calib_session/
        └── runs/
            └── <run_id>/
                ├── result.json               # Kết quả calibration
                └── export/                   # Exported files
```

---

## PHẦN 6: TROUBLESHOOTING

### Lỗi thường gặp

| Lỗi | Nguyên nhân | Cách sửa |
|------|-------------|-----------|
| `camera.yaml not found` | Chưa calibrate | Chạy G02 |
| `ImportError: No module named 'cv2'` | UV environment | `uv sync` |
| Camera không mở được | Index sai | Thử `--camera 1` |
| ChArUco không detect được | Ánh sáng kém | Cải thiện ánh sáng |
| FPS thấp | YOLO nặng | Dùng yolov8n thay vì yolov8m |

### Kiểm tra nhanh

```powershell
# 1. Kiểm tra môi trường
uv run python scripts/check_env.py --camera 0

# 2. Kiểm tra camera.yaml
type data\calib\camera.yaml

# 3. Kiểm tra board config
type configs\mono3d.yaml

# 4. Chạy test
uv run pytest tests/ -v
```

---

## PHẦN 7: VÍ DỤ HOÀN CHỈNH

### Scenario: Robot picking

```powershell
# 1. Setup (đã làm lần đầu)
# ...

# 2. Chạy hệ thống
cd D:\Desktop\5\DPL302m\mono-eye-in-hand-3d
uv run python scripts/realtime_viz.py

# 3. Quan sát output:
# - Tọa độ 3D của vật
# - Camera position & orientation
# - Quỹ đạo camera

# 4. Đọc log CSV
notepad results/logs/detections_latest.csv

# 5. Tạo báo cáo
uv run python scripts/run_evaluation.py --ground-truth configs/ground_truth_points.csv
```

### Output mẫu:

```
========================================
 Robot Picking - Live Output
========================================

Timestamp: 2026-10-06 10:30:15.123
----------------------------------------
 Object: box (ID: 5)
   Position: X=125.5mm, Y=80.3mm, Z=0.0mm
   Confidence: 95%

 Object: cylinder (ID: 7)
   Position: X=-45.2mm, Y=120.8mm, Z=0.0mm
   Confidence: 87%
----------------------------------------
 Camera: position=(45.2, -23.1, 287.5)mm
         orientation=pitch=15.2°, yaw=-3.1°
         quality=20 corners, error=0.45px
----------------------------------------
 FPS: 28.5
========================================
```

---

## TÓM TẮT CÁCH CHẠY

```powershell
# =====================
# LẦN ĐẦU (1 lần)
# =====================

# 1. Setup
uv sync

# 2. In bảng, đo, dán (thủ công)

# 3. Calibrate
.\run_fov.ps1 capture --camera 0 --name calib_session --width 1280 --height 720 --freeze-focus 1
.\run_fov.ps1 analyze sessions\calib_session --bootstrap 100
.\run_fov.ps1 export sessions\calib_session --name "my_camera"
copy sessions\calib_session\runs\<run_id>\export\camera.yaml data\calib\camera.yaml

# =====================
# MỖI LẦN CHẠY
# =====================

# Chạy hệ thống
uv run python scripts/realtime_viz.py

# Xem log
notepad results/logs\detections_latest.csv

# Tạo báo cáo
uv run python scripts/run_evaluation.py --ground-truth configs/ground_truth_points.csv
```

---

**Chúc bạn chạy thành công! 🚀**
