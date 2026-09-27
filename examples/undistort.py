#!/usr/bin/env python3
"""Remove lens distortion from images or a video using camera.yaml from `do_fov.py export`.

Needs only opencv-python and numpy.

    python undistort.py camera.yaml photo.jpg                 # -> photo_undistorted.jpg
    python undistort.py camera.yaml photos/ --out straight/   # every image in a folder
    python undistort.py camera.yaml clip.mp4                  # -> clip_undistorted.mp4
    python undistort.py camera.yaml photo.jpg --alpha 1       # keep every source pixel (black borders)

--alpha 0 (default) crops to the area where every output pixel has a source pixel;
--alpha 1 keeps the whole source image. --keep-k keeps the original camera matrix,
so pixel coordinates stay comparable with the calibration.
The calibration is only valid at the resolution it was made for.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".webm"}


def load_camera(path):
    fs = cv2.FileStorage(str(path), cv2.FILE_STORAGE_READ)
    if not fs.isOpened():
        raise FileNotFoundError(path)
    K = fs.getNode("camera_matrix").mat()
    D = fs.getNode("distortion_coefficients").mat().reshape(-1)
    size = (int(fs.getNode("image_width").real()), int(fs.getNode("image_height").real()))
    fs.release()
    return K, D, size


def build_maps(K, D, size, alpha=0.0, keep_k=False):
    new_K = K.copy() if keep_k else cv2.getOptimalNewCameraMatrix(K, D, size, alpha, size)[0]
    map1, map2 = cv2.initUndistortRectifyMap(K, D, None, new_K, size, cv2.CV_32FC1)
    return map1, map2, new_K


def check_size(image, size, name):
    got = (image.shape[1], image.shape[0])
    if got != size:
        raise SystemExit(f"{name}: {got[0]}x{got[1]}, but the calibration is for {size[0]}x{size[1]}. "
                         "Use images at the calibrated resolution.")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("camera", type=Path); p.add_argument("input", type=Path)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--alpha", type=float, default=0.0)
    p.add_argument("--keep-k", action="store_true")
    a = p.parse_args(argv)
    K, D, size = load_camera(a.camera)
    map1, map2, new_K = build_maps(K, D, size, a.alpha, a.keep_k)
    remap = lambda img: cv2.remap(img, map1, map2, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)

    if a.input.suffix.lower() in VIDEO_EXT:
        cap = cv2.VideoCapture(str(a.input))
        out = a.out or a.input.with_name(a.input.stem + "_undistorted.mp4")
        writer = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), cap.get(cv2.CAP_PROP_FPS) or 30, size)
        n = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            check_size(frame, size, a.input.name)
            writer.write(remap(frame)); n += 1
        cap.release(); writer.release()
        print(f"{n} frames -> {out}")
    else:
        files = sorted(f for f in a.input.iterdir() if f.suffix.lower() in IMAGE_EXT) if a.input.is_dir() else [a.input]
        out_dir = a.out if a.input.is_dir() else None
        if out_dir:
            out_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            img = cv2.imdecode(np.fromfile(str(f), np.uint8), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
            check_size(img, size, f.name)
            target = (out_dir / f.name) if out_dir else (a.out or f.with_name(f.stem + "_undistorted" + f.suffix))
            ok, buf = cv2.imencode(target.suffix, remap(img))
            buf.tofile(str(target))
            print(f"{f.name} -> {target}")
    print("new camera matrix:\n", np.array2string(new_K, precision=3))


if __name__ == "__main__":
    main()
