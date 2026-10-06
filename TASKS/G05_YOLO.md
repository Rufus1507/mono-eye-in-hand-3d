# PROMPT: Giai đoạn 5 - YOLO Detection & Tracking (VIẾT CODE)

## Mục tiêu
Viết `mono_eye/detect.py` hoàn chỉnh: phát hiện vật bằng YOLO, tracking, và kết hợp với pose để cho tọa độ 3D.

## Ngữ cảnh

### Module đã có
```python
# Từ G03: mono_eye/pose.py
from mono_eye.pose import CameraPose, PoseEstimator
pose = estimator.estimate(frame)

# Từ G04: mono_eye/projection.py
from mono_eye.projection import pixel_to_3d, ProjectionProcessor
success, point_3d = pixel_to_3d(pixel, pose, K, dist)
```

### Module cần cài đặt thêm
```bash
# Cài ultralytics (sẽ cài sau khi có bảng)
uv sync --group detect
```

---

## Yêu cầu code

### File: `mono_eye/detect.py`

```python
"""Giai đoạn 5 - YOLO detection, tracking, và 3D projection."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import numpy as np

# TODO: Import ultralytics khi cài
# from ultralytics import YOLO


@dataclass
class Detection:
    """Một detection từ YOLO.
    
    Attributes:
        track_id: Unique ID từ tracker (None nếu tracking tắt).
        class_id: Class ID từ model.
        class_name: Tên class.
        bbox: Bounding box [x1, y1, x2, y2] trong pixel.
        confidence: Confidence score [0, 1].
        reference_pixel: Pixel dùng làm tham chiếu cho 3D projection.
        position_3d: Tọa độ 3D (None nếu projection fail).
    """
    track_id: Optional[int]
    class_id: int
    class_name: str
    bbox: np.ndarray       # [x1, y1, x2, y2]
    confidence: float
    reference_pixel: tuple[float, float]  # (u, v)
    position_3d: Optional[np.ndarray]       # [x, y, z] mm


@dataclass
class DetectionResult:
    """Kết quả detection cho một frame.
    
    Attributes:
        timestamp: Thời gian capture.
        detections: List các Detection.
        pose: CameraPose (từ G03).
        frame_id: Frame counter.
    """
    timestamp: float
    frame_id: int
    detections: list[Detection]
    pose: Optional[CameraPose]  # None nếu không detect được pose


class ObjectDetector:
    """YOLO object detector với tracking."""
    
    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        tracking: bool = True,
        reference_type: str = "bottom_center"
    ):
        """Khởi tạo detector.
        
        Args:
            model_path: Đường dẫn model YOLO (.pt).
            conf_threshold: Confidence threshold.
            iou_threshold: IoU threshold cho NMS.
            tracking: Bật/tắt tracking.
            reference_type: "bottom_center", "center", hoặc "top_center".
        """
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.tracking = tracking
        self.reference_type = reference_type
        
        # TODO: Load model
        # self.model = YOLO(model_path)
        # if tracking:
        #     self.model.predict(..., tracker="bytetrack.yaml")
    
    def get_reference_pixel(
        self, 
        bbox: np.ndarray
    ) -> tuple[float, float]:
        """Chọn pixel tham chiếu từ bounding box.
        
        Args:
            bbox: [x1, y1, x2, y2]
            
        Returns:
            (u, v) pixel coordinates.
        """
        x1, y1, x2, y2 = bbox
        
        if self.reference_type == "bottom_center":
            u = (x1 + x2) / 2
            v = y2  # Giữa cạnh dưới (điểm chạm bàn)
        elif self.reference_type == "center":
            u = (x1 + x2) / 2
            v = (y1 + y2) / 2
        elif self.reference_type == "top_center":
            u = (x1 + x2) / 2
            v = y1
        else:
            u, v = (x1 + x2) / 2, (y1 + y2) / 2
        
        return float(u), float(v)
    
    def detect(
        self, 
        frame: np.ndarray,
        pose: Optional[CameraPose] = None,
        K: Optional[np.ndarray] = None,
        dist: Optional[np.ndarray] = None
    ) -> DetectionResult:
        """Phát hiện objects trong frame.
        
        Args:
            frame: BGR image.
            pose: CameraPose (từ G03) để project sang 3D.
            K: Camera matrix.
            dist: Distortion coefficients.
            
        Returns:
            DetectionResult.
        """
        # TODO: Run YOLO
        # results = self.model.track(frame, persist=self.tracking, ...)
        
        detections = []
        # for r in results:
        #     if r.boxes is None:
        #         continue
        #     for box, track_id, cls, conf in zip(
        #         r.boxes.xyxy, r.boxes.id, r.boxes.cls, r.boxes.conf
        #     ):
        #         # Tạo Detection object
        #         bbox = box.cpu().numpy()
        #         ref_pixel = self.get_reference_pixel(bbox)
        #         
        #         # Project sang 3D nếu có pose
        #         pos_3d = None
        #         if pose is not None and K is not None and dist is not None:
        #             success, pt = pixel_to_3d(ref_pixel, pose, K, dist)
        #             if success:
        #                 pos_3d = pt
        #         
        #         detections.append(Detection(
        #             track_id=int(track_id) if track_id else None,
        #             class_id=int(cls),
        #             class_name=self.model.names[int(cls)],
        #             bbox=bbox,
        #             confidence=float(conf),
        #             reference_pixel=ref_pixel,
        #             position_3d=pos_3d
        #         ))
        
        return DetectionResult(
            timestamp=0.0,  # TODO: set properly
            frame_id=0,
            detections=detections,
            pose=pose
        )


def create_default_detector() -> ObjectDetector:
    """Tạo detector với settings mặc định."""
    return ObjectDetector(
        model_path="yolov8n.pt",
        conf_threshold=0.25,
        tracking=True,
        reference_type="bottom_center"
    )
```

