# KỊCH BẢN THUYẾT TRÌNH V3: CHIẾU TRỰC TIẾP `PROJECT_REPORT.md`

**Dự án:** Mono Eye In-Hand 3D Localization
**Cách trình bày:** không dùng slide. Mở `PROJECT_REPORT.md` (VS Code Preview, Typora hoặc trình xem Markdown bất kỳ), bấm vào **Mục lục** hoặc cuộn tới từng mục theo thứ tự bên dưới.
**Thời lượng:** khoảng 16 phút + Q&A. **Xưng hô:** "em".

---

## 0. ĐỌC TRƯỚC: vì sao phải sửa báo cáo trước khi chiếu

Khi chiếu thẳng file, khán giả **đọc được mọi dòng trên màn hình**, kể cả những dòng dễ bị hỏi vặn. Có hai cách xử lý: (a) sửa nhanh file trước giờ nói (**khuyến nghị**, mất khoảng 10 phút), hoặc (b) giữ nguyên file và **nói đính chính** đúng lúc. Bảng dưới liệt kê từng dòng cần sửa.

| Vị trí trong file | Đang ghi | Vấn đề | Sửa thành (hoặc nói đính chính) |
|---|---|---|---|
| Đầu file | `Trạng thái: ~85% Hoàn thành` | Phần chưa làm lại là phần quyết định | `Trạng thái: Module phần mềm đã xong; chưa calibrate và chưa đo thực nghiệm` |
| 1.2 | `Đạt sai số < 5mm` | Chưa đo | `Mục tiêu: sai số < 5mm (chưa kiểm chứng)` |
| 1.2 | `tọa độ 3D (x, y, z)` | z do ràng buộc mặt phẳng | Giữ, nhưng **nói** "z do ràng buộc mặt phẳng" |
| 1.4 | Cột "Độ chính xác" (~2-5mm, ~1-2mm...) và LiDAR "1 camera" | Không có nguồn, chưa đo; LiDAR không phải "camera" | Xóa cột "Độ chính xác" và cột "Camera"; hoặc **bỏ qua cả bảng**, chỉ nói bằng lời |
| 4.1 "Bootstrap" | Liệt kê như ưu điểm của hệ thống | Bootstrap là của repo gốc | Thêm "(repo gốc)" |
| 4.1 "Ground Truth Validation" | Như đã có | Có công cụ, chưa có dữ liệu thật | `Có công cụ đánh giá (chưa chạy trên dữ liệu thật)` |
| 4.1 "Eye-in-hand capable", "Real-time 25-30 FPS" | Chưa kiểm chứng; FPS không nêu cách đo | | `Hướng tới eye-in-hand (còn thiếu hand-eye calibration)`; xóa FPS hoặc điền số bạn tự đo |
| 4.1 "82 tests" | Số không khớp | Xem dòng 6.1 | Dùng số thật từ `uv run pytest -q` |
| 6.1 | `82 tests passed (100%)` và các dòng cộng ra 87 | Nhóm "Environment 32" đã gồm "Infrastructure 11" (đếm hai lần); 32 gồm 21 test của repo gốc | Xóa khối này, thay bằng `N/N test tự động đạt (gồm test sẵn của repo gốc)` |
| 6.3 | Bảng latency, `20-30 FPS` | Chưa đo trên phần cứng thật | Xóa mục, hoặc ghi `[chưa đo]` |
| 6.4 | `Test Coverage 100%`, chấm sao | Coverage khác "test đạt"; tự chấm điểm dễ bị phản bác | **Xóa cả mục 6.4** |
| 8.1 | `Giảm noise 20-30%` | Chưa đo | `Kỳ vọng giảm nhiễu (chưa đo)` |
| 10.1 | `~85%`, `Code Quality: Xuất sắc`, `100%` | Như trên | Giống các dòng trên |
| 10.2 | `Code architecture xuất sắc`, `Test coverage cao 100%`, `Eye-in-hand ready` | Tự khen, sai thuật ngữ | Xóa hoặc đổi theo cách ở trên |
| Mục 2 | "Python 3.12 là phiên bản mới nhất" (nếu có) | Không đúng | `Phiên bản ổn định` |

