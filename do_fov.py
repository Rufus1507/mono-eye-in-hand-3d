#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

import cv2

from fov_tool.acquisition import AutoCapture
from fov_tool.board import load_board
from fov_tool.calibration import analyze
from fov_tool.camera import freeze_controls, open_camera
from fov_tool.observations import detect
from fov_tool.session import SessionWriter
from fov_tool.ui import draw

ROOT = Path(__file__).resolve().parent

# Windows Python can inherit a legacy console encoding that cannot print
# Vietnamese help/status text.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


def capture(args):
    spec, board, detector = load_board(args.board)
    requested = {"index": args.camera, "width": args.width, "height": args.height,
                 "fps": args.fps, "backend": args.backend}
    cap, frame, actual = open_camera(args.camera, args.width, args.height, args.fps, args.backend)
    writer = SessionWriter(args.sessions, spec, requested, actual, {"name": args.name, "index": args.camera})
    machine = AutoCapture(args.stable_ms, args.motion_median, args.motion_p90,
                          args.min_quality, args.buffer)
    controls_done = not (args.freeze_focus or args.freeze_exposure)
    settle_until_ns = 0
    finished = False
    print(f"Phiên: {writer.path}")
    print("Đổi tư thế, giữ yên ngắn; chương trình chọn frame tốt nhất.")
    cv2.namedWindow("do_fov", cv2.WINDOW_AUTOSIZE)
    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                writer.close("failed", "camera_read_failed")
                print("Mất camera; phiên được giữ lại với trạng thái failed.")
                return 2
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            obs = detect(gray, detector, args.min_corners)
            if obs is not None and not controls_done:
                controls = freeze_controls(cap, bool(args.freeze_focus), bool(args.freeze_exposure))
                writer.update_actual_camera({"freeze_attempt": controls})
                controls_done = True
                settle_until_ns = time.monotonic_ns() + 1_000_000_000
                machine = AutoCapture(args.stable_ms, args.motion_median, args.motion_p90,
                                      args.min_quality, args.buffer)
            if time.monotonic_ns() < settle_until_ns:
                decision = type("Decision", (), {"status":"Cho camera on dinh sau khi khoa focus/exposure", "accept":None})()
            else:
                decision = machine.update(frame, obs)
            status = decision.status
            auto_saved = decision.accept is not None
            if decision.accept:
                chosen_frame, chosen_obs = decision.accept
                writer.add(chosen_frame, chosen_obs)
                status = "Da luu; hay doi tu the"
                print(f"  lưu ảnh {writer.manifest['accepted_frames']:02d}: quality={chosen_obs.quality:.1f}, góc={len(chosen_obs.ids)}")
            # KHONG loc ascii o day nua: loc im lang bien "Giu bang yen" thanh
            # "Gi bng yn" ma khong ai biet. Moi chuoi status phai viet tieng
            # Viet KHONG DAU tu goc (cv2.putText font Hershey chi ve ASCII).
            view = draw(frame, obs, status,
                        writer.manifest["accepted_frames"], args.target, bool(args.mirror))
            cv2.imshow("do_fov", view)
            key = cv2.waitKey(1) & 0xff
            if key in (ord("q"), 27):
                writer.close("canceled", "user_cancel")
                print("Đã hủy. Không hiệu chuẩn; dữ liệu phiên vẫn được giữ.")
                return 1
            if key == ord(" ") and obs is not None and not auto_saved:
                writer.add(frame, obs, forced=True)
                machine.accepted = obs; machine.state = "wait_change"
                print("  lưu ảnh FORCE; báo cáo sẽ giữ cờ forced")
            if key in (13, ord("c")):
                finished = True; break
            if writer.manifest["accepted_frames"] >= args.target:
                finished = True; break
    except KeyboardInterrupt:
        writer.close("canceled", "keyboard_interrupt")
        print("Đã hủy bằng Ctrl+C. Không hiệu chuẩn.")
        return 1
    except Exception as exc:
        writer.close("failed", type(exc).__name__)
        raise
    finally:
        cap.release(); cv2.destroyAllWindows()
    if not finished:
        writer.close("canceled", "not_finished")
        return 1
    writer.close("captured")
    if writer.manifest["accepted_frames"] < 6:
        print("Phiên có dưới 6 ảnh; đã lưu nhưng chưa đủ để tính.")
        return 2
    report, run_dir = analyze(writer.path, board, args.k3, bootstrap=args.bootstrap)
    print_report(report, run_dir)
    return 0 if report["status"]["solved"] and report["status"]["observations_sufficient"] else 2


