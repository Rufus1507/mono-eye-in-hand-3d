"""Đọc camera.yaml do `do_fov.py export` ghi ra (cv::FileStorage)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class CameraModel:
    K: np.ndarray       # ma trận camera 3x3
    dist: np.ndarray    # hệ số méo
    width: int
    height: int

    def check_frame(self, frame: np.ndarray) -> None:
        """Từ chối khung hình có độ phân giải khác lúc hiệu chuẩn (K chỉ đúng cho chế độ đó)."""
        h, w = frame.shape[:2]
        if (w, h) != (self.width, self.height):
            raise ValueError(
                f"Khung hình {w}x{h} nhưng camera được hiệu chuẩn ở {self.width}x{self.height}"
            )


def load_camera_yaml(path: str | Path) -> CameraModel:
    # Đọc nội dung bằng Python rồi đưa cho OpenCV dạng chuỗi: tránh việc cv2.FileStorage mở file
    # bằng bảng mã ANSI trên Windows (đường dẫn có dấu tiếng Việt có thể mở không được).
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Không tìm thấy file camera: {path}")
    fs = cv2.FileStorage(p.read_text(encoding="utf-8"),
                         cv2.FILE_STORAGE_READ | cv2.FILE_STORAGE_MEMORY)
    if not fs.isOpened():
        raise ValueError(f"Không đọc được nội dung camera.yaml: {path}")
    try:
        K = fs.getNode("camera_matrix").mat()
        dist = fs.getNode("distortion_coefficients").mat()
        width = int(fs.getNode("image_width").real())
        height = int(fs.getNode("image_height").real())
    finally:
        fs.release()
    if K is None or dist is None:
        raise ValueError(f"{path} thiếu camera_matrix hoặc distortion_coefficients")
    if width <= 0 or height <= 0:
        raise ValueError(f"{path} có kích thước ảnh không hợp lệ: {width}x{height}")
    return CameraModel(K=K, dist=dist.reshape(-1), width=width, height=height)
