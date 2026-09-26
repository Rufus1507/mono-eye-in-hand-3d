#!/usr/bin/env python3
"""tao_bang - sinh BANG CHUAN ChArUco de hieu chuan camera (A4 hoac A3).

Chuong trinh DOC LAP, di cap voi calib/do_fov.py. Xuat ba file vao calib/:
  bang_charuco_<kho>.png   anh 300 dpi (xem nhanh, KHONG dung de in)
  bang_charuco_<kho>.pdf   BAN IN - in file nay
  bang_calib_<kho>.yaml    thong so bang, do_fov.py doc file nay

LUOI O KHONG DOI GIUA CAC KHO (11x7, DICT_4X4_50, marker/o = 0.7268). A4 chi
la ban A3 thu nho: canh o nho hon, moi thu khac y nguyen. Vi trong hieu chuan
Zhang canh o chi dat THANG DO cho the gioi - ma tran K (va f_px, va FOV) BAT
BIEN voi thang do do - nen bang A4 va bang A3 cho CUNG mot ket qua, chi khac
la bang nho thi phai dua lai gan camera hon.

Vi sao ChArUco chu khong phai ban co tron:
  ban co tron phai thay TRON VEN ca bang -> khong bao gio dua duoc bang ra sat
  4 goc khung -> he so meo o ria khong duoc rang buoc. ChArUco van nhan dien
  duoc khi bang bi che hay tran ra ngoai khung.

IN THE NAO:
  - In dung 100 % / "Actual size". TAT "Fit to page", "Scale to fit",
    "Shrink oversized pages" - may in thu nho thi thang do sai.
  - In tren giay day, dan PHANG len bia cung. Bang cong veo la sai so meo.
  - Mat giay mo (khong bong) - giay bong hat den lam nhoe goc o.

KIEM SAU KHI IN (in xong do ba so ghi o le duoi to giay):
  scale DANG HUONG (ca hai chieu cung ti le) KHONG lam sai f_px - xem tren.
  Cai lam hong phep do la scale DI HUONG: ngang va doc khac ti le -> bang bi
  banh -> fx/fy sai that. Ba so de bat loi do:
    1. CA BANG mep-toi-mep   (tay don dai nhat -> chinh xac nhat)
    2. thuoc ngang o le TREN
    3. thuoc doc o le TRAI
  Ti le ngang va ti le doc phai bang nhau. Lech nhau => in lai.

Usage:
    py -3.14 calib/tao_bang.py                 # A4 (mac dinh)
    py -3.14 calib/tao_bang.py --kho a3
    py -3.14 calib/tao_bang.py --kho a4 --o-ngang 11 --o-doc 7
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
import yaml
from PIL import Image

THU_MUC = Path(__file__).resolve().parent

# kho giay NGANG (landscape), mm - khung hinh camera la ngang
KHO = {"a4": (297.0, 210.0), "a3": (420.0, 297.0)}
KHO_THAM_CHIEU = 420.0        # moi kich thuoc net ve scale theo be ngang nay

# chieu cao vach theo loai moc (mm) + net ve, do cho kho A3; kho khac thi nhan k
VACH_MM = {0: 12.0, 1: 2.5, 5: 4.0, 10: 6.5, 50: 9.0}
VACH_NET_MM = {0: 0.6, 1: 0.25, 5: 0.3, 10: 0.4, 50: 0.5}
THUOC_NEN_NET_MM = 0.3        # duong nen cua thuoc
SO_CAO_MM = 3.4               # chieu cao chu so tren thuoc
SO_HO_MM = 4.2                # ho tu dau vach 50 toi day chu so
LE_THUOC_MM = 10.0            # thuoc cach mep giay - TUYET DOI, khong scale
HO_TOI_THIEU_MM = 3.0         # ho giua thuoc va bang
BANG_CHU_MM = 3.2             # chieu cao chu dong chu thich + dong KIEM IN
CHU_DAY_MM = (26.0, 18.5, 11.0)   # ba dong chu thich cach DAY to giay
DAI_CHU_MM = 30.0             # dai duoi to giay danh cho ba dong chu thich
                              # (= dong tren cung + than chu + ho toi bang)
CHU_TRANH_THUOC_MM = 30.0     # chu bat dau tu day de khong de len thuoc doc
AN_TOAN = 0.97                # rut canh o lai chut cho chac chan khong cham

DICTS = {"4X4_50": cv2.aruco.DICT_4X4_50,
         "4X4_100": cv2.aruco.DICT_4X4_100,
         "5X5_100": cv2.aruco.DICT_5X5_100}


class Trang:
    """Canvas mot to giay - moi phep ve nhan toa do MM, tu quy ra pixel."""

    def __init__(self, w_mm: float, h_mm: float, dpi: int, k: float):
        self.px_mm = dpi / 25.4
        self.k = k                        # he so thu nho net ve theo kho giay
        self.W = int(round(w_mm * self.px_mm))
        self.H = int(round(h_mm * self.px_mm))
        self.anh = np.full((self.H, self.W), 255, np.uint8)

    def p(self, mm: float) -> int:
        return int(round(mm * self.px_mm))

    def hop(self, x_mm: float, y_mm: float, w_mm: float, h_mm: float) -> None:
        """Chu nhat DEN dac - dung cho vach thuoc, bien trung bien pixel."""
        x, y = self.p(x_mm), self.p(y_mm)
        w, h = max(1, self.p(w_mm)), max(1, self.p(h_mm))
        self.anh[y:y + h, x:x + w] = 0

    def chu(self, s: str, x_mm: float, y_mm: float, cao_mm: float,
            can_giua: bool = False, rong_toi_da_mm: float | None = None) -> None:
        """Ve chu; y_mm la DAY chu. rong_toi_da_mm: tu co co chu cho vua - dong
        KIEM IN khong duoc tran ra mep, may in cat mat la mat luon so doi chieu."""
        co = cao_mm * self.px_mm / 22.0
        day = max(1, int(round(0.3 * self.k * self.px_mm)))
        (tw, _), _ = cv2.getTextSize(s, cv2.FONT_HERSHEY_SIMPLEX, co, day)
        if rong_toi_da_mm is not None and tw / self.px_mm > rong_toi_da_mm:
            co *= rong_toi_da_mm * self.px_mm / tw
            day = max(1, int(round(0.22 * self.k * self.px_mm)))
            (tw, _), _ = cv2.getTextSize(s, cv2.FONT_HERSHEY_SIMPLEX, co, day)
        x = self.p(x_mm) - (tw // 2 if can_giua else 0)
        cv2.putText(self.anh, s, (x, self.p(y_mm)), cv2.FONT_HERSHEY_SIMPLEX,
                    co, 0, day, cv2.LINE_AA)

    def thuoc(self, x0_mm: float, y0_mm: float, dai_mm: float, doc: bool,
              ghi_so: bool) -> None:
        """Thuoc vach mm. (x0_mm, y0_mm) = vach 0 tren duong nen; vach moc dua
        ra phia TANG cua truc con lai. doc=True -> thuoc chay theo chieu doc."""
        k, nen = self.k, THUOC_NEN_NET_MM * self.k
        if doc:
            self.hop(x0_mm, y0_mm, nen, dai_mm)
        else:
            self.hop(x0_mm, y0_mm, dai_mm, nen)
        for i in range(int(dai_mm) + 1):
            moc = (0 if i in (0, int(dai_mm)) else 50 if i % 50 == 0 else
                   10 if i % 10 == 0 else 5 if i % 5 == 0 else 1)
            cao, net = VACH_MM[moc] * k, VACH_NET_MM[moc] * k
            if doc:
                self.hop(x0_mm + nen, y0_mm + i, cao, net)
            else:
                self.hop(x0_mm + i, y0_mm + nen, net, cao)
            if ghi_so and i % 50 == 0 and not doc:
                self.chu(str(i), x0_mm + i,
                         y0_mm + nen + VACH_MM[50] * k + SO_HO_MM * k
                         + SO_CAO_MM * k, SO_CAO_MM * k, can_giua=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kho", choices=sorted(KHO), default="a4")
    ap.add_argument("--o-ngang", type=int, default=11, help="so O theo chieu ngang")
    ap.add_argument("--o-doc", type=int, default=7, help="so O theo chieu doc")
    ap.add_argument("--canh-mm", type=float, default=None,
                    help="canh o (mm); bo trong thi tu lay lon nhat vua to giay")
    ap.add_argument("--ti-le-marker", type=float, default=0.726832,
                    help="canh marker / canh o - GIU NGUYEN de moi kho cung bang")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--tu-dien", choices=sorted(DICTS), default="4X4_50")
    ap.add_argument("--ra", type=Path, default=THU_MUC)
    args = ap.parse_args()

    if args.o_ngang < 3 or args.o_doc < 3:
        print("LOI: moi chieu cua bang phai co it nhat 3 o")
        return 1
    if args.dpi <= 0:
        print("LOI: --dpi phai lon hon 0")
        return 1
    if args.canh_mm is not None and args.canh_mm <= 0:
        print("LOI: --canh-mm phai lon hon 0")
        return 1
    if not 0.0 < args.ti_le_marker < 1.0:
        print("LOI: --ti-le-marker phai nam trong (0, 1)")
        return 1

    W_MM, H_MM = KHO[args.kho]
    k = W_MM / KHO_THAM_CHIEU              # net ve thu nho theo kho giay

    # le toi thieu de thuoc khong cham bang
    cao_thuoc = (THUOC_NEN_NET_MM + VACH_MM[50] + SO_HO_MM + SO_CAO_MM) * k
    rong_thuoc = (THUOC_NEN_NET_MM + VACH_MM[0]) * k
    le_tren = LE_THUOC_MM + cao_thuoc + HO_TOI_THIEU_MM
    le_trai = LE_THUOC_MM + rong_thuoc + HO_TOI_THIEU_MM

    # chieu doc: tru ca dai chu thich o duoi, neu khong bang de len chu
    canh_mm = args.canh_mm or (AN_TOAN * min(
        (W_MM - 2 * le_trai) / args.o_ngang,
        (H_MM - le_tren - DAI_CHU_MM) / args.o_doc))
    if canh_mm <= 0:
        print("LOI: kho giay qua nho cho so o nay")
        return 1

    t = Trang(W_MM, H_MM, args.dpi, k)

    # canh o lam tron ve SO NGUYEN pixel -> canh o trung bien pixel, khong bi
    # khu rang cua lam nhoe goc. Lech thang do (~0.1 %) khong anh huong f_px vi
    # tool hieu chuan dung canh o = 1.0.
    canh_px = int(canh_mm * t.px_mm)
    bw, bh = canh_px * args.o_ngang, canh_px * args.o_doc
    canh_that = canh_px / t.px_mm
    marker_that = canh_that * args.ti_le_marker
    bang_w, bang_h = bw / t.px_mm, bh / t.px_mm

    tu_dien = cv2.aruco.getPredefinedDictionary(DICTS[args.tu_dien])
    board = cv2.aruco.CharucoBoard((args.o_ngang, args.o_doc),
                                   canh_that, marker_that, tu_dien)
    n_marker = len(board.getIds())
    if n_marker > tu_dien.bytesList.shape[0]:
        print(f"LOI: bang can {n_marker} marker, tu dien {args.tu_dien} khong du")
        return 1

    # bang can giua theo NGANG, va can giua vung con lai sau khi tru dai chu
    x0 = (t.W - bw) // 2
    y0 = t.p((le_tren + H_MM - DAI_CHU_MM) / 2.0) - bh // 2
    if x0 < 0 or y0 < 0:
        print("LOI: bang khong vua to giay - giam --canh-mm hoac so o")
        return 1
    t.anh[y0:y0 + bh, x0:x0 + bw] = board.generateImage((bw, bh))
    ho_tren = y0 / t.px_mm - (LE_THUOC_MM + cao_thuoc)
    ho_trai = x0 / t.px_mm - (LE_THUOC_MM + rong_thuoc)
    if ho_tren < 1.0 or ho_trai < 1.0:
        print(f"LOI: thuoc cham bang (ho tren {ho_tren:.1f} mm, trai "
              f"{ho_trai:.1f} mm) - giam --canh-mm")
        return 1

    # thuoc: dai nhat con vua giay, lam tron xuong boi so 10 mm
    dai_ngang = float(int((W_MM - 2 * LE_THUOC_MM - 4.0) / 10.0) * 10)
    dai_doc = float(int((H_MM - 2 * LE_THUOC_MM - 4.0) / 10.0) * 10)
    t.thuoc((W_MM - dai_ngang) / 2.0, LE_THUOC_MM, dai_ngang,
            doc=False, ghi_so=True)
    t.thuoc(LE_THUOC_MM, (H_MM - dai_doc) / 2.0, dai_doc,
            doc=True, ghi_so=False)

    # chu thich o le DUOI: bat dau tu CHU_TRANH_THUOC_MM de khong de len thuoc
    # doc, va cach day giay >= 10 mm de may in khong cat mat so KIEM IN
    x_chu = (CHU_TRANH_THUOC_MM + W_MM - LE_THUOC_MM) / 2.0
    rong_chu = W_MM - LE_THUOC_MM - CHU_TRANH_THUOC_MM
    cao_chu = BANG_CHU_MM
    t.chu(f"ChArUco {args.o_ngang}x{args.o_doc}  |  o {canh_that:.2f} mm  |  "
          f"marker {marker_that:.2f} mm  |  {args.tu_dien}  |  {args.kho.upper()} "
          f"ngang  |  IN 100 % (TAT Fit to page)",
          x_chu, H_MM - CHU_DAY_MM[0], cao_chu, can_giua=True,
          rong_toi_da_mm=rong_chu)
    t.chu(f"KIEM IN - do ba so nay:   CA BANG {bang_w:.1f} x {bang_h:.1f} mm"
          f"   |   thuoc tren {dai_ngang:.0f} mm   |   thuoc trai {dai_doc:.0f} mm",
          x_chu, H_MM - CHU_DAY_MM[1], cao_chu, can_giua=True,
          rong_toi_da_mm=rong_chu)
    # may in hay tu thu nho. Scale DEU khong lam sai f_px (canh o chi dat thang
    # do cho the gioi, K bat bien voi thang do) - chi scale LECH hai chieu moi
    # lam banh bang va sai fx/fy. Ghi len giay de khoi in lai vo ich.
    t.chu("Ti le ngang = ti le doc (vd ca hai 96 %): VAN DUNG, KHONG can in lai."
          "   Hai ti le KHAC nhau: in lai.",
          x_chu, H_MM - CHU_DAY_MM[2], cao_chu, can_giua=True,
          rong_toi_da_mm=rong_chu)

    args.ra.mkdir(parents=True, exist_ok=True)
    ten = f"bang_charuco_{args.kho.upper()}"
    p_png, p_pdf = args.ra / f"{ten}.png", args.ra / f"{ten}.pdf"
    p_yaml = args.ra / f"bang_calib_{args.kho.upper()}.yaml"
    cv2.imwrite(str(p_png), t.anh)
    Image.fromarray(t.anh).convert("L").save(str(p_pdf), "PDF",
                                             resolution=float(args.dpi))
    p_yaml.write_text(yaml.safe_dump({
        "bang": {"kieu": "charuco", "o_ngang": args.o_ngang, "o_doc": args.o_doc,
                 "tu_dien": args.tu_dien, "canh_o": 1.0,
                 "ti_le_marker_tren_o": float(args.ti_le_marker),
                 "so_goc_trong": int(board.getChessboardCorners().shape[0]),
                 "so_marker": n_marker, "opencv_sinh": cv2.__version__},
        "ban_in": {"kho": f"{args.kho.upper()} ngang", "dpi": args.dpi,
                   "canh_o_mm": round(canh_that, 3),
                   "marker_mm": round(marker_that, 3)},
        "kiem_in": {"ca_bang_ngang_mm": round(bang_w, 2),
                    "ca_bang_doc_mm": round(bang_h, 2),
                    "thuoc_ngang_mm": dai_ngang, "thuoc_doc_mm": dai_doc,
                    "do_duoc_ngang_mm": None, "do_duoc_doc_mm": None},
    }, sort_keys=False, allow_unicode=True), encoding="utf-8")

    print(f"kho          : {args.kho.upper()} ngang {W_MM:.0f} x {H_MM:.0f} mm @ "
          f"{args.dpi} dpi")
    print(f"bang         : {args.o_ngang}x{args.o_doc} o, canh o {canh_that:.2f} mm, "
          f"marker {marker_that:.2f} mm, {n_marker} marker, "
          f"{int(board.getChessboardCorners().shape[0])} goc trong")
    print(f"ca bang      : {bang_w:.1f} x {bang_h:.1f} mm  "
          f"(ho toi thuoc: tren {ho_tren:.1f} mm, trai {ho_trai:.1f} mm)")
    print(f"le an toan   : moi thu cach mep giay >= {LE_THUOC_MM:.0f} mm, "
          f"dong chu duoi cung cach day {CHU_DAY_MM[-1]:.0f} mm")
    print(f"\nIN {p_pdf.name}: chon 'Actual size' / 'Custom scale 100 %'.")
    print("  TAT 'Fit to page' / 'Fit to printable area' / 'Shrink oversized pages'")
    print("  (Acrobat: Size = Actual size. Edge/Chrome: More settings -> Scale = 100.)")
    print("In xong do ba so o le duoi giay. May in van thu nho? Khong sao, mien la")
    print("  ti le NGANG = ti le DOC - thang do khong vao f_px. Lech nhau moi in lai.")
    print(f"\nda ghi:\n  {p_pdf}\n  {p_png}\n  {p_yaml}")
    print(f"\nDo FOV bang bang nay:\n  .\\calib\\run_fov.ps1 capture "
          f"--board calib/{p_yaml.name} --name <ten camera>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
