"""Trình kết xuất Offscreen ModernGL chất lượng cao sử dụng Framebuffer (FBO) cho OpenCV Dashboard."""
from __future__ import annotations

from pathlib import Path
import glfw
import moderngl
import numpy as np

from mono_eye.viewer3d.camera import OrbitCamera, PoseCamera
from mono_eye.viewer3d.obj_loader import load_scene_cached
from mono_eye.viewer3d.paths import DEFAULT_OBJ
from mono_eye.viewer3d.piece_mapper import PIECE_GROUP_NAMES, calculate_piece_pivots
from mono_eye.viewer3d.renderer import Chess3DRenderer


class OffscreenRenderer:
    """Renderer OpenGL chạy ngầm (Offscreen) xuất trực tiếp ra mảng numpy RGB để ghép vào luồng video."""

    def __init__(
        self,
        width: int = 640,
        height: int = 480,
        obj_path: Path | None = None,
    ) -> None:
        self.width = width
        self.height = height

        if not glfw.init():
            raise RuntimeError("Không thể khởi tạo thư viện GLFW cho OffscreenRenderer!")

        # Tạo context OpenGL ẩn
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, True)
        glfw.window_hint(glfw.VISIBLE, False)

        self.window = glfw.create_window(16, 16, "OffscreenGL", None, None)
        if not self.window:
            glfw.terminate()
            raise RuntimeError("Không thể tạo cửa sổ GLFW ẩn!")

        glfw.make_context_current(self.window)
        self.ctx = moderngl.create_context()

        # Nạp mô hình và khởi tạo Renderer
        self.obj_data = load_scene_cached(obj_path or DEFAULT_OBJ)
        self.renderer = Chess3DRenderer(self.ctx, self.obj_data)
        self.pivots = calculate_piece_pivots(self.obj_data)

        # Khởi tạo Framebuffer Object (FBO)
        self.color_tex: moderngl.Texture | None = None
        self.depth_rb: moderngl.Renderbuffer | None = None
        self.fbo: moderngl.Framebuffer | None = None
        self._create_fbo(self.width, self.height)

    def _create_fbo(self, w: int, h: int) -> None:
        """Tạo hoặc thay đổi kích thước bộ đệm FBO."""
        if self.fbo is not None:
            self.fbo.release()
        if self.color_tex is not None:
            self.color_tex.release()
        if self.depth_rb is not None:
            self.depth_rb.release()

        self.color_tex = self.ctx.texture((w, h), 4)
        self.depth_rb = self.ctx.depth_renderbuffer((w, h))
        self.fbo = self.ctx.framebuffer(
            color_attachments=[self.color_tex],
            depth_attachment=self.depth_rb,
        )
        self.width = w
        self.height = h

    def render(
        self,
        camera: OrbitCamera | PoseCamera,
        width: int | None = None,
        height: int | None = None,
        instances: list[tuple[int, np.ndarray]] | None = None,
        hidden_groups: set[str] | None = None,
    ) -> np.ndarray:
        """Render khung hình phối cảnh 3D và trả về mảng numpy RGB uint8 (H, W, 3)."""
        w = width or self.width
        h = height or self.height

        if w != self.width or h != self.height or self.fbo is None:
            self._create_fbo(w, h)

        self.fbo.use()
        self.ctx.viewport = (0, 0, w, h)

        # Gọi Renderer vẽ nền, bàn cờ, và các quân cờ động
        self.renderer.render(
            camera,
            (w, h),
            instances=instances,
            hidden_groups=hidden_groups,
        )

        # Đọc pixel từ FBO
        raw = self.fbo.read(components=3, alignment=1)
        arr = np.frombuffer(raw, dtype=np.uint8).reshape((h, w, 3))
        # Lật ảnh theo trục dọc vì OpenGL origin ở bottom-left
        return np.flipud(arr)

    def close(self) -> None:
        """Giải phóng tài nguyên đồ họa."""
        if self.fbo is not None:
            self.fbo.release()
            self.fbo = None
        if self.color_tex is not None:
            self.color_tex.release()
            self.color_tex = None
        if self.depth_rb is not None:
            self.depth_rb.release()
            self.depth_rb = None

        if self.window is not None:
            glfw.destroy_window(self.window)
            self.window = None
        glfw.terminate()

    def __enter__(self) -> OffscreenRenderer:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
