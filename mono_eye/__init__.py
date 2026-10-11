"""mono_eye: tọa độ 3D trên mặt bàn từ MỘT camera (dùng tấm ChArUco làm mốc).

Dùng lại phần hiệu chuẩn của fov_tool (board, detect, camera.yaml); không sửa fov_tool.
"""

__version__ = "0.1.0"

from mono_eye.chess_detectors import CHESS_PIECE_LABELS, ChessPieceDetector
from mono_eye.chess_pipeline import ChessMonoEyePipeline, ChessResult
from mono_eye.detect import Detection, DetectionResult, ObjectDetector
from mono_eye.evaluate import (
    CSVLogger,
    ErrorAnalyzer,
    EvaluationResult,
    GroundTruthLoader,
    generate_error_report,
)
from mono_eye.filter import (
    KalmanTracker3D,
    TemporalSmoother,
    aggregate_observations,
    filter_parallel_ray,
    triangulate_two_views,
)
from mono_eye.pipeline import MonoEyePipeline
from mono_eye.pose import CameraPose, PoseEstimator
from mono_eye.projection import ProjectionProcessor, pixel_to_3d
from mono_eye.viz import (
    CameraView,
    Open3DVisualizer,
    SceneObject,
    SimpleVisualizer,
    TablePlane,
    create_visualizer,
)

__all__ = [
    "CHESS_PIECE_LABELS",
    "CSVLogger",
    "CameraPose",
    "CameraView",
    "ChessMonoEyePipeline",
    "ChessPieceDetector",
    "ChessResult",
    "Detection",
    "DetectionResult",
    "ErrorAnalyzer",
    "EvaluationResult",
    "GroundTruthLoader",
    "KalmanTracker3D",
    "MonoEyePipeline",
    "ObjectDetector",
    "Open3DVisualizer",
    "PoseEstimator",
    "ProjectionProcessor",
    "SceneObject",
    "SimpleVisualizer",
    "TablePlane",
    "TemporalSmoother",
    "aggregate_observations",
    "create_visualizer",
    "filter_parallel_ray",
    "generate_error_report",
    "pixel_to_3d",
    "triangulate_two_views",
    "__version__",
]



