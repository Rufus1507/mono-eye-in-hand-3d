"""Pipeline tích hợp: Camera Pose (ChArUco) → Phát hiện quân cờ (YOLO) → Chiếu tọa độ 3D."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import time
from typing import Any, Optional

import cv2
import numpy as np

from mono_eye.camera_io import CameraModel, load_camera_yaml
from mono_eye.chess_detectors import ChessPieceDetector
from mono_eye.config import ROOT
from mono_eye.pose import CameraPose, PoseEstimator
from mono_eye.projection import ProjectionProcessor


@dataclass
class ChessResult:
    """Kết quả xử lý định vị quân cờ cho một khung hình.

    Attributes:
        timestamp: Mốc thời gian xử lý khung hình.
        frame_id: Số thứ tự khung hình.
        pose: Tư thế camera ước lượng từ bảng ChArUco (CameraPose).
        pieces: Danh sách quân cờ phát hiện kèm tọa độ 3D (mm).
    """

    timestamp: float
    frame_id: int
    pose: CameraPose
    pieces: list[dict[str, Any]] = field(default_factory=list)

    @property
    def valid_pieces(self) -> list[dict[str, Any]]:
        """Danh sách quân cờ đã định vị 3D thành công."""
        return [p for p in self.pieces if p.get("position_3d") is not None]

    @property
    def num_pieces(self) -> int:
        """Tổng số quân cờ phát hiện được trong khung hình."""
        return len(self.pieces)

    def as_dict(self) -> dict[str, Any]:
        """Chuyển đổi sang dict thuận tiện cho xuất log hoặc truyền qua mạng."""
        pieces_data = []
        for p in self.pieces:
            pos = p.get("position_3d")
            pos_list = pos.tolist() if isinstance(pos, np.ndarray) else pos
            pieces_data.append({
                "class_name": p.get("class_name"),
                "fen_char": p.get("fen_char"),
                "confidence": p.get("confidence"),
                "bbox": p.get("bbox"),
                "bottom_center_pixel": p.get("bottom_center_pixel"),
                "position_3d": pos_list,
            })

        return {
            "timestamp": self.timestamp,
            "frame_id": self.frame_id,
            "pose_valid": self.pose.valid,
            "camera_center": (
                self.pose.camera_center.tolist()
                if self.pose.camera_center is not None
                else None
            ),
            "reproj_error_px": self.pose.reproj_error_px,
            "num_corners": self.pose.num_corners,
            "pieces": pieces_data,
        }


class ChessMonoEyePipeline:
    """Pipeline định vị quân cờ 3D sử dụng một camera và bảng chuẩn ChArUco."""

    def __init__(
        self,
        camera_config: str | Path = "data/calib/camera.yaml",
        camera: Optional[CameraModel] = None,
        board_config: str | Path = "bang_calib_A4.yaml",
        piece_model_path: str | Path = "data/models/best25e_2712.pt",
        detector: Optional[ChessPieceDetector] = None,
        conf_threshold: float = 0.5,
        plane_z: float = 0.0,
        device: str = "auto",
    ):
        """Khởi tạo ChessMonoEyePipeline.

        Args:
            camera_config: Đường dẫn file camera.yaml (nếu camera=None).
            camera: Đối tượng CameraModel nạp sẵn (tùy chọn).
            board_config: Đường dẫn cấu hình bảng ChArUco (YAML).
            piece_model_path: Đường dẫn tới weights YOLO phát hiện quân cờ (.pt).
            detector: Đối tượng ChessPieceDetector nạp sẵn (tùy chọn).
            conf_threshold: Ngưỡng tin cậy nhận diện quân cờ (mặc định 0.5).
            plane_z: Cao độ mặt phẳng bàn chứa quân cờ (mm, mặc định 0.0).
            device: Thiết bị chạy inference ('auto', 'cuda', 'cpu').
        """
        # 1. Nạp CameraModel
        if camera is not None:
            self.camera = camera
        else:
            cam_path = Path(camera_config)
            if not cam_path.is_file():
                alt_path = ROOT / camera_config
                if alt_path.is_file():
                    cam_path = alt_path
            self.camera = load_camera_yaml(cam_path)

        # 2. Khởi tạo PoseEstimator cho bảng ChArUco
        self.pose_estimator = PoseEstimator(
            camera=self.camera,
            board_config=board_config,
        )

        # 3. Khởi tạo ProjectionProcessor chiếu pixel sang 3D mặt phẳng plane_z
        self.projection = ProjectionProcessor(
            K=self.camera.K,
            dist=self.camera.dist,
            plane_z=plane_z,
        )

        # 4. Khởi tạo ChessPieceDetector
        if detector is not None:
            self.detector = detector
        else:
            self.detector = ChessPieceDetector(
                model_path=piece_model_path,
                conf_threshold=conf_threshold,
                device=device,
            )

        self.plane_z = float(plane_z)
        self.frame_id = 0

    def process_frame(
        self,
        frame: np.ndarray,
        detect_pieces: bool = True,
    ) -> ChessResult:
        """Xử lý một khung hình: Ước lượng Pose ChArUco và định vị 3D từng quân cờ.

        Args:
            frame: Ảnh numpy array (BGR).
            detect_pieces: Có bật nhận diện quân cờ không.

        Returns:
            ChessResult chứa tư thế camera và danh sách quân cờ kèm tọa độ 3D.
        """
        # Bước 1: Ước lượng Camera Pose từ ChArUco Board
        pose = self.pose_estimator.estimate(frame)

        pieces: list[dict[str, Any]] = []

        # Bước 2: Phát hiện quân cờ
        if detect_pieces and self.detector is not None:
            pieces = self.detector.detect(frame)

            # Bước 3: Chiếu điểm đáy quân cờ sang tọa độ 3D (Z = plane_z)
            for p in pieces:
                if pose.valid:
                    pixel = p["bottom_center_pixel"]
                    ok, pos_3d = self.projection.project(pixel, pose)
                    p["position_3d"] = pos_3d if ok else None
                else:
                    p["position_3d"] = None

        result = ChessResult(
            timestamp=time.time(),
            frame_id=self.frame_id,
            pose=pose,
            pieces=pieces,
        )

        self.frame_id += 1
        return result

    def visualize(
        self,
        frame: np.ndarray,
        result: ChessResult,
        draw_pose_axis: bool = True,
    ) -> np.ndarray:
        """Trực quan hóa kết quả: Vẽ hệ trục ChArUco và các quân cờ kèm tọa độ 3D.

        Args:
            frame: Khung hình gốc (BGR).
            result: Đối tượng ChessResult từ process_frame().
            draw_pose_axis: Có vẽ trục tọa độ ChArUco không.

        Returns:
            Ảnh numpy array đã vẽ trực quan.
        """
        vis = frame.copy()

        # 1. Vẽ trục tọa độ ChArUco board nếu pose hợp lệ
        if draw_pose_axis and result.pose.valid and result.pose.rvec is not None:
            axis_length = 50.0  # mm
            cv2.drawFrameAxes(
                vis,
                self.camera.K,
                self.camera.dist,
                result.pose.rvec,
                result.pose.tvec,
                axis_length,
                2,
            )

        # 2. Vẽ thông tin quân cờ và tọa độ 3D
        for p in result.pieces:
            bbox = p.get("bbox", [])
            if len(bbox) != 4:
                continue
            x1, y1, x2, y2 = [int(round(coord)) for coord in bbox]
            cls_name = p.get("class_name", "")
            fen = p.get("fen_char", "")
            conf = p.get("confidence", 0.0)

            is_white = cls_name.startswith("white")
            color = (255, 200, 0) if is_white else (50, 50, 255)

            # Hộp nhận diện
            cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)

            # Nhãn lớp + độ tin cậy
            label = f"{cls_name} ({fen}) {conf:.2f}"
            cv2.putText(
                vis,
                label,
                (x1, max(15, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                color,
                1,
                cv2.LINE_AA,
            )

            # Tọa độ 3D (mm)
            pos_3d = p.get("position_3d")
            if pos_3d is not None:
                text_3d = f"3D: ({pos_3d[0]:.1f}, {pos_3d[1]:.1f}, {pos_3d[2]:.1f}) mm"
                cv2.putText(
                    vis,
                    text_3d,
                    (x1, min(vis.shape[0] - 5, y2 + 15)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    (0, 255, 0),
                    1,
                    cv2.LINE_AA,
                )

            # Điểm đáy chạm bàn
            u, v = p.get("bottom_center_pixel", (0, 0))
            cv2.circle(vis, (int(round(u)), int(round(v))), 4, (0, 255, 0), -1)

        # Thông tin tổng quát ở góc trên
        status_text = (
            f"Frame {result.frame_id} | ChArUco: "
            + ("OK" if result.pose.valid else "LOST")
            + f" | Pieces: {result.num_pieces} (3D: {len(result.valid_pieces)})"
        )
        status_color = (0, 255, 0) if result.pose.valid else (0, 0, 255)
        cv2.putText(
            vis,
            status_text,
            (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            status_color,
            2,
            cv2.LINE_AA,
        )

        return vis
