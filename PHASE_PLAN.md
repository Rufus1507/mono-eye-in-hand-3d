# Lộ trình thực hiện mono-eye-in-hand-3D

**Repo gốc:** HuyLeSmartTech/camera-fov-charuco  
**Mục tiêu:** Từ một camera monocular, ước lượng tọa độ 3D của vật trên mặt bàn, dùng tấm ChArUco làm mốc.  
**Đơn vị:** milimét (mm) everywhere.  
**Framework chính:** opencv-contrib-python 4.13.x, Python 3.11+

---

## Bảng repo và công cụ

| Repo / Công cụ | Giai đoạn | Lấy gì | Không lấy gì |
|----------------|-----------|--------|--------------|
| camera-fov-charuco (repo này) | 0→8 | `fov_tool/` (board, observations, geometry, calibration), auto-capture, bootstrap error | Phần FOV measurement nếu không cần |
| [tony2guo/charuco-pose-estimation](https://github.com/tony2guo/charuco-pose-estimation) | 3 | Luồng pose estimation tham khảo | API ArUco cũ |
| [ftPeter/pose-estimation](https://github.com/ftPeter/pose-estimation) | 1, 3 | Quy trình in, đo, calibrate | Makefile |
| [Paul-Rohit/ArUcoTrackerArena](https://github.com/Paul-Rohit/ArUcoTrackerArena) | 4, 7 | Công thức giao tia-plane, script đo sai số | Chỉ học, tự viết lại |
| [Lumeon-Labs/vision-positioning-demo](https://github.com/Lumeon-Labs/vision-positioning-demo) | 3, 5 | Luồng webcam, ArUco, solvePnP, tọa độ | Phần robot control |
| [david-s-martinez/Automatic-Workspace-Calibration](https://github.com/david-s-martinez/Automatic-Workspace-Calibration-Based-on-Aruco) | 8 (tùy chọn) | Ý tưởng multi-marker cho workspace rộng | Chỉ khi cần |
| opencv-contrib-python | 0→8 | CharucoDetector, calibrateCamera, solvePnP, undistortPoints | Không headless, không API ArUco cũ |
| ultralytics/ultralytics | 5 | YOLO detection + tracking | |
| rerun-io/rerun | 6 | 3D visualization timeline | Nếu nặng: Open3D/matplotlib thay thế |
| pandas, matplotlib | 7 | Log analysis, biểu đồ | |
| filterpy, scipy | 8 | Kalman filter, trung vị | Chỉ khi GĐ7 chỉ ra cần |

---

## Thứ tự thực hiện

```
GĐ0 → GĐ1 → GĐ2 → GĐ3 → GĐ4 → GĐ6 → GĐ5 → GĐ7 → GĐ8
                       ↑                      ↑
                       └──────────────────────┘
                    Có thể test song song một phần
```

**Lý do đổi thứ tự GĐ5 và GĐ6:** Trực quan hóa giúp debug pose trước khi thêm YOLO.

---

## Giai đoạn 0: Setup môi trường

**Mục tiêu:** Có môi trường chạy ổn định, hiểu các repo tham khảo, chốt quy ước.

### Chuẩn bị
- Windows 11 / Linux, git, Python 3.11+, camera USB
- Cài `uv` (package manager)

### Việc cần làm

#### 0.1 Tạo môi trường uv
```bash
cd mono-eye-in-hand-3d
uv sync
```

#### 0.2 Kiểm tra OpenCV và ArUco module
```bash
uv run python -c "import cv2; print(cv2.__version__, hasattr(cv2, 'aruco'))"
```
**Phải output:** version 4.13.x, `True`

#### 0.3 Clone repos tham khảo
```bash
mkdir third_party
cd third_party
git clone https://github.com/tony2guo/charuco-pose-estimation
git clone https://github.com/ftPeter/pose-estimation
git clone https://github.com/Paul-Rohit/ArUcoTrackerArena
git clone https://github.com/Lumeon-Labs/vision-positioning-demo
```

#### 0.4 Chạy thử từng repo (smoke test)
- `camera-fov-charuco`: đọc camera, detect board → chạy được
- Các repo khác: đọc code, xác nhận luồng chính

#### 0.5 Ghi chú repo
Tạo file `docs/repo-notes.md` hoặc cập nhật:
```
| Repo | Dùng được gì | Cần sửa gì |
|------|--------------|-------------|
| tony2guo | ... | API cũ, cần đối chiếu OpenCV mới |
```

#### 0.6 Chốt quy ước trong `configs/mono3d.yaml`
```yaml
units: mm

camera:
  index: 0
  width: 1280
  height: 720
  calib_file: data/calib/camera.yaml  # Tạo sau GĐ2

board:
  file: bang_calib_A4.yaml
  measured:
    board_width_mm: null    # Điền sau GĐ1
    board_height_mm: null
  max_anisotropy: 0.015

world_frame:
  origin: "góc tấm (kiểm chứng ở GĐ3)"
  z_axis: "hướng lên khỏi mặt bàn (z=0)"
  table_plane_z_mm: 0.0

quality_gate:
  min_charuco_corners: 6
  max_reprojection_error_px: 1.5

# Thêm: logging schema
logging:
  format: csv
  columns:
    - timestamp
    - frame_id
    - num_corners
    - reproj_error_px
    - camera_x_mm
    - camera_y_mm
    - camera_z_mm
    - camera_pitch_deg
    - camera_yaw_deg
    - camera_roll_deg
```

#### 0.7 Khởi tạo cấu trúc thư mục
```
mono-eye-in-hand-3d/
├── config.yaml              # Symlink hoặc copy từ configs/mono3d.yaml
├── calib/                   # Chứa camera.yaml (sau GĐ2)
├── data/                    # Input data
│   ├── boards/              # Bảng đã in
│   └── ground_truth/        # Điểm chuẩn (sau GĐ1)
├── results/                 # Output
├── sessions/                # Calibration sessions (từ fov_tool)
├── third_party/             # Clone repos tham khảo
└── mono_eye/                # Code chính
```

### Đầu ra
- Môi trường uv chạy được
- File `docs/repo-notes.md` ghi chú từng repo
- `config.yaml` có quy ước cơ bản

### Tiêu chí hoàn thành
- [ ] `uv run python -c "import cv2; print(cv2.__version__)"` → 4.13.x
- [ ] Camera đọc được ở đúng resolution
- [ ] Có thể chạy `do_fov.py capture` thử (không cần thành công full)

### Lỗi hay gặp
| Lỗi | Nguyên nhân | Xử lý |
|-----|-------------|--------|
| `cv2 has no attribute 'aruco'` | Cài opencv-python thay vì opencv-contrib-python | `uv pip uninstall opencv-python && uv sync` |
| Camera index thay đổi | Cắm lại USB | Thử `--camera 1`, `--backend dshow` |
| UTF-8 BOM issues | PowerShell 5.1 đọc file có dấu | Dùng file ASCII hoặc thêm BOM |

---

## Giai đoạn 1: Chuẩn bị vật lý

**Mục tiêu:** Tấm chuẩn đúng kích thước thật, không gian thử cố định, ground truth points.

### Chuẩn bị
- Máy in, giấy in 100%, bìa cứng, băng dính hai mặt
- Thước thép (độ chính xác 0.5 mm)
- Tờ giấy lưới (in lưới chấm đều 20mm)
- Đèn ổn định (không bóng đổ)

### Việc cần làm

#### 1.1 Tạo bảng ChArUco
```bash
uv run python tao_bang.py --kho a4 --so_hang 5 --so_cot 7
```
**Tham số tham khảo:** 7x5 ô, ô 30mm, marker 15mm, dictionary 6x6  
**Quy tắc:** Số hàng LẺ để tránh vấn đề OpenCV đổi thuật toán sinh bảng.

Output: `bang_charuco_A4.pdf`, `bang_charuco_A4.png`, `bang_calib_A4.yaml`

#### 1.2 In bảng
- In **100%** (tắt "fit to page")
- Giấy **mờ** (matte)
- **Không** in bảng A3 và A4 cùng lúc (tránh nhầm)

#### 1.3 Đo kích thước thật
Dùng thước thép, đo:
- Chiều ngang: mép ngoài ô đen trái → mép ngoài ô đen phải
- Chiều dọc: mép ngoài ô đen trên → mép ngoài ô đen dưới
- Đo 3 lần, lấy trung bình

**Ghi vào `configs/mono3d.yaml`:**
```yaml
board:
  measured:
    board_width_mm: 235.63   # Thay bằng số đo thực
    board_height_mm: 149.94  # Thay bằng số đo thực
```

#### 1.4 Kiểm tra anisotropy
```bash
uv run python -c "
import yaml
with open('configs/mono3d.yaml') as f:
    cfg = yaml.safe_load(f)
w = cfg['board']['measured']['board_width_mm']
h = cfg['board']['measured']['board_height_mm']
ratio = w / h
# So với danh nghĩa
nominal = 235.63 / 149.94
diff = abs(ratio - nominal) / nominal
print(f'Tỉ lệ W/H: {ratio:.4f}')
print(f'Danh nghĩa: {nominal:.4f}')
print(f'Lệch: {diff*100:.2f}%')
assert diff < cfg['board']['max_anisotropy'], 'Tỉ lệ lệch quá ngưỡng, in lại bảng'
"
```

#### 1.5 Dán bảng lên bìa cứng
- Dùng băng dính hai mặt phủ đều
- Không để bọt khí
- Cố định chắc lên bàn (không được xê dịch sau này)

#### 1.6 Tạo ground truth points
In tờ lưới chấm (20mm), đặt cạnh tấm. Đo vị trí từng chấm:

**File `configs/ground_truth_points.csv`:**
```csv
point_id,x_mm,y_mm,z_mm
p01,0,0,0
p02,20,0,0
p03,40,0,0
...
```

#### 1.7 Chuẩn bị vật thử
- 3-5 vật có kích thước đã biết
- Đánh dấu vị trí đặt
- Chụp ảnh làm reference

### Đầu ra
- Bảng đã dán phẳng, cố định
- `configs/mono3d.yaml` có kích thước thật
- `configs/ground_truth_points.csv` có tọa độ chuẩn
- Ảnh reference của vật thử

### Tiêu chí hoàn thành
- [ ] Tấm phẳng (kiểm tra bằng thị giác)
- [ ] Anisotropy < 1.5%
- [ ] Kích thước ghi trong config khớp số đo thước
- [ ] Ground truth points có tọa độ thật

### Lỗi hay gặp
| Lỗi | Nguyên nhân | Xử lý |
|-----|-------------|--------|
| Tỉ lệ lệch > 1.5% | Máy in co giãn không đều | In lại, kiểm tra máy in |
| Tấm bị cong | Giấy ẩm, dán không đều | Phơi khô, dán lại |
| Ánh sáng phản chiếu | Đèn chiếu trực tiếp vào bảng | Điều chỉnh góc đèn |
| Ground truth đo sai | Thước không chính xác | Dùng thước thép, đo nhiều lần |

---

## Giai đoạn 2: Calibrate nội tham số camera

**Mục tiêu:** Ma trận K và D đáng tin, cùng ước lượng sai số thật.

### Chuẩn bị
- GĐ0 và GĐ1 hoàn tất
- Camera đặt ở khoảng cách làm việc thực tế

### Việc cần làm

#### 2.1 Khóa camera settings
```powershell
# Chạy do_fov.py với freeze focus
.\run_fov.ps1 capture --camera 0 --name calib_session --width 1280 --height 720 --freeze-focus 1
```

#### 2.2 Chụp ảnh hiệu chuẩn
- **Số lượng:** 30-40 ảnh
- **Khoảng cách:** 30-80 cm (nhiều khoảng cách)
- **Góc nghiêng:** 20-45° theo nhiều hướng
- **Vị trí:** Phủ bốn góc khung hình, đặc biệt các góc và rìa
- **Auto-capture:** Di chuyển tấm, giữ yên ~0.4s, chờ capture tự động

#### 2.3 Phân tích với bootstrap
```powershell
.\run_fov.ps1 analyze sessions\calib_session --bootstrap 100
```

#### 2.4 Kiểm tra kết quả
Đọc output:
```
FOV ngang: XX.XXX ± X.XXX°
trạng thái: observations=True solved=True
```

**Tiêu chí:** 
- RMS < 0.5 px (hoặc < 1 px với webcam)
- Bootstrap spread nhỏ và nhất quán
- Ảnh khử méo trông thẳng

#### 2.5 Export camera.yaml
```powershell
.\run_fov.ps1 export sessions\calib_session --name "my_camera"
```

Copy `sessions\calib_session\runs\<run>\export\camera.yaml` → `data/calib/`

#### 2.6 Kiểm tra visual
```bash
uv run python examples/undistort.py data/calib/camera.yaml <test_image>
```
Ảnh sau khử méo: đường thẳng thật phải thẳng.

### Đầu ra
- `data/calib/camera.yaml` chứa K, D
- Báo cáo bootstrap error
- Ảnh test khử méo

### Tiêu chí hoàn thành
- [ ] RMS < 0.5 px (hoặc < 1 px)
- [ ] Bootstrap ± nhỏ và ổn định
- [ ] Ảnh khử méo đường thẳng thật thẳng
- [ ] Kết quả nhất quán giữa các lần chạy lại

### Lỗi hay gặp
| Lỗi | Nguyên nhân | Xử lý |
|-----|-------------|--------|
| RMS cao (> 1px) | Ảnh mờ, autofocus thay đổi | Khoá nét, chụp lại |
| Bootstrap spread lớn | Tập ảnh quá giống nhau | Thêm pose đa dạng |
| Kết quả không nhất quán | Autofocus/zoom thay đổi | Cố định camera settings |
| Độ phân giải không khớp | Đổi resolution sau calibrate | Cố định resolution |

---

## Giai đoạn 3: Pose camera theo thời gian thực

**Mục tiêu:** Mỗi khung hình biết camera ở đâu và hướng nào trong hệ tọa độ tấm.

### Chuẩn bị
- `data/calib/camera.yaml`
- `configs/mono3d.yaml` (đã có measured dimensions)
- Tấm đã cố định

### Việc cần làm

#### 3.1 Thiết kế API cho pose.py

```python
# mono_eye/pose.py

from dataclasses import dataclass
import numpy as np
import cv2
from fov_tool.board import load_board

@dataclass
class CameraPose:
    valid: bool
    rvec: np.ndarray      # Rotation vector (Rodrigues)
    tvec: np.ndarray      # Translation vector (mm)
    num_corners: int
    reproj_error_px: float
    
    @property
    def rotation_matrix(self) -> np.ndarray:
        """R from Rodrigues."""
        return cv2.Rodrigues(self.rvec)[0]
    
    @property
    def camera_center(self) -> np.ndarray:
        """Camera center in world frame: C = -R^T @ t."""
        R = self.rotation_matrix
        return -R.T @ self.tvec
    
    @property
    def euler_angles(self) -> tuple:
        """(pitch, yaw, roll) in degrees."""
        R = self.rotation_matrix
        # Extract Euler angles from rotation matrix
        # ... (tự implement hoặc dùng scipy)
        pass

def estimate_pose(
    frame: np.ndarray,
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray,
    board_config: str = "bang_calib_A4.yaml"
) -> CameraPose:
    """
    Estimate camera pose from ChArUco board in frame.
    
    Returns CameraPose with valid=False if detection fails quality gates.
    """
    # 1. Detect ChArUco corners
    detector = cv2.aruco.CharucoDetector(...)
    charuco_corners, charuco_ids = detector.detectBoard(frame)
    
    # 2. Quality gate
    if len(charuco_corners) < 6:
        return CameraPose(valid=False, ...)
    
    # 3. solvePnP
    success, rvec, tvec = cv2.solvePnP(
        objectPoints=board_obj_points,
        imagePoints=charuco_corners,
        cameraMatrix=camera_matrix,
        distCoeffs=dist_coeffs,
        rvec=rvec, tvec=tvec,
        useExtrinsicGuess=False,
        flags=cv2.SOLVEPNP_ITERATIVE
    )
    
    # 4. Compute reprojection error
    reproj_err = compute_reproj_error(...)
    
    # 5. Quality gate
    if reproj_err > 1.5:
        return CameraPose(valid=False, ...)
    
    return CameraPose(valid=True, rvec, tvec, len(charuco_ids), reproj_err)
```

#### 3.2 Tái sử dụng fov_tool
```python
from fov_tool.board import load_board
from fov_tool.observations import detect_charuco

# load_board trả về board + detector
board, detector = load_board("bang_calib_A4.yaml")

# Dùng detector cho CharucoDetector API mới
```

#### 3.3 Vẽ trục tọa độ để kiểm chứng
```python
def draw_axis(frame, K, D, rvec, tvec, axis_length_mm=50):
    """Vẽ trục X(đỏ), Y(xanh lá), Z(xanh dương) lên ảnh."""
    cv2.drawFrameAxes(frame, K, D, rvec, tvec, axis_length_mm)
    return frame
```

#### 3.4 Kiểm chứng quy ước trục
- Chạy live, vẽ trục lên ảnh
- Di chuyển tấm: trục Z phải hướng lên khỏi mặt bàn
- Đối chiếu với quy ước OpenCV mặc định
- **Ghi lại** quy ước thực tế vào `configs/mono3d.yaml`

#### 3.5 Test nền nhiễu
```bash
# Camera đứng yên, ghi 200 khung
python scripts/measure_noise.py --frames 200
```

Output:
```
x: mean=XXX.XX, std=XX.XX mm
y: mean=XXX.XX, std=XX.XX mm
z: mean=XXX.XX, std=XX.XX mm
```

#### 3.6 Test độ cao
1. Đo độ cao camera bằng thước: `h_real = XXX mm`
2. Tính từ pose: `h_calc = camera_center[2]`
3. So sánh: `|h_real - h_calc| < ngưỡng`

### Đầu ra
- `mono_eye/pose.py` với API rõ ràng
- Quy ước trục đã kiểm chứng và ghi lại
- Bảng nền nhiễu (noise baseline)

### Tiêu chí hoàn thành
- [ ] Trục Z hướng lên khỏi mặt bàn (kiểm chứng bằng vẽ)
- [ ] z tính được khớp với thước đo (sai số chấp nhận được)
- [ ] Độ lệch chuẩn khi đứng yên < X mm (ngưỡng tạm: 2 mm)
- [ ] Pose không bị lật khi di chuyển chậm

### Lỗi hay gặp
| Lỗi | Nguyên nhân | Xử lý |
|-----|-------------|--------|
| Pose bị lật 180° | Nhìn từ phía sau tấm | Kiểm tra quy ước, dùng `SOLVEPNP_ITERATIVE` |
| Nhiễu cao | Ánh sáng không ổn định | Cố định ánh sáng |
| z không khớp thước | Đơn vị nhầm (m vs mm) | Kiểm tra `units: mm` trong config |
| solvePnP không hội tụ | Ít góc quá | Đảm bảo ≥ 6 góc |

---

## Giai đoạn 4: Pixel sang tọa độ 3D

**Mục tiêu:** Từ điểm ảnh (u, v) → tọa độ (x, y, z) trong hệ tấm.

### Chuẩn bị
- `mono_eye/pose.py` chạy ổn
- `configs/ground_truth_points.csv`

### Việc cần làm

#### 4.1 Thiết kế projection.py

```python
# mono_eye/projection.py
import numpy as np
import cv2

def pixel_to_3d(
    pixel: tuple[int, int],
    pose: CameraPose,
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray,
    plane_z: float = 0.0  # mm
) -> tuple[bool, np.ndarray]:
    """
    Ray-plane intersection: pixel -> 3D point on table.
    
    Args:
        pixel: (u, v) in image
        pose: CameraPose with R, t
        camera_matrix: K
        dist_coeffs: D
        plane_z: z of table plane (default 0.0)
    
    Returns:
        (success, point_3d) where point_3d = [x, y, z] in mm
    """
    # 1. Undistort pixel (remove lens distortion)
    pixel_undist = cv2.undistortPoints(
        pixel, camera_matrix, dist_coeffs,
        P=camera_matrix
    ).reshape(-1)
    
    # 2. Create ray direction in camera frame
    # pixel in camera coords: (x_c, y_c, f)
    f_x, f_y = camera_matrix[0, 0], camera_matrix[1, 1]
    c_x, c_y = camera_matrix[0, 2], camera_matrix[1, 2]
    
    ray_cam = np.array([
        (pixel_undist[0] - c_x) / f_x,
        (pixel_undist[1] - c_y) / f_y,
        1.0
    ])
    
    # 3. Transform ray to world frame
    R = pose.rotation_matrix
    ray_world = R.T @ ray_cam  # Camera to world rotation
    
    # 4. Ray-plane intersection
    # Ray: P = C + t * d, Plane: z = plane_z
    C = pose.camera_center
    t = (plane_z - C[2]) / ray_world[2]
    
    if t < 0:
        return False, None  # Point behind camera
    
    point_3d = C + t * ray_world
    return True, point_3d
```

#### 4.2 Công cụ click chuột để validate
```python
# scripts/validate_projection.py
import cv2
import numpy as np
from mono_eye.pose import estimate_pose
from mono_eye.projection import pixel_to_3d
from mono_eye.camera_io import load_camera

def onMouse(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        success, point = pixel_to_3d((x, y), current_pose, K, D)
        if success:
            print(f"3D: ({point[0]:.2f}, {point[1]:.2f}, {point[2]:.2f}) mm")

# Load camera
K, D = load_camera("data/calib/camera.yaml")

# Live loop
while True:
    ret, frame = cap.read()
    pose = estimate_pose(frame, K, D)
    if pose.valid:
        cv2.imshow("Click to get 3D", frame)
        cv2.setMouseCallback("Click to get 3D", onMouse)
    if cv2.waitKey(1) == 'q':
        break
```

#### 4.3 Validate trên ground truth points
```bash
python scripts/validate_projection.py --ground-truth configs/ground_truth_points.csv
```

Output:
```
Point p01: real=(0.00, 0.00, 0.00), calc=(0.23, -0.15, 0.02), error=0.28 mm
Point p02: real=(20.00, 0.00, 0.00), calc=(20.15, -0.08, 0.03), error=0.19 mm
...
Mean error: 0.XX mm
Max error: 0.XX mm
```

#### 4.4 Vẽ bản đồ sai số
```python
# Tạo heatmap sai số trên tờ ground truth
import matplotlib.pyplot as plt

errors = compute_errors_on_grid(ground_truth_points, calculated_points)
plt.imshow(errors, cmap='hot', interpolation='bilinear')
plt.colorbar(label='Error (mm)')
plt.title('Projection Error Map')
```

#### 4.5 Test ở nhiều điều kiện
| Yếu tố | Giá trị test |
|---------|--------------|
| Độ cao | 300mm, 500mm, 700mm |
| Góc nghiêng | 0°, 15°, 30°, 45° |
| Khoảng cách | Gần (marker chiếm 50% frame), xa (20%) |

### Đầu ra
- `mono_eye/projection.py`
- Bảng sai số trên ground truth points
- Bản đồ heatmap sai số
- Hiểu sai số tăng thế nào theo khoảng cách/góc

### Tiêu chí hoàn thành
- [ ] Ở điều kiện thuận lợi (nhìn gần thẳng, gần tấm): sai số < 2 mm
- [ ] Bản đồ sai số cho thấy xu hướng rõ ràng
- [ ] Hiểu được: nghiêng/xa → sai số tăng như thế nào

### Lỗi hay gặp
| Lỗi | Nguyên nhân | Xử lý |
|-----|-------------|--------|
| Quên undistort | Dùng pixel gốc thay vì undistorted | Luôn undistort trước |
| Đơn vị nhầm | Tính ra mét thay vì mm | Kiểm tra `units: mm` |
| z_plane sai | Dùng z của marker thay vì z của mặt bàn | Đo lại, mặt bàn z=0 |
| Point behind camera | Tia hướng xuống dưới | Kiểm tra t < 0 |

---

## Giai đoạn 5: Trực quan hóa 3D

**Mục tiêu:** Nhìn thấy không gian mô phỏng: bàn, tấm, camera, vật.

### Chuẩn bị
- Pipeline GĐ3 + GĐ4 chạy ổn

### Việc cần làm

#### 5.1 Chọn visualization framework
```bash
# Nhẹ: matplotlib 3D
uv sync --group matplotlib

# Nặng nhưng đẹp: Rerun
uv sync --group rerun
# hoặc
uv pip install rerun-sdk
```

#### 5.2 Vẽ mặt bàn và tấm
```python
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

def draw_scene(poses, objects, table_bounds):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    
    # Mặt bàn (z = 0)
    x = np.linspace(*table_bounds['x'], 10)
    y = np.linspace(*table_bounds['y'], 10)
    X, Y = np.meshgrid(x, y)
    Z = np.zeros_like(X)
    ax.plot_surface(X, Y, Z, alpha=0.3)
    
    # Tấm ChArUco (lấy từ config)
    draw_board_outline(ax, board_corners)
    
    # Camera positions
    for pose in poses:
        ax.scatter(*pose.camera_center, c='r', marker='^')
    
    # Vật
    for obj in objects:
        ax.scatter(*obj.position, c='g', marker='o')
    
    ax.set_xlabel('X (mm)')
    ax.set_ylabel('Y (mm)')
    ax.set_zlabel('Z (mm)')
    plt.show()
```

#### 5.3 Timeline visualization (Rerun)
```python
import rerun as rr

rr.init("mono_eye visualization")

# Log static entities
rr.log("table", rr.Boxes3D(...))
rr.log("board", rr.Mesh3D(...))

# Log camera pose over time
for i, pose in enumerate(poses):
    rr.set_time_sequence("frame", i)
    rr.log("camera", rr.Transform3D(
        translation=pose.camera_center,
        rotation=pose.rvec
    ))
```

#### 5.4 Đồ thị theo thời gian
```python
# Sai số tái chiếu theo frame
fig, (ax1, ax2) = plt.subplots(2, 1)
ax1.plot(frames, reproj_errors)
ax1.set_ylabel('Reprojection Error (px)')
ax2.plot(frames, num_corners)
ax2.set_ylabel('Num Corners')
plt.show()
```

### Đầu ra
- Script visualization chạy được
- Hiển thị: bàn, tấm, camera di chuyển, vật đứng yên

### Tiêu chí hoàn thành
- [ ] Khi cầm camera di chuyển, camera hiển thị di chuyển trong không gian
- [ ] Vật đứng yên có tọa độ nhất quán
- [ ] Có thể tua lại các frame lỗi

---

## Giai đoạn 6: Phát hiện vật bằng YOLO

**Mục tiêu:** Vật tự động được phát hiện và đổi thành tọa độ 3D.

### Chuẩn bị
- GĐ3, GĐ4, GĐ5 ổn định
- Model YOLO (pretrained hoặc fine-tuned)

### Việc cần làm

#### 6.1 Cài đặt ultralytics
```bash
uv sync --group detect
```

#### 6.2 Chọn model
| Loại vật | Model | Ghi chú |
|----------|-------|---------|
| Vật phổ biến (cup, bottle) | YOLOv8n pretrained | Chỉ cần class names |
| Vật tùy chỉnh | YOLOv8n fine-tuned | 100-500 ảnh train |

#### 6.3 Chọn điểm tham chiếu
```python
def get_object_reference_point(bbox, reference="bottom_center"):
    """
    Chọn điểm trên bounding box làm tham chiếu 3D.
    
    Args:
        bbox: [x1, y1, x2, y2] (pixels)
        reference: "bottom_center" (điểm chạm bàn), "center", "top_center"
    
    Returns:
        pixel: (u, v) điểm tham chiếu
    """
    x1, y1, x2, y2 = bbox
    if reference == "bottom_center":
        return ((x1 + x2) / 2, y2)  # Giữa cạnh dưới
    elif reference == "center":
        return ((x1 + x2) / 2, (y1 + y2) / 2)
```

#### 6.4 Bật tracking
```python
from ultralytics import YOLO

model = YOLO("yolov8n.pt")
results = model.track(frame, persist=True, classes=[0, 39])  # person, cup

for r in results:
    if r.boxes and r.boxes.id is not None:
        bbox = r.boxes.xyxy.cpu().numpy()
        track_id = r.boxes.id.cpu().numpy()
```

#### 6.5 Ghép pipeline
```python
# mono_eye/detect.py

def process_frame(frame, pose, yolo_model):
    """
    Pipeline: frame -> YOLO detection -> 3D coordinates
    """
    # 1. Detect objects
    results = yolo_model.track(frame, persist=True)
    
    # 2. For each detected object
    detections = []
    for r in results:
        if r.boxes.id is None:
            continue
        
        for box, track_id in zip(r.boxes.xyxy, r.boxes.id):
            # 3. Get reference pixel
            pixel = get_object_reference_point(box.cpu().numpy(), "bottom_center")
            
            # 4. Convert to 3D
            success, point_3d = pixel_to_3d(pixel, pose, K, D)
            
            if success:
                detections.append({
                    'track_id': track_id,
                    'class_id': r.boxes.cls,
                    'bbox': box,
                    'position_3d': point_3d
                })
    
    return detections
```

#### 6.6 Ghi log
```python
import csv
from datetime import datetime

log_file = open("results/detections.csv", "w", newline="")
writer = csv.DictWriter(log_file, fieldnames=[
    "timestamp", "frame_id", "track_id", "class_name",
    "x_px", "y_px", "x_3d", "y_3d", "z_3d",
    "num_corners", "reproj_error"
])
writer.writeheader()

def log_detection(det, pose, frame_id):
    writer.writerow({
        "timestamp": datetime.now().isoformat(),
        "frame_id": frame_id,
        "track_id": det['track_id'],
        "x_3d": det['position_3d'][0],
        "y_3d": det['position_3d'][1],
        "z_3d": det['position_3d'][2],
        "num_corners": pose.num_corners,
        "reproj_error": pose.reproj_error_px
    })
```

### Đầu ra
- `mono_eye/detect.py`
- Pipeline hoàn chỉnh
- Log CSV mẫu

### Tiêu chí hoàn thành
- [ ] Vật đứng yên, nhìn từ nhiều góc → tọa độ 3D gần nhau
- [ ] Tracking giữ ID khi vật di chuyển trong frame
- [ ] Không có pose hợp lệ → không xuất tọa độ (không dùng pose cũ)

### Lỗi hay gặp
| Lỗi | Nguyên nhân | Xử lý |
|-----|-------------|--------|
| Bounding box dao động | Model không ổn định | Smooth bbox, giảm confidence threshold |
| Tọa độ nhiễu | Bbox dao động + projection | Thêm moving average |
| ID chuyển lung tung | Tracking mất đối tượng | Tăng `iou_threshold`, giảm `miss_tolerance` |
| Sai điểm tham chiếu | Không phải điểm chạm bàn | Kiểm tra z của point, nên ≈ 0 |

---

## Giai đoạn 7: Đánh giá sai số có hệ thống

**Mục tiêu:** Có số liệu để kết luận độ khả thi của hệ thống.

### Chuẩn bị
- Ground truth points
- Pipeline GĐ6 ổn định
- Log CSV từ nhiều điều kiện

### Việc cần làm

#### 7.1 Thiết kế experiment grid
```python
experiment_config = {
    'camera_height_mm': [300, 500, 700],
    'camera_pitch_deg': [0, 15, 30, 45],
    'object_distance_mm': [50, 150, 300],
    'movement_speed': ['slow', 'medium', 'fast'],
    'num_markers_visible': [4, 8, 12, 16]  # Ước lượng từ pose
}

# Mỗi combination lặp 10 lần
# Total: 3 * 4 * 3 * 3 * 4 * 10 = 4320 measurements
# Có thể giảm nếu cần
```

#### 7.2 Chuẩn hóa CSV columns
```csv
timestamp,frame_id,camera_height_mm,camera_pitch_deg,camera_yaw_deg,
object_id,object_distance_mm,movement_speed,num_charuco_corners,
reproj_error_px,camera_x,camera_y,camera_z,
detected_x,detected_y,detected_z,
ground_truth_x,ground_truth_y,ground_truth_z,
error_x,error_y,error_z,error_total
```

#### 7.3 Phân tích bằng pandas
```python
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("results/experiment_log.csv")

# Tổng hợp theo từng yếu tố
for factor in ['camera_height_mm', 'camera_pitch_deg', 'object_distance_mm']:
    stats = df.groupby(factor)['error_total'].agg([
        'mean', 'median', 'std', 
        lambda x: x.quantile(0.95),
        'max'
    ])
    print(stats)
    
    # Biểu đồ
    fig, ax = plt.subplots()
    df.boxplot(column='error_total', by=factor, ax=ax)
    ax.set_ylabel('Error (mm)')
    ax.set_title(f'Error vs {factor}')
    plt.savefig(f'results/error_vs_{factor}.png')

# Xác định vùng làm việc an toàn
safe_zone = df[df['error_total'] < threshold]
print(f"Vùng làm việc an toàn (error < {threshold}mm):")
print(safe_zone.groupby(['camera_height_mm', 'camera_pitch_deg']).size())
```

#### 7.4 Báo cáo kết luận
```markdown
# Báo cáo đánh giá sai số

## Tóm tắt
- Mean error: XX mm
- Median error: XX mm
- 95th percentile: XX mm
- Worst case: XX mm

## Theo yếu tố

### Độ cao camera
| Độ cao (mm) | Mean (mm) | 95th %ile (mm) |
|-------------|-----------|----------------|
| 300 | 1.2 | 2.1 |
| 500 | 2.3 | 4.2 |
| 700 | 5.1 | 9.8 |

### Góc nghiêng
...

## Vùng làm việc an toàn
- Độ cao: 300-500 mm
- Góc nghiêng: 0-30°
- Khoảng cách vật: 0-200 mm

## Kết luận
Hệ thống **khả thi / không khả thi** cho ứng dụng [tên ứng dụng].
Sai số trung bình XX mm, đủ/nhỏ hơn ngưỡng yêu cầu.
```

### Đầu ra
- CSV experiment log
- Biểu đồ theo từng yếu tố
- Báo cáo kết luận

### Tiêu chí hoàn thành
- [ ] Đủ bảng và biểu đồ theo từng yếu tố
- [ ] Kết luận rõ ràng về vùng làm việc
- [ ] So sánh với yêu cầu cụ thể (ví dụ: kẹp FR5 cần chính xác bao nhiêu?)

---

## Giai đoạn 8: Cải thiện (theo kết quả GĐ7)

**Mục tiêu:** Giảm sai số ở các điểm yếu đã đo được.

**Chỉ làm khi GĐ7 chỉ ra cần.**

### Các hạng mục có thể

#### 8.1 Ngưỡng chất lượng chặt hơn
```python
# Thay đổi trong mono3d.yaml
quality_gate:
  min_charuco_corners: 8    # Từ 6 lên 8
  max_reprojection_error_px: 1.0  # Từ 1.5 xuống 1.0
```

#### 8.2 Loại bỏ quan sát khi tia gần song song với bàn
```python
def filter_parallel_rays(ray_world, threshold=0.1):
    """Loại bỏ khi tia gần song song mặt bàn (|ray_z| nhỏ)."""
    return abs(ray_world[2]) > threshold
```

#### 8.3 Làm mượt theo thời gian
```python
from scipy.ndimage import median_filter
from filterpy.kalman import KalmanFilter

# Median filter đơn giản
smoothed_x = median_filter(positions[:, 0], size=5)
smoothed_y = median_filter(positions[:, 1], size=5)
smoothed_z = median_filter(positions[:, 2], size=5)

# Kalman filter phức tạp hơn
kf = KalmanFilter(dim_x=3, dim_z=3)
kf.x = initial_position
# ... (predict, update)
```

#### 8.4 Tổng hợp nhiều khung
```python
def aggregate_observations(positions, window=10):
    """Lấy trung vị của N khung gần nhất."""
    return np.median(positions[-window:], axis=0)
```

#### 8.5 Multi-marker workspace
```python
# Nếu vùng làm việc rộng
# Tham khảo: david-s-martinez/Automatic-Workspace-Calibration
# Dùng nhiều marker, interpolate giữa các marker
```

#### 8.6 Triangulation từ hai góc nhìn
```python
# Nếu cần bỏ giả định mặt phẳng
# Dùng triangulatePoints từ hai vị trí camera
points_4d = cv2.triangulatePoints(P1, P2, points1, points2)
points_3d = points_4d[:3] / points_4d[3]
```

### Tiêu chí hoàn thành
- [ ] Cải thiện có ý nghĩa thống kê (p < 0.05)
- [ ] Đo bằng cùng bộ thí nghiệm GĐ7

---

## Giai đoạn 9: Tích hợp Robot (FR5)

**Mục tiêu:** Dùng động học robot thay cho tấm ChArUco.

**Dự kiến - chi tiết hóa sau khi có robot thật.**

### Bước sơ bộ
1. Hand-eye calibration: Tính transform camera ↔ end-effector
2. Forward kinematics: Tính end-effector pose từ joint angles
3. Thay pose từ marker bằng pose từ robot kinematics
4. Tích hợp FR5 SDK

### Điều kiện tiên quyết
- Có FR5 robot
- Có SDK documentation
- GĐ7 kết luận hệ thống khả thi

---

## Phụ lục

### A. Logging Schema
```python
# mono_eye/logging.py

LOG_COLUMNS = [
    'timestamp',           # ISO format
    'frame_id',            # Frame counter
    'session_id',          # Experiment session
    
    # Camera state
    'num_charuco_corners', # Quality indicator
    'reproj_error_px',     # Pose quality
    
    # Camera pose
    'camera_x', 'camera_y', 'camera_z',  # mm
    'camera_pitch', 'camera_yaw', 'camera_roll',  # degrees
    
    # Detection
    'track_id',            # YOLO track ID
    'class_id', 'class_name',
    'bbox_x1', 'bbox_y1', 'bbox_x2', 'bbox_y2',
    
    # 3D result
    'point_x', 'point_y', 'point_z',  # mm
    
    # Ground truth (if available)
    'gt_x', 'gt_y', 'gt_z',
    'error_x', 'error_y', 'error_z', 'error_total'
]
```

### B. Testing Strategy
```python
# tests/test_pose.py
def test_pose_consistency():
    """Pose không thay đổi nhiều khi camera đứng yên."""
    # Mock camera feed với synthetic frame
    pass

def test_projection_accuracy():
    """Projection đúng cho điểm biết trước."""
    # Tính point 3D, so với ground truth
    pass

# tests/test_integration.py
def test_pipeline():
    """Full pipeline: frame -> pose -> 3D."""
    pass
```

### C. Troubleshooting Quick Reference

| Triệu chứng | Nguyên nhân | Xử lý |
|-------------|-------------|--------|
| Pose = NaN | solvePnP không hội tụ | Tăng số góc, kiểm tra K/D |
| Error tăng đột ngột | Bounding box nhảy | Thêm smoothing |
| Camera position drift | Accumulated error | Kiểm tra K calibration |
| Tracking lost | Object occluded | Tăng miss tolerance |

---

## Changelog

| Ngày | Phiên bản | Thay đổi |
|------|-----------|----------|
| 2025-XX-XX | 1.0 | Bản đầu tiên |
