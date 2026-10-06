"""Synthetic test cho mono_eye modules.
Không cần camera thật, tạo synthetic frames để test.
"""
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def create_synthetic_charuco_board(width: int = 1280, height: int = 720) -> np.ndarray:
    """Tạo synthetic ChArUco board image để test."""
    img = np.ones((height, width, 3), dtype=np.uint8) * 200
    return img


def test_board_generation() -> bool:
    """Test board generation."""
    try:
        from fov_tool.board import load_board
        board_path = ROOT / "bang_calib_A4.yaml"
        spec, board, detector = load_board(board_path)

        # Tạo ảnh bảng ChArUco
        img = board.generateImage((1280, 720))

        print(f"✅ Board generated: {img.shape}")
        return True
    except Exception as e:
        print(f"❌ Board generation failed: {e}")
        return False


if __name__ == "__main__":
    print("=== Synthetic Test ===")
    test_board_generation()
