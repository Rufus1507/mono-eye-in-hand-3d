"""Unit tests cho evaluation và error analysis module (Giai đoạn 7)."""
from __future__ import annotations

import tempfile
from pathlib import Path
import numpy as np
import pytest

from mono_eye.evaluate import (
    CSVLogger,
    ErrorAnalyzer,
    EvaluationResult,
    GroundTruthLoader,
    generate_error_report,
)


def test_ground_truth_loader():
    """Kiểm tra GroundTruthLoader nạp và lọc điểm mốc từ CSV."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write("# Chú thích: Bảng tọa độ mốc\n")
        f.write("point_id,x_mm,y_mm,z_mm,note\n")
        f.write("# Dòng comment giữa các bản ghi\n")
        f.write("p01,0,0,0,Origin\n")
        f.write("p02,100,50,0,Corner\n")
        f.write("p03,-50,80,10,Slanted\n")
        temp_path = f.name

    try:
        loader = GroundTruthLoader(temp_path)

        # Kiểm tra số lượng và tọa độ
        assert len(loader.points) == 3
        assert np.allclose(loader.get_point("p01"), [0.0, 0.0, 0.0])
        assert np.allclose(loader.get_point("p02"), [100.0, 50.0, 0.0])
        assert np.allclose(loader.get_point("p03"), [-50.0, 80.0, 10.0])
        assert loader.get_point("p99_nonexistent") is None

        # Kiểm tra get_all_points trả về bản sao
        all_pts = loader.get_all_points()
        assert len(all_pts) == 3
        all_pts["temp"] = np.array([1, 1, 1])
        assert "temp" not in loader.points
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_evaluation_result_to_dict():
    """Kiểm tra EvaluationResult và chuyển đổi to_dict()."""
    res = EvaluationResult(
        timestamp=1000.0,
        frame_id=42,
        point_id="p01",
        estimated=np.array([10.0, 20.0, 0.0]),
        ground_truth=np.array([10.0, 15.0, 0.0]),
        error_total=5.0,
        error_x=0.0,
        error_y=5.0,
        error_z=0.0,
        num_corners=35,
        reproj_error_px=0.25,
        camera_x=0.0,
        camera_y=-100.0,
        camera_z=450.0,
    )

    d = res.to_dict()
    assert d["frame_id"] == 42
    assert d["point_id"] == "p01"
    assert d["estimated_x"] == 10.0
    assert d["estimated_y"] == 20.0
    assert d["ground_truth_y"] == 15.0
    assert d["error_total"] == 5.0
    assert d["error_y"] == 5.0
    assert d["num_corners"] == 35
    assert d["camera_z"] == 450.0


def test_error_analyzer():
    """Kiểm tra tính sai số và thống kê bằng ErrorAnalyzer."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write("point_id,x_mm,y_mm,z_mm\n")
        f.write("p01,0,0,0\n")
        f.write("p02,100,0,0\n")
        temp_path = f.name

    try:
        gt = GroundTruthLoader(temp_path)
        analyzer = ErrorAnalyzer(gt)

        # Tính sai số cho p01: cách gốc (3, 4, 0) -> khoảng cách 5.0
        r1 = analyzer.compute_error(
            "p01",
            np.array([3.0, 4.0, 0.0]),
            {"frame_id": 1, "num_corners": 40},
        )
        assert r1 is not None
        assert pytest.approx(r1.error_total, abs=1e-4) == 5.0
        assert pytest.approx(r1.error_x, abs=1e-4) == 3.0
        assert pytest.approx(r1.error_y, abs=1e-4) == 4.0
        assert r1.num_corners == 40

        # Điểm không có trong ground truth
        r_unknown = analyzer.compute_error("p99", np.array([0, 0, 0]))
        assert r_unknown is None

        # Thêm mẫu thứ 2 cho p02: [100, 0, 0] vs [100, 6, 8] -> khoảng cách 10.0
        r2 = analyzer.compute_error("p02", np.array([100.0, 6.0, 8.0]))
        assert r2 is not None
        assert pytest.approx(r2.error_total, abs=1e-4) == 10.0

        # Kiểm tra DataFrame và summary statistics
        df = analyzer.get_dataframe()
        assert len(df) == 2

        stats = analyzer.summary_statistics()
        assert stats["n_samples"] == 2
        # Mean của 5.0 và 10.0 = 7.5
        assert pytest.approx(stats["error_total"]["mean"], abs=1e-4) == 7.5
        assert stats["error_total"]["min"] == 5.0
        assert stats["error_total"]["max"] == 10.0
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_csv_logger_and_report_generation():
    """Kiểm tra ghi log CSV và sinh báo cáo markdown."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "eval.csv"
        report_path = Path(tmpdir) / "eval_report.md"

        logger = CSVLogger(csv_path)
        with logger:
            for i in range(5):
                res = EvaluationResult(
                    timestamp=100.0 + i,
                    frame_id=i,
                    point_id="p01",
                    estimated=np.array([float(i), 0.0, 0.0]),
                    ground_truth=np.array([0.0, 0.0, 0.0]),
                    error_total=float(i),
                    error_x=float(i),
                    error_y=0.0,
                    error_z=0.0,
                    num_corners=30 + i,
                )
                logger.write(res)

        assert csv_path.exists()
        content = csv_path.read_text(encoding="utf-8")
        assert "point_id" in content
        assert "p01" in content
        assert "error_total" in content

        # Sinh báo cáo markdown
        rep_text = generate_error_report(csv_path, report_path)
        assert report_path.exists()
        assert "# Error Analysis Report" in rep_text
        assert "Total samples" in rep_text or "Tổng số mẫu" in rep_text
        assert "p01" in rep_text
