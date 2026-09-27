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


def board_view(quad, size=(1280, 720)):
    """Anh gia lap: trang bang A4 chieu phoi canh vao tu giac quad (TL, TR, BR, BL)."""
    page = cv2.imread(str(ROOT / "bang_charuco_A4.png"))
    h, w = page.shape[:2]
    H = cv2.getPerspectiveTransform(np.float32([[0, 0], [w, 0], [w, h], [0, h]]), np.float32(quad))
    return cv2.warpPerspective(page, H, size, flags=cv2.INTER_AREA, borderValue=(255, 255, 255))


VIEWS = [[[100, 60], [900, 90], [880, 650], [120, 620]],
         [[350, 40], [1200, 60], [1150, 690], [380, 660]],
         [[60, 120], [700, 40], [760, 700], [40, 560]],
         [[500, 100], [1240, 180], [1180, 560], [560, 690]],
         [[200, 200], [1000, 150], [1050, 700], [150, 650]],
         [[20, 20], [640, 60], [600, 420], [60, 380]],
         [[640, 300], [1260, 330], [1240, 710], [660, 700]]]


class ImportTests(unittest.TestCase):
    """Moi cong loai anh co mot ca da biet la hong; da kiem: tat cong thi test do."""

    def setUp(self):
        from fov_tool import importing
        self.importing = importing
        _, _, self.detector = load_board(ROOT / "bang_calib_A4.yaml")
        self.td = tempfile.TemporaryDirectory(); self.dir = Path(self.td.name)

    def tearDown(self):
        self.td.cleanup()

    def write(self, name, image, exif=None):
        path = self.dir / name
        if exif is None:
            cv2.imwrite(str(path), image)
        else:
            from PIL import Image
            Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).save(path, exif=exif, quality=95)
        return path

    def decisions(self, paths):
        result = self.importing.import_images(paths, self.detector)
        return {Path(r["file"]).name: r["decision"] for r in result.records}, result

    def test_clean_views_all_accepted(self):
        paths = [self.write(f"v{i}.png", board_view(q)) for i, q in enumerate(VIEWS)]
        got, result = self.decisions(paths)
        self.assertEqual(set(got.values()), {"accepted"}, got)
        self.assertEqual(result.size, (1280, 720))

    def test_minority_size_rejected(self):
        paths = [self.write(f"v{i}.png", board_view(q)) for i, q in enumerate(VIEWS[:4])]
        paths.append(self.write("small.png", board_view(VIEWS[4], (960, 540))))
        got, result = self.decisions(paths)
        self.assertEqual(got["small.png"], "size_mismatch")
        self.assertEqual(result.size, (1280, 720))

    def test_blurred_photo_rejected(self):
        blurred = cv2.filter2D(board_view(VIEWS[1]), -1, np.ones((1, 7), np.float32) / 7)
        paths = [self.write("v0.png", board_view(VIEWS[0])), self.write("blur.png", blurred)]
        got, _ = self.decisions(paths)
        self.assertEqual(got["blur.png"], "blurry")

    def test_high_resolution_sharp_photo_not_called_blurry(self):
        # CUNG noi dung anh 1920 px, chi nhieu diem anh hon x3 (nhu anh dien thoai):
        # diem net phai giu nguyen. Khong chuan hoa thi anh net bi goi la mo.
        view = lambda q: board_view(np.asarray(q) * 1.5, (1920, 1080))
        up = lambda img: cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        blurred = cv2.filter2D(view(VIEWS[1]), -1, np.ones((1, 9), np.float32) / 9)
        paths = [self.write("sharp_hi.png", up(view(VIEWS[0]))), self.write("blur_hi.png", up(blurred))]
        got, result = self.decisions(paths)
        self.assertEqual(result.size, (5760, 3240))
        self.assertEqual(got, {"sharp_hi.png": "accepted", "blur_hi.png": "blurry"})

    def test_repeated_pose_rejected_even_if_not_consecutive(self):
        paths = [self.write("a.png", board_view(VIEWS[0])), self.write("b.png", board_view(VIEWS[1])),
                 self.write("c.png", board_view(VIEWS[0]))]
        got, _ = self.decisions(paths)
        self.assertEqual(got["c.png"], "same_pose")

    def test_views_without_common_corners_are_different_poses(self):
        # Loi da gap tren phien that: pose_change tra changed=False khi thieu goc chung.
        grid = np.array([[x, y] for y in range(3) for x in range(5)], np.float32) * 40 + 100
        a = observation(grid, ids=np.arange(15))
        b = observation(grid, ids=np.arange(40, 55))
        self.assertFalse(self.importing.same_pose(a, b))
        self.assertTrue(self.importing.same_pose(a, observation(grid + .5, ids=np.arange(15))))

    def test_different_lens_or_zoom_rejected(self):
        from PIL import Image
        def exif(focal):
            e = Image.Exif(); e[0x010F] = "Phone"; e[0x0110] = "X1"
            e.get_ifd(0x8769)[0x920A] = focal
            return e
        paths = [self.write(f"w{i}.jpg", board_view(q), exif(4.2)) for i, q in enumerate(VIEWS[:3])]
        paths.append(self.write("tele.jpg", board_view(VIEWS[3]), exif(9.0)))
        got, _ = self.decisions(paths)
        self.assertEqual(got["tele.jpg"], "different_camera_or_zoom")
        self.assertEqual([got[f"w{i}.jpg"] for i in range(3)], ["accepted"] * 3)

    def test_exif_rotation_ignored(self):
        from PIL import Image
        e = Image.Exif(); e[0x0112] = 6   # "xoay 90 do khi hien thi"
        path = self.write("rot.jpg", board_view(VIEWS[0]), e)
        self.assertEqual(self.importing.read_gray(path).shape, (720, 1280))
        self.assertEqual(self.importing.probe_image(path)["size"], (1280, 720))

    def test_video_held_poses_become_frames(self):
        path = self.dir / "clip.avi"
        out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 30, (1280, 720))
        self.assertTrue(out.isOpened())
        for q in VIEWS[:3]:
            frame = board_view(q)
            for _ in range(20):   # giu 0.67 s > 400 ms
                out.write(frame)
        out.release()
        result = self.importing.import_video(path, self.detector)
        self.assertEqual(result.size, (1280, 720))
        self.assertEqual(len(result.accepted), 3)


