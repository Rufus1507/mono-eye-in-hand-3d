# PROMPT: Giai đoạn 7 - Error Analysis (VIẾT CODE)

## Mục tiêu
Viết `mono_eye/evaluate.py` và infrastructure cho phân tích sai số.

## Ngữ cảnh

### Module đã có
```python
# Từ G05: mono_eye/detect.py
from mono_eye.detect import Detection, DetectionResult
detection.position_3d  # Tọa độ ước lượng
# Ground truth: đọc từ configs/ground_truth_points.csv
```

### Cần phân tích
```python
# Ước lượng vs Ground Truth
error = np.linalg.norm(position_3d - ground_truth)
error_x = position_3d[0] - ground_truth[0]
error_y = position_3d[1] - ground_truth[1]
error_z = position_3d[2] - ground_truth[2]
```

---

## Yêu cầu code

### File: `mono_eye/evaluate.py`

```python
"""Giai đoạn 7 - Error analysis và logging."""
from __future__ import annotations

import csv
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import numpy as np
import pandas as pd


@dataclass
class EvaluationResult:
    """Kết quả đánh giá cho một điểm.
    
    Attributes:
        timestamp: Thời gian.
        frame_id: Frame ID.
        point_id: ID của điểm ground truth.
        estimated: Tọa độ ước lượng.
        ground_truth: Tọa độ thật.
        error_total: Euclidean error (mm).
        error_x, error_y, error_z: Error theo từng trục.
        
        # Metadata
        num_corners: Số góc ChArUco phát hiện.
        reproj_error: Reprojection error (px).
        camera_position: Vị trí camera.
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
    
    # Metadata
    num_corners: int = 0
    reproj_error_px: float = float('inf')
    camera_x: float = 0.0
    camera_y: float = 0.0
    camera_z: float = 0.0
    
    def to_dict(self) -> dict:
        """Convert sang dict cho CSV."""
        return {
            'timestamp': self.timestamp,
            'frame_id': self.frame_id,
            'point_id': self.point_id,
            'estimated_x': self.estimated[0],
            'estimated_y': self.estimated[1],
            'estimated_z': self.estimated[2],
            'ground_truth_x': self.ground_truth[0],
            'ground_truth_y': self.ground_truth[1],
            'ground_truth_z': self.ground_truth[2],
            'error_total': self.error_total,
            'error_x': self.error_x,
            'error_y': self.error_y,
            'error_z': self.error_z,
            'num_corners': self.num_corners,
            'reproj_error_px': self.reproj_error_px,
            'camera_x': self.camera_x,
            'camera_y': self.camera_y,
            'camera_z': self.camera_z,
        }


class GroundTruthLoader:
    """Loader cho ground truth points."""
    
    def __init__(self, csv_path: str | Path):
        """Khởi tạo loader.
        
        Args:
            csv_path: Đường dẫn file ground_truth_points.csv.
        """
        self.csv_path = Path(csv_path)
        self.points = self._load()
    
    def _load(self) -> dict[str, np.ndarray]:
        """Load ground truth points từ CSV."""
        points = {}
        
        with open(self.csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                point_id = row['point_id']
                x = float(row['x_mm'])
                y = float(row['y_mm'])
                z = float(row.get('z_mm', 0.0))
                points[point_id] = np.array([x, y, z])
        
        return points
    
    def get_point(self, point_id: str) -> np.ndarray | None:
        """Lấy tọa độ ground truth của một điểm."""
        return self.points.get(point_id)
    
    def get_all_points(self) -> dict[str, np.ndarray]:
        """Lấy tất cả points."""
        return self.points.copy()


class ErrorAnalyzer:
    """Analyzer cho error analysis."""
    
    def __init__(self, ground_truth: GroundTruthLoader):
        """Khởi tạo.
        
        Args:
            ground_truth: GroundTruthLoader instance.
        """
        self.ground_truth = ground_truth
        self.results: list[EvaluationResult] = []
    
    def add_result(self, result: EvaluationResult):
        """Thêm một kết quả."""
        self.results.append(result)
    
    def compute_error(
        self,
        point_id: str,
        estimated: np.ndarray,
        metadata: dict | None = None
    ) -> Optional[EvaluationResult]:
        """Tính error cho một điểm.
        
        Args:
            point_id: ID của điểm ground truth.
            estimated: Tọa độ ước lượng.
            metadata: Thông tin bổ sung.
            
        Returns:
            EvaluationResult hoặc None nếu không có ground truth.
        """
        gt = self.ground_truth.get_point(point_id)
        if gt is None:
            return None
        
        # Tính error
        error_total = np.linalg.norm(estimated - gt)
        error_x = estimated[0] - gt[0]
        error_y = estimated[1] - gt[1]
        error_z = estimated[2] - gt[2]
        
        result = EvaluationResult(
            timestamp=time.time(),
            frame_id=metadata.get('frame_id', 0) if metadata else 0,
            point_id=point_id,
            estimated=estimated,
            ground_truth=gt,
            error_total=error_total,
            error_x=error_x,
            error_y=error_y,
            error_z=error_z,
            num_corners=metadata.get('num_corners', 0) if metadata else 0,
            reproj_error_px=metadata.get('reproj_error_px', float('inf')) if metadata else float('inf'),
            camera_x=metadata.get('camera_x', 0.0) if metadata else 0.0,
            camera_y=metadata.get('camera_y', 0.0) if metadata else 0.0,
            camera_z=metadata.get('camera_z', 0.0) if metadata else 0.0,
        )
        
        self.add_result(result)
        return result
    
    def get_dataframe(self) -> pd.DataFrame:
        """Convert results sang DataFrame."""
        if not self.results:
            return pd.DataFrame()
        
        return pd.DataFrame([r.to_dict() for r in self.results])
    
    def summary_statistics(self) -> dict:
        """Tính summary statistics.
        
        Returns:
            Dict với các statistics.
        """
        df = self.get_dataframe()
        if df.empty:
            return {}
        
        stats = {
            'n_samples': len(df),
            'error_total': {
                'mean': df['error_total'].mean(),
                'median': df['error_total'].median(),
                'std': df['error_total'].std(),
                'min': df['error_total'].min(),
                'max': df['error_total'].max(),
                'p95': df['error_total'].quantile(0.95),
            },
            'error_x': {
                'mean': df['error_x'].mean(),
                'std': df['error_x'].std(),
            },
            'error_y': {
                'mean': df['error_y'].mean(),
                'std': df['error_y'].std(),
            },
            'error_z': {
                'mean': df['error_z'].mean(),
                'std': df['error_z'].std(),
            },
        }
        
        return stats
    
    def group_by(self, column: str) -> pd.DataFrame:
        """Group results by column."""
        df = self.get_dataframe()
        if df.empty:
            return pd.DataFrame()
        
        return df.groupby(column).agg({
            'error_total': ['mean', 'median', 'std', 'count']
        })


class CSVLogger:
    """Logger để ghi results ra CSV."""
    
    def __init__(self, output_path: str | Path):
        """Khởi tạo.
        
        Args:
            output_path: Đường dẫn file output CSV.
        """
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._writer = None
        self._file = None
    
    def __enter__(self):
        """Context manager entry."""
        self._file = open(self.output_path, 'w', newline='')
        if self.results:
            self._writer = csv.DictWriter(self._file, fieldnames=self.results[0].keys())
            self._writer.writeheader()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self._file:
            self._file.close()
    
    @property
    def fieldnames(self) -> list[str]:
        """CSV fieldnames."""
        return [
            'timestamp', 'frame_id', 'point_id',
            'estimated_x', 'estimated_y', 'estimated_z',
            'ground_truth_x', 'ground_truth_y', 'ground_truth_z',
            'error_total', 'error_x', 'error_y', 'error_z',
            'num_corners', 'reproj_error_px',
            'camera_x', 'camera_y', 'camera_z',
        ]
    
    def write(self, result: EvaluationResult):
        """Ghi một result."""
        if self._writer is None:
            self._file = open(self.output_path, 'w', newline='')
            self._writer = csv.DictWriter(self._file, fieldnames=self.fieldnames)
            self._writer.writeheader()
        
        self._writer.writerow(result.to_dict())
    
    def close(self):
        """Đóng file."""
        if self._file:
            self._file.close()
            self._file = None
            self._writer = None


def generate_error_report(
    csv_path: str | Path,
    output_path: str | Path,
    ground_truth_path: str | Path
):
    """Generate error report từ CSV data.
    
    Args:
        csv_path: Input CSV.
        output_path: Output HTML/MD report.
        ground_truth_path: Ground truth points.
    """
    # Load data
    df = pd.read_csv(csv_path)
    
    # Compute statistics
    gt_loader = GroundTruthLoader(ground_truth_path)
    
    # Summary
    summary = {
        'total_samples': len(df),
        'mean_error': df['error_total'].mean(),
        'median_error': df['error_total'].median(),
        'std_error': df['error_total'].std(),
        'p95_error': df['error_total'].quantile(0.95),
        'max_error': df['error_total'].max(),
    }
    
    # Group by point_id
    by_point = df.groupby('point_id')['error_total'].agg(['mean', 'std', 'count'])
    
    # Group by num_corners (quality indicator)
    by_quality = df.groupby('num_corners')['error_total'].agg(['mean', 'median', 'count'])
    
    # Generate markdown report
    report = f"""# Error Analysis Report

## Summary
- Total samples: {summary['total_samples']}
- Mean error: {summary['mean_error']:.3f} mm
- Median error: {summary['median_error']:.3f} mm
- Std deviation: {summary['std_error']:.3f} mm
- 95th percentile: {summary['p95_error']:.3f} mm
- Max error: {summary['max_error']:.3f} mm

## Error by Point

| Point ID | Mean Error (mm) | Std | Count |
|-----------|----------------|-----|-------|
"""
    
    for point_id, row in by_point.iterrows():
        report += f"| {point_id} | {row['mean']:.3f} | {row['std']:.3f} | {int(row['count'])} |\n"
    
    report += """
## Error by Quality (Number of Corners)

| Corners | Mean Error | Median | Count |
|---------|------------|--------|-------|
"""
    
    for corners, row in by_quality.iterrows():
        report += f"| {corners} | {row['mean']:.3f} | {row['median']:.3f} | {int(row['count'])} |\n"
    
    # Write report
    Path(output_path).write_text(report)
    print(f"Report saved to: {output_path}")
```

