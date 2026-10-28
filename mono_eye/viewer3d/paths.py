"""Đường dẫn và tiện ích quản lý assets cho 3D Chess Viewer."""
from __future__ import annotations

from pathlib import Path

# Thư mục gốc chứa tài nguyên 3D
ASSET_ROOT = Path(__file__).resolve().parents[2] / "gender_3d"
TEXTURE_ROOT = ASSET_ROOT / "textures"
CACHE_DIR = ASSET_ROOT / "cache"
DEFAULT_OBJ = ASSET_ROOT / "chess.obj"
DEFAULT_MTL = ASSET_ROOT / "chess.mtl"


def resolve_texture(rel_or_abs: str | Path, base_dir: Path | None = None) -> Path:
    """Chuyển đổi đường dẫn texture thành đường dẫn Path tuyệt đối hợp lệ.
    
    Hỗ trợ cả dấu phân cách '/' và '\\' trên Windows và Linux.
    """
    p_str = str(rel_or_abs).strip().replace("\\", "/")
    p = Path(p_str)
    if p.is_absolute():
        return p

    base = base_dir if base_dir is not None else ASSET_ROOT
    candidate = (base / p).resolve()
    if candidate.exists():
        return candidate

    # Thử tìm trong TEXTURE_ROOT nếu đường dẫn không bắt đầu bằng 'textures'
    candidate_tex = (TEXTURE_ROOT / p).resolve()
    if candidate_tex.exists():
        return candidate_tex

    return candidate
