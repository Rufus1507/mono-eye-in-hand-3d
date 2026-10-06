# PROMPT: Giai đoạn 0 - Setup Môi trường

## Mục tiêu
Có môi trường chạy ổn định, hiểu các repo tham khảo (chỉ đọc, không clone), chốt quy ước trong `configs/mono3d.yaml`.

## Ngữ cảnh

### Repo hiện tại
```
D:\Desktop\5\DPL302m\mono-eye-in-hand-3d\
├── .venv/                    # Virtual environment (sẽ dùng uv)
├── pyproject.toml            # Cấu hình project
├── .python-version           # Python 3.12
├── uv.lock                  # Locked dependencies
├── requirements.txt         # Fallback pip dependencies
├── fov_tool/                # Module hiệu chuẩn camera (đã hoàn thiện)
├── mono_eye/                # Module 3D localization (đang phát triển)
├── configs/                 # Config files
├── scripts/                 # Utility scripts
├── tests/                   # Tests
├── data/                    # Input data (gitignored)
├── results/                 # Output results (gitignored)
├── sessions/                # Calibration sessions (gitignored)
├── bang_calib_A4.yaml       # ChArUco board config
├── bang_charuco_A4.pdf/png   # Bảng in sẵn
└── PHASE_PLAN.md            # Kế hoạch thực hiện
```

### Các repo tham khảo (CHỈ ĐỌC, không clone)
| Repo | URL | Mục đích |
|------|-----|----------|
| tony2guo/charuco-pose-estimation | https://github.com/tony2guo/charuco-pose-estimation | Luồng pose estimation |
| ftPeter/pose-estimation | https://github.com/ftPeter/pose-estimation | Quy trình in, đo, calibrate |
| Paul-Rohit/ArUcoTrackerArena | https://github.com/Paul-Rohit/ArUcoTrackerArena | Giao tia với mặt phẳng |
| Lumeon-Labs/vision-positioning-demo | https://github.com/Lumeon-Labs/vision-positioning-demo | Luồng webcam, pose, tọa độ |

---

## Các bước thực hiện

### 0.1 Kiểm tra Python và uv

**Kiểm tra:**
```bash
python --version
uv --version
```

**Yêu cầu:**
- Python: 3.11 hoặc 3.12
- uv: bất kỳ phiên bản nào

**Nếu chưa có uv:**
```powershell
# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Hoặc dùng pip thay thế
pip install uv
```

### 0.2 Tạo/Cập nhật virtual environment với uv

**Vào thư mục repo và chạy:**
```bash
cd D:\Desktop\5\DPL302m\mono-eye-in-hand-3d
uv sync
```

**Kết quả mong đợi:**
```
Using CPython 3.12 interpreter
Creating virtual environment at: .venv
Using seed dependencies from lock file
Resolved 6 packages in XXXms
Prepared 6 packages in XXXms
Installed 6 packages in XXXms
  + numpy (2.x.x)
  + opencv-contrib-python (4.13.x)
  + pillow (10.x.x)
  + pyyaml (6.x.x)
  + pytest (8.x.x)
```

### 0.3 Kiểm tra OpenCV và ArUco module

**Chạy:**
```bash
uv run python -c "import cv2; print('OpenCV:', cv2.__version__); print('Has aruco:', hasattr(cv2, 'aruco'))"
```

**Kết quả mong đợi:**
```
OpenCV: 4.13.x
Has aruco: True
```

**Nếu `Has aruco: False`:**
- Gỡ opencv-python nếu có: `uv pip uninstall opencv-python`
- Chạy lại: `uv sync`

### 0.4 Kiểm tra camera

**Liệt kê camera:**
```bash
uv run python -c "import cv2; cap = cv2.VideoCapture(0); print('Camera 0:', cap.isOpened()); cap.release()"
```

