# BÁO CÁO: TOÀN BỘ GIAI ĐOẠN CÒN LẠI

## Những việc cần làm để hoàn thành dự án

---

**Ngày:** 2026-10-06  
**Trạng thái dự án:** ~85% Hoàn thành  
**Còn lại:** G02 (Camera Calibration), G09 (Robot Integration)

---

## MỤC LỤC

1. [Tổng quan tình trạng](#1-tổng-quan-tình-trạng)
2. [G02: Camera Calibration](#2-g02-camera-calibration)
3. [G03-G08: Đã hoàn thành - Tóm tắt](#3-g03-g08-đã-hoàn-thành---tóm-tắt)
4. [G09: Robot Integration (FR5)](#4-g09-robot-integration-fr5)
5. [Timeline tổng hợp](#5-timeline-tổng-hợp)
6. [Checklist hoàn thành](#6-checklist-hoàn-thành)

---

## 1. TỔNG QUAN TÌNH TRẠNG

### 1.1 Đã hoàn thành

| Giai đoạn | Nội dung | Tests | Status |
|:---:|---|:---:|:---:|
| **G00** | Setup môi trường | 32 | ✅ Hoàn thành |
| **G01** | Chuẩn bị infrastructure | 11 | ✅ Hoàn thành |
| **G03** | Pose Estimation | 9 | ✅ Hoàn thành |
| **G04** | Projection (pixel→3D) | 11 | ✅ Hoàn thành |
| **G05** | Detection & Pipeline | 7 | ✅ Hoàn thành |
| **G06** | Visualization | 7 | ✅ Hoàn thành |
| **G07** | Evaluation | 4 | ✅ Hoàn thành |
| **G08** | Filtering & Improvements | 6 | ✅ Hoàn thành |

**Tổng: 82 tests passed (100%)**

### 1.2 Chưa hoàn thành

| Giai đoạn | Nội dung | Trạng thái |
|:---:|---|:---:|
| **G02** | Camera Calibration | ⏳ Cần làm ngay |
| **G09** | Robot Integration (FR5) | 📋 Cần robot FR5 |

### 1.3 Dependency giữa các giai đoạn

```
┌─────────────────────────────────────────────────────────────────────┐
│                      DEPENDENCY GRAPH                                 │
│                                                                      │
│  G00 ──▶ G01 ──▶ G02 ──▶ [Real Hardware Test]                    │
│                              │                                        │
│                              │ (Sau G02)                            │
│                              ▼                                        │
│                         G03 ──▶ G04 ──▶ G05 ──▶ G06 ──▶ G07       │
│                              │                                        │
│                              │ (Optional)                            │
│                              ▼                                        │
│                            G08 ───────────────────────────────────────┘
│                              │
│                              │ (Cần FR5 Robot)
│                              ▼
│                            G09
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. G02: CAMERA CALIBRATION

### 2.1 Mục tiêu

Tạo file `data/calib/camera.yaml` chứa:
- Ma trận nội tham số K (fx, fy, cx, cy)
- Hệ số méo D (k1, k2, p1, p2, k3)
- Ước lượng sai số thực qua bootstrap

### 2.2 Tại sao cần làm G02?

```
╔════════════════════════════════════════════════════════════════════════╗
║                                                                        ║
║  ⚠️  G02 LÀ BLOCKER CHO MỌI TEST THỰC TẾ!                        ║
║                                                                        ║
║  KHÔNG CÓ K, D → KHÔNG THỂ:                                       ║
║  ❌ Khử méo ảnh (undistort)                                        ║
║  ❌ Tính chính xác tọa độ 3D                                      ║
║  ❌ Chạy realtime_viz.py với camera thật                           ║
║  ❌ Validate độ chính xác thực tế                                  ║
║                                                                        ║
╚════════════════════════════════════════════════════════════════════════╝
```

### 2.3 Lưu ý quan trọng

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  ✅ G02 CHỈ CẦN LÀM MỘT LẦN!                                    │
│                                                                      │
│  SAU KHI CALIBRATE XONG:                                           │
│  • Di chuyển camera THOẢI MÁI (cao/thấp/trái/phải)            │
│  • Thay đổi góc nhìn THOẢI MÁI                                 │
│  • Gắn vào robot arm THOẢI MÁI                                    │
│  → Pose tự tính lại mỗi frame từ ChArUco                       │
│                                                                      │
│  CHỈ CẦN CALIBRATE LẠI KHI:                                       │
│  • Đổi camera                                                      │
│  • Đổi zoom/focus                                                 │
│  • Đổi resolution                                                  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.4 Chi tiết 10 bước G02

#### Bước 2.1: In bảng ChArUco (5 phút)

| Hạng mục | Chi tiết |
|-----------|----------|
| **File** | `bang_charuco_A4.pdf` |
| **Tỉ lệ** | 100% (KHÔNG fit to page) |
| **Giấy** | Giấy mờ (Matte paper) |
| **DPI** | 300 DPI |
| **Máy in** | Màu hoặc đen trắng đều được |

#### Bước 2.2: Đo kích thước bằng thước thép (10 phút)

**Dụng cụ:** Thước thép (độ chính xác 0.5mm)

**Cách đo:**
```
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│  ◄── W ──►                                                  │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  [MÉP NGOÀI Ô ĐEN TRÁI] ────────▶ [MÉP NGOÀI Ô ĐEN PHẢI] │
│  │           Chiều NGANG (W)                                │
│  │                                                            │
│  │  ▲                                                        │
│  │  │ H                                                      │
│  │  ▼                                                        │
│  │  Chiều DỌC (H)                                           │
│  └──────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

**Bảng ghi số liệu:**

| Lần đo | Chiều ngang (mm) | Chiều dọc (mm) |
|:------:|:-----------------:|:---------------:|
| 1 | | |
| 2 | | |
| 3 | | |
| **TB** | | |

#### Bước 2.3: Kiểm tra Anisotropy (2 phút)

```bash
uv run python -c "
w = float(input('Chiều ngang (mm): '))
h = float(input('Chiều dọc (mm): '))
ratio = (w/h) / (235.63/149.94)
anisotropy = abs(ratio - 1.0) * 100
print(f'Anisotropy: {anisotropy:.2f}%')
print('OK' if anisotropy < 1.5 else 'CẦN IN LẠI!')
"
```

**Tiêu chí:**

| Anisotropy | Kết quả |
|-----------|---------|
| < 1.5% | ✅ OK - Tiếp tục |
| > 1.5% | ❌ CẦN IN LẠI bảng |

#### Bước 2.4: Cập nhật config (2 phút)

**File:** `configs/mono3d.yaml`

```yaml
board:
  measured:
    board_width_mm: XXX.XX   # ← Giá trị đo được
    board_height_mm: XXX.XX  # ← Giá trị đo được
```

#### Bước 2.5: Dán bảng lên bìa cứng (5 phút)

1. Cắt bìa cứng vừa với bảng
2. Dán phẳng (keo sữa hoặc băng hai mặt)
3. Loại bỏ bọt khí
4. Đợi khô hoàn toàn

#### Bước 2.6: Tạo Ground Truth Points (15 phút)

**File:** `configs/ground_truth_points.csv`

**Tối thiểu:** 10-15 điểm

```csv
point_id,x_mm,y_mm,z_mm,note
p01,0,0,0,Góc trên-trái
p02,0,50,0,
p03,0,100,0,
p04,0,149.94,0,
p05,235.63,0,0,
p06,235.63,50,0,
...
```

#### Bước 2.7: Capture ảnh Calibration (15 phút)

**Camera Settings phải CỐ ĐỊNH trước khi capture:**
```
1. ✅ Resolution: 1280x720
2. ✅ Autofocus: TẮT / Khoá nét
3. ✅ Zoom: Fixed
```

**Lệnh:**
```bash
.\run_fov.ps1 capture --camera 0 --name calib_session --width 1280 --height 720 --freeze-focus 1
```

**Yêu cầu ảnh:**
- **30-40 ảnh**
- Nghiêng **20-45°**
- Phủ **4 góc** frame
- Khoảng cách **đa dạng** (30cm - 80cm)

**Phím điều khiển:**
| Phím | Hành động |
|:----:|-----------|
| `Q` | Thoát (giữ data) |
| `Enter` | Tính ngay |
| `Space` | Lưu cưỡng bức |

#### Bước 2.8: Analyze với Bootstrap (5 phút)

**Lệnh:**
```bash
.\run_fov.ps1 analyze sessions\calib_session --bootstrap 100
```

**Output mong đợi:**
```
RMS: 0.45 px
FOV horizontal: 72.123 ± 0.234°
FOV vertical: 44.567 ± 0.189°
Status: ✅ observations=True, solved=True
```

**Tiêu chí:**

| Metric | Ngưỡng tốt | Ngưỡng chấp nhận |
|--------|:-----------:|:-----------------:|
| RMS | < 0.5 px | < 1.0 px |
| Số ảnh | 30-40 | ≥ 20 |

#### Bước 2.9: Export camera.yaml (2 phút)

**Lệnh:**
```bash
.\run_fov.ps1 export sessions\calib_session --name "my_camera"
copy sessions\calib_session\runs\<run_id>\export\camera.yaml data\calib\camera.yaml
```

**Nội dung camera.yaml:**
```yaml
intrinsics:
  resolution:
    width: 1280
    height: 720
  k_matrix:
    fx: 1056.234
    fy: 1056.789
    cx: 639.5
    cy: 359.5
  distortion:
    k1: -0.0123
    k2: 0.0345
    p1: -0.0012
    p2: 0.0008
    k3: -0.0123
```

#### Bước 2.10: Verify (2 phút)

**Lệnh:**
```bash
uv run python scripts/check_env.py --camera 0
```

**Output mong đợi:**
```
✅ Calibration:
   K matrix: loaded
   Distortion: loaded
   RMS error: 0.45 px
   FOV: 72.1° x 44.6°
```

### 2.5 Tổng hợp lệnh G02

```powershell
# =====================
# G02: CAMERA CALIBRATION
# =====================

# Bước 1-6: Chuẩn bị (thủ công)
# - In bảng ChArUco
# - Đo kích thước bằng thước thép
# - Kiểm tra anisotropy < 1.5%
# - Cập nhật configs/mono3d.yaml
# - Dán bảng lên bìa cứng
# - Tạo ground_truth_points.csv

# Bước 7: Capture ảnh
cd D:\Desktop\5\DPL302m\mono-eye-in-hand-3d
.\run_fov.ps1 capture --camera 0 --name calib_session --width 1280 --height 720 --freeze-focus 1

# Bước 8: Analyze với Bootstrap
.\run_fov.ps1 analyze sessions\calib_session --bootstrap 100

# Bước 9: Export
.\run_fov.ps1 export sessions\calib_session --name "my_camera"
copy sessions\calib_session\runs\<run_id>\export\camera.yaml data\calib\camera.yaml

# Bước 10: Verify
uv run python scripts/check_env.py --camera 0
```

---

## 3. G03-G08: ĐÃ HOÀN THÀNH - TÓM TẮT

### 3.1 G03: Pose Estimation (9 tests ✅)

**Module:** `mono_eye/pose.py`

**Chức năng:**
- Ước lượng vị trí và hướng camera từ ChArUco corners
- Tích hợp `solvePnP`
- Quality gates (từ chối pose không đạt chất lượng)

**Classes:**
```python
CameraPose        # Lưu rvec, tvec, reproj_error
PoseEstimator     # Tích hợp solvePnP
```

### 3.2 G04: Projection (11 tests ✅)

**Module:** `mono_eye/projection.py`

**Pipeline:**
```
Pixel (u,v) → Undistort → Ray (camera) → Rotate → Ray (world) → Intersect Z=0 → Point 3D
```

**Functions:**
```python
undistort_pixel()              # Khử méo
pixel_to_ray_camera()          # Tạo tia trong camera frame
ray_to_world()                # Rotate sang world frame
ray_plane_intersection()      # Giao với mặt bàn
pixel_to_3d()                  # Hàm tổng hợp
```

### 3.3 G05: Detection & Pipeline (7 tests ✅)

**Modules:** `mono_eye/detect.py`, `mono_eye/pipeline.py`

**Chức năng:**
- YOLO object detection với lazy loading
- ByteTrack multi-object tracking
- Pipeline orchestration

```python
ObjectDetector    # YOLO + ByteTrack
MonoEyePipeline   # Kết hợp tất cả modules
```

### 3.4 G06: Visualization (7 tests ✅)

**Module:** `mono_eye/viz.py`

**Backends:**
- `SimpleVisualizer` (Matplotlib 3D)
- `Open3DVisualizer` (Open3D)

**Scripts:**
- `scripts/realtime_viz.py` - Realtime visualization
- `--demo` mode khi không có camera

### 3.5 G07: Evaluation (4 tests ✅)

**Module:** `mono_eye/evaluate.py`

**Chức năng:**
- GroundTruthLoader
- ErrorAnalyzer (mean, median, P95, max)
- CSVLogger
- Markdown report

**Scripts:**
- `scripts/run_evaluation.py`

### 3.6 G08: Filtering (6 tests ✅)

**Module:** `mono_eye/filter.py`

**Cải tiến đã implement:**
- `KalmanTracker3D` - Kalman filter 6 chiều
- `TemporalSmoother` - Làm mượt theo thời gian
- `triangulate_two_views()` - Tam giác đạc từ 2 góc nhìn
- `filter_parallel_ray()` - Loại bỏ tia góc cực hạn

---

## 4. G09: ROBOT INTEGRATION (FR5)

### 4.1 Mục tiêu

Tích hợp hệ thống với robot FR5 để:
- Xác định tọa độ vật trong không gian robot
- Điều khiển robot di chuyển đến vị trí vật
- Thực hiện autonomous picking

### 4.2 Yêu cầu

| Yêu cầu | Mô tả | Ưu tiên |
|----------|--------|:--------:|
| Robot FR5 | Phần cứng robot | 🔴 Cao |
| Gripper | Tay gắp | 🔴 Cao |
| ROS/ROS2 | Robot framework | 🟡 TB |
| Workspace setup | Bàn, ánh sáng | 🟡 TB |

### 4.3 Các phase trong G09

```
┌─────────────────────────────────────────────────────────────────────┐
│                    G09: ROBOT INTEGRATION                             │
│                                                                      │
│  Phase 1: Hand-Eye Calibration (1-2 ngày)                          │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Mục tiêu: Xác định transformation giữa camera ↔ robot     │    │
│  │                                                              │    │
│  │  Bước 1: Thu thập dữ liệu                               │    │
│  │  • Di chuyển robot đến nhiều vị trí khác nhau          │    │
│  │  • Chụp ảnh ChArUco tại mỗi vị trí                    │    │
│  │  • Ghi nhận joint angles / end-effector pose           │    │
│  │                                                              │    │
│  │  Bước 2: Tính transformation                             │    │
│  │  • X_cam = T_robot2cam × X_robot                        │    │
│  │  • Sử dụng thuật toán hand-eye calibration             │    │
│  │                                                              │    │
│  │  Bước 3: Validate                                         │    │
│  │  • Kiểm tra sai số < ngưỡng                             │    │
│  │  • Nếu không đạt, thu thập thêm dữ liệu               │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              ↓                                       │
│  Phase 2: Kinematics Integration (2-3 ngày)                        │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Mục tiêu: Kết nối với robot controller                     │    │
│  │                                                              │    │
│  │  Bước 1: ROS Interface                                    │    │
│  │  • Tạo ROS node cho mono_eye                             │    │
│  │  • Subscribe camera feed                                 │    │
│  │  • Publish object positions                              │    │
│  │                                                              │    │
│  │  Bước 2: Robot Control                                   │    │
│  │  • Subscribe object positions                           │    │
│  │  • Tính inverse kinematics                              │    │
│  │  • Điều khiển robot di chuyển                          │    │
│  │                                                              │    │
│  │  Bước 3: Gripper Control                                │    │
│  │  • Điều khiển gripper open/close                       │    │
│  │  • Timing coordination                                  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              ↓                                       │
│  Phase 3: Control Loop (3-5 ngày)                                  │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Mục tiêu: Vòng điều khiển hoàn chỉnh                      │    │
│  │                                                              │    │
│  │  ┌─────────────────────────────────────────────────────┐   │    │
│  │  │         DETECT → PROJECT → PLAN → MOVE → GRASP    │   │    │
│  │  └─────────────────────────────────────────────────────┘   │    │
│  │                                                              │    │
│  │  Bước 1: Detect & Localize                               │    │
│  │  • Phát hiện vật bằng YOLO                             │    │
│  │  • Tính tọa độ 3D                                      │    │
│  │                                                              │    │
│  │  Bước 2: Motion Planning                                │    │
│  │  • Tính trajectory đến vị trí vật                      │    │
│  │  • Tránh obstacles                                     │    │
│  │                                                              │    │
│  │  Bước 3: Execution                                      │    │
│  │  • Di chuyển robot đến vị trí                          │    │
│  │  • Hạ gripper xuống                                    │    │
│  │  • Gắp vật                                             │    │
│  │  • Nâng lên và di chuyển đến destination               │    │
│  │                                                              │    │
│  │  Bước 4: Feedback & Correction                          │    │
│  │  • Kiểm tra gripper có gắp được không                 │    │
│  │  • Nếu thất bại, thử lại hoặc báo lỗi               │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              ↓                                       │
│  Phase 4: Testing & Demo (2-3 ngày)                               │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  • Test với nhiều loại vật                             │    │
│  │  • Test ở các điều kiện ánh sáng khác nhau           │    │
│  │  • Demo autonomous picking                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.4 Chi tiết từng Phase

#### Phase 1: Hand-Eye Calibration

**Mục tiêu:** Xác định transformation matrix T_robot2cam

**Công thức:**
```
X_camera = T_robot2cam × X_robot
```

**Dữ liệu cần thu thập:**
- 20-30 pairs của:
  - Robot pose (joint angles hoặc end-effector pose)
  - Camera pose (từ ChArUco)

**Thuật toán:**
- Tích hợp sẵn trong OpenCV: `calibrateHandEye()`
- Hoặc: Tsai, Park, Horaud, Andreff...

#### Phase 2: Kinematics Integration

**Robot FR5 Specifications:**
- 6 DOF (6 joints)
- Payload: 5kg
- Reach: 850mm
- Repeatability: ±0.02mm

**ROS Interface:**
```python
# Pseudo-code
import rospy
from sensor_msgs.msg import Image
from geometry_msgs.msg import Pose

class RobotController:
    def __init__(self):
        self.pose_sub = rospy.Subscriber('/mono_eye/object_pose', Pose, self.on_object_detected)
        
    def on_object_detected(self, msg):
        # Convert camera frame to robot frame
        robot_pose = self.camera_to_robot(msg)
        
        # Inverse kinematics
        joint_angles = self.ik.solve(robot_pose)
        
        # Move robot
        self.robot.move(joint_angles)
        
        # Grasp
        self.gripper.close()
```

#### Phase 3: Control Loop

```
┌─────────────────────────────────────────────────────────────────────┐
│                      CONTROL LOOP                                     │
│                                                                      │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐       │
│  │ DETECT  │───▶│PROJECT  │───▶│  PLAN   │───▶│  MOVE   │       │
│  │         │    │         │    │         │    │         │       │
│  │ YOLO    │    │ 3D pos  │    │ Traject.│    │ Robot   │       │
│  └─────────┘    └─────────┘    └─────────┘    └────┬────┘       │
│                                                      │             │
│                                                      ▼             │
│                         ┌─────────┐    ┌─────────┐    ┌─────────┐│
│                         │ FEEDBACK│◀───│  GRASP  │◀───│ APPROACH││
│                         │         │    │         │    │         ││
│                         │ Success?│    │ Close   │    │ Pre-    ││
│                         └─────────┘    │ gripper │    │ grasp   ││
│                                          └─────────┘    └─────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

### 4.5 Timeline dự kiến G09

| Phase | Nhiệm vụ | Thời gian | Ghi chú |
|-------|---------|:---------:|---------|
| G09.1 | Hand-Eye Calibration | 1-2 ngày | Cần 20-30 data points |
| G09.2 | Kinematics Integration | 2-3 ngày | ROS interface |
| G09.3 | Control Loop | 3-5 ngày | Core logic |
| G09.4 | Testing & Demo | 2-3 ngày | Debug & refine |
| | **TỔNG G09** | **8-13 ngày** | |

---

## 5. TIMELINE TỔNG HỢP

### 5.1 Sơ đồ timeline

```
G02 ────────────────▶ G09.1 ─────────────────▶ G09.2 ─────────────────▶ G09.3 ─────────────────▶ G09.4
│                      │                       │                       │                       │
│                      │                       │                       │                       │
~60 phút               1-2 ngày               2-3 ngày               3-5 ngày               2-3 ngày
                       │
                       ▼
                 Test thực tế
                 (~1 ngày)
```

### 5.2 Thời gian ước tính

| Giai đoạn | Thời gian |
|-----------|:---------:|
| G02: Camera Calibration | ~60 phút |
| Test thực tế sau G02 | ~1 ngày |
| G09: Robot Integration | 8-13 ngày |
| **TỔNG CỘNG** | **~10-15 ngày** |

### 5.3 Milestones

| Milestone | Mô tả | Trạng thái |
|-----------|--------|:----------:|
| M1 | 82 unit tests passed | ✅ Đạt |
| M2 | Camera calibrated (K, D) | ⏳ Cần làm |
| M3 | Realtime demo với camera | ⏳ Cần làm |
| M4 | Đo sai số < 5mm | ⏳ Cần làm |
| M5 | Hand-eye calibration done | ⏳ Cần robot |
| M6 | Autonomous picking demo | ⏳ Cần robot |

---

## 6. CHECKLIST HOÀN THÀNH

### 6.1 G02: Camera Calibration

**Chuẩn bị:**
- [ ] In bảng ChArUco (100%, giấy mờ, 300 DPI)
- [ ] Thước thép sẵn sàng
- [ ] Bìa cứng + keo/băng hai mặt
- [ ] Camera đã khoá focus

**Thực hiện:**
- [ ] Đo kích thước bảng (3 lần mỗi chiều)
- [ ] Anisotropy < 1.5%
- [ ] Cập nhật `configs/mono3d.yaml`
- [ ] Dán bảng lên bìa cứng
- [ ] Cố định bảng lên bàn
- [ ] Tạo `ground_truth_points.csv` (≥10 điểm)
- [ ] Capture 30-40 ảnh
- [ ] Chạy `--bootstrap 100`
- [ ] RMS < 1.0 px
- [ ] Export `camera.yaml` vào `data/calib/`
- [ ] Verify với `check_env.py` ✅

### 6.2 Test thực tế sau G02

- [ ] Chạy `scripts/realtime_viz.py`
- [ ] Quan sát pose estimation
- [ ] Đo sai số trên ground truth
- [ ] Fine-tune parameters nếu cần

### 6.3 G09: Robot Integration

**Chuẩn bị:**
- [ ] Có robot FR5
- [ ] Có gripper
- [ ] ROS/ROS2 đã cài đặt
- [ ] Workspace setup xong

**Phase 1: Hand-Eye Calibration**
- [ ] Thu thập 20-30 data points
- [ ] Tính transformation matrix
- [ ] Validate sai số

**Phase 2: Kinematics Integration**
- [ ] Tạo ROS node cho mono_eye
- [ ] Implement inverse kinematics
- [ ] Kết nối với robot controller

**Phase 3: Control Loop**
- [ ] Detect & Localize
- [ ] Motion Planning
- [ ] Execution
- [ ] Feedback & Correction

**Phase 4: Testing & Demo**
- [ ] Test với nhiều loại vật
- [ ] Autonomous picking demo thành công

---

## LỆNH TỔNG HỢP

```powershell
# =====================
# G02: CAMERA CALIBRATION
# =====================
cd D:\Desktop\5\DPL302m\mono-eye-in-hand-3d

# 1. Chuẩn bị (thủ công)
# - In bảng, đo, cập nhật config

# 2. Capture
.\run_fov.ps1 capture --camera 0 --name calib_session --width 1280 --height 720 --freeze-focus 1

# 3. Analyze
.\run_fov.ps1 analyze sessions\calib_session --bootstrap 100

# 4. Export
.\run_fov.ps1 export sessions\calib_session --name "my_camera"
copy sessions\calib_session\runs\<run_id>\export\camera.yaml data\calib\camera.yaml

# 5. Verify
uv run python scripts/check_env.py --camera 0

# =====================
# TEST THỰC TẾ
# =====================
uv run python scripts/realtime_viz.py
uv run python scripts/run_evaluation.py --ground-truth configs/ground_truth_points.csv

# =====================
# G09: (Khi có robot FR5)
# =====================
# Xem TASKS/G09_ROBOT.md để biết chi tiết
```

---

## HỖ TRỢ

### Tài liệu tham khảo

| Tài liệu | Mô tả |
|-----------|--------|
| [docs/HOW_TO_RUN.md](docs/HOW_TO_RUN.md) | Hướng dẫn chạy hệ thống |
| [docs/roadmap.md](docs/roadmap.md) | Lộ trình dự án |
| [docs/PROJECT_REPORT.md](docs/PROJECT_REPORT.md) | Báo cáo tổng quan |
| [TASKS/G02_CALIBRATION.md](TASKS/G02_CALIBRATION.md) | Chi tiết G02 |
| [docs/PRESENTATION_SCRIPT_FULL.md](docs/PRESENTATION_SCRIPT_FULL.md) | Kịch bản trình bày |

### Troubleshooting

| Vấn đề | Xem thêm |
|---------|----------|
| Anisotropy cao | TASKS/G02_CALIBRATION.md |
| RMS cao | TASKS/G02_CALIBRATION.md |
| Camera không nhận | `scripts/check_env.py` |
| Lỗi khác | docs/roadmap.md |

---

**Báo cáo tạo ngày:** 2026-10-06  
**Phiên bản:** 1.0