SYN_K = np.array([[850., 0, 639.5], [0, 850., 359.5], [0, 0, 1.]])
SYN_D = np.array([-.25, .08, .001, -.001, 0.])   # meo ro de cham sang dich xa


def synthetic_session(root, n=25):
    spec, board, _ = load_board(ROOT / "bang_calib_A4.yaml")
    obj = board.getChessboardCorners(); center = obj.mean(axis=0)
    rng = np.random.default_rng(7)
    writer = SessionWriter(Path(root), spec, {}, {"width": 1280, "height": 720}, {"name": "synthetic"})
    for i in range(n):
        rv = rng.uniform([-.45, -.45, -.25], [.45, .45, .25]); R, _ = cv2.Rodrigues(rv)
        tv = np.array([rng.uniform(-4, 4), rng.uniform(-2, 2), rng.uniform(12, 20)]) - R @ center
        ip, _ = cv2.projectPoints(obj, rv, tv, SYN_K, SYN_D)
        writer.add(np.zeros((720, 1280, 3), np.uint8),
                   observation(ip.reshape(-1, 2) + rng.normal(0, .1, (len(obj), 2)), timestamp_ns=i + 1))
    writer.close("captured")
    return writer.path, board


class ExportTests(unittest.TestCase):
    def test_pinhole_fov_matches_closed_form(self):
        from fov_tool.export import pinhole_fov
        f = pinhole_fov(SYN_K, 1280, 720)
        self.assertAlmostEqual(f["horizontal_deg"], np.degrees(2 * np.arctan(640 / 850)), places=9)
        self.assertAlmostEqual(f["vertical_deg"], np.degrees(2 * np.arctan(360 / 850)), places=9)
        self.assertAlmostEqual(f["diagonal_deg"], np.degrees(2 * np.arctan(np.hypot(640, 360) / 850)), places=9)

    def test_exported_yaml_undistorts_a_known_point(self):
        # Cham sang dat o vi tri BI MEO cua mot tia; sau khi khu meo bang camera.yaml da xuat,
        # no phai nam o vi tri KHONG MEO cua cung tia do. Sai K, D, thu tu D hay chieu remap deu lam lech.
        sys.path.insert(0, str(ROOT / "examples"))
        import undistort
        from fov_tool.export import export, read_opencv_yaml
        with tempfile.TemporaryDirectory() as td:
            session, board = synthetic_session(td)
            report, _ = analyze(session, board, bootstrap=0)
            out = export(session, camera_name="syn")
            K, D, size = read_opencv_yaml(out / "camera.yaml")
            np.testing.assert_allclose(K, report["K"], rtol=0, atol=1e-9)
            np.testing.assert_allclose(D, report["D"], rtol=0, atol=1e-12)
            self.assertEqual(size, (1280, 720))
            ray = np.array([[[.62, .36, 1.]]])
            p_d = cv2.projectPoints(ray, np.zeros(3), np.zeros(3), SYN_K, SYN_D)[0].reshape(2)
            p_u = cv2.projectPoints(ray, np.zeros(3), np.zeros(3), SYN_K, np.zeros(5))[0].reshape(2)
            self.assertGreater(np.linalg.norm(p_d - p_u), 20)   # phep thu co y nghia: hai vi tri xa nhau
            img = np.zeros((720, 1280), np.float32)
            cv2.circle(img, tuple(int(round(v)) for v in p_d), 3, 255, -1)
            m1, m2, _ = undistort.build_maps(*undistort.load_camera(out / "camera.yaml"), keep_k=True)
            got = cv2.minMaxLoc(cv2.GaussianBlur(cv2.remap(img, m1, m2, cv2.INTER_LINEAR), (0, 0), 2))[3]
            self.assertLess(np.linalg.norm(np.array(got) - p_u), 2.0, (got, p_u, p_d))

    def test_report_warns_on_empty_corner_and_hides_paths(self):
        from fov_tool.export import report_html
        with tempfile.TemporaryDirectory() as td:
            session, board = synthetic_session(td)
            result, _ = analyze(session, board, bootstrap=0)
        manifest = {"import": {"records": [
            {"file": r"C:\Users\someone\secret_folder\IMG_0001.jpg", "decision": "accepted", "corners": 60, "quality": 7.0},
            {"file": r"C:\Users\someone\secret_folder\IMG_0002.jpg", "decision": "blurry", "corners": 60, "quality": 3.1}]}}
        full = [[3] * 8 for _ in range(5)]
        result["coverage"] = {**result["coverage"], "independent_views_per_cell": full}
        page = report_html(result, manifest, "cam")
        self.assertIn("IMG_0002.jpg", page); self.assertIn("too blurry", page)
        self.assertNotIn("secret_folder", page); self.assertNotIn("someone", page)
        self.assertNotIn("corner of the image", page)
        self.assertNotIn("usually below 1 px", page)   # du lieu gia lap: RMS ~0.14 px
        full[4][0] = 0
        self.assertIn("bottom-left corner of the image", report_html(result, manifest, "cam"))
        self.assertIn("usually below 1 px", report_html({**result, "rms_px": 2.8}, manifest, "cam"))


if __name__ == "__main__": unittest.main()
