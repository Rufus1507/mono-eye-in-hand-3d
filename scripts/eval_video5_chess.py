from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.realtime_chessboard8x8_viz import run_chessboard8x8_live


def compute_metrics_from_csv(csv_path: str | Path) -> dict:
    csv_file = Path(csv_path)
    if not csv_file.is_file():
        raise FileNotFoundError(f"Không tìm thấy file CSV: {csv_file}")

    rows = []
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    # 1. Đo lường chiều cao
    height_errors = []
    greens = 0
    yellows = 0
    reds = 0

    for r in rows:
        err_str = r.get("height_error_mm", "")
        if err_str != "":
            try:
                err = abs(float(err_str))
                height_errors.append(err)
                if err <= 5.0:
                    greens += 1
                elif err <= 10.0:
                    yellows += 1
                else:
                    reds += 1
            except ValueError:
                pass

    n_height = len(height_errors)
    import numpy as np

    mean_err = float(np.mean(height_errors)) if n_height > 0 else 0.0
    median_err = float(np.median(height_errors)) if n_height > 0 else 0.0
    p90_err = float(np.percentile(height_errors, 90)) if n_height > 0 else 0.0
    green_rate = (greens / max(1, n_height)) * 100.0
    yellow_rate = (yellows / max(1, n_height)) * 100.0
    pass_rate = green_rate + yellow_rate

    # 2. Đo độ ổn định nhãn (Class Churn)
    tracks_classes = {}
    for r in rows:
        t_id = r.get("track_id", "-1")
        c_name = r.get("class_name", "")
        if t_id not in ("-1", "", None) and c_name:
            if t_id not in tracks_classes:
                tracks_classes[t_id] = []
            tracks_classes[t_id].append(c_name)

    total_churn = 0
    for t_id, classes in tracks_classes.items():
        churn = sum(1 for i in range(1, len(classes)) if classes[i] != classes[i - 1])
        total_churn += churn

    # 3. Phân theo cung góc quay camera
    sectors = {}
    for r in rows:
        sec = r.get("cam_sector", "N/A")
        err_str = r.get("height_error_mm", "")
        if sec not in sectors:
            sectors[sec] = {"samples": 0, "errors": [], "greens": 0, "yellows": 0}
        if err_str != "":
            try:
                err = abs(float(err_str))
                sectors[sec]["samples"] += 1
                sectors[sec]["errors"].append(err)
                if err <= 5.0:
                    sectors[sec]["greens"] += 1
                elif err <= 10.0:
                    sectors[sec]["yellows"] += 1
            except ValueError:
                pass

    sec_summary = {}
    for s_name, s_data in sectors.items():
        cnt = s_data["samples"]
        if cnt > 0:
            s_mean = float(np.mean(s_data["errors"]))
            s_med = float(np.median(s_data["errors"]))
            s_pass = ((s_data["greens"] + s_data["yellows"]) / cnt) * 100.0
            sec_summary[s_name] = {
                "samples": cnt,
                "mean_err_mm": round(s_mean, 2),
                "median_err_mm": round(s_med, 2),
                "pass_rate": round(s_pass, 1),
            }

    return {
        "csv_path": str(csv_file),
        "total_rows": len(rows),
        "n_height_rows": n_height,
        "green_count": greens,
        "yellow_count": yellows,
        "red_count": reds,
        "green_rate": round(green_rate, 2),
        "yellow_rate": round(yellow_rate, 2),
        "pass_green_yellow_rate": round(pass_rate, 2),
        "mean_abs_err_mm": round(mean_err, 2),
        "median_abs_err_mm": round(median_err, 2),
        "p90_abs_err_mm": round(p90_err, 2),
        "class_churn": total_churn,
        "sectors": sec_summary,
    }


