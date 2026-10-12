# Prompt cho Gemini - Tạo Realtime 3D Visualization cho Chess Pipeline

## Nhiệm vụ

Chạy được `scripts/realtime_viz.py` với model chess (YOLO piece detection).

---

## Bối cảnh

| Thành phần | Hiện tại | Cần đạt |
|------------|----------|----------|
| Visualization | Dùng `MonoEyePipeline` | Dùng `ChessMonoEyePipeline` |
| Detections | Generic object | Chess pieces |
| 3D View | Grid + Objects | Grid + Chess pieces |
| Model | Generic YOLO | `best25e_2712.pt` |

---

## File gốc

`scripts/realtime_viz.py` - đã có visualization 3D với:
- Nửa trái: Camera 2D
- Nửa phải: Không gian 3D (grid, ChArUco, camera, trajectory)

## File mới cần tạo

`scripts/realtime_chess_viz.py` - adaptation cho chess pipeline

---

## Yêu cầu kỹ thuật

### 1. Thay đổi imports

```python
# Thay vì:
from mono_eye.pipeline import MonoEyePipeline
from mono_eye.viz import SimpleVisualizer

# Dùng:
from mono_eye.chess_pipeline import ChessMonoEyePipeline
```

### 2. Thay đổi detections visualization

```python
# Trong hàm render_3d_viewport:
# Thay det.position_3d bằng p['position_3d']
# Thay det.class_name bằng p['class_name']
# Màu sắc theo phe (white = cyan, black = magenta)
```

### 3. Cập nhật render_3d_viewport

```python
# Vẽ quân cờ trên mặt bàn
for p in chess_pieces:
    pos_3d = p.get('position_3d')
    if pos_3d is not None:
        # Màu theo phe
        is_white = p['class_name'].startswith('white')
        color = (255, 200, 0) if is_white else (50, 50, 255)
        
        # Vẽ marker 3D
        obj_center = proj(pos_3d)[0].astype(int)
        cv2.circle(canvas, tuple(obj_center), 8, color, -1)
        cv2.putText(canvas, f"{p['fen_char']}", ...)
```

### 4. Cập nhật run_live

```python
# Thay pose, detections = pipeline.process_frame()
# Bằng:
result = pipeline.process_frame(frame)
# Với result có: result.pose, result.pieces
```

### 5. Thêm CLI args

```python
parser.add_argument("--device", default="auto", help="Device: auto, cuda, cpu")
parser.add_argument("--conf", type=float, default=0.5, help="Confidence threshold")
```

---

## Cấu trúc code mới

```python
"""Realtime 3D Visualization cho Chess 3D Localization.

Hiển thị:
- Nửa trái: Camera 2D với chess pieces detected
- Nửa phải: Không gian 3D với grid, ChArUco, camera, chess pieces
"""
from mono_eye.chess_pipeline import ChessMonoEyePipeline

def render_3d_viewport_chess(
    camera_pos,
    camera_rvec,
    trajectory,
    chess_pieces,  # Thay detections
    width=640,
    height=480,
):
    # Vẽ grid, ChArUco, camera, trajectory (giữ nguyên)
    # Vẽ chess pieces (thay thế detections)
    ...

def run_live(
    pipeline: ChessMonoEyePipeline,
    camera_id: int = 1,
    ...
):
    ...
    result = pipeline.process_frame(frame)
    # Truyền result.pieces vào render_3d_viewport_chess
    ...
```

---

## Các bước thực hiện

### Bước 1: Tạo file mới
- [ ] Copy `realtime_viz.py` thành `realtime_chess_viz.py`
- [ ] Thay đổi imports

### Bước 2: Cập nhật visualization
- [ ] Sửa `render_3d_viewport` để nhận `chess_pieces` thay `detections`
- [ ] Thêm màu sắc theo phe (white/black)

### Bước 3: Cập nhật main và run_live
- [ ] Đổi `MonoEyePipeline` thành `ChessMonoEyePipeline`
- [ ] Cập nhật CLI args (--device, --conf)

### Bước 4: Test
- [ ] Chạy: `py -3.13 scripts/realtime_chess_viz.py --camera 1 --device cuda`
- [ ] Verify hiển thị đúng

---

## Expected Output

1. **File mới**: `scripts/realtime_chess_viz.py`
2. **Chạy thành công** với camera
3. **Hiển thị**: Chess pieces trên cả 2D và 3D view

---

## Ràng buộc

1. **Không sửa** `realtime_viz.py` gốc
2. **Tương thích** với `ChessMonoEyePipeline`
3. **Giữ nguyên** các tính năng 3D đã có

---

**Created**: 2025-01-XX
**Author**: Claude Code
**Task**: Tạo realtime chess visualization
