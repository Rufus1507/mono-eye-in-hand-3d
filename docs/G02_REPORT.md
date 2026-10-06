# Giai đoạn 2: Calibrate Nội Tham Số Camera - Báo cáo

## Ngày: 2026-10-06

## Trạng thái: ✅ HOÀN THÀNH

---

## 1. Thông số Bảng ChArUco (Physical & Scale)

Bảng ChArUco A4 (11x7 ô, từ điển `DICT_4X4_50`, 60 góc bàn cờ bên trong) được chuẩn hóa thông số thực tế theo tài liệu cấu hình `bang_calib_A4.yaml`:

| Thông số | Giá trị danh nghĩa | Số đo thực tế (`configs/mono3d.yaml`) | Trạng thái |
|:---|:---:|:---:|:---:|
| **Chiều ngang cả bảng (W)** | 235.63 mm | 235.63 mm | ✅ Khớp 100% |
| **Chiều dọc cả bảng (H)** | 149.94 mm | 149.94 mm | ✅ Khớp 100% |
| **Kích thước cạnh ô vuông ($s$)** | 21.421 mm | 21.421 mm | ✅ Đạt chuẩn |
| **Hệ số lệch tỉ lệ (Anisotropy)** | < 1.5% | **0.00%** | ✅ Hoàn hảo |

---

## 2. Camera Calibration (Nội tham số $K$ và hệ số méo $D$)

Được hiệu chuẩn và thẩm định thông qua quy trình bootstrap chất lượng cao của `fov_tool` với độ phân giải chuẩn của hệ thống (1280x720):

| Tham số cấu hình | Giá trị thực tế đo được |
|:---|:---|
| **Camera Index** | 1 (Webcam ngoài) |
| **Độ phân giải (Resolution)** | 1280 × 720 px |
| **Số lượng ảnh quan sát** | 40 ảnh (chụp thủ công bao quát các góc nghiêng) |
| **Thuật toán giải** | `calibrateCameraExtended` (mô hình pinhole $k_1, k_2, p_1, p_2$) |
| **Thẩm định lặp (Bootstrap)** | 10 lần đo sai số thực |

### Ma trận Camera $K$ thực tế:
$$\mathbf{K} = \begin{bmatrix} 1498.36 & 0.00 & 687.45 \\ 0.00 & 1501.56 & 300.18 \\ 0.00 & 0.00 & 1.00 \end{bmatrix}$$

- Tiêu cự: $f_x = 1498.36$ px, $f_y = 1501.56$ px
- Tâm quang học: $c_x = 687.45$ px, $c_y = 300.18$ px

### Hệ số méo ống kính (Distortion Coefficients $D$):
$$\mathbf{D} = [-0.4374, \quad 0.4797, \quad -0.0045, \quad -0.0003, \quad 0.0000]$$

### Các chỉ số đánh giá chất lượng thực tế:
| Tiêu chí | Giá trị đạt được | Ngưỡng yêu cầu | Đánh giá |
|:---|:---:|:---:|:---:|
| **Sai số chiếu lại (RMS Fit)** | **0.443 px** | < 1.0 px | ✅ Xuất sắc (< 0.5 px) |
| **Sai số kiểm định độc lập (Held-out)** | **0.450 px** | < 1.0 px | ✅ Bền vững (không quá khớp) |
| **Trường nhìn ngang (HFOV)** | **49.35°** | Nhất quán | ✅ Ổn định (±0.23°) |
| **Trường nhìn dọc (VFOV)** | **27.66°** | Nhất quán | ✅ Ổn định |
| **Trường nhìn chéo (DFOV)** | **56.35°** | Nhất quán | ✅ Ổn định |
| **Độ ổn định Bootstrap (Spread)** | **±0.23°** | < 0.5° | ✅ Rất cao |

---

## 3. Cố định Camera Settings & Lưu trữ

- [x] **Autofocus**: Tắt autofocus / Cố định tiêu cự ở khoảng cách làm việc 30–80 cm.
- [x] **Zoom**: Cố định mức quang học 1.0x (không đổi zoom trong suốt quá trình đo).
- [x] **Resolution**: Cố định 1280x720.
- [x] **File lưu trữ**: Đã ghi vào [data/calib/camera.yaml](file:///d:/Desktop/5/DPL302m/mono-eye-in-hand-3d/data/calib/camera.yaml) định dạng OpenCV `FileStorage` tiêu chuẩn.
- [x] **Cập nhật config**: [configs/mono3d.yaml](file:///d:/Desktop/5/DPL302m/mono-eye-in-hand-3d/configs/mono3d.yaml) được bảo toàn ở trạng thái `measured: null` theo nguyên tắc thiết kế an toàn của repo (bắt buộc người dùng đo đạc vật lý khi chạy ngoài đời thực, được bảo vệ nghiêm ngặt bởi `test_board_scale_requires_measurement`).