**Nếu camera 0 không mở được:**
```bash
uv run python -c "import cv2; cap = cv2.VideoCapture(1); print('Camera 1:', cap.isOpened()); cap.release()"
```

### 0.5 Chạy tests hiện có

**Kiểm tra fov_tool:**
```bash
uv run pytest tests/test_fov.py -v
```

**Kết quả mong đợi:** Tất cả tests pass

### 0.6 Cập nhật configs/mono3d.yaml

**Đọc file hiện tại và cập nhật:**
```yaml
# File: configs/mono3d.yaml
# QUY ƯỚC CHUNG - Thêm phần logging schema

units: mm

camera:
  index: 0                         # Có thể đổi sau khi cắm lại
  width: 1280                      # Cố định cho cả dự án
  height: 720
  calib_file: data/calib/camera.yaml  # Tạo sau GĐ2

board:
  file: bang_calib_A4.yaml         # Cùng file với do_fov.py capture
  measured:
    board_width_mm: null           # Điền sau GĐ1
    board_height_mm: null
  max_anisotropy: 0.015

world_frame:
  origin: "góc tấm (kiểm chứng ở GĐ3)"
  z_axis: "hướng lên khỏi mặt bàn (z=0)"
  table_plane_z_mm: 0.0

quality_gate:
  min_charuco_corners: 6
  max_reprojection_error_px: 1.5

# THÊM MỚI: Logging schema
logging:
  enabled: true
  format: csv
  output_dir: results/logs
  columns:
    - timestamp
    - frame_id
    - session_id
    - num_charuco_corners
    - reproj_error_px
    - camera_x_mm
    - camera_y_mm
    - camera_z_mm
    - camera_pitch_deg
    - camera_yaw_deg
    - camera_roll_deg
    - track_id
    - class_name
    - point_x_mm
    - point_y_mm
    - point_z_mm
    - error_mm
```

### 0.7 Tạo cấu trúc thư mục

**Tạo thư mục nếu chưa có:**
```bash
mkdir -p data/calib
mkdir -p data/ground_truth
mkdir -p results/logs
mkdir -p results/viz
```

**Verify cấu trúc cuối cùng:**
```
D:\Desktop\5\DPL302m\mono-eye-in-hand-3d\
├── data/
│   ├── calib/                  # Chứa camera.yaml (sau GĐ2)
│   └── ground_truth/           # Chứa ground truth points (sau GĐ1)
├── results/
│   ├── logs/                   # CSV logs
│   └── viz/                    # Visualization output
└── ... (các file khác giữ nguyên)
```

### 0.8 Thử chạy smoke test

**Smoke test cho pose module (chưa implement đầy đủ):**
```bash
uv run python -c "
from fov_tool.board import load_board
board, detector = load_board('bang_calib_A4.yaml')
print('Board loaded:', board)
print('Detector type:', type(detector).__name__)
"
```

---

## Báo cáo cần tạo

### File: `docs/G00_REPORT.md`

```markdown
# Giai đoạn 0: Setup Môi trường - Báo cáo

## Ngày: YYYY-MM-DD

## Kết quả kiểm tra

### Python và uv
- Python version: X.X.X
- uv version: X.X.X

### Dependencies
| Package | Version | Status |
|---------|---------|--------|
| numpy | X.X.X | ✅ |
| opencv-contrib-python | X.X.X | ✅ |
| PyYAML | X.X.X | ✅ |
| Pillow | X.X.X | ✅ |
| pytest | X.X.X | ✅ |

### OpenCV ArUco
- OpenCV version: X.X.X
- Has aruco: True/False

### Camera
- Camera 0: Opens/Doesn't open
- Camera 1: Opens/Doesn't open

### Tests
- test_fov.py: X/21 passed

## Cấu trúc thư mục
```
data/
├── calib/
└── ground_truth/
results/
├── logs/
└── viz/
```

## Ghi chú
- Ghi lại bất kỳ vấn đề nào gặp phải
- Ghi lại camera index thực tế
- Ghi lại các giải pháp đã thử

## Trạng thái: ✅ HOÀN THÀNH / ❌ CHƯA XONG
```

