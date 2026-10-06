from __future__ import annotations

import json
import random
import statistics
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from .geometry import distortion_health, field_of_view, pinhole_reference
from .session import create_run_dir, load_session, source_fingerprint


def _arrays(rows, board):
    object_points, image_points, kept = [], [], []
    for row in rows:
        ids = np.asarray(row["ids"], np.int32).reshape(-1, 1)
        corners = np.asarray(row["corners"], np.float32).reshape(-1, 1, 2)
        op, ip = board.matchImagePoints(corners, ids)
        if op is not None and len(op) >= 8:
            object_points.append(op.astype(np.float32)); image_points.append(ip.astype(np.float32)); kept.append(row)
    return object_points, image_points, kept


def fit(rows, board, size, k3=False, fix_principal=False):
    op, ip, kept = _arrays(rows, board)
    if len(op) < 6:
        raise ValueError(f"Chỉ có {len(op)} ảnh hợp lệ; cần ít nhất 6")
    flags = 0 if k3 else cv2.CALIB_FIX_K3
    # fix_principal: ghim tam quang o TAM ANH thay vi de no tu troi. Khong kem
    # CALIB_USE_INTRINSIC_GUESS thi OpenCV giu cx,cy = ((w-1)/2, (h-1)/2).
    # Day la GIA DINH, khong phai phep do - dung de chan doan xem cx,cy co
    # phai la bien dang troi khong; ket qua phai doc kem co nay.
    if fix_principal:
        flags |= cv2.CALIB_FIX_PRINCIPAL_POINT
    rms, K, D, rvecs, tvecs, sd, _, per_view = cv2.calibrateCameraExtended(
        op, ip, tuple(size), None, None, flags=flags)
    if not np.isfinite(K).all() or not np.isfinite(D).all():
        raise ValueError("Nghiệm hiệu chuẩn chứa giá trị không hữu hạn")
    residuals = []
    for row, obj, img, rv, tv in zip(kept, op, ip, rvecs, tvecs):
        projected, _ = cv2.projectPoints(obj, rv, tv, K, D)
        e = (projected - img).reshape(-1, 2)
        residuals.append({"index": row["index"], "rms_px": float(np.sqrt(np.mean(np.sum(e*e, axis=1)))),
                          "points_px": img.reshape(-1, 2).tolist(), "vectors_px": e.tolist()})
    return {"K": K, "D": D.reshape(-1), "rms": float(rms), "sd": sd.reshape(-1),
            "per_view": per_view.reshape(-1), "rows": kept, "residuals": residuals}


def held_out_error(rows, board, K, D):
    op, ip, kept = _arrays(rows, board)
    squared, count, failed = 0.0, 0, 0
    per_view = []
    for row, obj, img in zip(kept, op, ip):
        ok, rv, tv = cv2.solvePnP(obj, img, K, D, flags=cv2.SOLVEPNP_ITERATIVE)
        if not ok:
            failed += 1; continue
        projected, _ = cv2.projectPoints(obj, rv, tv, K, D)
        e = (projected - img).reshape(-1, 2)
        se = float(np.sum(e*e)); squared += se; count += len(e)
        per_view.append({"index": row["index"], "rms_px": float(np.sqrt(se/len(e)))})
    return {"rms_px": None if count == 0 else float(np.sqrt(squared/count)),
            "points": count, "views_ok": len(per_view), "views_failed": failed,
            "per_view": per_view}


def stability(rows, board, size, k3=False, fix_principal=False, n_lan=10,
              seed=20260914):
    """Do sai so THAT cua phep do bang bootstrap theo anh.

    Vi sao can: sd tu calibrateCameraExtended la sai so TRONG MOT lan fit, voi
    gia dinh cac diem doc lap. Do 14-09 tren hai phien webcam cho thay no bao
    ~0.1 deg trong khi doi tap anh lam FOV nhay toi 3.2 deg - tuc lac quan hon
    thuc te khoang 10 lan. Bootstrap lay lai n anh CO HOAN LAI tu chinh n anh
    roi fit lai; do tan cua cac nghiem la uoc luong truc tiep cua do CHUM.

    GIOI HAN, phai doc kem: day la do tan TRONG MOT PHIEN. No KHONG bao gom
    sai so he thong (bang in lech, camera doi trang thai giua cac phien), va
    neu nhieu anh gan trung tu the thi no se danh gia THAP sai so. Muon biet
    do DUNG thi phai co moc doc lap, khong phep tu kiem nao thay duoc.
    """
    if n_lan < 2 or len(rows) < 12:
        return None
    rng = random.Random(seed)
    mau = []
    for _ in range(n_lan):
        lay = [rows[rng.randrange(len(rows))] for _ in range(len(rows))]
        try:
            r = fit(lay, board, size, k3, fix_principal)
        except (ValueError, cv2.error):
            continue
        f = field_of_view(r["K"], r["D"], *size)
        mau.append((f["horizontal_deg"], f["vertical_deg"],
                    f["diagonal_tl_br_deg"], r["K"][0, 0], r["K"][1, 1]))
    if len(mau) < 3:
        return None
    ten = ("fov_horizontal_deg", "fov_vertical_deg", "fov_diagonal_deg",
           "fx_px", "fy_px")
    out = {"method": "bootstrap theo anh, lay co hoan lai",
           "runs_ok": len(mau), "runs_requested": n_lan,
           "note": "do tan TRONG phien; khong gom sai so he thong"}
    for k, t in enumerate(ten):
        v = [m[k] for m in mau]
        out[t] = {"sd": float(statistics.stdev(v)),
                  "min": float(min(v)), "max": float(max(v))}
    return out


