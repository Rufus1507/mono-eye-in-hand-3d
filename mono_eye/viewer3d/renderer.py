"""Trình kết xuất đồ họa ModernGL PBR chất lượng cao tận dụng GPU RTX 3060."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import moderngl

from mono_eye.viewer3d.camera import OrbitCamera
from mono_eye.viewer3d.materials import PbrMaterial, build_material_table, load_texture_image
from mono_eye.viewer3d.obj_loader import MeshGroup, ObjData
from mono_eye.viewer3d.semantics import IGNORE_OBJECTS
from mono_eye.viewer3d.shaders import BACKGROUND_FRAGMENT, BACKGROUND_VERTEX, PBR_FRAGMENT, PBR_VERTEX


class Chess3DRenderer:
    """Renderer OpenGL sử dụng ModernGL, hỗ trợ PBR Shading, Normal Mapping và Offscreen Framebuffer."""

    def __init__(self, ctx: moderngl.Context, obj_data: ObjData) -> None:
        self.ctx = ctx
        self.obj_data = obj_data
        self.mat_table = build_material_table()

        # Bật Depth Test và Face Culling
        self.ctx.enable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
        self.ctx.depth_func = "<="

        # Biên dịch Shader Programs
        self.pbr_prog = self.ctx.program(
            vertex_shader=PBR_VERTEX,
            fragment_shader=PBR_FRAGMENT,
        )
        self.bg_prog = self.ctx.program(
            vertex_shader=BACKGROUND_VERTEX,
            fragment_shader=BACKGROUND_FRAGMENT,
        )

        # Chuẩn bị Background Quad
        bg_vertices = np.array([
            -1.0, -1.0,
             1.0, -1.0,
            -1.0,  1.0,
             1.0,  1.0,
        ], dtype=np.float32)
        self.bg_vbo = self.ctx.buffer(bg_vertices.tobytes())
        self.bg_vao = self.ctx.simple_vertex_array(self.bg_prog, self.bg_vbo, "in_pos")

        # Nạp và khởi tạo Textures trên GPU
        self.gl_textures: dict[str, moderngl.Texture] = {}
        self._init_textures()

        # Tạo VAO cho từng Mesh Group
        self.group_vaos: list[tuple[MeshGroup, moderngl.VertexArray]] = []
        self.group_index_by_name: dict[str, int] = {}
        self._init_mesh_vaos()

        # Dictionary lưu trữ ma trận biến đổi Model riêng cho từng group (để di chuyển quân cờ)
        self.group_transforms: dict[int, np.ndarray] = {}

    def _init_textures(self) -> None:
        """Tải và đưa tất cả texture cần thiết vào bộ nhớ GPU."""
        for mat in self.mat_table.values():
            # 1. Albedo
            if isinstance(mat.albedo, Path):
                key = str(mat.albedo)
                if key not in self.gl_textures:
                    arr, (w, h) = load_texture_image(mat.albedo, srgb=True)
                    comp = 1 if arr.ndim == 2 else arr.shape[2]
                    tex = self.ctx.texture((w, h), comp, arr.tobytes())
                    tex.build_mipmaps()
                    tex.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
                    self.gl_textures[key] = tex

            # 2. Normal Map
            if mat.normal_map:
                key = str(mat.normal_map)
                if key not in self.gl_textures:
                    arr, (w, h) = load_texture_image(mat.normal_map, srgb=False)
                    comp = 1 if arr.ndim == 2 else arr.shape[2]
                    tex = self.ctx.texture((w, h), comp, arr.tobytes())
                    tex.build_mipmaps()
                    tex.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
                    self.gl_textures[key] = tex

            # 3. Roughness Map
            if mat.roughness_map:
                key = str(mat.roughness_map)
                if key not in self.gl_textures:
                    arr, (w, h) = load_texture_image(mat.roughness_map, is_roughness=True)
                    comp = 1 if arr.ndim == 2 else arr.shape[2]
                    tex = self.ctx.texture((w, h), comp, arr.tobytes())
                    tex.build_mipmaps()
                    tex.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
                    self.gl_textures[key] = tex

        # Default white texture (1x1)
        white_arr = np.array([255, 255, 255], dtype=np.uint8)
        self.white_tex = self.ctx.texture((1, 1), 3, white_arr.tobytes())

    def _init_mesh_vaos(self) -> None:
        """Ghép dữ liệu pos, normal, uv thành Interleaved Buffer và nạp vào VBO/IBO."""
        v = self.obj_data.vertices
        n = self.obj_data.normals
        uv = self.obj_data.texcoords

        # Interleaved array: [x, y, z, nx, ny, nz, u, v] (8 float32 = 32 bytes)
        interleaved = np.hstack([v, n, uv]).astype(np.float32)
        vbo = self.ctx.buffer(interleaved.tobytes())

        for group in self.obj_data.groups:
            if group.name in IGNORE_OBJECTS:
                continue

            ibo = self.ctx.buffer(group.indices.tobytes())
            vao = self.ctx.vertex_array(
                self.pbr_prog,
                [
                    (vbo, "3f 3f 2f", "in_position", "in_normal", "in_texcoord"),
                ],
                index_buffer=ibo,
                index_element_size=4,
            )
            idx = len(self.group_vaos)
            self.group_vaos.append((group, vao))
            self.group_index_by_name[group.name] = idx

    def render(
        self,
        camera: OrbitCamera,
        viewport_size: tuple[int, int],
        instances: list[tuple[int, np.ndarray]] | None = None,
        hidden_groups: set[str] | None = None,
    ) -> None:
        """Thực thi chu trình render hoàn chỉnh một khung hình.
        
        Args:
            camera: Camera phối cảnh (OrbitCamera hoặc PoseCamera)
            viewport_size: Kích thước vùng vẽ (width, height)
            instances: Danh sách các thực thể quân cờ động [(group_index, model_matrix), ...]
            hidden_groups: Tập hợp tên các group tĩnh cần ẩn (ví dụ: các quân cờ tĩnh bake sẵn)
        """
        w, h = viewport_size
        aspect = max(float(w) / max(float(h), 1.0), 1e-4)

        # Clear color buffer và depth buffer
        self.ctx.clear(color=(0.02, 0.03, 0.05, 1.0), depth=1.0)

        # 1. Background Pass (Tắt depth write để background luôn ở vô tận)
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.bg_vao.render(moderngl.TRIANGLE_STRIP)
        self.ctx.enable(moderngl.DEPTH_TEST)

        # 2. Main PBR Scene Pass
        V = camera.view_matrix()
        P = camera.projection_matrix(aspect)
        cam_eye = camera.eye

        # Thiết lập Global Uniforms
        self.pbr_prog["u_view"].write(V.T.tobytes())
        self.pbr_prog["u_proj"].write(P.T.tobytes())
        self.pbr_prog["u_cam_pos"].value = tuple(cam_eye)

        identity_model = np.eye(4, dtype=np.float32)

        # 2.1. Vẽ các nhóm tĩnh (Bàn cờ, viền, ô đá...) - bỏ qua nhóm trong hidden_groups
        for i, (group, vao) in enumerate(self.group_vaos):
            if hidden_groups is not None and group.name in hidden_groups:
                continue

            mat_desc = self.mat_table.get(group.material)
            if mat_desc is None:
                continue

            # Áp dụng model matrix riêng nếu group có transform
            M = self.group_transforms.get(i, identity_model)
            self._render_single_group(group, vao, mat_desc, M)

        # 2.2. Vẽ các instances quân cờ động (Dynamic Pieces detected from camera)
        if instances is not None:
            for group_idx, M in instances:
                if 0 <= group_idx < len(self.group_vaos):
                    group, vao = self.group_vaos[group_idx]
                    mat_desc = self.mat_table.get(group.material)
                    if mat_desc is not None:
                        self._render_single_group(group, vao, mat_desc, M)

    def _render_single_group(
        self,
        group: MeshGroup,
        vao: moderngl.VertexArray,
        mat_desc: PbrMaterial,
        M: np.ndarray,
    ) -> None:
        """Render một group hình học với ma trận biến đổi Model và vật liệu chỉ định."""
        normal_matrix = np.linalg.inv(M[:3, :3]).T.astype(np.float32)

        self.pbr_prog["u_model"].write(M.T.tobytes())
        self.pbr_prog["u_normal_mat"].write(normal_matrix.T.tobytes())

        # Thiết lập Material Uniforms
        self.pbr_prog["u_tint"].value = mat_desc.tint
        self.pbr_prog["u_uv_scale"].value = mat_desc.uv_scale
        self.pbr_prog["u_metallic"].value = mat_desc.metallic
        self.pbr_prog["u_roughness_factor"].value = mat_desc.roughness_factor
        self.pbr_prog["u_normal_strength"].value = mat_desc.normal_strength

        # Bind Albedo
        if isinstance(mat_desc.albedo, Path) and str(mat_desc.albedo) in self.gl_textures:
            tex = self.gl_textures[str(mat_desc.albedo)]
            tex.use(location=0)
        else:
            self.white_tex.use(location=0)
        self.pbr_prog["u_albedo_map"].value = 0

        # Bind Normal Map
        if mat_desc.normal_map and str(mat_desc.normal_map) in self.gl_textures:
            tex = self.gl_textures[str(mat_desc.normal_map)]
            tex.use(location=1)
            self.pbr_prog["u_has_normal_map"].value = 1
        else:
            self.pbr_prog["u_has_normal_map"].value = 0
        self.pbr_prog["u_normal_map"].value = 1

        # Bind Roughness Map
        if mat_desc.roughness_map and str(mat_desc.roughness_map) in self.gl_textures:
            tex = self.gl_textures[str(mat_desc.roughness_map)]
            tex.use(location=2)
            self.pbr_prog["u_has_rough_map"].value = 1
        else:
            self.pbr_prog["u_has_rough_map"].value = 0
        self.pbr_prog["u_roughness_map"].value = 2

        # Render mesh group
        vao.render(moderngl.TRIANGLES)
