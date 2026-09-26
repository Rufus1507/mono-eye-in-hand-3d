# Thiết kế

Cách dùng: `README.md`. File này ghi **vì sao** làm như vậy, đã loại gì, và còn nợ gì.

## 1. Bài toán

Đo FOV và K/D của một camera, đủ tin để dùng. Khó không nằm ở chỗ tính — OpenCV
làm sẵn — mà ở chỗ **biết kết quả chính xác tới đâu**. Một phép hiệu chuẩn rất dễ
cho ra con số đẹp kèm sai số nhỏ mà cả hai đều sai.

## 2. Nguyên lý

**ChArUco, không phải bàn cờ trơn.** Bàn cờ trơn phải thấy trọn vẹn cả bảng, nên
không bao giờ đưa được bảng ra sát bốn góc khung — đúng chỗ hệ số méo cần ràng
buộc nhất. ChArUco vẫn nhận diện được khi bảng bị che hoặc tràn ra ngoài khung.

**Cạnh ô = 1.0, không đo bằng thước.** Trong hiệu chuẩn Zhang, cạnh ô chỉ đặt
thang đo cho thế giới; K (và f, và FOV) **bất biến** với thang đo đó. Nên không
cần đo cạnh ô, không cần đo cự ly tới bảng, và máy in thu nhỏ **đều** cũng không
sao. Chỉ scale **dị hướng** (ngang và dọc khác tỉ lệ) mới làm hỏng fx/fy.

**Bảng phẳng cứng, không bù cong.** Xem §5.

**Phiên bất biến.** Mọi thứ cần để chạy lại đều lưu: ảnh gốc, toạ độ góc, hash mã
nguồn, hash bảng, trạng thái camera lúc mở. Thay một khâu rồi chạy lại trên đúng
dữ liệu cũ thì mới quy được cải thiện cho khâu đó.

## 3. Chuỗi xử lý

```
capture → session (bất biến) → detect → split → fit → validate → export
```

Tách lõi khỏi GUI để chạy lại offline. `Q` là hủy thật — không solve, không ghi
kết quả, phiên đóng với trạng thái `canceled`.

## 4. Tự chụp

Máy trạng thái: `tìm bảng → theo dõi → chờ ổn định → chọn khung tốt nhất → đợi
đổi tư thế`.

- **Đứng yên** đo bằng dịch chuyển của **cùng ID góc** giữa hai khung theo
  timestamp (median ≤ 0.8 px, p90 ≤ 1.5 px, giữ ≥ 400 ms), không phải dịch
  chuyển của tâm bảng — quay quanh tâm thì tâm đứng yên trong khi cả bảng đang
  quay.
- **Đổi tư thế** đo bằng affine trên ID chung, tách riêng tịnh tiến / tỉ lệ /
  góc / phần phi-tương-tự. Chữ ký kiểu "tâm + đường chéo bbox" không phân biệt
  được xoay 90°, lại coi việc mất/gặp lại marker là đổi tư thế.
- **Chất lượng** đo bằng gradient **hai hướng** quanh từng góc, lấy trung bình
  điều hoà rồi chuẩn hoá theo tương phản cục bộ. Một con số Laplacian trên cả
  vùng bảng không thấy được nhoè **một chiều**, và ngưỡng tuyệt đối của nó thay
  đổi theo độ sáng.

**Vì sao đòi nghiêng:** bảng luôn song song cảm biến thì f và k1 đổi chỗ cho
nhau được — cùng một ảnh, "f lớn + méo mạnh" và "f nhỏ + méo nhẹ" khớp như nhau.
Phối cảnh mạnh là thứ duy nhất tách hai cái đó.

## 5. Sai số — phần quan trọng nhất

`std_intrinsics` mà OpenCV trả về là độ chụm **trong một lần fit**, với giả định
các điểm độc lập. Đo 14-09 trên webcam laptop: nó báo ~0.1° trong khi chỉ cần
đổi tập ảnh con là FOV nhảy tới **3.2°** — **lạc quan khoảng 10 lần**.

Nên `stability()` đo sai số trực tiếp: **bootstrap theo ảnh** (lấy lại n ảnh có
hoàn lại từ chính n ảnh, fit lại, lấy độ tản của nghiệm). Con số này in ra cạnh
mỗi giá trị FOV.

Đã nghiệm trên 3 phiên 720p độc lập: bootstrap tự báo **0.908°**, độ tản thực tế
giữa ba phiên **0.895°** — lệch 1.4 %.

**Giới hạn, phải đọc kèm:** đây là độ tản **trong một phiên**. Không gồm sai số
hệ thống (bảng in lệch, camera đổi trạng thái giữa các phiên), và sẽ **đánh giá
thấp** nếu nhiều ảnh gần trùng tư thế.

## 6. Bốn số FOV khác nhau

