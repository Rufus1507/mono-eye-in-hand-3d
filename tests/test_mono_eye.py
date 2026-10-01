"""Test phần mono_eye (pytest). Test của fov_tool vẫn nằm ở tests/test_fov.py."""
from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

from fov_tool.board import load_board
from mono_eye.board_scale import BoardNotMeasured, board_scale
from mono_eye.camera_io import load_camera_yaml
from mono_eye.config import ROOT, load_config, resolve


def _board_yaml(tmp_path, **kiem_in):
    base = {"ban_in": {"canh_o_mm": 21.421},
            "kiem_in": {"thuoc_ngang_mm": 270.0, "thuoc_doc_mm": 180.0,
                        "do_duoc_ngang_mm": None, "do_duoc_doc_mm": None}}
    base["kiem_in"].update(kiem_in)
    p = tmp_path / "bang.yaml"
    p.write_text(yaml.safe_dump(base), encoding="utf-8")
    return p


def test_config_points_to_existing_board_and_loads_it():
    cfg = load_config()
    assert cfg["units"] == "mm" and cfg["camera"]["width"] > 0
    spec, board, _ = load_board(resolve(cfg["board"]["file"]))
    assert (spec.squares_x, spec.squares_y) == (11, 7)
    assert board.getChessboardCorners().shape[0] == 60
    assert (ROOT / "do_fov.py").is_file()


def test_board_scale_requires_measurement(tmp_path):
    with pytest.raises(BoardNotMeasured):
        board_scale(_board_yaml(tmp_path))


def test_board_scale_uses_measured_rulers(tmp_path):
    s = board_scale(_board_yaml(tmp_path, do_duoc_ngang_mm=270.0, do_duoc_doc_mm=180.0))
    assert s.square_mm == pytest.approx(21.421)
    s = board_scale(_board_yaml(tmp_path, do_duoc_ngang_mm=259.2, do_duoc_doc_mm=172.8))  # in thu nho 96 %
    assert s.square_mm == pytest.approx(21.421 * 0.96)


def test_board_scale_rejects_anisotropic_print(tmp_path):
    with pytest.raises(ValueError):
        board_scale(_board_yaml(tmp_path, do_duoc_ngang_mm=270.0, do_duoc_doc_mm=172.8))


def _write_camera(path, w=1280, h=720):
    fs = cv2.FileStorage(str(path), cv2.FILE_STORAGE_WRITE)
    fs.write("camera_matrix", np.array([[900.0, 0, 640], [0, 900.0, 360], [0, 0, 1]]))
    fs.write("distortion_coefficients", np.array([[0.1, -0.05, 0.0, 0.0, 0.0]]))
    fs.write("image_width", w)
    fs.write("image_height", h)
    fs.release()


def test_camera_yaml_roundtrip_and_resolution_check(tmp_path):
    p = tmp_path / "camera.yaml"
    _write_camera(p)
    cam = load_camera_yaml(p)
    assert cam.K.shape == (3, 3) and cam.dist.shape == (5,)
    cam.check_frame(np.zeros((720, 1280, 3), np.uint8))
    with pytest.raises(ValueError):
        cam.check_frame(np.zeros((1080, 1920, 3), np.uint8))
    with pytest.raises(FileNotFoundError):
        load_camera_yaml(tmp_path / "nope.yaml")