**Hai việc cần kiểm tra ngay trước giờ nói:**
- `uv run pytest -q` rồi dùng đúng số in ra. Điền vào chỗ `[N]` bên dưới.
- Mở `configs/mono3d.yaml`, xem ngưỡng số góc tối thiểu và sai số tái chiếu tối đa đang dùng. Báo cáo cũ ghi 15 góc/2.0 px nhưng cấu hình ban đầu là 6 góc/1.5 px (đều là giá trị tạm). Nói đúng số trong file.

---

## 1. BẢN ĐỒ THỜI GIAN VÀ ĐIỂM DỪNG

| Bước | Mục trong file | Chiếu gì | Phút | Tích lũy |
|---|---|---|---|---|
| 1 | Đầu file + Mục lục | Tiêu đề, mục lục | 0:45 | 0:45 |
| 2 | 1.1 và 1.2 | Giới thiệu, bảng mục tiêu | 1:15 | 2:00 |
| 3 | 1.3 | Sơ đồ nguyên lý (khối ASCII) | 2:00 | 4:00 |
| 4 | 1.4 | Bảng so sánh (đã sửa) | 1:15 | 5:15 |
| 5 | 2. Công nghệ | 2.1.1 đến 2.1.4 | 1:45 | 7:00 |
| 6 | 3. Kiến trúc | 3.1, 3.2, 3.3 | 2:15 | 9:15 |
| 7 | 4. Ưu và nhược | 4.1 lướt, 4.2 nói kỹ | 2:00 | 11:15 |
| 8 | 5 và 6 | Chỉ lướt danh sách module và bảng files | 1:30 | 12:45 |
| 9 | 7. Hạn chế | Hai bảng 7.1, 7.2 | 0:45 | 13:30 |
| 10 | 8. Cải tiến | Chỉ nhắc tên | 0:30 | 14:00 |
| 11 | 9. Kế hoạch | 9.1 đến 9.3 | 0:45 | 14:45 |
| 12 | 10. Kết luận | 10.3 và ba ý chốt | 1:15 | 16:00 |

**Mẹo thao tác khi chiếu file**
- Phóng to chữ (Ctrl + `+`) để người ngồi cuối đọc được.
- Dùng **Mục lục** ở đầu file để nhảy tới mục; hoặc bật thanh Outline.
- Không cuộn liên tục. Mỗi mục, **cuộn tới đầu mục, dừng, rồi nói**.
- Các khối mã ở mục 8 chỉ lướt qua, đừng đọc.
- Có thể thu gọn (fold) các mục 5, 6, 8 trước để cuộn nhanh.

---

## 2. KỊCH BẢN THEO TỪNG MỤC CỦA FILE

### BƯỚC 1: Đầu file và Mục lục (0:45)

**Đang chiếu:** tiêu đề *BÁO CÁO TỔNG QUAN DỰ ÁN*, tên dự án, Mục lục.

**Lời nói**

> "Em xin chào thầy/cô và các bạn. Em là [Họ tên]. Hôm nay em trình bày tổng quan dự án *Mono Eye In-Hand 3D Localization* ngay trên báo cáo của dự án. Em sẽ đi theo các mục trong mục lục này."
>
> "Em nói trước hai điều. Một, phần hiệu chuẩn camera dựa trên mã nguồn mở **camera-fov-charuco** của HuyLeSmartTech, giấy phép MIT. Em mở rộng bằng gói **mono_eye** để làm phần định vị 3D, và sẽ chỉ rõ phần nào của repo gốc, phần nào em làm thêm. Hai, đây là **prototype**: các module phần mềm đã xong và kiểm thử bằng dữ liệu giả lập, còn **đo độ chính xác trên phần cứng thật** là bước tiếp theo."
>
> "Em sẽ đi qua bài toán, công nghệ, kiến trúc, ưu nhược điểm, hiện trạng, và kế hoạch."