`fov_raw` là góc giữa các **tia thật** (qua tâm quang, có méo) — đây là FOV của
ảnh thật. `fov_pinhole_reference` là pinhole đối xứng, bỏ qua méo và lệch tâm.
Hai số lệch nhau cỡ **1°**.

Nhà sản xuất thường công bố theo pinhole đối xứng. So nhầm định nghĩa sẽ kết
luận sai — đã xảy ra khi đối chiếu FOV chéo: so `fov_raw` thì lệch 1.21° (1.27σ),
so đúng định nghĩa thì lệch 0.21° (0.65σ).

## 7. `validated` / `accepted` luôn false

Chương trình đo được **độ chụm**, không đo được **độ đúng**. Không phép tự kiểm
nào phát hiện được sai số hệ thống của chính nó. Chỉ mốc độc lập mới nói được, và
mốc đó phải do người đưa vào.

Kết quả đã đối chiếu (webcam laptop, 3 phiên 720p):

| | đo được | hãng | lệch |
|---|---|---|---|
| FOV ngang | 72.86 ± 0.52° | 72.55° | +0.31° (0.59σ) |
| FOV chéo (pinhole) | 80.41 ± 0.33° | 80.2° | +0.21° (0.65σ) |

## 8. Phương án đã loại

| Phương án | Vì sao bỏ |
|---|---|
| Bù độ cong bảng (một ẩn z mỗi góc, ~60 ẩn) | thừa sức làm RMS đẹp hơn mà không làm K đúng hơn. Dùng bảng cứng phẳng, rẻ hơn nhiều |
| Loại ảnh có RMS > mean+2σ rồi so RMS | tập đánh giá đã đổi nên RMS mới không chứng minh gì. Ảnh nghiêng gắt dễ bị loại nhất, mà đó chính là ảnh cần giữ |
| Bộ chọn ưu tiên ảnh nghiêng trước khi xét phủ | ăn hết quota trước bước phủ: phản ví dụ cho thiếu 0 ô → **39 ô** sau khi chọn |
| Chữ ký tư thế = tâm + đường chéo bbox | xoay 90° cho khoảng cách ~0 (mù), đổi tập ID cho 462 px (báo động giả) |
| Laplacian trên cả vùng bảng làm cổng nét | không thấy nhoè một chiều; ngưỡng tuyệt đối đổi theo độ sáng |
| Thả k3 tự do làm mặc định | RMS ngoài mẫu chỉ giảm 0.3–0.4 % nhưng FOV chéo nhảy 3–5° và ánh xạ méo mất hiệu lực (`solved=False`) |
| Ghim tâm quang để "ổn định hoá" | thử rồi: độ tản **tệ gấp đôi**. Tâm quang đang hấp thụ biến thiên có thật; ghim lại thì nó dồn sang f. Giữ làm cờ chẩn đoán `--fix-principal` |

## 9. Đã loại trừ những gì (14-09)

Độ tản ±0.9° từng bị nghi là triệu chứng của một lỗi. Năm giả thuyết, năm lần bác:

| Nghi can | Phép thử | Kết quả |
|---|---|---|
| Toạ độ góc lưu sai | `--redetect` | lệch 0.02–0.05° |
| Thiếu bậc tự do k3 | `--compare-models` | k3 tự do làm hình học vỡ |
| Tâm quang trôi tự do | `--fix-principal` | tản tệ gấp đôi |
| Autofocus đổi theo thời gian | chia nửa theo thời gian vs ngẫu nhiên | chia ngẫu nhiên tản **nhiều hơn** → không có xu hướng thời gian |
| Tư thế quá phẳng | đo nghiêng 80 ảnh | 22–25/40 ảnh nghiêng mạnh, gấp đôi mức cần |

Kết luận: **không có lỗi nào cả.** ±0.9° là độ chụm bình thường của bài toán này.
Cái hỏng thật chỉ là **con số sai số** — đã sửa ở §5.

Bài học: mốc ngoài (thông số hãng) trả lời được trong một phút cái mà năm phép
thử nội bộ không trả lời nổi. **Tìm mốc ngoài trước, đừng tối ưu trước.**

## 10. Nợ

- **Chưa có test cho `camera.py`** — toàn bộ đường nói chuyện với phần cứng. Đã
  có lần 9/9 test xanh trong khi `do_fov.py` gãy ngay dòng `import`.
- **Chưa có test cho `stability()`**.
- **Cổng `observations_sufficient` chỉ đếm phủ vị trí**, không đo đa dạng phối
  cảnh — nó xanh kể cả khi bộ ảnh thiếu nghiêng. Hiện phải tự canh khi chụp.
- **`fov_pinhole_reference` thiếu đường chéo** — muốn đối chiếu chéo với thông số
  hãng phải tự tính ngoài.
