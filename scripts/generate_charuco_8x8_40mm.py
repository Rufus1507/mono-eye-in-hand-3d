import cv2
import numpy as np
import yaml
from pathlib import Path
from PIL import Image

def generate_charuco_8x8_40mm():
    """Tạo bảng ChArUco chuẩn 8x8 (ô đúng 40.0mm, marker đúng 32.0mm, viền 20mm).
    
    Kích thước tổng thể: 360mm x 360mm (8 ô x 40mm = 320mm, viền 20mm mỗi bên).
    Độ phân giải: 300 DPI chuẩn chế bản in sắc nét từng micron.
    """
    dpi = 300
    px_per_mm = dpi / 25.4

    cols, rows = 8, 8
    square_mm = 40.0
    marker_mm = 32.0 # 80% ô
    border_mm = 20.0
    total_mm = cols * square_mm + 2 * border_mm # 360.0 mm

    square_px = int(round(square_mm * px_per_mm))
    marker_px = int(round(marker_mm * px_per_mm))
    border_px = int(round(border_mm * px_per_mm))
    board_px = square_px * cols # 320mm in px
    total_px = board_px + 2 * border_px

    # 1. Tạo ChArUco Board từ OpenCV
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_100)
    charuco_board = cv2.aruco.CharucoBoard((cols, rows), square_mm, marker_mm, dictionary)
    board_img = charuco_board.generateImage((board_px, board_px), marginSize=0)

    # 2. Tạo Canvas nền trắng kích thước 360x360mm
    canvas = np.full((total_px, total_px), 255, dtype=np.uint8)
    canvas[border_px:border_px + board_px, border_px:border_px + board_px] = board_img

    # 3. Kẻ viền đen bo quanh bàn cờ
    cv2.rectangle(canvas, (border_px, border_px), (border_px + board_px, border_px + board_px), 0, 3)
    cv2.rectangle(canvas, (4, 4), (total_px - 4, total_px - 4), 0, 2)

    # 4. Ghi nhãn cột A-H và hàng 1-8 trên viền
    cols_str = ["A", "B", "C", "D", "E", "F", "G", "H"]
    for c in range(8):
        x_t = border_px + c * square_px + square_px // 2 - 12
        cv2.putText(canvas, cols_str[c], (x_t, border_px - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 0, 2)
        cv2.putText(canvas, cols_str[c], (x_t, border_px + board_px + 45), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 0, 2)

    for r in range(8):
        # r=0 là hàng 1 (ở dưới), r=7 là hàng 8 (ở trên)
        y_t = border_px + (7 - r) * square_px + square_px // 2 + 10
        cv2.putText(canvas, str(r + 1), (border_px - 45, y_t), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 0, 2)
        cv2.putText(canvas, str(r + 1), (border_px + board_px + 25, y_t), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 0, 2)

    # 5. Vẽ thước kiểm tra 300 mm ở cạnh dưới ngoài viền
    ruler_w_mm = 300.0
    ruler_x0_mm = (total_mm - ruler_w_mm) / 2.0
    ruler_y_mm = total_mm - 6.0
    ry_px = int(round(ruler_y_mm * px_per_mm))
    rx0_px = int(round(ruler_x0_mm * px_per_mm))
    rlen_px = int(round(ruler_w_mm * px_per_mm))

    cv2.line(canvas, (rx0_px, ry_px), (rx0_px + rlen_px, ry_px), 0, 2)
    for mm in range(0, int(ruler_w_mm) + 1):
        x = int(round((ruler_x0_mm + mm) * px_per_mm))
        if mm % 50 == 0:
            tick = int(round(5.0 * px_per_mm))
            cv2.line(canvas, (x, ry_px), (x, ry_px - tick), 0, 2)
        elif mm % 10 == 0:
            tick = int(round(3.5 * px_per_mm))
            cv2.line(canvas, (x, ry_px), (x, ry_px - tick), 0, 1)

    # 6. Xuất các file đầu ra
    p_pdf = Path("bang_charuco_8x8_o40mm_marker32mm.pdf")
    p_png = Path("bang_charuco_8x8_o40mm_marker32mm.png")
    p_yaml = Path("configs/bang_charuco_8x8_o40mm.yaml")

    cv2.imwrite(str(p_png), canvas)
    Image.fromarray(canvas).save(str(p_pdf), "PDF", resolution=float(dpi))

    # Xuất cấu hình YAML đồng bộ cho hệ thống Mono Eye
    cfg_data = {
        "bang": {
            "kieu": "charuco",
            "ten": "Ban co ChArUco 8x8 Chuan Quoc Te (O 40mm, Marker 32mm)",
            "o_ngang": cols,
            "o_doc": rows,
            "canh_o_mm": square_mm,
            "marker_mm": marker_mm,
            "ti_le_marker_tren_o": round(marker_mm / square_mm, 4),
            "tu_dien": "4X4_100",
            "chieu_rong_vien_mm": border_mm,
            "tong_rong_mm": cols * square_mm,
            "tong_dai_mm": rows * square_mm,
            "tong_rong_ca_vien_mm": total_mm,
            "tong_dai_ca_vien_mm": total_mm,
        },
        "ban_in": {
            "dpi": dpi,
            "canh_o_mm": square_mm,
            "marker_mm": marker_mm,
            "tong_mm": total_mm,
        }
    }
    with open(p_yaml, "w", encoding="utf-8") as f:
        yaml.dump(cfg_data, f, allow_unicode=True, sort_keys=False)

    print(f"-> Da tao thanh cong: {p_pdf}")
    print(f"-> Da tao anh PNG net: {p_png}")
    print(f"-> Da luu cau hinh:    {p_yaml}")

if __name__ == "__main__":
    generate_charuco_8x8_40mm()
