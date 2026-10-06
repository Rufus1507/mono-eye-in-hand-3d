# PROMPT: Giai đoạn 2 - Calibrate Nội Tham Số Camera

## Mục tiêu
Có ma trận camera K và hệ số méo D đáng tin, cùng ước lượng sai số thật qua bootstrap.

---

## ⚠️ LƯU Ý QUAN TRỌNG - ĐỌC TRƯỚC KHI LÀM

### G02 chỉ cần làm MỘT LẦN!

```
╔════════════════════════════════════════════════════════════════════════╗
║                                                                        ║
║  ✅ SAU KHI CALIBRATE XONG:                                           ║
║                                                                        ║
║  • Di chuyển camera THOẢI MÁI (cao/thấp/trái/phải)                ║
║  • Thay đổi góc nhìn THOẢI MÁI                                     ║
║  • Gắn vào robot arm THOẢI MÁI                                       ║
║                                                                        ║
║  → Pose tự tính lại mỗi frame từ ChArUco                          ║
║                                                                        ║
║  ❌ CHỈ CẦN CALIBRATE LẠI KHI:                                       ║
║                                                                        ║
║  • Đổi camera                                                        ║
║  • Đổi zoom/focus                                                   ║
║  • Đổi resolution                                                    ║
║                                                                        ║
╚════════════════════════════════════════════════════════════════════════╝
```

### Camera Settings phải CỐ ĐỊNH trước khi calibrate

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  TRƯỚC KHI CALIBRATE:                                              │
│                                                                      │
│  1. ✅ Tắt autofocus / Khoá nét ở khoảng cách làm việc         │
│  2. ✅ Cố định zoom (nếu có)                                      │
│  3. ✅ Đặt resolution: 1280x720                                    │
│  4. ✅ KHÔNG thay đổi các settings này sau khi calibrate           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Ngữ cảnh

### Trạng thái từ Giai đoạn 1
- ✅ Môi trường hoạt động
- ✅ Camera 1280×720 hoạt động
- ✅ Board config sẵn có (A4: 11×7, ô 21.421mm)
- ⏳ Bảng ChArUco: **CẦN IN**

### Thiết bị cần chuẩn bị
- Máy in (300 DPI, giấy mờ)
- Thước thép
- Bìa cứng + keo/băng hai mặt
- Bàn phẳng cố định

---

## Các bước thực hiện

### 2.1 In bảng ChArUco

**File có sẵn:**
```
D:\Desktop\5\DPL302m\mono-eye-in-hand-3d\
├── bang_charuco_A4.pdf    # Bảng in sẵn
├── bang_charuco_A4.png    # Preview
```

**Cách in:**
1. Mở `bang_charuco_A4.pdf`
2. Print → **Tỉ lệ 100%** (tắt Fit to page)
3. Giấy mờ, 300 DPI
4. Không in duplex

### 2.2 Đo kích thước thật

**Dụng cụ:** Thước thép

**Cách đo:**
```
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│  ◄── 1 ──►                                                  │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  [MÉP NGOÀI Ô ĐEN TRÁI] ────────▶ [MÉP NGOÀI Ô ĐEN PHẢI] │
│  │           Chiều NGANG (W)                                │
│  │                                                            │
│  │  ▲                                                        │
│  │  │ 2                                                      │
│  │  ▼                                                        │
│  │  Chiều DỌC (H)                                           │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Đo 3 lần mỗi chiều:**

| Lần | Chiều ngang (mm) | Chiều dọc (mm) |
|-----|-------------------|------------------|
| 1 | | |
| 2 | | |
| 3 | | |
| **TB** | | |

**So sánh với danh nghĩa:**
- Chiều ngang: **235.63 mm**
- Chiều dọc: **149.94 mm**
- Mỗi ô: **21.421 mm**

### 2.3 Kiểm tra Anisotropy

```bash
uv run python -c "
measured_width = float(input('Chiều ngang (mm): '))
measured_height = float(input('Chiều dọc (mm): '))

ratio = (measured_width / measured_height) / (235.63 / 149.94)
anisotropy = abs(ratio - 1.0) * 100

