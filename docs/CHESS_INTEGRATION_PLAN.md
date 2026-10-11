# Kế hoạch tích hợp Chess Models vào mono_eye

## Tóm tắt

**Mục tiêu**: Dùng model YOLO (`best25e_2712.pt`) để detect các quân cờ riêng lẻ trên bàn, sau đó dùng ChArUco pose để project chúng ra tọa độ 3D.

**Lưu ý quan trọng**: Không có bàn cờ trong frame. Chỉ detect quân cờ và định vị 3D.

---

## Kiến trúc

```
Camera Frame (BGR)
    │
    ├─────────────────────────────────────────┐
    │                                            │
    ▼                                            ▼
┌──────────────────────┐          ┌──────────────────────┐
│   ChArUco Board       │          │   Chess Pieces          │
│   (A4 board)         │          │   (best25e_2712.pt)     │
└─────────┬────────────┘          └─────────┬────────────┘
          │                                  │
          ▼                                  ▼
┌──────────────────────┐          ┌──────────────────────┐
│  PoseEstimator        │          │  ChessPieceDetector    │
│  solvePnP → rvec,   │          │  YOLO → bbox, class,  │
│  tvec, camera_center │          │  bottom_center_pixel   │
└─────────┬────────────┘          └─────────┬────────────┘
          │                                  │
          │      ┌──────────────────────────┘
          │      │
          ▼      ▼
┌──────────────────────────────┐
│     pixel_to_3d()            │
│  Ray-plane intersection       │
│  bottom_center → (x, y, z)    │
└─────────┬────────────────────┘
          │
          ▼
   3D Position (mm) per piece
   [{class, confidence, (x, y, z)}, ...]
```

---

## Ràng buộc đã xác nhận

| Tham số | Giá trị | Ghi chú |
|---------|---------|---------|
| Camera calibration | `data/calib/camera.yaml` | Dùng ChArUco từ mono_eye |
| ChArUco board | A4 11×7 | File: `bang_charuco_A4.png` |
| Piece model | `best25e_2712.pt` | Từ chessRobot |
| Robot integration | Không | Vision-only |
| Bàn cờ trong frame | Không | Chỉ detect quân cờ |

---

## Các bước thực hiện

### Bước 1: Chuẩn bị môi trường

- [ ] Copy model file `best25e_2712.pt` vào `data/models/`
- [ ] Kiểm tra ultralytics version tương thích

### Bước 2: Tạo module `mono_eye/chess_detectors.py`

#### ChessPieceDetector

| Thuộc tính | Mô tả |
|------------|--------|
| Input | frame (np.ndarray) |
| Output | List[Dict]: `{'class_name', 'confidence', 'bbox', 'bottom_center_pixel'}` |
| Model | `best25e_2712.pt` |
| Classes | white/black × {king, queen, rook, bishop, knight, pawn} |

### Bước 3: Tái sử dụng modules có sẵn

- [ ] `pose.py` - ChArUco pose estimation (giữ nguyên)
- [ ] `projection.py` - Ray-plane intersection (giữ nguyên)

### Bước 4: Tạo ChessPipeline (đơn giản)

```python
class ChessMonoEyePipeline:
    """
    Pipeline cho detect + định vị 3D quân cờ:
    ChArUco Pose → Piece Detection → Projection → 3D Positions
    """
    
    def __init__(
        self,
        piece_model_path: str,
        camera_yaml: str,
    ):
        ...
    
    def process_frame(self, frame) -> ChessResult:
        """
        Returns:
            - pose: CameraPose
            - pieces: List[Dict] với position_3d
        """
        ...
```

### Bước 5: Viết tests

- [ ] Test piece detection
- [ ] Test projection
- [ ] Test full pipeline

### Bước 6: Validation

- [ ] Đo sai số 3D positioning (mm)
- [ ] Benchmark FPS

---

## Chi tiết module

### ChessPieceDetector

**File**: `mono_eye/chess_detectors.py`

**Class mapping** (từ model `best25e_2712.pt`):
```python
CHESS_PIECE_LABELS = {
    'white_pawn': 'P', 'white_knight': 'N', 'white_bishop': 'B',
    'white_rook': 'R', 'white_queen': 'Q', 'white_king': 'K',
    'black_pawn': 'p', 'black_knight': 'n', 'black_bishop': 'b',
    'black_rook': 'r', 'black_queen': 'q', 'black_king': 'k'
}
```

