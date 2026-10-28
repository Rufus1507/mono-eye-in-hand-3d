import cv2
import numpy as np
import yaml
from pathlib import Path
from PIL import Image

def generate_charuco_8x8_a3_35mm():
    """Tạo bảng ChArUco 8x8 in VỪA KHÍT 1 tờ giấy A3 tiêu chuẩn (420x297mm).
    
    Kích thước ô: 35.0 mm (3.5 cm).
    Kích thước marker: 28.0 mm (80% ô).
    Kích thước bàn cờ: 8 ô x 35mm = 280mm x 280mm.
    Khổ giấy A3 ngang: 420mm x 297mm (Lọt thỏm hoàn hảo, còn dư lề trên dưới 8.5mm).
    """
    dpi = 300
    px_per_mm = dpi / 25.4

    cols, rows = 8, 8
    square_mm = 35.0
    marker_mm = 28.0
    w_mm, h_mm = 420.0, 297.0 # Khổ A3 tiêu chuẩn

    w_px = int(round(w_mm * px_per_mm))
    h_px = int(round(h_mm * px_per_mm))
    square_px = int(round(square_mm * px_per_mm))
    board_px = square_px * cols # 280mm in px

    # 1. Tạo ChArUco Board từ OpenCV
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_100)
    charuco_board = cv2.aruco.CharucoBoard((cols, rows), square_mm, marker_mm, dictionary)
    board_img = charuco_board.generateImage((board_px, board_px), marginSize=0)

    # 2. Tạo Canvas A3 nền trắng và căn giữa bàn cờ
    canvas = np.full((h_px, w_px), 255, dtype=np.uint8)
    ox = (w_px - board_px) // 2
    oy = (h_px - board_px) // 2
    canvas[oy:oy + board_px, ox:ox + board_px] = board_img

    # 3. Kẻ viền đen bo quanh bàn cờ
    cv2.rectangle(canvas, (ox, oy), (ox + board_px, oy + board_px), 0, 3)

    # 4. Ghi nhãn cột A-H và hàng 1-8 trên khoảng trống hai bên
    cols_str = ["A", "B", "C", "D", "E", "F", "G", "H"]
    for c in range(8):
        x_t = ox + c * square_px + square_px // 2 - 10
        cv2.putText(canvas, cols_str[c], (x_t, oy - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.55, 0, 2)
        cv2.putText(canvas, cols_str[c], (x_t, oy + board_px + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.55, 0, 2)

    for r in range(8):
        y_t = oy + (7 - r) * square_px + square_px // 2 + 8
        cv2.putText(canvas, str(r + 1), (ox - 35, y_t), cv2.FONT_HERSHEY_SIMPLEX, 0.65, 0, 2)
        cv2.putText(canvas, str(r + 1), (ox + board_px + 20, y_t), cv2.FONT_HERSHEY_SIMPLEX, 0.65, 0, 2)

    # 5. Thước kiểm tra 250mm ở mép dưới bên phải
    ruler_len_mm = 250.0
    rx0_px = ox
    ry_px = int(round(288.0 * px_per_mm))
    rlen_px = int(round(ruler_len_mm * px_per_mm))

    cv2.line(canvas, (rx0_px, ry_px), (rx0_px + rlen_px, ry_px), 0, 2)
    for mm in range(0, int(ruler_len_mm) + 1):
        x = int(round((rx0_px / px_per_mm + mm) * px_per_mm))
        if mm % 50 == 0:
            cv2.line(canvas, (x, ry_px), (x, ry_px + int(round(4.0 * px_per_mm))), 0, 2)
            cv2.putText(canvas, str(mm), (x - 12, ry_px + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 0, 1)
        elif mm % 10 == 0:
            cv2.line(canvas, (x, ry_px), (x, ry_px + int(round(2.5 * px_per_mm))), 0, 1)

    info = "BANG CHARUCO 8x8 (A3 NGANG 420x297mm) | O 35.0mm | MARKER 28.0mm | DICT_4X4_100"
    cv2.putText(canvas, info, (ox, int(round(12.0 * px_per_mm))), cv2.FONT_HERSHEY_SIMPLEX, 0.55, 0, 1)

    p_pdf = Path("bang_charuco_8x8_A3_o35mm_marker28mm.pdf")
    p_png = Path("bang_charuco_8x8_A3_o35mm_marker28mm.png")
    p_yaml = Path("configs/bang_charuco_8x8_A3_o35mm.yaml")

    cv2.imwrite(str(p_png), canvas)
    Image.fromarray(canvas).save(str(p_pdf), "PDF", resolution=float(dpi))

    cfg_data = {
        "bang": {
            "kieu": "charuco",
            "ten": "Ban co ChArUco 8x8 A3 Vua Khit (O 35mm, Marker 28mm)",
            "o_ngang": cols,
            "o_doc": rows,
            "canh_o_mm": square_mm,
            "marker_mm": marker_mm,
            "ti_le_marker_tren_o": round(marker_mm / square_mm, 4),
            "tu_dien": "4X4_100",
            "tong_rong_mm": cols * square_mm,
            "tong_dai_mm": rows * square_mm,
            "kho": "A3",
        },
        "ban_in": {
            "dpi": dpi,
            "canh_o_mm": square_mm,
            "marker_mm": marker_mm,
        }
    }
    with open(p_yaml, "w", encoding="utf-8") as f:
        yaml.dump(cfg_data, f, allow_unicode=True, sort_keys=False)

    print(f"-> Da tao ban in A3: {p_pdf}")

if __name__ == "__main__":
    generate_charuco_8x8_a3_35mm()
