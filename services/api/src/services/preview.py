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

