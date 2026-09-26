"""Nhap anh/video do nguoi khac chup thanh mot phien, cung dinh dang phien tu chup.

Khac voi tu chup: khong dieu khien duoc camera, khong thay truc tiep, nen moi
cong kiem tra phai lam SAU tren tap anh nhan duoc, va moi anh bi loai phai ghi
ro ly do vao manifest.

Nhung loi hay gap o anh gui den va cach xu ly:
- Dien thoai xoay anh bang the EXIF Orientation. Doc theo huong CAM BIEN (bo
  qua the xoay): K thuoc ve cam bien, anh doc/ngang chi la cung cam bien.
- Tron do phan giai, hoac tron ong kinh/zoom (dien thoai tu chuyen ong kinh khi
  zoom): la HAI camera khac nhau, fit chung cho ket qua vo nghia ma khong bao
  loi. Giu nhom dong nhat, loai phan con lai.
- Anh mo, anh trung tu the: dung lai cong chat luong va cong doi tu the cua
  tu chup. Anh trung tu the con lam bootstrap danh gia THAP sai so (THIET_KE §5),
  nen o day so voi MOI anh da nhan, khong chi anh lien truoc.
- Video: cho tung khung qua dung may trang thai AutoCapture, lay moc thoi gian
  tu so thu tu khung, nen cung cong on dinh/net/doi tu the nhu tu chup.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from .acquisition import AutoCapture
from .observations import _corner_quality, detect, pose_change

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".webm"}

# EXIF: 0x010F Make, 0x0110 Model, 0x0112 Orientation (IFD0);
# 0x920A FocalLength, 0xA404 DigitalZoomRatio (Exif IFD 0x8769).
_EXIF_IFD = 0x8769


QUALITY_LONG_SIDE = 1920


def detect_scaled_quality(gray, detector, min_corners=12, timestamp_ns=None):
    """detect() tren anh goc, nhung diem net cham tren ban thu ve canh dai <= 1920 px.

    Diem net la gradient tren moi DIEM ANH, nen cung mot do nhoe quang hoc, anh
    nhieu diem anh hon cho diem thap hon: do tren phien tham chieu 1080p, phong
    to x2 thi 20/20 anh tut duoi nguong 5.0 (median 5.58 -> 4.39). Nguong 5.0
    duoc dat tren webcam <= 1920 px, nen dua anh ve dung vung do truoc khi cham.
    Goc va hieu chuan van dung anh goc. Anh <= 1920 px: khong doi gi.
    """
    obs = detect(gray, detector, min_corners, timestamp_ns)
    long_side = max(gray.shape[:2])
    if obs is None or long_side <= QUALITY_LONG_SIDE:
        return obs
    f = QUALITY_LONG_SIDE / long_side
    small = cv2.resize(gray, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    # Tam diem anh: goc (x, y) o anh goc -> ((x + .5) * f - .5) o anh nho.
    corners = (obs.corners.astype(np.float64) + .5) * f - .5
    obs.quality, obs.quality_x, obs.quality_y, obs.contrast = _corner_quality(small, corners)
    return obs


def same_pose(a, b):
    """Hai anh co cung tu the khong.

    KHONG dung thang pose_change()["changed"]: khi hai anh co < 8 goc chung no tra
    changed=False (hop voi tu chup: chua du so sanh thi cho tiep). O day thieu goc
    chung nghia la hai anh nhin hai vung bang khac nhau, tuc KHAC tu the - dung
    ham goc thi anh 3 va anh 25 cua phien tham chieu bi loai oan.
    """
    change = pose_change(a, b)
    return change.get("reason") != "not-enough-common-corners" and not change["changed"]


def natural_key(path: Path):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]


def collect_inputs(paths):
    """Tra ve (anh, video, bo_qua) theo thu tu ten tu nhien."""
    images, videos, ignored = [], [], []
    for p in paths:
        p = Path(p)
        candidates = sorted((q for q in p.iterdir() if q.is_file()), key=natural_key) if p.is_dir() else [p]
        for q in candidates:
            ext = q.suffix.lower()
            if ext in IMAGE_EXT: images.append(q)
            elif ext in VIDEO_EXT: videos.append(q)
            else: ignored.append(q)
    return images, videos, ignored


def sha256_file(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _num(value):
    try:
        return None if value is None else round(float(value), 4)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def probe_image(path: Path):
    """Kich thuoc theo huong cam bien + nhan dang camera tu EXIF, khong giai ma anh."""
    from PIL import Image
    try:
        with Image.open(path) as im:
            size = tuple(im.size)
            exif = im.getexif()
            sub = exif.get_ifd(_EXIF_IFD) if exif else {}
            make = str(exif.get(0x010F, "")).strip() or None
            model = str(exif.get(0x0110, "")).strip() or None
            focal = _num(sub.get(0x920A))
            zoom = _num(sub.get(0xA404))
            if zoom in (0.0, 1.0): zoom = None
            orientation = exif.get(0x0112)
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return {"ok": True, "size": size,
            "camera_key": [make, model, focal, zoom],
            "orientation": None if orientation is None else int(orientation)}


def read_gray(path: Path):
    """Doc theo huong cam bien; chuyen xam dung cach tu chup lam (cvtColor BGR->GRAY)."""
    data = np.fromfile(str(path), np.uint8)  # np.fromfile: duong dan Unicode tren Windows
    image = cv2.imdecode(data, cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
    if image is None:
        return None
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


@dataclass
class ImportResult:
    size: tuple[int, int] | None
    accepted: list = field(default_factory=list)   # (gray, obs, record)
    records: list = field(default_factory=list)    # moi tep/khung: quyet dinh + ly do
    frames_read: int | None = None                 # chi video

    def counts(self):
        return Counter(r["decision"] for r in self.records)


def import_images(images, detector, min_corners=12, min_quality=5.0):
    result = ImportResult(None)
    probes = {}
    for path in images:
        probes[path] = probe_image(path)
    good = [p for p in images if probes[p]["ok"]]
    for p in images:
        if not probes[p]["ok"]:
            result.records.append({"file": str(p), "decision": "unreadable",
                                   "detail": probes[p]["error"]})
    if not good:
        return result
    # Nhom dong nhat lon nhat theo (kich thuoc, camera). Hoa thi lay nhom gap truoc.
    groups = Counter((probes[p]["size"], tuple(probes[p]["camera_key"])) for p in good)
    (size, key), _ = groups.most_common(1)[0]
    result.size = size
    for index, path in enumerate(good):
        pr = probes[path]
        rec = {"file": str(path), "sha256": sha256_file(path), "size": list(pr["size"]),
               "camera_key": pr["camera_key"], "exif_orientation": pr["orientation"]}
        result.records.append(rec)
        if pr["size"] != size:
            rec["decision"] = "size_mismatch"; continue
        if tuple(pr["camera_key"]) != key:
            rec["decision"] = "different_camera_or_zoom"; continue
        gray = read_gray(path)
        if gray is None:
            rec["decision"] = "unreadable"; continue
        if (gray.shape[1], gray.shape[0]) != size:
            # Pillow va OpenCV hieu kich thuoc khac nhau: khong doan, loai.
            rec["decision"] = "size_mismatch"; rec["detail"] = "decoder_disagrees"; continue
        obs = detect_scaled_quality(gray, detector, min_corners, index + 1)
        if obs is None:
            rec["decision"] = "board_not_found"; continue
        rec["quality"] = obs.quality; rec["corners"] = int(len(obs.ids))
        if obs.quality < min_quality:
            rec["decision"] = "blurry"; continue
        same = next((r for _, o, r in result.accepted
                     if same_pose(o, obs)), None)
        if same is not None:
            rec["decision"] = "same_pose"; rec["detail"] = same["file"]; continue
        rec["decision"] = "accepted"
        result.accepted.append((gray, obs, rec))
    return result


def import_video(path: Path, detector, min_corners=12, stable_ms=400,
                 motion_median=.8, motion_p90=1.5, min_quality=5.0, buffer=20, step=1):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return ImportResult(None, records=[{"file": str(path), "decision": "unreadable"}])
    # Giu huong cam bien, giong anh: khong tu xoay theo metadata cua video.
    cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 0)
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or not np.isfinite(fps) or fps <= 0:
        cap.release()
        return ImportResult(None, records=[{"file": str(path), "decision": "unreadable",
                                            "detail": "fps_unknown"}])
    machine = None
    result = ImportResult(None)
    digest = sha256_file(path)
    frame_index = -1
    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            frame_index += 1
            if frame_index % step:
                continue
            size = (frame.shape[1], frame.shape[0])
            if result.size is None:
                result.size = size
                # Nguong "dung yen" tinh bang diem anh, dat tren webcam <= 1920 px:
                # nhan theo cung ti le nhu diem net (xem detect_scaled_quality).
                s = max(1.0, max(size) / QUALITY_LONG_SIDE)
                machine = AutoCapture(stable_ms, motion_median * s, motion_p90 * s, min_quality, buffer)
            elif size != result.size:
                result.records.append({"file": str(path), "frame": frame_index,
                                       "decision": "size_mismatch"})
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            timestamp_ns = int(round(frame_index * 1e9 / fps))
            decision = machine.update(gray, detect_scaled_quality(gray, detector, min_corners, timestamp_ns))
            if decision.accept:
                chosen, obs = decision.accept
                # Khung duoc chon la khung net nhat trong bo dem, khong phai khung vua doc.
                chosen_index = int(round(obs.timestamp_ns * fps / 1e9))
                # AutoCapture chi so voi anh nhan LIEN TRUOC; so them voi moi anh da nhan.
                if any(same_pose(o, obs) for _, o, _ in result.accepted):
                    result.records.append({"file": str(path), "sha256": digest,
                                           "frame": chosen_index, "decision": "same_pose"})
                    continue
                rec = {"file": str(path), "sha256": digest, "frame": chosen_index,
                       "time_s": obs.timestamp_ns / 1e9, "quality": obs.quality,
                       "corners": int(len(obs.ids)), "decision": "accepted"}
                result.records.append(rec)
                result.accepted.append((chosen, obs, rec))
    finally:
        cap.release()
    result.frames_read = frame_index + 1
    return result
