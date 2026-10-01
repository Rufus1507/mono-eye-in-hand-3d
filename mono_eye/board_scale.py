"""Cạnh ô THẬT của tấm ChArUco đã in, tính từ các số đo bằng thước.

Hiệu chuẩn camera (fov_tool) coi cạnh ô = 1.0 vì K không phụ thuộc thang đo. Nhưng tọa độ 3D
thì phụ thuộc: sai thang đo là sai mọi kết quả. Nên ở đây dùng số đo thật.

File bảng (bang_calib_*.yaml) có sẵn các trường kiem_in:
    thuoc_ngang_mm / thuoc_doc_mm      độ dài danh nghĩa của hai thước in ở lề giấy
    do_duoc_ngang_mm / do_duoc_doc_mm  độ dài bạn ĐO ĐƯỢC của hai thước đó sau khi in
Tỉ lệ ngang = do_duoc_ngang / thuoc_ngang, tỉ lệ dọc tương tự. Hai tỉ lệ phải gần bằng nhau
(nếu lệch thì bảng bị méo, theo tao_bang.py là phải in lại).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


class BoardNotMeasured(RuntimeError):
    """Chưa điền do_duoc_ngang_mm / do_duoc_doc_mm trong file bảng."""


@dataclass(frozen=True)
class BoardScale:
    design_square_mm: float
    scale_x: float
    scale_y: float
    square_mm: float          # cạnh ô thật = thiết kế * tỉ lệ trung bình
    anisotropy: float         # |sx - sy| / trung bình


def board_scale(board_yaml: str | Path, max_anisotropy: float = 0.005) -> BoardScale:
    """Tính cạnh ô thật. `max_anisotropy` (0.5% mặc định, tạm thời) là độ lệch cho phép
    giữa tỉ lệ ngang và dọc; vượt ngưỡng thì báo lỗi (in lại bảng)."""
    cfg = yaml.safe_load(Path(board_yaml).read_text(encoding="utf-8")) or {}
    printed = cfg.get("ban_in") or {}
    check = cfg.get("kiem_in") or {}
    design = printed.get("canh_o_mm")
    if design is None:
        raise ValueError(f"{board_yaml} thiếu ban_in.canh_o_mm")
    need = ("thuoc_ngang_mm", "thuoc_doc_mm", "do_duoc_ngang_mm", "do_duoc_doc_mm")
    if any(check.get(k) is None for k in need):
        raise BoardNotMeasured(
            "Chưa có số đo thật: điền kiem_in.do_duoc_ngang_mm và do_duoc_doc_mm "
            f"trong {board_yaml} sau khi đo hai thước in ở lề giấy."
        )
    sx = float(check["do_duoc_ngang_mm"]) / float(check["thuoc_ngang_mm"])
    sy = float(check["do_duoc_doc_mm"]) / float(check["thuoc_doc_mm"])
    mean = (sx + sy) / 2.0
    aniso = abs(sx - sy) / mean
    if aniso > max_anisotropy:
        raise ValueError(
            f"Tỉ lệ ngang {sx:.4f} khác tỉ lệ dọc {sy:.4f} ({aniso:.2%}): bảng in bị méo, nên in lại."
        )
    return BoardScale(float(design), sx, sy, float(design) * mean, aniso)