**Output**:
```python
[
    {
        'class_name': 'white_knight',  # Từ model
        'fen_char': 'N',                 # Ký tự FEN
        'confidence': 0.95,
        'bbox': [x1, y1, x2, y2],      # Bounding box
        'bottom_center_pixel': (u, v),   # (x1+x2)/2, y2
        'position_3d': (x, y, z)       # Từ projection (mm)
    },
    ...
]
```

**Detection Logic**:
```python
def detect(self, frame):
    results = self.model(frame, conf=0.5, iou=0.5)
    pieces = []
    for r in results:
        for box, conf, cls_id in zip(r.boxes.xyxy, r.boxes.conf, r.boxes.cls):
            x1, y1, x2, y2 = box
            bottom_center = ((x1+x2)/2, y2)  # Điểm chạm bàn
            pieces.append({
                'class_name': r.names[int(cls_id)],
                'confidence': float(conf),
                'bbox': [x1, y1, x2, y2],
                'bottom_center_pixel': bottom_center
            })
    return pieces
```

---

## File structure

```
mono_eye/
├── __init__.py                    # Cập nhật exports
├── config.py                      # Giữ nguyên
├── camera_io.py                   # Giữ nguyên
├── board_scale.py                 # Giữ nguyên
├── pose.py                        # Giữ nguyên
├── projection.py                  # Giữ nguyên
├── detect.py                      # Giữ nguyên
├── filter.py                      # Giữ nguyên
├── viz.py                         # Giữ nguyên
├── evaluate.py                    # Giữ nguyên
├── pipeline.py                    # Giữ nguyên
│
├── chess_detectors.py             # MỚI: ChessPieceDetector
├── chess_pipeline.py             # MỚI: ChessPipeline
│
└── tests/
    ├── test_chess.py             # MỚI: Tests
    └── ...

data/
├── calib/
│   └── camera.yaml               # Từ fov_tool export
└── models/
    └── best25e_2712.pt         # Copy từ chessRobot
```

---

## Testing strategy

### Unit Tests

| Test case | Mô tả |
|-----------|--------|
| Piece detection | Detect known pieces |
| Piece detection empty | No pieces in frame |
| Projection valid | 3D position in expected range |
| Projection invalid | Point behind camera |

### Integration Tests

| Test | Mô tả |
|------|--------|
| Full pipeline | All pieces have valid 3D positions |
| Multiple frames | Consistent results across frames |

### Benchmark

| Metric | Target |
|--------|--------|
| Detection FPS | ≥ 30 fps |
| Full pipeline FPS | ≥ 15 fps |
| 3D position error | ≤ 5 mm |

---

## Milestones

### Milestone 1: Piece Detector (3 ngày)
- [ ] Copy model file `best25e_2712.pt` vào `data/models/`
- [ ] Tạo `chess_detectors.py` với ChessPieceDetector class
- [ ] Viết test đơn giản

### Milestone 2: Pipeline Integration (5 ngày)
- [ ] Tạo `chess_pipeline.py`
- [ ] Integration với pose.py và projection.py
- [ ] Viết integration test

### Milestone 3: Visualization (2 ngày)
- [ ] Thêm visualization mode cho 3D points
- [ ] Test với camera thật

### Milestone 4: Validation (2 ngày)
- [ ] Benchmark FPS
- [ ] Đo sai số 3D trên ground truth points

**Tổng thời gian ước tính: ~2 tuần**

---

## Đã xác nhận

| Tham số | Giá trị |
|----------|---------|
| Piece model | `best25e_2712.pt` |
| Camera calibration | `camera.yaml` (ChArUco) |
| ChArUco board | A4 11×7 |
| Robot integration | Không |
| Bàn cờ trong frame | Không có |

---

## Các quyết định đã đưa ra

### 1. Plane z = 0mm
- **Quyết định**: z = 0mm cho tất cả pieces
- **Lý do**: Giả định pieces đặt trên mặt phẳng bàn. Đây là assumption hợp lý cho eye-in-hand robot picking.

### 2. Confidence threshold = 0.5
- **Quyết định**: `conf=0.5` (50%)
- **Lý do**: Theo chessRobot reference code sử dụng cùng ngưỡng. Cân bằng giữa detection rate và false positives.

### 3. ChArUco Placement
- **Quyết định**: Đặt ChArUco ở góc frame (ví dụ: góc dưới bên phải)
- **Lý do**: Không che các pieces, vẫn đủ góc để calibrate pose

### 4. Visualization
- **Quyết định**: Hiển thị 3D points với class label
- **Cụ thể**: 
  - 3D scatter plot (matplotlib/Open3D)
  - Mỗi point có màu theo class (white/black)
  - Label hiển thị class name

---

**Created**: 2025-10-07
**Author**: Claude Code
**Version**: 3.0 (Simplified - No Board)