---

## Unit Tests

### File: `tests/test_evaluate.py`

```python
"""Tests cho evaluation module."""
import pytest
import numpy as np
import tempfile
from pathlib import Path


def test_ground_truth_loader():
    """Test ground truth loader."""
    from mono_eye.evaluate import GroundTruthLoader
    
    # Create temp CSV
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("point_id,x_mm,y_mm,z_mm\n")
        f.write("p01,0,0,0\n")
        f.write("p02,100,0,0\n")
        f.write("p03,0,100,0\n")
        temp_path = f.name
    
    try:
        loader = GroundTruthLoader(temp_path)
        
        assert loader.get_point("p01") is not None
        assert np.allclose(loader.get_point("p01"), [0, 0, 0])
        assert np.allclose(loader.get_point("p02"), [100, 0, 0])
        assert loader.get_point("p99") is None
    finally:
        Path(temp_path).unlink()


def test_evaluation_result_to_dict():
    """Test EvaluationResult.to_dict()."""
    from mono_eye.evaluate import EvaluationResult
    
    result = EvaluationResult(
        timestamp=1.0,
        frame_id=1,
        point_id="p01",
        estimated=np.array([1.0, 2.0, 0.0]),
        ground_truth=np.array([0.0, 0.0, 0.0]),
        error_total=2.236,
        error_x=1.0,
        error_y=2.0,
        error_z=0.0,
    )
    
    d = result.to_dict()
    
    assert d['point_id'] == "p01"
    assert d['estimated_x'] == 1.0
    assert d['ground_truth_x'] == 0.0
    assert abs(d['error_total'] - 2.236) < 0.01


def test_error_analyzer():
    """Test ErrorAnalyzer."""
    from mono_eye.evaluate import GroundTruthLoader, ErrorAnalyzer
    
    # Create temp ground truth
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("point_id,x_mm,y_mm,z_mm\n")
        f.write("p01,0,0,0\n")
        f.write("p02,100,0,0\n")
        temp_path = f.name
    
    try:
        gt = GroundTruthLoader(temp_path)
        analyzer = ErrorAnalyzer(gt)
        
        # Add result
        result = analyzer.compute_error(
            "p01",
            np.array([5.0, 5.0, 0.0])
        )
        
        assert result is not None
        assert abs(result.error_total - 7.07) < 0.1
        assert len(analyzer.results) == 1
        
        # DataFrame
        df = analyzer.get_dataframe()
        assert len(df) == 1
        
        # Summary
        summary = analyzer.summary_statistics()
        assert summary['n_samples'] == 1
    finally:
        Path(temp_path).unlink()


def test_csv_logger():
    """Test CSVLogger."""
    from mono_eye.evaluate import EvaluationResult, CSVLogger
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test.csv"
        
        result = EvaluationResult(
            timestamp=1.0,
            frame_id=1,
            point_id="p01",
            estimated=np.array([1.0, 2.0, 0.0]),
            ground_truth=np.array([0.0, 0.0, 0.0]),
            error_total=2.236,
            error_x=1.0,
            error_y=2.0,
            error_z=0.0,
        )
        
        logger = CSVLogger(output_path)
        logger.write(result)
        logger.close()
        
        # Verify
        assert output_path.exists()
        content = output_path.read_text()
        assert "point_id" in content
        assert "p01" in content
```

