"""Chạy kiểm thử Chess Piece 3D Localization Pipeline (trên camera hoặc file ảnh)."""
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

from mono_eye.chess_pipeline import ChessMonoEyePipeline

DEFAULT_CALIB = ROOT / "data" / "calib" / "camera.yaml"
DEFAULT_BOARD = ROOT / "bang_calib_A4.yaml"
DEFAULT_MODEL = ROOT / "data" / "models" / "best25e_2712.pt"


def find_working_camera(preferred: list[int] = (1, 0, 2)) -> int:
    """Tự động tìm camera khả dụng và có hình ảnh sáng rõ (không bị màn đen)."""
    for idx in preferred:
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            for _ in range(3):
                cap.read()
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None and frame.mean() > 25:
                return idx
    return 0


def run_pipeline(
    source: int | str = "auto",
    calib_file: Path = DEFAULT_CALIB,
    board_file: Path = DEFAULT_BOARD,
    model_file: Path = DEFAULT_MODEL,
    conf_threshold: float = 0.5,
    plane_z: float = 0.0,
    device: str = "auto",
):
    print("=" * 60)
    print("Khởi tạo Chess Mono Eye 3D Localization Pipeline...")
    print(f"Calibration: {calib_file}")
    print(f"ChArUco Board: {board_file}")
    print(f"YOLO Model: {model_file}")
    print(f"Confidence Threshold: {conf_threshold}")
    print(f"Table Plane Z: {plane_z} mm")
    print(f"Device: {device}")
    print("=" * 60)

    # Tự động chọn camera nếu source="auto"
    if isinstance(source, str) and source.lower() == "auto":
        detected_cam = find_working_camera()
        print(f"[*] Chế độ 'auto': Đã tự động chọn Camera Index {detected_cam} (có tín hiệu hình ảnh).")
        source = detected_cam

    pipeline = ChessMonoEyePipeline(
        camera_config=calib_file,
        board_config=board_file,
        piece_model_path=model_file,
        conf_threshold=conf_threshold,
        plane_z=plane_z,
        device=device,
    )

    # Nếu source là đường dẫn tới ảnh tĩnh
    if isinstance(source, str) and Path(source).is_file():
        img_path = Path(source)
        frame = cv2.imread(str(img_path))
        if frame is None:
            print(f"Lỗi: Không thể mở file ảnh {img_path}")
            return

        result = pipeline.process_frame(frame)
        print(f"Pose valid: {result.pose.valid}")
        if result.pose.valid:
            c = result.pose.camera_center
            print(f"Tâm camera: X={c[0]:.1f}, Y={c[1]:.1f}, Z={c[2]:.1f} mm")

        print(f"Phát hiện {result.num_pieces} quân cờ:")
        for idx, p in enumerate(result.pieces, 1):
            pos = p.get("position_3d")
            pos_str = f"({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}) mm" if pos is not None else "Không xác định"
            print(f"  [{idx}] {p['class_name']} ({p['fen_char']}) conf={p['confidence']:.2f} -> 3D: {pos_str}")

        vis = pipeline.visualize(frame, result)
        cv2.imshow("Chess 3D Pipeline (Nhan phim bat ky de thoat)", vis)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        return

    # Nếu source là Camera index hoặc video
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"Lỗi: Không thể mở camera hoặc nguồn video: {source}")
        return

    # Cố định độ phân giải theo hiệu chuẩn
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, pipeline.camera.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, pipeline.camera.height)

    print(f"Đang chạy camera (Source: {source})...")
    print("  -> Nhấn 'q' hoặc ESC để thoát.")
    print("  -> Nhấn 'c' để chuyển đổi giữa Camera 0 và Camera 1.")
    prev_time = time.time()
    black_frame_warned = False

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Kết thúc luồng video hoặc mất tín hiệu camera.")
            break

        now = time.time()
        fps = 1.0 / max(1e-5, now - prev_time)
        prev_time = now

        result = pipeline.process_frame(frame)
        vis = pipeline.visualize(frame, result)

        # Kiểm tra nếu màn hình bị đen
        if frame.mean() < 25.0:
            if not black_frame_warned:
                print(
                    f"\n[CẢNH BÁO] Camera {source} bị đen màn (độ sáng trung bình={frame.mean():.1f}/255)!\n"
                    f"  - Nguyên nhân: Nắp che webcam (Privacy Shutter) đang đóng HOẶC đây là webcam phụ.\n"
                    f"  - Khắc phục: Nhấn phím 'c' trên cửa sổ để chuyển sang Camera khác, hoặc chạy với: --source 1\n"
                )
                black_frame_warned = True

            cv2.putText(
                vis,
                f"CANH BAO: Camera {source} bi toi/den! Nhan 'c' de doi camera hoac mo nap che webcam",
                (10, vis.shape[0] - 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 0, 255),
                2,
                cv2.LINE_AA,
            )

        # Vẽ thêm FPS & Nguồn Camera
        cv2.putText(
            vis,
            f"FPS: {fps:.1f} | Cam: {source} (Bam 'c' de doi)",
            (10, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 0),
            2,
            cv2.LINE_AA,
        )

        cv2.imshow("Chess Mono Eye 3D Localization", vis)
        key = cv2.waitKey(1) & 0xFF
        if key in (27, ord("q"), ord("Q")):
            break
        elif key in (ord("c"), ord("C")):
            if isinstance(source, int):
                next_source = 1 if source == 0 else 0
                print(f"[*] Đang chuyển camera sang Index {next_source}...")
                cap.release()
                source = next_source
                cap = cv2.VideoCapture(source)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, pipeline.camera.width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, pipeline.camera.height)
                black_frame_warned = False

    cap.release()
    cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description="Chạy Chess 3D Localization Pipeline.")
    parser.add_argument("--source", default="auto", help="Camera index (ví dụ: 'auto', 0, 1) hoặc đường dẫn file ảnh/video.")
    parser.add_argument("--conf", type=float, default=0.5, help="Ngưỡng độ tin cậy YOLO.")
    parser.add_argument("--plane-z", type=float, default=0.0, help="Cao độ mặt phẳng bàn (mm).")
    parser.add_argument("--device", default="auto", help="Inference device: 'auto', 'cuda', 'cuda:0', 'cpu'.")
    args = parser.parse_args()

    source = int(args.source) if args.source.isdigit() else args.source
    run_pipeline(
        source=source,
        conf_threshold=args.conf,
        plane_z=args.plane_z,
        device=args.device,
    )


if __name__ == "__main__":
    main()
