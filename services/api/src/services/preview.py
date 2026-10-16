import os
import threading
from datetime import datetime
import cv2
import numpy as np


class FrameGenerator:
    """Generates preview frames from real video source (e.g. Rekaman_2.MOV) or synthetic fallback."""

    _lock = threading.Lock()
    _caps: dict[str, cv2.VideoCapture] = {}

    @classmethod
    def _resolve_video_path(cls) -> str | None:
        candidates = [
            os.getenv("VIDEO_PATH", ""),
            "/samples/Rekaman_2.MOV",
            "samples/Rekaman_2.MOV",
            "../samples/Rekaman_2.MOV",
        ]
        for path in candidates:
            if path and os.path.isfile(path):
                return path
        return None

    @classmethod
    def _get_capture(cls, video_path: str) -> cv2.VideoCapture:
        cap = cls._caps.get(video_path)
        if cap is None or not cap.isOpened():
            cap = cv2.VideoCapture(video_path)
            cls._caps[video_path] = cap
        return cap

    @classmethod
    def generate_jpeg_frame(cls, line_id: str, frame_num: int = 0) -> bytes:
        safe_frame_num = max(0, frame_num)
        video_path = cls._resolve_video_path()

        if video_path is not None:
            with cls._lock:
                cap = cls._get_capture(video_path)
                ret, frame = cap.read()
                if not ret:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()

            if ret and frame is not None:
                # Resize for responsive web preview (480, 640, 3) to match standard preview dimensions
                resized = cv2.resize(frame, (640, 480))

                # Virtual counting line (green vertical line)
                mid_x = 320
                cv2.line(resized, (mid_x, 70), (mid_x, 460), (0, 220, 100), 2)
                cv2.putText(
                    resized,
                    "COUNTING LINE (RIGHT)",
                    (mid_x - 90, 58),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (0, 220, 100),
                    1,
                )

                # Shackle line guide rail
                cv2.line(resized, (20, 115), (620, 115), (80, 180, 255), 1)

                # HUD overlay
                ts_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cv2.putText(
                    resized,
                    f"LIVE FEED - {line_id.upper()} | {ts_str}",
                    (20, 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.50,
                    (255, 255, 255),
                    1,
                )
                cv2.putText(
                    resized,
                    "Source: Rekaman_2.MOV | Overhead Shackle Line",
                    (20, 45),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.40,
                    (100, 255, 100),
                    1,
                )

                _, encoded = cv2.imencode(".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, 75])
                return encoded.tobytes()

        # Fallback synthetic frame if video file not available
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

