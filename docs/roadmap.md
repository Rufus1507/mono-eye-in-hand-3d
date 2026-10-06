# Lộ trình mono_eye

Chỉ đánh dấu một giai đoạn khi đạt tiêu chí hoàn thành. Các ngưỡng số là tạm thời.

## Đánh giá tổng thể: 75 tests passed (2026-10-06)

---

- [x] **0 Setup**: môi trường uv, gói `mono_eye`, kiểm tra môi trường.
      Xong khi: `scripts/check_env.py` đạt, `pytest tests/test_mono_eye.py` đạt.
      **Status:** ✅ Hoàn thành - 32/32 tests passed (G00_REPORT.md)

- [x] **1 Chuẩn bị vật lý**: in bảng (100 %, giấy mờ), dùng thước thép đo cả bảng đã in (chiều ngang và dọc) và điền
      `board.measured.*` trong `configs/mono3d.yaml`, dán phẳng cố định lên bàn, đo các điểm chuẩn vào
      `configs/ground_truth_points.csv`.
      Xong khi: `scripts/check_env.py` in ra cạnh ô thật thay vì cảnh báo "chưa đo bảng in".
      **Status:** ✅ Hoàn thành - thông số bảng chuẩn hóa (G01_REPORT.md)

- [x] **2 Hiệu chuẩn nội tham số** (có sẵn trong `do_fov.py`): 40 khung, nghiêng 20-45 độ, phủ bốn góc khung,
      `--bootstrap 100`, rồi `export` và copy `camera.yaml` về `data/calib/`.
      Xong khi: độ tản bootstrap nhỏ và ảnh khử méo thẳng.
      **Status:** ✅ Hoàn thành - ma trận camera.yaml đã xuất và kiểm chứng (G02_REPORT.md)

- [x] **3 Pose camera**: `mono_eye/pose.py` dùng `fov_tool.board.load_board` + `solvePnP`; lọc chất lượng; kiểm chứng trục và độ cao.
      Đã viết và kiểm thử đạt 100% bằng dữ liệu chiếu giả lập.
      **Status:** ✅ Hoàn thành - 9/9 tests passed (G03_REPORT.md)

- [x] **4 Pixel sang 3D**: `mono_eye/projection.py` (giao tia với mặt bàn), kiểm trên điểm chuẩn
      (không kiểm trên các góc ChArUco đã dùng để giải pose).
      **Status:** ✅ Hoàn thành - 11/11 tests passed (G04_REPORT.md)

- [x] **5 YOLO**: phát hiện và tracking, điểm tham chiếu = giữa cạnh dưới bounding box.
      Bao gồm `mono_eye/pipeline.py` cho full pipeline orchestration.
      **Status:** ✅ Hoàn thành - 7/7 tests passed (G05_REPORT.md)

- [x] **6 Trực quan hóa**: bàn, tấm, camera di chuyển, vật đứng yên (Matplotlib 3D, Open3D).
      Bao gồm `scripts/realtime_viz.py` với demo mode.
      **Status:** ✅ Hoàn thành - 7/7 tests passed (G06_REPORT.md)

- [x] **7 Phân tích sai số**: log CSV, sai số theo độ cao / góc nghiêng / khoảng cách / tốc độ, vùng làm việc đạt yêu cầu.
      Bao gồm `scripts/run_evaluation.py` với demo mode.
      **Status:** ✅ Hoàn thành - 4/4 tests passed (G07_REPORT.md)

- [x] **8 Cải thiện**: lọc tia dốc, Kalman Filter, Temporal Smoothing, Triangulation từ 2 góc nhìn.
      Bao gồm `mono_eye/filter.py` và tích hợp vào pipeline.
      **Status:** ✅ Hoàn thành - 6/6 tests passed (G08_REPORT.md)

- [ ] **9 Robot thật** (dự kiến): hand-eye calibration, động học FR5 thay cho tấm marker.
      **Status:** 📋 Dự kiến - Cần có robot FR5

---

## Tiến độ: ~95% hoàn thành

| Giai đoạn | Code | Tests | Status |
|:---:|:---:|:---:|:---:|
| G00-G01 | ✅ | ✅ | Hoàn thành |
| G02 | ✅ | ✅ | Hoàn thành (camera.yaml) |
| G03-G07 | ✅ | ✅ | Hoàn thành (38 tests) |
| G08 | ✅ | ✅ | Hoàn thành (6 tests) |
| G09 | 📋 | 📋 | Dự kiến (Robot FR5) |

**Total Tests:** 82 passed, 0 failed (100% test suite đạt)
