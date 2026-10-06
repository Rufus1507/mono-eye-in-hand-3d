"""Giai đoạn 7 - Error analysis, evaluation và logging cho hệ thống Mono Eye 3D."""
from __future__ import annotations

import csv
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
import numpy as np

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    pd = None
    HAS_PANDAS = False


@dataclass
class EvaluationResult:
    """Kết quả đánh giá sai số tọa độ 3D cho một điểm mốc.

    Attributes:
        timestamp: Thời gian đo (epoch seconds).
        frame_id: Chỉ số khung hình camera.
        point_id: Định danh điểm ground truth (vd: 'p01').
        estimated: Vector tọa độ 3D ước lượng [x, y, z] (mm).
        ground_truth: Vector tọa độ 3D chuẩn [x, y, z] (mm).
        error_total: Khoảng cách sai số Euclidean (mm).
        error_x: Độ lệch trục X: estimated[0] - gt[0] (mm).
        error_y: Độ lệch trục Y: estimated[1] - gt[1] (mm).
        error_z: Độ lệch trục Z: estimated[2] - gt[2] (mm).
        num_corners: Số góc ChArUco phát hiện được trong khung hình.
        reproj_error_px: Sai số chiếu lại của camera pose (pixels).
        camera_x: Tọa độ X của tâm camera (mm).
        camera_y: Tọa độ Y của tâm camera (mm).
        camera_z: Tọa độ Z của tâm camera (mm).
    """

    timestamp: float
    frame_id: int
    point_id: str
    estimated: np.ndarray
    ground_truth: np.ndarray
    error_total: float
    error_x: float
    error_y: float
    error_z: float

    # Metadata chất lượng
    num_corners: int = 0
    reproj_error_px: float = float("inf")
    camera_x: float = 0.0
    camera_y: float = 0.0
    camera_z: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Chuyển đổi kết quả sang dạng dictionary để xuất bảng CSV."""
        return {
            "timestamp": float(self.timestamp),
            "frame_id": int(self.frame_id),
            "point_id": str(self.point_id),
            "estimated_x": float(self.estimated[0]),
            "estimated_y": float(self.estimated[1]),
            "estimated_z": float(self.estimated[2]),
            "ground_truth_x": float(self.ground_truth[0]),
            "ground_truth_y": float(self.ground_truth[1]),
            "ground_truth_z": float(self.ground_truth[2]),
            "error_total": float(self.error_total),
            "error_x": float(self.error_x),
            "error_y": float(self.error_y),
            "error_z": float(self.error_z),
            "num_corners": int(self.num_corners),
            "reproj_error_px": float(self.reproj_error_px),
            "camera_x": float(self.camera_x),
            "camera_y": float(self.camera_y),
            "camera_z": float(self.camera_z),
        }


class GroundTruthLoader:
    """Bộ nạp tọa độ điểm mốc thực tế (ground truth) từ file CSV."""

    def __init__(self, csv_path: str | Path):
        """Khởi tạo loader và đọc danh sách điểm.

        Args:
            csv_path: Đường dẫn file CSV chứa ground truth points.
        """
        self.csv_path = Path(csv_path)
        self.points: dict[str, np.ndarray] = self._load()

    def _load(self) -> dict[str, np.ndarray]:
        """Đọc và lọc các dòng dữ liệu hợp lệ trong file CSV."""
        points: dict[str, np.ndarray] = {}
        if not self.csv_path.exists():
            return points

        with open(self.csv_path, mode="r", encoding="utf-8") as f:
            valid_lines = [
                line for line in f
                if line.strip() and not line.strip().startswith("#")
            ]

        if not valid_lines:
            return points

        reader = csv.DictReader(valid_lines)
        for row in reader:
            if not row or "point_id" not in row or not row["point_id"]:
                continue
            pid = str(row["point_id"]).strip()
            if not pid:
                continue
            try:
                x = float(row["x_mm"])
                y = float(row["y_mm"])
                z = float(row.get("z_mm", 0.0) or 0.0)
                points[pid] = np.array([x, y, z], dtype=np.float64)
            except (ValueError, KeyError):
                continue

        return points

    def get_point(self, point_id: str) -> Optional[np.ndarray]:
        """Lấy tọa độ 3D thực tế của một điểm mốc."""
        return self.points.get(point_id)

    def get_all_points(self) -> dict[str, np.ndarray]:
        """Lấy bản sao toàn bộ từ điển tọa độ điểm mốc."""
        return self.points.copy()


class SimpleDataFrame:
    """Đối tượng mô phỏng DataFrame nhẹ khi môi trường chưa cài pandas."""

    def __init__(self, records: list[dict[str, Any]]):
        self._records = records

    @property
    def empty(self) -> bool:
        return len(self._records) == 0

    def __len__(self) -> int:
        return len(self._records)

    def __getitem__(self, col: str) -> "SimpleSeries":
        vals = [r.get(col) for r in self._records]
        return SimpleSeries(vals)

    def iterrows(self):
        for idx, r in enumerate(self._records):
            yield idx, r

    def groupby(self, column: str):
        groups: dict[Any, list[dict[str, Any]]] = {}
        for r in self._records:
            k = r.get(column)
            groups.setdefault(k, []).append(r)
        return SimpleGroupBy(groups)


class SimpleSeries:
    """Mô phỏng Series hỗ trợ tính các phép toán thống kê cơ bản."""

    def __init__(self, values: list[Any]):
        self._values = [v for v in values if v is not None]

    def mean(self) -> float:
        return float(np.mean(self._values)) if self._values else 0.0

    def median(self) -> float:
        return float(np.median(self._values)) if self._values else 0.0

    def std(self) -> float:
        return float(np.std(self._values, ddof=1)) if len(self._values) > 1 else 0.0

    def min(self) -> float:
        return float(np.min(self._values)) if self._values else 0.0

    def max(self) -> float:
        return float(np.max(self._values)) if self._values else 0.0

    def quantile(self, q: float) -> float:
        return float(np.percentile(self._values, q * 100)) if self._values else 0.0


class SimpleGroupBy:
    """Mô phỏng GroupBy tối thiểu."""

    def __init__(self, groups: dict[Any, list[dict[str, Any]]]):
        self._groups = groups

    def agg(self, agg_dict: dict[str, list[str]]):
        return self._groups


class ErrorAnalyzer:
    """Bộ phân tích sai số (Error Analyzer) giữa ước lượng và ground truth."""

    def __init__(self, ground_truth: GroundTruthLoader):
        """Khởi tạo analyzer với GroundTruthLoader."""
        self.ground_truth = ground_truth
        self.results: list[EvaluationResult] = []

    def add_result(self, result: EvaluationResult):
        """Thêm một kết quả đánh giá vào danh sách theo dõi."""
        self.results.append(result)

    def compute_error(
        self,
        point_id: str,
        estimated: np.ndarray,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[EvaluationResult]:
        """Tính toán sai số đối với một điểm cụ thể.

        Args:
            point_id: Định danh điểm ground truth.
            estimated: Tọa độ 3D ước lượng [x, y, z] (mm).
            metadata: Thông tin bổ sung (frame_id, num_corners, camera pose, v.v.).

        Returns:
            EvaluationResult nếu điểm tồn tại trong ground truth, ngược lại None.
        """
        gt = self.ground_truth.get_point(point_id)
        if gt is None:
            return None

        est = np.asarray(estimated, dtype=np.float64).reshape(3)
        diff = est - gt
        error_total = float(np.linalg.norm(diff))

        meta = metadata or {}
        result = EvaluationResult(
            timestamp=float(meta.get("timestamp", time.time())),
            frame_id=int(meta.get("frame_id", 0)),
            point_id=point_id,
            estimated=est,
            ground_truth=gt,
            error_total=error_total,
            error_x=float(diff[0]),
            error_y=float(diff[1]),
            error_z=float(diff[2]),
            num_corners=int(meta.get("num_corners", 0)),
            reproj_error_px=float(meta.get("reproj_error_px", float("inf"))),
            camera_x=float(meta.get("camera_x", 0.0)),
            camera_y=float(meta.get("camera_y", 0.0)),
            camera_z=float(meta.get("camera_z", 0.0)),
        )

        self.add_result(result)
        return result

    def get_dataframe(self) -> Any:
        """Chuyển danh sách kết quả sang DataFrame (Pandas hoặc SimpleDataFrame)."""
        records = [r.to_dict() for r in self.results]
        if HAS_PANDAS and pd is not None:
            return pd.DataFrame(records)
        return SimpleDataFrame(records)

    def summary_statistics(self) -> dict[str, Any]:
        """Tính toán các chỉ số thống kê sai số tổng hợp (mean, median, std, min, max, p95)."""
        if not self.results:
            return {}

        tot = np.array([r.error_total for r in self.results], dtype=np.float64)
        ex = np.array([r.error_x for r in self.results], dtype=np.float64)
        ey = np.array([r.error_y for r in self.results], dtype=np.float64)
        ez = np.array([r.error_z for r in self.results], dtype=np.float64)

        n = len(tot)
        std_tot = float(np.std(tot, ddof=1)) if n > 1 else 0.0
        std_x = float(np.std(ex, ddof=1)) if n > 1 else 0.0
        std_y = float(np.std(ey, ddof=1)) if n > 1 else 0.0
        std_z = float(np.std(ez, ddof=1)) if n > 1 else 0.0

        return {
            "n_samples": n,
            "error_total": {
                "mean": float(np.mean(tot)),
                "median": float(np.median(tot)),
                "std": std_tot,
                "min": float(np.min(tot)),
                "max": float(np.max(tot)),
                "p95": float(np.percentile(tot, 95)),
            },
            "error_x": {
                "mean": float(np.mean(ex)),
                "std": std_x,
            },
            "error_y": {
                "mean": float(np.mean(ey)),
                "std": std_y,
            },
            "error_z": {
                "mean": float(np.mean(ez)),
                "std": std_z,
            },
        }

    def group_by(self, column: str) -> Any:
        """Nhóm kết quả theo một cột và tính toán sai số tổng."""
        df = self.get_dataframe()
        if hasattr(df, "empty") and df.empty:
            return df
        return df.groupby(column)


class CSVLogger:
    """Logger ghi nhận các mẫu đánh giá ra file CSV."""

    def __init__(self, output_path: str | Path):
        """Khởi tạo logger với đường dẫn file CSV xuất."""
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._writer: Optional[csv.DictWriter] = None
        self._file: Any = None

    @property
    def fieldnames(self) -> list[str]:
        """Tên các cột chuẩn trong file CSV."""
        return [
            "timestamp",
            "frame_id",
            "point_id",
            "estimated_x",
            "estimated_y",
            "estimated_z",
            "ground_truth_x",
            "ground_truth_y",
            "ground_truth_z",
            "error_total",
            "error_x",
            "error_y",
            "error_z",
            "num_corners",
            "reproj_error_px",
            "camera_x",
            "camera_y",
            "camera_z",
        ]

    def __enter__(self) -> "CSVLogger":
        """Context manager entry."""
        self._file = open(self.output_path, "w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=self.fieldnames)
        self._writer.writeheader()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any):
        """Context manager exit."""
        self.close()

    def write(self, result: EvaluationResult):
        """Ghi một bản ghi EvaluationResult vào file."""
        if self._writer is None:
            needs_header = not self.output_path.exists() or self.output_path.stat().st_size == 0
            self._file = open(self.output_path, "a", newline="", encoding="utf-8")
            self._writer = csv.DictWriter(self._file, fieldnames=self.fieldnames)
            if needs_header:
                self._writer.writeheader()

        self._writer.writerow(result.to_dict())
        if self._file:
            self._file.flush()

    def close(self):
        """Đóng file và giải phóng tài nguyên."""
        if self._file:
            self._file.close()
            self._file = None
            self._writer = None


def generate_error_report(
    csv_path: str | Path,
    output_path: str | Path,
    ground_truth_path: Optional[str | Path] = None,
) -> str:
    """Tạo báo cáo Markdown phân tích sai số chi tiết từ file CSV ghi nhận.

    Args:
        csv_path: Đường dẫn file CSV kết quả đo.
        output_path: Đường dẫn lưu báo cáo Markdown.
        ground_truth_path: Đường dẫn file ground truth points (nếu cần bổ sung).

    Returns:
        Nội dung báo cáo dưới dạng chuỗi Markdown.
    """
    csv_file = Path(csv_path)
    if not csv_file.exists():
        raise FileNotFoundError(f"File kết quả {csv_path} không tồn tại.")

    # Đọc dữ liệu từ CSV
    rows: list[dict[str, Any]] = []
    with open(csv_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if not rows:
        report = "# Error Analysis Report\n\nKhông có dữ liệu đo đạc nào được ghi nhận.\n"
        Path(output_path).write_text(report, encoding="utf-8")
        return report

    errors_tot = [float(r["error_total"]) for r in rows if "error_total" in r]
    total_samples = len(errors_tot)
    mean_err = float(np.mean(errors_tot))
    median_err = float(np.median(errors_tot))
    std_err = float(np.std(errors_tot, ddof=1)) if total_samples > 1 else 0.0
    p95_err = float(np.percentile(errors_tot, 95))
    max_err = float(np.max(errors_tot))
    min_err = float(np.min(errors_tot))

    # Nhóm theo point_id
    by_point: dict[str, list[float]] = {}
    # Nhóm theo num_corners
    by_corners: dict[int, list[float]] = {}

    for r in rows:
        pid = r.get("point_id", "unknown")
        err = float(r.get("error_total", 0.0))
        by_point.setdefault(pid, []).append(err)

        corners = int(r.get("num_corners", 0))
        by_corners.setdefault(corners, []).append(err)

    report_lines = [
        "# Error Analysis Report",
        "",
        "## 1. Summary Statistics",
        f"- **Tổng số mẫu đo (Total samples):** {total_samples}",
        f"- **Sai số trung bình (Mean Error):** {mean_err:.3f} mm",
        f"- **Trung vị sai số (Median Error):** {median_err:.3f} mm",
        f"- **Độ lệch chuẩn (Std Dev):** {std_err:.3f} mm",
        f"- **Bách phân vị 95 (95th Percentile):** {p95_err:.3f} mm",
        f"- **Sai số nhỏ nhất (Min Error):** {min_err:.3f} mm",
        f"- **Sai số lớn nhất (Max Error):** {max_err:.3f} mm",
        "",
        "## 2. Error by Ground Truth Point",
        "",
        "| Point ID | Mean Error (mm) | Median (mm) | Std (mm) | Count |",
        "|----------|-----------------|-------------|----------|-------|",
    ]

    for pid in sorted(by_point.keys()):
        pts = by_point[pid]
        p_mean = np.mean(pts)
        p_med = np.median(pts)
        p_std = np.std(pts, ddof=1) if len(pts) > 1 else 0.0
        report_lines.append(
            f"| `{pid}` | {p_mean:.3f} | {p_med:.3f} | {p_std:.3f} | {len(pts)} |"
        )

    report_lines.extend([
        "",
        "## 3. Error by Pose Quality (Number of Corners)",
        "",
        "| ChArUco Corners | Mean Error (mm) | Median (mm) | Sample Count |",
        "|-----------------|-----------------|-------------|--------------|",
    ])

    for nc in sorted(by_corners.keys()):
        c_pts = by_corners[nc]
        c_mean = np.mean(c_pts)
        c_med = np.median(c_pts)
        report_lines.append(
            f"| {nc} góc | {c_mean:.3f} | {c_med:.3f} | {len(c_pts)} |"
        )

    report_text = "\n".join(report_lines) + "\n"
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(report_text, encoding="utf-8")
    return report_text