---

## Script: `scripts/run_evaluation.py`

```python
"""Script chạy evaluation."""
import argparse
import numpy as np
from pathlib import Path

from mono_eye.camera_io import load_camera_yaml
from mono_eye.pose import PoseEstimator
from mono_eye.projection import ProjectionProcessor
from mono_eye.evaluate import GroundTruthLoader, ErrorAnalyzer, CSVLogger


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", default="data/calib/camera.yaml")
    parser.add_argument("--board", default="bang_calib_A4.yaml")
    parser.add_argument("--ground-truth", default="configs/ground_truth_points.csv")
    parser.add_argument("--output", default="results/logs/evaluation.csv")
    args = parser.parse_args()
    
    # Load
    cam = load_camera_yaml(args.camera)
    gt_loader = GroundTruthLoader(args.ground_truth)
    analyzer = ErrorAnalyzer(gt_loader)
    logger = CSVLogger(args.output)
    
    print(f"Ground truth points: {len(gt_loader.points)}")
    print(f"Output: {args.output}")
    
    # TODO: Load frames, estimate pose, project, compute error
    # For now, just show that modules work
    
    print("Evaluation setup complete. Ready for data collection.")


if __name__ == "__main__":
    main()
```

---

## Tiêu chí hoàn thành

- [x] `mono_eye/evaluate.py` viết hoàn chỉnh
- [x] `GroundTruthLoader` class
- [x] `ErrorAnalyzer` class
- [x] `CSVLogger` class
- [x] `EvaluationResult` dataclass
- [x] `generate_error_report()` function
- [x] `tests/test_evaluate.py` viết và pass
- [x] `scripts/run_evaluation.py` tạo được

---

## Commands

```bash
# Chạy tests
uv run pytest tests/test_evaluate.py -v

# Import test
uv run python -c "from mono_eye.evaluate import ErrorAnalyzer; print('OK')"

# Run evaluation script
uv run python scripts/run_evaluation.py --ground-truth configs/ground_truth_points.csv
```

---

## Output mong đợi

1. **File `mono_eye/evaluate.py`** viết hoàn chỉnh
2. **File `tests/test_evaluate.py`** với ≥ 4 tests
3. **File `scripts/run_evaluation.py`**
4. **Kết quả tests:** `pytest tests/test_evaluate.py -v` → passed
