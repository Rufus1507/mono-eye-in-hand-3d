"""Xuat ket qua mot run thanh bo file giao cho nguoi dung ngoai:

- camera.yaml : dinh dang cv2.FileStorage (camera_matrix, distortion_coefficients, ...)
- camera.json : cung so lieu, cho moi ngon ngu
- report.html : bao cao doc duoc, in ra PDF duoc; noi ro gioi han cua phep do

Bao cao chi ghi TEN tep anh, khong ghi duong dan tren may nguoi gui.
"""
from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from . import __version__
from .geometry import angle_between

D_NAMES = ("k1", "k2", "p1", "p2", "k3")
REASONS = {
    "accepted": "used",
    "size_mismatch": "different resolution from the other photos",
    "different_camera_or_zoom": "different camera, lens or zoom (EXIF)",
    "board_not_found": "board not found (fewer than 12 corners)",
    "blurry": "too blurry",
    "same_pose": "same pose as an earlier photo",
    "unreadable": "file could not be read",
}


def latest_run(session: Path) -> Path:
    runs = sorted((session / "runs").glob("*/result.json"))
    if not runs:
        raise FileNotFoundError(f"Phiên chưa có run nào: {session}")
    return runs[-1].parent


def pinhole_fov(K, width, height):
    """FOV pinhole doi xung (bo meo) theo ca ba chieu, cung quy uoc bien diem anh -0.5..N-0.5
    nhu geometry.field_of_view. Duong cheo tu cac GOC anh - dinh nghia hay gap trong datasheet."""
    K = np.asarray(K, np.float64); z = np.zeros(5)
    l, r, t, b = -.5, width - .5, -.5, height - .5
    cx, cy = K[0, 2], K[1, 2]
    return {"horizontal_deg": angle_between(((l, cy), (r, cy)), K, z),
            "vertical_deg": angle_between(((cx, t), (cx, b)), K, z),
            "diagonal_deg": angle_between(((l, t), (r, b)), K, z)}


def write_opencv_yaml(path: Path, K, D, size, extra: dict):
    fs = cv2.FileStorage(str(path), cv2.FILE_STORAGE_WRITE)
    try:
        fs.write("image_width", int(size[0])); fs.write("image_height", int(size[1]))
        fs.write("camera_matrix", np.asarray(K, np.float64))
        fs.write("distortion_coefficients", np.asarray(D, np.float64).reshape(1, -1))
        fs.write("distortion_model", "opencv k1 k2 p1 p2 k3")
        for key, value in extra.items():
            fs.write(key, value)
    finally:
        fs.release()


def read_opencv_yaml(path: Path):
    fs = cv2.FileStorage(str(path), cv2.FILE_STORAGE_READ)
    try:
        K = fs.getNode("camera_matrix").mat(); D = fs.getNode("distortion_coefficients").mat().reshape(-1)
        size = (int(fs.getNode("image_width").real()), int(fs.getNode("image_height").real()))
    finally:
        fs.release()
    return K, D, size


def _photo_rows(manifest, result):
    """Moi anh: ten, quyet dinh, so goc, diem net, RMS rieng anh (neu duoc dung)."""
    per_view = {r["index"]: r["rms_px"] for r in result.get("residuals", [])}
    held = {r["index"]: r["rms_px"] for r in ((result.get("validation") or {}).get("held_out") or {}).get("per_view", [])}
    rows, index = [], 0
    records = (manifest.get("import") or {}).get("records")
    if records is None:   # phien tu chup: moi anh deu la anh da nhan
        for i in range(manifest.get("accepted_frames", 0)):
            rows.append({"name": f"frame_{i:04d}.png", "decision": "accepted", "index": i})
    else:
        for rec in records:
            name = Path(rec["file"]).name + (f" @ frame {rec['frame']}" if "frame" in rec else "")
            row = {"name": name, "decision": rec["decision"], "corners": rec.get("corners"),
                   "quality": rec.get("quality")}
            if rec["decision"] == "accepted":
                row["index"] = index; index += 1
            rows.append(row)
    for row in rows:
        if "index" in row:
            row["fit_rms_px"] = per_view.get(row["index"])
            row["held_out_rms_px"] = held.get(row["index"])
    return rows


def _fmt(v, n=2, unit=""):
    return "&ndash;" if v is None else f"{v:.{n}f}{unit}"


def _coverage_table(cov):
    counts = cov["independent_views_per_cell"]
    top = max(1, max(max(r) for r in counts))
    cells = []
    for r in counts:
        tds = []
        for c in r:
            if c == 0:
                tds.append('<td class="empty">0</td>')
            else:
                a = 0.12 + 0.78 * c / top   # mot sac do, nhat -> dam theo so luot
                ink = "#fff" if a > .55 else "#0b0b0b"
                tds.append(f'<td style="background:rgba(42,120,214,{a:.2f});color:{ink}">{c}</td>')
        cells.append("<tr>" + "".join(tds) + "</tr>")
    return '<table class="cov">' + "".join(cells) + "</table>"


