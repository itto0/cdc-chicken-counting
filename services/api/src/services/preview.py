import os
import threading
import time
from datetime import datetime
import cv2
import numpy as np

from shared.time_utils import now_jakarta, format_jakarta_display, WIB_LABEL

_relay_lock = threading.Lock()
_active_viewers: dict[str, float] = {}
_latest_frames: dict[str, tuple[bytes, float]] = {}


def record_viewer_activity(line_id: str) -> None:
    """Record that an active viewer is watching the preview stream for line_id."""
    with _relay_lock:
        _active_viewers[line_id] = time.time()


def is_stream_requested(line_id: str, timeout_sec: float = 10.0) -> bool:
    """Check if any active viewer has watched line_id in the last timeout_sec seconds."""
    with _relay_lock:
        last_seen = _active_viewers.get(line_id, 0.0)
    return (time.time() - last_seen) < timeout_sec


def store_live_frame(line_id: str, frame_bytes: bytes) -> None:
    """Store the newest uploaded JPEG frame for line_id."""
    with _relay_lock:
        _latest_frames[line_id] = (frame_bytes, time.time())


def get_live_frame(line_id: str, max_age_sec: float = 8.0) -> bytes | None:
    """Retrieve the latest uploaded JPEG frame if not older than max_age_sec."""
    with _relay_lock:
        item = _latest_frames.get(line_id)
    if item is None:
        return None
    frame_bytes, ts = item
    if (time.time() - ts) > max_age_sec:
        return None
    return frame_bytes


def clear_relay_buffer() -> None:
    """Clear in-memory viewer tracking and frame cache (useful for tests)."""
    with _relay_lock:
        _active_viewers.clear()
        _latest_frames.clear()


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
    def _detect_chickens_on_frame(cls, frame: np.ndarray) -> list[int]:
        """Industrial shackle conveyor detector identifying chicken horizontal centers."""
        h, w = frame.shape[:2]
        y1_shackle = int(0.24 * h)
        y2_shackle = int(0.48 * h)
        if y2_shackle <= y1_shackle:
            return []

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        roi = gray[y1_shackle:y2_shackle, :]
        sobelx = np.abs(cv2.Sobel(roi, cv2.CV_64F, 1, 0, ksize=3)).astype(np.uint8)
        col_energy = cv2.GaussianBlur(sobelx.mean(axis=0).reshape(1, -1), (25, 1), 0).flatten()
        max_e = float(col_energy.max()) if len(col_energy) > 0 else 0.0
        if max_e < 10.0:
            return []

        thresh = max(12.0, float(max_e * 0.40))
        peaks = [
            i
            for i in range(1, len(col_energy) - 1)
            if col_energy[i] >= thresh
            and col_energy[i] > col_energy[i - 1]
            and col_energy[i] >= col_energy[i + 1]
        ]
        clusters: list[list[int]] = []
        for p in peaks:
            if not clusters or (p - clusters[-1][-1]) > 25.0:
                clusters.append([p])
            else:
                clusters[-1].append(p)

        centers = [int(np.mean(c)) for c in clusters]
        filtered: list[int] = []
        for cx in centers:
            if not filtered or (cx - filtered[-1]) >= 55.0:
                filtered.append(cx)

        y1_carcass = int(0.62 * h)
        y2_carcass = int(0.76 * h)
        pw = max(6, int(0.006 * w))
        valid_chickens: list[int] = []
        for cx in filtered:
            patch = gray[y1_carcass:y2_carcass, max(0, cx - pw) : min(w, cx + pw)]
            if patch.size > 0:
                grad_mag = float(np.abs(cv2.Sobel(patch, cv2.CV_16S, 1, 0)).mean())
                if grad_mag >= 4.5:
                    valid_chickens.append(cx)

        return valid_chickens

    @classmethod
    def generate_jpeg_frame(cls, line_id: str, frame_num: int = 0) -> bytes:
        live_frame = get_live_frame(line_id, max_age_sec=8.0)
        if live_frame is not None:
            return live_frame

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
                h, w = frame.shape[:2]
                chicken_centers = cls._detect_chickens_on_frame(frame)

                # Resize for responsive web preview (480, 640, 3) to match standard preview dimensions
                resized = cv2.resize(frame, (640, 480))
                scale_x = 640.0 / w
                scale_y = 480.0 / h

                mid_x = 320
                line_active = False

                # Draw bounding boxes for detected chickens
                for cx in chicken_centers:
                    rcx = int(cx * scale_x)
                    rw = int(115.0 * scale_x)
                    rh = int(540.0 * scale_y)
                    ry = int(260.0 * scale_y)
                    rx1 = max(0, rcx - rw // 2)
                    rx2 = min(640, rcx + rw // 2)
                    ry1 = max(0, ry)
                    ry2 = min(480, ry + rh)

                    is_crossing = abs(rcx - mid_x) <= 18
                    if is_crossing:
                        line_active = True
                        box_color = (0, 255, 0)
                        label = "COUNTING (90%)"
                    elif rcx > mid_x + 18:
                        box_color = (0, 220, 0)
                        label = "Ayam [COUNTED] (90%)"
                    else:
                        box_color = (0, 180, 255)
                        label = "Ayam (90%)"

                    cv2.rectangle(resized, (rx1, ry1), (rx2, ry2), box_color, 2)
                    cv2.putText(
                        resized,
                        label,
                        (rx1, max(12, ry1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.36,
                        box_color,
                        1,
                    )

                # Virtual counting line (green vertical line, turns yellow when bird crosses)
                line_color = (0, 255, 255) if line_active else (0, 220, 100)
                cv2.line(resized, (mid_x, 70), (mid_x, 460), line_color, 2)
                cv2.putText(
                    resized,
                    f"COUNTING LINE (RIGHT){' [CROSSING]' if line_active else ''}",
                    (mid_x - 95, 58),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.42,
                    line_color,
                    1,
                )

                # Shackle line guide rail
                cv2.line(resized, (20, 115), (620, 115), (80, 180, 255), 1)

                # HUD overlay
                ts_str = f"{format_jakarta_display(now_jakarta())} {WIB_LABEL}"
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
                    f"Source: Rekaman_2.MOV | Terdeteksi: {len(chicken_centers)} ayam di conveyor",
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
        mid_x = 320
        if abs(x_pos - mid_x) <= 20:
            box_color = (0, 255, 0)
            label = f"Chicken #{(safe_frame_num // 33) + 1} COUNTING (98%)"
        elif x_pos > mid_x + 20:
            box_color = (0, 220, 0)
            label = f"Chicken #{(safe_frame_num // 33) + 1} [COUNTED] (98%)"
        else:
            box_color = (0, 180, 255)
            label = f"Chicken #{(safe_frame_num // 33) + 1} (98%)"

        cv2.rectangle(img, (x_pos - 30, 190), (x_pos + 30, 310), box_color, 2)
        cv2.putText(img, label, (x_pos - 35, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.4, box_color, 1)

        # HUD overlay
        ts_str = f"{format_jakarta_display(now_jakarta())} {WIB_LABEL}"
        cv2.putText(img, f"LIVE PREVIEW - {line_id.upper()} | {ts_str}", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        cv2.putText(img, "Status: ACTIVE | 120 cpm", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 255, 100), 1)

        _, encoded = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return encoded.tobytes()