**Chuyển ý:** cuộn xuống mục 1.1.

---

### BƯỚC 2: Mục 1.1 và 1.2: Giới thiệu và Mục tiêu (1:15)

**Đang chiếu:** đoạn giới thiệu và bảng mục tiêu.

**Lời nói**

> "Hãy tưởng tượng robot cần gắp một vật. Nó cần biết vật ở đâu trong không gian 3D, nhưng camera chỉ cho **một ảnh 2D**: mỗi điểm ảnh cho biết hướng, nhưng không cho biết xa bao nhiêu. Dự án này dùng **một camera đơn** để xác định vị trí của vật nằm trên mặt bàn."
>
> "Trong bảng mục tiêu, em nhấn vào hai dòng. Dòng **Phạm vi**: camera **di động**, cầm tay hoặc gắn trên tay robot. *Eye-in-hand* nghĩa là camera đi theo tay robot, nên vị trí camera thay đổi từng khung hình và phải được tính lại liên tục. Dòng **Độ chính xác**: dưới 5 milimét là **mục tiêu** trong điều kiện tối ưu, **chưa phải kết quả**, vì em chưa calibrate và chưa đo thực tế."
>
> "Một điểm cho chính xác: vì vật nằm trên mặt bàn, nên z **do ràng buộc mặt phẳng** cho trước. Thứ hệ thống thật sự phải tìm là vị trí **ngang** của vật."

**Chuyển ý:** "Vậy nguyên lý hoạt động là gì? Mục 1.3."

---

### BƯỚC 3: Mục 1.3: Nguyên lý hoạt động (2:00)

**Đang chiếu:** khối sơ đồ Calibrate → Pose → Detect → Project → Output.

> Khối ASCII không có hình tia và mặt phẳng. Hãy **vẽ tay hoặc nói bằng ví dụ số** (xem bên dưới), đừng chỉ đọc sơ đồ.

**Lời nói**

> "Ý tưởng cốt lõi: coi camera như một **đèn pin ngược**. Mỗi điểm ảnh tương ứng với **một tia** đi từ tâm camera ra ngoài. Ta không biết vật nằm ở đâu trên tia đó, nhưng nếu **biết vật nằm trên mặt bàn**, thì tia và mặt phẳng gặp nhau tại **đúng một điểm**. Đó là vị trí của vật."
>
> "Công thức: P bằng C cộng t nhân d, trong đó C là vị trí camera, d là hướng tia, t là khoảng cách cần tìm, chọn t sao cho z bằng 0."
>
> "Ví dụ số: camera ở 100, âm 200, 300 milimét, tia có hướng 0,2; 0,4; âm 0,8. Muốn z về 0 thì t bằng 300 chia 0,8, bằng 375. Suy ra P bằng 175, âm 50, và 0. Em xin kiểm tra lại: 100 cộng 0,2 nhân 375 là 175; âm 200 cộng 0,4 nhân 375 là âm 50; 300 trừ 0,8 nhân 375 là 0."
>
> "Giờ nhìn sơ đồ. Bốn khối này là bốn bước. **Calibrate** tính thông số ống kính K và D, làm **một lần**. **Pose** tính vị trí và hướng camera, làm **mỗi khung hình**. **Detect** tìm vật trong ảnh. **Project** biến điểm ảnh thành tia và giao với mặt bàn, ra tọa độ cuối cùng."
>
> "Để hệ thống biết camera ở đâu, ta cần một **mốc trên bàn**. Em sẽ nói ở mục 2."

**Chuyển ý:** cuộn xuống 1.4.

---

### BƯỚC 4: Mục 1.4: So sánh với các phương pháp khác (1:15)

**Đang chiếu:** bảng so sánh (**đã sửa**, xem phần 0). Nếu chưa sửa, **cuộn qua** và chỉ nói bằng lời.

**Lời nói**

