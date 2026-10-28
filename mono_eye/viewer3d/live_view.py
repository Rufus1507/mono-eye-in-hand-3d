"""Bộ điều phối Khung nhìn 3D Thời gian thực (Live3DView) tích hợp trực tiếp vào OpenCV Dashboard."""
from __future__ import annotations

import time
import cv2
import numpy as np

from mono_eye.viewer3d.board_transform import fov_y_from_K, scene_cam_from_pose
from mono_eye.viewer3d.camera import OrbitCamera, OrbitController, PoseCamera
from mono_eye.viewer3d.offscreen import OffscreenRenderer
from mono_eye.viewer3d.piece_mapper import PIECE_GROUP_NAMES, build_piece_instances
from mono_eye.viewer3d.piece_stabilizer import PieceStabilizer


class Live3DView:
    """Quản lý render 3D offscreen và đồng bộ tương tác chuột/phím từ OpenCV GUI."""

    def __init__(
        self,
        width: int = 640,
        height: int = 480,
        default_mode: str = "orbit",
    ) -> None:
        self.width = width
        self.height = height
        self.mode = default_mode.lower()  # 'orbit' hoặc 'virtual'

        self.offscreen = OffscreenRenderer(self.width, self.height)
        self.orbit_cam = OrbitCamera(distance=1.35, elevation=38.0, azimuth=45.0)
        self.orbit_ctrl = OrbitController(self.orbit_cam)

        self.last_pose_cam: PoseCamera | None = None
        self.active_pieces_count: int = 0
        self.fps_3d: float = 0.0
        self._last_render_time = time.perf_counter()
        self.stabilizer = PieceStabilizer(persist_frames=6, debounce_frames=3)

    def reset_stabilizer(self) -> None:
        """Đặt lại bộ nhớ bộ ổn định quân cờ."""
        self.stabilizer.reset()

    def toggle_mode(self) -> str:
        """Chuyển đổi qua lại giữa chế độ Orbit Camera và Virtual Camera theo góc máy thật."""
        self.mode = "virtual" if self.mode == "orbit" else "orbit"
        return self.mode

    def reset_view(self) -> None:
        """Đặt lại vị trí góc nhìn mặc định của Orbit Camera."""
        self.orbit_cam.target = np.array([0.0, 0.15, 0.0], dtype=np.float32)
        self.orbit_cam.distance = 1.35
        self.orbit_cam.azimuth = 45.0
        self.orbit_cam.elevation = 38.0

    def zoom(self, factor: float) -> None:
        """Thu phóng khoảng cách camera (dolly zoom)."""
        self.orbit_cam.distance = max(0.2, min(10.0, self.orbit_cam.distance * factor))

    def handle_mouse(self, event: int, x: int, y: int, flags: int) -> None:
        """Xử lý sự kiện chuột từ OpenCV (đã chuẩn hóa tọa độ cục bộ trong khung 3D)."""
        shift = bool(flags & cv2.EVENT_FLAG_SHIFTKEY)
        if event == cv2.EVENT_LBUTTONDOWN:
            self.orbit_ctrl.on_mouse_press(0, float(x), float(y), shift_pressed=shift)
        elif event == cv2.EVENT_RBUTTONDOWN:
            self.orbit_ctrl.on_mouse_press(1, float(x), float(y), shift_pressed=shift)
        elif event == cv2.EVENT_MBUTTONDOWN:
            self.orbit_ctrl.on_mouse_press(2, float(x), float(y), shift_pressed=shift)
        elif event in (cv2.EVENT_LBUTTONUP, cv2.EVENT_RBUTTONUP, cv2.EVENT_MBUTTONUP):
            b = 0 if event == cv2.EVENT_LBUTTONUP else (1 if event == cv2.EVENT_RBUTTONUP else 2)
            self.orbit_ctrl.on_mouse_release(b)
        elif event == cv2.EVENT_MOUSEMOVE:
            self.orbit_ctrl.on_mouse_move(float(x), float(y))

    def update(
        self,
        chess_result,
        view_size: tuple[int, int] | None = None,
        camera_matrix: np.ndarray | None = None,
        image_size: tuple[int, int] | None = None,
    ) -> np.ndarray:
        """Render khung hình 3D dựa trên kết quả phát hiện quân cờ từ camera thực tế.
        
        Quy tắc:
        - CHỈ xuất hiện các quân cờ thực tế có trong chess_result.chess_pieces.
        - Toàn bộ 18 nhóm quân tĩnh trong OBJ bị ẩn (hidden_groups = PIECE_GROUP_NAMES).
        - Trả về ảnh định dạng BGR uint8 sẵn sàng ghép vào OpenCV Dashboard.
        """
        t0 = time.perf_counter()
        w, h = view_size if view_size is not None else (self.width, self.height)

        # 1. Trích xuất danh sách quân cờ thực tế được phát hiện
        detected_pieces: list[dict] = []
        if chess_result is not None:
            if hasattr(chess_result, "pieces") and chess_result.pieces:
                detected_pieces = chess_result.pieces
            elif hasattr(chess_result, "chess_pieces") and chess_result.chess_pieces:
                detected_pieces = chess_result.chess_pieces
            elif isinstance(chess_result, dict):
                detected_pieces = chess_result.get("pieces") or chess_result.get("chess_pieces") or []

        # Ổn định quân cờ theo thời gian: loại bỏ hoàn toàn nhấp nháy (flicker)
        stabilized_pieces = self.stabilizer.feed(detected_pieces)

        # Sinh danh sách các 3D instances
        instances = build_piece_instances(
            detected_pieces=stabilized_pieces,
            group_index_by_name=self.offscreen.renderer.group_index_by_name,
            pivots=self.offscreen.pivots,
        )
        self.active_pieces_count = len(instances)

        # 2. Xác định Camera phối cảnh
        active_camera = self.orbit_cam

        if self.mode == "virtual" and chess_result is not None:
            pose = getattr(chess_result, "pose", None)
            if isinstance(chess_result, dict):
                pose = chess_result.get("pose")

            if pose is not None and getattr(pose, "valid", False) and pose.rvec is not None and pose.tvec is not None:
                # Tính toán góc nhìn camera ảo theo sát camera thực
                eye_scene, R_cam_scene = scene_cam_from_pose(pose.rvec, pose.tvec)
                fov_y = 50.0
                if camera_matrix is not None and image_size is not None:
                    fov_y = fov_y_from_K(camera_matrix, image_size[1])

                self.last_pose_cam = PoseCamera(eye_scene, R_cam_scene, fov_y)
                active_camera = self.last_pose_cam
            elif self.last_pose_cam is not None:
                # Nếu mất pose tạm thời, giữ nguyên vị trí camera ảo trước đó
                active_camera = self.last_pose_cam

        # 3. Kết xuất Offscreen (ẩn 18 quân cờ tĩnh và vẽ các instance động)
        rgb_frame = self.offscreen.render(
            camera=active_camera,
            width=w,
            height=h,
            instances=instances,
            hidden_groups=PIECE_GROUP_NAMES,
        )

        # 4. Chuyển đổi RGB sang BGR để hiển thị với OpenCV
        bgr_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)

        # Đo tốc độ FPS 3D
        dt = time.perf_counter() - t0
        self.fps_3d = 1.0 / max(dt, 1e-4)

        return bgr_frame

    def close(self) -> None:
        """Đóng renderer và giải phóng bộ nhớ."""
        self.offscreen.close()
