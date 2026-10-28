import cv2
import numpy as np
import yaml
from pathlib import Path
from PIL import Image

def generate_charuco_a3_40mm():
    """Tạo bảng ChArUco trên khổ giấy A3 với cạnh ô đúng bằng 40.0 mm."""
    dpi = 300
    px_per_mm = dpi / 25.4
    
    # Khổ giấy A3 ngang: 420mm x 297mm
    w_mm, h_mm = 420.0, 297.0
    w_px = int(round(w_mm * px_per_mm))
    h_px = int(round(h_mm * px_per_mm))
    
    canvas = np.full((h_px, w_px), 255, dtype=np.uint8)
    
    # Lưới 9 cột x 6 hàng, mỗi ô 40mm
    cols, rows = 9, 6
    square_mm = 40.0
    marker_mm = 24.0  # Marker 24mm theo đúng kích thước bạn đã cung cấp
    
    board_w_mm = cols * square_mm  # 360mm
    board_h_mm = rows * square_mm  # 240mm
    
    square_px = int(round(square_mm * px_per_mm))
    marker_px = int(round(marker_mm * px_per_mm))
    board_w_px = square_px * cols
    board_h_px = square_px * rows
    
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    charuco_board = cv2.aruco.CharucoBoard((cols, rows), square_mm, marker_mm, dictionary)
    board_img = charuco_board.generateImage((board_w_px, board_h_px), marginSize=0)
    
    # Căn giữa bảng trên trang A3 (dành khoảng trống bên dưới cho dòng chú thích & thước kiểm tra)
    offset_x = (w_px - board_w_px) // 2
    offset_y = int(round(20.0 * px_per_mm))
    
    canvas[offset_y:offset_y + board_h_px, offset_x:offset_x + board_w_px] = board_img
    
    # Vẽ thước kiểm tra 350 mm ở mép dưới
    ruler_y_mm = 270.0
    ruler_x0_mm = (w_mm - 350.0) / 2.0
    ruler_len_mm = 350.0
    
    ry_px = int(round(ruler_y_mm * px_per_mm))
    rx0_px = int(round(ruler_x0_mm * px_per_mm))
    rlen_px = int(round(ruler_len_mm * px_per_mm))
    
    cv2.line(canvas, (rx0_px, ry_px), (rx0_px + rlen_px, ry_px), 0, 2)
    for mm in range(0, int(ruler_len_mm) + 1):
        x = int(round((ruler_x0_mm + mm) * px_per_mm))
        if mm % 50 == 0:
            tick = int(round(8.0 * px_per_mm))
            cv2.putText(canvas, f"{mm}", (x - 15, ry_px + tick + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 0, 2)
        elif mm % 10 == 0:
            tick = int(round(5.0 * px_per_mm))
        elif mm % 5 == 0:
            tick = int(round(3.5 * px_per_mm))
        else:
            tick = int(round(2.0 * px_per_mm))
        cv2.line(canvas, (x, ry_px), (x, ry_px + tick), 0, 1)
        
    # Chú thích hướng dẫn in
    info_text = f"BANG CHARUCO CHUAN O 40.0mm (A3 NGANG 420x297mm) | Lưới {cols}x{rows} | Marker {marker_mm:.1f}mm | DICT_4X4_50"
    guide_text = "HUONG DAN IN: Chon 'Actual Size' (100%), TAT 'Fit to page'. In xong dung thuoc do doan 0-350mm de kiem tra."
    cv2.putText(canvas, info_text, (offset_x, offset_y + board_h_px + int(round(12.0 * px_per_mm))), cv2.FONT_HERSHEY_SIMPLEX, 0.65, 0, 2)
    cv2.putText(canvas, guide_text, (offset_x, offset_y + board_h_px + int(round(20.0 * px_per_mm))), cv2.FONT_HERSHEY_SIMPLEX, 0.60, 0, 1)
    
    # Xuất file
    p_png = Path("bang_charuco_A3_o40mm.png")
    p_pdf = Path("bang_charuco_A3_o40mm.pdf")
    p_yaml = Path("bang_charuco_A3_o40mm.yaml")
    
    cv2.imwrite(str(p_png), canvas)
    Image.fromarray(canvas).save(str(p_pdf), "PDF", resolution=float(dpi))
    
    with open(p_yaml, "w", encoding="utf-8") as f:
        yaml.dump({
            "bang": {
                "kieu": "charuco",
                "o_ngang": cols,
                "o_doc": rows,
                "canh_o_mm": square_mm,
                "marker_mm": marker_mm,
                "tu_dien": "4X4_50",
                "kho": "A3",
                "tong_rong_mm": board_w_mm,
                "tong_dai_mm": board_h_mm,
            }
        }, f, allow_unicode=True)
    print(f"-> Da tao: {p_pdf} va {p_png}")


def generate_chessboard_8x8_aruco_40mm():
    """Tạo bàn cờ vua thật 8x8 ô 40mm, viền 20mm, tích hợp 32 ArUco 24mm chuẩn banco_8x8.yaml."""
    dpi = 300
    px_per_mm = dpi / 25.4
    
    # Bàn cờ 8 ô x 40mm = 320mm. Viền 20mm mỗi bên -> Tổng thể 360mm x 360mm
    total_mm = 360.0
    border_mm = 20.0
    square_mm = 40.0
    marker_mm = 24.0
    
    total_px = int(round(total_mm * px_per_mm))
    border_px = int(round(border_mm * px_per_mm))
    square_px = int(round(square_mm * px_per_mm))
    marker_px = int(round(marker_mm * px_per_mm))
    
    canvas = np.full((total_px, total_px), 255, dtype=np.uint8)
    
    # Nạp cấu hình vị trí 32 markers từ banco_8x8.yaml
    with open("configs/banco_8x8.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    marker_dict_cfg = cfg.get("markers", {})
    
    dict_aruco = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    
    # Vẽ 64 ô cờ vua 8x8 (Ô A1 ở dưới-trái, hàng 1 ở dưới cùng y tăng dần từ dưới lên hoặc từ trên xuống theo quy ước)
    # Quy ước cờ vua: A1 là ô Đen ở góc trái dưới người cầm quân Trắng.
    # Trong banco_8x8: row 0 = hàng 1, col 0 = cột a.
    for r in range(8):
        for c in range(8):
            # Tọa độ ô cờ: r=0 ở dưới cùng (Y cao nhất)
            x_o = border_px + c * square_px
            y_o = border_px + (7 - r) * square_px  # hàng 1 (r=0) ở dưới
            
            # Ô cờ xen kẽ màu: (r + c) % 2 == 0 là ô Đen (Dark Square)
            is_dark = (r + c) % 2 == 0
            if is_dark:
                canvas[y_o:y_o + square_px, x_o:x_o + square_px] = 40  # Màu xám đậm / đen
            else:
                canvas[y_o:y_o + square_px, x_o:x_o + square_px] = 250  # Màu trắng
                
    # Dán 32 mã ArUco lên các ô cờ theo đúng banco_8x8.yaml
    for m_id, m_info in marker_dict_cfg.items():
        c_idx = m_info["col_idx"]
        r_idx = m_info["row_idx"]
        rot_deg = m_info.get("rot_deg", 0)
        
        # Tạo ảnh marker ArUco 24mm
        m_img = cv2.aruco.generateImageMarker(dict_aruco, int(m_id), marker_px, borderBits=1)
        
        # Xoay marker theo rot_deg
        if rot_deg == 90:
            m_img = cv2.rotate(m_img, cv2.ROTATE_90_CLOCKWISE)
        elif rot_deg == 180:
            m_img = cv2.rotate(m_img, cv2.ROTATE_180)
        elif rot_deg == 270:
            m_img = cv2.rotate(m_img, cv2.ROTATE_90_COUNTERCLOCKWISE)
            
        # Căn giữa marker trong ô cờ
        x_o = border_px + c_idx * square_px
        y_o = border_px + (7 - r_idx) * square_px
        offset_m_x = (square_px - marker_px) // 2
        offset_m_y = (square_px - marker_px) // 2
        
        canvas[y_o + offset_m_y:y_o + offset_m_y + marker_px, x_o + offset_m_x:x_o + offset_m_x + marker_px] = m_img
        
    # Kẻ viền bao quanh bàn cờ
    cv2.rectangle(canvas, (border_px, border_px), (border_px + 8 * square_px, border_px + 8 * square_px), 0, 3)
    cv2.rectangle(canvas, (4, 4), (total_px - 4, total_px - 4), 0, 2)
    
    # Ghi tên cột A-H và hàng 1-8 trên phần viền 20mm
    cols_str = ["A", "B", "C", "D", "E", "F", "G", "H"]
    for c in range(8):
        x_t = border_px + c * square_px + square_px // 2 - 10
        cv2.putText(canvas, cols_str[c], (x_t, border_px - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 0, 2)
        cv2.putText(canvas, cols_str[c], (x_t, border_px + 8 * square_px + 45), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 0, 2)
        
    for r in range(8):
        y_t = border_px + (7 - r) * square_px + square_px // 2 + 10
        cv2.putText(canvas, str(r + 1), (border_px - 45, y_t), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 0, 2)
        cv2.putText(canvas, str(r + 1), (border_px + 8 * square_px + 20, y_t), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 0, 2)
        
    # Thước kiểm tra 100mm ở góc viền dưới
    p_banco_png = Path("banco_8x8_aruco_40mm.png")
    p_banco_pdf = Path("banco_8x8_aruco_40mm.pdf")
    
    cv2.imwrite(str(p_banco_png), canvas)
    Image.fromarray(canvas).save(str(p_banco_pdf), "PDF", resolution=float(dpi))
    print(f"-> Da tao: {p_banco_pdf} va {p_banco_png}")

if __name__ == "__main__":
    generate_charuco_a3_40mm()
    generate_chessboard_8x8_aruco_40mm()