> "Có mấy hướng phổ biến. **Stereo** dùng hai camera nên cần hiệu chuẩn cặp, setup phức tạp hơn. **LiDAR** đo khoảng cách trực tiếp nhưng thiết bị đắt. **Camera RGB-D** cho độ sâu sẵn, rất tiện, nhưng đắt hơn webcam và có thể nhiễu với vật bóng hoặc trong suốt. Còn **mạng học sâu ước lượng độ sâu từ một ảnh** thì thường chỉ cho độ sâu tương đối, thiếu tỉ lệ thật tính bằng milimét."
>
> "Câu hỏi của dự án là: **nếu chỉ có một webcam và biết vật nằm trên mặt bàn, ta đi được bao xa?** Cái giá phải trả là hai ràng buộc: vật nằm trên mặt phẳng, và camera phải nhìn thấy một tấm marker."
>
> "Em lưu ý: bảng này em chỉ dùng để so sánh về **hình thức**. Em **chưa có số đo độ chính xác** để so với các hướng khác."

**Chuyển ý:** cuộn tới mục 2.

---

### BƯỚC 5: Mục 2: Công nghệ sử dụng (1:45)

**Đang chiếu:** 2.1.1 OpenCV, 2.1.2 ChArUco, 2.1.3 YOLO, 2.1.4 Python.

**Lời nói**

> "Nền tảng là **OpenCV**: dùng cho bảng ChArUco, hiệu chuẩn camera, khử méo và giải pose bằng **solvePnP**."
>
> "Mục 2.1.2, **ChArUco**, là phần quan trọng. Đây là bàn cờ có gắn các marker ArUco. **Góc bàn cờ** cho vị trí rất chính xác. **Marker ArUco** cho mỗi vị trí một mã số riêng, nên hệ thống biết mình nhìn vào góc nào, kể cả khi tấm bảng bị che một phần. Ta **biết trước tọa độ thật** của từng góc, camera thấy các góc đó trong ảnh, nên **solvePnP** tính ra camera đang ở đâu và hướng thế nào so với bảng."
>
> "Một chi tiết hay bị bỏ qua: **kích thước thật của ô bảng quyết định tỉ lệ của mọi kết quả**. Sau khi in, em đo bảng bằng thước thép và nhập số đo thật vào cấu hình, thay vì tin kích thước thiết kế."
>
> "Mục 2.1.3, **YOLOv8n** phát hiện vật, kèm **ByteTrack** để gán mã theo dõi qua các khung hình. [Hiện em dùng trọng số huấn luyện sẵn.]"
>
> "Mục 2.1.4: NumPy, PyYAML, Matplotlib, Open3D, Pandas, và môi trường quản lý bằng **uv**. Python 3.12 là phiên bản ổn định mà các thư viện AI hỗ trợ tốt."

**Ghi chú:** ⚠ chỉ giữ câu trong ngoặc vuông nếu đúng sự thật. Nếu đã fine-tune YOLO thì mô tả quá trình đó (dữ liệu nào, bao nhiêu ảnh).

---

### BƯỚC 6: Mục 3: Kiến trúc hệ thống (2:15)

**Đang chiếu:** 3.1 sơ đồ kiến trúc, 3.2 bảng module, 3.3 luồng dữ liệu.

**Lời nói**

