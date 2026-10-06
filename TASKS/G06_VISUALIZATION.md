# PROMPT: Giai đoạn 6 - 3D Visualization (VIẾT CODE)

## Mục tiêu
Viết `mono_eye/viz.py` hoàn chỉnh: hiển thị không gian 3D với camera, bàn, vật.

## Ngữ cảnh

### Module đã có
```python
# Từ G03: mono_eye/pose.py
from mono_eye.pose import CameraPose
center = pose.camera_center  # np.array([x, y, z])

# Từ G05: mono_eye/detect.py
from mono_eye.detect import Detection, DetectionResult
detection.position_3d  # np.array([x, y, z])
```

### Visualization Options

| Library | Pros | Cons |
|---------|------|------|
| **matplotlib 3D** | Không cần cài thêm, đơn giản | Chậm, không realtime |
| **Open3D** | Đẹp, nhanh, realtime được | Cần cài thêm |
| **Rerun** | Timeline visualization, đẹp | Nặng, phức tạp |
| **Plotly** | Interactive | Không realtime |

---

## Yêu cầu code

### File: `mono_eye/viz.py`

```python
"""Giai đoạn 6 - 3D visualization."""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Optional

try:
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    import open3d as o3d
    HAS_OPEN3D = True
except ImportError:
    HAS_OPEN3D = False


@dataclass
class SceneObject:
    """Một đối tượng trong scene 3D.
    
    Attributes:
        name: Tên đối tượng.
        position: Tọa độ tâm [x, y, z] (mm).
        color: Màu RGB.
        size: Kích thước (mm).
        object_type: "sphere", "box", "mesh".
    """
    name: str
    position: np.ndarray
    color: tuple[int, int, int] = (0, 255, 0)  # Green
    size: float = 20.0
    object_type: str = "sphere"


@dataclass  
class TablePlane:
    """Mặt bàn.
    
    Attributes:
        bounds: (x_min, x_max, y_min, y_max, z) trong mm.
        color: Màu.
        alpha: Độ trong suốt.
    """
    bounds: tuple[float, float, float, float, float]
    color: tuple[int, int, int] = (200, 200, 200)  # Gray
    alpha: float = 0.3


@dataclass
class CameraView:
    """Camera view.
    
    Attributes:
        position: Tọa độ camera [x, y, z].
        rotation: Rotation vector (Rodrigues).
        fov: Field of view (degrees).
    """
    position: np.ndarray
    rotation: Optional[np.ndarray] = None
    fov: float = 60.0


class SimpleVisualizer:
    """Simple 3D visualizer dùng matplotlib.
    
    Đơn giản, không cần cài thêm library.
    """
    
    def __init__(self, figsize: tuple[int, int] = (12, 8)):
        """Khởi tạo visualizer.
        
        Args:
            figsize: Kích thước figure.
        """
        if not HAS_MATPLOTLIB:
            raise ImportError("matplotlib not installed")
        
        self.figsize = figsize
        self.fig = None
        self.ax = None
        self.table = None
        self.camera_marker = None
        self.object_markers = []
        
        self._init_figure()
    
    def _init_figure(self):
        """Khởi tạo figure."""
        self.fig = plt.figure(figsize=self.figsize)
        self.ax = self.fig.add_subplot(111, projection='3d')
        
        self._setup_axes()
    
    def _setup_axes(self):
        """Cài đặt axes."""
        # Labels
        self.ax.set_xlabel('X (mm)')
        self.ax.set_ylabel('Y (mm)')
        self.ax.set_zlabel('Z (mm)')
        
        # Title
        self.ax.set_title('Mono Eye 3D Visualization')
        
        # Equal aspect ratio
        self.ax.set_box_aspect([1, 1, 1])
    
    def clear(self):
        """Xóa tất cả objects."""
        self.ax.cla()
        self._setup_axes()
        self.object_markers = []
    
    def draw_table(
        self,
        x_range: tuple[float, float] = (-200, 200),
        y_range: tuple[float, float] = (-200, 200),
        z: float = 0.0
    ):
        """Vẽ mặt bàn.
        
        Args:
            x_range: Phạm vi X.
            y_range: Phạm vi Y.
            z: Độ cao mặt bàn.
        """
        # Tạo lưới
        x = np.linspace(x_range[0], x_range[1], 10)
        y = np.linspace(y_range[0], y_range[1], 10)
        X, Y = np.meshgrid(x, y)
        Z = np.ones_like(X) * z
        
        # Vẽ mặt phẳng
        self.ax.plot_surface(X, Y, Z, alpha=0.3, color='gray')
        
        # Vẽ đường grid
        for z_level in [0]:
            self.ax.plot_wireframe(X, Y, Z, alpha=0.1, color='black')
    
    def draw_board_outline(
        self,
        corners: np.ndarray,
        z: float = 0.0,
        color: str = 'blue'
    ):
        """Vẽ outline của ChArUco board.
        
        Args:
            corners: Array shape (4, 3) với 4 góc board.
            z: Độ cao.
            color: Màu.
        """
        if len(corners) < 4:
            return
        
        # Thêm z coordinate
        corners_z = np.column_stack([corners[:, :2], np.ones(len(corners)) * z])
        
        # Vẽ rectangle
        for i in range(4):
            start = corners_z[i]
            end = corners_z[(i + 1) % 4]
            self.ax.plot([start[0], end[0]], 
                        [start[1], end[1]], 
                        [z, z], color=color, linewidth=2)
    
    def draw_camera(
        self,
        position: np.ndarray,
        rotation: np.ndarray | None = None,
        scale: float = 50.0,
        color: str = 'red'
    ):
        """Vẽ camera position.
        
        Args:
            position: Tọa độ [x, y, z].
            rotation: Rotation vector (Rodrigues) để vẽ hướng.
            scale: Kích thước marker.
            color: Màu.
        """
        x, y, z = position
        
        # Marker cho camera
        self.ax.scatter([x], [y], [z], c=color, marker='^', s=200)
        
        # Nếu có rotation, vẽ hướng nhìn
        if rotation is not None:
            import cv2
            R, _ = cv2.Rodrigues(rotation)
            
            # Z-axis của camera (hướng nhìn)
            z_axis = R @ np.array([0, 0, 1])
            
            # Vẽ đường hướng nhìn
            self.ax.quiver(x, y, z, 
                          z_axis[0], z_axis[1], z_axis[2],
                          length=scale, color='green', arrow_length_ratio=0.3)
    
    def draw_object(
        self,
        position: np.ndarray,
        name: str = "",
        color: str = 'green',
        size: float = 20.0
    ):
        """Vẽ một đối tượng.
        
        Args:
            position: Tọa độ [x, y, z].
            name: Tên để hiển thị.
            color: Màu.
            size: Kích thước.
        """
        x, y, z = position
        
        marker = self.ax.scatter([x], [y], [z], c=color, s=size*2)
        
        if name:
            self.ax.text(x, y, z + size/2, name, fontsize=8)
        
        self.object_markers.append((position, name, color))
    
    def draw_trajectory(
        self,
        positions: list[np.ndarray],
        color: str = 'purple',
        alpha: float = 0.5
    ):
        """Vẽ trajectory (đường đi) của camera.
        
        Args:
            positions: List các vị trí.
            color: Màu.
            alpha: Độ trong suốt.
        """
        if len(positions) < 2:
            return
        
        positions = np.array(positions)
        self.ax.plot(positions[:, 0], 
                    positions[:, 1], 
                    positions[:, 2],
                    color=color, alpha=alpha, linewidth=1)
    
    def add_text(self, text: str, x: float = 0.02, y: float = 0.98):
        """Thêm text lên figure.
        
        Args:
            text: Nội dung text.
            x, y: Vị trí normalized.
        """
        self.fig.text(x, y, text, transform=self.fig.transFigure,
                     fontsize=10, verticalalignment='top',
                     bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    def show(self, block: bool = True):
        """Hiển thị figure.
        
        Args:
            block: Block cho đến khi đóng window.
        """
        plt.tight_layout()
        plt.show(block=block)
    
    def save(self, path: str, dpi: int = 150):
        """Lưu figure ra file.
        
        Args:
            path: Đường dẫn file.
            dpi: Độ phân giải.
        """
        plt.savefig(path, dpi=dpi, bbox_inches='tight')
    
    def pause(self, interval: float = 0.01):
        """Pause để update animation.
        
        Args:
            interval: Thời gian pause (giây).
        """
        plt.pause(interval)


class Open3DVisualizer:
    """3D Visualizer dùng Open3D (đẹp và nhanh hơn).
    
    Cài đặt: pip install open3d
    """
    
    def __init__(self):
        if not HAS_OPEN3D:
            raise ImportError("open3d not installed. Run: pip install open3d")
        
        self.vis = o3d.visualization.Visualizer()
        self.vis.create_window(window_name='Mono Eye 3D')
        
        # Geometries
        self.geometries = {}
    
    def clear(self):
        """Xóa tất cả geometries."""
        for geo in self.geometries.values():
            self.vis.remove_geometry(geo)
        self.geometries.clear()
    
    def add_coordinate_frame(self, size: float = 100):
        """Thêm coordinate frame."""
        mesh = o3d.geometry.TriangleMesh.create_coordinate_frame(size=size)
        self.vis.add_geometry(mesh)
    
    def add_table(
        self,
        x_range: tuple[float, float] = (-200, 200),
        y_range: tuple[float, float] = (-200, 200),
        z: float = 0.0
    ):
        """Thêm mặt bàn."""
        # Tạo mesh
        mesh = o3d.geometry.TriangleMesh.create_box(
            width=x_range[1] - x_range[0],
            height=y_range[1] - y_range[0],
            depth=1
        )
        
        # Translate đến vị trí
        mesh.translate([
            (x_range[0] + x_range[1]) / 2,
            (y_range[0] + y_range[1]) / 2,
            z - 0.5
        ])
        
        # Màu xám nhạt
        mesh.paint_uniform_color([0.8, 0.8, 0.8])
        
        self.vis.add_geometry(mesh)
        self.geometries['table'] = mesh
    
    def add_sphere(
        self,
        position: np.ndarray,
        radius: float = 20.0,
        color: tuple[float, float, float] = (0, 1, 0),
        name: str = ""
    ):
        """Thêm hình cầu (đối tượng).
        
        Args:
            position: [x, y, z].
            radius: Bán kính.
            color: RGB [0, 1].
            name: Tên.
        """
        sphere = o3d.geometry.TriangleMesh.create_sphere(radius=radius)
        sphere.translate(position)
        sphere.paint_uniform_color(color)
        
        self.vis.add_geometry(sphere)
        self.geometries[name or f'sphere_{len(self.geometries)}'] = sphere
    
    def add_camera_marker(
        self,
        position: np.ndarray,
        rotation: np.ndarray | None = None,
        scale: float = 50.0
    ):
        """Thêm marker cho camera.
        
        Args:
            position: [x, y, z].
            rotation: Rotation vector.
            scale: Kích thước.
        """
        # Tạo frustum đơn giản
        mesh = o3d.geometry.TriangleMesh.create_cone(
            radius=scale * 0.5,
            height=scale
        )
        mesh.translate(position)
        mesh.paint_uniform_color([1, 0, 0])  # Red
        
        self.vis.add_geometry(mesh)
        self.geometries['camera'] = mesh
    
    def update(self):
        """Update visualization."""
        self.vis.update_geometry(None)
        self.vis.poll_events()
        self.vis.update_renderer()
    
    def show(self, block: bool = True):
        """Hiển thị."""
        self.vis.run()
    
    def close(self):
        """Đóng window."""
        self.vis.destroy_window()


def create_visualizer(backend: str = "matplotlib") -> SimpleVisualizer | Open3DVisualizer:
    """Factory function để tạo visualizer.
    
    Args:
        backend: "matplotlib" hoặc "open3d".
        
    Returns:
        Visualizer instance.
    """
    if backend == "open3d":
        return Open3DVisualizer()
    else:
        return SimpleVisualizer()


# =============================================================================
# Realtime Visualization Example
# =============================================================================

def visualize_realtime_example():
    """Ví dụ visualization realtime.
    
    Chạy: uv run python -c "from mono_eye.viz import visualize_realtime_example; visualize_realtime_example()"
    """
    import time
    
    viz = SimpleVisualizer()
    viz.draw_table(x_range=(-300, 300), y_range=(-300, 300))
    
    # Fake trajectory
    trajectory = []
    
    for i in range(100):
        # Clear objects
        viz.clear()
        viz.draw_table()
        
        # Fake camera position
        x = 100 * np.sin(i * 0.1)
        y = 100 * np.cos(i * 0.1)
        z = 300 + 50 * np.sin(i * 0.2)
        pos = np.array([x, y, z])
        
        trajectory.append(pos)
        
        # Draw trajectory
        viz.draw_trajectory(trajectory)
        
        # Draw camera
        viz.draw_camera(pos, color='red')
        
        # Draw some objects
        for j in range(3):
            obj_pos = np.array([50 * j - 50, 0, 0])
            viz.draw_object(obj_pos, name=f"Obj {j}", color='green')
        
        viz.add_text(f"Frame: {i}")
        
        viz.pause(0.05)
    
    viz.show()


if __name__ == "__main__":
    visualize_realtime_example()
```