def compare_csvs(csv_a: str | Path, csv_b: str | Path) -> None:
    met_a = compute_metrics_from_csv(csv_a)
    met_b = compute_metrics_from_csv(csv_b)

    print("=" * 70)
    print(" SO SÁNH ĐỊNH LƯỢNG KẾT QUẢ TRƯỚC / SAU CẢI TIẾN")
    print("=" * 70)
    print(f" Bản A (Trước): {Path(csv_a).name}")
    print(f" Bản B (Sau)  : {Path(csv_b).name}")
    print("-" * 70)
    print(f"{'Chỉ số (Metric)':<28} | {'Bản A':<12} | {'Bản B':<12} | {'Biến thiên (Delta)'}")
    print("-" * 70)

    # Pass Rate
    d_pass = met_b["pass_green_yellow_rate"] - met_a["pass_green_yellow_rate"]
    print(f"{'Tỷ lệ Đạt Chuẩn (Xanh+Vàng)':<28} | {met_a['pass_green_yellow_rate']:>11.1f}% | {met_b['pass_green_yellow_rate']:>11.1f}% | {d_pass:>+10.1f}%")

    # Green Rate
    d_green = met_b["green_rate"] - met_a["green_rate"]
    print(f"{'Tỷ lệ Xanh lá (<=5mm)':<28} | {met_a['green_rate']:>11.1f}% | {met_b['green_rate']:>11.1f}% | {d_green:>+10.1f}%")

    # Mean Error
    d_mean = met_b["mean_abs_err_mm"] - met_a["mean_abs_err_mm"]
    print(f"{'Sai số trung bình (Mean)':<28} | {met_a['mean_abs_err_mm']:>10.1f}mm | {met_b['mean_abs_err_mm']:>10.1f}mm | {d_mean:>+9.1f}mm")

    # Median Error
    d_med = met_b["median_abs_err_mm"] - met_a["median_abs_err_mm"]
    print(f"{'Trung vị sai số (Median)':<28} | {met_a['median_abs_err_mm']:>10.1f}mm | {met_b['median_abs_err_mm']:>10.1f}mm | {d_med:>+9.1f}mm")

    # Class Churn
    d_churn = met_b["class_churn"] - met_a["class_churn"]
    print(f"{'Độ lật nhãn (Class Churn)':<28} | {met_a['class_churn']:>12d} | {met_b['class_churn']:>12d} | {d_churn:>+11d}")

    print("-" * 70)

    # Quyết định KEEP hay REVERT
    # Tiêu chuẩn: Pass Rate tăng hoặc giữ nguyên VÀ Mean Error không tăng đáng kể
    improved = (d_pass > 0.0 or (abs(d_pass) <= 0.5 and d_mean <= 0.2)) and (d_churn <= 0 or d_pass > 2.0)
    worse = (d_pass < -1.5) or (d_mean > 1.5 and d_med > 1.5)

    if improved:
        decision = "🟢 KEEP (KẾT QUẢ TỐT HƠN - GIỮ LẠI)"
    elif worse:
        decision = "🔴 REVERT (KẾT QUẢ TỆ HƠN - HOÀN TÁC BẢN CŨ)"
    else:
        decision = "🟡 NEUTRAL (KẾT QUẢ TƯƠNG ĐƯƠNG - XEM XÉT CHI TIẾT)"

    print(f" QUYẾT ĐỊNH: {decision}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Công cụ đánh giá định lượng và so sánh Video 5")
    parser.add_argument("--source", default="videochess/video5.mp4", help="Đường dẫn video")
    parser.add_argument("--dump-csv", default=None, help="Đường dẫn file CSV xuất dữ liệu")
    parser.add_argument("--label", default="eval", help="Tên nhãn kết quả")
    parser.add_argument("--max-frames", type=int, default=350, help="Số frame chạy đánh giá")
    parser.add_argument("--compare", nargs=2, default=None, metavar=("CSV_A", "CSV_B"), help="So sánh 2 file CSV")
    args = parser.parse_args()

    if args.compare:
        compare_csvs(args.compare[0], args.compare[1])
        return

    csv_path = args.dump_csv or f"results/video5/{args.label}.csv"
    json_path = f"results/video5/{args.label}.json"

    print(f"Đang chạy đánh giá {args.source} trên {args.max_frames} frames...")
    run_chessboard8x8_live(
        source=args.source,
        charuco_cfg_file="bang_calib.yaml",
        board_type="charuco",
        headless=True,
        max_frames=args.max_frames,
        dump_csv_path=csv_path,
    )

    metrics = compute_metrics_from_csv(csv_path)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    print(f"Đã lưu kết quả tại: {csv_path} và {json_path}")
    print(f" - Tổng lượt đo chiều cao: {metrics['n_height_rows']}")
    print(f" - Tỷ lệ Đạt chuẩn (Xanh + Vàng): {metrics['pass_green_yellow_rate']}%")
    print(f" - Sai số TB: {metrics['mean_abs_err_mm']}mm | Trung vị: {metrics['median_abs_err_mm']}mm")
    print(f" - Số lần lật nhãn (Class Churn): {metrics['class_churn']}")


if __name__ == "__main__":
    main()
