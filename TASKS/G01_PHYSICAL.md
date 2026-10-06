# PROMPT: Giai đoạn 1 - Chuẩn bị & Kiểm thử (KHÔNG cần ChArUco)

## Mục tiêu
Kiểm tra môi trường hoạt động đầy đủ, chuẩn bị code infrastructure, và **hoãn việc in bảng ChArUco** sang sau.

## ⚠️ LƯU Ý QUAN TRỌNG
**KHÔNG cần in bảng ChArUco trong giai đoạn này.** Việc in bảng sẽ thực hiện sau. Tập trung vào các bước có thể làm ngay.

---

## Các bước thực hiện

### 1.1 Chạy lại tất cả tests (ƯU TIÊN CAO NHẤT)

**Mục đích:** Xác nhận môi trường ổn định sau Giai đoạn 0

```bash
cd D:\Desktop\5\DPL302m\mono-eye-in-hand-3d
uv run pytest tests/test_fov.py -v
uv run pytest tests/test_mono_eye.py -v
```

**Kết quả mong đợi:**
```
tests/test_fov.py::test_xxx PASSED
...
==================== 21 passed in X.XXs ====================

tests/test_mono_eye.py::test_xxx PASSED
...
==================== 11 passed in X.XXs ====================
```

**Nếu có test fail:**
- Ghi lại test nào fail
- Chạy `uv run pytest tests/test_xxx.py -v --tb=short` để xem chi tiết lỗi
- Báo cáo lỗi

### 1.2 Kiểm tra smoke test cho modules

**Mục đích:** Xác nhận các module chính import được

```bash
# Test fov_tool
uv run python -c "
from fov_tool.board import load_board
from fov_tool.camera import Camera
from fov_tool.observations import detect_charuco
from fov_tool.geometry import field_of_view
print('✅ fov_tool imports OK')
"

# Test mono_eye
uv run python -c "
from mono_eye.config import load_config
from mono_eye.camera_io import load_camera
from mono_eye.board_scale import compute_scale
print('✅ mono_eye imports OK')
"

# Test OpenCV aruco
uv run python -c "
import cv2
print(f'OpenCV: {cv2.__version__}')
detector = cv2.aruco.CharucoDetector()
print('✅ CharucoDetector API OK')
"
```

### 1.3 Kiểm tra camera (nếu có sẵn)

**Mục đích:** Xác nhận camera hoạt động

```bash
uv run python scripts/check_env.py --camera 0
```

**Output mong đợi:**
```
Camera: 0
Resolution: 1280x720 ✅
Frame rate: 30 fps
```

**Nếu không có camera:**
- Báo cáo và chuyển sang bước tiếp theo
- Camera có thể test sau khi có hardware

### 1.4 Verify config files

**Kiểm tra cấu trúc:**
```bash
uv run python -c "
import yaml
from pathlib import Path

# Check mono3d.yaml
config = yaml.safe_load(open('configs/mono3d.yaml'))
print('=== configs/mono3d.yaml ===')
print(f'units: {config.get(\"units\")}')
print(f'camera.index: {config.get(\"camera\", {}).get(\"index\")}')
print(f'camera.resolution: {config.get(\"camera\", {}).get(\"width\")}x{config.get(\"camera\", {}).get(\"height\")}')
print(f'board.measured.board_width_mm: {config.get(\"board\", {}).get(\"measured\", {}).get(\"board_width_mm\")}')
print(f'logging.enabled: {config.get(\"logging\", {}).get(\"enabled\")}')

# Check ground_truth_points.csv
gt_file = Path('configs/ground_truth_points.csv')
if gt_file.exists():
    print(f'\\n=== ground_truth_points.csv ===')
    print(f'Exists: True')
    print(f'Size: {gt_file.stat().st_size} bytes')
else:
    print(f'\\n=== ground_truth_points.csv ===')
    print(f'Exists: False (sẽ tạo sau)')
"
```

### 1.5 Tạo directory structure

