"""Mô-đun phát hiện quân cờ bằng mô hình YOLO cho mono_eye."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Sequence
import cv2
import numpy as np

from mono_eye.config import ROOT

try:
    from ultralytics import YOLO
    HAS_ULTRALYTICS = True
except ImportError:
    YOLO = None
    HAS_ULTRALYTICS = False

try:
    import torch
    HAS_TORCH = True
except ImportError:
    torch = None
    HAS_TORCH = False


# Bảng ánh xạ nhãn lớp của mô hình sang ký tự FEN tiêu chuẩn
CHESS_PIECE_LABELS: dict[str, str] = {
    "white_pawn": "P",
    "white_knight": "N",
    "white_bishop": "B",
    "white_rook": "R",
    "white_queen": "Q",
    "white_king": "K",
    "black_pawn": "p",
    "black_knight": "n",
    "black_bishop": "b",
    "black_rook": "r",
    "black_queen": "q",
    "black_king": "k",
}


class ChessPieceDetector:
    """Bộ phát hiện quân cờ dựa trên mô hình YOLO chuyên dụng (ví dụ: best25e_2712.pt)."""

    def __init__(
        self,
        model_path: str | Path = "data/models/best25e_2712.pt",
        conf_threshold: float = 0.5,
        iou_threshold: float = 0.5,
        model: Any = None,
        device: str = "auto",
    ):
        """Khởi tạo ChessPieceDetector.

        Args:
            model_path: Đường dẫn tới file trọng số mô hình (.pt hoặc .onnx).
            conf_threshold: Ngưỡng độ tin cậy để nhận diện quân cờ (mặc định 0.5).
            iou_threshold: Ngưỡng IoU cho NMS (mặc định 0.5).
            model: Instance model đã tải sẵn (hoặc mock model dùng cho testing).
            device: Thiết bị chạy inference ('auto', 'cuda', 'cuda:0', 'cpu').
        """
        self.model_path = Path(model_path) if model_path is not None else None
        self.conf_threshold = float(conf_threshold)
        self.iou_threshold = float(iou_threshold)
        self._model = model

        # Tự động phát hiện và chọn thiết bị tốt nhất
        if device == "auto":
            if HAS_TORCH and torch.cuda.is_available():
                self.device = "cuda:0"
            else:
                self.device = "cpu"
        elif str(device).startswith("cuda"):
            if HAS_TORCH and torch.cuda.is_available():
                self.device = str(device)
            else:
                self.device = "cpu"
        else:
            self.device = str(device)

    @property
    def model(self) -> Any:
        """Tải mô hình YOLO theo phương thức lazy loading."""
        if self._model is None:
            if not HAS_ULTRALYTICS:
                raise ImportError(
                    "Thư viện 'ultralytics' chưa được cài đặt. "
                    "Hãy cài đặt bằng: pip install ultralytics"
                )

            if self.model_path is None:
                raise ValueError("Không thể tải model: model_path chưa được cung cấp.")

            path = self.model_path
            if not path.is_file():
                alt_path = ROOT / path
                if alt_path.is_file():
                    path = alt_path
                else:
                    raise FileNotFoundError(
                        f"Không tìm thấy file trọng số YOLO cho quân cờ tại: {path}"
                    )

            self._model = YOLO(str(path))
        return self._model

    def detect(self, frame: np.ndarray) -> list[dict[str, Any]]:
        """Phát hiện các quân cờ trong khung hình.

        Args:
            frame: Ảnh numpy array (BGR).

        Returns:
            Danh sách các dict chứa thông tin quân cờ:
            [
                {
                    'class_name': 'white_knight',
                    'fen_char': 'N',
                    'confidence': 0.95,
                    'bbox': [x1, y1, x2, y2],
                    'bottom_center_pixel': (u, v),
                },
                ...
            ]
        """
        if frame is None or frame.size == 0:
            return []

        kwargs: dict[str, Any] = {
            "conf": self.conf_threshold,
            "iou": self.iou_threshold,
            "verbose": False,
        }
        if getattr(self, "device", None):
            kwargs["device"] = self.device

        results = self.model(frame, **kwargs)

        pieces: list[dict[str, Any]] = []

        for r in results:
            if r is None or getattr(r, "boxes", None) is None:
                continue

            boxes_obj = r.boxes
            if hasattr(boxes_obj, "xyxy"):
                if hasattr(boxes_obj.xyxy, "cpu"):
                    boxes = boxes_obj.xyxy.cpu().numpy()
                    confs = boxes_obj.conf.cpu().numpy()
                    clss = boxes_obj.cls.cpu().numpy()
                else:
                    boxes = np.asarray(boxes_obj.xyxy)
                    confs = np.asarray(boxes_obj.conf)
                    clss = np.asarray(boxes_obj.cls)
            else:
                continue

            if len(boxes) == 0:
                continue

            names = r.names if hasattr(r, "names") else {}

            for (x1, y1, x2, y2), conf, cls_id in zip(boxes, confs, clss):
                confidence = float(conf)
                if confidence < self.conf_threshold:
                    continue

                class_name = names.get(int(cls_id), f"class_{int(cls_id)}")
                fen_char = CHESS_PIECE_LABELS.get(class_name, "?")

                # Điểm tiếp xúc mặt bàn: chính giữa cạnh đáy bounding box
                u = (float(x1) + float(x2)) / 2.0
                v = float(y2)

                pieces.append({
                    "class_name": class_name,
                    "fen_char": fen_char,
                    "confidence": confidence,
                    "bbox": [float(x1), float(y1), float(x2), float(y2)],
                    "bottom_center_pixel": (u, v),
                })

        return pieces

    def visualize(
        self,
        frame: np.ndarray,
        pieces: list[dict[str, Any]],
        draw_dots: bool = True,
    ) -> np.ndarray:
        """Vẽ bounding boxes, nhãn lớp và điểm tham chiếu chân quân cờ lên ảnh.

        Args:
            frame: Ảnh gốc numpy array (BGR).
            pieces: Danh sách quân cờ trả về từ detect().
            draw_dots: Có vẽ điểm chấm tròn tại bottom_center_pixel không.

        Returns:
            Ảnh đã vẽ trực quan hóa.
        """
        vis = frame.copy()
        for p in pieces:
            bbox = p.get("bbox", [])
            if len(bbox) != 4:
                continue
            x1, y1, x2, y2 = [int(round(coord)) for coord in bbox]
            cls_name = p.get("class_name", "")
            fen = p.get("fen_char", "")
            conf = p.get("confidence", 0.0)

            # Màu sắc phân biệt phe trắng (cyan) và phe đen (magenta)
            is_white = cls_name.startswith("white")
            color = (255, 200, 0) if is_white else (50, 50, 255)

            # Bounding box
            cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)

            # Nhãn
            label = f"{cls_name} ({fen}) {conf:.2f}"
            cv2.putText(
                vis,
                label,
                (x1, max(15, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
                cv2.LINE_AA,
            )

            # Điểm tiếp xúc bàn chân vật
            if draw_dots and "bottom_center_pixel" in p:
                u, v = p["bottom_center_pixel"]
                cv2.circle(vis, (int(round(u)), int(round(v))), 4, (0, 255, 0), -1)

        return vis
