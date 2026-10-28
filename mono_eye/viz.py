"""Giai đoạn 6 - 3D Visualization cho hệ thống Mono Eye 3D."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence
import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D
    HAS_MATPLOTLIB = True
except ImportError:
    plt = None
    Axes3D = None
    HAS_MATPLOTLIB = False

try:
    import open3d as o3d
    HAS_OPEN3D = True
except ImportError:
    o3d = None
    HAS_OPEN3D = False


@dataclass
class SceneObject:
    """Một đối tượng trong scene 3D.

    Attributes:
        name: Tên đối tượng (ví dụ: 'cup', 'box').
        position: Tọa độ tâm [x, y, z] trong world frame (mm).
        color: Màu RGB tuple.
        size: Kích thước biểu diễn (mm).
        object_type: Loại hình học ("sphere", "box", "mesh").
    """

    name: str
    position: np.ndarray
    color: tuple[int, int, int] = (0, 255, 0)  # Green
    size: float = 20.0
    object_type: str = "sphere"


@dataclass
class TablePlane:
    """Mặt bàn làm việc.

    Attributes:
        bounds: Tọa độ giới hạn (x_min, x_max, y_min, y_max, z) tính bằng mm.
        color: Màu RGB tuple.
        alpha: Độ trong suốt [0.0, 1.0].
    """

    bounds: tuple[float, float, float, float, float]
    color: tuple[int, int, int] = (200, 200, 200)  # Gray
    alpha: float = 0.3


@dataclass
class CameraView:
    """Tư thế và góc nhìn của camera.

    Attributes:
        position: Tọa độ camera [x, y, z] trong world frame (mm).
        rotation: Vector quay rvec (Rodrigues) trong camera pose.
        fov: Góc mở trường nhìn (độ).
    """

    position: np.ndarray
    rotation: Optional[np.ndarray] = None
    fov: float = 60.0


class DummyAxes3D:
    """Mock axes dùng khi chưa cài matplotlib để test không bị crash."""

    def __init__(self):
        self.elements: list[dict[str, Any]] = []

    def cla(self):
        self.elements.clear()

    def set_xlabel(self, *args, **kwargs): pass
    def set_ylabel(self, *args, **kwargs): pass
    def set_zlabel(self, *args, **kwargs): pass
    def set_title(self, *args, **kwargs): pass
    def set_box_aspect(self, *args, **kwargs): pass

    def plot_surface(self, *args, **kwargs):
        self.elements.append({"type": "surface", "args": args})

    def plot_wireframe(self, *args, **kwargs):
        self.elements.append({"type": "wireframe", "args": args})

    def plot(self, *args, **kwargs):
        self.elements.append({"type": "plot", "args": args})

    def scatter(self, *args, **kwargs):
        self.elements.append({"type": "scatter", "args": args})

    def text(self, *args, **kwargs):
        self.elements.append({"type": "text", "args": args})

    def quiver(self, *args, **kwargs):
        self.elements.append({"type": "quiver", "args": args})


class DummyFigure:
    """Mock figure dùng khi chưa cài matplotlib."""

    def __init__(self, figsize=(12, 8)):
        self.figsize = figsize
        self.ax = DummyAxes3D()
        self.texts: list[str] = []

    def add_subplot(self, *args, **kwargs):
        return self.ax

    def text(self, x, y, s, *args, **kwargs):
        self.texts.append(s)


class SimpleVisualizer:
    """3D Visualizer trực quan dùng Matplotlib (hoặc fallback stub)."""

    def __init__(self, figsize: tuple[int, int] = (12, 8)):
        """Khởi tạo visualizer."""
        self.figsize = figsize
        self.fig: Any = None
        self.ax: Any = None
        self.table: Optional[TablePlane] = None
        self.object_markers: list[tuple[np.ndarray, str, str]] = []

        self._init_figure()

    def _init_figure(self):
        """Khởi tạo figure và axes 3D."""
        if HAS_MATPLOTLIB:
            self.fig = plt.figure(figsize=self.figsize)
            self.ax = self.fig.add_subplot(111, projection="3d")
        else:
            self.fig = DummyFigure(self.figsize)
            self.ax = self.fig.ax

        self._setup_axes()

    def _setup_axes(self):
        """Thiết lập các trục X, Y, Z."""
        self.ax.set_xlabel("X (mm)")
        self.ax.set_ylabel("Y (mm)")
        self.ax.set_zlabel("Z (mm)")
        self.ax.set_title("Mono Eye 3D Visualization")
        self.ax.set_box_aspect([1, 1, 1])

    def clear(self):
        """Xóa sạch các đối tượng đang hiển thị."""
        self.ax.cla()
        self._setup_axes()
        self.object_markers = []

    def draw_table(
        self,
        x_range: tuple[float, float] = (-200.0, 200.0),
        y_range: tuple[float, float] = (-200.0, 200.0),
        z: float = 0.0,
    ):
        """Vẽ mặt phẳng bàn làm việc.

        Args:
            x_range: Giới hạn tọa độ X (mm).
            y_range: Giới hạn tọa độ Y (mm).
            z: Độ cao mặt bàn (mm, mặc định 0.0).
        """
        x = np.linspace(x_range[0], x_range[1], 10)
        y = np.linspace(y_range[0], y_range[1], 10)
        X, Y = np.meshgrid(x, y)
        Z = np.ones_like(X) * z

        self.ax.plot_surface(X, Y, Z, alpha=0.3, color="gray")
        self.ax.plot_wireframe(X, Y, Z, alpha=0.1, color="black")

    def draw_board_outline(
        self,
        corners: np.ndarray,
        z: float = 0.0,
        color: str = "blue",
    ):
        """Vẽ đường viền khung của bảng ChArUco.

        Args:
            corners: Mảng shape (4, 2) hoặc (4, 3) chứa 4 góc của bảng.
            z: Độ cao z.
            color: Màu đường viền.
        """
        pts = np.asarray(corners)
        if len(pts) < 4:
            return

        corners_z = np.column_stack([pts[:, :2], np.ones(len(pts)) * z])
        for i in range(4):
            start = corners_z[i]
            end = corners_z[(i + 1) % 4]
            self.ax.plot(
                [start[0], end[0]],
                [start[1], end[1]],
                [z, z],
                color=color,
                linewidth=2,
            )

    def draw_camera(
        self,
        position: np.ndarray,
        rotation: Optional[np.ndarray] = None,
        scale: float = 50.0,
        color: str = "red",
    ):
        """Vẽ vị trí camera và hướng nhìn.

        Args:
            position: Tọa độ camera [x, y, z] (mm).
            rotation: Vector quay rvec (Rodrigues).
            scale: Độ dài mũi tên hướng nhìn.
            color: Màu sắc marker camera.
        """
        pos = np.asarray(position, dtype=np.float64).reshape(-1)
        x, y, z = pos[0], pos[1], pos[2]

        self.ax.scatter([x], [y], [z], c=color, marker="^", s=200)

        if rotation is not None:
            import cv2
            r = np.asarray(rotation, dtype=np.float64).reshape(3)
            R, _ = cv2.Rodrigues(r)
            # Trục quang học +Z trong camera frame biến sang world qua R.T
            z_axis = R.T @ np.array([0.0, 0.0, 1.0])
            self.ax.quiver(
                x, y, z,
                z_axis[0], z_axis[1], z_axis[2],
                length=scale,
                color="green",
                arrow_length_ratio=0.3,
            )

    def draw_object(
        self,
        position: np.ndarray,
        name: str = "",
        color: str = "green",
        size: float = 20.0,
    ):
        """Vẽ một vật thể phát hiện được trong không gian 3D.

        Args:
            position: Tọa độ [x, y, z] (mm).
            name: Tên hoặc ID nhãn vật thể.
            color: Màu sắc marker.
            size: Kích thước hiển thị.
        """
        pos = np.asarray(position, dtype=np.float64).reshape(-1)
        x, y, z = pos[0], pos[1], pos[2]

        self.ax.scatter([x], [y], [z], c=color, s=size * 2)
        if name:
            self.ax.text(x, y, z + size / 2.0, name, fontsize=8)

        self.object_markers.append((pos, name, color))

    def draw_trajectory(
        self,
        positions: list[np.ndarray] | np.ndarray,
        color: str = "purple",
        alpha: float = 0.5,
    ):
        """Vẽ quỹ đạo di chuyển (trajectory) của camera.

        Args:
            positions: Danh sách các điểm tọa độ [x, y, z].
            color: Màu nét vẽ.
            alpha: Độ trong suốt.
        """
        pts = np.asarray(positions)
        if len(pts) < 2:
            return

        self.ax.plot(
            pts[:, 0],
            pts[:, 1],
            pts[:, 2],
            color=color,
            alpha=alpha,
            linewidth=1.5,
        )

    def add_text(self, text: str, x: float = 0.02, y: float = 0.98):
        """Thêm nhãn thông tin lên góc figure.

        Args:
            text: Nội dung chuỗi văn bản.
            x, y: Tọa độ chuẩn hóa trên figure.
        """
        if hasattr(self.fig, "text"):
            self.fig.text(
                x, y, text,
                fontsize=10,
                verticalalignment="top",
            )

    def show(self, block: bool = True):
        """Hiển thị cửa sổ figure."""
        if HAS_MATPLOTLIB and plt is not None:
            plt.tight_layout()
            plt.show(block=block)

    def save(self, path: str, dpi: int = 150):
        """Lưu hình ảnh không gian 3D ra file."""
        if HAS_MATPLOTLIB and plt is not None:
            plt.savefig(path, dpi=dpi, bbox_inches="tight")

    def pause(self, interval: float = 0.01):
        """Tạm dừng để cập nhật animation trong vòng lặp realtime."""
        if HAS_MATPLOTLIB and plt is not None:
            plt.pause(interval)


class Open3DVisualizer:
    """3D Visualizer hiệu năng cao dùng Open3D."""

    def __init__(self):
        if not HAS_OPEN3D or o3d is None:
            raise ImportError(
                "Thư viện 'open3d' chưa được cài đặt. "
                "Hãy cài đặt bằng: pip install open3d"
            )

        self.vis = o3d.visualization.Visualizer()
        self.vis.create_window(window_name="Mono Eye 3D Visualizer")
        self.geometries: dict[str, Any] = {}

    def clear(self):
        """Xóa tất cả hình học trong visualizer."""
        for geo in self.geometries.values():
            self.vis.remove_geometry(geo)
        self.geometries.clear()

    def add_coordinate_frame(self, size: float = 100.0):
        """Thêm hệ trục tọa độ RGB."""
        mesh = o3d.geometry.TriangleMesh.create_coordinate_frame(size=size)
        self.vis.add_geometry(mesh)

    def add_table(
        self,
        x_range: tuple[float, float] = (-200.0, 200.0),
        y_range: tuple[float, float] = (-200.0, 200.0),
        z: float = 0.0,
    ):
        """Thêm mặt bàn dạng khối hộp mỏng."""
        w = x_range[1] - x_range[0]
        h = y_range[1] - y_range[0]
        mesh = o3d.geometry.TriangleMesh.create_box(width=w, height=h, depth=1.0)
        mesh.translate([(x_range[0] + x_range[1]) / 2.0, (y_range[0] + y_range[1]) / 2.0, z - 0.5])
        mesh.paint_uniform_color([0.8, 0.8, 0.8])
        self.vis.add_geometry(mesh)
        self.geometries["table"] = mesh

    def add_sphere(
        self,
        position: np.ndarray,
        radius: float = 20.0,
        color: tuple[float, float, float] = (0.0, 1.0, 0.0),
        name: str = "",
    ):
        """Thêm vật thể dạng hình cầu."""
        sphere = o3d.geometry.TriangleMesh.create_sphere(radius=radius)
        sphere.translate(position)
        sphere.paint_uniform_color(color)
        self.vis.add_geometry(sphere)
        self.geometries[name or f"sphere_{len(self.geometries)}"] = sphere

    def update(self):
        """Cập nhật renderer trong vòng lặp."""
        self.vis.poll_events()
        self.vis.update_renderer()

    def show(self, block: bool = True):
        """Khởi động vòng lặp hiển thị."""
        self.vis.run()

    def close(self):
        """Đóng cửa sổ hiển thị."""
        self.vis.destroy_window()


def create_visualizer(backend: str = "matplotlib") -> SimpleVisualizer | Open3DVisualizer:
    """Factory function tạo bộ hiển thị 3D theo backend mong muốn."""
    if backend == "open3d":
        return Open3DVisualizer()
    return SimpleVisualizer()


def visualize_realtime_example():
    """Ví dụ kịch bản mô phỏng chuyển động camera và hiển thị vật thể."""
    viz = SimpleVisualizer()
    viz.draw_table(x_range=(-300.0, 300.0), y_range=(-300.0, 300.0))

    trajectory = []
    for i in range(10):
        viz.clear()
        viz.draw_table()

        x = 100.0 * np.sin(i * 0.1)
        y = 100.0 * np.cos(i * 0.1)
        z = 300.0 + 50.0 * np.sin(i * 0.2)
        pos = np.array([x, y, z])
        trajectory.append(pos)

        viz.draw_trajectory(trajectory)
        viz.draw_camera(pos, color="red")
        viz.draw_object(np.array([50.0, 0.0, 0.0]), name="Target 1", color="green")
        viz.add_text(f"Simulating Frame: {i}")

    print("✅ Completed visualize_realtime_example simulation.")