> "Mục 3.1: hệ thống chia ba lớp. **Đầu vào**: camera USB, tấm ChArUco cố định trên bàn, mô hình YOLO. **Xử lý**: calibrate, pose, detect, project. **Đầu ra**: tọa độ trên terminal, file CSV và hiển thị 3D."
>
> "Mục 3.3, em đi theo **một khung hình**. Camera cho ảnh 1280 nhân 720. **CharucoDetector** tìm các góc của tấm bảng. **solvePnP** biến chúng thành vị trí và hướng camera. Song song, **YOLO** tìm các vật và **ByteTrack** gán mã theo dõi. Từ khung bao của mỗi vật, em chọn **điểm đáy giữa của khung bao** làm điểm tham chiếu, với giả định đó là chỗ vật chạm bàn. Cuối cùng hàm `pixel_to_3d` giao tia của điểm đó với mặt bàn để ra tọa độ."
>
> "Hai nguyên tắc thiết kế: **calibrate làm offline một lần**, pipeline chỉ đọc kết quả đó. Và nếu một khung hình **không đạt kiểm tra chất lượng** về số góc phát hiện hoặc sai số tái chiếu, hệ thống **không xuất tọa độ**, thay vì dùng bừa vị trí camera cũ. Ngưỡng hiện dùng là [số trong `configs/mono3d.yaml`]."
>
> "Mục 3.2: phần nào của ai. **Phần hiệu chuẩn** nằm trong gói `fov_tool` của repo gốc: tạo bảng, chụp ảnh, tính K và D, ước lượng sai số bằng bootstrap, xuất `camera.yaml`. Phần em **xây thêm** là gói `mono_eye` gồm pose, projection, detect, pipeline, viz, evaluate, filter và các tiện ích cấu hình."

**Chuyển ý:** "Từ kiến trúc, em nói thẳng về ưu và nhược điểm."

---

### BƯỚC 7: Mục 4: Ưu điểm và nhược điểm (2:00)

**Đang chiếu:** 4.1 (lướt 20 giây), 4.2 (nói kỹ).

**Lời nói cho 4.1**

> "Ưu điểm chính là **chi phí thấp**: chỉ cần một webcam USB, phần mềm mã nguồn mở. Và **camera di chuyển tự do**, vì vị trí camera được tính lại ở từng khung hình. Hệ thống cũng có **kiểm tra chất lượng** để từ chối khung hình kém. Em ghi nguồn: phần ước lượng sai số bootstrap là của repo gốc."

**Lời nói cho 4.2 (nhấn mạnh)**

> "Giờ đến phần em muốn nói thẳng: nhược điểm. Ba ràng buộc:"
>
> "Một, **vật phải nằm trên mặt phẳng đã biết**. Vật ở độ cao khác hoặc xếp chồng thì kết quả lệch. Muốn bỏ ràng buộc này cần nhìn từ **hai góc** rồi tam giác đạc; em đã cài sẵn hàm nhưng chưa kiểm chứng thực tế."
>
> "Hai, **tấm ChArUco phải nằm trong khung hình**. Mất tấm bảng là mất vị trí camera. Khi gắn lên robot thật, vị trí camera sẽ lấy từ robot nên giới hạn này mất đi, nhưng cần thêm hand-eye calibration."
>
> "Ba, và thú vị nhất về hình học, là **góc nhìn**. Khi tia gần song song với mặt bàn, chỉ lệch một chút là điểm giao dịch đi rất xa. Ví dụ minh họa với giả định camera cao 300 milimét, tiêu cự khoảng 900 điểm ảnh, chỉ tính lệch một điểm ảnh: ở góc khoảng 53 độ so với mặt bàn, sai số chỉ khoảng 0,5 milimét; ở góc khoảng 5,7 độ, sai số lên khoảng **33 milimét**, gấp khoảng 64 lần. Đây là ví dụ minh họa, chưa phải số đo, và chưa tính sai số calibrate hay sai số vị trí camera. Vì vậy hệ thống có bộ lọc **loại các tia gần song song** (`min_ray_z`), thay vì cố tính ra một kết quả không đáng tin."
>
> "Ngoài ra còn các rủi ro thực tế trong 4.2: **ánh sáng** ảnh hưởng độ ổn định phát hiện, và **autofocus** đổi tiêu cự làm K không còn đúng, nên em khóa nét khi calibrate."

**Ghi chú:** công thức nếu bị hỏi: sai số vị trí ≈ h / sin²θ nhân với độ lệch góc (h là độ cao camera, θ là góc của tia so với mặt bàn). Tỉ lệ giữa hai góc là (sin 53° / sin 5,7°)² ≈ 64.

---

### BƯỚC 8: Mục 5 và 6: Những gì đã làm, tổng hợp (1:30)

