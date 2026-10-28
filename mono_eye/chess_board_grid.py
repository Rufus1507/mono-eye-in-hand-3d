"""Module xử lý hình học lưới bàn cờ 8x8, phân xử ô cờ và sinh chuỗi FEN cho mono_eye."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence
import numpy as np


# Chiều cao vật lý tiêu chuẩn ước lượng của các quân cờ (mm) theo số đo thực tế
CHESS_PIECE_HEIGHTS: dict[str, float] = {
    "king": 65.0,
    "queen": 57.0,
    "bishop": 47.0,
    "knight": 41.0,
    "rook": 37.0,
    "pawn": 33.0,
}


def get_piece_true_height(class_name: str) -> Optional[float]:
    """Lấy chiều cao chuẩn danh nghĩa (mm) theo loại quân cờ (quân trắng và đen bằng nhau)."""
    c = str(class_name).lower()
    for piece_type, h in CHESS_PIECE_HEIGHTS.items():
        if piece_type in c:
            return h
    return None


@dataclass
class BoardGrid8x8:
    """Mô hình hình học lưới bàn cờ 8x8 ô vuông."""

    square_size_mm: float = 40.0
    cols: int = 8
    rows: int = 8
    # Gốc (0,0) tại góc ngoài ô A1, +X sang cột H, +Y sang hàng 8
    col_names: list[str] = field(default_factory=lambda: ["a", "b", "c", "d", "e", "f", "g", "h"])
    rank_names: list[str] = field(default_factory=lambda: ["1", "2", "3", "4", "5", "6", "7", "8"])

    def __post_init__(self):
        if len(self.col_names) < self.cols:
            self.col_names = [chr(ord("a") + i) for i in range(self.cols)]
        if len(self.rank_names) < self.rows:
            self.rank_names = [str(i + 1) for i in range(self.rows)]

    @property
    def width_mm(self) -> float:
        return self.cols * self.square_size_mm

    @property
    def height_mm(self) -> float:
        return self.rows * self.square_size_mm

    def coord_to_square(self, x_mm: float, y_mm: float, margin_mm: float = 20.0) -> Optional[str]:
        """Chuyển đổi tọa độ 3D (X, Y) sang tên ô cờ vua (ví dụ 'e4', 'a1').

        Args:
            x_mm: Tọa độ X trên mặt bàn cờ (mm).
            y_mm: Tọa độ Y trên mặt bàn cờ (mm).
            margin_mm: Độ dung sai cho phép ngoài mép bàn cờ (mm).

        Returns:
            Tên ô cờ (ví dụ 'e4') hoặc None nếu nằm ngoài bàn cờ.
        """
        if (
            x_mm < -margin_mm
            or x_mm >= self.width_mm + margin_mm
            or y_mm < -margin_mm
            or y_mm >= self.height_mm + margin_mm
        ):
            return None

        # Giới hạn chỉ số trong [0, 7]
        c = int(np.clip(int(np.floor(x_mm / self.square_size_mm)), 0, self.cols - 1))
        r = int(np.clip(int(np.floor(y_mm / self.square_size_mm)), 0, self.rows - 1))

        return f"{self.col_names[c]}{self.rank_names[r]}"

    def square_to_center(self, square: str) -> Optional[tuple[float, float]]:
        """Trả về tọa độ tâm lý thuyết (X, Y) của một ô cờ (mm).

        Args:
            square: Tên ô cờ (ví dụ 'e4', 'a1').
        """
        if not square or len(square) < 2:
            return None
        col_char = square[0].lower()
        rank_char = square[1]

        if col_char not in self.col_names or rank_char not in self.rank_names:
            return None

        c_idx = self.col_names.index(col_char)
        r_idx = self.rank_names.index(rank_char)

        x_center = (c_idx + 0.5) * self.square_size_mm
        y_center = (r_idx + 0.5) * self.square_size_mm
        return (x_center, y_center)

    def square_to_col_row(self, square: str) -> Optional[tuple[int, int]]:
        """Trả về chỉ số (col_idx, row_idx) trong khoảng [0, 7]."""
        if not square or len(square) < 2:
            return None
        col_char = square[0].lower()
        rank_char = square[1]
        if col_char not in self.col_names or rank_char not in self.rank_names:
            return None
        return (self.col_names.index(col_char), self.rank_names.index(rank_char))

    def assign_pieces_to_squares(
        self,
        pieces: list[dict[str, Any]],
        max_dist_to_center_mm: float = 35.0,
    ) -> list[dict[str, Any]]:
        """Gán từng quân cờ vào đúng một ô cờ duy nhất (xử lý xung đột khi nhiều quân cờ).

        Nếu có 2 quân cờ cùng rơi vào 1 ô do góc nhìn nghiêng, quân cờ gần tâm ô hơn
        sẽ được ưu tiên giữ ô đó; quân còn lại sẽ được gán vào ô lân cận trống gần nhất.
        """
        candidates: list[dict[str, Any]] = []

        for p in pieces:
            p_copy = dict(p)
            pos_3d = p_copy.get("position_3d")

            if pos_3d is None:
                p_copy["square"] = None
                p_copy["dist_to_center_mm"] = None
                candidates.append(p_copy)
                continue

            x, y = float(pos_3d[0]), float(pos_3d[1])
            sq = self.coord_to_square(x, y)
            if sq is not None:
                center = self.square_to_center(sq)
                dist = float(np.hypot(x - center[0], y - center[1])) if center else float("inf")
            else:
                dist = float("inf")

            p_copy["raw_square"] = sq
            p_copy["dist_to_center_mm"] = dist
            candidates.append(p_copy)

        # Sắp xếp các quân cờ hợp lệ theo độ tin cậy và khoảng cách tâm
        # Ưu tiên quân có khoảng cách tâm nhỏ và confidence cao
        valid_indices = [
            i for i, p in enumerate(candidates)
            if p.get("raw_square") is not None and p["dist_to_center_mm"] <= max_dist_to_center_mm
        ]

        # Sắp xếp các ứng viên theo dist_to_center_mm tăng dần
        valid_indices.sort(key=lambda idx: candidates[idx]["dist_to_center_mm"])

        occupied_squares: dict[str, int] = {}  # square -> index in candidates

        for idx in valid_indices:
            p = candidates[idx]
            raw_sq = p["raw_square"]

            if raw_sq not in occupied_squares:
                occupied_squares[raw_sq] = idx
                p["square"] = raw_sq
            else:
                # Xung đột: ô đã có quân khác chiếm
                # Tìm ô liền kề trống có khoảng cách gần nhất
                pos = p.get("position_3d")
                x, y = float(pos[0]), float(pos[1])
                best_neighbor = None
                best_n_dist = float("inf")

                curr_col, curr_row = self.square_to_col_row(raw_sq)
                for dc in [-1, 0, 1]:
                    for dr in [-1, 0, 1]:
                        if dc == 0 and dr == 0:
                            continue
                        nc, nr = curr_col + dc, curr_row + dr
                        if 0 <= nc < self.cols and 0 <= nr < self.rows:
                            n_sq = f"{self.col_names[nc]}{self.rank_names[nr]}"
                            if n_sq not in occupied_squares:
                                n_center = self.square_to_center(n_sq)
                                n_dist = float(np.hypot(x - n_center[0], y - n_center[1]))
                                if n_dist < best_n_dist and n_dist <= max_dist_to_center_mm * 1.5:
                                    best_n_dist = n_dist
                                    best_neighbor = n_sq

                if best_neighbor is not None:
                    occupied_squares[best_neighbor] = idx
                    p["square"] = best_neighbor
                    p["dist_to_center_mm"] = best_n_dist
                else:
                    p["square"] = None  # Bỏ gán nếu không tìm được ô hợp lệ

        for i, p in enumerate(candidates):
            if "square" not in p:
                p["square"] = None

        return candidates

    def generate_fen(self, pieces: list[dict[str, Any]]) -> str:
        """Tạo chuỗi vị trí quân cờ FEN (Forsyth–Edwards Notation) từ các quân cờ đã gán ô.

        Chuỗi FEN duyệt từ hàng 8 xuống hàng 1, và từ cột 'a' sang cột 'h'.
        """
        board_grid: dict[str, str] = {}
        for p in pieces:
            sq = p.get("square")
            fen_char = p.get("fen_char", "?")
            if sq and fen_char and fen_char != "?":
                board_grid[sq.lower()] = fen_char

        fen_rows: list[str] = []
        standard_files = ["a", "b", "c", "d", "e", "f", "g", "h"]
        ranks = ["8", "7", "6", "5", "4", "3", "2", "1"]

        for r in ranks:
            empty_count = 0
            row_str = ""
            for f in standard_files:
                sq = f"{f}{r}"
                if sq in board_grid:
                    if empty_count > 0:
                        row_str += str(empty_count)
                        empty_count = 0
                    row_str += board_grid[sq]
                else:
                    empty_count += 1
            if empty_count > 0:
                row_str += str(empty_count)
            fen_rows.append(row_str)

        return "/".join(fen_rows)


def compensate_piece_occlusions(
    pieces: list[dict[str, Any]],
    iou_occlusion_thresh: float = 0.25,
) -> list[dict[str, Any]]:
    """Xử lý che khuất khi nhiều quân cờ đứng thẳng hàng nhìn từ góc nghiêng camera.

    Quân cờ phía trước (có đáy y2 lớn hơn) che chân đế của quân cờ phía sau (y2 nhỏ hơn).
    Thuật toán sắp xếp theo độ sâu (Depth Sorting) và bù trừ điểm tiếp xúc chân quân cờ.
    """
    if not pieces:
        return []

    processed = [dict(p) for p in pieces]

    # Sắp xếp theo y2 giảm dần (quân gần camera hơn đứng trước)
    processed.sort(key=lambda p: p.get("bbox", [0, 0, 0, 0])[3], reverse=True)

    for i in range(len(processed)):
        curr = processed[i]
        curr["is_occluded"] = False
        curr_box = curr.get("bbox", [])
        if len(curr_box) != 4:
            continue

        cx1, cy1, cx2, cy2 = curr_box
        curr_width = cx2 - cx1
        curr_height = cy2 - cy1
        curr_bottom = (curr.get("bottom_center_pixel") or ((cx1 + cx2) / 2.0, cy2))

        # So sánh với tất cả các quân cờ đứng trước (j < i)
        for j in range(i):
            front = processed[j]
            front_box = front.get("bbox", [])
            if len(front_box) != 4:
                continue
            fx1, fy1, fx2, fy2 = front_box

            # Kiểm tra xem điểm chân của quân sau có nằm trong hoặc sát cạnh trên của quân trước
            bx, by = curr_bottom
            if fx1 <= bx <= fx2 and (fy1 - 0.2 * curr_height) <= by <= fy2:
                curr["is_occluded"] = True
                curr["occluded_by"] = front.get("class_name", "unknown")

                # Bù chân đế: nếu chân bị che, ước lượng lại điểm đáy
                # Dùng tỷ lệ chiều cao/chiều rộng đặc trưng của quân cờ để ước lượng chiều cao thực
                c_name = str(curr.get("class_name", "")).lower()
                expected_aspect = 2.2  # Chiều cao ~ 2.2 lần chiều rộng đế
                if "pawn" in c_name:
                    expected_aspect = 1.8
                elif "king" in c_name or "queen" in c_name:
                    expected_aspect = 2.6

                estimated_height = curr_width * expected_aspect
                if curr_height < estimated_height * 0.8:
                    # Bounding box bị cắt cụt đáy bởi thân quân phía trước
                    adjusted_v = cy1 + estimated_height
                    curr["bottom_center_pixel"] = (bx, adjusted_v)
                break

    return processed
