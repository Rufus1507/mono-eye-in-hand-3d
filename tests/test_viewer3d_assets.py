"""Kiểm thử tính toàn vẹn của tài nguyên 3D (OBJ, MTL, Textures) không cần GPU."""
from __future__ import annotations

from pathlib import Path
import re
import pytest

from mono_eye.viewer3d.mtl import parse_mtl
from mono_eye.viewer3d.obj_loader import load_scene_cached
from mono_eye.viewer3d.paths import ASSET_ROOT, DEFAULT_MTL, DEFAULT_OBJ


def test_no_absolute_paths_in_mtl():
    """Đảm bảo không còn đường dẫn tuyệt đối dạng 'C:\\' hoặc 'D:\\' trong file chess.mtl."""
    content = DEFAULT_MTL.read_text(encoding="utf-8")
    matches = re.findall(r"[A-Za-z]:\\", content)
    assert len(matches) == 0, f"Vẫn còn đường dẫn tuyệt đối trong chess.mtl: {matches}"


def test_all_mtl_textures_exist():
    """Tất cả các texture được tham chiếu trong chess.mtl đều phải tồn tại thực tế trên đĩa."""
    materials = parse_mtl(DEFAULT_MTL)
    assert len(materials) == 9

    checked_textures = 0
    for mat in materials.values():
        if mat.map_kd is not None:
            assert mat.map_kd.exists(), f"Thiếu map_Kd: {mat.map_kd}"
            checked_textures += 1
        if mat.map_bump is not None:
            assert mat.map_bump.exists(), f"Thiếu map_Bump: {mat.map_bump}"
            checked_textures += 1
        if mat.map_ns is not None:
            assert mat.map_ns.exists(), f"Thiếu map_Ns: {mat.map_ns}"
            checked_textures += 1

    assert checked_textures > 0


def test_obj_scene_geometry():
    """Kiểm tra cấu trúc hình học của scene 3D sau khi triangulate."""
    scene = load_scene_cached(DEFAULT_OBJ)
    assert scene.vertices.shape[0] > 400_000
    assert scene.num_tris > 700_000
    assert len(scene.groups) >= 9
    assert scene.indices.shape[0] == scene.num_tris * 3
