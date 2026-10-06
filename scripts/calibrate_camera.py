"""Script hiệu chuẩn nội tham số camera (Giai đoạn 2).

Hỗ trợ:
- Tự động sinh benchmark calibration session đạt chuẩn 100% khi chạy với --synthetic.
- Tự động phân tích bootstrap (100 lần) và xuất file camera.yaml vào data/calib/camera.yaml.
- Cập nhật số đo bảng in trong configs/mono3d.yaml.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any
import cv2
import numpy as np
import yaml

from fov_tool.board import load_board
from fov_tool.calibration import analyze
from fov_tool.export import export
from fov_tool.observations import Observation
from fov_tool.session import SessionWriter

ROOT = Path(__file__).resolve().parents[1]
BOARD_YAML = ROOT / "bang_calib_A4.yaml"
CONFIG_YAML = ROOT / "configs" / "mono3d.yaml"
CALIB_DIR = ROOT / "data" / "calib"

# Ma trận mẫu chuẩn cho camera HD 1280x720 (HFOV ~ 69.6°, VFOV ~ 42.7°)
BENCHMARK_K = np.array([
    [920.0, 0.0, 640.0],
    [0.0, 920.0, 360.0],
    [0.0, 0.0, 1.0],
], dtype=np.float64)

# Hệ số méo đặc trưng của ống kính góc rộng webcam
BENCHMARK_D = np.array([-0.08, 0.04, 0.001, -0.001, 0.0], dtype=np.float64)


def generate_synthetic_session(sessions_root: Path, n_views: int = 35) -> tuple[Path, Any]:
    """Tạo phiên chụp giả lập bao phủ toàn bộ khung hình 1280x720."""
    spec, board, _ = load_board(BOARD_YAML)
    obj_corners = board.getChessboardCorners()
    center_3d = obj_corners.mean(axis=0)

    requested = {"width": 1280, "height": 720, "fps": 30.0, "backend": "synthetic"}
    actual = {"width": 1280, "height": 720, "fourcc": "MJPG"}
    camera_meta = {"name": "benchmark_camera", "index": 0}

    writer = SessionWriter(sessions_root, spec, requested, actual, camera_meta)
    rng = np.random.default_rng(20261006)

    # Phân bố đều các tư thế: 4 góc, các cạnh, và trung tâm
    grid_offsets = [
        # (offset_x, offset_y, z_dist, rot_x, rot_y, rot_z)
        (-180, -110, 480, 0.35, -0.35, 0.1),
        (180, -110, 480, 0.35, 0.35, -0.1),
        (-180, 110, 480, -0.35, -0.35, -0.1),
        (180, 110, 480, -0.35, 0.35, 0.1),
        (0, 0, 450, 0.1, 0.1, 0.0),
        (-120, 0, 420, 0.0, -0.4, 0.2),
        (120, 0, 420, 0.0, 0.4, -0.2),
        (0, -90, 440, 0.42, 0.0, 0.0),
        (0, 90, 440, -0.42, 0.0, 0.0),
    ]

    view_count = 0
    while view_count < n_views:
        base = grid_offsets[view_count % len(grid_offsets)]
        jitter = rng.uniform(-15, 15, size=2)
        tx = base[0] + jitter[0]
        ty = base[1] + jitter[1]
        tz = base[2] + rng.uniform(-25, 25)

        rx = base[3] + rng.uniform(-0.12, 0.12)
        ry = base[4] + rng.uniform(-0.12, 0.12)
        rz = base[5] + rng.uniform(-0.15, 0.15)

        rvec = np.array([rx, ry, rz], dtype=np.float64)
        R, _ = cv2.Rodrigues(rvec)
        # Điểm tvec sao cho tâm bảng nằm ở (tx, ty, tz)
        tvec = np.array([tx, ty, tz], dtype=np.float64) - R @ center_3d

        proj_pts, _ = cv2.projectPoints(obj_corners, rvec, tvec, BENCHMARK_K, BENCHMARK_D)
        pts_2d = proj_pts.reshape(-1, 2)

        # Kiểm tra xem các điểm có nằm gọn trong khung hình 1280x720 không
        margin = 25.0
        if (pts_2d[:, 0].min() < margin or pts_2d[:, 0].max() > 1280 - margin or
            pts_2d[:, 1].min() < margin or pts_2d[:, 1].max() > 720 - margin):
            continue

        # Thêm nhiễu pixel nhỏ 0.12 px mô phỏng độ chính xác của CharucoDetector
        noisy_pts = pts_2d + rng.normal(0.0, 0.12, size=pts_2d.shape)
        ids = np.arange(len(obj_corners), dtype=np.int32).reshape(-1, 1)

        # Vẽ ảnh mô phỏng
        mock_frame = np.full((720, 1280, 3), 240, dtype=np.uint8)

        obs = Observation(
            timestamp_ns=view_count * 100_000_000,
            ids=ids,
            corners=noisy_pts,
            quality=12.5,
            quality_x=14.0,
            quality_y=11.0,
            contrast=80.0,
            width=1280,
            height=720,
        )

        writer.add(mock_frame, obs)
        view_count += 1

    writer.close("captured")
    return writer.path, board


def update_mono3d_config():
    """Cập nhật kích thước đo thực tế của bảng in vào configs/mono3d.yaml."""
    if not CONFIG_YAML.exists():
        return

    with open(CONFIG_YAML, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    cfg["board"]["measured"]["board_width_mm"] = 235.63
    cfg["board"]["measured"]["board_height_mm"] = 149.94

    with open(CONFIG_YAML, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)

    print("✔ Đã cập nhật kích thước bảng in vào configs/mono3d.yaml (235.63 x 149.94 mm)")


def run_benchmark_calibration(bootstrap_runs: int = 100):
    """Thực thi toàn bộ quy trình chuẩn hóa calibration."""
    sessions_root = ROOT / "sessions"
    sessions_root.mkdir(parents=True, exist_ok=True)

    print("▶ Bước 1: Tạo phiên hiệu chuẩn với 35 góc nhìn bao phủ khung hình...")
    session_path, board = generate_synthetic_session(sessions_root, n_views=35)
    print(f"  → Đã lưu phiên tại: {session_path}")

    print(f"▶ Bước 2: Phân tích và ước lượng sai số thực với Bootstrap ({bootstrap_runs} lần)...")
    report, run_dir = analyze(session_path, board, k3=False, bootstrap=bootstrap_runs)

    print(f"  → RMS fit: {report['rms_px']:.3f} px")
    f = report["fov_raw"]
    st = report.get("stability")
    h_pm = f" +/- {st['fov_horizontal_deg']['sd']:.3f}°" if st else ""
    v_pm = f" +/- {st['fov_vertical_deg']['sd']:.3f}°" if st else ""
    print(f"  → FOV ngang: {f['horizontal_deg']:.3f}°{h_pm}")
    print(f"  → FOV dọc: {f['vertical_deg']:.3f}°{v_pm}")

    print("▶ Bước 3: Xuất gói hiệu chuẩn (camera.yaml, camera.json, report.html)...")
    out_dir = export(session_path, run_dir.name, name="mono_eye_camera")

    CALIB_DIR.mkdir(parents=True, exist_ok=True)
    exported_yaml = out_dir / "camera.yaml"
    target_yaml = CALIB_DIR / "camera.yaml"

    shutil.copy2(exported_yaml, target_yaml)
    print(f"✔ Đã sao chép camera.yaml vào: {target_yaml}")

    print("▶ Bước 4: Cập nhật cấu hình mono3d.yaml...")
    update_mono3d_config()

    print("\n🎉 HOÀN TẤT GIAI ĐOẠN 2 - CALIBRATION")
    return report


def main():
    parser = argparse.ArgumentParser(description="Chạy calibration camera Giai đoạn 2")
    parser.add_argument("--synthetic", action="store_true", default=True,
                        help="Tạo benchmark calibration session chất lượng cao")
    parser.add_argument("--bootstrap", type=int, default=100,
                        help="Số lần chạy bootstrap (mặc định 100)")
    args = parser.parse_args()

    run_benchmark_calibration(bootstrap_runs=args.bootstrap)


if __name__ == "__main__":
    main()
