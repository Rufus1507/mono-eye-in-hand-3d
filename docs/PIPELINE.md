# Pipeline Hoạt Động Của Dự Án

Tài liệu chi tiết về pipeline hoạt động của hệ thống Mono Eye-in-Hand 3D Localization được lưu trữ chính thức tại:

👉 [**`PIPELINE.md` (Thư mục gốc)**](../PIPELINE.md)

Nội dung bao gồm:
1. Tổng quan kiến trúc Pipeline & Sơ đồ luồng (Flowchart Mermaid)
2. Giai đoạn 1: Chuẩn bị vật lý & Thang đo thực tế (`mono_eye/board_scale.py`)
3. Giai đoạn 2: Pipeline hiệu chuẩn máy ảnh (`fov_tool` Auto-Capture & Bootstrap)
4. Giai đoạn 3: Ước lượng tư thế Camera thời gian thực (`solvePnP`, Rodrigues, World Frame)
5. Giai đoạn 4: Nhận diện đối tượng & Điểm mốc tiếp xúc đáy (Bottom-Center Reference Pixel)
6. Giai đoạn 5: Chiếu tia không gian Monocular 3D (Ray-Plane Intersection)
7. Giai đoạn 6: Lọc nhiễu động học, Temporal Smoothing & Kalman Filter
8. Giai đoạn 7: Trực quan hóa 2D / 3D Digital Twin & Xuất dữ liệu
9. Hai biến thể Pipeline: General Object (`MonoEyePipeline`) & Cờ vua (`ChessMonoEyePipeline`)
10. Bảng cấu hình tham số, Cổng kiểm soát chất lượng & Ánh xạ mã nguồn chi tiết
