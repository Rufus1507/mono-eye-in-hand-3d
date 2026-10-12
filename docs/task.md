Viewed GEMINI_REALTIME_VIZ_PROMPT.md:1-164
Created realtime_chess_viz.py
Created realtime_chess_viz.py
Ran command: `py -3.13 scripts/realtime_chess_viz.py --help`

Đang kiểm tra CLI parser của `realtime_chess_viz.py`...

Viewed test_chess.py:275-284
Viewed test_chess.py:280-284
Edited test_chess.py
Ran command: `py -3.13 -m pytest tests/test_chess.py -v`

Đang kiểm tra toàn bộ unit test với `realtime_chess_viz`...

Tôi đã hoàn thành toàn bộ yêu cầu trong [GEMINI_REALTIME_VIZ_PROMPT.md](file:///h:/GameProject/mono-eye-in-hand-3d/mono-eye-in-hand-3d/docs/GEMINI_REALTIME_VIZ_PROMPT.md):

---

### Các nội dung đã hoàn thành:

1. **Tạo mới [scripts/realtime_chess_viz.py](file:///h:/GameProject/mono-eye-in-hand-3d/mono-eye-in-hand-3d/scripts/realtime_chess_viz.py)** (và forwarder script tại thư mục gốc workspace):
   - Chuyển đổi từ `MonoEyePipeline` sang **`ChessMonoEyePipeline`** chuyên dụng cho cờ vua.
   - Nạp mô hình trọng số YOLO cờ vua thực tế: [data/models/best25e_2712.pt](file:///h:/GameProject/mono-eye-in-hand-3d/mono-eye-in-hand-3d/data/models/best25e_2712.pt).
   - Tối ưu hóa suy luận với GPU NVIDIA RTX 4060 thông qua tham số `--device auto` hoặc `--device cuda`.

2. **Cập nhật không gian phối cảnh 3D Digital Twin (`render_3d_viewport_chess`)**:
   - Vẽ bảng ChArUco chuẩn tại gốc tọa độ $(0, 0)$ với kích thước thực tế $235.6 \times 149.9\text{ mm}$ kèm các ô lưới.
   - Hiển thị vị trí thực của Camera 3D, bóng chiếu trên mặt bàn, trục tọa độ camera và quỹ đạo di chuyển (Trajectory).
   - **Vẽ các quân cờ 3D trong không gian**:
     - Tọa độ chân đế tiếp xúc mặt bàn $(X, Y, 0.0)\text{ mm}$.
     - Trụ 3D mô phỏng chiều cao thực tế theo từng loại quân (Vua, Hậu, Tượng, Mã, Xe, Tốt).
     - Phân biệt màu sắc theo phe: **Quân Trắng (Cyan/Vàng nhạt)** và **Quân Đen (Đỏ/Tím đậm)**.
     - Ký hiệu FEN (`N`, `P`, `R`, `Q`, `K`, `B` / `n`, `p`, `r`, `q`, `k`, `b`) và tọa độ 3D $(X, Y)$ tương ứng.

3. **Bảo toàn tính toàn vẹn hệ thống**:
   - Giữ nguyên [scripts/realtime_viz.py](file:///h:/GameProject/mono-eye-in-hand-3d/mono-eye-in-hand-3d/scripts/realtime_viz.py) gốc.
   - Bổ sung unit test `test_render_3d_viewport_chess` trong [tests/test_chess.py](file:///h:/GameProject/mono-eye-in-hand-3d/mono-eye-in-hand-3d/tests/test_chess.py) (toàn bộ **12/12 unit tests PASSED 100%**).

---

### Hướng Dẫn Chạy

Bạn mở terminal và chạy lệnh sau:

```powershell
py -3.13 scripts/realtime_chess_viz.py --camera 1 --conf 0.4 --device cuda:0
```

#### Phím tắt điều khiển trên cửa sổ:
- **`R`**: Xoay khung hình camera ($0^\circ \to 90^\circ \to 180^\circ \to 270^\circ$).
- **`C`**: Chuyển đổi giữa **Camera 1** (DV20 USB Camera) và **Camera 0** (Webcam laptop).
- **`M`**: Bật / tắt chế độ lật gương (Mirror).
- **`Q`** hoặc **`ESC`**: Thoát chương trình.