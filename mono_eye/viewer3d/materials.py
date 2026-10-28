"""Quản lý vật liệu PBR (Physically-Based Rendering) và nạp Textures với bộ đệm Cache."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import numpy as np
from PIL import Image

from mono_eye.viewer3d.paths import ASSET_ROOT, CACHE_DIR, TEXTURE_ROOT


@dataclass
class PbrMaterial:
    """Đặc tả vật liệu PBR chất lượng cao theo chuẩn Metal-Roughness."""
    name: str
    albedo: Path | tuple[float, float, float] | None = None  # File ảnh texture, màu RGB [0..1] hoặc None
    normal_map: Path | None = None
    roughness_map: Path | None = None
    metallic: float = 0.0
    roughness_factor: float = 1.0
    normal_strength: float = 1.0
    uv_scale: tuple[float, float] = (1.0, 1.0)
    tint: tuple[float, float, float] = (1.0, 1.0, 1.0)


def build_material_table() -> dict[str, PbrMaterial]:
    """Xây dựng bảng vật liệu PBR ánh xạ chính xác với các thành phần của bàn cờ và quân cờ."""
    marble_dir = TEXTURE_ROOT / "Marble020_1K-JPG"
    wood_dir = TEXTURE_ROOT / "Wood062_1K-JPG"

    marble_color = marble_dir / "Marble020_1K-JPG_Color.jpg"
    marble_normal = marble_dir / "Marble020_1K-JPG_NormalGL.jpg"
    marble_rough = marble_dir / "Marble020_1K-JPG_Roughness.jpg"

    wood_color = wood_dir / "Wood062_1K-JPG_Color.jpg"
    wood_normal = wood_dir / "Wood062_1K-JPG_NormalGL.jpg"
    wood_rough = wood_dir / "Wood062_1K-JPG_Roughness.jpg"

    table: dict[str, PbrMaterial] = {
        # Mặt bàn đá cẩm thạch tổng thể
        "Material.007": PbrMaterial(
            name="Material.007",
            albedo=marble_color,
            normal_map=marble_normal,
            roughness_map=marble_rough,
            metallic=0.0,
            roughness_factor=0.6,
            normal_strength=1.0,
            uv_scale=(2.0, 2.0),
            tint=(1.0, 1.0, 1.0),
        ),
        "Material.003": PbrMaterial(
            name="Material.003",
            albedo=marble_color,
            normal_map=marble_normal,
            roughness_map=marble_rough,
            metallic=0.0,
            roughness_factor=0.6,
            normal_strength=1.0,
            uv_scale=(2.0, 2.0),
            tint=(0.95, 0.95, 0.95),
        ),
        # Ô cờ sáng (Marble trắng bóng)
        "Material.004": PbrMaterial(
            name="Material.004",
            albedo=marble_color,
            normal_map=marble_normal,
            roughness_map=marble_rough,
            metallic=0.0,
            roughness_factor=0.4,
            normal_strength=0.8,
            uv_scale=(1.0, 1.0),
            tint=(0.92, 0.92, 0.90),
        ),
        # Ô cờ tối (Đá marble sẫm màu / đen sang trọng)
        "Material.002": PbrMaterial(
            name="Material.002",
            albedo=marble_color,
            normal_map=marble_normal,
            roughness_map=marble_rough,
            metallic=0.0,
            roughness_factor=0.35,
            normal_strength=0.8,
            uv_scale=(1.0, 1.0),
            tint=(0.12, 0.12, 0.14),
        ),
        # Quân cờ trắng (Vân gỗ sáng sơn bóng)
        "bayaz_": PbrMaterial(
            name="bayaz_",
            albedo=wood_color,
            normal_map=wood_normal,
            roughness_map=wood_rough,
            metallic=0.0,
            roughness_factor=0.55,
            normal_strength=0.8,
            uv_scale=(1.0, 1.0),
            tint=(1.00, 0.96, 0.90),
        ),
        # Ô cờ trắng trên bàn cờ (Màu trắng ngà mịn mượt, không dùng texture gỗ sọc)
        "bayaz_.001": PbrMaterial(
            name="bayaz_.001",
            albedo=None,
            normal_map=None,
            roughness_map=None,
            metallic=0.0,
            roughness_factor=0.35,
            normal_strength=0.0,
            uv_scale=(1.0, 1.0),
            tint=(0.92, 0.92, 0.90),
        ),
        # Quân cờ đen (Vân gỗ tối màu óc chó / mun)
        "siyah": PbrMaterial(
            name="siyah",
            albedo=wood_color,
            normal_map=wood_normal,
            roughness_map=wood_rough,
            metallic=0.0,
            roughness_factor=0.45,
            normal_strength=0.8,
            uv_scale=(1.0, 1.0),
            tint=(0.16, 0.13, 0.11),
        ),
        # Ô cờ đen trên bàn cờ (Màu đen tuyền / xám đậm mịn mượt, không dùng texture gỗ sọc)
        "siyah.001": PbrMaterial(
            name="siyah.001",
            albedo=None,
            normal_map=None,
            roughness_map=None,
            metallic=0.0,
            roughness_factor=0.35,
            normal_strength=0.0,
            uv_scale=(1.0, 1.0),
            tint=(0.08, 0.08, 0.09),
        ),
    }

    # Kiểm tra đảm bảo tất cả file texture chỉ định đều tồn tại
    for mat in table.values():
        if isinstance(mat.albedo, Path) and not mat.albedo.exists():
            raise FileNotFoundError(f"Texture albedo không tồn tại: {mat.albedo}")
        if mat.normal_map and not mat.normal_map.exists():
            raise FileNotFoundError(f"Texture normal map không tồn tại: {mat.normal_map}")
        if mat.roughness_map and not mat.roughness_map.exists():
            raise FileNotFoundError(f"Texture roughness map không tồn tại: {mat.roughness_map}")

    return table


def load_texture_image(
    image_path: Path,
    srgb: bool = True,
    is_roughness: bool = False,
    cache_dir: Path | None = None,
) -> tuple[np.ndarray, tuple[int, int]]:
    """Tải texture và chuyển đổi sang mảng uint8 hoặc float32 sẵn sàng nạp OpenGL.
    
    Tự động cache sang .npy trong cache_dir để nạp cực nhanh.
    """
    c_dir = cache_dir if cache_dir is not None else (CACHE_DIR / "textures")
    c_dir.mkdir(parents=True, exist_ok=True)
    cache_file = c_dir / f"{image_path.stem}_{'srgb' if srgb else 'linear'}_{'rough' if is_roughness else 'norm'}.npy"

    if cache_file.exists():
        data = np.load(cache_file)
        return data, (data.shape[1], data.shape[0])

    img = Image.open(image_path)
    if is_roughness:
        # Lấy kênh G chuẩn theo ORM packing cho roughness
        img = img.convert("RGB")
        arr = np.array(img, dtype=np.uint8)
        rough_channel = arr[:, :, 1]
        data = np.ascontiguousarray(rough_channel)
    else:
        # Albedo và Normal map đều dùng RGB 3 kênh chuẩn
        img = img.convert("RGB")
        data = np.ascontiguousarray(np.array(img, dtype=np.uint8))

    # Lật trục Y vì OpenGL đọc ảnh từ dưới lên
    data = np.flipud(data)
    np.save(cache_file, data)
    return data, (img.width, img.height)
