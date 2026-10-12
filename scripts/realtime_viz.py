"""Realtime 3D Digital Twin & Visualization cho Mono Eye 3D pipeline.

Hiển thị song song trên một màn hình Dashboard duy nhất:
- Nửa bên trái: Luồng Camera 2D thực tế (nhận diện bảng ChArUco & vật thể).
- Nửa bên phải: Không gian 3D phối cảnh (Mặt bàn Z=0, Camera 3D đang bay, Quỹ đạo di chuyển, Vật thể 3D).

Phím tắt điều khiển:
- 'r' / 'R': Xoay khung hình camera 90° (0° -> 90° -> 180° -> 270°)
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

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mono_eye.pipeline import MonoEyePipeline
from mono_eye.viz import SimpleVisualizer



def render_3d_viewport(
    camera_pos: np.ndarray | None,
    camera_rvec: np.ndarray | None,
    trajectory: list[np.ndarray],
    detections=None,
    width: int = 640,
    height: int = 480,
) -> np.ndarray:
    """Tạo khung nhìn phối cảnh 3D thời gian thực (Perspective 3D Viewport)."""
    canvas = np.full((height, width, 3), 22, dtype=np.uint8)

    # Vị trí camera ảo quan sát toàn cảnh từ trên cao
    cam_eye = np.array([0.0, -520.0, 450.0], dtype=np.float64)
    target = np.array([0.0, 0.0, 0.0], dtype=np.float64)
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
        [460.0, 0.0, width / 2.0],
        [0.0, 460.0, height / 2.0],
        [0.0, 0.0, 1.0],
    ], dtype=np.float64)
    dist_view = np.zeros(5, dtype=np.float64)

    def proj(pts_3d: np.ndarray) -> np.ndarray:
        pts = np.asarray(pts_3d, dtype=np.float64).reshape(-1, 3)
        proj_pts, _ = cv2.projectPoints(pts, rvec_view, t_view, K_view, dist_view)
        return proj_pts.reshape(-1, 2)

    # 1. Vẽ lưới mặt bàn Z = 0 (Grid Lines)
    grid_range = np.arange(-300, 350, 50)
    for x in grid_range:
        line_pts = np.array([[x, -300.0, 0.0], [x, 300.0, 0.0]])
        p = proj(line_pts)
        cv2.line(canvas, tuple(p[0].astype(int)), tuple(p[1].astype(int)), (45, 45, 45), 1, cv2.LINE_AA)
    for y in grid_range:
        line_pts = np.array([[-300.0, y, 0.0], [300.0, y, 0.0]])
        p = proj(line_pts)
        cv2.line(canvas, tuple(p[0].astype(int)), tuple(p[1].astype(int)), (45, 45, 45), 1, cv2.LINE_AA)

    # 2. Vẽ bảng ChArUco ở gốc tọa độ (A4: 235 x 150 mm)
    board_3d = np.array([
        [-118.0, -75.0, 0.0],
        [118.0, -75.0, 0.0],
        [118.0, 75.0, 0.0],
        [-118.0, 75.0, 0.0],
    ])
    bp = proj(board_3d).astype(np.int32)
    cv2.polylines(canvas, [bp], isClosed=True, color=(0, 140, 255), thickness=2, lineType=cv2.LINE_AA)

    # 3. Vẽ hệ trục tọa độ thế giới (World Frame) tại gốc (0, 0, 0)
    origin_3d = np.array([[0.0, 0.0, 0.0], [80.0, 0.0, 0.0], [0.0, 80.0, 0.0], [0.0, 0.0, 80.0]])
    op = proj(origin_3d).astype(int)
    cv2.line(canvas, tuple(op[0]), tuple(op[1]), (0, 0, 255), 2, cv2.LINE_AA)  # X: Đỏ
    cv2.line(canvas, tuple(op[0]), tuple(op[2]), (0, 255, 0), 2, cv2.LINE_AA)  # Y: Xanh lá
    cv2.line(canvas, tuple(op[0]), tuple(op[3]), (255, 120, 0), 2, cv2.LINE_AA)  # Z: Xanh dương

    # Chuyển đổi từ hệ bảng (Z đâm vào bàn) sang hệ Bàn làm việc (Z hướng lên trời)
    def to_table(p_arr: np.ndarray) -> np.ndarray:
        out = np.asarray(p_arr, dtype=np.float64).copy()
        if out.ndim == 1:
            out[2] = -out[2]
        else:
            out[:, 2] = -out[:, 2]
        return out

    # 4. Vẽ quỹ đạo di chuyển (Trajectory)
    if len(trajectory) >= 2:
        t_pts_raw = np.array(trajectory[-40:])
        t_pts = to_table(t_pts_raw)
        tp = proj(t_pts).astype(int)
        for i in range(len(tp) - 1):
            alpha_frac = (i + 1) / len(tp)
            c_val = int(100 + 155 * alpha_frac)
            cv2.line(canvas, tuple(tp[i]), tuple(tp[i + 1]), (c_val, 50, c_val), 2, cv2.LINE_AA)

    # 5. Vẽ Camera 3D tại vị trí thực tế
    if camera_pos is not None:
        cam_pos_table = to_table(camera_pos)
        c_pt = proj(cam_pos_table)[0].astype(int)

        # Bóng trên mặt bàn Z = 0
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

        # Vẽ 3 trục tọa độ của chính camera (độ dài 35 mm)
        cam_axes_local = np.array([[35.0, 0, 0], [0, 35.0, 0], [0, 0, 45.0]])
        v_axes_board = (cam_r_mat.T @ cam_axes_local.T).T
        v_axes_table = to_table(v_axes_board)
        cam_axes_world = cam_pos_table + v_axes_table
        ax_pts = proj(cam_axes_world).astype(int)
        cv2.line(canvas, tuple(c_pt), tuple(ax_pts[0]), (0, 0, 255), 2, cv2.LINE_AA)  # Cam X: Đỏ
        cv2.line(canvas, tuple(c_pt), tuple(ax_pts[1]), (0, 255, 0), 2, cv2.LINE_AA)  # Cam Y: Xanh lá
        cv2.line(canvas, tuple(c_pt), tuple(ax_pts[2]), (255, 200, 0), 2, cv2.LINE_AA) # Cam Z: Vàng

        h_mm = cam_pos_table[2]
        cv2.putText(
            canvas,
            f"Cam: ({cam_pos_table[0]:.0f}, {cam_pos_table[1]:.0f}, Cao={h_mm:.0f}) mm",
            (max(10, c_pt[0] - 60), max(20, c_pt[1] - 12)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (0, 255, 255),
            1,
            cv2.LINE_AA,
        )

    # 6. Vẽ các vật thể phát hiện trên mặt bàn (Detections)
    if detections:
        for det in detections.detections:
            if det.position_3d is not None:
                p_3d = det.position_3d
                obj_center = proj(p_3d)[0].astype(int)
                cv2.circle(canvas, tuple(obj_center), 8, (0, 255, 0), -1, cv2.LINE_AA)
                cv2.circle(canvas, tuple(obj_center), 12, (0, 200, 0), 1, cv2.LINE_AA)
                name = det.class_name
                cv2.putText(
                    canvas,
                    f"{name} ({p_3d[0]:.0f},{p_3d[1]:.0f})",
                    (obj_center[0] + 10, obj_center[1] + 4),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.42,
                    (100, 255, 100),
                    1,
                    cv2.LINE_AA,
                )

    # Header cho Viewport 3D
    cv2.putText(
        canvas,
        "3D DIGITAL TWIN (TABLE FRAME Z=0)",
        (15, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (0, 200, 255),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        "Red: X | Green: Y | Blue: Z | Orange: ChArUco Board",
        (15, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.38,
        (160, 160, 160),
        1,
        cv2.LINE_AA,
    )
    return canvas


def run_live(
    pipeline: MonoEyePipeline,
    camera_id: int = 1,
    rotation: int = 90,
    mirror: bool = False,
):
    """Chạy trực tiếp từ nguồn camera thực."""
    current_rot = rotation % 360
    current_mirror = mirror
    rot_names = {0: "0°", 90: "90° (PHẢI)", 180: "180°", 270: "270° (TRÁI)"}
    print(f"▶ Mở camera {camera_id} (Xoay: {rot_names.get(current_rot, f'{current_rot}°')})...")
    cap = cv2.VideoCapture(camera_id)
    if not cap.isOpened():
        cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"❌ Không thể mở camera #{camera_id}.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    trajectory = []
    window_name = "MONO EYE 3D - DIGITAL TWIN (Trai: Camera 2D | Phai: Khong gian 3D)"
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

    print("=" * 70)
    print("🖥 ĐANG HIỂN THỊ CỬA SỔ DUY NHẤT: BÊN TRÁI LÀ CAMERA, BÊN PHẢI LÀ KHÔNG GIAN 3D")
    print("▶ Phím [R]: Xoay góc | [C]: Đổi camera | [M]: Lật gương | [Q]: Thoát")
    print("=" * 70)

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

            if current_rot == 90:
                frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            elif current_rot == 180:
                frame = cv2.rotate(frame, cv2.ROTATE_180)
            elif current_rot == 270:
                frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

            if current_mirror:
                frame = cv2.flip(frame, 1)

            # Xử lý frame qua pipeline
            pose, detections = pipeline.process_frame(frame, detect_objects=True)

            cam_center = None
            cam_rvec = None
            if pose.valid:
                cam_center = pose.camera_center
                cam_rvec = pose.rvec
                trajectory.append(cam_center)

            # Tạo khung nhìn 3D trực tiếp (640x480)
            view_3d = render_3d_viewport(
                camera_pos=cam_center,
                camera_rvec=cam_rvec,
                trajectory=trajectory,
                detections=detections,
                width=640,
                height=480,
            )

            # Chuẩn bị khung 2D camera (resize sang 640x480 để khớp chiều cao)
            cam_view = cv2.resize(frame, (640, 480))
            status_text = "3D TRACKING OK" if pose.valid else "SEARCHING CHARUCO..."
            status_col = (0, 255, 0) if pose.valid else (0, 165, 255)
            cv2.putText(cam_view, f"STATUS: {status_text}", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.55, status_col, 2)
            cv2.putText(
                cam_view,
                f"Rot: {rot_names.get(current_rot, f'{current_rot}°')} | [R]: Xoay | [C]: Doi Cam | [M]: Mirror | [Q]: Thoat",
                (15, 465),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                (0, 255, 255),
                1,
                cv2.LINE_AA,
            )

            # Ghép đôi 2D Camera và 3D Space cạnh nhau thành 1 Dashboard duy nhất
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
                cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
                if not cap.isOpened():
                    cap = cv2.VideoCapture(camera_id)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    finally:
        cap.release()
        cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description="Realtime 3D Visualization cho Mono Eye 3D")
    parser.add_argument("--camera", type=int, default=1, help="Camera device ID (mặc định 1)")
    parser.add_argument("--camera-config", default="data/calib/camera.yaml", help="Path camera calibration YAML")
    parser.add_argument("--board-config", default="bang_calib_A4.yaml", help="Path ChArUco board YAML")
    parser.add_argument("--rotation", type=int, choices=(0, 90, 180, 270), default=None,
                        help="Góc xoay (0, 90, 180, 270). Mặc định đọc configs/mono3d.yaml hoặc 0")
    parser.add_argument("--mirror", action="store_true", help="Bật lật gương (mặc định tắt)")
    parser.add_argument("--model", default=None, help="Đường dẫn tới weights YOLO (ví dụ data/models/best25e_2712.pt)")
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

    rot = args.rotation
    if rot is None:
        cfg_path = Path("configs/mono3d.yaml")
        if not cfg_path.is_file():
            alt_cfg = ROOT / "configs" / "mono3d.yaml"
            if alt_cfg.is_file():
                cfg_path = alt_cfg

        if cfg_path.is_file():
            try:
                import yaml
                with open(cfg_path, "r", encoding="utf-8") as f:
                    c = yaml.safe_load(f)
                rot = int(c.get("camera", {}).get("rotation", 0))
            except Exception:
                rot = 0
        else:
            rot = 0

    if not cam_cfg.exists() or not board_cfg.exists():
        print(f"❌ Thiếu file cấu hình camera ({cam_cfg}) hoặc board ({board_cfg}). Vui lòng kiểm tra lại data/calib/camera.yaml!")
        return 1

    detector_config = None
    model_path = Path(args.model) if args.model else ROOT / "data" / "models" / "best25e_2712.pt"
    if model_path.is_file():
        detector_config = {
            "model_path": str(model_path),
            "conf_threshold": 0.4,
            "tracking": False,
        }
        print(f"🤖 Đã nạp YOLO model: {model_path.name}")

    pipeline = MonoEyePipeline(
        camera_config=str(cam_cfg),
        board_config=str(board_cfg),
        detector_config=detector_config,
    )

    run_live(pipeline, camera_id=args.camera, rotation=rot, mirror=args.mirror)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