def coverage(rows, size, cols=8, rows_n=5):
    w, h = size; seen = [[set() for _ in range(cols)] for _ in range(rows_n)]
    for row in rows:
        for x, y in row["corners"]:
            c = min(cols-1, max(0, int(x/w*cols))); r = min(rows_n-1, max(0, int(y/h*rows_n)))
            seen[r][c].add(row["index"])
    counts = [[len(v) for v in line] for line in seen]
    return {"independent_views_per_cell": counts,
            "empty_cells": sum(v == 0 for line in counts for v in line),
            "cells_with_2plus": sum(v >= 2 for line in counts for v in line),
            "cells_total": cols*rows_n}


def residual_structure(residuals, size, cols=5, rows_n=3):
    w, h = size
    cells = [[[] for _ in range(cols)] for _ in range(rows_n)]
    for view in residuals:
        for (x, y), vector in zip(view["points_px"], view["vectors_px"]):
            c = min(cols-1, max(0, int(x/w*cols))); r = min(rows_n-1, max(0, int(y/h*rows_n)))
            cells[r][c].append(vector)
    result = []
    for r in range(rows_n):
        line = []
        for c in range(cols):
            a = np.asarray(cells[r][c], np.float64)
            line.append({"count": len(a),
                         "mean_vector_px": None if not len(a) else a.mean(axis=0).tolist(),
                         "rms_px": None if not len(a) else float(np.sqrt(np.mean(np.sum(a*a, axis=1))))})
        result.append(line)
    return {"grid": [cols, rows_n], "cells": result}


def analyze(session_path: Path, board, k3=False, override_rows=None,
            detection_source="stored", fix_principal=False, bootstrap=10):
    manifest, stored_rows = load_session(session_path)
    rows = stored_rows if override_rows is None else override_rows
    forced_count = sum(bool(row.get("forced")) for row in rows)
    auto_rows = [row for row in rows if not row.get("forced")]
    if len(auto_rows) >= 6:
        rows = auto_rows
        excluded_forced = forced_count
    else:
        valid_rows = [row for row in rows if len(row.get("ids", [])) >= 6]
        if len(valid_rows) >= 6:
            rows = valid_rows
            excluded_forced = 0
        else:
            raise ValueError("Phiên chỉ có ảnh FORCE; không có ảnh tự động đạt cổng chất lượng")
    size = tuple(manifest["actual_camera"][k] for k in ("width", "height"))
    test = [row for i, row in enumerate(rows) if i % 5 == 0]
    train = [row for i, row in enumerate(rows) if i % 5 != 0]
    train_fit = (fit(train, board, size, k3, fix_principal)
                 if len(train) >= 6 and len(test) >= 2 else None)
    validation = ({"held_out": held_out_error(test, board, train_fit["K"], train_fit["D"]),
                   "train_views": len(train_fit["rows"]), "test_views": len(test)}
                  if train_fit else {"held_out": None, "reason": "Không đủ ảnh để tách tập kiểm"})
    final = fit(rows, board, size, k3, fix_principal)
    K, D = final["K"], final["D"]
    health = distortion_health(K, D, *size)
    observation_ok = len(final["rows"]) >= 20 and coverage(final["rows"], size)["cells_with_2plus"] >= 28
    solved = bool(np.isfinite(final["rms"]) and health["valid"])
    report = {"schema_version": 1, "created_local": datetime.now().astimezone().isoformat(),
              "session_id": manifest["session_id"], "source_sha256": source_fingerprint(),
              "capture_source_sha256": manifest.get("source_sha256"), "detection_source": detection_source,
              "model": ("pinhole_k1_k2_p1_p2" + ("_k3" if k3 else "_fixed_k3")
                        + ("_fixed_pp" if fix_principal else "")),
              "principal_point_fixed_at_image_center": bool(fix_principal),
              "status": {"observations_sufficient": observation_ok, "solved": solved,
                         "internal_validation_completed": bool(
                             validation["held_out"] is not None
                             and validation["held_out"].get("rms_px") is not None and solved),
                         "validated": False,
                         "accepted": False,
                         "note": "validated/accepted cần tiêu chí ứng dụng và kiểm chứng độc lập/giữa phiên"},
              "image_size": list(size), "K": K.tolist(), "D": D.tolist(), "rms_px": final["rms"],
              # std_intrinsics la sai so TRONG MOT lan fit - do 14-09 cho thay
              # no lac quan ~10 lan. Doc "stability" ben duoi moi la sai so that.
              "std_intrinsics": final["sd"].tolist(),
              "stability": stability(rows, board, size, k3, fix_principal, bootstrap),
              "fov_raw": field_of_view(K, D, *size),
              "fov_pinhole_reference": pinhole_reference(K, *size),
              "distortion_health": health, "coverage": coverage(final["rows"], size),
              "validation": validation,
              "split": {"train_indices": [row["index"] for row in train],
                        "test_indices": [row["index"] for row in test]},
              "observation_gate": {"minimum_views": 20, "minimum_cells_with_2_views": 28},
              "residual_structure": residual_structure(final["residuals"], size),
              "excluded_forced_views": excluded_forced, "residuals": final["residuals"]}
    rid, run_dir = create_run_dir(session_path)
    report["run_id"] = rid
    (run_dir / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report, run_dir
