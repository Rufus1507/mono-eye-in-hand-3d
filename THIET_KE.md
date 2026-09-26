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
capture ─┐
import  ─┴→ session (bất biến) → detect → split → fit → validate → export
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

**Số lần bootstrap (đo 27-09):** 10 lần là quá ít để chính con số ± đáng tin. Trên
phiên 1080p 40 ảnh, bớt 1–2 ảnh làm ± nhảy 1.21° / 0.85° / 2.06° với 10 lần; với
100 lần thì 1.41° (40 ảnh) và 1.32° (39 ảnh), khớp nhau trong 7 %. Nên `import`
(dùng để giao kết quả) mặc định 100 lần, đổi lại mất khoảng 15 phút cho 40 ảnh 1080p.
`capture`/`analyze` vẫn mặc định 10 cho nhanh; khi báo cáo con số ± thì chạy lại
với `--bootstrap 100`. Con số 0.908° vs 0.895° ở trên đo bằng 10 lần — sự trùng
khớp tốt tới 1.4 % một phần là may mắn.

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

## 10. Nhập ảnh/video người khác chụp (27-09)

`import` biến thư mục ảnh hoặc một video thành phiên cùng định dạng, để đo camera
không cắm được vào máy. Không điều khiển được camera, không thấy trực tiếp, nên
mọi cổng làm **sau**, và mọi ảnh bị loại đều ghi lý do vào manifest.

| Quyết định | Vì sao |
|---|---|
| Đọc theo hướng cảm biến, bỏ thẻ xoay EXIF | K thuộc về cảm biến; ảnh dọc/ngang của điện thoại là cùng cảm biến |
| Giữ nhóm (kích thước, EXIF hãng/model/tiêu cự/zoom) đông nhất, loại phần còn lại | trộn hai chế độ hay hai ống kính cho nghiệm vô nghĩa mà không báo lỗi |
| Ảnh xám bằng `imdecode` màu + `cvtColor`, không `IMREAD_GRAYSCALE` | `IMREAD_GRAYSCALE` lệch tối đa 1 mức xám, đủ làm góc lệch tới **1.48 px**, và 6/40 ảnh không còn so được (khác ID hoặc bị loại). Cũng là lý do `--redetect` lệch 0.008° |
| Trùng tư thế so với **mọi** ảnh đã nhận | ảnh gần trùng làm bootstrap đánh giá thấp sai số (§5) |
| Thiếu góc chung (< 8) = **khác** tư thế | `pose_change` trả `changed=False` khi thiếu góc chung (đúng cho tự chụp: chưa đủ so thì chờ). Dùng thẳng thì ảnh 3 và 25 của phiên tham chiếu — hai vùng bảng khác hẳn — bị loại oan |
| Chấm điểm nét trên bản thu về cạnh dài 1920 px | điểm nét là gradient **trên điểm ảnh**: cùng nội dung phóng ×2 thì median 5.58 → 4.39, loại oan 20/20. Sau chuẩn hoá: 5.48, loại 0/20. Góc và fit vẫn dùng ảnh gốc |
| Video đi qua `AutoCapture` với mốc thời gian từ số thứ tự khung | cùng cổng đứng yên / nét / đổi tư thế như tự chụp; ngưỡng đứng yên nhân theo tỉ lệ cạnh dài / 1920 |

**Đã kiểm:**
- Nhập 40 ảnh của một phiên 1080p có sẵn: toạ độ góc, ID, điểm nét **trùng từng
  bit** với lúc tự chụp. Loại đúng 1 ảnh gần trùng (ảnh 2 so ảnh 1: tịnh tiến 26
  px, xoay 0.9°). Với cùng 39 ảnh, K và D của đường `import` và đường gốc lệch
  **0**.
- Phép thử trên **có khả năng thất bại**: thay bằng `IMREAD_GRAYSCALE` thì nó bắt
  được ngay (góc lệch 1.48 px).
- Mỗi cổng có một test ca hỏng; tắt cổng thì test đỏ (8/8).

## 11. Nợ

- **Chưa có test cho `camera.py`** — toàn bộ đường nói chuyện với phần cứng. Đã
  có lần 9/9 test xanh trong khi `do_fov.py` gãy ngay dòng `import`.
- **Chưa có test cho `stability()`**.
- **Cổng `observations_sufficient` chỉ đếm phủ vị trí**, không đo đa dạng phối
  cảnh — nó xanh kể cả khi bộ ảnh thiếu nghiêng. Hiện phải tự canh khi chụp.
- **`fov_pinhole_reference` thiếu đường chéo** — muốn đối chiếu chéo với thông số
  hãng phải tự tính ngoài.
- **`import` chưa chạy trên ảnh điện thoại thật và video thật.** Phần chuẩn hoá độ
  phân giải chỉ mới kiểm bằng ảnh phóng to, chưa có bộ ảnh 12 MP thật; ngưỡng đứng
  yên của video 4K là suy ra, chưa đo.
- **Điểm nét sát ngưỡng và không đơn điệu theo tỉ lệ.** Phiên tham chiếu 1080p có
  ảnh thấp nhất 5.24 (ngưỡng 5.0). Ảnh giả lập phóng ×1.5 được 4.43 nhưng ×2 lại
  được 5.30. Cổng nét là thô; đừng đọc nó như một phép đo.
