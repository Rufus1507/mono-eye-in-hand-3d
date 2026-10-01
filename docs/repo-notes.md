# Repo tham khảo

| Repo | Vai trò | Lấy gì | Không lấy gì |
|---|---|---|---|
| camera-fov-charuco (repo này, MIT, tác giả gốc HuyLeSmartTech) | Nền: bảng, tự chụp, hiệu chuẩn, xuất camera.yaml | Toàn bộ phần hiệu chuẩn; `fov_tool.board`, `fov_tool.observations` dùng lại cho pose | Cờ `validated` luôn false: độ đúng phải tự kiểm bằng điểm chuẩn |
| [tony2guo/charuco-pose-estimation](https://github.com/tony2guo/charuco-pose-estimation) | Chỉ đọc | Luồng ước lượng pose | Code có thể dùng API ArUco cũ |
| [ftPeter/pose-estimation](https://github.com/ftPeter/pose-estimation) | Chỉ đọc | Quy trình in, đo, hiệu chuẩn | |
| [Paul-Rohit/ArUcoTrackerArena](https://github.com/Paul-Rohit/ArUcoTrackerArena) | Chỉ đọc | Ý tưởng giao tia với mặt phẳng, script đo sai số | |
| [Lumeon-Labs/vision-positioning-demo](https://github.com/Lumeon-Labs/vision-positioning-demo) | Chỉ đọc | Luồng webcam, pose, tọa độ | Phần điều khiển robot |

Lưu ý
- Dùng API OpenCV mới (`CharucoDetector`), không dùng `interpolateCornersCharuco` / `estimatePoseCharucoBoard`.
- Kiểm tra giấy phép trước khi chép code từ repo khác; nếu không chắc thì chỉ đọc rồi tự viết.
- Giữ nguyên `LICENSE` gốc (MIT, yêu cầu giữ thông báo bản quyền); bạn có thể thêm dòng bản quyền của mình bên dưới.
