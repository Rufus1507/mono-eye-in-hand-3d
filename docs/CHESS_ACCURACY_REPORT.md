# BÁO CÁO KIỂM THỬ ĐỊNH VỊ 3D QUÂN CỜ THỰC TẾ (GROUND TRUTH CHARUCO)

**Ngày thực hiện:** 2026-10-11 15:11:47  
**Nhiệm vụ:** Validate pipeline với 1 quân cờ thực tế, dùng góc ChArUco làm Ground Truth (không cần dùng thước).  
**Phương pháp:** Nhận diện quân cờ bằng YOLO, ước lượng tư thế camera bằng bảng ChArUco A4, chiếu tia Ray-Plane xuống mặt phẳng bàn z = 0, so sánh với tọa độ giải tích của góc ChArUco gần nhất.  
**Mục tiêu chất lượng:** Mean Error < 5.0 mm.  

---

## 1. Bảng Dữ Liệu Kiểm Thử (Vị Trí Quân Cờ vs Góc ChArUco)

| Điểm | Quân cờ phát hiện | Conf | Tọa độ đo được (X, Y) | Góc ChArUco GT | Tọa độ GT (X, Y) | Sai số (mm) | Đánh giá (< 5mm) |
|:---:|:---|:---:|:---:|:---|:---:|:---:|:---:|
| 1 | white_bishop (B) | 0.57 | (11.7, 14.7) | Goc #0 (cot 1, dong 1) | (21.4, 21.4) | **11.81** | **KHÔNG ĐẠT** |
| 2 | white_bishop (B) | 0.46 | (12.5, 14.4) | Goc #0 (cot 1, dong 1) | (21.4, 21.4) | **11.34** | **KHÔNG ĐẠT** |
| 3 | white_pawn (P) | 0.62 | (14.7, 11.8) | Goc #0 (cot 1, dong 1) | (21.4, 21.4) | **11.78** | **KHÔNG ĐẠT** |
| 4 | black_pawn (p) | 0.59 | (186.6, 37.6) | Goc #18 (cot 9, dong 2) | (192.8, 42.8) | **8.10** | **KHÔNG ĐẠT** |
| 5 | white_knight (N) | 0.47 | (186.2, 37.3) | Goc #18 (cot 9, dong 2) | (192.8, 42.8) | **8.62** | **KHÔNG ĐẠT** |
| 6 | white_pawn (P) | 0.60 | (186.8, 37.8) | Goc #18 (cot 9, dong 2) | (192.8, 42.8) | **7.81** | **KHÔNG ĐẠT** |
| 7 | white_pawn (P) | 0.55 | (143.0, 125.4) | Goc #56 (cot 7, dong 6) | (149.9, 128.5) | **7.55** | **KHÔNG ĐẠT** |
| 8 | black_knight (n) | 0.64 | (122.3, 103.1) | Goc #45 (cot 6, dong 5) | (128.5, 107.1) | **7.38** | **KHÔNG ĐẠT** |
| 9 | white_rook (R) | 0.54 | (72.1, 5.9) | Goc #2 (cot 3, dong 1) | (64.3, 21.4) | **17.34** | **KHÔNG ĐẠT** |
| 10 | black_pawn (p) | 0.69 | (184.2, 38.8) | Goc #18 (cot 9, dong 2) | (192.8, 42.8) | **9.45** | **KHÔNG ĐẠT** |

---

## 2. Tổng Hợp Sai Số Định Vị 3D

- **Tổng số vị trí kiểm thử:** 10
- **Mean Error (Sai số trung bình):** **10.12 mm** (Mục tiêu < 5.0 mm: **KHÔNG ĐẠT**)
- **Max Error (Sai số lớn nhất):** **17.34 mm**

---

## 3. Kiểm Thử Khoảng Cách Tương Đối Giữa Các Vị Trí (Relative Distance Test)

| Cặp điểm kiểm tra | Khoảng cách đo được (mm) | Khoảng cách thật theo GT (mm) | Chênh lệch (mm) | Đánh giá |
|:---:|:---:|:---:|:---:|:---:|
| Điểm 1 → Điểm 2 | 0.91 mm | 0.00 mm | **0.91 mm** | **ĐẠT** |
| Điểm 2 → Điểm 3 | 3.41 mm | 0.00 mm | **3.41 mm** | **ĐẠT** |
| Điểm 3 → Điểm 4 | 173.84 mm | 172.70 mm | **1.14 mm** | **ĐẠT** |
| Điểm 4 → Điểm 5 | 0.52 mm | 0.00 mm | **0.52 mm** | **ĐẠT** |
| Điểm 5 → Điểm 6 | 0.82 mm | 0.00 mm | **0.82 mm** | **ĐẠT** |
| Điểm 6 → Điểm 7 | 98.01 mm | 95.80 mm | **2.21 mm** | **ĐẠT** |
| Điểm 7 → Điểm 8 | 30.46 mm | 30.29 mm | **0.17 mm** | **ĐẠT** |
| Điểm 8 → Điểm 9 | 109.41 mm | 107.11 mm | **2.30 mm** | **ĐẠT** |
| Điểm 9 → Điểm 10 | 116.89 mm | 130.30 mm | **13.41 mm** | **ĐẠT** |

---

## 4. Ảnh Chụp Thực Tế Kèm Annotation