**Tạo nếu chưa có:**
```bash
mkdir -p data/calib
mkdir -p data/ground_truth
mkdir -p results/logs
mkdir -p results/viz
mkdir -p results/experiments
```

**Verify:**
```bash
ls -la data/
ls -la results/
```

### 1.6 Tạo placeholder cho ground truth points

**Vì chưa in bảng, tạo template file:**

```csv
point_id,x_mm,y_mm,z_mm,note
# Đây là template - sẽ điền sau khi in bảng
# Sau khi in bảng ChArUco, đo các điểm và cập nhật file này
# Ví dụ:
# p01,0,0,0,Góc trên-trái tấm
# p02,20,0,0,Theo hàng ngang
```

**File: `configs/ground_truth_points.csv`** (tạo nếu chưa có)

### 1.7 Code review cho mono_eye modules

**Kiểm tra trạng thái các stub files:**

```bash
# Kiểm tra pose.py
echo "=== mono_eye/pose.py ==="
wc -l mono_eye/pose.py
head -5 mono_eye/pose.py

# Kiểm tra projection.py
echo "=== mono_eye/projection.py ==="
wc -l mono_eye/projection.py
head -5 mono_eye/projection.py

# Kiểm tra detect.py
echo "=== mono_eye/detect.py ==="
wc -l mono_eye/detect.py
head -5 mono_eye/detect.py

# Kiểm tra viz.py
echo "=== mono_eye/viz.py ==="
wc -l mono_eye/viz.py
head -5 mono_eye/viz.py
```

**Output mong đợi:**
```
=== mono_eye/pose.py ===
10
"""Giai đoạn 3 - pose camera từ tấm ChArUco"""
=== mono_eye/projection.py ===
2
"""Giai đoạn 4 - pixel -> 3D"""
...
```

### 1.8 Tạo simulation/test data infrastructure

**Tạo script để test không cần camera thật:**

**File: `scripts/synthetic_test.py`**
```python
"""
Synthetic test cho mono_eye modules.
Không cần camera thật, tạo synthetic frames để test.
"""
import numpy as np
import cv2

def create_synthetic_charuco_board(width=1280, height=720):
    """Tạo synthetic ChArUco board image để test."""
    # Tạo ảnh trắng
    img = np.ones((height, width, 3), dtype=np.uint8) * 200
    
    # Vẽ một số markers giả
    # (Trong thực tế sẽ dùng CharucoBoard.generateImage())
    
    return img

def test_board_generation():
    """Test board generation."""
    try:
        from fov_tool.board import load_board
        board, detector = load_board('bang_calib_A4.yaml')
        
        # Tạo ảnh bảng
        img = board.generateImage((1280, 720))
        
        print(f"✅ Board generated: {img.shape}")
        return True
    except Exception as e:
        print(f"❌ Board generation failed: {e}")
        return False

if __name__ == "__main__":
    print("=== Synthetic Test ===")
    test_board_generation()
```

**Chạy thử:**
```bash
uv run python scripts/synthetic_test.py
```

### 1.9 Tạo unit tests mẫu cho mono_eye

**File: `tests/test_mono_eye_modules.py`**

