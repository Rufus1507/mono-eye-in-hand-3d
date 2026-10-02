# Quy ước

- **Đơn vị**: milimét ở mọi nơi (code, CSV, biểu đồ).
- **Một nguồn sự thật cho tấm ChArUco**: file `bang_calib_*.yaml` của `tao_bang.py`. `mono_eye` không lặp lại thông số bảng.
- **Cạnh ô thật**: `fov_tool` dùng cạnh ô = 1.0 vì K không phụ thuộc thang đo, nhưng tọa độ 3D thì có. Vì vậy
  sau khi in, dùng thước thép đo cả bảng (mép ngoài các ô đen ở hai góc) và điền vào `configs/mono3d.yaml`,
  mục `board.measured.board_width_mm` / `board_height_mm` (danh nghĩa A4: 235.63 x 149.94 mm). `mono_eye.board_scale`
  lấy tỉ lệ = số đo / danh nghĩa (`kiem_in.ca_bang_*` của file bảng) rồi nhân với `ban_in.canh_o_mm`.
  Hai tỉ lệ ngang và dọc phải gần nhau (`board.max_anisotropy`, mặc định 1.5 %, giá trị tạm); lệch nhiều thì đo lại,
  vẫn lệch thì in lại.
- **Các trường `kiem_in.do_duoc_*` và `thuoc_*` trong file bảng KHÔNG được `mono_eye` dùng**: `tao_bang.py` in ba số kiểm
  (cả bảng, thước trên, thước trái) nhưng file YAML chỉ có hai ô `do_duoc_*`, không nói chúng ứng với số nào. Dùng trường
  riêng, tên rõ nghĩa, để không ai điền nhầm chiều dài thước vào chỗ của cả bảng.
- **Hệ tọa độ thế giới**: gắn với tấm ChArUco nằm trên bàn, `z = 0` là mặt bàn. Gốc và chiều các trục được kiểm chứng
  ở giai đoạn 3 (vẽ trục lên ảnh) rồi ghi lại ở đây; không giả định trước.
- **Pose**: `rvec, tvec` từ `solvePnP` biến tọa độ tấm sang tọa độ camera. Tâm camera trong hệ thế giới: `C = -R^T t`.
- **Chế độ camera**: một độ phân giải cố định (`configs/mono3d.yaml`). K chỉ đúng cho chế độ lúc hiệu chuẩn;
  `CameraModel.check_frame` từ chối khung khác kích thước.
- **camera.yaml**: `cv::FileStorage` với `camera_matrix`, `distortion_coefficients`, `image_width`, `image_height`,
  do `do_fov.py export` ghi, `mono_eye.camera_io` đọc.
- **Phiên bản OpenCV**: giữ 4.13.x cho cả việc sinh bảng lẫn nhận diện (OpenCV từng đổi thuật toán sinh bảng).
- **Không bao giờ** đánh giá độ chính xác trên các góc ChArUco đã dùng để giải pose.
- **Launcher**: `run_fov.ps1` phải giữ thuần ASCII (PowerShell 5.1 đọc file không BOM bằng codepage ANSI).
