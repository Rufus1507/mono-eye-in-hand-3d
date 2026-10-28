"""Bộ nạp và xử lý mô hình Wavefront OBJ với bộ đệm Cache (.npz) tốc độ cao."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
import numpy as np

from mono_eye.viewer3d.paths import ASSET_ROOT, CACHE_DIR, DEFAULT_OBJ


@dataclass
class MeshGroup:
    """Nhóm lưới bề mặt chia theo Object và Material."""
    name: str
    material: str
    start_tri: int
    tri_count: int
    indices: np.ndarray  # uint32


@dataclass
class ObjData:
    """Dữ liệu hình học 3D đã được triangulate và chuẩn hóa buffer."""
    vertices: np.ndarray   # float32 (N, 3)
    normals: np.ndarray    # float32 (N, 3)
    texcoords: np.ndarray  # float32 (N, 2)
    indices: np.ndarray    # uint32 (Total_Tris * 3,)
    groups: list[MeshGroup]
    num_tris: int


def parse_obj(obj_path: str | Path) -> ObjData:
    """Phân tích file .obj lớn, triangulate quad/n-gon và mở rộng corner v/vt/vn."""
    path = Path(obj_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file OBJ: {path}")

    t0 = time.time()
    v_list: list[list[float]] = []
    vt_list: list[list[float]] = []
    vn_list: list[list[float]] = []

    # Map corner tuple (v_idx, vt_idx, vn_idx) -> unique_vertex_idx
    corner_map: dict[tuple[int, int, int], int] = {}
    out_pos: list[list[float]] = []
    out_norm: list[list[float]] = []
    out_uv: list[list[float]] = []

    group_records: list[tuple[str, str, list[int]]] = []
    current_object = "default"
    current_material = "default"
    current_indices: list[int] = []

    def switch_group(new_obj: str, new_mat: str):
        nonlocal current_object, current_material, current_indices
        if current_indices:
            group_records.append((current_object, current_material, current_indices))
            current_indices = []
        current_object = new_obj
        current_material = new_mat

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line or line.startswith("#"):
                continue
            first_char = line[0]
            if first_char == "v":
                parts = line.split()
                prefix = parts[0]
                if prefix == "v":
                    v_list.append([float(parts[1]), float(parts[2]), float(parts[3])])
                elif prefix == "vt":
                    vt_list.append([float(parts[1]), float(parts[2])])
                elif prefix == "vn":
                    vn_list.append([float(parts[1]), float(parts[2]), float(parts[3])])
            elif first_char == "f":
                tokens = line.split()[1:]
                n_tokens = len(tokens)
                if n_tokens < 3:
                    continue

                # Parse corner indices cho từng đỉnh trong face
                face_corners: list[int] = []
                for tok in tokens:
                    sub = tok.split("/")
                    # OBJ 1-based indexing
                    vi = int(sub[0]) - 1 if sub[0] else 0
                    vti = int(sub[1]) - 1 if len(sub) > 1 and sub[1] else 0
                    vni = int(sub[2]) - 1 if len(sub) > 2 and sub[2] else 0
                    key = (vi, vti, vni)
                    idx = corner_map.get(key)
                    if idx is None:
                        idx = len(corner_map)
                        corner_map[key] = idx
                        out_pos.append(v_list[vi])
                        out_uv.append(vt_list[vti] if vti < len(vt_list) else [0.0, 0.0])
                        out_norm.append(vn_list[vni] if vni < len(vn_list) else [0.0, 1.0, 0.0])
                    face_corners.append(idx)

                # Fan triangulation cho triangle, quad, hoặc n-gon
                c0 = face_corners[0]
                for i in range(1, n_tokens - 1):
                    current_indices.extend([c0, face_corners[i], face_corners[i + 1]])

            elif first_char == "o":
                parts = line.split()
                new_obj = parts[1] if len(parts) > 1 else "default"
                switch_group(new_obj, current_material)
            elif first_char == "u" and line.startswith("usemtl"):
                parts = line.split()
                new_mat = parts[1] if len(parts) > 1 else "default"
                switch_group(current_object, new_mat)

    # Đóng group cuối cùng
    if current_indices:
        group_records.append((current_object, current_material, current_indices))

    # Chuyển đổi sang mảng numpy tối ưu
    vertices = np.array(out_pos, dtype=np.float32)
    normals = np.array(out_norm, dtype=np.float32)
    texcoords = np.array(out_uv, dtype=np.float32)

    # Khắc phục lỗi thiếu UV ở thân quân xe (kale) trong file OBJ gốc:
    # Tự động sinh Cylindrical UV Mapping cho các đỉnh có UV thoái hóa [0, 0]
    for g_obj, g_mat, idx_list in group_records:
        if "kale" in g_obj.lower():
            g_indices = np.array(idx_list, dtype=np.int64)
            unique_indices = np.unique(g_indices)
            g_verts = vertices[unique_indices]
            g_uvs = texcoords[unique_indices]

            zero_mask = (g_uvs[:, 0] == 0.0) & (g_uvs[:, 1] == 0.0)
            if np.any(zero_mask):
                cx = (g_verts[:, 0].min() + g_verts[:, 0].max()) / 2.0
                cz = (g_verts[:, 2].min() + g_verts[:, 2].max()) / 2.0
                ymin = g_verts[:, 1].min()
                ymax = g_verts[:, 1].max()
                height = max(ymax - ymin, 1e-4)

                zero_indices = unique_indices[zero_mask]
                z_verts = vertices[zero_indices]
                angles = np.arctan2(z_verts[:, 2] - cz, z_verts[:, 0] - cx)
                texcoords[zero_indices, 0] = (angles / (2.0 * np.pi)) + 0.5
                texcoords[zero_indices, 1] = (z_verts[:, 1] - ymin) / height

    # Đảm bảo trục V của texture coordinate được xử lý đúng (OBJ UV origin bottom-left)
    all_indices_list: list[int] = []
    mesh_groups: list[MeshGroup] = []
    current_tri_start = 0

    for g_obj, g_mat, idx_list in group_records:
        if not idx_list:
            continue
        g_idx_arr = np.array(idx_list, dtype=np.uint32)
        n_tris = len(g_idx_arr) // 3
        mesh_groups.append(MeshGroup(
            name=g_obj,
            material=g_mat,
            start_tri=current_tri_start,
            tri_count=n_tris,
            indices=g_idx_arr,
        ))
        all_indices_list.extend(idx_list)
        current_tri_start += n_tris

    all_indices = np.array(all_indices_list, dtype=np.uint32)
    total_tris = len(all_indices) // 3
    _append_single_pawn_groups(mesh_groups)
    t_cost = time.time() - t0
    print(f"[OBJ Loader] Parsed {path.name}: {len(vertices)} vertices, {total_tris} triangles, {len(mesh_groups)} groups in {t_cost:.2f}s")

    return ObjData(
        vertices=vertices,
        normals=normals,
        texcoords=texcoords,
        indices=all_indices,
        groups=mesh_groups,
        num_tris=total_tris,
    )


def _append_single_pawn_groups(groups: list[MeshGroup]) -> None:
    """Tách 1 quân chốt đơn lẻ từ hàng 8 chốt để render từng quân theo phát hiện thực tế."""
    single_pawn_groups: list[MeshGroup] = []
    group_names = {g.name for g in groups}
    for g in groups:
        if g.name == "piyon_Cylinder.001" and "piyon_single" not in group_names:
            single_pawn_groups.append(MeshGroup(
                name="piyon_single",
                material=g.material,
                start_tri=g.start_tri,
                tri_count=13710 // 3,
                indices=g.indices[:13710].copy(),
            ))
        elif g.name == "piyon.001_Cylinder.013" and "piyon.001_single" not in group_names:
            single_pawn_groups.append(MeshGroup(
                name="piyon.001_single",
                material=g.material,
                start_tri=g.start_tri,
                tri_count=13710 // 3,
                indices=g.indices[:13710].copy(),
            ))
    groups.extend(single_pawn_groups)


def save_scene_cache(obj_data: ObjData, cache_file: Path) -> None:
    """Lưu trữ dữ liệu ObjData vào file .npz nén để khởi động tức thì."""
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    group_names = [g.name for g in obj_data.groups]
    group_mats = [g.material for g in obj_data.groups]
    group_starts = [g.start_tri for g in obj_data.groups]
    group_counts = [g.tri_count for g in obj_data.groups]

    np.savez_compressed(
        cache_file,
        vertices=obj_data.vertices,
        normals=obj_data.normals,
        texcoords=obj_data.texcoords,
        indices=obj_data.indices,
        group_names=np.array(group_names, dtype=str),
        group_mats=np.array(group_mats, dtype=str),
        group_starts=np.array(group_starts, dtype=np.int32),
        group_counts=np.array(group_counts, dtype=np.int32),
        num_tris=obj_data.num_tris,
    )


def load_scene_cached(
    obj_path: str | Path | None = None,
    cache_dir: str | Path | None = None,
    force_rebuild: bool = False,
) -> ObjData:
    """Tải dữ liệu 3D từ bộ đệm .npz. Nếu chưa có thì parse và lưu cache."""
    path = Path(obj_path) if obj_path is not None else DEFAULT_OBJ
    c_dir = Path(cache_dir) if cache_dir is not None else CACHE_DIR
    cache_file = c_dir / f"{path.stem}_scene.npz"

    if cache_file.exists() and not force_rebuild:
        t0 = time.time()
        with np.load(cache_file, allow_pickle=True) as data:
            vertices = data["vertices"]
            normals = data["normals"]
            texcoords = data["texcoords"]
            indices = data["indices"]
            group_names = data["group_names"]
            group_mats = data["group_mats"]
            group_starts = data["group_starts"]
            group_counts = data["group_counts"]
            num_tris = int(data["num_tris"])

            groups: list[MeshGroup] = []
            for name, mat, start, count in zip(group_names, group_mats, group_starts, group_counts):
                g_start_idx = start * 3
                g_end_idx = (start + count) * 3
                g_indices = indices[g_start_idx:g_end_idx]
                groups.append(MeshGroup(
                    name=str(name),
                    material=str(mat),
                    start_tri=int(start),
                    tri_count=int(count),
                    indices=g_indices,
                ))

            _append_single_pawn_groups(groups)

        print(f"[OBJ Loader] Loaded cache {cache_file.name}: {len(vertices)} vertices, {num_tris} triangles in {time.time()-t0:.3f}s (Cache Hit)")
        return ObjData(
            vertices=vertices,
            normals=normals,
            texcoords=texcoords,
            indices=indices,
            groups=groups,
            num_tris=num_tris,
        )

    # Chưa có cache -> parse OBJ và lưu cache
    obj_data = parse_obj(path)
    save_scene_cache(obj_data, cache_file)
    return obj_data
