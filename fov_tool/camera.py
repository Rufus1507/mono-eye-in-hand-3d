from __future__ import annotations

import cv2

BACKENDS = {"msmf": cv2.CAP_MSMF, "dshow": cv2.CAP_DSHOW, "any": cv2.CAP_ANY}


def open_camera(index: int, width: int, height: int, fps: float, backend: str):
    choices = [backend] if backend != "auto" else ["msmf", "dshow", "any"]
    for name in choices:
        cap = cv2.VideoCapture(index, BACKENDS[name])
        if not cap.isOpened():
            cap.release(); continue
        # THU TU QUAN TRONG. DirectShow chi doi sang MJPG khi FOURCC duoc dat
        # SAU kich thuoc; dat truoc thi driver giu YUY2 khong nen va 1080p tut
        # xuong 5 fps (tran USB 2.0). Luc do cua so on dinh chi con 1 khung nen
        # viec "chon khung net nhat trong bo dem" mat tac dung ma khong bao loi.
        # THU TU BAT BUOC: fps -> size -> FOURCC. Duoi DirectShow, BAT KY lenh
        # set nao chay SAU khi dat FOURCC deu day dinh dang ve YUY2 khong nen
        # (do da nghiem: "size,fourcc,fps" -> YUY2 5 fps; "fps,size,fourcc" ->
        # MJPG 30 fps tren cung camera). YUY2 1080p dung het tran USB 2.0 nen
        # con 5 fps; luc do cua so on dinh 200 ms chi gom duoc 1 khung, viec
        # chon khung net nhat trong bo dem mat tac dung MA KHONG BAO LOI.
        # Kich thuoc thuc te doc lai tu khung dau tien ben duoi.
        if fps > 0: cap.set(cv2.CAP_PROP_FPS, fps)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        first = None
        for _ in range(10):
            ok, frame = cap.read()
            if ok and frame is not None:
                first = frame; break
        if first is None:
            cap.release(); continue
        h, w = first.shape[:2]
        raw_fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
        actual = {"width": w, "height": h, "fps_reported": cap.get(cv2.CAP_PROP_FPS),
                  "fourcc_reported": raw_fourcc,
                  # So nguyen tho doc khong ra; khong giai ma thi manifest khong
                  # the hien duoc luc nao camera roi ve YUY2 thay vi MJPG.
                  "fourcc_text": "".join(chr((raw_fourcc >> (8 * i)) & 0xFF) for i in range(4)),
                  "backend": name}
        controls = {}
        for label, prop in (("focus", cv2.CAP_PROP_FOCUS), ("autofocus", cv2.CAP_PROP_AUTOFOCUS),
                            ("zoom", cv2.CAP_PROP_ZOOM), ("exposure", cv2.CAP_PROP_EXPOSURE),
                            ("auto_exposure", cv2.CAP_PROP_AUTO_EXPOSURE)):
            value = cap.get(prop)
            controls[label] = None if value == -1 else float(value)
        actual["controls_readback"] = controls
        return cap, first, actual
    raise RuntimeError(f"Không mở được camera {index} bằng backend {backend}")


def freeze_controls(cap, freeze_focus=True, freeze_exposure=False):
    """Best effort only; every attempted set and readback is reported."""
    report = {}
    jobs = []
    if freeze_focus:
        jobs.append(("focus", cv2.CAP_PROP_AUTOFOCUS, cv2.CAP_PROP_FOCUS, 0.0))
    if freeze_exposure:
        # OpenCV's documented DirectShow manual-exposure value is 0.25.
        jobs.append(("exposure", cv2.CAP_PROP_AUTO_EXPOSURE, cv2.CAP_PROP_EXPOSURE, .25))
    for name, auto_prop, manual_prop, off in jobs:
        manual_before = float(cap.get(manual_prop))
        auto_before = float(cap.get(auto_prop))
        auto_set = bool(cap.set(auto_prop, off))
        manual_set = False if manual_before == -1 else bool(cap.set(manual_prop, manual_before))
        report[name] = {"auto_before": None if auto_before == -1 else auto_before,
                        "manual_before": None if manual_before == -1 else manual_before,
                        "auto_set_returned": auto_set, "manual_set_returned": manual_set,
                        "auto_after": None if cap.get(auto_prop) == -1 else float(cap.get(auto_prop)),
                        "manual_after": None if cap.get(manual_prop) == -1 else float(cap.get(manual_prop)),
                        "guaranteed": False}
    return report
