"""Cạnh ô THẬT của tấm ChArUco đã in, tính từ số đo bằng thước.

Hiệu chuẩn camera (fov_tool) coi cạnh ô = 1.0 vì K không phụ thuộc thang đo. Nhưng tọa độ 3D thì
phụ thuộc: sai thang đo là sai mọi kết quả. Nên ở đây dùng số đo thật.

Số đo nằm trong configs/mono3d.yaml (mục board.measured), KHÔNG nằm trong file bảng:
    board_width_mm   : từ mép ngoài trái tới mép ngoài phải của cả bảng (các ô đen ở hai góc)
    board_height_mm  : từ mép ngoài trên tới mép ngoài dưới của cả bảng
Giá trị danh nghĩa lấy từ file bảng: kiem_in.ca_bang_ngang_mm / ca_bang_doc_mm.
Các trường kiem_in.do_duoc_* và thuoc_* của file bảng KHÔNG được dùng ở đây: tao_bang.py không
nói rõ do_duoc_* ứng với thước lề hay với cả bảng, nên mono_eye dùng trường riêng, tên rõ nghĩa.

Tỉ lệ ngang = đo được / danh nghĩa theo chiều ngang, tỉ lệ dọc tương tự. Hai tỉ lệ phải gần
nhau; lệch nhiều nghĩa là bảng in bị méo (tao_bang.py: phải in lại).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_MAX_ANISOTROPY = 0.015  # 1.5 %, tạm thời: đo lệch ngược chiều 1 mm ở cả hai chiều đã cho ~1.1 %


class BoardNotMeasured(RuntimeError):
    """Chưa điền board.measured.* trong configs/mono3d.yaml."""


@dataclass(frozen=True)
class BoardScale:
    design_square_mm: float
    scale_x: float
    scale_y: float
    square_mm: float          # cạnh ô thật = thiết kế * tỉ lệ trung bình
    anisotropy: float         # |sx - sy| / trung bình


def _nominal(board_yaml: Path) -> tuple[float, float, float]:
    cfg = yaml.safe_load(board_yaml.read_text(encoding="utf-8")) or {}
    bang, printed, check = (cfg.get(k) or {} for k in ("bang", "ban_in", "kiem_in"))
    try:
        square = float(printed["canh_o_mm"])
        w = float(check["ca_bang_ngang_mm"])
        h = float(check["ca_bang_doc_mm"])
        nx, ny = int(bang["o_ngang"]), int(bang["o_doc"])
    except KeyError as e:
        raise ValueError(f"{board_yaml} thiếu trường {e}") from e
    # Bắt lỗi file bảng không nhất quán với chính nó (sai quá 0.2 %).
    if abs(w - nx * square) / w > 0.002 or abs(h - ny * square) / h > 0.002:
        raise ValueError(f"{board_yaml}: ca_bang_* không khớp số ô x canh_o_mm")
    return square, w, h


def board_scale(board_yaml: str | Path, measured_width_mm: float | None,
                measured_height_mm: float | None,
                max_anisotropy: float = DEFAULT_MAX_ANISOTROPY) -> BoardScale:
    if measured_width_mm is None or measured_height_mm is None:
        raise BoardNotMeasured(
            "Chưa có số đo thật: điền board.measured.board_width_mm và board_height_mm "
            "trong configs/mono3d.yaml sau khi đo cả bảng đã in."
        )
    square, w, h = _nominal(Path(board_yaml))
    sx = float(measured_width_mm) / w
    sy = float(measured_height_mm) / h
    mean = (sx + sy) / 2.0
    aniso = abs(sx - sy) / mean
    if aniso > max_anisotropy:
        raise ValueError(
            f"Tỉ lệ ngang {sx:.4f} khác tỉ lệ dọc {sy:.4f} ({aniso:.2%} > {max_anisotropy:.2%}): "
            "đo lại bằng thước thép; nếu vẫn lệch thì bảng in bị méo, nên in lại."
        )
    return BoardScale(square, sx, sy, square * mean, aniso)


def board_scale_from_config(cfg: dict) -> BoardScale:
    """Tính từ cấu hình mono3d.yaml đã load (dùng mono_eye.config.load_config)."""
    from mono_eye.config import resolve

    b = cfg["board"]
    m = b.get("measured") or {}
    return board_scale(resolve(b["file"]), m.get("board_width_mm"), m.get("board_height_mm"),
                       float(b.get("max_anisotropy", DEFAULT_MAX_ANISOTROPY)))
