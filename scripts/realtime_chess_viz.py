"""Realtime 3D Digital Twin & Visualization cho Chess 3D Localization Pipeline.

Hiển thị song song trên một màn hình Dashboard duy nhất:
- Nửa bên trái: Luồng Camera 2D thực tế với phát hiện quân cờ YOLO và theo dõi ChArUco.
- Nửa bên phải: Không gian 3D phối cảnh (Mặt bàn Z=0, Bảng ChArUco, Camera 3D đang bay, Quỹ đạo di chuyển, Quân cờ 3D).

Phím tắt điều khiển:
- 'r' / 'R': Xoay khung hình camera 90° (0° -> 90° -> 180° -> 270°)
- 'c' / 'C': Chuyển đổi giữa Camera 1 (USB Camera) và Camera 0 (Laptop Webcam)
- 'm' / 'M': Bật / tắt lật gương (Mirror)
- 'q' / ESC: Thoát
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

import cv2
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mono_eye.chess_pipeline import ChessMonoEyePipeline
from mono_eye.viewer3d.piece_mapper import square_to_board_center_mm

# Cấu hình mặc định cho Bàn ChArUco 8x8 Khổ A2 (ô 40mm) và Video thử nghiệm
DEFAULT_CALIB = ROOT / "data" / "calib" / "camera_phone_video7.yaml"
DEFAULT_BOARD = ROOT / "configs" / "bang_charuco_8x8_o40mm.yaml"
DEFAULT_MODEL = ROOT / "data" / "models" / "best.pt"

try:
    from mono_eye.viewer3d.live_view import Live3DView
    HAVE_VIEWER3D = True
except Exception:
    HAVE_VIEWER3D = False


def render_3d_viewport_chess(
    camera_pos: np.ndarray | None,
    camera_rvec: np.ndarray | None,
    trajectory: list[np.ndarray],
    chess_pieces: list[dict] | None = None,
    width: int = 640,
    height: int = 480,
    board_w_mm: float = 235.63,
    board_h_mm: float = 149.94,
) -> np.ndarray:
    """Tạo khung nhìn phối cảnh 3D thời gian thực hiển thị bàn cờ và quân cờ 3D."""
    canvas = np.full((height, width, 3), 22, dtype=np.uint8)

    # Vị trí camera ảo quan sát toàn cảnh từ trên cao
    cam_eye = np.array([120.0, -420.0, 480.0], dtype=np.float64)
    target = np.array([120.0, 80.0, 0.0], dtype=np.float64)
    up = np.array([0.0, 0.0, 1.0], dtype=np.float64)

    # Tính Extrinsics ma trận quay
    z_axis = target - cam_eye
    z_axis = z_axis / np.linalg.norm(z_axis)
    x_axis = np.cross(z_axis, up)
    x_axis = x_axis / np.linalg.norm(x_axis)
    y_axis = np.cross(z_axis, x_axis)

    R_view = np.vstack([x_axis, y_axis, z_axis])
    t_view = -R_view @ cam_eye
    rvec_view, _ = cv2.Rodrigues(R_view)

    K_view = np.array([
        [480.0, 0.0, width / 2.0],
        [0.0, 480.0, height / 2.0],
        [0.0, 0.0, 1.0],
    ], dtype=np.float64)
    dist_view = np.zeros(5, dtype=np.float64)

    def proj(pts_3d: np.ndarray) -> np.ndarray:
        pts = np.asarray(pts_3d, dtype=np.float64).reshape(-1, 3)
        proj_pts, _ = cv2.projectPoints(pts, rvec_view, t_view, K_view, dist_view)
        return proj_pts.reshape(-1, 2)

    # 1. Vẽ lưới mặt bàn Z = 0 (Grid Lines)
    grid_range_x = np.arange(-200, 450, 50)
    grid_range_y = np.arange(-150, 350, 50)
    for x in grid_range_x:
        line_pts = np.array([[x, -150.0, 0.0], [x, 300.0, 0.0]])
        p = proj(line_pts)
        cv2.line(canvas, tuple(p[0].astype(int)), tuple(p[1].astype(int)), (40, 40, 40), 1, cv2.LINE_AA)
    for y in grid_range_y:
        line_pts = np.array([[-200.0, y, 0.0], [400.0, y, 0.0]])
        p = proj(line_pts)
        cv2.line(canvas, tuple(p[0].astype(int)), tuple(p[1].astype(int)), (40, 40, 40), 1, cv2.LINE_AA)

    # 2. Vẽ bảng ChArUco A4 tại gốc tọa độ (0, 0) đến (board_w, board_h) mm
    board_3d = np.array([
        [0.0, 0.0, 0.0],
        [board_w_mm, 0.0, 0.0],
        [board_w_mm, board_h_mm, 0.0],
        [0.0, board_h_mm, 0.0],
    ])
    bp = proj(board_3d).astype(np.int32)
    # Tô nền bảng ChArUco
    cv2.fillPoly(canvas, [bp], color=(35, 45, 55), lineType=cv2.LINE_AA)
    cv2.polylines(canvas, [bp], isClosed=True, color=(0, 165, 255), thickness=2, lineType=cv2.LINE_AA)

    # Vẽ các ô vuông ChArUco nhỏ bên trong
    sq_size = 21.421
    for i in range(1, 11):
        line_x = np.array([[i * sq_size, 0.0, 0.0], [i * sq_size, board_h_mm, 0.0]])
        p = proj(line_x)
        cv2.line(canvas, tuple(p[0].astype(int)), tuple(p[1].astype(int)), (60, 70, 80), 1, cv2.LINE_AA)
    for j in range(1, 7):
        line_y = np.array([[0.0, j * sq_size, 0.0], [board_w_mm, j * sq_size, 0.0]])
        p = proj(line_y)
        cv2.line(canvas, tuple(p[0].astype(int)), tuple(p[1].astype(int)), (60, 70, 80), 1, cv2.LINE_AA)

    # 3. Vẽ hệ trục tọa độ thế giới (World Frame) tại gốc (0, 0, 0)
    origin_3d = np.array([[0.0, 0.0, 0.0], [70.0, 0.0, 0.0], [0.0, 70.0, 0.0], [0.0, 0.0, 70.0]])
    op = proj(origin_3d).astype(int)
    cv2.line(canvas, tuple(op[0]), tuple(op[1]), (0, 0, 255), 2, cv2.LINE_AA)    # X: Đỏ
    cv2.line(canvas, tuple(op[0]), tuple(op[2]), (0, 255, 0), 2, cv2.LINE_AA)    # Y: Xanh lá
    cv2.line(canvas, tuple(op[0]), tuple(op[3]), (255, 120, 0), 2, cv2.LINE_AA)  # Z: Xanh dương
    cv2.putText(canvas, "+X", tuple(op[1] + [5, 0]), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
    cv2.putText(canvas, "+Y", tuple(op[2] + [0, 10]), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

    # Chuyển đổi từ hệ bảng (Z đâm vào bàn) sang hệ Bàn làm việc (Z hướng lên trời)
    def to_table(p_arr: np.ndarray) -> np.ndarray:
        out = np.asarray(p_arr, dtype=np.float64).copy()
        if out.ndim == 1:
            out[2] = -out[2]
        else:
            out[:, 2] = -out[:, 2]
        return out

    # 4. Vẽ quỹ đạo di chuyển của Camera (Trajectory)
    if len(trajectory) >= 2:
        t_pts_raw = np.array(trajectory[-40:])
        t_pts = to_table(t_pts_raw)
        tp = proj(t_pts).astype(int)
        for i in range(len(tp) - 1):
            alpha_frac = (i + 1) / len(tp)
            c_val = int(80 + 175 * alpha_frac)
            cv2.line(canvas, tuple(tp[i]), tuple(tp[i + 1]), (c_val, 40, c_val), 2, cv2.LINE_AA)

    # 5. Vẽ Camera 3D tại vị trí thực tế
    if camera_pos is not None:
        cam_pos_table = to_table(camera_pos)
        c_pt = proj(cam_pos_table)[0].astype(int)

        # Bóng camera chiếu vuông góc xuống mặt bàn Z = 0
        shadow_pos = np.array([cam_pos_table[0], cam_pos_table[1], 0.0])
        sp_pt = proj(shadow_pos)[0].astype(int)
        cv2.line(canvas, tuple(c_pt), tuple(sp_pt), (80, 80, 80), 1, cv2.LINE_AA)
        cv2.circle(canvas, tuple(sp_pt), 4, (80, 80, 80), -1, cv2.LINE_AA)

        cam_r_mat = np.eye(3)
        if camera_rvec is not None:
            cam_r_mat, _ = cv2.Rodrigues(camera_rvec)

        s = 35.0
        local_frustum = np.array([
            [-s * 1.2, -s * 0.8, s * 1.5],
            [s * 1.2, -s * 0.8, s * 1.5],
            [s * 1.2, s * 0.8, s * 1.5],
            [-s * 1.2, s * 0.8, s * 1.5],
        ])
        v_frustum_board = (cam_r_mat.T @ local_frustum.T).T
        v_frustum_table = to_table(v_frustum_board)
        world_frustum = cam_pos_table + v_frustum_table
        f_pts = proj(world_frustum).astype(int)

        for fp in f_pts:
            cv2.line(canvas, tuple(c_pt), tuple(fp), (0, 80, 255), 1, cv2.LINE_AA)
        for i in range(4):
            cv2.line(canvas, tuple(f_pts[i]), tuple(f_pts[(i + 1) % 4]), (0, 0, 255), 2, cv2.LINE_AA)
        cv2.circle(canvas, tuple(c_pt), 5, (0, 255, 255), -1, cv2.LINE_AA)

        # Trục tọa độ camera
        cam_axes_local = np.array([[30.0, 0, 0], [0, 30.0, 0], [0, 0, 40.0]])
        v_axes_board = (cam_r_mat.T @ cam_axes_local.T).T
        v_axes_table = to_table(v_axes_board)
        cam_axes_world = cam_pos_table + v_axes_table
        ax_pts = proj(cam_axes_world).astype(int)
        cv2.line(canvas, tuple(c_pt), tuple(ax_pts[0]), (0, 0, 255), 2, cv2.LINE_AA)
        cv2.line(canvas, tuple(c_pt), tuple(ax_pts[1]), (0, 255, 0), 2, cv2.LINE_AA)
        cv2.line(canvas, tuple(c_pt), tuple(ax_pts[2]), (255, 200, 0), 2, cv2.LINE_AA)

        h_mm = cam_pos_table[2]
        cv2.putText(
            canvas,
            f"Cam: ({cam_pos_table[0]:.0f}, {cam_pos_table[1]:.0f}, Cao={h_mm:.0f}) mm",
            (max(10, c_pt[0] - 60), max(20, c_pt[1] - 12)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.40,
            (0, 255, 255),
            1,
            cv2.LINE_AA,
        )

    # 6. Vẽ các quân cờ 3D trên mặt bàn (Chess Pieces) - snap 100% vào tâm ô cờ
    if chess_pieces:
        for p in chess_pieces:
            sq = p.get("square")
            pos_3d = p.get("position_3d")
            sq_center = square_to_board_center_mm(sq) if sq else None
            if sq_center is not None:
                px, py = sq_center
            elif pos_3d is not None:
                px, py = float(pos_3d[0]), float(pos_3d[1])
            else:
                continue

            base_pt = np.array([px, py, 0.0], dtype=np.float64)
            c_name = str(p.get("class_name", "")).lower()
            is_white = c_name.startswith("white")
            fen_char = p.get("fen_char", "?")
            
            if "king" in c_name or "queen" in c_name:
                p_height = 50.0
            elif "bishop" in c_name or "knight" in c_name:
                p_height = 42.0
            elif "rook" in c_name:
                p_height = 36.0
            else:
                p_height = 28.0

            top_pt = np.array([px, py, p_height], dtype=np.float64)

            b_2d = proj(base_pt)[0].astype(int)
            t_2d = proj(top_pt)[0].astype(int)

            # Màu sắc: Trắng (Cyan/Vàng nhạt), Đen (Đỏ/Tím đậm)
            piece_col = (255, 230, 80) if is_white else (60, 60, 240)
            edge_col = (200, 180, 40) if is_white else (30, 30, 180)

            # Vẽ thân trụ 3D của quân cờ
            cv2.line(canvas, tuple(b_2d), tuple(t_2d), piece_col, 3, cv2.LINE_AA)

            # Vẽ đế và đỉnh quân cờ
            cv2.circle(canvas, tuple(b_2d), 7, edge_col, -1, cv2.LINE_AA)
            cv2.circle(canvas, tuple(b_2d), 9, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.circle(canvas, tuple(t_2d), 6, piece_col, -1, cv2.LINE_AA)

            # Chú thích FEN và tọa độ
            label = f"{fen_char}: ({px:.0f}, {py:.0f})"
            cv2.putText(
                canvas,
                label,
                (t_2d[0] + 8, t_2d[1] - 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

    # Header cho Viewport 3D
    cv2.putText(
        canvas,
        "3D DIGITAL TWIN - CHESS LOCALIZATION",
        (15, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (0, 200, 255),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        "Red: +X | Green: +Y | Blue: +Z | Cyan: White | Red: Black",
        (15, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.36,
        (160, 160, 160),
        1,
        cv2.LINE_AA,
    )
    return canvas


def get_available_videos() -> list[tuple[str, Path]]:
    """Lấy danh sách các video kiểm thử cờ vua có sẵn trong thư mục videochess."""
    vdir = ROOT / "videochess"
    if not vdir.is_dir():
        return []
    videos = sorted(list(vdir.glob("*.mp4")))
    result = []
    for v in videos:
        name = v.name.lower()
        if "video8" in name:
            label = "Video 8: Ban Co ChArUco 8x8 A2 (video8.mp4)"
        elif "video7" in name:
            label = "Video 7: Ban co A3 (video7.mp4)"
        elif "video6" in name:
            label = "Video 6: Ban co A4 (video6.mp4)"
        elif "video5" in name:
            label = "Video 5: 32 Quan day du (video5.mp4)"
        elif "340" in name:
            label = "Video 1: Quân Tượng đen (Bishop)"
        elif "349" in name:
            label = "Video 2: Quân Mã đen (Knight)"
        elif "357" in name:
            label = "Video 3: Quân Hậu đen (Queen)"
        elif "365" in name:
            label = "Video 4: Quân Tốt đen (Pawn)"
        else:
            label = f"Video: {name[:24]}"
        result.append((label, v))
    return result


def prompt_input_source(videos: list[tuple[str, Path]]) -> int | str:
    """Hiển thị menu tương tác trên terminal cho phép người dùng chọn Camera hoặc Video."""
    print("\n" + "=" * 70)
    print("🎬 CHỌN NGUỒN ĐẦU VÀO CHO REALTIME CHESS 3D VISUALIZATION:")
    print("=" * 70)
    print("  [1] 📹 Camera trực tiếp #1 (DV20 USB Camera)")
    print("  [2] 💻 Camera trực tiếp #0 (Webcam Laptop)")

    idx_map: dict[str, int | str] = {"1": 1, "2": 0}
    opt = 3
    for label, vpath in videos:
        print(f"  [{opt}] ♟️  {label}")
        idx_map[str(opt)] = str(vpath)
        opt += 1

    custom_opt = opt
    print(f"  [{custom_opt}] 📂 Nhập đường dẫn file video tùy ý (.mp4)")
    print("-" * 70)
    print(f"👉 Nhập lựa chọn [1 - {custom_opt}] (Hoặc nhấn Enter để chọn Camera #1): ", end="", flush=True)

    try:
        choice = input().strip()
    except (EOFError, KeyboardInterrupt):
        print("\n▶ Mặc định chọn Camera #1.")
        return 1

    if not choice or choice == "1":
        return 1
    elif choice == "2":
        return 0
    elif choice in idx_map:
        return idx_map[choice]
    elif choice == str(custom_opt):
        print("👉 Nhập đường dẫn file video: ", end="", flush=True)
        try:
            custom_p = input().strip()
        except (EOFError, KeyboardInterrupt):
            return 1
        if Path(custom_p).is_file():
            return custom_p
        alt = ROOT / custom_p
        if alt.is_file():
            return str(alt)
        print(f"⚠ Không tìm thấy file: {custom_p}. Chuyển về mặc định Camera #1.")
        return 1
    else:
        if Path(choice).is_file():
            return choice
        try:
            return int(choice)
        except ValueError:
            print("⚠ Lựa chọn không hợp lệ. Mặc định chọn Camera #1.")
            return 1


def run_live(
    pipeline: ChessMonoEyePipeline,
    source: int | str | Path = 1,
    rotation: int = 0,
    mirror: bool = False,
    loop: bool = True,
    use_3d_pbr: bool = True,
    three_d_mode: str = "orbit",
    view_width: int = 800,
    view_height: int = 600,
):
    """Chạy vòng lặp thời gian thực từ Camera hoặc file Video và hiển thị song song 2D + 3D."""
    current_rot = rotation % 360
    current_mirror = mirror
    rot_names = {0: "0°", 90: "90° (PHẢI)", 180: "180°", 270: "270° (TRÁI)"}

    available_videos = get_available_videos()

    def open_stream(src):
        is_vid = False
        vid_p = None
        label = ""
        if isinstance(src, (str, Path)):
            p = Path(src)
            if not p.is_file():
                alt = ROOT / src
                if alt.is_file():
                    p = alt
            if p.is_file():
                is_vid = True
                vid_p = p
                matched_label = next((l for l, vp in available_videos if vp.resolve() == p.resolve()), None)
                label = matched_label or f"Video: {p.name[:24]}"
            else:
                try:
                    src = int(src)
                except ValueError:
                    pass

        if is_vid:
            c = cv2.VideoCapture(str(vid_p))
            if not c.isOpened():
                return None, False, None, label
            return c, True, vid_p, label
        else:
            cam_idx = int(src)
            label = f"Camera #{cam_idx} ({'DV20 USB' if cam_idx == 1 else 'Webcam Laptop'})"
            c = cv2.VideoCapture(cam_idx)
            if not c.isOpened():
                c = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)
            if not c.isOpened():
                return None, False, None, label
            c.set(cv2.CAP_PROP_FRAME_WIDTH, pipeline.camera.width)
            c.set(cv2.CAP_PROP_FRAME_HEIGHT, pipeline.camera.height)
            return c, False, None, label

    cap, is_video, video_path, current_label = open_stream(source)
    if cap is None:
        print(f"❌ Không thể mở nguồn phát ban đầu: {source}.")
        if source == 1:
            print("🔄 Đang thử kết nối Camera #0...")
            source = 0
            cap, is_video, video_path, current_label = open_stream(source)
        if cap is None:
            print("❌ Không thể mở bất kỳ nguồn phát nào.")
            return

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) if is_video else 0
    video_fps = cap.get(cv2.CAP_PROP_FPS) if is_video else 30.0
    if video_fps <= 0 or np.isnan(video_fps):
        video_fps = 30.0

    trajectory: list[np.ndarray] = []
    window_name = "CHESS MONO EYE 3D - DIGITAL TWIN (Trai: Camera 2D | Phai: Khong gian 3D)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, view_width * 2, view_height)

    print("=" * 70)
    print("🖥 ĐANG HIỂN THỊ CỬA SỔ DUY NHẤT: BÊN TRÁI LÀ CAMERA, BÊN PHẢI LÀ KHÔNG GIAN 3D")
    print(f"📐 Kích thước hiển thị: {view_width * 2}x{view_height} (Mỗi nửa {view_width}x{view_height}, có thể kéo dãn cửa sổ tùy ý)")
    print("▶ Phím tắt chuyển đổi nguồn phát & điều khiển:")
    print("  - [1] - [8]: Chuyển trực tiếp sang Video 1 - Video 8")
    print("  - [C]: Chuyển sang Camera trực tiếp (toggle Camera 1 <-> 0)")
    print("  - [V]: Chuyển sang Video tiếp theo trong danh sách")
    print("  - [SPACE]: Tạm dừng / Tiếp tục phát video")
    print("  - [R]: Phát lại video từ đầu / Đổi góc xoay camera")
    print("  - [M]: Bật / tắt chế độ lật gương (Mirror)")
    print("  - [Q] hoặc [ESC]: Thoát chương trình")
    print("=" * 70)

    # Khởi tạo 3D PBR Viewport nếu khả dụng
    live3d = None
    if use_3d_pbr and HAVE_VIEWER3D:
        try:
            live3d = Live3DView(width=view_width, height=view_height, default_mode=three_d_mode)
            print(f"[RealtimeViz] Da khoi tao ModernGL 3D PBR Viewport ({view_width}x{view_height}) thanh cong!")
        except Exception as e:
            print(f"[RealtimeViz] Khong the khoi tao ModernGL 3D ({e}), dung fallback 2.5D wireframe.")
            live3d = None

    def on_mouse_event(event, x, y, flags, param):
        if live3d is not None and x >= view_width:
            # Tọa độ cục bộ của nửa khung hình 3D bên phải
            live3d.handle_mouse(event, x - view_width, y, flags)

    cv2.setMouseCallback(window_name, on_mouse_event)

    prev_time = time.time()
    failed_count = 0
    paused = False
    last_frame = None
    osd_msg = f"ĐANG CHẠY: {current_label}"
    osd_expire = time.time() + 2.5

    try:
        while True:
            if not paused:
                ret, frame = cap.read()
                if not ret or frame is None:
                    if is_video:
                        if loop:
                            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            trajectory.clear()
                            continue
                        else:
                            print("🎬 Đã phát hết video.")
                            break
                    else:
                        failed_count += 1
                        if failed_count > 30:
                            print("❌ Mất tín hiệu từ camera.")
                            break
                        time.sleep(0.01)
                        continue
                failed_count = 0
                last_frame = frame.copy()
            else:
                if last_frame is None:
                    time.sleep(0.05)
                    continue
                frame = last_frame.copy()

            # Tính FPS
            now = time.time()
            fps = 1.0 / max(1e-5, now - prev_time)
            prev_time = now

            if current_rot == 90:
                frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            elif current_rot == 180:
                frame = cv2.rotate(frame, cv2.ROTATE_180)
            elif current_rot == 270:
                frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

            if current_mirror:
                frame = cv2.flip(frame, 1)

            # Xử lý toàn bộ khung hình qua ChessMonoEyePipeline
            result = pipeline.process_frame(frame)
            vis_2d = pipeline.visualize(frame, result)

            cam_center = None
            cam_rvec = None
            if result.pose.valid:
                cam_center = result.pose.camera_center
                cam_rvec = result.pose.rvec
                trajectory.append(cam_center)

            # Tạo khung nhìn phối cảnh 3D thời gian thực (view_width x view_height)
            if live3d is not None:
                view_3d = live3d.update(
                    chess_result=result,
                    camera_matrix=pipeline.camera.K,
                    image_size=(pipeline.camera.width, pipeline.camera.height),
                )
            else:
                view_3d = render_3d_viewport_chess(
                    camera_pos=cam_center,
                    camera_rvec=cam_rvec,
                    trajectory=trajectory,
                    chess_pieces=result.pieces,
                    width=view_width,
                    height=view_height,
                )

            # Chuẩn bị khung 2D camera (resize sang view_width x view_height để khớp chiều cao)
            cam_view = cv2.resize(vis_2d, (view_width, view_height))

            # 1. Header Bar trên 2D Camera View (Hiệu ứng kính mờ tối sang trọng)
            overlay = cam_view.copy()
            cv2.rectangle(overlay, (0, 0), (view_width, 42), (18, 18, 18), -1)
            cv2.addWeighted(overlay, 0.75, cam_view, 0.25, 0, cam_view)

            # Badge nguồn phát
            if is_video:
                cur_f = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
                badge_text = "▶ VIDEO"
                cv2.putText(cam_view, badge_text, (12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (255, 200, 0), 2, cv2.LINE_AA)
                cv2.putText(cam_view, f"{current_label} [{cur_f}/{total_frames}]", (90, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (240, 240, 240), 1, cv2.LINE_AA)
            else:
                dot_color = (0, 255, 120) if (int(now * 2) % 2 == 0) else (0, 200, 80)
                cv2.circle(cam_view, (20, 22), 5, dot_color, -1, cv2.LINE_AA)
                cv2.putText(cam_view, "LIVE CAMERA", (32, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 255, 120), 2, cv2.LINE_AA)
                cv2.putText(cam_view, f"[{current_label}]", (145, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (220, 220, 220), 1, cv2.LINE_AA)

            # FPS và Device bên phải Header
            dev_str = "CUDA" if "cuda" in str(pipeline.detector.device).lower() else "CPU"
            cv2.putText(cam_view, f"{fps:.1f} FPS | {dev_str}", (view_width - 130, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (0, 230, 255), 1, cv2.LINE_AA)

            # 2. Sub-header Status Pill (Báo trạng thái bám vết ChArUco & nhận diện quân cờ)
            if result.pose.valid:
                cv2.rectangle(cam_view, (10, 48), (view_width - 10, 74), (20, 45, 20), -1)
                cv2.rectangle(cam_view, (10, 48), (view_width - 10, 74), (0, 220, 100), 1)
                st_msg = f"✓ CHARUCO OK ({result.pose.num_corners} pts | err={result.pose.reproj_error_px:.1f}px) | Quan co 3D: {len(result.valid_pieces)}/{result.num_pieces}"
                cv2.putText(cam_view, st_msg, (18, 66), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 255, 120), 1, cv2.LINE_AA)
            else:
                cv2.rectangle(cam_view, (10, 48), (view_width - 10, 74), (20, 25, 45), -1)
                cv2.rectangle(cam_view, (10, 48), (view_width - 10, 74), (0, 140, 255), 1)
                st_msg = "⚠ TIM KIEM BAN CO CHARUCO A4... (Vui long dua ban co vao khung hinh)"
                cv2.putText(cam_view, st_msg, (18, 66), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 165, 255), 1, cv2.LINE_AA)

            # 3. Video Progress Bar (Nếu đang phát video)
            if is_video and total_frames > 0:
                prog_w = int(view_width * cur_f / max(1, total_frames))
                cv2.rectangle(cam_view, (0, view_height - 38), (view_width, view_height - 34), (40, 40, 40), -1)
                cv2.rectangle(cam_view, (0, view_height - 38), (prog_w, view_height - 34), (255, 215, 0), -1)

            # 4. Footer Toolbar Overlay
            overlay_bot = cam_view.copy()
            cv2.rectangle(overlay_bot, (0, view_height - 32), (view_width, view_height), (18, 18, 18), -1)
            cv2.addWeighted(overlay_bot, 0.80, cam_view, 0.20, 0, cam_view)

            if is_video:
                foot_ctl = "[1-8]: Video | [C]: Cam | [V]: Tiep | [Space]: Dung | [R]: Phat lai | [O]: 3D Cam | [Q]: Thoat"
            else:
                foot_ctl = f"[C]: Cam | [1-8]: Video | [R]: Xoay ({rot_names.get(current_rot, f'{current_rot}')}) | [M]: Mirror | [O]: 3D Cam | [Q]: Thoat"
            cv2.putText(cam_view, foot_ctl, (12, view_height - 11), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (220, 220, 220), 1, cv2.LINE_AA)

            # 5. OSD Popup Banner (Hiển thị khi chuyển nguồn hoặc thao tác phím)
            if time.time() < osd_expire and osd_msg:
                box_w, box_h = 460, 44
                bx1, by1 = (view_width - box_w) // 2, (view_height - box_h) // 2
                overlay_osd = cam_view.copy()
                cv2.rectangle(overlay_osd, (bx1, by1), (bx1 + box_w, by1 + box_h), (20, 20, 20), -1)
                cv2.addWeighted(overlay_osd, 0.85, cam_view, 0.15, 0, cam_view)
                cv2.rectangle(cam_view, (bx1, by1), (bx1 + box_w, by1 + box_h), (0, 230, 255), 2)
                (tw, th), _ = cv2.getTextSize(osd_msg, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 1)
                tx = bx1 + (box_w - tw) // 2
                ty = by1 + (box_h + th) // 2
                cv2.putText(cam_view, osd_msg, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 255, 255), 1, cv2.LINE_AA)

            # Ghép đôi 2D Camera và 3D Space cạnh nhau thành 1 Dashboard duy nhất (1280 x 480)
            dashboard = np.hstack([cam_view, view_3d])

            cv2.imshow(window_name, dashboard)
            wait_delay = 30 if paused else max(1, int(1000 / video_fps)) if is_video else 1
            key = cv2.waitKey(wait_delay) & 0xFF

            if key in (ord("q"), ord("Q"), 27):
                break
            elif key == ord(" "):
                paused = not paused
                osd_msg = "TẠM DỪNG VIDEO" if paused else "TIẾP TỤC PHÁT"
                osd_expire = time.time() + 1.5
            elif key in (ord("r"), ord("R")):
                if is_video:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    trajectory.clear()
                    if live3d is not None:
                        live3d.reset_stabilizer()
                    osd_msg = "PHÁT LẠI VIDEO TỪ ĐẦU"
                    osd_expire = time.time() + 1.5
                    print("🔄 Phát lại video từ đầu...")
                else:
                    current_rot = (current_rot + 90) % 360
                    osd_msg = f"ĐỔI GÓC XOAY: {rot_names.get(current_rot, f'{current_rot}°')}"
                    osd_expire = time.time() + 1.5
                    print(f"🔄 Đổi góc xoay: {rot_names.get(current_rot, f'{current_rot}°')}")
            elif key in (ord("m"), ord("M")):
                current_mirror = not current_mirror
                osd_msg = f"MIRROR: {'BẬT' if current_mirror else 'TẮT'}"
                osd_expire = time.time() + 1.5
                print(f"🔄 Mirror: {'BẬT' if current_mirror else 'TẮT'}")
            elif key in (ord("c"), ord("C")):
                # Chuyển đổi giữa Camera 1 và Camera 0
                next_cam = 0 if (not is_video and source == 1) else 1
                new_cap, new_is_vid, new_vid_p, new_lbl = open_stream(next_cam)
                if new_cap is not None:
                    cap.release()
                    cap, is_video, video_path, current_label = new_cap, new_is_vid, new_vid_p, new_lbl
                    source = next_cam
                    trajectory.clear()
                    if live3d is not None:
                        live3d.reset_stabilizer()
                    paused = False
                    total_frames = 0
                    video_fps = 30.0
                    osd_msg = f"ĐÃ CHUYỂN: {current_label}"
                    osd_expire = time.time() + 2.5
                    print(f"🔄 Đã chuyển sang: {current_label}")
                else:
                    osd_msg = f"LỖI: Không thể mở Camera #{next_cam}"
                    osd_expire = time.time() + 2.0
                    print(f"❌ Không thể mở Camera #{next_cam}")
            elif key in (ord("v"), ord("V")):
                # Chuyển vòng lặp sang video tiếp theo trong danh sách
                if available_videos:
                    cur_idx = -1
                    if is_video and video_path is not None:
                        for idx, (_, vp) in enumerate(available_videos):
                            if vp.resolve() == video_path.resolve():
                                cur_idx = idx
                                break
                    next_idx = (cur_idx + 1) % len(available_videos)
                    next_vid_path = available_videos[next_idx][1]
                    new_cap, new_is_vid, new_vid_p, new_lbl = open_stream(next_vid_path)
                    if new_cap is not None:
                        cap.release()
                        cap, is_video, video_path, current_label = new_cap, new_is_vid, new_vid_p, new_lbl
                        source = next_vid_path
                        trajectory.clear()
                        if live3d is not None:
                            live3d.reset_stabilizer()
                        paused = False
                        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                        osd_msg = f"ĐÃ CHUYỂN: {current_label}"
                        osd_expire = time.time() + 2.5
                        print(f"🔄 Đã chuyển sang: {current_label}")
            elif ord("1") <= key <= ord("8"):
                target_idx = key - ord("1")
                if target_idx < len(available_videos):
                    target_vid = available_videos[target_idx][1]
                    new_cap, new_is_vid, new_vid_p, new_lbl = open_stream(target_vid)
                    if new_cap is not None:
                        cap.release()
                        cap, is_video, video_path, current_label = new_cap, new_is_vid, new_vid_p, new_lbl
                        source = target_vid
                        trajectory.clear()
                        if live3d is not None:
                            live3d.reset_stabilizer()
                        paused = False
                        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                        osd_msg = f"ĐÃ CHUYỂN: {current_label}"
                        osd_expire = time.time() + 2.5
                        print(f"🔄 Đã chuyển sang: {current_label}")
            elif key in (ord("o"), ord("O")):
                if live3d is not None:
                    m = live3d.toggle_mode()
                    osd_msg = f"3D CAMERA: {m.upper()}"
                    osd_expire = time.time() + 1.5
                    print(f"🔄 Đổi chế độ 3D Camera: {m.upper()}")
            elif key in (ord("+"), ord("=")):
                if live3d is not None:
                    live3d.zoom(0.85)
            elif key in (ord("-"), ord("_")):
                if live3d is not None:
                    live3d.zoom(1.15)
            elif key == ord("0"):
                if live3d is not None:
                    live3d.reset_view()
                    osd_msg = "3D VIEW: RESET GÓC NHÌN"
                    osd_expire = time.time() + 1.5
    finally:
        if live3d is not None:
            live3d.close()
        cap.release()
        cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description="Realtime 3D Visualization cho Chess Mono Eye 3D")
    parser.add_argument("--source", default=None, help="Camera index (ví dụ: 0, 1) HOẶC đường dẫn file video (.mp4)")
    parser.add_argument("--video", default=None, help="Đường dẫn file video chạy thử nghiệm")
    parser.add_argument("--camera", type=int, default=None, help="Camera device ID (ví dụ: 0 hoặc 1)")
    parser.add_argument("--camera-config", default=str(DEFAULT_CALIB), help="Path camera calibration YAML")
    parser.add_argument("--board-config", default=str(DEFAULT_BOARD), help="Path ChArUco board YAML")
    parser.add_argument("--model", default=str(DEFAULT_MODEL), help="Path YOLO chess model (.pt)")
    parser.add_argument("--conf", type=float, default=0.45, help="Ngưỡng tin cậy YOLO (mặc định 0.45)")
    parser.add_argument("--device", default="auto", help="Inference device: 'auto', 'cuda', 'cuda:0', 'cpu'")
    parser.add_argument("--plane-z", type=float, default=0.0, help="Cao độ mặt phẳng bàn Z (mm)")
    parser.add_argument("--max-reproj", type=float, default=6.0, help="Sai số tái chiếu tối đa (px, mặc định 6.0)")
    parser.add_argument("--rotation", type=int, choices=(0, 90, 180, 270), default=None,
                        help="Góc xoay (0, 90, 180, 270). Mặc định đọc configs/mono3d.yaml hoặc 0")
    parser.add_argument("--mirror", action="store_true", help="Bật lật gương (mặc định tắt)")
    parser.add_argument("--loop", action="store_true", default=True, help="Tự động lặp lại video khi hết (mặc định bật)")
    parser.add_argument("--no-loop", dest="loop", action="store_false", help="Không lặp lại video")
    parser.add_argument("--menu", action="store_true", help="Luôn hiển thị menu tương tác chọn nguồn đầu vào")
    parser.add_argument("--3d-mode", dest="three_d_mode", choices=("orbit", "virtual"), default="orbit",
                        help="Che do camera 3D: 'orbit' (xoay tu do) hoac 'virtual' (theo camera thuc)")
    parser.add_argument("--no-3d", dest="no_3d", action="store_true", help="Tat renderer ModernGL 3D, dung legacy wireframe")
    parser.add_argument("--preset", default=None, choices=("video8",), help="Preset cau hinh nhanh, vi du: 'video8'")
    parser.add_argument("--view-width", type=int, default=800, help="Chieu rong moi nua khung nhin (mac dinh 800 -> tong dashboard 1600)")
    parser.add_argument("--view-height", type=int, default=600, help="Chieu cao khung nhin (mac dinh 600)")
    args = parser.parse_args()

    if args.preset == "video8":
        args.video = "videochess/video8.mp4"
        args.board_config = "configs/bang_charuco_8x8_o40mm.yaml"
        args.camera_config = "data/calib/camera_phone_video7.yaml" 

    cam_cfg = Path(args.camera_config)
    if not cam_cfg.is_file():
        alt_cam = ROOT / args.camera_config
        if alt_cam.is_file():
            cam_cfg = alt_cam

    board_cfg = Path(args.board_config)
    if not board_cfg.is_file():
        alt_board = ROOT / args.board_config
        if alt_board.is_file():
            board_cfg = alt_board

    model_path = Path(args.model)
    if not model_path.is_file():
        alt_model = ROOT / args.model
        if alt_model.is_file():
            model_path = alt_model

    rot = args.rotation
    if rot is None:
        cfg_path = ROOT / "configs" / "mono3d.yaml"
        if cfg_path.is_file():
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    c = yaml.safe_load(f)
                rot = int(c.get("camera", {}).get("rotation", 0))
            except Exception:
                rot = 0
        else:
            rot = 0

    if not cam_cfg.is_file():
        print(f"❌ Thiếu file cấu hình camera: {cam_cfg}")
        return 1

    if not board_cfg.is_file():
        print(f"❌ Thiếu file cấu hình bảng ChArUco: {board_cfg}")
        return 1

    # Tìm danh sách video có sẵn
    available_videos = get_available_videos()

    # Xác định nguồn phát (source/video/camera hoặc hiển thị menu tương tác)
    source_input = args.source or args.video
    if source_input is None and args.camera is not None:
        source_input = args.camera

    if source_input is None or args.menu:
        # Hiển thị menu cho phép chọn trực tiếp Camera hoặc Video
        source_input = prompt_input_source(available_videos)

    print("=" * 70)
    print("KHỞI TẠO REALTIME CHESS 3D VISUALIZATION PIPELINE")
    print(f"Nguồn phát (Source): {source_input}")
    print(f"Camera Calibration: {cam_cfg}")
    print(f"ChArUco Board:      {board_cfg}")
    print(f"YOLO Model:         {model_path} ({'Tìm thấy' if model_path.is_file() else 'Không thấy'})")
    print(f"Device:             {args.device}")
    print(f"Confidence:         {args.conf}")
    print(f"Max Reproj Error:   {args.max_reproj} px")
    print("=" * 70)

    pipeline = ChessMonoEyePipeline(
        camera_config=cam_cfg,
        board_config=board_cfg,
        piece_model_path=model_path,
        conf_threshold=args.conf,
        plane_z=args.plane_z,
        device=args.device,
        max_reproj_error_px=args.max_reproj,
    )

    run_live(
        pipeline,
        source=source_input,
        rotation=rot,
        mirror=args.mirror,
        loop=args.loop,
        use_3d_pbr=not args.no_3d,
        three_d_mode=args.three_d_mode,
        view_width=args.view_width,
        view_height=args.view_height,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

