"""Toàn bộ pipeline: Camera → Pose → Detection → 3D Projection."""
from __future__ import annotations

from pathlib import Path
import time
from typing import Optional

import cv2
import numpy as np

from mono_eye.camera_io import CameraModel, load_camera_yaml
from mono_eye.config import ROOT
from mono_eye.detect import DetectionResult, ObjectDetector
from mono_eye.filter import TemporalSmoother, filter_parallel_ray
from mono_eye.pose import CameraPose, PoseEstimator
from mono_eye.projection import ProjectionProcessor


class MonoEyePipeline:
    """Full pipeline cho hệ thống Monocular Eye-in-Hand 3D localization."""

    def __init__(
        self,
        camera_config: str | Path = "data/calib/camera.yaml",
        camera: Optional[CameraModel] = None,
        board_config: str | Path = "bang_calib_A4.yaml",
        detector_config: Optional[dict] = None,
        detector: Optional[ObjectDetector] = None,
        plane_z: float = 0.0,
        enable_smoothing: bool = False,
        smooth_window: int = 5,
        min_ray_z: float = 0.05,
    ):
        """Khởi tạo pipeline.

        Args:
            camera_config: Đường dẫn file camera.yaml (chỉ dùng nếu camera=None).
            camera: Đối tượng CameraModel đã nạp sẵn (nếu có).
            board_config: Đường dẫn file cấu hình bảng ChArUco.
            detector_config: Dict cấu hình khởi tạo ObjectDetector (nếu chưa có detector).
            detector: Đối tượng ObjectDetector đã tạo sẵn (tùy chọn).
            plane_z: Tọa độ Z của mặt phẳng bàn làm việc (mặc định 0.0 mm).
            enable_smoothing: Có bật làm mượt vị trí 3D theo thời gian không.
            smooth_window: Kích thước cửa sổ trượt (frames).
            min_ray_z: Ngưỡng loại bỏ tia nhìn gần song song mặt bàn.
        """
        # 1. Khởi tạo CameraModel
        if camera is not None:
            self.camera = camera
        else:
            cam_path = Path(camera_config)
            if not cam_path.is_file():
                alt_path = ROOT / camera_config
                if alt_path.is_file():
                    cam_path = alt_path
            self.camera = load_camera_yaml(cam_path)

        # 2. Khởi tạo PoseEstimator
        self.pose_estimator = PoseEstimator(
            camera=self.camera,
            board_config=board_config,
        )

        # 3. Khởi tạo ProjectionProcessor
        self.projection = ProjectionProcessor(
            K=self.camera.K,
            dist=self.camera.dist,
            plane_z=plane_z,
        )

        # 4. Khởi tạo ObjectDetector
        if detector is not None:
            self.detector = detector
        elif detector_config is not None:
            self.detector = ObjectDetector(**detector_config)
        else:
            self.detector = None

        self.smoother = (
            TemporalSmoother(window_size=smooth_window)
            if enable_smoothing
            else None
        )
        self.min_ray_z = min_ray_z
        self.frame_id = 0

    def process_frame(
        self,
        frame: np.ndarray,
        detect_objects: bool = True,
    ) -> tuple[CameraPose, Optional[DetectionResult]]:
        """Xử lý một khung hình: Ước lượng pose camera và định vị 3D vật thể.

        Args:
            frame: Ảnh numpy array (BGR).
            detect_objects: Có chạy phát hiện vật thể không.

        Returns:
            (pose, detection_result)
        """
        # Bước 1: Ước lượng Pose từ ChArUco board
        pose = self.pose_estimator.estimate(frame)

        # Bước 2: Phát hiện vật thể và chiếu sang 3D
        detections: Optional[DetectionResult] = None
        if detect_objects and self.detector is not None:
            detections = self.detector.detect(
                frame,
                pose=pose,
                K=self.camera.K,
                dist=self.camera.dist,
                plane_z=self.projection.plane_z,
                frame_id=self.frame_id,
            )
            # Áp dụng Temporal Smoothing nếu đã bật
            if detections is not None and self.smoother is not None:
                for det in detections.detections:
                    if det.position_3d is not None:
                        track_key = det.track_id if det.track_id is not None else 0
                        det.position_3d = self.smoother.update(track_key, det.position_3d)

        self.frame_id += 1
        return pose, detections

    def process_video(
        self,
        video_path: str,
        output_path: Optional[str] = None,
        draw_annotations: bool = True,
    ) -> list[tuple[CameraPose, Optional[DetectionResult]]]:
        """Xử lý toàn bộ video file.

        Args:
            video_path: Đường dẫn file video đầu vào.
            output_path: Đường dẫn file video đầu ra có vẽ trực quan (tùy chọn).
            draw_annotations: Có vẽ trục tọa độ và bounding boxes không.

        Returns:
            Danh sách các cặp (pose, detection_result) cho từng khung hình.
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Không thể mở file video: {video_path}")

        results: list[tuple[CameraPose, Optional[DetectionResult]]] = []
        writer: Optional[cv2.VideoWriter] = None

        if output_path is not None:
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            writer = cv2.VideoWriter(
                output_path,
                fourcc,
                fps,
                (self.camera.width, self.camera.height),
            )

        try:
            while True:
                ret, frame = cap.read()
                if not ret or frame is None:
                    break

                pose, detections = self.process_frame(frame)
                results.append((pose, detections))

                if writer is not None and draw_annotations:
                    annotated = frame.copy()

                    # Vẽ hệ trục tọa độ thế giới khi pose hợp lệ
                    if pose.valid and pose.rvec is not None and pose.tvec is not None:
                        cv2.drawFrameAxes(
                            annotated,
                            self.camera.K,
                            self.camera.dist,
                            pose.rvec,
                            pose.tvec,
                            length=50.0,
                        )
                        label = f"Corners: {pose.num_corners} | Err: {pose.reproj_error_px:.2f}px"
                        cv2.putText(
                            annotated,
                            label,
                            (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.7,
                            (0, 255, 0),
                            2,
                        )

                    # Vẽ bounding boxes và vị trí 3D vật thể
                    if detections is not None:
                        for d in detections.detections:
                            b = [int(v) for v in d.bbox]
                            cv2.rectangle(
                                annotated,
                                (b[0], b[1]),
                                (b[2], b[3]),
                                (0, 165, 255),
                                2,
                            )
                            ref_u, ref_v = int(d.reference_pixel[0]), int(d.reference_pixel[1])
                            cv2.circle(annotated, (ref_u, ref_v), 4, (0, 0, 255), -1)

                            if d.position_3d is not None:
                                pos_str = f"{d.class_name}: X={d.position_3d[0]:.1f}, Y={d.position_3d[1]:.1f}mm"
                            else:
                                pos_str = f"{d.class_name} ({d.confidence:.2f})"

                            cv2.putText(
                                annotated,
                                pos_str,
                                (b[0], max(20, b[1] - 8)),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.5,
                                (0, 255, 255),
                                1,
                            )

                    writer.write(annotated)
        finally:
            cap.release()
            if writer is not None:
                writer.release()

        return results
