"""Bộ lọc ổn định quân cờ thời gian thực (PieceStabilizer) chống hiện tượng nhấp nháy và nhảy cờ."""
from __future__ import annotations

from collections import Counter
from typing import Any


def square_distance(sq1: str, sq2: str) -> int:
    """Tính khoảng cách ô cờ Chebyshev (max(|col1 - col2|, |rank1 - rank2|))."""
    if not sq1 or not sq2 or len(sq1) < 2 or len(sq2) < 2:
        return 999
    c1, r1 = ord(sq1[0].lower()) - ord("a"), int(sq1[1])
    c2, r2 = ord(sq2[0].lower()) - ord("a"), int(sq2[1])
    return max(abs(c1 - c2), abs(r1 - r2))


class PieceStabilizer:
    """Quản lý trạng thái và ổn định quân cờ trên bàn cờ theo thời gian (Temporal Hysteresis & Spatial Dedup).
    
    Giải quyết 3 vấn đề:
    1. Chống nhấp nháy (Flicker Persistence): Duy trì quân cờ thêm `persist_frames` (mặc định 5 frames)
       nếu YOLO tạm thời không phát hiện được do góc nghiêng hoặc che khuất nhẹ giữa các khung hình.
    2. Chống nhảy cờ & bóng ma lân cận (Confirmation Delay & Spatial Dedup):
       - Yêu cầu xác nhận (min_hits=2): Quân cờ mới phải xuất hiện ít nhất 2 frames mới được hiển thị,
         loại bỏ hoàn toàn các detection ngẫu nhiên 1 frame.
       - Khử trùng lặp ô lân cận (Spatial Dedup): Khi quân cờ dao động qua lại ranh giới giữa 2 ô
         (ví dụ e3 và e4), chỉ giữ lại 1 ô có độ tin cậy và tần suất cao hơn, không để 2 quân cùng xuất hiện.
    3. Ổn định loại quân cờ (Class Debounce): Tránh nhầm lẫn đổi class liên tục giữa các frame
       bằng cách đếm tần suất xuất hiện (majority vote) trên cửa sổ lịch sử.
    """

    def __init__(
        self,
        persist_frames: int = 5,
        min_hits: int = 2,
        debounce_frames: int = 3,
        min_conf_pawn: float = 0.45,
    ) -> None:
        self.persist_frames = max(1, persist_frames)
        self.min_hits = max(1, min_hits)
        self.debounce_frames = max(1, debounce_frames)
        self.min_conf_pawn = min_conf_pawn

        # square -> {
        #   "piece": dict,
        #   "ttl": int,
        #   "hits": int,
        #   "recent_seen": list[bool],
        #   "class_history": list[str],
        #   "confidence_history": list[float],
        # }
        self.tracks: dict[str, dict[str, Any]] = {}

    def reset(self) -> None:
        """Đặt lại toàn bộ trạng thái bám vết (dùng khi đổi video hoặc phát lại từ đầu)."""
        self.tracks.clear()

    def feed(self, current_pieces: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Cập nhật frame mới và trả về danh sách quân cờ đã được ổn định.
        
        Args:
            current_pieces: Danh sách quân cờ phát hiện được ở frame hiện tại từ pipeline.
            
        Returns:
            Danh sách quân cờ đã qua bộ lọc ổn định thời gian và khử bóng ma.
        """
        seen_squares: set[str] = set()
        unassigned_pieces: list[dict[str, Any]] = []

        for p in current_pieces:
            square = p.get("square")
            class_name = p.get("class_name")
            conf = float(p.get("confidence", 0.5))

            if not class_name:
                continue

            # Lọc ngưỡng tin cậy riêng cho quân chốt để tránh nhận diện nhầm vào marker ChArUco
            if "pawn" in class_name and conf < self.min_conf_pawn:
                continue

            if not square:
                # Quân cờ chưa gán được vào ô nào (ví dụ đang di chuyển ngoài bàn)
                unassigned_pieces.append(dict(p))
                continue

            seen_squares.add(square)

            if square not in self.tracks:
                self.tracks[square] = {
                    "piece": dict(p),
                    "ttl": self.persist_frames,
                    "hits": 1,
                    "recent_seen": [True],
                    "class_history": [class_name],
                    "confidence_history": [conf],
                }
            else:
                track = self.tracks[square]
                track["ttl"] = self.persist_frames  # Làm mới thời gian sống
                track["hits"] += 1
                track["recent_seen"].append(True)
                if len(track["recent_seen"]) > 6:
                    track["recent_seen"].pop(0)

                track["class_history"].append(class_name)
                track["confidence_history"].append(conf)

                if len(track["class_history"]) > 15:
                    track["class_history"].pop(0)
                if len(track["confidence_history"]) > 15:
                    track["confidence_history"].pop(0)

                if p.get("position_3d") is not None:
                    track["piece"]["position_3d"] = p["position_3d"]

                # Ổn định class: Dùng majority vote trên 7 frame gần nhất
                recent_classes = track["class_history"][-7:]
                counts = Counter(recent_classes)
                dominant_class = counts.most_common(1)[0][0]
                track["piece"]["class_name"] = dominant_class

                recent_confs = track["confidence_history"][-5:]
                track["piece"]["confidence"] = sum(recent_confs) / len(recent_confs)

        # Xử lý các ô không nhìn thấy ở frame này
        dead_squares: list[str] = []
        for square, track in self.tracks.items():
            if square not in seen_squares:
                track["ttl"] -= 1
                track["recent_seen"].append(False)
                if len(track["recent_seen"]) > 6:
                    track["recent_seen"].pop(0)

                if track["ttl"] <= 0:
                    dead_squares.append(square)

        for sq in dead_squares:
            del self.tracks[sq]

        # 1. Lọc điều kiện hiển thị (Confirmation Delay):
        # Chỉ quân có ít nhất min_hits hoặc được phát hiện >= 2 lần trong 4 frame gần nhất mới được hiển thị
        candidate_tracks: dict[str, dict[str, Any]] = {}
        for square, track in self.tracks.items():
            recent_hits = sum(track["recent_seen"][-4:])
            if track["hits"] >= self.min_hits and recent_hits >= 1:
                candidate_tracks[square] = track

        # 2. Khử trùng lặp không gian (Spatial Dedup):
        # Nếu có 2 track cùng loại quân cờ ở 2 ô liền kề (khoảng cách <= 1 ô do nhiễu ranh giới),
        # chỉ giữ lại 1 ô có độ tin cậy và số lần hit cao hơn
        suppressed_squares: set[str] = set()
        squares_list = list(candidate_tracks.keys())

        for i in range(len(squares_list)):
            sq1 = squares_list[i]
            if sq1 in suppressed_squares:
                continue
            t1 = candidate_tracks[sq1]
            cls1 = t1["piece"].get("class_name")

            for j in range(i + 1, len(squares_list)):
                sq2 = squares_list[j]
                if sq2 in suppressed_squares:
                    continue
                t2 = candidate_tracks[sq2]
                cls2 = t2["piece"].get("class_name")

                # Cùng loại quân và ở ô liền kề
                if cls1 == cls2 and square_distance(sq1, sq2) <= 1:
                    score1 = t1["hits"] * 2.0 + float(t1["piece"].get("confidence", 0.5)) + (2.0 if sq1 in seen_squares else 0.0)
                    score2 = t2["hits"] * 2.0 + float(t2["piece"].get("confidence", 0.5)) + (2.0 if sq2 in seen_squares else 0.0)

                    if score1 >= score2:
                        suppressed_squares.add(sq2)
                    else:
                        suppressed_squares.add(sq1)
                        break

        # Trả về danh sách quân cờ đã qua toàn bộ các lớp lọc
        stabilized: list[dict[str, Any]] = []
        for square, track in candidate_tracks.items():
            if square not in suppressed_squares:
                stabilized.append(dict(track["piece"]))

        stabilized.extend(unassigned_pieces)
        return stabilized
