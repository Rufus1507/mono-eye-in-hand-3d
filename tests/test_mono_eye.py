"""Test phần mono_eye (pytest). Test của fov_tool vẫn nằm ở tests/test_fov.py."""
import cv2
import numpy as np
import pytest
import yaml

from fov_tool.board import load_board
from mono_eye.board_scale import BoardNotMeasured, board_scale, board_scale_from_config
from mono_eye.camera_io import load_camera_yaml
from mono_eye.config import ROOT, load_config, resolve

A4_YAML = ROOT / "bang_calib_A4.yaml"


def test_config_points_to_existing_board_and_loads_it():
    cfg = load_config()
    assert cfg["units"] == "mm" and cfg["camera"]["width"] > 0
    spec, board, _ = load_board(resolve(cfg["board"]["file"]))
    assert (spec.squares_x, spec.squares_y) == (11, 7)
    assert board.getChessboardCorners().shape[0] == 60
    assert (ROOT / "do_fov.py").is_file()


def test_board_scale_requires_measurement():
    with pytest.raises(BoardNotMeasured):
        board_scale(A4_YAML, None, None)
    with pytest.raises(BoardNotMeasured):
        board_scale_from_config(load_config())      # mono3d.yaml được giao với measured: null


def test_board_scale_perfect_print_gives_design_square():
    s = board_scale(A4_YAML, 235.63, 149.94)
    assert s.square_mm == pytest.approx(21.421, rel=1e-3)
    assert s.scale_x == pytest.approx(1.0, abs=1e-3)


def test_board_scale_uniform_shrink_is_accepted_and_scales_the_square():
    s = board_scale(A4_YAML, 235.63 * 0.96, 149.94 * 0.96)   # máy in thu nhỏ đều 96 %
    assert s.square_mm == pytest.approx(21.421 * 0.96, rel=1e-3)


def test_board_scale_rejects_anisotropic_print():
    with pytest.raises(ValueError):
        board_scale(A4_YAML, 235.63, 149.94 * 0.96)           # lệch 4 %: phải in lại


def test_board_scale_tolerates_one_millimetre_ruler_error():
    s = board_scale(A4_YAML, 235.63 + 1.0, 149.94 - 1.0)      # thước nhựa đo lệch 1 mm mỗi chiều
    assert s.anisotropy < 0.015


def test_ruler_lengths_entered_as_board_size_are_not_silently_accepted():
    # Nhầm lẫn mà bản đánh giá nêu ra: điền chiều dài thước lề (270 x 180 mm) vào ô "cả bảng"
    # (danh nghĩa 235.63 x 149.94). Hai tỉ lệ lệch nhau ~4.7 % nên phải bị từ chối, không được
    # lặng lẽ cho ra cạnh ô sai.
    with pytest.raises(ValueError):
        board_scale(A4_YAML, 270.0, 180.0)


def test_inconsistent_board_yaml_is_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump({
        "bang": {"o_ngang": 11, "o_doc": 7}, "ban_in": {"canh_o_mm": 21.421},
        "kiem_in": {"ca_bang_ngang_mm": 300.0, "ca_bang_doc_mm": 149.94}}), encoding="utf-8")
    with pytest.raises(ValueError):
        board_scale(bad, 300.0, 149.94)


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


def test_camera_yaml_in_folder_with_vietnamese_name(tmp_path):
    d = tmp_path / "Nghiên Cứu"
    d.mkdir()
    p = d / "camera.yaml"
    _write_camera(p)
    assert load_camera_yaml(p).width == 1280


def test_camera_yaml_rejects_non_positive_size(tmp_path):
    p = tmp_path / "camera.yaml"
    _write_camera(p, w=0, h=720)
    with pytest.raises(ValueError):
        load_camera_yaml(p)
