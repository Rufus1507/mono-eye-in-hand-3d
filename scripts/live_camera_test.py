"""Kiểm tra và tương tác trực tiếp với Camera thật (Live Camera Test).

Chức năng:
- Mở luồng video trực tiếp từ webcam (1280x720).
- Nhận diện bảng ChArUco realtime và vẽ các góc quan sát được.
- Ước lượng tư thế Camera 6DoF và vẽ hệ trục tọa độ 3D (X: Đỏ, Y: Xanh lá, Z: Xanh dương) trên bảng.
- Hiển thị thông số tư thế camera (X, Y, Z, Roll, Pitch, Yaw) và FPS thời gian thực.
- Phím tắt:
    'q' / ESC: Thoát chương trình
    's': Lưu ảnh chụp hiện tại vào thư mục results/
    'c': Chuyển đổi camera index tiếp theo
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path
import cv2
import numpy as np

from mono_eye.camera_io import load_camera_yaml
from mono_eye.pose import PoseEstimator

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CALIB = ROOT / "data" / "calib" / "camera.yaml"
DEFAULT_BOARD = ROOT / "bang_calib_A4.yaml"
SNAPSHOT_DIR = ROOT / "results" / "snapshots"


def draw_hud(
    frame: np.ndarray,
    fps: float,
    valid_pose: bool,
    num_corners: int,
    cam_pos: np.ndarray | None,
    euler: tuple[float, float, float] | None,
    cam_idx: int,
    rotation: int = 90,
    mirror: bool = False,
):
    """Vẽ giao diện hiển thị thông số (HUD Overlay) lên khung hình."""
    h, w = frame.shape[:2]

    # Panel nền mờ ở góc trên-trái
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (450, 190), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)
    cv2.rectangle(frame, (10, 10), (450, 190), (0, 200, 255), 1)

    # Tiêu đề
    rot_names = {0: "0°", 90: "90° (PHẢI)", 180: "180°", 270: "270° (TRÁI)"}
    rot_str = rot_names.get(rotation, f"{rotation}°")
    cv2.putText(
        frame,
        f"MONO EYE 3D - LIVE CAM #{cam_idx} [{rot_str}]",
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )

    # FPS và Trạng thái
    status_str = "TRACKING 3D OK" if valid_pose else "SEARCHING CHARUCO..."
    status_color = (0, 255, 0) if valid_pose else (0, 165, 255)

    cv2.putText(frame, f"FPS: {fps:.1f} | Res: {w}x{h} | Mirror: {'BẬT' if mirror else 'TẮT'}", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (220, 220, 220), 1)
    cv2.putText(frame, f"ChArUco Corners: {num_corners}", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1)
    cv2.putText(frame, f"Status: {status_str}", (20, 102), cv2.FONT_HERSHEY_SIMPLEX, 0.45, status_color, 2)

    # Tọa độ 3D và góc nếu có
    if valid_pose and cam_pos is not None and euler is not None:
        cx, cy, cz = cam_pos
        roll, pitch, yaw = euler
        cv2.putText(
            frame,
            f"Cam Pos (mm): X={cx:6.1f}  Y={cy:6.1f}  Z={-cz:6.1f}",
            (20, 132),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.43,
            (100, 255, 100),
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            f"Euler (deg): R={roll:5.1f}  P={pitch:5.1f}  Y={yaw:5.1f}",
            (20, 158),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.43,
            (100, 255, 255),
            1,
            cv2.LINE_AA,
        )

    # Hướng dẫn phím tắt ở cạnh dưới
    cv2.putText(
        frame,
        "[R]: Xoay 90 | [M]: Mirror | [S]: Luu anh | [C]: Doi Cam | [Q]: Thoat",
        (20, h - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (0, 255, 255),
        1,
        cv2.LINE_AA,
    )


def open_live_camera(camera_index: int, width: int = 1280, height: int = 720) -> cv2.VideoCapture:
    """Mở camera với backend phù hợp nhất trên Windows."""
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(camera_index)

    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    return cap


def run_live_test(
    camera_index: int = 1,
    calib_file: str | Path = DEFAULT_CALIB,
    board_file: str | Path = DEFAULT_BOARD,
    rotation: int = 90,
    mirror: bool = False,
):
    """Vòng lặp chạy live camera test."""
    calib_path = Path(calib_file)
    if not calib_path.is_file():
        print(f"❌ Không tìm thấy file calibration: {calib_path}")
        return

    print("▶ Nạp ma trận hiệu chuẩn camera...")
    camera_model = load_camera_yaml(calib_path)

    print("▶ Khởi tạo Pose Estimator từ ChArUco...")
    estimator = PoseEstimator(camera=camera_model, board_config=board_file)

    current_cam_idx = camera_index
    cap = open_live_camera(current_cam_idx, camera_model.width, camera_model.height)

    if not cap.isOpened():
        print(f"❌ Không thể mở camera #{current_cam_idx}.")
        return

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    current_rot = rotation % 360
    current_mirror = mirror
    rot_names = {0: "0°", 90: "90° (PHẢI)", 180: "180°", 270: "270° (TRÁI)"}
    print(f"✔ Đã mở Camera #{current_cam_idx} ({actual_w}x{actual_h}). Xoay: {rot_names.get(current_rot, f'{current_rot}°')}")
    print("▶ Live Stream (Bấm [R] để xoay tiếp 90°, [M] lật gương, [Q] để thoát).")

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    window_name = "Mono Eye 3D - Live Camera Test"
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

    prev_time = time.time()
    fps = 30.0

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                print("⚠ Mất tín hiệu từ camera.")
                break

            # Xoay khung hình
            if current_rot == 90:
                frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            elif current_rot == 180:
                frame = cv2.rotate(frame, cv2.ROTATE_180)
            elif current_rot == 270:
                frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

            if current_mirror:
                frame = cv2.flip(frame, 1)

            now = time.time()
            dt = now - prev_time
            prev_time = now
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / dt)

            # Ước lượng Pose từ ChArUco
            pose = estimator.estimate(frame)

            # Nếu tìm thấy pose hợp lệ, vẽ hệ trục tọa độ 3D (độ dài 50 mm)
            cam_pos = None
            euler = None
            if pose.valid and pose.rvec is not None and pose.tvec is not None:
                cam_pos = pose.camera_center
                euler = (pose.roll_deg, pose.pitch_deg, pose.yaw_deg)
                cv2.drawFrameAxes(
                    frame,
                    camera_model.K,
                    camera_model.dist,
                    pose.rvec,
                    pose.tvec,
                    length=50.0,
                    thickness=2,
                )

            # Vẽ giao diện thông tin HUD
            draw_hud(
                frame,
                fps=fps,
                valid_pose=pose.valid,
                num_corners=pose.num_corners,
                cam_pos=cam_pos,
                euler=euler,
                cam_idx=current_cam_idx,
                rotation=current_rot,
                mirror=current_mirror,
            )

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF

            if key in (ord("q"), 27):  # 'q' hoặc ESC
                print("▶ Người dùng dừng chương trình.")
                break
            elif key in (ord("r"), ord("R")):  # Xoay 90 độ tiếp theo
                current_rot = (current_rot + 90) % 360
                print(f"🔄 Chuyển chế độ xoay: {rot_names.get(current_rot, f'{current_rot}°')}")
            elif key in (ord("m"), ord("M")):
                current_mirror = not current_mirror
                print(f"🔄 Lật gương (Mirror): {'BẬT' if current_mirror else 'TẮT'}")
            elif key == ord("s"):  # Lưu ảnh chụp
                snap_path = SNAPSHOT_DIR / f"snapshot_{int(time.time())}.png"
                cv2.imwrite(str(snap_path), frame)
                print(f"📸 Đã lưu ảnh chụp: {snap_path}")
            elif key == ord("c"):  # Chuyển camera
                current_cam_idx = (current_cam_idx + 1) % 4
                print(f"▶ Thử chuyển sang Camera #{current_cam_idx}...")
                cap.release()
                cap = open_live_camera(current_cam_idx, camera_model.width, camera_model.height)
                if not cap.isOpened():
                    current_cam_idx = 1
                    cap = open_live_camera(current_cam_idx, camera_model.width, camera_model.height)

    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("✔ Đã đóng camera và giải phóng tài nguyên.")


def main():
    parser = argparse.ArgumentParser(description="Live Camera Test cho Mono Eye 3D")
    parser.add_argument("--camera", type=int, default=1, help="Camera device index (mặc định 1)")
    parser.add_argument("--calib", default=str(DEFAULT_CALIB), help="Đường dẫn file camera.yaml")
    parser.add_argument("--board", default=str(DEFAULT_BOARD), help="Đường dẫn file bang_calib_A4.yaml")
    parser.add_argument("--rotation", type=int, choices=(0, 90, 180, 270), default=None,
                        help="Góc xoay (0, 90, 180, 270). Mặc định đọc configs/mono3d.yaml hoặc 90")
    parser.add_argument("--mirror", action="store_true", help="Bật lật gương (mặc định tắt)")
    args = parser.parse_args()

    rot = args.rotation
    if rot is None:
        cfg_path = ROOT / "configs" / "mono3d.yaml"
        if cfg_path.exists():
            try:
                import yaml
                with open(cfg_path, "r", encoding="utf-8") as f:
                    c = yaml.safe_load(f)
                rot = int(c.get("camera", {}).get("rotation", 90))
            except Exception:
                rot = 90
        else:
            rot = 90

    run_live_test(
        camera_index=args.camera,
        calib_file=args.calib,
        board_file=args.board,
        rotation=rot,
        mirror=args.mirror,
    )


if __name__ == "__main__":
    main()

