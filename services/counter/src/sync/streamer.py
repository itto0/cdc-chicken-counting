"""Asynchronous live video frame streamer and compressor for edge counter."""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Any

import cv2
import httpx
import numpy as np

logger = logging.getLogger("counter.streamer")


class LiveStreamUploader:
    """
    Asynchronous, non-blocking frame compressor and uploader.

    Transmits live camera JPEG frames to backend API relay when viewers are present
    without blocking or stalling the core detection/counting pipeline.
    """

    def __init__(
        self,
        api_frame_url: str,
        api_token: str | None = None,
        target_fps: float = 4.0,
        jpeg_quality: int = 75,
        max_dimensions: tuple[int, int] = (640, 480),
        http_client: Any = None,
        timeout: float = 3.0,
    ) -> None:
        self.api_frame_url = api_frame_url
        self.api_token = api_token
        self.target_fps = max(1.0, min(15.0, float(target_fps)))
        self.jpeg_quality = max(30, min(95, int(jpeg_quality)))
        self.max_dimensions = max_dimensions
        self.timeout = float(timeout)

        self._owns_client = http_client is None
        self.http_client = http_client if http_client is not None else httpx.Client()

        self._frame_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=1)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_submit_time: float = 0.0
        self.min_frame_interval_sec: float = 1.0 / self.target_fps

    def start(self) -> None:
        """Start background daemon thread target _worker_loop. Idempotent if already started."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._worker_loop,
            name="LiveStreamUploaderWorker",
            daemon=True,
        )
        self._thread.start()

    def submit_frame(self, frame: np.ndarray) -> bool:
        """
        Submit a new camera frame for asynchronous compression and upload.

        Pacing is checked against target FPS, and old unread frames are dropped
        so the live camera feed is never lagged.

        Returns:
            True if the frame was accepted and queued.
            False if discarded due to pacing (rate limiting) or invalid frame.
        """
        if not isinstance(frame, np.ndarray) or frame.size == 0 or frame.ndim < 2:
            return False

        now = time.time()
        if (now - self._last_submit_time) < self.min_frame_interval_sec:
            return False

        if self._frame_queue.full():
            try:
                self._frame_queue.get_nowait()
            except queue.Empty:
                pass

        try:
            self._frame_queue.put_nowait(frame.copy())
        except queue.Full:
            try:
                self._frame_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._frame_queue.put_nowait(frame.copy())
            except queue.Full:
                pass

        self._last_submit_time = now
        return True

    def _worker_loop(self) -> None:
        """Worker thread loop consuming frames, resizing, compressing to JPEG, and posting."""
        while not self._stop_event.is_set():
            try:
                frame = self._frame_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                h, w = frame.shape[:2]
                max_w, max_h = self.max_dimensions
                if w != max_w or h != max_h:
                    frame = cv2.resize(frame, (max_w, max_h))

                encode_success, buffer = cv2.imencode(
                    ".jpg",
                    frame,
                    [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality],
                )
                if not encode_success:
                    logger.debug("Failed to encode live stream frame to JPEG")
                    continue

                jpeg_bytes = buffer.tobytes()

                headers = {"Content-Type": "image/jpeg"}
                if self.api_token and self.api_token.strip():
                    headers["Authorization"] = f"Bearer {self.api_token.strip()}"

                resp = self.http_client.post(
                    self.api_frame_url,
                    content=jpeg_bytes,
                    headers=headers,
                    timeout=self.timeout,
                )
                if resp.status_code not in (200, 204):
                    logger.debug(
                        "Live stream frame upload responded with status %s",
                        resp.status_code,
                    )
            except Exception as exc:
                logger.debug("Live stream frame upload encountered error: %s", exc)

    def stop(self) -> None:
        """Signal worker thread to stop, join it, and close owned HTTP client."""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            self._thread = None
        if self._owns_client and self.http_client is not None:
            if hasattr(self.http_client, "close") and callable(self.http_client.close):
                try:
                    self.http_client.close()
                except Exception:
                    pass

    def __enter__(self) -> "LiveStreamUploader":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()
