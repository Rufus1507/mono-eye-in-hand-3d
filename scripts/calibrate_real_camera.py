"""Script thực hiện Camera Calibration từ tập ảnh chụp thực tế của bảng ChArUco A4.

Xuất kết quả ra data/calib/camera.yaml và đánh giá sai số reprojection error.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys

import cv2
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mono_eye.camera_io import load_camera_yaml
from mono_eye.pose import PoseEstimator

DEFAULT_BOARD = ROOT / "bang_calib_A4.yaml"
DEFAULT_FRAMES_DIR = ROOT / "sessions" / "calib_real"
ALT_FRAMES_DIR = ROOT.parent / "frames"
DEFAULT_OUTPUT = ROOT / "data" / "calib" / "camera.yaml"
DEFAULT_BACKUP = ROOT / "data" / "calib" / "camera_generic_backup.yaml"


def load_board(board_path: Path):
    with open(board_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    dict_id = cv2.aruco.DICT_4X4_50
    aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
    board = cv2.aruco.CharucoBoard(
        (cfg["bang"]["o_ngang"], cfg["bang"]["o_doc"]),
        cfg["ban_in"]["canh_o_mm"],
        cfg["ban_in"]["marker_mm"],
        aruco_dict,
    )
    return board, cfg


def export_camera_yaml(output_path: Path, K: np.ndarray, D: np.ndarray, width: int, height: int, rms: float):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fs = cv2.FileStorage(str(output_path), cv2.FILE_STORAGE_WRITE)
    try:
        fs.write("image_width", int(width))
        fs.write("image_height", int(height))
        fs.write("camera_matrix", np.asarray(K, dtype=np.float64))
        fs.write("distortion_coefficients", np.asarray(D, dtype=np.float64).reshape(1, -1))
        fs.write("distortion_model", "opencv k1 k2 p1 p2 k3")
        fs.write("reprojection_error_px", float(rms))
        fs.write("calibration_date", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    finally:
        fs.release()


def run_calibration(
    frames_dir: Path,
    board_path: Path = DEFAULT_BOARD,
    output_path: Path = DEFAULT_OUTPUT,
    backup_path: Path = DEFAULT_BACKUP,
    min_corners: int = 12,
    fix_k3: bool = True,
):
    print("=" * 70)
    print("BẮT ĐẦU QUY TRÌNH CAMERA CALIBRATION TỪ ẢNH THỰC TẾ")
    print("=" * 70)

    if not frames_dir.exists():
        if ALT_FRAMES_DIR.exists():
            frames_dir = ALT_FRAMES_DIR
        else:
            raise FileNotFoundError(f"Không tìm thấy thư mục ảnh: {frames_dir}")

    print(f"Thư mục ảnh: {frames_dir}")
    print(f"Bảng ChArUco: {board_path}")
    print(f"File xuất: {output_path}")

    # Backup file cũ nếu có
    if output_path.is_file() and not backup_path.is_file():
        import shutil
        shutil.copy2(output_path, backup_path)
        print(f"[*] Đã sao lưu camera.yaml cũ sang: {backup_path}")

    board, cfg = load_board(board_path)
    detector = cv2.aruco.CharucoDetector(board)

    # Tìm các file ảnh PNG/JPG
    image_files = sorted(
        list(frames_dir.glob("*.png")) + list(frames_dir.glob("*.jpg")) + list(frames_dir.glob("*.jpeg"))
    )

    if not image_files:
        raise ValueError(f"Không tìm thấy file ảnh nào trong {frames_dir}")

    print(f"Tìm thấy tổng cộng {len(image_files)} ảnh.")

    all_obj_points = []
    all_img_points = []
    used_images = []
    image_size = None

    for idx, img_path in enumerate(image_files, 1):
        frame = cv2.imread(str(img_path))
        if frame is None:
            print(f"  [{idx:02d}/{len(image_files)}] Không thể đọc {img_path.name}")
            continue

        h, w = frame.shape[:2]
        if image_size is None:
            image_size = (w, h)
        elif image_size != (w, h):
            print(f"  [{idx:02d}/{len(image_files)}] {img_path.name}: Sai kích thước ({w}x{h} != {image_size}) -> Bỏ qua")
            continue

        corners, ids, _, _ = detector.detectBoard(frame)
        num_corners = len(corners) if corners is not None else 0

        if corners is not None and num_corners >= min_corners:
            op, ip = board.matchImagePoints(corners, ids)
            if op is not None and len(op) >= min_corners:
                all_obj_points.append(op)
                all_img_points.append(ip)
                used_images.append(img_path.name)
                print(f"  [{idx:02d}/{len(image_files)}] {img_path.name}: {num_corners} góc ChArUco -> HỢP LỆ")
            else:
                print(f"  [{idx:02d}/{len(image_files)}] {img_path.name}: Match điểm thất bại -> Bỏ qua")
        else:
            print(f"  [{idx:02d}/{len(image_files)}] {img_path.name}: Chỉ có {num_corners} góc (< {min_corners}) -> Bỏ qua")

    num_used = len(all_obj_points)
    print(f"\nTổng số ảnh đạt yêu cầu đưa vào calibration: {num_used} / {len(image_files)} ảnh.")
    if num_used < 10:
        raise ValueError(f"Cần tối thiểu 10 ảnh hợp lệ, hiện chỉ có {num_used} ảnh.")

    print("\nĐang tính toán ma trận Camera Intrinsic và Distortion Coefficients...")
    flags = cv2.CALIB_FIX_K3 if fix_k3 else 0

    rms, K, D, rvecs, tvecs, std_int, std_ext, per_view = cv2.calibrateCameraExtended(
        all_obj_points,
        all_img_points,
        image_size,
        None,
        None,
        flags=flags,
    )

    d_vec = D.ravel()
    k1, k2, p1, p2 = d_vec[0], d_vec[1], d_vec[2], d_vec[3]
    k3 = d_vec[4] if len(d_vec) > 4 else 0.0

    fx, fy = K[0, 0], K[1, 1]
    cx, cy = K[0, 2], K[1, 2]

    per_view_flat = per_view.ravel()
    mean_err = float(np.mean(per_view_flat))
    min_err = float(np.min(per_view_flat))
    max_err = float(np.max(per_view_flat))

    print("\n" + "=" * 70)
    print("KẾT QUẢ HIỆU CHUẨN CAMERA THỰC TẾ (REAL CAMERA CALIBRATION)")
    print("=" * 70)
    print(f"Số ảnh sử dụng:            {num_used} / {len(image_files)}")
    print(f"Độ phân giải hiệu chuẩn:   {image_size[0]} x {image_size[1]}")
    print(f"RMS Reprojection Error:    {rms:.4f} px (Mục tiêu < 1.5 px: {'ĐẠT (VƯỢT TRỘI)' if rms < 1.5 else 'KHÔNG ĐẠT'})")
    print(f"Mean Reprojection Error:   {mean_err:.4f} px")
    print(f"Min Reprojection Error:    {min_err:.4f} px")
    print(f"Max Reprojection Error:    {max_err:.4f} px")
    print("-" * 70)
    print("Ma trận Camera Intrinsic (K):")
    print(f"  fx = {fx:.2f} px")
    print(f"  fy = {fy:.2f} px")
    print(f"  cx = {cx:.2f} px")
    print(f"  cy = {cy:.2f} px")
    print(f"  Aspect ratio (fy/fx) = {fy/fx:.4f}")
    print("-" * 70)
    print("Hệ số méo quang học (Distortion Coefficients):")
    print(f"  k1 = {k1:.6f}")
    print(f"  k2 = {k2:.6f}")
    print(f"  p1 = {p1:.6f}")
    print(f"  p2 = {p2:.6f}")
    print(f"  k3 = {k3:.6f}")
    print("=" * 70)

    # Xuất ra file YAML
    export_camera_yaml(output_path, K, D, image_size[0], image_size[1], rms)
    print(f"\n[OK] Đã xuất cấu hình thành công: {output_path}")

    # Xác thực đọc lại bằng load_camera_yaml
    print("\nĐang xác thực nạp lại file bằng mono_eye.camera_io.load_camera_yaml...")
    cam_model = load_camera_yaml(output_path)
    assert cam_model.width == image_size[0]
    assert cam_model.height == image_size[1]
    assert np.allclose(cam_model.K, K)
    assert np.allclose(cam_model.dist, d_vec)
    print("[OK] Xác thực CameraModel hoàn tất. Không có lỗi định dạng!")

    # Thử nghiệm ước lượng Pose trên ảnh thực tế đầu tiên
    print("\nKiểm tra ước lượng Pose với PoseEstimator trên ảnh mẫu...")
    pose_est = PoseEstimator(camera=cam_model, board_config=board_path)
    sample_img = cv2.imread(str(frames_dir / used_images[0]))
    pose = pose_est.estimate(sample_img)
    print(f"Pose valid: {pose.valid}")
    print(f"Số góc phát hiện: {pose.num_corners}")
    print(f"Reprojection error ước lượng: {pose.reproj_error_px:.4f} px")
    if pose.valid:
        c = pose.camera_center
        print(f"Tâm camera 3D: X={c[0]:.1f}, Y={c[1]:.1f}, Z={c[2]:.1f} mm")

    print("\n" + "=" * 70)
    print("HIỆU CHUẨN CAMERA THỰC TẾ HOÀN TẤT THÀNH CÔNG!")
    print("=" * 70)

    return {
        "num_used": num_used,
        "total_images": len(image_files),
        "rms": rms,
        "mean_err": mean_err,
        "min_err": min_err,
        "max_err": max_err,
        "K": K,
        "D": d_vec,
        "fx": fx,
        "fy": fy,
        "cx": cx,
        "cy": cy,
        "k1": k1,
        "k2": k2,
        "p1": p1,
        "p2": p2,
        "k3": k3,
    }


def main():
    parser = argparse.ArgumentParser(description="Hiệu chuẩn camera thực tế từ ảnh ChArUco.")
    parser.add_argument("--frames-dir", type=Path, default=DEFAULT_FRAMES_DIR, help="Thư mục chứa ảnh frames.")
    parser.add_argument("--board", type=Path, default=DEFAULT_BOARD, help="File cấu hình bảng ChArUco.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="File xuất camera.yaml.")
    parser.add_argument("--allow-k3", action="store_true", help="Bật k3 trong mô hình méo.")
    args = parser.parse_args()

    run_calibration(
        frames_dir=args.frames_dir,
        board_path=args.board,
        output_path=args.output,
        fix_k3=not args.allow_k3,
    )


if __name__ == "__main__":
    main()