---

## Pipeline Integration

### File: `mono_eye/pipeline.py` (mới)

```python
"""Full pipeline: Camera → Pose → Detection → 3D Projection."""
from __future__ import annotations

import time
import cv2
import numpy as np

from mono_eye.camera_io import CameraModel, load_camera_yaml
from mono_eye.pose import PoseEstimator, CameraPose
from mono_eye.projection import ProjectionProcessor
from mono_eye.detect import ObjectDetector, DetectionResult


class MonoEyePipeline:
    """Full pipeline cho monocular eye-in-hand localization."""
    
    def __init__(
        self,
        camera_config: str = "data/calib/camera.yaml",
        board_config: str = "bang_calib_A4.yaml",
        detector_config: dict | None = None
    ):
        """Khởi tạo pipeline.
        
        Args:
            camera_config: Đường dẫn camera.yaml.
            board_config: Đường dẫn board config.
            detector_config: Config cho ObjectDetector.
        """
        # Load camera
        self.camera = load_camera_yaml(camera_config)
        
        # Initialize pose estimator
        self.pose_estimator = PoseEstimator(
            camera=self.camera,
            board_config=board_config
        )
        
        # Initialize projection processor
        self.projection = ProjectionProcessor(
            K=self.camera.K,
            dist=self.camera.dist,
            plane_z=0.0
        )
        
        # Initialize detector (tùy chọn)
        self.detector = None
        if detector_config:
            self.detector = ObjectDetector(**detector_config)
        
        self.frame_id = 0
    
    def process_frame(
        self, 
        frame: np.ndarray,
        detect_objects: bool = True
    ) -> tuple[CameraPose, DetectionResult | None]:
        """Xử lý một frame.
        
        Args:
            frame: BGR image.
            detect_objects: Có chạy detection không.
            
        Returns:
            (pose, detection_result)
        """
        # Step 1: Estimate pose
        pose = self.pose_estimator.estimate(frame)
        
        # Step 2: Detect objects (nếu cần)
        detections = None
        if detect_objects and self.detector and pose.valid:
            detections = self.detector.detect(
                frame, 
                pose=pose,
                K=self.camera.K,
                dist=self.camera.dist
            )
            detections.frame_id = self.frame_id
            detections.timestamp = time.perf_counter()
        
        self.frame_id += 1
        return pose, detections
    
    def process_video(
        self,
        video_path: str,
        output_path: str | None = None
    ) -> list[DetectionResult]:
        """Process video file.
        
        Args:
            video_path: Đường dẫn video.
            output_path: Đường dẫn output video (tùy chọn).
            
        Returns:
            List DetectionResults.
        """
        cap = cv2.VideoCapture(video_path)
        results = []
        
        writer = None
        if output_path:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(output_path, fourcc, 30, (1280, 720))
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            pose, detections = self.process_frame(frame)
            
            # Vẽ debug info
            if pose.valid:
                # Vẽ trục
                cv2.drawFrameAxes(
                    frame, self.camera.K, self.camera.dist,
                    pose.rvec, pose.tvec, 50
                )
                # Vẽ số góc, error
                text = f"Corners: {pose.num_corners}, Error: {pose.reproj_error_px:.2f}px"
                cv2.putText(frame, text, (10, 30), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            if writer:
                writer.write(frame)
            
            results.append(detections)
        
        cap.release()
        if writer:
            writer.release()
        
        return results
```

