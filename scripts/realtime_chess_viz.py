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

DEFAULT_CALIB = ROOT / "data" / "calib" / "camera.yaml"
DEFAULT_BOARD = ROOT / "bang_calib_A4.yaml"
DEFAULT_MODEL = ROOT / "data" / "models" / "best25e_2712.pt"


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

    # 6. Vẽ các quân cờ 3D trên mặt bàn (Chess Pieces)
    if chess_pieces:
        for p in chess_pieces:
            pos_3d = p.get("position_3d")
            if pos_3d is not None:
                # Tọa độ đáy quân cờ trên mặt bàn
                base_pt = np.array([float(pos_3d[0]), float(pos_3d[1]), 0.0], dtype=np.float64)
                
                # Chiều cao mô phỏng của quân cờ theo loại
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

                top_pt = np.array([float(pos_3d[0]), float(pos_3d[1]), p_height], dtype=np.float64)

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
                label = f"{fen_char}: ({pos_3d[0]:.0f}, {pos_3d[1]:.0f})"
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


def run_live(
    pipeline: ChessMonoEyePipeline,
    camera_id: int = 1,
    rotation: int = 0,
    mirror: bool = False,
):
    """Chạy vòng lặp camera thời gian thực và hiển thị song song 2D + 3D."""
    current_rot = rotation % 360
    current_mirror = mirror
    rot_names = {0: "0°", 90: "90° (PHẢI)", 180: "180°", 270: "270° (TRÁI)"}

    print(f"▶ Mở camera #{camera_id} (Xoay: {rot_names.get(current_rot, f'{current_rot}°')})...")
    cap = cv2.VideoCapture(camera_id)
    if not cap.isOpened():
        cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"❌ Không thể mở camera #{camera_id}.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, pipeline.camera.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, pipeline.camera.height)

    trajectory: list[np.ndarray] = []
    window_name = "CHESS MONO EYE 3D - DIGITAL TWIN (Trai: Camera 2D | Phai: Khong gian 3D)"
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

    print("=" * 70)
    print("🖥 ĐANG HIỂN THỊ CỬA SỔ DUY NHẤT: BÊN TRÁI LÀ CAMERA, BÊN PHẢI LÀ KHÔNG GIAN 3D")
    print("▶ Phím [R]: Xoay góc | [C]: Đổi camera | [M]: Lật gương | [Q]: Thoát")
    print("=" * 70)

    prev_time = time.time()
    failed_count = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                failed_count += 1
                if failed_count > 30:
                    print("❌ Mất tín hiệu từ camera.")
                    break
                time.sleep(0.01)
                continue
            failed_count = 0

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

            # Tạo khung nhìn phối cảnh 3D thời gian thực (640x480)
            view_3d = render_3d_viewport_chess(
                camera_pos=cam_center,
                camera_rvec=cam_rvec,
                trajectory=trajectory,
                chess_pieces=result.pieces,
                width=640,
                height=480,
            )

            # Chuẩn bị khung 2D camera (resize sang 640x480 để khớp chiều cao)
            cam_view = cv2.resize(vis_2d, (640, 480))
            status_text = f"TRACKING OK ({result.pose.num_corners} pts)" if result.pose.valid else "SEARCHING CHARUCO..."
            status_col = (0, 255, 0) if result.pose.valid else (0, 165, 255)
            cv2.putText(cam_view, f"STATUS: {status_text}", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.55, status_col, 2)
            cv2.putText(
                cam_view,
                f"FPS: {fps:.1f} | Pieces: {result.num_pieces} (3D: {len(result.valid_pieces)})",
                (15, 55),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.50,
                (255, 255, 0),
                2,
            )
            cv2.putText(
                cam_view,
                f"Rot: {rot_names.get(current_rot, f'{current_rot}°')} | [R]: Xoay | [C]: Doi Cam | [M]: Mirror | [Q]: Thoat",
                (15, 465),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.36,
                (0, 255, 255),
                1,
                cv2.LINE_AA,
            )

            # Ghép đôi 2D Camera và 3D Space cạnh nhau thành 1 Dashboard duy nhất (1280 x 480)
            dashboard = np.hstack([cam_view, view_3d])

            cv2.imshow(window_name, dashboard)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q"), 27):
                break
            elif key in (ord("r"), ord("R")):
                current_rot = (current_rot + 90) % 360
                print(f"🔄 Đổi góc xoay: {rot_names.get(current_rot, f'{current_rot}°')}")
            elif key in (ord("m"), ord("M")):
                current_mirror = not current_mirror
                print(f"🔄 Mirror: {'BẬT' if current_mirror else 'TẮT'}")
            elif key in (ord("c"), ord("C")):
                next_cam = 0 if camera_id == 1 else 1
                print(f"🔄 Chuyển sang Camera #{next_cam}...")
                cap.release()
                camera_id = next_cam
                cap = cv2.VideoCapture(camera_id)
                if not cap.isOpened():
                    cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, pipeline.camera.width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, pipeline.camera.height)
    finally:
        cap.release()
        cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description="Realtime 3D Visualization cho Chess Mono Eye 3D")
    parser.add_argument("--camera", type=int, default=1, help="Camera device ID (mặc định 1)")
    parser.add_argument("--camera-config", default=str(DEFAULT_CALIB), help="Path camera calibration YAML")
    parser.add_argument("--board-config", default=str(DEFAULT_BOARD), help="Path ChArUco board YAML")
    parser.add_argument("--model", default=str(DEFAULT_MODEL), help="Path YOLO chess model (.pt)")
    parser.add_argument("--conf", type=float, default=0.4, help="Ngưỡng tin cậy YOLO (mặc định 0.4)")
    parser.add_argument("--device", default="auto", help="Inference device: 'auto', 'cuda', 'cuda:0', 'cpu'")
    parser.add_argument("--plane-z", type=float, default=0.0, help="Cao độ mặt phẳng bàn Z (mm)")
    parser.add_argument("--rotation", type=int, choices=(0, 90, 180, 270), default=None,
                        help="Góc xoay (0, 90, 180, 270). Mặc định đọc configs/mono3d.yaml hoặc 0")
    parser.add_argument("--mirror", action="store_true", help="Bật lật gương (mặc định tắt)")
    args = parser.parse_args()

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

    print("=" * 70)
    print("KHỞI TẠO REALTIME CHESS 3D VISUALIZATION PIPELINE")
    print(f"Camera Calibration: {cam_cfg}")
    print(f"ChArUco Board:      {board_cfg}")
    print(f"YOLO Model:         {model_path} ({'Tìm thấy' if model_path.is_file() else 'Không thấy'})")
    print(f"Device:             {args.device}")
    print(f"Confidence:         {args.conf}")
    print("=" * 70)

    pipeline = ChessMonoEyePipeline(
        camera_config=cam_cfg,
        board_config=board_cfg,
        piece_model_path=model_path,
        conf_threshold=args.conf,
        plane_z=args.plane_z,
        device=args.device,
    )

    run_live(pipeline, camera_id=args.camera, rotation=rot, mirror=args.mirror)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