**Đang chiếu:** cuộn **nhanh** qua danh sách module 5.1 đến 5.10, dừng ở bảng *Files đã tạo/sửa* (6.2). **Không dừng ở 6.1, 6.3, 6.4** nếu chưa sửa.

**Lời nói**

> "Mục 5 liệt kê từng giai đoạn em làm, em không đọc chi tiết, chỉ nói ý chính: môi trường và testing, rồi các module **pose**, **projection**, **detect**, **pipeline**, **viz**, **evaluate**, **filter**. Mục 6.2 liệt kê các file."
>
> "Về kiểm thử, các module được kiểm bằng **[N] test tự động, tất cả đều đạt**. Em nói rõ: một phần các test đó là test sẵn của repo gốc, và test cho module mới đều dùng **dữ liệu giả lập**."
>
> "Dữ liệu giả lập có ý nghĩa: nó chứng minh **phần tính toán đúng về mặt hình học**, ví dụ chiếu một điểm 3D đã biết xuống ảnh rồi tính ngược lại phải ra đúng điểm đó. Nhưng nó **chưa chứng minh** hệ thống chính xác ngoài đời, vì ngoài đời còn sai số calibrate, nhiễu ảnh, ánh sáng và sai số in bảng."

**Nếu chưa sửa file:** nói thêm, "Em xin đính chính: con số 100% trong báo cáo là tỉ lệ test đạt, không phải code coverage, và các số FPS, độ trễ trong mục 6.3 là ước lượng, em chưa đo trên phần cứng thật."

---

### BƯỚC 9: Mục 7: Hạn chế và thách thức (0:45)

**Đang chiếu:** hai bảng 7.1 và 7.2.

**Lời nói**

> "Mục 7.1 tóm lại hạn chế hiện tại, và dòng quan trọng nhất là **chưa calibrate camera**, nên chưa có K và D thật. Đó là lý do em chưa có số đo."
>
> "Mục 7.2 có một thách thức em thấy đáng nói: **máy in có thể làm méo bảng**. Nếu in thu nhỏ đều 4% mà vẫn dùng kích thước thiết kế thì mọi tọa độ sai khoảng 4%. Nên hệ thống kiểm tra độ lệch giữa hai chiều, và em đo bằng thước thép."

---

### BƯỚC 10: Mục 8: Cải tiến và tối ưu (0:30)

**Đang chiếu:** 8.1 Kalman, 8.2 Triangulation, 8.3 Outlier. **Không đọc khối mã.**

**Lời nói**

> "Mục 8 là ba hướng cải tiến: **bộ lọc Kalman** để làm mượt, **tam giác đạc từ hai góc nhìn** để bỏ ràng buộc mặt phẳng, và **loại ngoại lai**. Em đã cài và kiểm thử đúng đắn về mặt cài đặt, nhưng **chưa đo hiệu quả trên dữ liệu thật**. Con số giảm nhiễu 20 đến 30% là kỳ vọng, không phải kết quả."

---

### BƯỚC 11: Mục 9: Kế hoạch tiếp theo (0:45)

**Đang chiếu:** khối *GIAI ĐOẠN 2 - CALIBRATION*, 9.2, 9.3.

**Lời nói**

> "Bước tiếp theo, **9.1**, là calibrate camera: in bảng ở tỉ lệ 100%, đo bằng thước thép, dán phẳng, chụp khoảng 30 đến 40 ảnh từ nhiều góc, ước lượng sai số bằng bootstrap rồi xuất file thông số camera."
>
> "**9.2**: đo thực nghiệm. Đặt vật ở các điểm chuẩn đã đo bằng thước, thay đổi độ cao và góc nghiêng camera, rồi phân tích sai số trung bình, trung vị, P95 và lớn nhất. Từ đó em mới kết luận **một camera đủ chính xác trong điều kiện nào**."
>
> "**9.3**: dài hạn, nếu có robot FR5, là **hand-eye calibration** và tích hợp với động học robot."