```python
"""Unit tests cho mono_eye modules (không cần hardware)."""
import pytest
import numpy as np
from pathlib import Path
import yaml

def test_config_loading():
    """Test load config."""
    config_path = Path("configs/mono3d.yaml")
    assert config_path.exists(), "mono3d.yaml not found"
    
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    assert config["units"] == "mm"
    assert "camera" in config
    assert "board" in config

def test_logging_schema():
    """Test logging schema is defined."""
    config_path = Path("configs/mono3d.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    assert "logging" in config
    assert config["logging"]["enabled"] == True
    assert "columns" in config["logging"]
    
    expected_columns = ["timestamp", "frame_id", "num_charuco_corners", 
                       "camera_x_mm", "camera_y_mm", "camera_z_mm"]
    for col in expected_columns:
        assert col in config["logging"]["columns"], f"Missing column: {col}"

def test_board_config_exists():
    """Test board config file exists."""
    config_path = Path("configs/mono3d.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    board_file = Path(config["board"]["file"])
    assert board_file.exists(), f"Board config {board_file} not found"

def test_camera_matrix_structure():
    """Test camera calibration file structure (if exists)."""
    calib_file = Path("data/calib/camera.yaml")
    
    if not calib_file.exists():
        pytest.skip("camera.yaml not yet created (Giai đoạn 2)")
    
    with open(calib_file) as f:
        content = f.read()
    
    assert "camera_matrix:" in content
    assert "distortion_coefficients:" in content

def test_numpy_operations():
    """Test numpy operations used in mono_eye."""
    # Test Rodrigues conversion
    rvec = np.array([0.1, 0.2, 0.3])
    R, _ = cv2.Rodrigues(rvec)
    assert R.shape == (3, 3)
    
    # Test camera center calculation
    tvec = np.array([100, 50, 200])
    C = -R.T @ tvec
    assert C.shape == (3,)
    
    print("✅ Numpy operations OK")

def test_ray_plane_intersection():
    """Test ray-plane intersection logic."""
    # Camera at (0, 0, 500), looking down at z=0
    camera_center = np.array([0, 0, 500])
    ray_direction = np.array([0.1, 0.1, -1])
    ray_direction = ray_direction / np.linalg.norm(ray_direction)
    
    # Plane at z=0
    plane_z = 0.0
    
    # Intersection: P = C + t * d, solve for z = plane_z
    t = (plane_z - camera_center[2]) / ray_direction[2]
    intersection = camera_center + t * ray_direction
    
    # z should be close to 0
    assert abs(intersection[2] - plane_z) < 0.001, f"z={intersection[2]} != {plane_z}"
    
    print(f"✅ Ray-plane intersection OK: {intersection}")
```

**Chạy tests:**
```bash
uv run pytest tests/test_mono_eye_modules.py -v
```

### 1.10 Tạo documentation cho repo

**Kiểm tra README:**
```bash
head -50 README.md
```

**Cập nhật docs/conventions.md nếu cần**

---

## Bước HOÃN LẠI (không làm trong giai đoạn này)

### ❌ KHÔNG cần làm bây giờ:

| Task | Lý do hoãn | Làm khi nào |
|------|-----------|-------------|
| In bảng ChArUco | Chưa cần thiết | Giai đoạn 2 (calibration) |
| Đo kích thước bảng | Cần có bảng in | Giai đoạn 2 |
| Tạo ground truth points | Cần có bảng | Giai đoạn 2 |
| Dán bảng lên bìa | Chưa có bảng | Giai đoạn 2 |
| Cố định bảng lên bàn | Chưa có bảng | Giai đoạn 2 |

---

## Báo cáo cần tạo

### File: `docs/G01_REPORT.md`

