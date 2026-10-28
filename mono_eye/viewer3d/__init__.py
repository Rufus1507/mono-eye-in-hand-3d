"""Gói 3D Chess Viewer chất lượng cao (ModernGL + PBR Textures) cho Mono-Eye."""
from __future__ import annotations

from mono_eye.viewer3d.paths import (
    ASSET_ROOT,
    CACHE_DIR,
    DEFAULT_MTL,
    DEFAULT_OBJ,
    TEXTURE_ROOT,
    resolve_texture,
)
from mono_eye.viewer3d.mtl import MtlMaterial, parse_mtl
from mono_eye.viewer3d.obj_loader import MeshGroup, ObjData, load_scene_cached, parse_obj
from mono_eye.viewer3d.camera import OrbitCamera, OrbitController, PoseCamera
from mono_eye.viewer3d.renderer import Chess3DRenderer
from mono_eye.viewer3d.app import ViewerApp
from mono_eye.viewer3d.scene_api import Chess3DScene
from mono_eye.viewer3d.board_transform import board_mm_to_scene, scene_cam_from_pose, fov_y_from_K
from mono_eye.viewer3d.piece_mapper import PIECE_GROUP_NAMES, PIECE_MESH_BY_CLASS, build_piece_instances
from mono_eye.viewer3d.offscreen import OffscreenRenderer
from mono_eye.viewer3d.live_view import Live3DView

__all__ = [
    "ASSET_ROOT",
    "TEXTURE_ROOT",
    "CACHE_DIR",
    "DEFAULT_OBJ",
    "DEFAULT_MTL",
    "resolve_texture",
    "MtlMaterial",
    "parse_mtl",
    "MeshGroup",
    "ObjData",
    "parse_obj",
    "load_scene_cached",
    "OrbitCamera",
    "OrbitController",
    "PoseCamera",
    "Chess3DRenderer",
    "ViewerApp",
    "Chess3DScene",
    "board_mm_to_scene",
    "scene_cam_from_pose",
    "fov_y_from_K",
    "PIECE_GROUP_NAMES",
    "PIECE_MESH_BY_CLASS",
    "build_piece_instances",
    "OffscreenRenderer",
    "Live3DView",
]
