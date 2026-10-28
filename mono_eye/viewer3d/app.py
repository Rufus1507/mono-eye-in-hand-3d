"""Ứng dụng cửa sổ tương tác GLFW và Offscreen Rendering cho 3D Chess Viewer."""
from __future__ import annotations

import datetime
from pathlib import Path
import sys
import numpy as np
from PIL import Image
import glfw
import moderngl

from mono_eye.viewer3d.camera import OrbitCamera, OrbitController
from mono_eye.viewer3d.obj_loader import load_scene_cached
from mono_eye.viewer3d.paths import DEFAULT_OBJ
from mono_eye.viewer3d.renderer import Chess3DRenderer


class ViewerApp:
    """Cửa sổ ứng dụng 3D Chess Viewer tương tác với GPU."""

    def __init__(
        self,
        width: int = 1280,
        height: int = 720,
        title: str = "3D Chess Studio Viewer (PBR + RTX 3060)",
        headless: bool = False,
    ) -> None:
        self.width = width
        self.height = height
        self.title = title
        self.headless = headless

        if not glfw.init():
            raise RuntimeError("Không thể khởi tạo thư viện GLFW!")

        # Thiết lập thuộc tính cửa sổ OpenGL
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, True)
        if self.headless:
            glfw.window_hint(glfw.VISIBLE, False)

        self.window = glfw.create_window(self.width, self.height, self.title, None, None)
        if not self.window:
            glfw.terminate()
            raise RuntimeError("Không thể tạo cửa sổ GLFW!")

        glfw.make_context_current(self.window)
        glfw.swap_interval(1)

        self.ctx = moderngl.create_context()
        self.camera = OrbitCamera(distance=1.35, elevation=35.0, azimuth=45.0)
        self.controller = OrbitController(self.camera)

        # Nạp mô hình 3D và khởi tạo Renderer
        print("[ViewerApp] Loading 3D model from cache...")
        self.obj_data = load_scene_cached(DEFAULT_OBJ)
        print("[ViewerApp] Compiling shaders and uploading textures to GPU...")
        self.renderer = Chess3DRenderer(self.ctx, self.obj_data)
        print(f"[ViewerApp] Ready! GPU Renderer: {self.ctx.info['GL_RENDERER']}")

        if not self.headless:
            self._register_callbacks()

    def _register_callbacks(self) -> None:
        """Đăng ký các sự kiện chuột và bàn phím tương tác."""
        def mouse_button_cb(win, button, action, mods):
            shift = bool(mods & glfw.MOD_SHIFT)
            x, y = glfw.get_cursor_pos(win)
            b = 0 if button == glfw.MOUSE_BUTTON_LEFT else (1 if button == glfw.MOUSE_BUTTON_RIGHT else 2)
            if action == glfw.PRESS:
                self.controller.on_mouse_press(b, x, y, shift_pressed=shift)
            elif action == glfw.RELEASE:
                self.controller.on_mouse_release(b)

        def cursor_pos_cb(win, x, y):
            self.controller.on_mouse_move(x, y)

        def scroll_cb(win, x_offset, y_offset):
            self.controller.on_scroll(y_offset)

        def key_cb(win, key, scancode, action, mods):
            if action == glfw.PRESS:
                if key == glfw.KEY_ESCAPE:
                    glfw.set_window_should_close(win, True)
                elif key == glfw.KEY_R:
                    # Reset góc nhìn
                    self.camera.target = np.array([0.0, 0.15, 0.0], dtype=np.float32)
                    self.camera.distance = 1.35
                    self.camera.azimuth = 45.0
                    self.camera.elevation = 35.0
                    print("[ViewerApp] Reset camera to default.")
                elif key == glfw.KEY_S:
                    # Chup anh man hinh
                    out_dir = Path("outputs")
                    out_dir.mkdir(exist_ok=True)
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    out_path = out_dir / f"screenshot_{timestamp}.png"
                    self.save_screenshot(out_path)
                    print(f"[ViewerApp] Saved screenshot: {out_path}")

        def framebuffer_size_cb(win, w, h):
            if w > 0 and h > 0:
                self.width = w
                self.height = h
                self.ctx.viewport = (0, 0, w, h)

        glfw.set_mouse_button_callback(self.window, mouse_button_cb)
        glfw.set_cursor_pos_callback(self.window, cursor_pos_cb)
        glfw.set_scroll_callback(self.window, scroll_cb)
        glfw.set_key_callback(self.window, key_cb)
        glfw.set_framebuffer_size_callback(self.window, framebuffer_size_cb)

    def capture_frame(self) -> np.ndarray:
        """Render khung hình và đọc pixels từ framebuffer thành mảng numpy RGB."""
        fb_w, fb_h = glfw.get_framebuffer_size(self.window)
        self.ctx.viewport = (0, 0, fb_w, fb_h)
        self.renderer.render(self.camera, (fb_w, fb_h))

        raw = self.ctx.screen.read(components=3, alignment=1)
        img_arr = np.frombuffer(raw, dtype=np.uint8).reshape((fb_h, fb_w, 3))
        # Lật ảnh theo trục dọc vì OpenGL origin ở bottom-left
        return np.flipud(img_arr)

    def save_screenshot(self, out_path: str | Path) -> Path:
        """Lưu khung hình render hiện tại ra file ảnh PNG chất lượng cao."""
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        img_arr = self.capture_frame()
        img = Image.fromarray(img_arr)
        img.save(path, quality=95)
        return path

    def run(self, max_frames: int | None = None) -> None:
        """Bắt đầu vòng lặp hiển thị thời gian thực."""
        frame_count = 0
        while not glfw.window_should_close(self.window):
            glfw.poll_events()
            fb_w, fb_h = glfw.get_framebuffer_size(self.window)
            self.ctx.viewport = (0, 0, fb_w, fb_h)

            self.renderer.render(self.camera, (fb_w, fb_h))
            glfw.swap_buffers(self.window)

            frame_count += 1
            if max_frames is not None and frame_count >= max_frames:
                break

    def close(self) -> None:
        """Dọn dẹp và giải phóng tài nguyên GLFW."""
        if self.window:
            glfw.destroy_window(self.window)
            self.window = None
        glfw.terminate()
