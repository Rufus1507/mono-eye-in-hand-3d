from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import cv2

from . import SCHEMA_VERSION, __version__


def source_fingerprint():
    root = Path(__file__).resolve().parents[1]
    paths = sorted((root / "fov_tool").glob("*.py")) + [root / "do_fov.py"]
    digest = __import__("hashlib").sha256()
    for path in paths:
        digest.update(path.name.encode()); digest.update(path.read_bytes())
    return digest.hexdigest()


def _atomic_json(path: Path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


class SessionWriter:
    def __init__(self, root: Path, board_spec, requested: dict, actual: dict,
                 camera: dict):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self.id = f"{stamp}_{uuid4().hex[:8]}"
        self.path = root.resolve() / self.id
        self.frames = self.path / "frames"
        self.runs = self.path / "runs"
        self.frames.mkdir(parents=True)
        self.runs.mkdir()
        shutil.copy2(board_spec.path, self.path / "board.yaml")
        self.manifest = {"schema_version": SCHEMA_VERSION, "tool_version": __version__,
                         "source_sha256": source_fingerprint(), "opencv": cv2.__version__,
                         "session_id": self.id, "status": "capturing",
                         "created_local": datetime.now().astimezone().isoformat(),
                         "created_monotonic_ns": time.monotonic_ns(),
                         "board_sha256": board_spec.sha256,
                         "requested_camera": requested, "actual_camera": actual,
                         "camera": camera, "accepted_frames": 0}
        _atomic_json(self.path / "manifest.json", self.manifest)
        self.obs_path = self.path / "observations.jsonl"

    def add(self, frame, obs, forced=False):
        index = self.manifest["accepted_frames"]
        name = f"frame_{index:04d}.png"
        target = self.frames / name
        if not cv2.imwrite(str(target), frame):
            raise OSError(f"Không ghi được ảnh {target}")
        record = obs.as_json() | {"index": index, "image": f"frames/{name}",
                                  "forced": bool(forced)}
        try:
            with self.obs_path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                stream.flush(); os.fsync(stream.fileno())
        except Exception:
            target.unlink(missing_ok=True)
            raise
        self.manifest["accepted_frames"] = index + 1
        _atomic_json(self.path / "manifest.json", self.manifest)
        return target

    def close(self, status: str, reason: str | None = None):
        self.manifest["status"] = status
        self.manifest["closed_local"] = datetime.now().astimezone().isoformat()
        if reason:
            self.manifest["reason"] = reason
        _atomic_json(self.path / "manifest.json", self.manifest)

    def update_actual_camera(self, values: dict):
        self.manifest["actual_camera"].update(values)
        _atomic_json(self.path / "manifest.json", self.manifest)


def load_session(path: Path):
    path = path.resolve()
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Phiên có schema không được phiên bản này hỗ trợ")
    board_path = path / "board.yaml"
    board_hash = __import__("hashlib").sha256(board_path.read_bytes()).hexdigest()
    if board_hash != manifest.get("board_sha256"):
        raise ValueError("board.yaml trong phiên đã thay đổi hoặc bị hỏng")
    rows = []
    obs_path = path / "observations.jsonl"
    if obs_path.exists():
        for line in obs_path.read_text(encoding="utf-8").splitlines():
            if line.strip(): rows.append(json.loads(line))
    if len(rows) != manifest.get("accepted_frames"):
        raise ValueError("Manifest và observations không cùng số ảnh")
    return manifest, rows


def create_run_dir(session: Path):
    rid = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_" + uuid4().hex[:8]
    path = session.resolve() / "runs" / rid
    path.mkdir(parents=True, exist_ok=False)
    return rid, path
