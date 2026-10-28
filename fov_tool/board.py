from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import yaml


@dataclass(frozen=True)
class BoardSpec:
    path: Path
    sha256: str
    squares_x: int
    squares_y: int
    dictionary: str
    marker_ratio: float
    square_mm: float | None


def load_board(path: str | Path):
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy cấu hình bảng: {path}")
    raw = path.read_bytes()
    cfg = yaml.safe_load(raw.decode("utf-8")) or {}
    b = cfg.get("bang") or {}
    if "ti_le_marker_tren_o" not in b and "canh_o_mm" in b and "marker_mm" in b:
        b["ti_le_marker_tren_o"] = float(b["marker_mm"]) / float(b["canh_o_mm"])
    required = ("o_ngang", "o_doc", "tu_dien", "ti_le_marker_tren_o")
    missing = [key for key in required if key not in b]
    if missing:
        raise ValueError(f"Cấu hình bảng thiếu: {', '.join(missing)}")
    sx, sy = int(b["o_ngang"]), int(b["o_doc"])
    ratio = float(b["ti_le_marker_tren_o"])
    if sx < 3 or sy < 3 or not 0.0 < ratio < 1.0:
        raise ValueError("Số ô phải >= 3 và tỷ lệ marker phải nằm trong (0, 1)")
    dictionary_name = "DICT_" + str(b["tu_dien"])
    if not hasattr(cv2.aruco, dictionary_name):
        raise ValueError(f"OpenCV không có từ điển {dictionary_name}")
    dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dictionary_name))

    if "id_bat_dau" in b or "ids_start" in b:
        id_start = int(b.get("id_bat_dau", b.get("ids_start", 0)))
        charuco_dummy = cv2.aruco.CharucoBoard((sx, sy), 1.0, ratio, dictionary)
        n_m = len(charuco_dummy.getIds())
        custom_ids = np.arange(id_start, id_start + n_m, dtype=np.int32).reshape(-1, 1)
        board = cv2.aruco.CharucoBoard((sx, sy), 1.0, ratio, dictionary, ids=custom_ids)
    else:
        board = cv2.aruco.CharucoBoard((sx, sy), 1.0, ratio, dictionary)

    detector = cv2.aruco.CharucoDetector(board)
    square_mm = (cfg.get("ban_in") or {}).get("canh_o_mm") or b.get("canh_o_mm")
    spec = BoardSpec(path, hashlib.sha256(raw).hexdigest(), sx, sy,
                     str(b["tu_dien"]), ratio,
                     None if square_mm is None else float(square_mm))
    return spec, board, detector
