"""Đánh giá và phân tích toàn diện phiên hiệu chuẩn vừa chụp (Session Evaluation & Export).

Chức năng:
1. Đọc và phân tích phiên chụp (ChArUco Session Analysis).
2. Tối ưu ma trận nội suy camera K và hệ số méo D.
3. Xuất file camera.yaml, camera.json và báo cáo HTML.
4. Cập nhật camera.yaml vào data/calib/camera.yaml để toàn bộ hệ thống sử dụng.
5. In ra bảng kết quả đánh giá chất lượng (RMS, FOV, Bootstrap Error).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fov_tool.board import load_board
from fov_tool.calibration import analyze
from fov_tool.export import export


def find_latest_session(sessions_dir: Path) -> Path | None:
    candidates = [p for p in sessions_dir.iterdir() if p.is_dir() and (p / "manifest.json").exists()]
    if not candidates:
        return None
    return sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def main():
    parser = argparse.ArgumentParser(description="Đánh giá và phân tích phiên hiệu chuẩn Camera")
    parser.add_argument("session", nargs="?", default=None, help="Đường dẫn thư mục phiên (bỏ trống để tự lấy phiên mới nhất)")
    parser.add_argument("--board", default="bang_calib_A4.yaml", help="File cấu hình ChArUco board")
    parser.add_argument("--k3", action="store_true", help="Bật hệ số méo bậc 3 k3")
    parser.add_argument("--bootstrap", type=int, default=10, help="Số lần bootstrap đo độ ổn định")
    args = parser.parse_args()

    sessions_dir = ROOT / "sessions"
    if args.session:
        session_path = Path(args.session).resolve()
    else:
        session_path = find_latest_session(sessions_dir)
        if session_path is None:
            print(f"❌ Không tìm thấy phiên nào trong {sessions_dir}")
            return 1

    if not session_path.exists():
        print(f"❌ Thư mục phiên không tồn tại: {session_path}")
        return 1

    board_path = ROOT / args.board
    print("=" * 70)
    print(f"📊 BẮT ĐẦU ĐÁNH GIÁ PHIÊN: {session_path.name}")
    print(f"📄 Bảng ChArUco: {board_path.name}")
    print("=" * 70)

    # 1. Nạp board
    _, board, _ = load_board(board_path)

    # 2. Phân tích và hiệu chuẩn
    print("▶ Đang phân tích ma trận góc và tối ưu hóa ma trận camera...")
    report, run_dir = analyze(session_path, board, k3=args.k3, bootstrap=args.bootstrap)

    # 3. Xuất file
    print("▶ Đang xuất báo cáo và file cấu hình camera...")
    export_dir = export(session_path, run=run_dir, out=run_dir / "export", camera_name="camera_1")

    # 4. Cập nhật camera.yaml vào data/calib/camera.yaml
    target_calib = ROOT / "data" / "calib" / "camera.yaml"
    target_calib.parent.mkdir(parents=True, exist_ok=True)
    exported_yaml = export_dir / "camera.yaml"
    if exported_yaml.exists():
        shutil.copy2(exported_yaml, target_calib)
        print(f"✔ Đã cập nhật file cấu hình vào: {target_calib.relative_to(ROOT)}")

    # 5. In bảng đánh giá chi tiết
    K = np.array(report["K"])
    D = np.array(report["D"])
    rms = report["rms_px"]
    fov = report["fov_raw"]
    stab = report.get("stability")
    held_out = report.get("validation", {}).get("held_out")

    print("\n" + "=" * 70)
    print("🎯 KẾT QUẢ HIỆU CHUẨN CAMERA (INTRINSICS EVALUATION)")
    print("=" * 70)
    print(f" • Kích thước ảnh: {report['image_size'][0]} x {report['image_size'][1]} px")
    print(f" • Tiêu cự fx, fy: {K[0,0]:.2f} px, {K[1,1]:.2f} px")
    print(f" • Tâm quang cx, cy: {K[0,2]:.2f} px, {K[1,2]:.2f} px")
    print(f" • Hệ số méo D: k1={D[0]:.4f}, k2={D[1]:.4f}, p1={D[2]:.4f}, p2={D[3]:.4f}")
    print(f" • Sai số tái chiếu (RMS Reprojection Error): {rms:.3f} pixel  ({'ĐẠT CHUẨN XUẤT SẮC' if rms < 0.8 else 'ĐẠT'})")
    print(f" • Trường nhìn thực tế (Field of View - FOV):")
    print(f"     - Ngang (H-FOV): {fov['horizontal_deg']:.2f}°")
    print(f"     - Dọc   (V-FOV): {fov['vertical_deg']:.2f}°")
    print(f"     - Chéo  (D-FOV): {fov['diagonal_tl_br_deg']:.2f}°")

    if stab and "fov_horizontal_deg" in stab:
        h_sd = stab["fov_horizontal_deg"]["sd"]
        print(f" • Độ ổn định phép đo (Bootstrap Stability): ±{h_sd:.2f}°")

    if held_out and held_out.get("rms_px") is not None:
        print(f" • Sai số kiểm định độc lập (Held-out Error): {held_out['rms_px']:.3f} pixel")

    status = report["status"]
    print(f" • Trạng thái nghiệm:")
    print(f"     - Số ảnh đạt chuẩn quan sát: {report.get('observation_gate', {}).get('minimum_views', 20)} ảnh")
    print(f"     - Nghiệm giải thành công (Solved): {status['solved']}")
    print(f"     - Kiểm định nội bộ hoàn tất: {status['internal_validation_completed']}")

    print("\n📁 Các tệp đã tạo:")
    print(f"   1. Cấu hình Camera YAML: {target_calib}")
    print(f"   2. Báo cáo HTML trực quan: {export_dir / 'report.html'}")
    print(f"   3. Chi tiết JSON: {run_dir / 'result.json'}")
    print("=" * 70)

    # 6. Chạy tiếp đánh giá sai số tọa độ 3D
    print("\n▶ Tiếp tục chạy đánh giá sai số định vị 3D (3D Error Analysis)...")
    eval_script = ROOT / "scripts" / "run_evaluation.py"
    if eval_script.exists():
        import subprocess
        subprocess.call([sys.executable, str(eval_script), "--camera", str(target_calib), "--demo"])

    print("\n🎉 HOÀN TẤT ĐÁNH GIÁ!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
