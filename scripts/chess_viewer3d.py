#!/usr/bin/env python3
"""CLI khởi chạy Standalone 3D Chess Viewer chất lượng cao (ModernGL PBR + GPU RTX 3060).

Phím tắt điều khiển:
- Chuột trái kéo: Xoay góc nhìn toàn cảnh bàn cờ (Orbit 360°)
- Con lăn chuột: Thu phóng camera mượt mà (Dolly Zoom)
- Chuột phải / Shift + Chuột trái: Di chuyển tâm nhìn (Pan)
- Phím 'r' / 'R': Đặt lại góc nhìn mặc định (Reset Camera)
- Phím 's' / 'S': Chụp ảnh màn hình chất lượng cao lưu vào outputs/
- Phím ESC: Thoát ứng dụng
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mono_eye.viewer3d.app import ViewerApp


def main() -> None:
    parser = argparse.ArgumentParser(description="Standalone 3D Chess Studio Viewer")
    parser.add_argument("--width", type=int, default=1280, help="Chiều rộng cửa sổ")
    parser.add_argument("--height", type=int, default=720, help="Chiều cao cửa sổ")
    parser.add_argument("--headless-frames", type=int, default=None, help="Số khung hình render ẩn rồi tự động lưu ảnh và thoát")
    parser.add_argument("--screenshot-out", type=str, default=None, help="Đường dẫn file ảnh xuất ra khi chạy headless")
    args = parser.parse_args()

    is_headless = args.headless_frames is not None
    app = ViewerApp(
        width=args.width,
        height=args.height,
        title="3D Chess Studio Viewer (PBR + RTX 3060)",
        headless=is_headless,
    )

    try:
        if is_headless:
            app.run(max_frames=args.headless_frames)
            out_file = args.screenshot_out or "outputs/viewer_screenshot.png"
            saved_path = app.save_screenshot(out_file)
            print(f"[CLI] Headless render complete! Saved: {saved_path}")
        else:
            print("\n" + "=" * 60)
            print("  3D CHESS STUDIO VIEWER RUNNING")
            print("  - Left Mouse Drag : Orbit 360 view")
            print("  - Scroll Wheel    : Zoom in / Zoom out")
            print("  - Right Drag/Shift: Pan camera")
            print("  - Key 'R'         : Reset view")
            print("  - Key 'S'         : Save screenshot to outputs/")
            print("  - Key ESC         : Close window")
            print("=" * 60 + "\n")
            app.run()
    finally:
        app.close()


if __name__ == "__main__":
    main()
