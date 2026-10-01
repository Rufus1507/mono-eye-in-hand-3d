# Lộ trình mono_eye

Chỉ đánh dấu một giai đoạn khi đạt tiêu chí hoàn thành. Các ngưỡng số là tạm thời.

- [x] **0 Setup**: môi trường uv, gói `mono_eye`, kiểm tra môi trường.
      Xong khi: `scripts/check_env.py` đạt, `pytest tests/test_mono_eye.py` đạt.
- [ ] **1 Chuẩn bị vật lý**: in bảng (100 %, giấy mờ), đo hai thước in ở lề giấy và điền `kiem_in.do_duoc_ngang_mm`,
      `do_duoc_doc_mm` vào file bảng, dán phẳng cố định lên bàn, đo các điểm chuẩn vào `configs/ground_truth_points.csv`.
      Xong khi: `board_scale()` trả về cạnh ô thật.
- [ ] **2 Hiệu chuẩn nội tham số** (có sẵn trong `do_fov.py`): 40 khung, nghiêng 20-45 độ, phủ bốn góc khung,
      `--bootstrap 100`, rồi `export` và copy `camera.yaml` về `data/calib/`.
      Xong khi: độ tản bootstrap nhỏ và ảnh khử méo thẳng.
- [ ] **3 Pose camera**: `mono_eye/pose.py` dùng `fov_tool.board.load_board` + `solvePnP`; lọc chất lượng; kiểm chứng trục và độ cao.
      Có thể viết và kiểm thử trước bằng dữ liệu chiếu giả lập.
- [ ] **4 Pixel sang 3D**: `mono_eye/projection.py` (giao tia với mặt bàn), kiểm trên điểm chuẩn
      (không kiểm trên các góc ChArUco đã dùng để giải pose).
- [ ] **5 YOLO**: phát hiện và tracking, điểm tham chiếu = giữa cạnh dưới bounding box.
- [ ] **6 Trực quan hóa**: bàn, tấm, camera di chuyển, vật đứng yên (Rerun).
- [ ] **7 Phân tích sai số**: log CSV, sai số theo độ cao / góc nghiêng / khoảng cách / tốc độ, vùng làm việc đạt yêu cầu.
- [ ] **8 Cải thiện**: chỉ làm phần giai đoạn 7 cho thấy cần (lọc, gộp nhiều khung, tam giác đạc hai góc nhìn).
- [ ] **9 Robot thật** (dự kiến): hand-eye calibration, động học FR5 thay cho tấm marker.
