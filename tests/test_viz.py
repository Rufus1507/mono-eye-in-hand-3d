"""Unit tests cho module 3D Visualization (Giai đoạn 6)."""
from __future__ import annotations

import pytest
import numpy as np

from mono_eye.viz import (
    CameraView,
    Open3DVisualizer,
    SceneObject,
    SimpleVisualizer,
    TablePlane,
    create_visualizer,
    HAS_OPEN3D,
    HAS_MATPLOTLIB,
)


def test_import_visualizer():
    """Kiểm tra import các lớp và helper từ mono_eye.viz."""
    assert SimpleVisualizer is not None
    assert create_visualizer is not None
    assert SceneObject is not None
    assert TablePlane is not None
    assert CameraView is not None


def test_scene_object_dataclass():
    """Kiểm tra khởi tạo và thuộc tính của SceneObject."""
    obj = SceneObject(
        name="cube_red",
        position=np.array([120.0, -45.0, 10.0]),
        color=(255, 0, 0),
        size=25.0,
        object_type="box",
    )
    assert obj.name == "cube_red"
    assert np.allclose(obj.position, [120.0, -45.0, 10.0])
    assert obj.color == (255, 0, 0)
    assert obj.size == 25.0
    assert obj.object_type == "box"


def test_table_plane_dataclass():
    """Kiểm tra cấu hình mặt phẳng TablePlane."""
    table = TablePlane(
        bounds=(-250.0, 250.0, -200.0, 200.0, 0.0),
        color=(210, 210, 210),
        alpha=0.4,
    )
    assert table.bounds == (-250.0, 250.0, -200.0, 200.0, 0.0)
    assert table.color == (210, 210, 210)
    assert pytest.approx(table.alpha) == 0.4


def test_camera_view_dataclass():
    """Kiểm tra CameraView với tọa độ và hướng quay."""
    pos = np.array([0.0, -50.0, 420.0])
    rot = np.array([3.14, 0.0, 0.0])
    cam = CameraView(position=pos, rotation=rot, fov=65.0)

    assert np.allclose(cam.position, pos)
    assert np.allclose(cam.rotation, rot)
    assert cam.fov == 65.0


def test_create_visualizer_factory():
    """Kiểm tra hàm tạo create_visualizer."""
    viz = create_visualizer("matplotlib")
    assert isinstance(viz, SimpleVisualizer)

    if not HAS_OPEN3D:
        with pytest.raises(ImportError):
            create_visualizer("open3d")
    else:
        o3d_viz = create_visualizer("open3d")
        assert isinstance(o3d_viz, Open3DVisualizer)


def test_simple_visualizer_init():
    """Kiểm tra khởi tạo SimpleVisualizer."""
    viz = SimpleVisualizer(figsize=(8, 6))
    assert viz.figsize == (8, 6)
    assert viz.fig is not None
    assert viz.ax is not None


def test_simple_visualizer_draw_methods():
    """Kiểm tra các phương thức vẽ trong SimpleVisualizer không phát sinh lỗi."""
    viz = SimpleVisualizer(figsize=(6, 5))

    # Vẽ bàn
    viz.draw_table(x_range=(-200.0, 200.0), y_range=(-150.0, 150.0), z=0.0)

    # Vẽ viền ChArUco board
    board_corners = np.array([
        [-100.0, -70.0],
        [100.0, -70.0],
        [100.0, 70.0],
        [-100.0, 70.0],
    ])
    viz.draw_board_outline(board_corners, z=0.0, color="blue")

    # Vẽ camera có và không có rotation
    viz.draw_camera(np.array([0.0, 0.0, 300.0]), rotation=None)
    viz.draw_camera(np.array([10.0, -10.0, 350.0]), rotation=np.array([np.pi, 0.0, 0.0]))

    # Vẽ vật thể
    viz.draw_object(np.array([50.0, 20.0, 0.0]), name="Item1", color="red", size=15.0)
    assert len(viz.object_markers) == 1

    # Vẽ quỹ đạo trajectory
    traj = [
        np.array([0.0, 0.0, 300.0]),
        np.array([10.0, 5.0, 310.0]),
        np.array([20.0, 10.0, 320.0]),
    ]
    viz.draw_trajectory(traj)

    # Thêm text và xóa
    viz.add_text("Test Frame 10")
    viz.clear()
    assert len(viz.object_markers) == 0