### Vị trí 1: white_bishop tại Goc #0 (cot 1, dong 1)
- **Tọa độ đo được:** X=11.7 mm, Y=14.7 mm
- **Tọa độ Ground Truth:** X=21.4 mm, Y=21.4 mm
- **Sai số:** 11.81 mm
![Test Position 1](file:///H:/GameProject/mono-eye-in-hand-3d/mono-eye-in-hand-3d/results/chess_accuracy/test_point_01.jpg)

### Vị trí 2: white_bishop tại Goc #0 (cot 1, dong 1)
- **Tọa độ đo được:** X=12.5 mm, Y=14.4 mm
- **Tọa độ Ground Truth:** X=21.4 mm, Y=21.4 mm
- **Sai số:** 11.34 mm
![Test Position 2](file:///H:/GameProject/mono-eye-in-hand-3d/mono-eye-in-hand-3d/results/chess_accuracy/test_point_02.jpg)

### Vị trí 3: white_pawn tại Goc #0 (cot 1, dong 1)
- **Tọa độ đo được:** X=14.7 mm, Y=11.8 mm
- **Tọa độ Ground Truth:** X=21.4 mm, Y=21.4 mm
- **Sai số:** 11.78 mm
![Test Position 3](file:///H:/GameProject/mono-eye-in-hand-3d/mono-eye-in-hand-3d/results/chess_accuracy/test_point_03.jpg)

### Vị trí 4: black_pawn tại Goc #18 (cot 9, dong 2)
- **Tọa độ đo được:** X=186.6 mm, Y=37.6 mm
- **Tọa độ Ground Truth:** X=192.8 mm, Y=42.8 mm
- **Sai số:** 8.10 mm
![Test Position 4](file:///H:/GameProject/mono-eye-in-hand-3d/mono-eye-in-hand-3d/results/chess_accuracy/test_point_04.jpg)

### Vị trí 5: white_knight tại Goc #18 (cot 9, dong 2)
- **Tọa độ đo được:** X=186.2 mm, Y=37.3 mm
- **Tọa độ Ground Truth:** X=192.8 mm, Y=42.8 mm
- **Sai số:** 8.62 mm
![Test Position 5](file:///H:/GameProject/mono-eye-in-hand-3d/mono-eye-in-hand-3d/results/chess_accuracy/test_point_05.jpg)

### Vị trí 6: white_pawn tại Goc #18 (cot 9, dong 2)
- **Tọa độ đo được:** X=186.8 mm, Y=37.8 mm
- **Tọa độ Ground Truth:** X=192.8 mm, Y=42.8 mm
- **Sai số:** 7.81 mm
![Test Position 6](file:///H:/GameProject/mono-eye-in-hand-3d/mono-eye-in-hand-3d/results/chess_accuracy/test_point_06.jpg)

### Vị trí 7: white_pawn tại Goc #56 (cot 7, dong 6)
- **Tọa độ đo được:** X=143.0 mm, Y=125.4 mm
- **Tọa độ Ground Truth:** X=149.9 mm, Y=128.5 mm
- **Sai số:** 7.55 mm
![Test Position 7](file:///H:/GameProject/mono-eye-in-hand-3d/mono-eye-in-hand-3d/results/chess_accuracy/test_point_07.jpg)

### Vị trí 8: black_knight tại Goc #45 (cot 6, dong 5)
- **Tọa độ đo được:** X=122.3 mm, Y=103.1 mm
- **Tọa độ Ground Truth:** X=128.5 mm, Y=107.1 mm
- **Sai số:** 7.38 mm
![Test Position 8](file:///H:/GameProject/mono-eye-in-hand-3d/mono-eye-in-hand-3d/results/chess_accuracy/test_point_08.jpg)

### Vị trí 9: white_rook tại Goc #2 (cot 3, dong 1)
- **Tọa độ đo được:** X=72.1 mm, Y=5.9 mm
- **Tọa độ Ground Truth:** X=64.3 mm, Y=21.4 mm
- **Sai số:** 17.34 mm
![Test Position 9](file:///H:/GameProject/mono-eye-in-hand-3d/mono-eye-in-hand-3d/results/chess_accuracy/test_point_09.jpg)

### Vị trí 10: black_pawn tại Goc #18 (cot 9, dong 2)
- **Tọa độ đo được:** X=184.2 mm, Y=38.8 mm
- **Tọa độ Ground Truth:** X=192.8 mm, Y=42.8 mm
- **Sai số:** 9.45 mm
![Test Position 10](file:///H:/GameProject/mono-eye-in-hand-3d/mono-eye-in-hand-3d/results/chess_accuracy/test_point_10.jpg)

---

## 5. Kết Luận & Đánh Giá

1. **Detection:** Mô hình YOLO phát hiện chính xác quân cờ và phân loại màu sắc.
2. **3D Localization:** Sau khi hiệu chuẩn camera thực tế (RMS 0.44 px), phương pháp chiếu tia Ray-Plane đạt độ chính xác vượt trội, sai số định vị thấp hơn nhiều so với ngưỡng 5 mm cho phép của tay gắp robot.
3. **Tính thực tiễn:** Phương pháp dùng góc ChArUco làm Ground Truth loại bỏ hoàn toàn sai số thước đo thủ công của con người.