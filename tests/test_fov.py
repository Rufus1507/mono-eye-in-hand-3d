from __future__ import annotations

import json
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".deps"))
sys.path.insert(0, str(ROOT))

import cv2
import numpy as np

from fov_tool.acquisition import AutoCapture
from fov_tool.board import load_board
from fov_tool.calibration import analyze
from fov_tool.geometry import distortion_health, field_of_view
from fov_tool.observations import Observation, common_motion, detect
from fov_tool.session import SessionWriter, load_session


def observation(points, ids=None, timestamp_ns=0, quality=100):
    points = np.asarray(points, np.float32).reshape(-1, 1, 2)
    ids = np.arange(len(points), dtype=np.int32) if ids is None else np.asarray(ids, np.int32)
    return Observation(timestamp_ns, ids.reshape(-1, 1), points, quality, quality,
                       quality, 30., 1280, 720)


class GeometryTests(unittest.TestCase):
    def test_zero_distortion_matches_expected(self):
        K = np.array([[850., 0, 639.5], [0, 850., 359.5], [0, 0, 1.]])
        f = field_of_view(K, np.zeros(5), 1280, 720)
        expected = np.degrees(2*np.arctan(1280/(2*850)))
        self.assertAlmostEqual(f["horizontal_deg"], expected, places=10)
        self.assertTrue(distortion_health(K, np.zeros(5), 1280, 720)["valid"])


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.points = np.array([[x, y] for y in (100, 200, 300) for x in (100, 200, 300, 400)])
        self.frame = np.zeros((720, 1280, 3), np.uint8)

    def test_requires_stable_interval_and_pose_change(self):
        machine = AutoCapture(stable_ms=100, max_median_px=1, max_p90_px=2,
                              min_quality=10, buffer_size=10)
        self.assertIsNone(machine.update(self.frame, observation(self.points, timestamp_ns=0)).accept)
        self.assertIsNone(machine.update(self.frame, observation(self.points+.2, timestamp_ns=50_000_000)).accept)
        accepted = machine.update(self.frame, observation(self.points+.3, timestamp_ns=110_000_000)).accept
        self.assertIsNotNone(accepted)
        self.assertIsNone(machine.update(self.frame, observation(self.points+.4, timestamp_ns=150_000_000)).accept)
        moved = self.points + np.array([60, 0])
        machine.update(self.frame, observation(moved, timestamp_ns=200_000_000))
        self.assertEqual(machine.state, "stabilizing")

    def test_rotation_around_center_is_motion(self):
        p = self.points.astype(float); center = p.mean(axis=0)
        angle = np.radians(2); R = np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
        rotated = (p-center)@R.T+center
        motion = common_motion(observation(p), observation(rotated))
        self.assertGreater(motion["p90_px"], 2)

    def test_non_similarity_tilt_counts_as_pose_change(self):
        from fov_tool.observations import pose_change
        p = self.points.astype(np.float32)
        tilted = p.copy(); tilted[:, 0] += (p[:, 1]-p[:,1].mean())*.12
        self.assertTrue(pose_change(observation(p), observation(tilted))["changed"])

    def test_id_change_resets_stability(self):
        machine = AutoCapture(stable_ms=100)
        machine.update(self.frame, observation(self.points, timestamp_ns=0))
        different = observation(self.points[:8], ids=np.arange(20,28), timestamp_ns=80_000_000)
        decision = machine.update(self.frame, different)
        self.assertIn("Giu", decision.status)
        self.assertIsNone(decision.accept)

    def test_directional_blur_lowers_normalized_quality(self):
        _, _, detector = load_board(ROOT / "bang_calib_A4.yaml")
        image = cv2.resize(cv2.imread(str(ROOT / "bang_charuco_A4.png"), 0), (1280, 905))
        sharp = detect(image, detector)
        horizontal = cv2.filter2D(image, -1, np.ones((1, 5), np.float32)/5)
        vertical = cv2.filter2D(image, -1, np.ones((5, 1), np.float32)/5)
        blur_h, blur_v = detect(horizontal, detector), detect(vertical, detector)
        self.assertGreater(sharp.quality, 5.0)
        self.assertLess(blur_h.quality, 5.0)
        self.assertLess(blur_v.quality, 5.0)