print(f'Anisotropy: {anisotropy:.2f}%')
print('OK' if anisotropy < 1.5 else 'CẦN IN LẠI')
"
```

**Tiêu chí:** `anisotropy < 1.5%`

### 2.4 Cập nhật configs/mono3d.yaml

```yaml
board:
  measured:
    board_width_mm: XXX.XX   # ← Số đo thực tế
    board_height_mm: XXX.XX  # ← Số đo thực tế
```

### 2.5 Dán bảng lên bìa cứng

1. Cắt bìa cứng vừa với bảng
2. Dán bảng phẳng (keo sữa hoặc băng hai mặt)
3. Không để bọt khí
4. Đợi khô

### 2.6 Cố định bảng lên bàn

1. Chọn vị trí bàn phẳng, ánh sáng ổn định
2. Đặt bảng, cố định bằng băng keo hai mặt
3. **Đánh dấu vị trí** bảng (vẽ đường viền)
4. **Bảng phải CỐ ĐỊNH trong suốt quá trình sử dụng**

### 2.7 Tạo Ground Truth Points

**File:** `configs/ground_truth_points.csv`

```csv
point_id,x_mm,y_mm,z_mm,note
p01,0,0,0,Góc trên-trái tấm
p02,20,0,0,
p03,40,0,0,
...
```

**Tối thiểu:** 10-15 điểm phân bố đều

---

## 2.8 Calibrate Camera (BƯỚC CHÍNH)

### 2.8.1 Cố định Camera Settings TRƯỚC KHI capture

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  ⚠️  QUAN TRỌNG: CỐ ĐỊNH CAMERA TRƯỚC!                        │
│                                                                      │
│  Trước khi chạy capture:                                          │
│                                                                      │
│  1. Đặt camera ở khoảng cách làm việc (30-80cm)                │
│  2. Tắt autofocus / Khoá nét ở khoảng cách này                  │
│  3. Đặt resolution: 1280x720                                       │
│  4. Tắt zoom (hoặc để fixed)                                     │
│                                                                      │
│  KHÔNG thay đổi các settings này trong suốt quá trình!           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.8.2 Capture Images

```powershell
cd D:\Desktop\5\DPL302m\mono-eye-in-hand-3d
.\run_fov.ps1 capture --camera 0 --name calib_session --width 1280 --height 720 --freeze-focus 1
```

**Hướng dẫn:**
- Di chuyển tấm đến các vị trí khác nhau
- **Giữ yên ~0.4s** giữa mỗi tư thế
- Chương trình tự chụp khi phát hiện tấm đứng yên

**Yêu cầu ảnh:**
| Yêu cầu | Mục đích |
|----------|-----------|
| **30-40 ảnh** | Đủ data để calibrate |
| **Nghiêng 20-45°** | Đa dạng góc nhìn |
| **Phủ 4 góc frame** | Cover frame edges |
| **Khoảng cách đa dạng** | Gần, xa, trung bình |

**Phím điều khiển:**
- `Q`: Hủy (giữ data, không tính)
- `Enter`: Tính ngay
- `Space`: Lưu cưỡng bức (bị loại khỏi tính)

### 2.8.3 Analyze với Bootstrap

```powershell
.\run_fov.ps1 analyze sessions\calib_session --bootstrap 100
```

**Output mong đợi:**
```
FOV ngang: 72.XXX ± X.XXX°
FOV dọc: 44.XXX ± X.XXX°
trạng thái: observations=True solved=True
```

### 2.8.4 Tiêu chí đánh giá

| Metric | Ngưỡng | Notes |
|--------|---------|-------|
| RMS | < 1.0 px (webcam) | Càng thấp càng tốt |
| Bootstrap spread | Nhỏ, nhất quán | ± ổn định |
| Số ảnh | ≥ 20 | Đủ để calibration tốt |

### 2.8.5 Export camera.yaml

```powershell
.\run_fov.ps1 export sessions\calib_session --name "my_camera"
```

**Copy file:**
```bash
copy sessions\calib_session\runs\<run_id>\export\camera.yaml data\calib\camera.yaml
```

### 2.8.6 Verify

```bash
uv run python scripts/check_env.py --camera 0
```

**Output mong đợi:**
```
✅ Calibration:
   K matrix: loaded
   Distortion: loaded
   Resolution: 1280x720
