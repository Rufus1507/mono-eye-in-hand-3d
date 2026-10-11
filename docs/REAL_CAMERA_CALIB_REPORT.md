# BÁO CÁO HIỆU CHUẨN CAMERA THỰC TẾ (REAL CAMERA CALIBRATION REPORT)

## 1. Thông Tin Tổng Quan & Môi Trường

| Tiêu chí | Thông số thực tế |
|---|---|
| **Ngày thực hiện** | 2026-10-10 |
| **Thiết bị camera** | DV20 USB Camera (1280x720) |
| **Bảng hiệu chuẩn** | ChArUco Board A4 (`bang_calib_A4.yaml`) |
| **Kích thước bảng** | 11 x 7 ô cờ (60 góc trong, 38 markers, từ điển DICT_4X4_50) |
| **Kích thước in thực tế** | Ô cờ: 21.421 mm, Marker: 15.569 mm |
| **Thư mục ảnh chụp vật lý** | `H:\GameProject\mono-eye-in-hand-3d\frames\` (40 ảnh) |
| **Thư mục phiên làm việc** | `sessions/calib_real/` |
| **File xuất cấu hình** | `data/calib/camera.yaml` |
| **File sao lưu cấu hình cũ** | `data/calib/camera_generic_backup.yaml` |

---

## 2. Kết Quả Hiệu Chuẩn Chi Tiết

- **Tổng số ảnh được cung cấp**: 40 ảnh.
- **Số ảnh đạt chuẩn đưa vào tính toán**: **40 / 40 ảnh (100%)**.
- **Số góc phát hiện trung bình mỗi ảnh**: 58.7 / 60 góc.

### Sai số tái chiếu (Reprojection Error):
| Chỉ số | Giá trị | Ngưỡng chất lượng | Đánh giá |
|---|---|---|---|
| **RMS Reprojection Error** | **0.4420 px** | < 1.5 px | **ĐẠT (VƯỢT TRỘI)** |
| **Mean Reprojection Error** | **0.4390 px** | < 1.5 px | **ĐẠT (VƯỢT TRỘI)** |
| **Min Reprojection Error** | **0.3220 px** | - | Cực kỳ chính xác |
| **Max Reprojection Error** | **0.5886 px** | < 1.5 px | Tốt hơn 2.5 lần so với ngưỡng tối đa |

---

## 3. Ma Trận Thông Số Nội (Camera Matrix K) & Hệ Số Méo (Distortion)

### Ma trận Intrinsic $K$:
$$
K = \begin{bmatrix}
1498.68 & 0.00 & 686.81 \\
0.00 & 1501.79 & 299.46 \\
0.00 & 0.00 & 1.00
\end{bmatrix}
$$

- **Tiêu cự**:
  - $f_x = 1498.68\text{ px}$
  - $f_y = 1501.79\text{ px}$
  - **Tỉ lệ khung hình (Aspect Ratio)**: $f_y / f_x = 1.0021 \approx 1.0$ (điểm ảnh vuông chuẩn, cảm biến CMOS chất lượng cao).
- **Tâm quang học (Principal Point)**:
  - $c_x = 686.81\text{ px}$
  - $c_y = 299.46\text{ px}$

### Hệ số méo quang học (Distortion Coefficients):
- $k_1 = -0.437674$ (méo thùng/barrel đặc trưng của ống kính góc rộng)
- $k_2 = 0.479925$
- $p_1 = -0.004391$ (méo tiếp tuyến)
- $p_2 = -0.000253$ (méo tiếp tuyến)
- $k_3 = 0.000000$ (cố định để đảm bảo tính ổn định của mô hình pinhole)

---

## 4. So Sánh Với Camera Generic Cũ

| Thông số | Camera Generic Cũ (Ước lượng giả định) | Camera Thực Tế (Sau hiệu chuẩn) | Nhận xét |
|---|---|---|---|
| **Nguồn dữ liệu** | Giả định lý thuyết | **40 ảnh chụp vật lý góc đa dạng** | Đo đạc thực tế chính xác |
| **Độ phân giải** | 1280 x 720 | 1280 x 720 | Khớp chuẩn |
| **$f_x$ (px)** | 900.00 | **1498.68** | Tiêu cự thực tế dài hơn ~1.66x |
| **$f_y$ (px)** | 900.00 | **1501.79** | Tương thích hoàn hảo với $f_x$ |
| **$c_x$ (px)** | 640.00 | **686.81** | Lệch phải nhẹ (~46.8 px) do lắp ráp cảm biến |
| **$c_y$ (px)** | 360.00 | **299.46** | Lệch lên trên nhẹ (~60.5 px) |
| **$k_1$** | 0.000000 | **-0.437674** | Ống kính thực có độ méo viền rõ rệt |
| **$k_2$** | 0.000000 | **0.479925** | Bù trừ méo bậc cao |
| **$p_1, p_2$** | 0.000000, 0.000000 | **-0.004391, -0.000253** | Bù sai lệch trục thấu kính thực tế |
| **Reprojection Error** | Không xác định | **0.4420 px** | Dưới 0.5 px (chính xác mức sub-pixel) |

---

## 5. Xác Thực Hoạt Động (Validation)

1. **Nạp cấu hình**: Đã kiểm tra nạp file `data/calib/camera.yaml` bằng `mono_eye.camera_io.load_camera_yaml()`. Kết quả không lỗi, đúng 100% kích thước và cấu trúc ma trận.
2. **Pose Estimation**: Đã chạy thử nghiệm trên ảnh chụp thực tế:
   - Số góc ChArUco phát hiện: **58 / 60 góc**.
   - Trạng thái: **Pose Valid: True**.
   - Sai số tái chiếu góc tư thế: **0.4137 px**.
   - Tọa độ tâm camera ước lượng: $X=298.6\text{ mm}, Y=323.0\text{ mm}, Z=-415.1\text{ mm}$.
3. **Unit Tests**: Chạy toàn bộ 11 test cases trong `tests/test_chess.py` đều **PASSED 100%**.