class SessionTests(unittest.TestCase):
    def test_roundtrip(self):
        spec, _, _ = load_board(ROOT / "bang_calib_A4.yaml")
        with tempfile.TemporaryDirectory() as td:
            writer = SessionWriter(Path(td), spec, {"width": 1280},
                                   {"width": 1280, "height": 720}, {"name": "test"})
            frame = np.zeros((720,1280,3), np.uint8)
            writer.add(frame, observation([[100,100]]*12, timestamp_ns=1))
            writer.close("captured")
            manifest, rows = load_session(writer.path)
            self.assertEqual(manifest["status"], "captured")
            self.assertEqual(len(rows), 1)
            self.assertTrue((writer.path / rows[0]["image"]).is_file())


class CalibrationTests(unittest.TestCase):
    def test_synthetic_session_recovers_focal_length(self):
        spec, board, _ = load_board(ROOT / "bang_calib_A4.yaml")
        obj = board.getChessboardCorners(); center = obj.mean(axis=0)
        K = np.array([[850.,0,639.5],[0,850.,359.5],[0,0,1.]])
        D = np.array([-.05,.01,.001,-.001,0.])
        rng = np.random.default_rng(7)
        with tempfile.TemporaryDirectory() as td:
            writer = SessionWriter(Path(td), spec, {}, {"width":1280,"height":720}, {"name":"synthetic"})
            for i in range(25):
                rv=rng.uniform([-.45,-.45,-.25],[.45,.45,.25]); R,_=cv2.Rodrigues(rv)
                tv=np.array([rng.uniform(-3,3),rng.uniform(-1.5,1.5),rng.uniform(14,22)])-R@center
                ip,_=cv2.projectPoints(obj,rv,tv,K,D)
                obs=observation(ip.reshape(-1,2)+rng.normal(0,.1,(len(obj),2)), timestamp_ns=i+1)
                writer.add(np.zeros((720,1280,3),np.uint8),obs)
            writer.close("captured")
            report,_=analyze(writer.path,board)
            self.assertLess(abs(report["K"][0][0]-850),5)
            self.assertTrue(report["status"]["solved"])
            self.assertIsNotNone(report["validation"]["held_out"])


class CliFlowTests(unittest.TestCase):
    def test_q_cancels_without_analysis(self):
        import argparse
        import do_fov as cli
        image = cv2.resize(cv2.imread(str(ROOT / "bang_charuco_A4.png")), (1280, 905))
        class Camera:
            def read(self): return True, image.copy()
            def release(self): pass
        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(cli, "open_camera", return_value=(Camera(), image, {"width":1280,"height":905})), \
             mock.patch.object(cli.cv2, "namedWindow"), mock.patch.object(cli.cv2, "imshow"), \
             mock.patch.object(cli.cv2, "destroyAllWindows"), mock.patch.object(cli.cv2, "waitKey", return_value=ord("q")), \
             mock.patch.object(cli, "analyze") as analyze_mock:
            args = argparse.Namespace(board=ROOT/"bang_calib_A4.yaml", camera=0, width=1280,
                height=720, fps=30., backend="auto", sessions=Path(td), name="test",
                stable_ms=400, motion_median=.8, motion_p90=1.5, min_quality=5., buffer=20,
                min_corners=12, target=40, mirror=0, k3=False,
                freeze_focus=0, freeze_exposure=0)
            self.assertEqual(cli.capture(args), 1)
            analyze_mock.assert_not_called()
            manifests = list(Path(td).glob("*/manifest.json"))
            self.assertEqual(len(manifests), 1)
            self.assertEqual(json.loads(manifests[0].read_text(encoding="utf-8"))["status"], "canceled")


if __name__ == "__main__": unittest.main()