---

### BƯỚC 12: Mục 10: Kết luận (1:15)

**Đang chiếu:** 10.3 *Cần hoàn thành* và 10.4. **Cuộn qua** 10.1 và 10.2 nếu chưa sửa.

**Lời nói**

> "Em xin chốt lại ba ý."
>
> "Một: **ý tưởng cốt lõi** là biến mỗi điểm ảnh thành một tia và giao với mặt bàn, với vị trí camera lấy từ tấm ChArUco."
>
> "Hai: em đã có **pipeline đầy đủ, kiểm thử được bằng dữ liệu giả lập**, đặt trên nền hiệu chuẩn của repo gốc. Về hướng eye-in-hand, bước còn thiếu là hand-eye calibration, nên em dùng cụm **hướng tới** chứ chưa phải *sẵn sàng*."
>
> "Ba: bước tiếp theo, và là bước quan trọng nhất, là **calibrate và đo thực tế** để trả lời câu hỏi một camera có đủ chính xác hay không. Các module phần mềm đã xong; phần **thực nghiệm** là phần còn lại."
>
> "Em xin cảm ơn thầy/cô và các bạn. Em sẵn sàng trả lời câu hỏi ạ."

**Ghi chú:** khi chuyển sang Q&A, **cuộn về đầu mục 10.3** và để màn hình đó. Dừng 2 giây sau câu cuối.

---

## 3. CHUẨN BỊ Q&A (giữ nguyên nội dung, thêm chỗ cuộn tới)

| Câu hỏi | Trả lời ngắn | Cuộn tới mục |
|---|---|---|
| Sao không dùng RGB-D? | RGB-D là lựa chọn hợp lý. Em chọn một camera vì chi phí thấp và để khám phá hình học đi được bao xa. Với vật xếp chồng thì RGB-D nhiều khả năng tốt hơn. Kết quả đo sẽ cho em dữ liệu để quyết định. | 1.4 |
| Sao không dùng mạng ước lượng độ sâu một ảnh? | Thường cho độ sâu tương đối, thiếu tỉ lệ thật, không ổn định giữa các khung. Em dùng hình học với marker để có tỉ lệ thật. Có thể kết hợp sau này, em chưa thử. | 1.4 |
| 3D mà z = 0 thì có thật là 3D không? | z do ràng buộc mặt phẳng; hệ thống tìm vị trí ngang. Với vật ở độ cao khác, đặt mặt phẳng ở độ cao đó nếu biết trước. Muốn tìm độ cao thật cần hai góc nhìn (đã cài, chưa kiểm chứng). | 4.2, 8.2 |
| Mất tấm ChArUco thì sao? | Khung đó không có vị trí camera nên không xuất tọa độ. Với robot thật, vị trí camera lấy từ động học, cần hand-eye calibration. | 4.2, 9.3 |
| Độ chính xác bao nhiêu? | Chưa có số đo. Mục tiêu < 5 mm. Em chỉ báo sau khi đo, theo điều kiện (độ cao, góc nghiêng), kèm trung vị, P95, lớn nhất, không chỉ trung bình. | 1.2, 9.2 |
| Vì sao chọn đáy giữa khung bao? | Gần chỗ vật chạm bàn nhất. Chỉ là xấp xỉ: khi camera nhìn xiên, đáy khung bao 2D không trùng tâm vùng tiếp xúc; đây là một nguồn sai số. | 3.3 |
| Khi nào phải calibrate lại? | Khi đổi camera, đổi độ phân giải, hoặc tiêu cự thay đổi (autofocus). Di chuyển camera thì không cần, vì pose tính lại mỗi khung. | 7.2 |
| Vì sao ChArUco chứ không bàn cờ hay một ArUco? | Bàn cờ chính xác nhưng không có mã số; một ArUco có mã nhưng chỉ 4 góc nên pose nhiễu hơn. ChArUco có cả hai ưu điểm. | 2.1.2 |
| Eye-in-hand khác hiện tại thế nào? Hand-eye calibration là gì? | Hiện em cầm camera và lấy pose từ tấm ChArUco. Eye-in-hand thật lấy pose từ robot; cần biết camera nằm đâu so với đầu tay robot, đó là hand-eye calibration, em chưa làm. | 9.3 |
| Phần deep learning nằm đâu? | YOLOv8n và ByteTrack; còn lại chủ yếu là hình học. Phần học sâu hiện còn mỏng nếu chỉ dùng trọng số có sẵn. Hướng mở rộng: fine-tune YOLO trên vật thật. (Nếu đã fine-tune thì thay bằng mô tả thực tế.) | 2.1.3 |
| Kalman đã chứng minh hiệu quả chưa? | Đã kiểm thử đúng về cài đặt, chưa đo giảm nhiễu trên dữ liệu thật. 20 đến 30% là kỳ vọng. | 8.1 |
| Phần nào tự làm, có dùng AI không? | Hiệu chuẩn là của repo gốc (MIT). Phần `mono_eye` là em xây. Em có dùng công cụ AI hỗ trợ viết và rà soát code; em chịu trách nhiệm về thiết kế và kiểm tra kết quả. ⚠ Kiểm tra quy định môn học về khai báo AI và trả lời đúng quy định. | Phụ lục A |
| Nhiều vật cùng lúc? | YOLO phát hiện nhiều vật, ByteTrack gán mã, mỗi vật có tia riêng. Vật bị che hoặc xếp chồng thì giả định mặt phẳng không còn đúng. | 3.3 |

