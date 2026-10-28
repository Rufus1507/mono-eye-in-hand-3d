"""Kiểm thử chu trình Render Offscreen FBO (yêu cầu ModernGL)."""
from __future__ import annotations

import numpy as np
import pytest

moderngl = pytest.importorskip("moderngl")
glfw = pytest.importorskip("glfw")

from mono_eye.viewer3d.camera import OrbitCamera
from mono_eye.viewer3d.offscreen import OffscreenRenderer


def test_offscreen_renderer_cycle():
    """Kiểm tra khởi tạo FBO, kết xuất một khung hình và đọc pixels RGB thành công."""
    w, h = 160, 120
    renderer = OffscreenRenderer(width=w, height=h)
    try:
        camera = OrbitCamera(distance=1.35, elevation=38.0, azimuth=45.0)
        img = renderer.render(camera=camera, width=w, height=h)

        # Kiểm tra shape, dtype và nội dung ảnh
        assert img.shape == (h, w, 3)
        assert img.dtype == np.uint8
        # Ảnh phải có độ tương phản và chi tiết, không được đen đặc
        assert float(img.std()) > 1.0
        assert float(img.mean()) > 10.0
    finally:
        renderer.close()