def report_html(result, manifest, camera_name, datasheet=None):
    w, h = result["image_size"]; K = np.asarray(result["K"]); D = result["D"]
    raw, st = result["fov_raw"], result.get("stability") or {}
    pin = pinhole_fov(K, w, h)
    held = (result.get("validation") or {}).get("held_out") or {}
    cov = result["coverage"]; status = result["status"]
    rows = _photo_rows(manifest, result)
    used = sum(r["decision"] == "accepted" for r in rows)

    def sd(key):
        return st.get(key, {}).get("sd")

    def fov_row(label, value, spread):
        pm = f" &plusmn; {spread:.2f}&deg;" if spread is not None else ""
        return f"<tr><td>{label}</td><td class='num'>{value:.2f}&deg;{pm}</td></tr>"

    fov_rows = (fov_row("Horizontal", raw["horizontal_deg"], sd("fov_horizontal_deg"))
                + fov_row("Vertical", raw["vertical_deg"], sd("fov_vertical_deg"))
                + fov_row("Diagonal", raw["diagonal_tl_br_deg"], sd("fov_diagonal_deg")))
    pin_rows = (fov_row("Horizontal", pin["horizontal_deg"], None) + fov_row("Vertical", pin["vertical_deg"], None)
                + fov_row("Diagonal", pin["diagonal_deg"], None))

    warnings = []
    if not status["observations_sufficient"]:
        warnings.append("Too few usable photos or too little coverage of the frame: treat the numbers as provisional.")
    if not status["solved"]:
        warnings.append("The distortion model is not valid over the whole image: do not use this calibration.")
    corners_empty = [name for name, (r, c) in (("top-left", (0, 0)), ("top-right", (0, -1)),
                                                ("bottom-left", (-1, 0)), ("bottom-right", (-1, -1)))
                     if cov["independent_views_per_cell"][r][c] == 0]
    if corners_empty:
        warnings.append("No board points in the " + ", ".join(corners_empty) + " corner"
                        + ("s" if len(corners_empty) > 1 else "") + " of the image. Lens distortion there is "
                        "extrapolated, not measured. More photos with the board in those corners would fix this.")
    if result["rms_px"] > 1.0:
        warnings.append(f"Reprojection error is {result['rms_px']:.2f} px; a good calibration is usually below 1 px. "
                        "Common causes: a board that is not flat, motion blur, or focus changing between photos. "
                        "The photos with the largest error are listed below.")
    if held.get("rms_px") is not None and held["rms_px"] > 1.5 * result["rms_px"]:
        warnings.append("Error on held-out photos is much larger than on the fitted photos: possible overfitting.")
    warn_html = "".join(f"<li>{html.escape(x)}</li>" for x in warnings) or "<li>None.</li>"

    ds_html = ""
    if datasheet:
        lines = []
        for key, label, ours, spread in (("hfov", "Horizontal", pin["horizontal_deg"], sd("fov_horizontal_deg")),
                                         ("dfov", "Diagonal", pin["diagonal_deg"], sd("fov_diagonal_deg"))):
            if datasheet.get(key) is None:
                continue
            diff = ours - datasheet[key]
            sig = f"{abs(diff) / spread:.1f}&sigma;" if spread else "&ndash;"
            lines.append(f"<tr><td>{label}</td><td class='num'>{ours:.2f}&deg;</td>"
                         f"<td class='num'>{datasheet[key]:.2f}&deg;</td><td class='num'>{diff:+.2f}&deg; ({sig})</td></tr>")
        if lines:
            ds_html = ("<h2>Comparison with the datasheet</h2><table><tr><th></th><th>Measured (pinhole)</th>"
                       "<th>Datasheet</th><th>Difference</th></tr>" + "".join(lines) + "</table>"
                       "<p class='note'>Datasheets usually quote the pinhole FOV, so the pinhole value is compared. "
                       "&sigma; uses the bootstrap spread of the real-ray FOV as an estimate.</p>")

    photo_html = "".join(
        f"<tr class='{'' if r['decision'] == 'accepted' else 'rej'}'><td>{html.escape(r['name'])}</td>"
        f"<td>{html.escape(REASONS.get(r['decision'], r['decision']))}</td>"
        f"<td class='num'>{r.get('corners') or '&ndash;'}</td><td class='num'>{_fmt(r.get('quality'), 1)}</td>"
        f"<td class='num'>{_fmt(r.get('fit_rms_px'), 2)}</td><td class='num'>{_fmt(r.get('held_out_rms_px'), 2)}</td></tr>"
        for r in rows)
    k_html = "".join("<tr>" + "".join(f"<td class='num'>{v:.4f}</td>" for v in row) + "</tr>" for row in K)
    d_html = "".join(f"<tr><td>{n}</td><td class='num'>{v:.6f}</td></tr>" for n, v in zip(D_NAMES, D))
    runs = st.get("runs_ok")

    css = """
    body{font-family:Arial,sans-serif;color:#0b0b0b;background:#fcfcfb;max-width:900px;margin:24px auto;padding:0 16px;font-size:14px;line-height:1.45}
    h1{font-size:24px;margin:0 0 4px} h2{font-size:17px;margin:26px 0 8px;color:#2a78d6}
    .sub,.note{color:#52514e} .note{font-size:12.5px}
    table{border-collapse:collapse;margin:6px 0} td,th{padding:4px 10px;border-bottom:1px solid #e4e3df;text-align:left}
    th{color:#52514e;font-weight:normal} .num{text-align:right;font-variant-numeric:tabular-nums}
    tr.rej td{color:#8a8984} .cov td{width:34px;height:24px;text-align:center;border:2px solid #fcfcfb;font-size:12px}
    .cov td.empty{background:#f0efec;color:#b3b2ad} .warn li{margin:4px 0}
    @media print{body{margin:0;max-width:none} h2{break-after:avoid} table{break-inside:auto}}
    """
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Camera calibration report</title>
<style>{css}</style></head><body>
<h1>Camera calibration report</h1>
<p class="sub">{html.escape(camera_name)} &middot; {w} &times; {h} px &middot; {used} of {len(rows)} photos used &middot;
{datetime.now().strftime("%Y-%m-%d")}</p>

