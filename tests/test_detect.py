"""Unit tests cho mono_eye/detect.py và mono_eye/pipeline.py."""
from types import SimpleNamespace
import numpy as np
import pytest

from mono_eye.camera_io import CameraModel
from mono_eye.config import ROOT
from mono_eye.detect import Detection, DetectionResult, ObjectDetector
from mono_eye.pipeline import MonoEyePipeline
from mono_eye.pose import CameraPose

BOARD_CONFIG = ROOT / "bang_calib_A4.yaml"


@pytest.fixture
def dummy_camera():
    """Tạo CameraModel chuẩn 1280x720."""
    K = np.array(
        [[1000.0, 0.0, 640.0], [0.0, 1000.0, 360.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    dist = np.zeros(5, dtype=np.float64)
    return CameraModel(K=K, dist=dist, width=1280, height=720)


class MockBoxes:
    """Mock boxes structure tương thích ultralytics Results.boxes."""

    def __init__(self, xyxy, conf, cls, ids=None):
        self.xyxy = np.asarray(xyxy, dtype=np.float64)
        self.conf = np.asarray(conf, dtype=np.float64)
        self.cls = np.asarray(cls, dtype=np.int32)
        self.id = np.asarray(ids, dtype=np.int32) if ids is not None else None

    def __len__(self):
        return len(self.xyxy)


class MockYOLO:
    """Mock YOLO model trả về các bounding boxes định sẵn mà không cần weights."""

    def __init__(self, boxes=None, names=None):
        self.boxes = boxes or MockBoxes(
            xyxy=[[590.0, 310.0, 690.0, 360.0]],  # bottom center tại (640, 360)
            conf=[0.92],
            cls=[0],
            ids=[1],
        )
        self.names = names or {0: "cup", 1: "bottle"}

    def __call__(self, frame, **kwargs):
        return [SimpleNamespace(boxes=self.boxes)]

    def track(self, frame, **kwargs):
        return [SimpleNamespace(boxes=self.boxes)]


def test_reference_pixel_bottom_center():
    """Test điểm tham chiếu giữa cạnh dưới (chân vật tiếp xúc bàn)."""
    detector = ObjectDetector(reference_type="bottom_center")
    bbox = np.array([100.0, 100.0, 200.0, 200.0])

    ref = detector.get_reference_pixel(bbox)
    # u = (100+200)/2 = 150, v = 200 (cạnh đáy)
    assert ref == (150.0, 200.0)


def test_reference_pixel_center():
    """Test điểm tham chiếu tâm box."""
    detector = ObjectDetector(reference_type="center")
    bbox = np.array([100.0, 100.0, 200.0, 200.0])

    ref = detector.get_reference_pixel(bbox)
    assert ref == (150.0, 150.0)


def test_reference_pixel_top_center():
    """Test điểm tham chiếu giữa cạnh trên."""
    detector = ObjectDetector(reference_type="top_center")
    bbox = np.array([100.0, 100.0, 200.0, 200.0])

    ref = detector.get_reference_pixel(bbox)
    assert ref == (150.0, 100.0)


def test_detection_result_dataclass():
    """Test cấu trúc dataclass Detection và DetectionResult."""
    pose = CameraPose(valid=True, rvec=np.zeros(3), tvec=np.array([0.0, 0.0, 100.0]))

    det = Detection(
        track_id=1,
        class_id=0,
        class_name="cup",
        bbox=np.array([100.0, 100.0, 200.0, 200.0]),
        confidence=0.95,
        reference_pixel=(150.0, 200.0),
        position_3d=np.array([50.0, 50.0, 0.0]),
    )

    res = DetectionResult(
        timestamp=1.23,
        frame_id=42,
        detections=[det],
        pose=pose,
    )

    assert res.frame_id == 42
    assert len(res.detections) == 1
    assert res.detections[0].track_id == 1
    assert res.detections[0].class_name == "cup"
    assert np.allclose(res.detections[0].position_3d, [50.0, 50.0, 0.0])


def test_detection_with_mock_yolo(dummy_camera):
    """Test ObjectDetector phát hiện vật và tính toán tọa độ 3D với Mock YOLO."""
    mock_model = MockYOLO()
    detector = ObjectDetector(
        reference_type="bottom_center",
        tracking=True,
        model=mock_model,
    )

    frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    # Pose: camera đặt ở độ cao 500 mm nhìn chúc xuống mặt bàn z=0
    rvec = np.array([np.pi, 0.0, 0.0], dtype=np.float64)
    tvec = np.array([0.0, 0.0, 500.0], dtype=np.float64)
    pose = CameraPose(valid=True, rvec=rvec, tvec=tvec, num_corners=20)

    res = detector.detect(
        frame=frame,
        pose=pose,
        K=dummy_camera.K,
        dist=dummy_camera.dist,
        plane_z=0.0,
        frame_id=1,
    )

    assert len(res.detections) == 1
    d = res.detections[0]
    assert d.track_id == 1
    assert d.class_name == "cup"
    assert d.reference_pixel == (640.0, 360.0)  # Tâm quang học
    assert d.position_3d is not None
    # Chiếu tâm quang học (640, 360) với camera ở (0, 0, 500) phải rơi trúng [0, 0, 0] mm
    assert np.allclose(d.position_3d, [0.0, 0.0, 0.0], atol=1e-4)


def test_pipeline_initialization(dummy_camera):
    """Test khởi tạo MonoEyePipeline với CameraModel đã nạp sẵn."""
    pipeline = MonoEyePipeline(
        camera=dummy_camera,
        board_config=BOARD_CONFIG,
    )

    assert pipeline.camera is dummy_camera
    assert pipeline.pose_estimator is not None
    assert pipeline.projection is not None
    assert pipeline.detector is None
    assert pipeline.frame_id == 0


def test_pipeline_process_frame(dummy_camera):
    """Test quy trình pipeline xử lý frame tích hợp."""
    mock_detector = ObjectDetector(model=MockYOLO())
    pipeline = MonoEyePipeline(
        camera=dummy_camera,
        board_config=BOARD_CONFIG,
        detector=mock_detector,
    )

    blank_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    pose, detections = pipeline.process_frame(blank_frame, detect_objects=True)

    # Khung hình đen -> pose invalid
    assert not pose.valid
    # Detections vẫn chạy được
    assert detections is not None
    assert len(detections.detections) == 1
    # Vì pose invalid nên position_3d = None
    assert detections.detections[0].position_3d is None
    assert pipeline.frame_id == 1