---

## Unit Tests

### File: `tests/test_viz.py`

```python
"""Tests cho visualization module."""
import pytest
import numpy as np


def test_import_visualizer():
    """Test import module."""
    from mono_eye.viz import SimpleVisualizer, create_visualizer
    assert SimpleVisualizer is not None


def test_scene_object_dataclass():
    """Test SceneObject dataclass."""
    from mono_eye.viz import SceneObject
    
    obj = SceneObject(
        name="test",
        position=np.array([100, 200, 0]),
        color=(0, 255, 0),
        size=20.0
    )
    
    assert obj.name == "test"
    assert np.allclose(obj.position, [100, 200, 0])


def test_table_plane_dataclass():
    """Test TablePlane dataclass."""
    from mono_eye.viz import TablePlane
    
    table = TablePlane(
        bounds=(-200, 200, -200, 200, 0),
        color=(200, 200, 200),
        alpha=0.3
    )
    
    assert table.bounds == (-200, 200, -200, 200, 0)


def test_camera_view_dataclass():
    """Test CameraView dataclass."""
    from mono_eye.viz import CameraView
    
    cam = CameraView(
        position=np.array([0, 0, 300]),
        fov=60.0
    )
    
    assert cam.fov == 60.0
    assert np.allclose(cam.position, [0, 0, 300])


def test_create_visualizer():
    """Test factory function."""
    from mono_eye.viz import create_visualizer, SimpleVisualizer
    
    viz = create_visualizer("matplotlib")
    assert isinstance(viz, SimpleVisualizer)


def test_visualizer_init():
    """Test visualizer initialization."""
    from mono_eye.viz import SimpleVisualizer
    
    viz = SimpleVisualizer(figsize=(10, 8))
    assert viz.figsize == (10, 8)
    assert viz.fig is not None
    assert viz.ax is not None
```

