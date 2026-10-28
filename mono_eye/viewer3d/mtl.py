"""Bộ phân tích file vật liệu Wavefront (.mtl) cho 3D Chess Viewer."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re

from mono_eye.viewer3d.paths import resolve_texture


@dataclass
class MtlMaterial:
    """Định nghĩa một vật liệu từ file .mtl."""
    name: str
    kd: tuple[float, float, float] = (1.0, 1.0, 1.0)
    ks: tuple[float, float, float] = (0.5, 0.5, 0.5)
    ns: float = 225.0
    ni: float = 1.45
    alpha: float = 1.0
    map_kd: Path | None = None
    map_bump: Path | None = None
    map_ns: Path | None = None
    bump_scale: float = 1.0


def parse_mtl(mtl_path: str | Path) -> dict[str, MtlMaterial]:
    """Phân tích file .mtl và trả về từ điển {tên_vật_liệu: MtlMaterial}.
    
    Tự động chuẩn hóa và kiểm tra sự tồn tại của các file textures.
    Raise FileNotFoundError nếu bất kỳ texture nào được chỉ định không tồn tại.
    """
    path = Path(mtl_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file MTL: {path}")

    base_dir = path.parent
    materials: dict[str, MtlMaterial] = {}
    current: MtlMaterial | None = None
    missing_textures: list[str] = []

    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()
        tag = parts[0].lower()

        if tag == "newmtl":
            mat_name = parts[1]
            current = MtlMaterial(name=mat_name)
            materials[mat_name] = current
        elif current is None:
            continue
        elif tag == "kd" and len(parts) >= 4:
            current.kd = (float(parts[1]), float(parts[2]), float(parts[3]))
        elif tag == "ks" and len(parts) >= 4:
            current.ks = (float(parts[1]), float(parts[2]), float(parts[3]))
        elif tag == "ns" and len(parts) >= 2:
            current.ns = float(parts[1])
        elif tag == "ni" and len(parts) >= 2:
            current.ni = float(parts[1])
        elif tag == "d" and len(parts) >= 2:
            current.alpha = float(parts[1])
        elif tag == "map_kd":
            tex_sub = line[len(parts[0]):].strip()
            tex_path = resolve_texture(tex_sub, base_dir)
            if not tex_path.exists():
                missing_textures.append(f"{current.name}: map_Kd -> {tex_path}")
            current.map_kd = tex_path
        elif tag == "map_bump":
            # Hỗ trợ cú pháp map_Bump -bm 0.6 <file> hoặc map_Bump <file>
            match_bm = re.search(r"-bm\s+([0-9.]+)\s+(.+)", line, re.IGNORECASE)
            if match_bm:
                current.bump_scale = float(match_bm.group(1))
                tex_sub = match_bm.group(2).strip()
            else:
                tex_sub = line[len(parts[0]):].strip()
            tex_path = resolve_texture(tex_sub, base_dir)
            if not tex_path.exists():
                missing_textures.append(f"{current.name}: map_Bump -> {tex_path}")
            current.map_bump = tex_path
        elif tag == "map_ns":
            tex_sub = line[len(parts[0]):].strip()
            tex_path = resolve_texture(tex_sub, base_dir)
            if not tex_path.exists():
                missing_textures.append(f"{current.name}: map_Ns -> {tex_path}")
            current.map_ns = tex_path

    if missing_textures:
        err_msg = "Phát hiện textures không tồn tại trong MTL:\n" + "\n".join(missing_textures)
        raise FileNotFoundError(err_msg)

    return materials
