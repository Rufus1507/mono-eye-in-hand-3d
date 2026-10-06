# BÁO CÁO: GIAI ĐOẠN TIẾP THEO

## Những việc cần làm để hoàn thành dự án

---

**Ngày:** 2026-10-06  
**Trạng thái dự án:** ~85% Hoàn thành  
**Bước tiếp theo:** G02 - Camera Calibration

---

## MỤC LỤC

1. [Tổng quan tình trạng](#1-tổng-quan-tình-trạng)
2. [Giai đoạn 2: Camera Calibration](#2-giai-đoạn-2-camera-calibration)
3. [Sau khi calibrate - Test thực tế](#3-sau-khi-calibrate---test-thực-tế)
4. [G09: Robot Integration (FR5)](#4-g09-robot-integration-fr5)
5. [Checklist hoàn thành](#5-checklist-hoàn-thành)

---

## 1. TỔNG QUAN TÌNH TRẠNG

### 1.1 Đã hoàn thành

| Giai đoạn | Nội dung | Tests |
|:---:|---|:---:|
| G00 | Setup môi trường | 32 ✅ |
| G01 | Infrastructure | 11 ✅ |
| G03 | Pose Estimation | 9 ✅ |
| G04 | Projection | 11 ✅ |
| G05 | Detection & Pipeline | 7 ✅ |
| G06 | Visualization | 7 ✅ |
| G07 | Evaluation | 4 ✅ |
| G08 | Filtering | 6 ✅ |

**Tổng: 82 tests passed (100%)**

### 1.2 Chưa hoàn thành

| Giai đoạn | Nội dung | Trạng thái |
|:---:|---|:---:|
| **G02** | Camera Calibration | ⏳ Cần làm |
| **G09** | Robot Integration | 📋 Dự kiến |

### 1.3 Tại sao G02 là bước tiếp theo?

```
┌─────────────────────────────────────────────────────────────────────┐
│                         TẠI SAO CẦN G02?                            │
│                                                                      │
│  G02 = Camera Calibration = Tính ma trận K và hệ số méo D           │
│                                                                      │
│  KHÔNG CÓ K, D → KHÔNG THỂ:                                       │
│                                                                      │
│  ❌ Khử méo ảnh (undistort)                                        │
│  ❌ Tính chính xác tọa độ 3D                                      │
│  ❌ Chạy realtime_viz.py với camera thật                           │
│  ❌ Validate độ chính xác thực tế                                  │
│                                                                      │
│  → G02 là BLOCKER cho mọi test thực tế!                            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. GIAI ĐOẠN 2: CAMERA CALIBRATION

### 2.1 Mục tiêu

Tạo file `data/calib/camera.yaml` chứa:
- Ma trận nội tham số K (fx, fy, cx, cy)
- Hệ số méo D (k1, k2, p1, p2, k3)
- Ước lượng sai số thực qua bootstrap

### 2.2 Tổng quan các bước

```
┌─────────────────────────────────────────────────────────────────────┐
│                    G02: 10 BƯỚC CALIBRATION                          │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  BƯỚC CHUẨN BỊ:                                           │    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐      │    │
│  │  │ 2.1     │→ │ 2.2     │→ │ 2.3     │→ │ 2.4     │      │    │
│  │  │In bảng │  │Đo kích  │  │Kiểm tra│  │Cập nhật │      │    │
│  │  │ChArUco │  │thước    │  │Anisotrpy│  │config   │      │    │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘      │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              ↓                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  BƯỚC THỰC HIỆN:                                          │    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐      │    │
│  │  │ 2.5     │→ │ 2.6     │→ │ 2.7     │→ │ 2.8     │      │    │
│  │  │Dán bảng│  │Ground   │  │Capture  │  │Analyze  │      │    │
│  │  │bìa cứng│  │Truth    │  │ảnh      │  │Bootstrap│      │    │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘      │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              ↓                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  BƯỚC HOÀN TẤT:                                           │    │
│  │  ┌─────────┐  ┌─────────┐                                 │    │
│  │  │ 2.9     │→ │ 2.10    │                                 │    │
│  │  │Export   │→ │Verify   │                                 │    │
│  │  │camera.  │  │✓ OK     │                                 │    │
│  │  │yaml     │  │         │                                 │    │
│  │  └─────────┘  └─────────┘                                 │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ⏱️ Tổng thời gian: ~60 phút                                    │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.3 Chi tiết từng bước

#### Bước 2.1: In bảng ChArUco (5 phút)

**File cần in:**
```
D:\Desktop\5\DPL302m\mono-eye-in-hand-3d\
├── bang_charuco_A4.pdf    # Bảng in
├── bang_charuco_A4.png    # Preview
```

**Cách in:**
1. Mở `bang_charuco_A4.pdf`
2. Print → **Scale: 100%** (KHÔNG fit to page)
3. Paper: A4, **Giấy mờ (Matte)**
4. Quality: **300 DPI**

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
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Bảng ghi số liệu:**

| Lần đo | Chiều ngang (mm) | Chiều dọc (mm) |
|:------:|:-----------------:|:---------------:|
| 1 | | |
| 2 | | |
| 3 | | |
| **TB** | | |

**Giá trị danh nghĩa:**
- Chiều ngang: **235.63 mm**
- Chiều dọc: **149.94 mm**

#### Bước 2.3: Kiểm tra Anisotropy (2 phút)

**Script:**
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
| > 1.5% | ❌ CẦN IN LẠI |

#### Bước 2.4: Cập nhật config (2 phút)

**File:** `configs/mono3d.yaml`

```yaml
board:
  measured:
    board_width_mm: XXX.XX   # ← Số đo thực tế
    board_height_mm: XXX.XX  # ← Số đo thực tế
```

#### Bước 2.5: Dán bảng lên bìa cứng (5 phút)

1. Cắt bìa cứng vừa với bảng
2. Dán bảng phẳng (keo sữa hoặc băng hai mặt)
3. Không để bọt khí
4. Đợi khô

#### Bước 2.6: Tạo Ground Truth Points (15 phút)

**File:** `configs/ground_truth_points.csv`

**Tối thiểu:** 10-15 điểm phân bố đều

```csv
point_id,x_mm,y_mm,z_mm,note
p01,0,0,0,Góc trên-trái
p02,0,50,0,
p03,0,100,0,
...
```

#### Bước 2.7: Capture ảnh (15 phút)

**Camera Settings phải CỐ ĐỊNH:**
```
1. ✅ Resolution: 1280x720
2. ✅ Autofocus: TẮT / Khoá nét
3. ✅ Zoom: Fixed
```

**Lệnh:**
```bash
.\run_fov.ps1 capture --camera 0 --name calib_session --width 1280 --height 720 --freeze-focus 1
```

**Yêu cầu:**
- 30-40 ảnh
- Nghiêng 20-45°
- Phủ 4 góc frame
- Khoảng cách đa dạng

#### Bước 2.8: Analyze với Bootstrap (5 phút)

**Lệnh:**
```bash
.\run_fov.ps1 analyze sessions\calib_session --bootstrap 100
```

**Output mong đợi:**
```
RMS: 0.45 px
FOV horizontal: 72.XXX ± X.XXX°
FOV vertical: 44.XXX ± X.XXX°
Status: ✅ observations=True, solved=True
```

**Tiêu chí:**
| Metric | Ngưỡng |
|--------|--------|
| RMS | < 1.0 px |
| Bootstrap spread | < 1.0° |
| Số ảnh | ≥ 20 |

#### Bước 2.9: Export camera.yaml (2 phút)

**Lệnh:**
```bash
.\run_fov.ps1 export sessions\calib_session --name "my_camera"
copy sessions\calib_session\runs\<run_id>\export\camera.yaml data\calib\camera.yaml
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

### 2.4 Thời gian ước tính

| Bước | Nhiệm vụ | Thời gian |
|:---:|---|:---:|
| 2.1 | In bảng | 5 phút |
| 2.2 | Đo kích thước | 10 phút |
| 2.3 | Kiểm tra Anisotropy | 2 phút |
| 2.4 | Cập nhật config | 2 phút |
| 2.5 | Dán bảng | 5 phút |
| 2.6 | Ground Truth Points | 15 phút |
| 2.7 | Capture ảnh | 15 phút |
| 2.8 | Analyze | 5 phút |
| 2.9 | Export | 2 phút |
| 2.10 | Verify | 2 phút |
| | **TỔNG** | **~60 phút** |

### 2.5 Thiết bị cần chuẩn bị

| Thiết bị | Sẵn có? | Cần mua? |
|---------|:--------:|:---------:|
| Máy in | ☐ | ☐ |
| Giấy mờ A4 | ☐ | ☐ |
| Thước thép | ☐ | ☐ |
| Bìa cứng | ☐ | ☐ |
| Keo/băng hai mặt | ☐ | ☐ |

---

## 3. SAU KHI CALIBRATE - TEST THỰC TẾ

### 3.1 Chạy Realtime Visualization

```bash
# Với camera thật
cd D:\Desktop\5\DPL302m\mono-eye-in-hand-3d
uv run python scripts/realtime_viz.py

# Hoặc demo mode (không cần camera)
uv run python scripts/realtime_viz.py --demo
```

### 3.2 Đo sai số thực tế

```bash
# Tạo báo cáo sai số
uv run python scripts/run_evaluation.py --ground-truth configs/ground_truth_points.csv
```

**Output:**
```
# Error Analysis Report

## Summary
- Total samples: 500
- Mean error: 1.2 mm
- Median error: 0.9 mm
- 95th percentile: 2.8 mm
- Max error: 4.5 mm
```

### 3.3 Đánh giá kết quả

| Metric | Mục tiêu | Thực tế | Đạt? |
|--------|-----------|---------|:----:|
| Mean error | < 5mm | ? | ⏳ |
| P95 error | < 10mm | ? | ⏳ |
| FPS | > 20 | ? | ⏳ |

---

## 4. G09: ROBOT INTEGRATION (FR5)

### 4.1 Mục tiêu

Tích hợp hệ thống với robot FR5 để:
- Hand-eye calibration
- Real-time robot control
- Autonomous picking

### 4.2 Các bước dự kiến

```
┌─────────────────────────────────────────────────────────────────────┐
│                    G09: ROBOT INTEGRATION                            │
│                                                                      │
│  Phase 1: Hand-Eye Calibration                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  • Xác định mối quan hệ camera ↔ end-effector           │    │
│  │  • Thu thập dữ liệu từ nhiều vị trí robot              │    │
│  │  • Tính transformation matrix                            │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              ↓                                       │
│  Phase 2: Robot Kinematics Integration                             │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  • Kết nối với robot controller                          │    │
│  │  • Forward/inverse kinematics                             │    │
│  │  • Coordinate transformation                               │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              ↓                                       │
│  Phase 3: Control Loop                                              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  • Detect → Project → Plan → Move → Execute              │    │
│  │  • Feedback loop                                          │    │
│  │  • Error correction                                       │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.3 Yêu cầu

| Yêu cầu | Mô tả | Ưu tiên |
|----------|--------|:--------:|
| Robot FR5 | Phần cứng robot | 🔴 Cao |
| ROS/ROS2 | Robot framework | 🟡 TB |
| Gripper | Tay gắp | 🟡 TB |
| Workspace setup | Bàn, ánh sáng | 🟡 TB |

### 4.4 Timeline dự kiến

| Phase | Nhiệm vụ | Thời gian |
|-------|---------|-----------|
| G09.1 | Hand-eye calibration | 1-2 ngày |
| G09.2 | Kinematics integration | 2-3 ngày |
| G09.3 | Control loop | 3-5 ngày |
| G09.4 | Testing & tuning | 2-3 ngày |
| | **TỔNG** | **8-13 ngày** |

---

## 5. CHECKLIST HOÀN THÀNH

### 5.1 G02 - Camera Calibration

- [ ] In bảng ChArUco (100%, giấy mờ, 300 DPI)
- [ ] Đo kích thước (3 lần mỗi chiều)
- [ ] Anisotropy < 1.5%
- [ ] Cập nhật `configs/mono3d.yaml`
- [ ] Dán bảng lên bìa cứng
- [ ] Cố định bảng lên bàn
- [ ] Tạo `ground_truth_points.csv` (≥10 điểm)
- [ ] Camera settings đã cố định
- [ ] Capture 30-40 ảnh
- [ ] Chạy `--bootstrap 100`
- [ ] RMS < 1.0 px
- [ ] Export `camera.yaml`
- [ ] Verify với `check_env.py`

### 5.2 Sau G02 - Test thực tế

- [ ] Chạy `realtime_viz.py`
- [ ] Đo sai số trên ground truth
- [ ] Fine-tune parameters
- [ ] Benchmark FPS

### 5.3 G09 - Robot Integration

- [ ] Có robot FR5
- [ ] Hand-eye calibration
- [ ] Kinematics integration
- [ ] Control loop
- [ ] Autonomous picking demo

---

## LỆNH TỔNG HỢP

```powershell
# =======================
# G02: CAMERA CALIBRATION
# =======================

# Bước 1-6: Chuẩn bị (thủ công)
# - In bảng
# - Đo kích thước
# - Kiểm tra anisotropy
# - Cập nhật config

# Bước 7: Capture
cd D:\Desktop\5\DPL302m\mono-eye-in-hand-3d
.\run_fov.ps1 capture --camera 0 --name calib_session --width 1280 --height 720 --freeze-focus 1

# Bước 8: Analyze
.\run_fov.ps1 analyze sessions\calib_session --bootstrap 100

# Bước 9: Export
.\run_fov.ps1 export sessions\calib_session --name "my_camera"
copy sessions\calib_session\runs\<run_id>\export\camera.yaml data\calib\camera.yaml

# Bước 10: Verify
uv run python scripts/check_env.py --camera 0

# =======================
# SAU KHI CALIBRATE
# =======================

# Chạy realtime visualization
uv run python scripts/realtime_viz.py

# Đo sai số
uv run python scripts/run_evaluation.py --ground-truth configs/ground_truth_points.csv
```

---

## HỖ TRỢ

### Khi cần giúp đỡ

| Vấn đề | Xem thêm |
|---------|----------|
| Anisotropy cao | TASKS/G02_CALIBRATION.md |
| RMS cao | TASKS/G02_CALIBRATION.md |
| Camera không nhận | scripts/check_env.py |
| Lỗi khác | docs/roadmap.md |

### Liên hệ

Nếu có câu hỏi, xem:
- [docs/HOW_TO_RUN.md](docs/HOW_TO_RUN.md) - Hướng dẫn chạy hệ thống
- [docs/roadmap.md](docs/roadmap.md) - Lộ trình dự án
- [docs/PROJECT_REPORT.md](docs/PROJECT_REPORT.md) - Báo cáo tổng quan

---

**Báo cáo tạo ngày:** 2026-10-06  
**Phiên bản:** 1.0