---

## Integration với Pipeline

### Script: `scripts/realtime_viz.py`

```python
"""Realtime visualization của pipeline."""
import cv2
from mono_eye.pipeline import MonoEyePipeline
from mono_eye.viz import SimpleVisualizer


def main():
    pipeline = MonoEyePipeline(
        camera_config="data/calib/camera.yaml",
        board_config="bang_calib_A4.yaml"
    )
    
    viz = SimpleVisualizer()
    viz.draw_table(x_range=(-300, 300), y_range=(-300, 300))
    
    cap = cv2.VideoCapture(0)
    
    trajectory = []
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Process frame
            pose, detections = pipeline.process_frame(frame, detect_objects=True)
            
            # Update visualization
            viz.clear()
            viz.draw_table()
            
            if pose.valid:
                center = pose.camera_center
                trajectory.append(center)
                
                # Draw camera
                viz.draw_camera(center, pose.rvec)
                
                # Draw trajectory
                viz.draw_trajectory(trajectory, alpha=0.3)
                
                # Draw detections
                if detections:
                    for det in detections.detections:
                        if det.position_3d is not None:
                            viz.draw_object(
                                det.position_3d,
                                name=f"ID:{det.track_id}",
                                color='green'
                            )
            
            viz.add_text(f"Frame: {pipeline.frame_id}")
            viz.pause(0.01)
            
            # Show frame
            cv2.imshow('Camera', frame)
            if cv2.waitKey(1) == 'q':
                break
    
    finally:
        cap.release()
        cv2.destroyAllWindows()
        viz.show()


if __name__ == "__main__":
    main()
```

---

## Tiêu chí hoàn thành

- [x] `mono_eye/viz.py` viết hoàn chỉnh
- [x] `SimpleVisualizer` class hoạt động
- [x] `Open3DVisualizer` class (bonus)
- [x] Methods: `draw_table`, `draw_camera`, `draw_object`, `draw_trajectory`
- [x] Realtime update support
- [x] `tests/test_viz.py` viết và pass
- [x] Script `scripts/realtime_viz.py` chạy được (stub OK)

---

## Commands

```bash
# Cài matplotlib (thường đã có)
uv run pip install matplotlib

# Cài open3d (tùy chọn)
uv run pip install open3d

# Chạy tests
uv run pytest tests/test_viz.py -v

# Import test
uv run python -c "from mono_eye.viz import SimpleVisualizer; print('OK')"

# Run example
uv run python scripts/realtime_viz.py
```

---

## Output mong đợi

1. **File `mono_eye/viz.py`** viết hoàn chỉnh
2. **File `tests/test_viz.py`** với ≥ 5 tests
3. **File `scripts/realtime_viz.py`** (stub OK)
4. **Kết quả tests:** `pytest tests/test_viz.py -v` → passed
