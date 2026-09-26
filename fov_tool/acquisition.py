from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .observations import Observation, common_motion, pose_change


@dataclass
class CaptureDecision:
    status: str
    accept: tuple[object, Observation] | None = None


class AutoCapture:
    """Pure state machine: stable interval -> best frame -> wait for pose change."""
    def __init__(self, stable_ms=400, max_median_px=0.8, max_p90_px=1.5,
                 min_quality=5.0, buffer_size=20):
        self.stable_ns = int(stable_ms * 1_000_000)
        self.max_median_px = max_median_px
        self.max_p90_px = max_p90_px
        self.min_quality = min_quality
        self.buffer = deque(maxlen=buffer_size)
        self.state = "searching"
        self.stable_since = None
        self.previous = None
        self.accepted = None

    def update(self, frame, obs: Observation | None):
        # Moi chuoi status duoi day di thang vao cv2.putText, ma font Hershey
        # CHI ve duoc ASCII -> bat buoc viet tieng Viet KHONG DAU.
        if obs is None:
            self.buffer.clear(); self.previous = None; self.stable_since = None
            return CaptureDecision("Khong thay du goc ChArUco")
        if self.state == "wait_change":
            change = pose_change(self.accepted, obs)
            if not change["changed"]:
                return CaptureDecision("Doi vi tri, kich thuoc hoac goc nghieng cua bang")
            self.state = "stabilizing"; self.previous = None; self.stable_since = None
            self.buffer.clear()
        motion = None if self.previous is None else common_motion(self.previous, obs)
        self.previous = obs
        if motion is None or motion["median_px"] > self.max_median_px or motion["p90_px"] > self.max_p90_px:
            self.buffer.clear(); self.buffer.append((frame.copy(), obs))
            self.stable_since = obs.timestamp_ns
            self.state = "stabilizing"
            return CaptureDecision("Giu bang yen")
        self.buffer.append((frame.copy(), obs))
        if self.stable_since is None:
            self.stable_since = obs.timestamp_ns
        elapsed = obs.timestamp_ns - self.stable_since
        if elapsed < self.stable_ns:
            return CaptureDecision(f"Giu yen {elapsed/1e6:.0f}/{self.stable_ns/1e6:.0f} ms")
        best = max(self.buffer, key=lambda item: item[1].quality)
        if best[1].quality < self.min_quality:
            return CaptureDecision("Anh chua du net theo ca hai huong")
        self.accepted = best[1]; self.state = "wait_change"; self.buffer.clear()
        return CaptureDecision("Da luu; hay doi tu the", best)
