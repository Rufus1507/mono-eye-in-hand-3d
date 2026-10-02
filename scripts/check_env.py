"""Kiểm tra môi trường (giai đoạn 0).

    uv run python scripts/check_env.py              # chỉ kiểm tra gói và file bảng
    uv run python scripts/check_env.py --camera 0   # thử thêm mở camera, đọc một khung
Mã thoát khác 0 nếu một mục BẮT BUỘC thất bại.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.metadata as md
import platform
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # chạy được cả khi chưa cài package

OK, WARN, FAIL = "[ OK ]", "[WARN]", "[FAIL]"
failed = False


def report(tag: str, msg: str) -> None:
    global failed
    failed = failed or tag == FAIL
    print(f"{tag} {msg}")


def _installed(dist: str) -> bool:
    try:
        md.version(dist)
        return True
    except md.PackageNotFoundError:
        return False


def check_opencv() -> None:
    try:
        import cv2
    except Exception as e:  # noqa: BLE001
        report(FAIL, f"không import được cv2: {e}")
        return
    report(OK, f"cv2 {cv2.__version__} ({cv2.__file__})")
    dists = [d for d in ("opencv-python", "opencv-contrib-python",
                         "opencv-python-headless", "opencv-contrib-python-headless")
             if _installed(d)]
    report(OK if dists == ["opencv-contrib-python"] else WARN, f"bản OpenCV đã cài: {dists or 'không thấy'}")
    if any("headless" in d for d in dists):
        report(FAIL, "đang cài bản headless: cửa sổ GUI sẽ không hiện")
    if len(dists) > 1:
        report(WARN, "nhiều bản OpenCV đè lên nhau; chạy: uv sync --reinstall-package opencv-contrib-python")
    if not hasattr(cv2, "aruco"):
        report(FAIL, "thiếu cv2.aruco")
        return
    ok = hasattr(cv2.aruco, "CharucoBoard") and hasattr(cv2.aruco, "CharucoDetector")
    report(OK if ok else FAIL, "API ChArUco mới (CharucoBoard / CharucoDetector)")
    if not cv2.__version__.startswith("4.13"):
        report(WARN, f"cv2 {cv2.__version__}: file bảng sinh bằng 4.13.0, nên dùng cùng bản để khớp mẫu bảng")


def check_board() -> None:
    try:
        from fov_tool.board import load_board
        from mono_eye.config import load_config, resolve
        cfg = load_config()
        spec, board, _ = load_board(resolve(cfg["board"]["file"]))
        n = board.getChessboardCorners().shape[0]
        report(OK, f"đọc được bảng {spec.squares_x}x{spec.squares_y}, {spec.dictionary}, {n} góc trong")
    except Exception as e:  # noqa: BLE001
        report(FAIL, f"không đọc được file bảng: {e}")


def check_board_measured() -> None:
    from mono_eye.board_scale import BoardNotMeasured, board_scale_from_config
    from mono_eye.config import load_config
    try:
        s = board_scale_from_config(load_config())
        report(OK, f"cạnh ô thật {s.square_mm:.3f} mm (tỉ lệ ngang {s.scale_x:.4f}, dọc {s.scale_y:.4f})")
    except BoardNotMeasured:
        report(WARN, "chưa đo bảng in (board.measured.* trong configs/mono3d.yaml): chưa cần cho giai đoạn 0, cần từ giai đoạn 3")
    except Exception as e:  # noqa: BLE001
        report(FAIL, f"số đo bảng không hợp lệ: {e}")


def check_module(name: str, required: bool, hint: str) -> None:
    try:
        m = importlib.import_module(name)
        report(OK, f"{name} {getattr(m, '__version__', '')}".rstrip())
    except Exception as e:  # noqa: BLE001
        report(FAIL if required else WARN, f"{name} không import được ({type(e).__name__}); {hint}")


def check_camera(index: int, width: int, height: int) -> None:
    # Dùng chính open_camera của fov_tool (thứ tự đặt fps -> kích thước -> MJPG, thử msmf/dshow/any),
    # để phép thử phản ánh đúng điều kiện lúc chụp thật.
    from fov_tool.camera import open_camera
    try:
        cap, frame, actual = open_camera(index, width, height, 30.0, "auto")
    except RuntimeError as e:
        report(FAIL, f"{e} (thử index khác, đóng app khác đang dùng camera)")
        return
    cap.release()
    h, w = frame.shape[:2]
    report(OK if (w, h) == (width, height) else WARN,
           f"camera {index} ({actual['backend']}, {actual['fourcc_text']}) trả về {w}x{h} (yêu cầu {width}x{height})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", type=int, default=None)
    ap.add_argument("--width", type=int, default=None)
    ap.add_argument("--height", type=int, default=None)
    args = ap.parse_args()

    v = sys.version_info
    report(OK, f"Python {v.major}.{v.minor}.{v.micro} trên {platform.platform()}")
    check_opencv()
    check_module("numpy", True, "chạy: uv sync")
    check_module("yaml", True, "chạy: uv sync")
    check_module("fov_tool", True, "chạy: uv sync")
    check_module("mono_eye", True, "chạy: uv sync")
    check_board()
    check_board_measured()
    check_module("ultralytics", False, "giai đoạn 5: uv sync --group detect")
    check_module("rerun", False, "giai đoạn 6: uv sync --group viz")
    check_module("pandas", False, "giai đoạn 7: uv sync --group analysis")
    if args.camera is not None:
        from mono_eye.config import load_config
        cam = load_config()["camera"]
        check_camera(args.camera, args.width or cam["width"], args.height or cam["height"])
    print("\nKẾT QUẢ:", "CÓ LỖI" if failed else "các mục bắt buộc đều đạt")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