def analyze_cmd(args):
    board_path = args.session.resolve() / "board.yaml"
    _, board, detector = load_board(board_path)
    override = None
    source = "stored"
    if args.redetect:
        from fov_tool.session import load_session
        _, rows = load_session(args.session)
        override = []
        for row in rows:
            image = cv2.imread(str(args.session.resolve() / row["image"]), cv2.IMREAD_GRAYSCALE)
            if image is None:
                raise OSError(f"Không đọc được {row['image']}")
            obs = detect(image, detector, args.min_corners, row["timestamp_ns"])
            if obs is not None:
                override.append(obs.as_json() | {"index":row["index"], "image":row["image"],
                                                  "forced":row.get("forced", False)})
        source = f"redetected_opencv_{cv2.__version__}"
    if args.compare_models:
        reports = []
        for k3 in (False, True):
            report, run_dir = analyze(args.session, board, k3, override, source,
                                      args.fix_principal, args.bootstrap)
            print_report(report, run_dir); reports.append(report)
        a, b = (x["validation"].get("held_out") for x in reports)
        if a and b and a["rms_px"] is not None and b["rms_px"] is not None:
            print(f"  so mô hình trên cùng tập giữ riêng: k3 khóa {a['rms_px']:.4f} px | k3 tự do {b['rms_px']:.4f} px")
        return 0 if all(r["status"]["solved"] for r in reports) else 2
    report, run_dir = analyze(args.session, board, args.k3, override, source,
                              args.fix_principal, args.bootstrap)
    print_report(report, run_dir)
    return 0 if report["status"]["solved"] and report["status"]["observations_sufficient"] else 2


def print_report(report, run_dir):
    f = report["fov_raw"]; s = report["status"]; val = report["validation"].get("held_out")
    st = report.get("stability")

    def pm(khoa):
        """Sai so THAT (bootstrap). Rong hon sd cua mot lan fit khoang 10 lan."""
        return "" if not st or khoa not in st else f" +/- {st[khoa]['sd']:.3f}"

    print("\nKẾT QUẢ V2")
    print(f"  FOV ngang {f['horizontal_deg']:.3f}{pm('fov_horizontal_deg')}° | "
          f"dọc {f['vertical_deg']:.3f}{pm('fov_vertical_deg')}°")
    print(f"  FOV chéo {f['diagonal_tl_br_deg']:.3f}{pm('fov_diagonal_deg')}° / "
          f"{f['diagonal_tr_bl_deg']:.3f}°")
    if st:
        print(f"    (+/- la do tan do bang bootstrap {st['runs_ok']}/{st['runs_requested']} lan "
              f"tren chinh bo anh nay — do CHUM trong mot phien,")
        print(f"     KHONG gom sai so he thong. Muon biet do DUNG phai co moc doc lap.)")
    else:
        print("    (chua do duoc do tan: bootstrap tat hoac qua it anh — "
              "sai so THUC TE rong hon std_intrinsics nhieu)")
    print(f"  RMS fit {report['rms_px']:.3f} px")
    if val and val.get("rms_px") is not None:
        print(f"  RMS tập giữ riêng {val['rms_px']:.3f} px ({val['views_ok']} ảnh)")
    elif val:
        print("  Tập giữ riêng không giải được pose hợp lệ")
    K = report["K"]
    print(f"  cx {K[0][2]:.1f} | cy {K[1][2]:.1f}"
          + ("   [GHIM o tam anh — gia dinh, khong phai phep do]"
             if report.get("principal_point_fixed_at_image_center") else ""))
    print(f"  trạng thái: observations={s['observations_sufficient']} solved={s['solved']} "
          f"internal_check={s['internal_validation_completed']} validated={s['validated']} accepted={s['accepted']}")
    print(f"  báo cáo: {run_dir / 'result.json'}")