---

## Tiêu chí hoàn thành

- [x] `uv run python -c "import cv2; print(cv2.__version__)"` → 4.13.x
- [x] `hasattr(cv2, 'aruco')` → True
- [x] Camera đọc được ở đúng resolution (1280x720)
- [x] `pytest tests/test_fov.py` → passed
- [x] `configs/mono3d.yaml` đã cập nhật với logging schema
- [x] Cấu trúc thư mục data/, results/ đã tạo
- [x] File `docs/G00_REPORT.md` đã tạo

---

## Lỗi hay gặp và xử lý

| Lỗi | Nguyên nhân | Xử lý |
|------|-------------|--------|
| `ModuleNotFoundError: No module named 'cv2'` | Chưa activate venv hoặc uv sync lỗi | `uv sync` lại |
| `cv2 has no attribute 'aruco'` | Cài opencv-python thay vì opencv-contrib-python | `uv pip uninstall opencv-python opencv-python-headless` rồi `uv sync` |
| Camera index thay đổi | Cắm lại USB | Thử `--camera 1`, `--camera 2` |
| `uv: command not found` | uv chưa cài | Cài theo hướng dẫn 0.1 |
| UTF-8 BOM issues với PowerShell | PowerShell 5.1 đọc file có dấu | Dùng ASCII hoặc thêm BOM |
| Tests fail với path separators | Windows vs Unix path | Chạy trên Windows |

---

## Repo tham khảo (chỉ đọc online)

### tony2guo/charuco-pose-estimation
- **URL:** https://github.com/tony2guo/charuco-pose-estimation
- **Mục đích:** Tham khảo luồng pose estimation
- **Lấy gì:** Luồng code, cách dùng solvePnP với CharUco
- **Lưu ý:** API ArUco có thể cũ, cần kiểm tra với OpenCV 4.13

### ftPeter/pose-estimation
- **URL:** https://github.com/ftPeter/pose-estimation
- **Mục đích:** Quy trình in, đo, calibrate
- **Lấy gì:** Best practices cho việc in bảng, đo kích thước

### Paul-Rohit/ArUcoTrackerArena
- **URL:** https://github.com/Paul-Rohit/ArUcoTrackerArena
- **Mục đích:** Giao tia với mặt phẳng (ray-plane intersection)
- **Lấy gì:** Công thức toán học, script đo sai số

### Lumeon-Labs/vision-positioning-demo
- **URL:** https://github.com/Lumeon-Labs/vision-positioning-demo
- **Mục đích:** Luồng hoàn chỉnh từ webcam đến tọa độ 3D
- **Lấy gì:** Pipeline tổng thể, cách ghép các bước

---

## Commands tổng hợp

```bash
# 1. Di chuyển vào repo
cd D:\Desktop\5\DPL302m\mono-eye-in-hand-3d

# 2. Sync dependencies
uv sync

# 3. Kiểm tra OpenCV
uv run python -c "import cv2; print(cv2.__version__, hasattr(cv2, 'aruco'))"

# 4. Kiểm tra camera
uv run python -c "import cv2; cap = cv2.VideoCapture(0); print('OK' if cap.isOpened() else 'FAIL'); cap.release()"

# 5. Chạy tests
uv run pytest tests/test_fov.py -v

# 6. Tạo thư mục
mkdir -p data/calib data/ground_truth results/logs results/viz
```

---

## Output mong đợi từ Antigravity

Sau khi hoàn thành, Antigravity cần tạo:
1. Xác nhận tất cả commands chạy thành công
2. Screenshot output hoặc paste terminal output
3. File `docs/G00_REPORT.md` với đầy đủ thông tin
4. Danh sách các vấn đề gặp phải (nếu có) và cách giải quyết