```

---

## TÓM TẮT QUY TRÌNH

```
┌─────────────────────────────────────────────────────────────────────┐
│                         G02 CALIBRATION                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  CHỈ LÀM MỘT LẦN!                                                 │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  1. In bảng (100%, giấy mờ)                              │    │
│  │  2. Đo kích thước + cập nhật config                      │    │
│  │  3. Dán + cố định bảng lên bàn                          │    │
│  │  4. Tạo ground truth points                              │    │
│  │  5. Cố định camera settings (focus, zoom, resolution)     │    │
│  │  6. Capture 30-40 ảnh với các góc đa dạng              │    │
│  │  7. Analyze với --bootstrap 100                           │    │
│  │  8. Export camera.yaml                                   │    │
│  │  9. Verify với check_env.py                              │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  SAU ĐÓ:                                                           │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  • Di chuyển camera THOẢI MÁI                             │    │
│  │  • Thay đổi chiều cao THOẢI MÁI                           │    │
│  │  • Gắn vào robot THOẢI MÁI                                │    │
│  │                                                              │    │
│  │  → Pose tự tính lại mỗi frame từ ChArUco                │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Commands tổng hợp

```powershell
# 1. Capture
cd D:\Desktop\5\DPL302m\mono-eye-in-hand-3d
.\run_fov.ps1 capture --camera 0 --name calib_session --width 1280 --height 720 --freeze-focus 1

# 2. Analyze
.\run_fov.ps1 analyze sessions\calib_session --bootstrap 100

# 3. Export
.\run_fov.ps1 export sessions\calib_session --name "my_camera"

# 4. Copy
copy sessions\calib_session\runs\<run_id>\export\camera.yaml data\calib\camera.yaml

# 5. Verify
uv run python scripts/check_env.py --camera 0
```

---

## Khi nào cần calibrate lại?

| Thay đổi | Calibrate lại? |
|-----------|----------------|
| Zoom | ✅ Có |
| Focus | ✅ Có |
| Resolution | ✅ Có |
| Camera khác | ✅ Có |
| Vị trí cao/thấp | ❌ Không |
| Vị trí trái/phải | ❌ Không |
| Góc nhìn | ❌ Không |
| Gắn robot | ❌ Không |

---

## Tiêu chí hoàn thành

- [x] Bảng đã in (100%, giấy mờ)
- [x] Kích thước đã đo
- [x] Anisotropy < 1.5%
- [x] `configs/mono3d.yaml` đã cập nhật
- [x] Bảng đã dán + cố định
- [x] Ground truth points đã tạo (≥10 điểm)
- [x] Camera settings đã cố định
- [x] Đã capture 30-40 ảnh
- [x] `--bootstrap 100` đã chạy
- [x] RMS < 1.0 px
- [x] Bootstrap spread nhỏ và ổn định
- [x] `camera.yaml` đã export vào `data/calib/`
- [x] `check_env.py` verify OK
- [x] File `docs/G02_REPORT.md` đã tạo

---

## Báo cáo mẫu

### File: `docs/G02_REPORT.md`

```markdown
# Giai đoạn 2: Calibrate Nội Tham Số Camera

## Ngày: YYYY-MM-DD

---

## 1. Bảng ChArUco

| Thông số | Giá trị |
|----------|---------|
| Chiều ngang | XXX.XX mm |
| Chiều dọc | XXX.XX mm |
| Anisotropy | X.XX% |
| Trạng thái | ✅ OK / ❌ Cần in lại |

---

## 2. Camera Calibration

| Parameter | Value |
|-----------|-------|
| Camera | 0 |
| Resolution | 1280×720 |
| Session | calib_session |

### Kết quả
| Metric | Value |
|--------|-------|
| RMS | X.XX px |
| FOV ngang | XX.XXX ± X.XXX° |
| FOV dọc | XX.XXX ± X.XXX° |
| Số ảnh | XX |

---

## 3. Camera Settings đã cố định

- [ ] Autofocus: OFF / Khoá nét
- [ ] Zoom: Fixed
- [ ] Resolution: 1280x720

---

## Trạng thái: ✅ HOÀN THÀNH
```
