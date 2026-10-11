# Prompt cho Gemini - Test với Quân Cờ Thật (Không cần thước)

## Nhiệm vụ

Validate pipeline với **1 quân cờ duy nhất**, dùng **góc ChArUco làm ground truth**.

---

## Bối cảnh

| Thà phần | Trạng thái |
|-----------|-------------|
| Camera calibration | ✅ RMS 0.44 px |
| FPS | ✅ 43.5 FPS |
| ChArUco detection | ✅ 60 góc biết vị trí chính xác |
| **Phương pháp GT** | **Dùng góc ChArUco** |

---

## Nguyên tắc Ground Truth

Các góc ChArUco có **vị trí 3D chính xác** vì:
- Cạnh ô được đo thực tế và lưu trong `bang_calib_A4.yaml`
- Tọa độ 3D của mỗi góc được tính toán từ board geometry

### Cách lấy Ground Truth

**Phương pháp 1**: Đặt quân cờ tại góc ChArUco
- Đặt quân cờ **sát mép góc ChArUco**
- Dùng tọa độ góc ChArUco gần nhất làm GT

**Phương pháp 2**: Đo khoảng cách tương đối
- Đặt quân cờ tại 2 góc ChArUco khác nhau
- Tính khoảng cách giữa 2 vị trí
- So sánh với khoảng cách thật (tính từ board geometry)

---

## Test Setup

```
┌────────────────────────────────────────────┐
│                                            │
│  ○───○───○───○───○───○───○───○───○───○  │
│  │   │   │   │   │   │   │   │   │   │   │
│  ○───○───○───○───○───○───○───○───○───○  │
│  │   │   │   │   │   │   │   │   │   │   │
│  ○───○───○───○───○───○───○───○───○───○  │
│  │   │   │   │   │   │   │   │   │   │   │
│  ○───○───○───○───○───○───○───○───○───○  │
│  │   │   │   │   │   │   │   │   │   │   │
│  ○───○───○───○───○───○───○───○───○───○  │
│  │   │   │   │   │   │   │   │   │   │   │
│  ○───○───○───○───○───○───○───○───○───○  │
│  │   │   │   │   │   │   │   │   │   │   │
│  ○───○───○───○───○───○───○───○───○───○  │
│                                            │
│  ○ = góc ChArUco (vị trí known)           │
│  ● = quân cờ đặt tại/sát góc              │
│                                            │
└────────────────────────────────────────────┘
```

---

## Các bước thực hiện

### Bước 1: Lấy tọa độ góc ChArUco

Viết script để tính tọa độ 3D của các góc:

```python
# Tính tọa độ 3D của góc ChArUco
# Board: 11x7 ô, cạnh ô = 21.421 mm
# Corner (i, j) có tọa độ: (i * square_size, j * square_size, 0)
```

### Bước 2: Test với quân cờ

1. Đặt quân cờ tại/sát một góc ChArUco
2. Chạy pipeline
3. Ghi nhận position_3d của quân cờ
4. So sánh với tọa độ góc ChArUco gần nhất

### Bước 3: Test khoảng cách tương đối

1. Đặt quân cờ tại góc A
2. Ghi nhận tọa độ
3. Di chuyển đến góc B
4. So sánh khoảng cách đo được vs khoảng cách thật

---

## Script Validation

Tạo script để tự động:

1. **Lấy tọa độ góc ChArUco** từ board config
2. **So sánh** position quân cờ với góc gần nhất
3. **Tính sai số** Euclidean distance

```python
# scripts/validate_chess_accuracy.py
from pathlib import Path
import cv2
import numpy as np
import yaml

from mono_eye.chess_pipeline import ChessMonoEyePipeline

# Load board config
with open('bang_calib_A4.yaml') as f:
    cfg = yaml.safe_load(f)

squares_x = cfg['bang']['o_ngang']
squares_y = cfg['bang']['o_doc']
square_mm = cfg['ban_in']['canh_o_mm']

# Tính tọa độ các góc ChArUco
charuco_corners_3d = []
for j in range(squares_y):
    for i in range(squares_x):
        charuco_corners_3d.append((i * square_mm, j * square_mm, 0.0))

# Chạy pipeline
pipeline = ChessMonoEyePipeline()
# ... capture frame, process ...
piece_pos = result.pieces[0]['position_3d']

# Tìm góc ChArUco gần nhất
distances = [np.linalg.norm(np.array(piece_pos[:2]) - np.array(corner[:2])) 
             for corner in charuco_corners_3d]
min_idx = np.argmin(distances)
gt_pos = charuco_corners_3d[min_idx]

error = distances[min_idx]
print(f"GT corner: {gt_pos}")
print(f"Measured: {piece_pos}")
print(f"Error: {error:.2f} mm")
```

---

## Ràng buộc

1. **Độ chính xác 3D**: Mean error < 5 mm
2. **Detection**: Quân cờ được nhận diện đúng
3. **Không cần thước**: Dùng góc ChArUco làm GT

---

## Expected Output

1. **Ảnh test** với annotation
2. **Bảng dữ liệu**:
   ```
   | Vị trí | GT Corner | Measured (X,Y) | Error (mm) |
   |---------|-----------|----------------|------------|
   | 1       | (0, 0)    | (1.2, -0.8)   | 1.4        |
   | 2       | (21, 0)   | (22.1, 0.3)   | 1.3        |
   ```
3. **Summary**: Mean error, Max error

---

## Sau khi hoàn thành

Báo cáo gồm:
1. Screenshot test cases
2. Bảng so sánh GT vs measured
3. Độ chính xác đạt được
4. Phát hiện issues

---

**Created**: 2025-01-XX
**Author**: Claude Code
**Task**: Test với 1 quân cờ, không cần thước
