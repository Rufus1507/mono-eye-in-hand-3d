"""Đọc cấu hình chung của phần mono_eye (configs/mono3d.yaml)."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "mono3d.yaml"


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict:
    """Trả về cấu hình YAML dạng dict."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve(path: str | Path) -> Path:
    """Đường dẫn tương đối trong cấu hình được hiểu là tính từ thư mục gốc của repo."""
    p = Path(path)
    return p if p.is_absolute() else ROOT / p
