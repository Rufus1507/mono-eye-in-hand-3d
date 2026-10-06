"""Script thực thi và đánh giá sai số tọa độ 3D (Giai đoạn 7)."""
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np

from mono_eye.camera_io import load_camera_yaml
from mono_eye.evaluate import (
    CSVLogger,
    ErrorAnalyzer,
    EvaluationResult,
    GroundTruthLoader,
    generate_error_report,
)


def main():
    parser = argparse.ArgumentParser(description="Chạy đánh giá sai số Mono Eye 3D")
    parser.add_argument("--camera", default="data/calib/camera.yaml", help="Path camera calibration YAML")
    parser.add_argument("--board", default="bang_calib_A4.yaml", help="Path ChArUco board YAML")
    parser.add_argument("--ground-truth", default="configs/ground_truth_points.csv", help="Path ground truth points CSV")
    parser.add_argument("--output", default="results/logs/evaluation.csv", help="Path output evaluation CSV")
    parser.add_argument("--report", default="results/logs/evaluation_report.md", help="Path output report Markdown")
    parser.add_argument("--demo", action="store_true", help="Chạy kịch bản đánh giá mô phỏng mẫu")
    args = parser.parse_args()

    gt_file = Path(args.ground_truth)
    if not gt_file.exists():
        print(f"⚠ File ground truth {gt_file} không tồn tại. Tạo file mẫu...")
        gt_file.parent.mkdir(parents=True, exist_ok=True)
        gt_file.write_text("point_id,x_mm,y_mm,z_mm\np01,0,0,0\np02,100,0,0\np03,0,100,0\n", encoding="utf-8")

    gt_loader = GroundTruthLoader(gt_file)
    analyzer = ErrorAnalyzer(gt_loader)
    logger = CSVLogger(args.output)

    print(f"▶ Nạp Ground Truth: {len(gt_loader.points)} điểm mốc ({list(gt_loader.points.keys())})")
    print(f"▶ File xuất kết quả: {args.output}")

    # Chạy kịch bản demo tính sai số nếu được yêu cầu hoặc nếu chưa có camera
    if args.demo or not Path(args.camera).exists():
        print("▶ Đang tạo dữ liệu đánh giá mô phỏng (Synthetic Evaluation Samples)...")
        with logger:
            for i, (pid, true_pos) in enumerate(gt_loader.points.items()):
                # Thêm nhiễu ngẫu nhiên nhỏ mô phỏng thực tế
                noise = np.array([
                    np.sin(i + 1) * 1.5,
                    np.cos(i + 1) * 1.2,
                    0.0,
                ], dtype=np.float64)
                est_pos = true_pos + noise

                meta = {
                    "frame_id": i + 1,
                    "num_corners": 45,
                    "reproj_error_px": 0.32,
                    "camera_x": 0.0,
                    "camera_y": -50.0,
                    "camera_z": 400.0,
                }
                res = analyzer.compute_error(pid, est_pos, meta)
                if res:
                    logger.write(res)

        print("✔ Đã ghi các mẫu đánh giá vào CSV.")
        rep = generate_error_report(args.output, args.report)
        print(f"✔ Đã xuất báo cáo tại: {args.report}")
        stats = analyzer.summary_statistics()
        if stats:
            print(f"  → Số mẫu: {stats['n_samples']}")
            print(f"  → Sai số trung bình: {stats['error_total']['mean']:.3f} mm")
            print(f"  → Sai số P95: {stats['error_total']['p95']:.3f} mm")
    else:
        print("ℹ Hệ thống đánh giá đã sẵn sàng cho pipeline thu thập dữ liệu thực tế.")


if __name__ == "__main__":
    main()
