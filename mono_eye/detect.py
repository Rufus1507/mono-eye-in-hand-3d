"""Giai đoạn 5 - YOLO detection, tracking, và 3D projection."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any, Optional, Sequence, Tuple

import cv2
import numpy as np

from mono_eye.pose import CameraPose
from mono_eye.projection import pixel_to_3d

try:
    from ultralytics import YOLO
    HAS_ULTRALYTICS = True
except ImportError:
    YOLO = None
    HAS_ULTRALYTICS = False


@dataclass
class Detection:
    """Một đối tượng phát hiện từ YOLO.

    Attributes:
        track_id: ID theo dõi duy nhất từ tracker (None nếu tắt tracking).
        class_id: ID lớp đối tượng từ mô hình.
        class_name: Tên lớp đối tượng (ví dụ: 'box', 'cup', 'bottle').
        bbox: Tọa độ bounding box [x1, y1, x2, y2] trong không gian ảnh pixel.
        confidence: Độ tin cậy dự đoán trong khoảng [0, 1].
        reference_pixel: Tọa độ pixel (u, v) dùng làm mốc chiếu sang không gian 3D.
        position_3d: Tọa độ 3D [x, y, z] trong world frame (mm), hoặc None nếu chiếu thất bại.
    """

    track_id: Optional[int]
    class_id: int
    class_name: str
    bbox: np.ndarray  # [x1, y1, x2, y2]
    confidence: float
    reference_pixel: tuple[float, float]  # (u, v)
    position_3d: Optional[np.ndarray] = None  # [x, y, z] mm


@dataclass
class DetectionResult:
    """Kết quả phát hiện và định vị 3D của một khung hình.

    Attributes:
        timestamp: Mốc thời gian xử lý khung hình.
        frame_id: Chỉ số thứ tự khung hình.
        detections: Danh sách các đối tượng Detection.
        pose: CameraPose của khung hình (None nếu không ước lượng được pose).
    """

    timestamp: float
    frame_id: int
    detections: list[Detection]
    pose: Optional[CameraPose] = None


class ObjectDetector:
    """Bộ phát hiện đối tượng YOLO tích hợp tracking và tính điểm tham chiếu."""

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        tracking: bool = True,
        reference_type: str = "bottom_center",
        model: Any = None,
    ):
        """Khởi tạo ObjectDetector.

        Args:
            model_path: Đường dẫn tới trọng số YOLO (.pt).
            conf_threshold: Ngưỡng độ tin cậy để lọc box.
            iou_threshold: Ngưỡng IoU cho NMS.
            tracking: Bật/tắt chế độ theo dõi đối tượng (ByteTrack/BoT-SORT).
            reference_type: Kiểu chọn điểm tham chiếu: "bottom_center" (chân vật tiếp xúc bàn),
                            "center" (tâm box), hoặc "top_center".
            model: Instance model đã tải sẵn (hoặc mock model để kiểm thử).
        """
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.tracking = tracking
        self.reference_type = reference_type

        self._model = model

    @property
    def model(self) -> Any:
        """Tải mô hình YOLO theo phương thức lazy loading."""
        if self._model is None:
            if not HAS_ULTRALYTICS:
                raise ImportError(
                    "Thư viện 'ultralytics' chưa được cài đặt. "
                    "Hãy chạy: uv sync --group detect"
                )
            self._model = YOLO(self.model_path)
        return self._model

    def get_reference_pixel(
        self,
        bbox: np.ndarray | Sequence[float],
    ) -> tuple[float, float]:
        """Chọn điểm pixel tham chiếu từ bounding box của vật thể.

        Quy ước chọn điểm:
        - "bottom_center": Điểm giữa của cạnh dưới (x1+x2)/2, y2.
          Đây là điểm vật thể chạm mặt bàn z = 0, phù hợp nhất với phép giao tia mặt bàn.
        - "center": Điểm chính giữa bounding box.
        - "top_center": Điểm giữa cạnh trên.

        Args:
            bbox: [x1, y1, x2, y2] dạng numpy array hoặc sequence.

        Returns:
            (u, v) tọa độ pixel dạng float.
        """
        x1, y1, x2, y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])

        if self.reference_type == "bottom_center":
            u = (x1 + x2) / 2.0
            v = y2
        elif self.reference_type == "center":
            u = (x1 + x2) / 2.0
            v = (y1 + y2) / 2.0
        elif self.reference_type == "top_center":
            u = (x1 + x2) / 2.0
            v = y1
        else:
            u = (x1 + x2) / 2.0
            v = (y1 + y2) / 2.0

        return float(u), float(v)

    def detect(
        self,
        frame: np.ndarray,
        pose: Optional[CameraPose] = None,
        K: Optional[np.ndarray] = None,
        dist: Optional[np.ndarray] = None,
        plane_z: float = 0.0,
        frame_id: int = 0,
        timestamp: Optional[float] = None,
    ) -> DetectionResult:
        """Phát hiện các vật thể trên khung hình và chiếu sang tọa độ 3D nếu có pose.

        Args:
            frame: Ảnh camera numpy array (BGR).
            pose: CameraPose của camera tại thời điểm frame được chụp.
            K: Ma trận nội tham số camera 3x3.
            dist: Hệ số méo camera.
            plane_z: Độ cao mặt phẳng bàn (mm, mặc định 0.0).
            frame_id: Số thứ tự khung hình.
            timestamp: Thời gian đo (mặc định lấy time.perf_counter()).

        Returns:
            DetectionResult chứa danh sách Detection và tọa độ 3D.
        """
        t0 = time.perf_counter() if timestamp is None else timestamp
        detections: list[Detection] = []

        # Chạy dự đoán hoặc tracking với mô hình
        if self.tracking and hasattr(self.model, "track"):
            results = self.model.track(
                frame,
                conf=self.conf_threshold,
                iou=self.iou_threshold,
                persist=True,
                verbose=False,
            )
        else:
            results = self.model(
                frame,
                conf=self.conf_threshold,
                iou=self.iou_threshold,
                verbose=False,
            )

        names = getattr(self.model, "names", {})

        for r in results:
            boxes = getattr(r, "boxes", None)
            if boxes is None or len(boxes) == 0:
                continue

            xyxy = boxes.xyxy
            if hasattr(xyxy, "cpu"):
                xyxy = xyxy.cpu().numpy()
            else:
                xyxy = np.asarray(xyxy)

            conf_arr = boxes.conf
            if hasattr(conf_arr, "cpu"):
                conf_arr = conf_arr.cpu().numpy()
            else:
                conf_arr = np.asarray(conf_arr)

            cls_arr = boxes.cls
            if hasattr(cls_arr, "cpu"):
                cls_arr = cls_arr.cpu().numpy()
            else:
                cls_arr = np.asarray(cls_arr)

            id_arr = getattr(boxes, "id", None)
            if id_arr is not None:
                if hasattr(id_arr, "cpu"):
                    id_arr = id_arr.cpu().numpy()
                else:
                    id_arr = np.asarray(id_arr)

            for idx, box in enumerate(xyxy):
                conf = float(conf_arr[idx])
                cls_id = int(cls_arr[idx])
                cls_name = names.get(cls_id, str(cls_id)) if isinstance(names, dict) else str(cls_id)
                track_id = int(id_arr[idx]) if id_arr is not None and id_arr[idx] is not None else None

                bbox_coords = np.asarray(box, dtype=np.float64)
                ref_pixel = self.get_reference_pixel(bbox_coords)

                # Chiếu sang không gian 3D nếu pose hợp lệ và có thông số camera
                pos_3d: Optional[np.ndarray] = None
                if (
                    pose is not None
                    and pose.valid
                    and K is not None
                    and dist is not None
                ):
                    success, pt = pixel_to_3d(
                        ref_pixel,
                        pose,
                        K,
                        dist,
                        plane_z=plane_z,
                    )
                    if success:
                        pos_3d = pt

                detections.append(
                    Detection(
                        track_id=track_id,
                        class_id=cls_id,
                        class_name=cls_name,
                        bbox=bbox_coords,
                        confidence=conf,
                        reference_pixel=ref_pixel,
                        position_3d=pos_3d,
                    )
                )

        return DetectionResult(
            timestamp=t0,
            frame_id=frame_id,
            detections=detections,
            pose=pose,
        )


def create_default_detector() -> ObjectDetector:
    """Tạo detector với thiết lập mặc định (yolov8n, bottom_center reference)."""
    return ObjectDetector(
        model_path="yolov8n.pt",
        conf_threshold=0.25,
        tracking=True,
        reference_type="bottom_center",
    )
