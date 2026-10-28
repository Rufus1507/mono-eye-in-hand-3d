# Tài Liệu Kỹ Thuật: Standalone 3D Chess Studio Viewer (PBR + ModernGL)

## 1. Giới thiệu tổng quan
Module `mono_eye.viewer3d` là hệ thống hiển thị và kết xuất 3D bàn cờ vua chất lượng cao thời gian thực được xây dựng nhằm thay thế khung nhìn 2.5D wireframe phẳng cũ bằng mô hình 3D thực thụ với vật liệu PBR (Physically-Based Rendering), ánh sáng studio và tận dụng sức mạnh GPU (NVIDIA RTX 3060).

---

## 2. Kiến trúc Module (`mono_eye/viewer3d/`)

| Module | Chức năng chính |
|---|---|
| `paths.py` | Quản lý đường dẫn tập trung (`gender_3d/`, textures, cache) và resolve path đa nền tảng |
| `mtl.py` | Bộ phân tích cú pháp file `.mtl` và kiểm tra toàn vẹn đường dẫn texture |
| `obj_loader.py` | Parser OBJ tối ưu đọc file 56MB trong ~4 giây, tự động triangulate và lưu đệm `.npz` để nạp trong **0.07 giây** (Cache Hit) |
| `semantics.py` | Nhận diện ngữ nghĩa hình học bàn cờ 8x8, loại bỏ vật thể rác ngoài cảnh (`Cylinder_Cylinder.003`), tính toán tọa độ tâm ô |
| `materials.py` | Bảng vật liệu PBR chuẩn Metal-Roughness: Đá cẩm thạch `Marble020` cho bàn cờ và Vân gỗ `Wood062` cho quân cờ trắng (`bayaz_`) & quân cờ đen (`siyah`) |
| `shaders.py` | Mã nguồn GLSL 330: Cook-Torrance GGX BRDF, Screen-Space Derivative Normal Mapping, Studio 3-point lighting, ACES Filmic Tone Mapping |
| `camera.py` | OrbitCamera & OrbitController: Xoay 360°, Phóng to / Thu nhỏ (Dolly Zoom), Di chuyển mặt phẳng (Pan) |
| `renderer.py` | Chess3DRenderer ModernGL: Quản lý VBO/IBO/VAO, bind textures theo sampler units, kết xuất đa pass |
| `app.py` | ViewerApp GLFW: Cửa sổ tương tác 60+ FPS và hỗ trợ chụp ảnh màn hình / headless render |
| `scene_api.py` | `Chess3DScene`: Lớp API trung gian sẵn sàng nhận pose camera, tọa độ milimet thực tế hoặc nước đi cờ vua |

---

## 3. Hướng dẫn sử dụng CLI

Khởi chạy ứng dụng hiển thị tương tác:
```powershell
python scripts/chess_viewer3d.py
```

### Phím tắt điều khiển:
- **Chuột trái kéo:** Xoay tự do xung quanh bàn cờ (Orbit 360°).
- **Con lăn chuột:** Phóng to / thu nhỏ góc nhìn mượt mà (Dolly Zoom).
- **Chuột phải kéo (hoặc Shift + Chuột trái):** Di chuyển tâm nhìn sang ngang / lên xuống (Pan).
- **Phím `R` / `r`:** Đặt lại góc nhìn mặc định (Reset Camera).
- **Phím `S` / `s`:** Chụp ảnh màn hình độ phân giải cao lưu trực tiếp vào thư mục `outputs/`.
- **Phím `ESC`:** Thoát chương trình.

### Chế độ Headless (Chụp ảnh tự động không cần mở cửa sổ):
```powershell
python scripts/chess_viewer3d.py --headless-frames 5 --screenshot-out outputs/viewer_final.png
```

---

## 4. Hướng dẫn tích hợp vào Video Pipeline (`realtime_chess_viz.py`)

Khi cần tích hợp kết quả nhận diện quân cờ từ camera thực tế vào 3D Scene:
```python
from mono_eye.viewer3d.scene_api import Chess3DScene

# 1. Khởi tạo scene 3D
scene = Chess3DScene()

# 2. Cập nhật vị trí quân cờ từ tên ô cờ FEN (ví dụ: phát hiện quân vua ở e4)
scene.set_piece_square("white_king", "e4")

# 3. Hoặc cập nhật trực tiếp từ tọa độ 3D milimet đo được bởi camera:
scene.set_piece_position_mm("white_knight_1", x_mm=120.5, y_mm=0.0, z_mm=45.2)

# 4. Lấy ma trận transforms của các quân cờ để nạp vào renderer
transforms = scene.piece_transforms()
```