def compare(args):
    rows = []
    for path in args.results:
        data = json.loads(path.read_text(encoding="utf-8")); f = data["fov_raw"]
        rows.append((path, f["horizontal_deg"], f["vertical_deg"], f["diagonal_tl_br_deg"]))
    print("result\tFOV-H\tFOV-V\tFOV-D")
    for p, h, v, d in rows: print(f"{p}\t{h:.4f}\t{v:.4f}\t{d:.4f}")
    if len(rows) > 1:
        for label, pos in (("ngang",1),("dọc",2),("chéo",3)):
            values=[r[pos] for r in rows]
            print(f"độ tản {label}: {max(values)-min(values):.4f}°")
    return 0


def parser():
    p = argparse.ArgumentParser(description="Đo FOV ChArUco có lưu phiên và chạy lại offline")
    sub = p.add_subparsers(dest="command", required=True)
    c = sub.add_parser("capture", help="tự chụp một phiên và phân tích")
    c.add_argument("--camera", type=int, default=0); c.add_argument("--name", default="camera")
    c.add_argument("--width", type=int, default=1920); c.add_argument("--height", type=int, default=1080)
    c.add_argument("--fps", type=float, default=30); c.add_argument("--backend", choices=("auto","msmf","dshow","any"), default="auto")
    c.add_argument("--board", type=Path, default=ROOT/"bang_calib_A4.yaml")
    c.add_argument("--sessions", type=Path, default=ROOT/"sessions")
    c.add_argument("--target", type=int, default=40); c.add_argument("--min-corners", type=int, default=12)
    c.add_argument("--stable-ms", type=int, default=400); c.add_argument("--motion-median", type=float, default=.8)
    c.add_argument("--motion-p90", type=float, default=1.5); c.add_argument("--min-quality", type=float, default=5.)
    c.add_argument("--buffer", type=int, default=20); c.add_argument("--mirror", type=int, default=1)
    c.add_argument("--freeze-focus", type=int, default=1,
                   help="thử khóa autofocus tại giá trị sau khi thấy bảng; manifest ghi rõ readback")
    c.add_argument("--freeze-exposure", type=int, default=0,
                   help="thử khóa exposure; mặc định tắt vì backend webcam khác nhau")
    c.add_argument("--k3", action="store_true")
    c.add_argument("--bootstrap", type=int, default=10,
                   help="số lần bootstrap để đo SAI SỐ THẬT của phép đo "
                        "(0 = tắt; khi tắt thì báo cáo không có độ tản)")
    c.set_defaults(func=capture)
    a = sub.add_parser("analyze", help="phân tích lại một phiên đã lưu")
    a.add_argument("session", type=Path); a.add_argument("--k3", action="store_true")
    a.add_argument("--redetect", action="store_true", help="nhận diện lại từ PNG thay vì dùng tọa độ đã lưu")
    a.add_argument("--compare-models", action="store_true", help="chạy riêng k3 khóa và k3 tự do trên cùng split")
    a.add_argument("--fix-principal", action="store_true",
                   help="ghim tâm quang ở tâm ảnh thay vì để nó tự do. Đây là "
                        "GIẢ ĐỊNH chẩn đoán, không phải phép đo: dùng để xem "
                        "cx,cy có phải biến đang trôi giữa các phiên không")
    a.add_argument("--bootstrap", type=int, default=10,
                   help="số lần bootstrap để đo SAI SỐ THẬT của phép đo (0 = tắt)")
    a.add_argument("--min-corners", type=int, default=12); a.set_defaults(func=analyze_cmd)
    q = sub.add_parser("compare", help="so nhiều result.json cùng định nghĩa")
    q.add_argument("results", type=Path, nargs="+"); q.set_defaults(func=compare)
    return p


if __name__ == "__main__":
    args = parser().parse_args()
    raise SystemExit(args.func(args))