---

## 4. BẢN RÚT GỌN

**10 phút:** bỏ Bước 4 (chỉ nói một câu: "so với stereo, LiDAR, RGB-D thì webcam rẻ hơn nhưng có ràng buộc mặt phẳng"), bỏ Bước 10, rút Bước 5 còn 1:15, Bước 8 còn 0:45.

**90 giây (không chiếu file, hoặc chỉ chiếu 1.3):**

> "Dự án của em xác định vị trí vật trên mặt bàn chỉ bằng một webcam. Ý tưởng: mỗi điểm ảnh là một tia từ camera. Nếu biết camera đang ở đâu và vật nằm trên mặt bàn, ta giao tia với mặt bàn để ra tọa độ. Vị trí camera được tính từ một tấm marker ChArUco đặt trên bàn, nên camera di chuyển tự do. Hệ thống dùng OpenCV cho calibrate và pose, YOLO để phát hiện vật, trên nền hiệu chuẩn mã nguồn mở camera-fov-charuco. Hiện các module phần mềm đã xong và kiểm thử bằng dữ liệu giả lập. Bước tiếp theo là calibrate camera và đo độ chính xác thật, mục tiêu dưới 5 milimét, rồi hướng tới tích hợp robot."

---

## 5. CHECKLIST TRƯỚC GIỜ NÓI

- [ ] Sửa các dòng trong bảng ở phần 0 (hoặc chuẩn bị câu đính chính)
- [ ] `uv run pytest -q` rồi điền `[N]` ở Bước 8
- [ ] Mở `configs/mono3d.yaml`, ghi lại ngưỡng số góc và sai số tái chiếu (Bước 6)
- [ ] Xác nhận YOLO dùng trọng số có sẵn hay đã fine-tune (Bước 5, Q&A)
- [ ] Chỉ nêu FPS hoặc độ trễ nếu **tự đo**; nếu chưa đo thì bỏ
- [ ] Thử mở file trên máy chiếu: kiểm tra bảng và khối ASCII (mục 1.3, 3.1) hiển thị thẳng hàng, chữ đủ lớn
- [ ] Chuẩn bị một hình tia và mặt phẳng (vẽ tay hoặc giấy) cho Bước 3, vì file không có hình này
- [ ] Mở sẵn một tab thứ hai ở mục 10.3 để dùng khi Q&A
- [ ] Nhớ: nói **mục tiêu** khi nói 5 mm, nói **kết quả** chỉ khi đã có số đo