# camera-fov-charuco

**English** · [Tiếng Việt](#tiếng-việt)

Measure a camera's field of view (FOV) and intrinsics (K, distortion D) with a
ChArUco board, **and report how far the numbers can be trusted**.

Computing a calibration is easy (OpenCV does it). Knowing its real error is not:
a calibration readily returns a nice number with a small error bar where both are
wrong. This tool is built around that problem.

## What makes it different

- **Honest error bars.** OpenCV's `std_intrinsics` assumes independent points and
  was measured here to be **~10× too optimistic** (reported ~0.1°, while re-fitting
  on image subsets moved the FOV by up to 3.2°). The tool instead reports a
  **per-image bootstrap** spread. Checked on 3 independent 720p sessions: bootstrap
  predicted 0.908°, the actual spread between sessions was 0.895° (1.4 % apart).
- **Checked against an external reference.** Laptop webcam, 3 sessions:

  | | measured | manufacturer | difference |
  |---|---|---|---|
  | Horizontal FOV | 72.86 ± 0.52° | 72.55° | +0.31° (0.59σ) |
  | Diagonal FOV (pinhole) | 80.41 ± 0.33° | 80.2° | +0.21° (0.65σ) |

- **Compares like with like.** Real-ray FOV (with distortion) and the symmetric
  pinhole FOV that datasheets usually quote differ by ~1°. Comparing the wrong pair
  gave 1.27σ; the right pair gave 0.65σ. Both are reported.
- **Immutable sessions.** Every capture stores raw frames, detected corners, board
  hash, code hash and camera state, so any stage can be changed and re-run on the
  exact same data.
- **Auto-capture that understands pose.** Stillness is measured on the *same
  corner IDs* between frames; pose change is decomposed into translation / scale /
  rotation / non-similar parts; sharpness is a two-direction gradient per corner,
  normalised by local contrast (a single Laplacian number misses one-directional
  blur).
- **`validated` is always `false`.** The program measures precision, not accuracy.
  Only an independent reference, supplied by a person, can establish accuracy.

Full design notes, rejected alternatives and open issues are in
[`THIET_KE.md`](THIET_KE.md) (Vietnamese).

## Install

```powershell
py -3.14 -m pip install -r requirements.txt
py -3.14 -c "import cv2; print(cv2.__version__, hasattr(cv2,'aruco'))"
```

Requires `opencv-contrib-python` 4.13 (ArUco module).

## Print the board

A4 and A3 boards are included (`bang_charuco_A4.pdf`, `bang_charuco_A3.pdf`).
Regenerate with `py -3.14 tao_bang.py --kho a4`. The `.pdf`, `.png` and `.yaml`
must come from the same run.

Print at **100 %** (no "fit to page"), glue **flat** on rigid card, matte paper.
Uniform printer scaling is harmless: FOV does not depend on the board's absolute
size. Only different horizontal and vertical scaling breaks fx/fy.

## Capture

```powershell
.\run_fov.ps1 capture --camera 0 --name my_webcam --width 1280 --height 720
```

Move the board to a new pose and **hold still ~0.4 s**. The tool keeps the
sharpest frame and asks for a new pose. At 40 frames it analyses automatically.

`Q` cancel (data kept, no solve) · `Enter` solve now · `Space` force-save (marked
`forced`, excluded from the solve).

For a good result, cover the whole frame, **especially the four corners**, and
**tilt the board 20–45° in several directions**. Without tilt, focal length and
distortion can trade off against each other.

| Flag | Default | |
|---|---|---|
| `--camera N` | 0 | index may change after re-plugging |
| `--width/--height` | 1920/1080 | FOV belongs to a (camera, mode) pair |
| `--target N` | 40 | frames to collect |
| `--bootstrap N` | 10 (`import`: 100) | bootstrap resamples, `0` = off. Use 100 when you report the ± figure: with 10 the ± itself varied 0.85–2.06° on one image set |
| `--freeze-focus 0` | on | turn off for fixed-focus webcams |
| `--board` | `bang_calib_A4.yaml` | use `bang_calib.yaml` for A3 |

## Import photos or a video

For a camera you cannot plug in, e.g. photos someone else took (see
[`PHOTO_GUIDE.md`](PHOTO_GUIDE.md)):

```powershell
.\run_fov.ps1 import path\to\photos --name client_cam
.\run_fov.ps1 import path\to\clip.mp4 --name client_cam
```

The photos become a normal session (same format, same `analyze`), and every
rejected file is listed in `manifest.json` with a reason:

| Reason | Why |
|---|---|
| `size_mismatch` | not the most common resolution: another camera mode |
| `different_camera_or_zoom` | EXIF make/model/focal length/digital zoom differs: phones switch lenses when zooming |
| `board_not_found` | fewer than 12 corners |
| `blurry` | same two-direction sharpness gate as capture |
| `same_pose` | same pose as **any** earlier accepted photo; near-duplicates make the bootstrap error too small |

Photos are read in **sensor orientation** (EXIF rotation ignored). Sharpness is
scored on a copy scaled to a 1920 px long side, because the gate was set on
webcams: without it, sharp 12 MP phone photos are rejected as blurry. Corners
and the fit always use the full image. A video goes through the same
auto-capture state machine as a live camera.

Checked on a stored 40-frame 1080p session: importing its frames gives the
same corners, bit for bit, as the live capture, and the same K and D.

## Re-analyse

```powershell
.\run_fov.ps1 analyze sessions\<id> [--redetect|--compare-models|--fix-principal|--k3]
.\run_fov.ps1 compare sessions\<id1>\runs\<r1>\result.json sessions\<id2>\runs\<r2>\result.json
```

Each `analyze` creates a new run and never overwrites.

## Output

```
FOV ngang 72.739 +/- 0.947° | dọc 44.889 +/- 0.583°
trạng thái: observations=True solved=True internal_check=True validated=False accepted=False
```

(`ngang` = horizontal, `dọc` = vertical.) `+/-` is the bootstrap error. Do not use
`std_intrinsics` from `result.json`. **Low RMS does not mean correct**: a set of
near-parallel views gives excellent RMS with a wrong focal length.

## Export for use elsewhere

```powershell
.\run_fov.ps1 export sessions\<id> --name "my camera" [--datasheet-hfov 72.55] [--datasheet-dfov 80.2]
```

Writes to `<run>/export/` (or `--out`):

| File | |
|---|---|
| `camera.yaml` | `cv::FileStorage`: `camera_matrix`, `distortion_coefficients`, `image_width`, `image_height` |
| `camera.json` | the same numbers plus FOV (real-ray, pinhole incl. diagonal) and bootstrap spread |
| `report.html` | readable report, prints to PDF: FOV, warnings, K and D, coverage grid, every photo with its result |

The report warns when a corner of the image has no board points (distortion
there is extrapolated), when RMS is above 1 px, and when held-out error is much
larger than fit error. It shows only file names, never paths from the sender's
computer.

`examples/undistort.py camera.yaml <image | folder | video>` removes distortion
using only OpenCV and NumPy; it refuses images at another resolution.

## Tests

```powershell
py -3.14 tests\test_fov.py
```

21 tests. The numerical-core tests were checked to fail when the FOV
computation is deliberately biased by 2 %; each import gate and each export
check was checked to fail its test when deliberately broken. `camera.py` and
`stability()` are not yet covered.

## Layout

```
do_fov.py          CLI: capture / import / analyze / export / compare
run_fov.ps1        launcher
tao_bang.py        board generator: .pdf + .png + .yaml
PHOTO_GUIDE.md     how to take photos for `import`
examples/
  undistort.py     remove distortion with camera.yaml (OpenCV + NumPy only)
fov_tool/
  board.py         board config, board + detector
  camera.py        open camera, record control state
  observations.py  corner detection, quality, motion / pose change
  acquisition.py   auto-capture state machine
  importing.py     photos / video -> session, with rejection reasons
  export.py        camera.yaml, camera.json, report.html
  session.py       immutable sessions and runs
  calibration.py   fit, hold-out set, coverage, bootstrap, report
  geometry.py      pixel <-> ray, FOV, distortion-map validity
  ui.py            window drawing
```

Console messages and some file names are in Vietnamese.

## License

MIT

---

## Tiếng Việt

Công cụ đo FOV và hiệu chuẩn camera (K, D) bằng bảng ChArUco, **kèm sai số thật**.
Mỗi lần chụp lưu thành một **phiên bất biến** (ảnh gốc + toạ độ góc + trạng thái
camera) nên phân tích lại được mà không phải chụp lại.

Vì sao thiết kế như vậy, đã loại phương án nào, còn nợ gì: [`THIET_KE.md`](THIET_KE.md).

### Cài

```powershell
py -3.14 -m pip install -r requirements.txt
py -3.14 -c "import cv2; print(cv2.__version__, hasattr(cv2,'aruco'))"
```

### In bảng

Bảng A4/A3 đã có sẵn. In lại hoặc đổi khổ: `py -3.14 tao_bang.py --kho a4`

Sinh ba file đi kèm nhau (`.pdf` bản in, `.png` xem nhanh, `.yaml` chương trình
đọc) — **phải cùng một lần sinh**, lệch nhau thì số đo sai mà không có gì báo.

In **100 %** (tắt "Fit to page"), dán **phẳng** lên bìa cứng, giấy **mờ**. Máy in
thu nhỏ đều cả hai chiều thì không sao — thang đo không đi vào K. Chỉ in lại khi
tỉ lệ ngang khác tỉ lệ dọc.

### Chụp

```powershell
.\run_fov.ps1 capture --camera 0 --name my_webcam --width 1280 --height 720
```

Đổi tư thế bảng rồi **giữ yên ~0,4 giây**; chương trình tự chọn khung nét nhất
rồi đòi đổi tư thế mới. Đủ 40 ảnh thì tự phân tích.

`Q` hủy (giữ dữ liệu, không tính) · `Enter` tính ngay · `Space` lưu cưỡng bức,
đánh dấu `forced` và **bị loại khỏi phép tính**.

Chụp thế nào cho tốt: đưa bảng khắp khung **nhất là bốn góc**; **nghiêng 20–45°
theo nhiều hướng** (quan trọng nhất — thiếu thì tiêu cự và hệ số méo đổi chỗ cho
nhau được); đưa gần cho bảng chiếm phần lớn khung.

| Cờ | Mặc định | |
|---|---|---|
| `--camera N` | 0 | chỉ số đổi sau mỗi lần cắm lại |
| `--width/--height` | 1920/1080 | **FOV thuộc về cặp (camera, chế độ)** — đổi chế độ là phép đo khác |
| `--target N` | 40 | số ảnh thì dừng |
| `--bootstrap N` | 10 (`import`: 100) | số lần đo sai số thật; `0` = tắt. Báo cáo con số ± thì dùng 100: với 10 lần, chính con số ± dao động 0,85–2,06° trên cùng một bộ ảnh |
| `--freeze-focus 0` | bật | tắt nếu webcam fixed-focus |
| `--board` | `bang_calib_A4.yaml` | dùng A3 thì trỏ `bang_calib.yaml` |

### Nhập ảnh hoặc video

Dùng khi không cắm được camera vào máy, ví dụ ảnh người khác chụp theo
[`PHOTO_GUIDE.md`](PHOTO_GUIDE.md):

```powershell
.\run_fov.ps1 import duong\dan\thu_muc_anh --name cam_khach
.\run_fov.ps1 import duong\dan\clip.mp4 --name cam_khach
```

Ảnh được chuyển thành một phiên bình thường (cùng định dạng, `analyze` như cũ).
Mỗi tệp bị loại đều ghi lý do trong `manifest.json`:

| Lý do | Vì sao |
|---|---|
| `size_mismatch` | khác độ phân giải chiếm đa số: là chế độ camera khác |
| `different_camera_or_zoom` | EXIF khác hãng/model/tiêu cự/zoom số: điện thoại tự đổi ống kính khi zoom |
| `board_not_found` | dưới 12 góc |
| `blurry` | cùng cổng độ nét hai hướng như khi tự chụp |
| `same_pose` | trùng tư thế với **bất kỳ** ảnh đã nhận nào; ảnh gần trùng làm bootstrap báo sai số quá nhỏ |

Ảnh đọc theo **hướng cảm biến** (bỏ qua thẻ xoay EXIF). Điểm nét chấm trên bản thu
về cạnh dài 1920 px, vì ngưỡng được đặt trên webcam: không thu thì ảnh điện thoại
12 MP nét vẫn bị gọi là mờ. Tìm góc và hiệu chuẩn luôn dùng ảnh gốc. Video đi qua
đúng máy trạng thái tự chụp như camera trực tiếp.

Đã kiểm trên một phiên 1080p 40 ảnh có sẵn: nhập lại ảnh của nó cho tọa độ góc
trùng từng bit với lúc chụp trực tiếp, và cùng K, D.

### Phân tích lại

```powershell
.\run_fov.ps1 analyze sessions\<id> [--redetect|--compare-models|--fix-principal|--k3]
.\run_fov.ps1 compare sessions\<id1>\runs\<r1>\result.json sessions\<id2>\runs\<r2>\result.json
```

| Cờ | Dùng để |
|---|---|
| `--redetect` | nhận diện lại góc từ PNG — tách lỗi "phát hiện góc" khỏi lỗi "fit" |
| `--compare-models` | k3 khoá vs k3 tự do trên **cùng tập giữ riêng** |
| `--fix-principal` | ghim tâm quang ở tâm ảnh — **giả định chẩn đoán**, không phải phép đo |

Mỗi lần `analyze` tạo run mới, không ghi đè.

### Đọc kết quả

```
FOV ngang 72.739 +/- 0.947° | dọc 44.889 +/- 0.583°
trạng thái: observations=True solved=True internal_check=True validated=False accepted=False
```

**`+/-` là sai số thật** (bootstrap trên chính bộ ảnh đó). Đừng dùng
`std_intrinsics` trong `result.json` — nó lạc quan khoảng **10 lần**.

| Trạng thái | Nghĩa |
|---|---|
| `observations_sufficient` | ≥ 20 ảnh và ≥ 28/40 ô lưới có ≥ 2 lượt quan sát độc lập |
| `solved` | nghiệm hữu hạn **và** ánh xạ méo hợp lệ |
| `internal_validation_completed` | đã chấm trên tập giữ riêng với K/D cố định |
| `validated`, `accepted` | **luôn `false`** — tự kiểm không chứng minh được độ đúng |

**RMS thấp không có nghĩa là đo đúng**: bộ ảnh quá phẳng cho RMS rất đẹp mà tiêu
cự sai nhiều. Chương trình chỉ đo được **độ chụm**; muốn biết **độ đúng** phải có
mốc độc lập (thông số hãng, hoặc phép đo góc bằng cách khác).

Đối chiếu thông số hãng thì **phải so cùng định nghĩa**: `fov_raw` là góc giữa
các tia thật (có méo), hãng thường công bố **pinhole đối xứng** — lệch nhau cỡ
**1°**, đủ để kết luận sai. Dùng `fov_pinhole_reference` trong `result.json`,
hoặc mục pinhole (có cả đường chéo) trong `camera.json` / `report.html` của `export`.

### Xuất kết quả để dùng nơi khác

```powershell
.\run_fov.ps1 export sessions\<id> --name "ten camera" [--datasheet-hfov 72.55] [--datasheet-dfov 80.2]
```

Ghi vào `<run>/export/` (hoặc `--out`):

| Tệp | |
|---|---|
| `camera.yaml` | `cv::FileStorage`: `camera_matrix`, `distortion_coefficients`, `image_width`, `image_height` |
| `camera.json` | cùng số liệu, kèm FOV (tia thật, pinhole có đường chéo) và độ tản bootstrap |
| `report.html` | báo cáo tiếng Anh, in ra PDF được: FOV, cảnh báo, K và D, lưới độ phủ, từng ảnh kèm kết quả |

Báo cáo cảnh báo khi một góc ảnh không có điểm bảng (méo ở đó là ngoại suy), khi
RMS trên 1 px, và khi sai số tập giữ riêng lớn hơn hẳn sai số fit. Chỉ ghi tên tệp,
không bao giờ ghi đường dẫn trên máy người gửi.

`examples/undistort.py camera.yaml <ảnh | thư mục | video>` khử méo, chỉ cần
OpenCV và NumPy; từ chối ảnh khác độ phân giải đã hiệu chuẩn.

### Sự cố

| Hiện tượng | Nguyên nhân |
|---|---|
| Cửa sổ hiện chữ cụt (`Gi bng yn`) | có chuỗi **có dấu** lọt vào phần vẽ; `cv2.putText` chỉ vẽ ASCII |
| `.ps1`: `string is missing the terminator` | file UTF-8 **không BOM** + chữ có dấu; PowerShell 5.1 đọc bằng ANSI |
| `cv2 has no attribute 'CAP_MSMF'` / `__version__` | `PYTHONPATH` trỏ vào thư mục thư viện hỏng → `cv2` thành package rỗng. Xoá biến đó |
| Không mở được camera | chỉ số đổi sau khi cắm lại; thử `--camera 1`, `--backend dshow`; hoặc app khác đang chiếm |
| `"guaranteed": false` trong manifest | driver **không cho khoá** autofocus. Giữ khoảng cách bảng–camera gần như không đổi, và đo ≥ 2 phiên rồi `compare` |
| Chụp mãi không lưu ảnh | đọc dòng trạng thái trên cửa sổ — nó nói đang vướng cổng nào |

### Kiểm thử

```powershell
py -3.14 tests\test_fov.py
```

Không dùng `-m unittest tests.test_fov` (`tests\` không có `__init__.py`).
21 test. Test phần lõi tính toán đã thử cố ý làm lệch FOV 2 % thì báo lỗi; mỗi
cổng loại ảnh của `import` và mỗi phép kiểm của `export` đã thử làm hỏng thì test của nó báo lỗi.
**Chưa phủ `camera.py` và `stability()`** — nên 21/21 đạt không đồng nghĩa chương
trình chạy được.

### Cấu trúc

```
do_fov.py          CLI: capture / import / analyze / export / compare
run_fov.ps1        launcher (gọi py -3.14 do_fov.py)
tao_bang.py        sinh bảng: .pdf + .png + .yaml
PHOTO_GUIDE.md     hướng dẫn chụp ảnh cho `import` (tiếng Anh, gửi khách)
examples/
  undistort.py     khử méo bằng camera.yaml (chỉ cần OpenCV + NumPy)
fov_tool/
  board.py         đọc cấu hình bảng, tạo board + detector
  camera.py        mở camera, ghi nhận trạng thái điều khiển
  observations.py  phát hiện góc, chấm chất lượng, đo chuyển động / đổi tư thế
  acquisition.py   máy trạng thái tự chụp
  importing.py     ảnh / video -> phiên, kèm lý do loại
  export.py        camera.yaml, camera.json, report.html
  session.py       ghi/đọc phiên bất biến, tạo run
  calibration.py   fit, tập giữ riêng, độ phủ, bootstrap sai số, xuất báo cáo
  geometry.py      pixel ↔ tia, FOV, kiểm tra ánh xạ méo
  ui.py            vẽ cửa sổ
sessions/<id>/     manifest.json · board.yaml · frames/ · observations.jsonl
                   runs/<run_id>/result.json
```

### Giấy phép

MIT