```markdown
# Giai đoạn 1: Chuẩn bị & Kiểm thử - Báo cáo

## Ngày: YYYY-MM-DD

## Trạng thái: ĐANG THỰC HIỆN
## Lưu ý: VIỆC IN BẢNG CHARUCO ĐƯỢC HOÃN LẠI

---

## 1. Test Results

### test_fov.py
```
==================== X passed ====================
```

### test_mono_eye.py
```
==================== X passed ====================
```

### Module Imports
| Module | Status |
|--------|--------|
| fov_tool.board | ✅/❌ |
| fov_tool.camera | ✅/❌ |
| mono_eye.config | ✅/❌ |
| mono_eye.camera_io | ✅/❌ |
| cv2.aruco.CharucoDetector | ✅/❌ |

### Camera
- Camera 0: ✅/❌ Opens OK / ❌ Not available

### smoke_test
- [ ] Board generation
- [ ] Synthetic test

---

## 2. Config Verification

| File | Status | Notes |
|------|--------|-------|
| configs/mono3d.yaml | ✅ Exists | |
| configs/ground_truth_points.csv | ✅ Exists / ❌ Needs creation |
| bang_calib_A4.yaml | ✅ Exists | |

---

## 3. Directory Structure

```
data/
├── calib/              ✅ Created / ❌
└── ground_truth/       ✅ Created / ❌
results/
├── logs/               ✅ Created / ❌
├── viz/                ✅ Created / ❌
└── experiments/        ✅ Created / ❌
```

---

## 4. mono_eye Module Status

| Module | Lines | Status | Notes |
|--------|-------|--------|-------|
| pose.py | X | stub | Giai đoạn 3 |
| projection.py | X | stub | Giai đoạn 4 |
| detect.py | X | stub | Giai đoạn 5 |
| viz.py | X | stub | Giai đoạn 6 |

---

## 5. Unit Tests

### tests/test_mono_eye_modules.py
```
==================== X passed ====================
```

---

## 6. Issues Encountered

| Issue | Severity | Resolution |
|-------|----------|------------|
| (ghi lại nếu có) | | |

---

## 7. Deferred Tasks (CHƯA LÀM - SẼ LÀM SAU)

| Task | Reason | Target Phase |
|------|--------|--------------|
| In bảng ChArUco | Chưa cần | Giai đoạn 2 |
| Đo kích thước bảng | Cần bảng in | Giai đoạn 2 |
| Tạo ground truth points | Cần bảng | Giai đoạn 2 |
| Dán & cố định bảng | Chưa có bảng | Giai đoạn 2 |

---

## Trạng thái: ✅ HOÀN THÀNH / ⏳ ĐANG LÀM / ❌ CÓ VẤN ĐỀ
```

---

## Tiêu chí hoàn thành

- [x] `pytest tests/test_fov.py` → passed
- [x] `pytest tests/test_mono_eye.py` → passed
- [x] Tất cả module imports thành công
- [x] Config files verify OK
- [x] Directory structure created
- [x] `tests/test_mono_eye_modules.py` → passed (hoặc tạo mới)
- [x] File `docs/G01_REPORT.md` đã tạo
- [x] Báo cáo rõ: VIỆC IN BẢNG ĐƯỢC HOÃN

---

## Commands tổng hợp

```bash
cd D:\Desktop\5\DPL302m\mono-eye-in-hand-3d

# 1. Chạy tất cả tests
uv run pytest tests/test_fov.py -v
uv run pytest tests/test_mono_eye.py -v

# 2. Module imports
uv run python -c "
from fov_tool.board import load_board
from mono_eye.config import load_config
import cv2
print('OpenCV:', cv2.__version__)
print('Has aruco:', hasattr(cv2, 'aruco'))
"

# 3. Tạo directories
mkdir -p data/calib data/ground_truth results/logs results/viz results/experiments

# 4. Verify config
uv run python -c "
import yaml
from pathlib import Path
c = yaml.safe_load(open('configs/mono3d.yaml'))
print('units:', c.get('units'))
print('camera:', c.get('camera', {}).get('width'), 'x', c.get('camera', {}).get('height'))
"

# 5. Board generation test
uv run python -c "
from fov_tool.board import load_board
board, detector = load_board('bang_calib_A4.yaml')
img = board.generateImage((1280, 720))
print('Board image:', img.shape)
"

# 6. Tạo/cập nhật unit tests
uv run pytest tests/test_mono_eye_modules.py -v
```

---

## Output mong đợi từ Antigravity

1. **Test Results:**
   - Copy/paste output của pytest
   - Xác nhận tất cả passed

2. **Config Verification:**
   - Output của verification script
   - Xác nhận files tồn tại

3. **Directory Structure:**
   - Screenshot hoặc `ls` output

4. **Issues (nếu có):**
   - Mô tả chi tiết lỗi
   - Cách đã thử fix

5. **File `docs/G01_REPORT.md`:**
   - Tạo với đầy đủ thông tin
   - Đánh dấu DEFERRED tasks rõ ràng