---

## Unit Tests

### File: `tests/test_detect.py`

```python
"""Tests cho detection module."""
import pytest
import numpy as np


def test_reference_pixel_bottom_center():
    """Test bottom_center reference pixel."""
    from mono_eye.detect import ObjectDetector
    
    detector = ObjectDetector(reference_type="bottom_center")
    bbox = np.array([100, 100, 200, 200])  # [x1, y1, x2, y2]
    
    ref = detector.get_reference_pixel(bbox)
    
    # Center of bottom edge: ((100+200)/2, 200)
    assert ref == (150.0, 200.0)


def test_reference_pixel_center():
    """Test center reference pixel."""
    from mono_eye.detect import ObjectDetector
    
    detector = ObjectDetector(reference_type="center")
    bbox = np.array([100, 100, 200, 200])
    
    ref = detector.get_reference_pixel(bbox)
    
    assert ref == (150.0, 150.0)


def test_detection_result_dataclass():
    """Test DetectionResult dataclass."""
    from mono_eye.detect import Detection, DetectionResult
    from mono_eye.pose import CameraPose
    
    pose = CameraPose(valid=True, rvec=np.zeros(3), tvec=np.array([0, 0, 100]))
    
    detection = Detection(
        track_id=1,
        class_id=0,
        class_name="person",
        bbox=np.array([100, 100, 200, 200]),
        confidence=0.95,
        reference_pixel=(150.0, 200.0),
        position_3d=np.array([50, 50, 0])
    )
    
    result = DetectionResult(
        timestamp=1.0,
        frame_id=1,
        detections=[detection],
        pose=pose
    )
    
    assert len(result.detections) == 1
    assert result.detections[0].track_id == 1


# TODO: Tests với mock YOLO (không cần model thật)
def test_detection_with_mock_yolo():
    """Test detection với mock YOLO."""
    # Mock YOLO results
    pass
```

---

## Tiêu chí hoàn thành

- [x] `mono_eye/detect.py` viết hoàn chỉnh
- [x] `Detection` và `DetectionResult` dataclasses
- [x] `ObjectDetector` class với:
  - [x] YOLO integration (stub OK)
  - [x] Tracking support
  - [x] Reference pixel selection
- [x] `mono_eye/pipeline.py` viết hoàn chỉnh
- [x] `MonoEyePipeline` class
- [x] `tests/test_detect.py` viết và pass
- [x] Code có docstrings rõ ràng

---

## Commands

```bash
# Cài ultralytics (khi cần)
uv sync --group detect

# Chạy tests
uv run pytest tests/test_detect.py -v

# Import test
uv run python -c "from mono_eye.detect import ObjectDetector; print('OK')"
uv run python -c "from mono_eye.pipeline import MonoEyePipeline; print('OK')"
```

---

## Lưu ý

### YOLO Model Options

| Model | Size | Speed | Accuracy |
|-------|------|-------|----------|
| yolov8n.pt | 3.9MB | Fastest | OK |
| yolov8s.pt | 11.4MB | Fast | Better |
| yolov8m.pt | 26.3MB | Medium | Good |
| Custom | ? | ? | Depends |

### Custom Training

Nếu cần detect vật không có sẵn:
1. Chụp 100-500 ảnh vật
2. Label bằng LabelImg
3. Train: `yolo detect train data=data.yaml model=yolov8n.pt epochs=50`

---

## Output mong đợi

1. **File `mono_eye/detect.py`** viết hoàn chỉnh
2. **File `mono_eye/pipeline.py`** viết hoàn chỉnh
3. **File `tests/test_detect.py`** với ≥ 3 tests
4. **Kết quả tests:** `pytest tests/test_detect.py -v` → passed
