"""Công cụ chụp ảnh thủ công phục vụ hiệu chuẩn Camera (Manual Snapshot Calibration).

Dành cho trường hợp người dùng muốn tự tay bấm chụp từng bức ảnh thay vì để máy tự bắt tự động:
- Phím SPACE: Chụp 1 bức ảnh và lưu vào thư mục `data/calib_images/`
- Phím R: Xoay khung hình 90° (chu kỳ 0° -> 90° -> 180° -> 270°)
- Phím M: Bật / tắt lật gương
- Phím ENTER: Dừng chụp và tự động chạy hiệu chuẩn `do_fov.py import`
- Phím Q / ESC: Thoát
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import time
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SAVE_DIR = ROOT / "data" / "calib_images"


def main():
    parser = argparse.ArgumentParser(description="Chụp ảnh thủ công bằng phím SPACE để hiệu chuẩn")
    parser.add_argument("--camera", type=int, default=1, help="Camera index (mặc định 1)")
    parser.add_argument("--width", type=int, default=1280, help="Độ phân giải ngang")
    parser.add_argument("--height", type=int, default=720, help="Độ phân giải dọc")
    parser.add_argument("--rotation", type=int, default=90, help="Góc xoay (0, 90, 180, 270)")
    parser.add_argument("--clear", action="store_true", help="Xóa các ảnh chụp cũ trong thư mục trước khi bắt đầu")
    args = parser.parse_args()

    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    if args.clear:
        for p in SAVE_DIR.glob("*.png"):
            p.unlink()

    # Mở camera
    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"❌ Không thể mở camera #{args.camera}")
        return 1

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    current_rot = args.rotation % 360
    current_mirror = False
    rot_names = {0: "0°", 90: "90° (PHẢI)", 180: "180°", 270: "270° (TRÁI)"}

    # Đếm số ảnh hiện có
    existing_photos = sorted(SAVE_DIR.glob("snap_*.png"))
    count = len(existing_photos)

    window_name = "Chup anh hieu chuan (Manual Snapshot)"
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

    print("=" * 60)
    print(f"📷 MỞ CAMERA #{args.camera} | Độ phân giải: {args.width}x{args.height}")
    print(f"📁 Thư mục lưu ảnh: {SAVE_DIR}")
    print(f"▶ Hướng dẫn:")
    print("   - [SPACE]: Chụp 1 ảnh (cần khoảng 15 - 25 ảnh ở nhiều góc khác nhau)")
    print("   - [R]: Xoay tiếp 90° nếu ảnh bị nghiêng")
    print("   - [M]: Bật / tắt lật gương")
    print("   - [ENTER]: Hoàn tất và tự động tính ma trận camera")
    print("   - [Q]: Thoát")
    print("=" * 60)

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                print("⚠ Không đọc được frame từ camera.")
                break

            # Xoay ảnh
            if current_rot == 90:
                frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            elif current_rot == 180:
                frame = cv2.rotate(frame, cv2.ROTATE_180)
            elif current_rot == 270:
                frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

            if current_mirror:
                frame = cv2.flip(frame, 1)

            display = frame.copy()
            h, w = display.shape[:2]

            # Header HUD
            cv2.rectangle(display, (0, 0), (w, 50), (25, 25, 25), -1)
            cv2.putText(
                display,
                f"ANH DA CHUP: {count} | Rot: {rot_names.get(current_rot, f'{current_rot}°')}",
                (15, 32),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 255, 0) if count >= 12 else (0, 200, 255),
                2,
                cv2.LINE_AA,
            )

            # Footer HUD
            cv2.rectangle(display, (0, h - 35), (w, h), (25, 25, 25), -1)
            cv2.putText(
                display,
                "[SPACE] Chup anh | [ENTER] Tinh toan | [R] Xoay | [Q] Thoat",
                (15, h - 12),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (220, 220, 220),
                1,
                cv2.LINE_AA,
            )

            cv2.imshow(window_name, display)
            key = cv2.waitKey(1) & 0xFF

            if key in (ord("q"), 27):
                print("▶ Đã hủy/thoát.")
                return 0

            elif key == ord(" "):  # Chụp ảnh
                count += 1
                img_path = SAVE_DIR / f"snap_{count:03d}_{int(time.time())}.png"
                cv2.imwrite(str(img_path), frame)
                print(f"📸 Đã chụp ảnh #{count}: {img_path.name}")
                # Hiệu ứng chớp trắng báo chụp thành công
                white_flash = np.ones_like(display) * 255
                cv2.imshow(window_name, white_flash)
                cv2.waitKey(50)

            elif key in (ord("r"), ord("R")):
                current_rot = (current_rot + 90) % 360
                print(f"🔄 Đổi góc xoay thành: {rot_names.get(current_rot, f'{current_rot}°')}")

            elif key in (ord("m"), ord("M")):
                current_mirror = not current_mirror
                print(f"🔄 Mirror: {'BẬT' if current_mirror else 'TẮT'}")

            elif key in (13, ord("c")):  # ENTER
                if count < 6:
                    print(f"⚠ Mới có {count} ảnh. Cần tối thiểu 6 ảnh (khuyến nghị 15-25 ảnh) để hiệu chuẩn!")
                else:
                    print(f"\n✔ Đã có {count} ảnh đạt yêu cầu. Bắt đầu chạy hiệu chuẩn từ tập ảnh này...")
                    break

    finally:
        cap.release()
        cv2.destroyAllWindows()

    if count >= 6:
        cmd = [
            sys.executable,
            str(ROOT / "do_fov.py"),
            "import",
            str(SAVE_DIR),
            "--name",
            "manual_snapshots",
        ]
        print(f"\n▶ Đang thực thi: {' '.join(cmd)}")
        return subprocess.call(cmd)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