<h2>Field of view</h2>
<table><tr><th>Real rays, with distortion</th><th></th></tr>{fov_rows}</table>
<p class="note">&plusmn; is one standard deviation over {runs or 0} bootstrap resamples of your photos: how much the result
moves if the photo set changes. It measures precision, not accuracy: it does not include systematic errors such as a
bent board or a focus change between photos.</p>
<table><tr><th>Pinhole, distortion ignored (what datasheets usually quote)</th><th></th></tr>{pin_rows}</table>
{ds_html}

<h2>Warnings</h2><ul class="warn">{warn_html}</ul>

<h2>Camera matrix K (pixels)</h2><table>{k_html}</table>
<h2>Distortion coefficients (OpenCV order)</h2><table>{d_html}</table>
<p class="note">Reprojection error: {result['rms_px']:.3f} px on the fitted photos,
{_fmt(held.get('rms_px'), 3, ' px')} on {held.get('views_ok', 0)} held-out photos that were not used for fitting.
Model: {html.escape(result['model'])}.</p>

<h2>Coverage of the image</h2>
{_coverage_table(cov)}
<p class="note">The image divided into 8 &times; 5 cells; each number is how many photos had board corners in that
cell. Empty cells are not measured.</p>

<h2>Photos</h2>
<table><tr><th>File</th><th>Result</th><th>Corners</th><th>Sharpness</th><th>Fit RMS px</th><th>Held-out RMS px</th></tr>
{photo_html}</table>

<h2>Files</h2>
<p><code>camera.yaml</code> (OpenCV <code>cv::FileStorage</code>) and <code>camera.json</code> hold the same K and
distortion coefficients for this resolution. They are valid only for this camera, this resolution and this
lens/zoom setting.</p>
<p class="note">Session {html.escape(result['session_id'])}, run {html.escape(result.get('run_id', ''))},
tool version {__version__}.</p>
</body></html>"""


def export(session: Path, run: Path | None = None, out: Path | None = None, camera_name="camera",
           datasheet=None):
    session = session.resolve()
    run = latest_run(session) if run is None else run.resolve()
    result = json.loads((run / "result.json").read_text(encoding="utf-8"))
    manifest = json.loads((session / "manifest.json").read_text(encoding="utf-8"))
    out = (run / "export") if out is None else out
    out.mkdir(parents=True, exist_ok=True)
    w, h = result["image_size"]
    pin = pinhole_fov(result["K"], w, h)
    st = result.get("stability") or {}
    fov = {"real_rays": {"horizontal_deg": result["fov_raw"]["horizontal_deg"],
                         "vertical_deg": result["fov_raw"]["vertical_deg"],
                         "diagonal_deg": result["fov_raw"]["diagonal_tl_br_deg"]},
           "pinhole": pin,
           "bootstrap_sd_deg": {k: st[f"fov_{k}_deg"]["sd"] for k in ("horizontal", "vertical", "diagonal")
                                if f"fov_{k}_deg" in st},
           "bootstrap_runs": st.get("runs_ok")}
    write_opencv_yaml(out / "camera.yaml", result["K"], result["D"], (w, h),
                      {"rms_px": float(result["rms_px"]),
                       "fov_horizontal_deg": float(fov["real_rays"]["horizontal_deg"]),
                       "fov_vertical_deg": float(fov["real_rays"]["vertical_deg"]),
                       "fov_diagonal_deg": float(fov["real_rays"]["diagonal_deg"])})
    data = {"image_width": w, "image_height": h, "camera_matrix": result["K"],
            "distortion_coefficients": result["D"], "distortion_model": "opencv k1 k2 p1 p2 k3",
            "rms_px": result["rms_px"],
            "held_out_rms_px": ((result.get("validation") or {}).get("held_out") or {}).get("rms_px"),
            "fov": fov, "session_id": result["session_id"], "run_id": result.get("run_id"),
            "tool_version": __version__}
    (out / "camera.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    (out / "report.html").write_text(report_html(result, manifest, camera_name, datasheet), encoding="utf-8")
    return out
