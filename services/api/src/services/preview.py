import cv2
import numpy as np
from datetime import datetime


class FrameGenerator:
    """Generates synthetic annotated frames with chicken conveyor and virtual line for preview."""

    @staticmethod
    def generate_jpeg_frame(line_id: str, frame_num: int = 0) -> bytes:
        safe_frame_num = max(0, frame_num)

        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img[:] = (30, 30, 40)  # dark background

        # Draw conveyor rail
        cv2.line(img, (50, 180), (590, 180), (120, 120, 120), 4)

        # Draw virtual counting line (green)
        cv2.line(img, (320, 100), (320, 400), (0, 220, 100), 2)
        cv2.putText(img, "COUNTING LINE", (260, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 100), 1)

        # Animated shackle / chicken moving across
        x_pos = int((safe_frame_num * 15) % 500 + 70)
        cv2.rectangle(img, (x_pos - 30, 190), (x_pos + 30, 310), (0, 180, 255), 2)
        cv2.putText(img, f"Chicken #{(safe_frame_num // 33) + 1} (98%)", (x_pos - 35, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 180, 255), 1)

        # HUD overlay
        ts_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(img, f"LIVE PREVIEW - {line_id.upper()} | {ts_str}", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        cv2.putText(img, "Status: ACTIVE | 120 cpm", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 255, 100), 1)

        _, encoded = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return encoded.tobytes()
