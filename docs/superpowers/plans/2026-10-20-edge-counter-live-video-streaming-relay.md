# Edge Counter Live Video Streaming Relay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement an on-demand, bandwidth-efficient live video streaming relay between edge counter instances and the cloud dashboard, allowing live camera feeds with chicken detection bounding boxes and counting lines to be viewed in real-time.

**Architecture:** The cloud Central API tracks active dashboard viewers on `GET /api/v1/lines/{line_id}/preview` and signals viewer presence to the edge counter during periodic sync telemetry (`POST /api/v1/sync/batch`). When a viewer is watching, the edge counter samples annotated frames at 3–5 FPS, compresses them to 640×480 JPEGs, and posts them via an asynchronous background uploader to `POST /api/v1/lines/{line_id}/frame`. The Central API caches the newest frame in memory and serves it to the web client via MJPEG, falling back to synthetic preview when no fresh frames are uploaded.

**Tech Stack:** Python 3.12+, FastAPI, OpenCV (`cv2`), `httpx`, NumPy, Pytest.

## Global Constraints

- **Frame Upload Route:** `POST /api/v1/lines/{line_id}/frame` authenticated with API Token (`require_role(["operator", "admin"])`).
- **Maximum Payload:** Maximum 1 MB (1,048,576 bytes) for uploaded frame JPEGs; status 413 if exceeded.
- **Image Validation:** Body must start with JPEG magic bytes (`b"\xff\xd8"`); status 400 if invalid.
- **Freshness Timeout:** In-memory frames older than 8.0 seconds expire and fall back to synthetic generation.
- **Viewer Timeout:** Viewer activity expires after 10.0 seconds of no preview polling/streaming.
- **Zero-Block Edge Inference:** Edge detection and counting pipeline must never block on network upload; uploader runs in a detached thread with a queue size of 1 (drops lagging frames).
- **Test Integrity:** All automated unit and API tests must pass cleanly (`pytest`).

---

### Task 1: Central API Viewer Presence Tracking & In-Memory Relay Buffer

**Files:**
- Modify: `services/api/src/services/preview.py`
- Modify: `services/api/src/api/live.py:187-225`
- Modify: `services/api/src/api/sync.py:146-153`
- Test: `services/api/tests/test_stream_relay_buffer.py`

**Interfaces:**
- Consumes: `services/api/src/services/preview.py`
- Produces:
  - `record_viewer_activity(line_id: str) -> None`
  - `is_stream_requested(line_id: str) -> bool`
  - `store_live_frame(line_id: str, frame_bytes: bytes) -> None`
  - `get_live_frame(line_id: str, max_age_sec: float = 8.0) -> bytes | None`
  - `clear_relay_buffer() -> None`
  - `FrameGenerator.generate_jpeg_frame(line_id: str, frame_num: int = 0) -> bytes` (prefers fresh live frame)
  - `sync_batch` response with `"stream_requested": bool`

- [ ] **Step 1: Write the failing test**

Create `services/api/tests/test_stream_relay_buffer.py`:
```python
import time
import pytest
from services.api.src.services.preview import (
    record_viewer_activity,
    is_stream_requested,
    store_live_frame,
    get_live_frame,
    clear_relay_buffer,
    FrameGenerator,
)


def test_viewer_activity_presence_and_expiration():
    clear_relay_buffer()
    assert is_stream_requested("line-1") is False

    record_viewer_activity("line-1")
    assert is_stream_requested("line-1") is True
    assert is_stream_requested("line-2") is False


def test_store_and_retrieve_live_frame():
    clear_relay_buffer()
    dummy_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 20 + b"\xff\xd9"
    store_live_frame("line-1", dummy_jpeg)

    retrieved = get_live_frame("line-1", max_age_sec=5.0)
    assert retrieved == dummy_jpeg
    assert get_live_frame("line-2") is None


def test_live_frame_expiration_falls_back_to_synthetic():
    clear_relay_buffer()
    dummy_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 20 + b"\xff\xd9"
    store_live_frame("line-1", dummy_jpeg)

    # Frame within freshness window
    frame = FrameGenerator.generate_jpeg_frame("line-1", 0)
    assert frame == dummy_jpeg

    # Frame beyond freshness window (0.001s max_age)
    time.sleep(0.01)
    expired = get_live_frame("line-1", max_age_sec=0.005)
    assert expired is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest services/api/tests/test_stream_relay_buffer.py -v`
Expected: FAIL with `ImportError: cannot import name 'record_viewer_activity'`

- [ ] **Step 3: Implement buffer and presence tracking**

In `services/api/src/services/preview.py`, add memory structures and helper functions:
```python
import os
import threading
import time
from datetime import datetime
import cv2
import numpy as np

# In-memory relay buffers:
# _active_viewers maps line_id -> timestamp (time.time())
# _latest_frames maps line_id -> (jpeg_bytes, timestamp)
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
```

In `services/api/src/services/preview.py`, update `FrameGenerator.generate_jpeg_frame`:
```python
    @classmethod
    def generate_jpeg_frame(cls, line_id: str, frame_num: int = 0) -> bytes:
        # Check if a fresh live frame from an edge counter is available
        live_frame = get_live_frame(line_id, max_age_sec=8.0)
        if live_frame is not None:
            return live_frame

        safe_frame_num = max(0, frame_num)
        video_path = cls._resolve_video_path()
        # [Remaining video file / synthetic fallback code unchanged]
```

In `services/api/src/api/live.py`:
Import `record_viewer_activity` and call it inside `preview_stream`:
```python
from services.api.src.services.preview import FrameGenerator, record_viewer_activity

# inside preview_stream:
    async def frame_stream():
        frame_idx = 0
        try:
            while True:
                if limit_frames is not None and frame_idx >= limit_frames:
                    break
                if await request.is_disconnected():
                    break
                record_viewer_activity(line_id)
                jpeg_bytes = await asyncio.to_thread(FrameGenerator.generate_jpeg_frame, line_id, frame_idx)
                # ...
```

In `services/api/src/api/sync.py`:
Import `is_stream_requested` from `services.api.src.services.preview` and include in `sync_batch` return value:
```python
    return {
        "status": "success",
        "line_id": payload.line_id,
        "ingested_events": ingested_events,
        "duplicates_skipped": duplicates_skipped,
        "ingested_aggregates": ingested_aggregates,
        "health_ingested": health_ingested,
        "stream_requested": is_stream_requested(payload.line_id),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest services/api/tests/test_stream_relay_buffer.py -v`
Expected: PASS (all 3 tests pass)

- [ ] **Step 5: Run full api tests suite**

Run: `py -m pytest services/api/tests/ -q`
Expected: PASS (200+ passed)

- [ ] **Step 6: Commit**

```bash
git add services/api/src/services/preview.py services/api/src/api/live.py services/api/src/api/sync.py services/api/tests/test_stream_relay_buffer.py
git commit -m "feat(api): add viewer presence tracking and in-memory frame relay buffer"
```

---

### Task 2: Central API Frame Ingestion Endpoint (`POST /api/v1/lines/{line_id}/frame`)

**Files:**
- Modify: `services/api/src/api/live.py`
- Test: `services/api/tests/test_frame_upload_api.py`

**Interfaces:**
- Consumes:
  - `store_live_frame` from `services/api/src/services/preview.py`
  - `require_role`, `get_current_user`, `UserDTO` from `services/api/src/api/auth.py`
- Produces:
  - `POST /api/v1/lines/{line_id}/frame` HTTP endpoint

- [ ] **Step 1: Write the failing test**

Create `services/api/tests/test_frame_upload_api.py`:
```python
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from services.api.src.main import app
from services.api.src.api.auth import create_access_token, UserDTO
from services.api.src.services.preview import clear_relay_buffer, get_live_frame


@pytest.fixture(autouse=True)
def clean_buffer():
    clear_relay_buffer()
    yield
    clear_relay_buffer()


def test_frame_upload_success_with_operator_token():
    token = create_access_token(data={"sub": "device:line-1", "role": "OPERATOR"})
    dummy_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 30 + b"\xff\xd9"

    with TestClient(app) as client:
        res = client.post(
            "/api/v1/lines/line-1/frame",
            content=dummy_jpeg,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "image/jpeg",
            },
        )
        assert res.status_code == 204
        # Verify frame is present in buffer
        stored = get_live_frame("line-1")
        assert stored == dummy_jpeg


def test_frame_upload_device_mismatched_line_forbidden():
    # Token issued for line-1, attempting to post to line-2
    token = create_access_token(data={"sub": "device:line-1", "role": "OPERATOR"})
    dummy_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 30 + b"\xff\xd9"

    with TestClient(app) as client:
        res = client.post(
            "/api/v1/lines/line-2/frame",
            content=dummy_jpeg,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 403
        assert "not authorized for this line" in res.json()["detail"].lower()


def test_frame_upload_admin_can_post_any_line():
    token = create_access_token(data={"sub": "admin", "role": "ADMIN"})
    dummy_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 30 + b"\xff\xd9"

    with TestClient(app) as client:
        res = client.post(
            "/api/v1/lines/line-99/frame",
            content=dummy_jpeg,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 204
        assert get_live_frame("line-99") == dummy_jpeg


def test_frame_upload_unauthorized():
    dummy_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 30 + b"\xff\xd9"
    with TestClient(app) as client:
        res = client.post("/api/v1/lines/line-1/frame", content=dummy_jpeg)
        assert res.status_code == 401


def test_frame_upload_payload_too_large():
    token = create_access_token(data={"sub": "device:line-1", "role": "OPERATOR"})
    oversized = b"\xff\xd8" + b"\x00" * (1024 * 1024 + 10)  # > 1 MB

    with TestClient(app) as client:
        res = client.post(
            "/api/v1/lines/line-1/frame",
            content=oversized,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 413


def test_frame_upload_invalid_non_jpeg():
    token = create_access_token(data={"sub": "device:line-1", "role": "OPERATOR"})
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50

    with TestClient(app) as client:
        res = client.post(
            "/api/v1/lines/line-1/frame",
            content=png_bytes,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 400
        assert "jpeg" in res.json()["detail"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest services/api/tests/test_frame_upload_api.py -v`
Expected: FAIL with 404 or 405 Method Not Allowed

- [ ] **Step 3: Implement endpoint in `services/api/src/api/live.py`**

Add the route to `services/api/src/api/live.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from services.api.src.api.auth import require_role, UserDTO
from services.api.src.services.preview import FrameGenerator, record_viewer_activity, store_live_frame

MAX_FRAME_SIZE_BYTES = 1024 * 1024  # 1 MB


@router.post("/{line_id}/frame", status_code=status.HTTP_204_NO_CONTENT)
async def upload_line_frame(
    line_id: str,
    request: Request,
    current_user: UserDTO = Depends(require_role(["operator", "admin"])),
):
    """Ingest a live JPEG frame from an authenticated edge counter."""
    line_slug = line_id.strip()
    if not line_slug:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid line_id")

    # If authenticated as a device token, ensure token corresponds to this line
    if current_user.role.lower() != "admin":
        device_prefix = "device:"
        if current_user.username.startswith(device_prefix):
            allowed_line = current_user.username[len(device_prefix):]
            if allowed_line != line_slug:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Token not authorized for this line (authorized: '{allowed_line}')",
                )

    body = await request.body()
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty frame body")

    if len(body) > MAX_FRAME_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Frame exceeds maximum size limit of {MAX_FRAME_SIZE_BYTES} bytes",
        )

    # Validate standard JPEG SOI magic bytes (0xFF, 0xD8)
    if len(body) < 4 or not body.startswith(b"\xff\xd8"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image format: must be JPEG (SOI marker missing)",
        )

    store_live_frame(line_slug, body)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest services/api/tests/test_frame_upload_api.py -v`
Expected: PASS (all 6 tests pass)

- [ ] **Step 5: Run full api tests suite**

Run: `py -m pytest services/api/tests/ -q`
Expected: PASS (200+ passed)

- [ ] **Step 6: Commit**

```bash
git add services/api/src/api/live.py services/api/tests/test_frame_upload_api.py
git commit -m "feat(api): add POST /lines/{line_id}/frame endpoint with role check and JPEG validation"
```

---

### Task 3: Edge Counter Stream Dispatcher & Async Frame Uploader

**Files:**
- Modify: `services/counter/src/sync/dispatcher.py`
- Create: `services/counter/src/sync/streamer.py`
- Test: `services/counter/tests/test_streamer.py`

**Interfaces:**
- Consumes:
  - `dispatcher.sync_once()` returning synced count and updating `stream_requested`
- Produces:
  - `dispatcher.stream_requested: bool`
  - `LiveStreamUploader(api_frame_url, api_token, target_fps, jpeg_quality, max_size)`
  - `uploader.submit_frame(frame: np.ndarray) -> bool`
  - `uploader.stop() -> None`

- [ ] **Step 1: Write the failing test**

Create `services/counter/tests/test_streamer.py`:
```python
import time
from unittest.mock import MagicMock, patch
import numpy as np
import pytest
from services.counter.src.sync.streamer import LiveStreamUploader
from services.counter.src.sync.dispatcher import OutboxSyncDispatcher


def test_sync_dispatcher_captures_stream_requested(tmp_path):
    from services.counter.src.storage.db import LocalStorage
    storage = LocalStorage(db_path=str(tmp_path / "sync.db"))
    storage.init_db()

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "success", "stream_requested": True}
    mock_client.post.return_value = mock_resp

    from shared.contracts import CountEventDTO
    from datetime import datetime, timezone
    storage.insert_event("lineA", CountEventDTO(track_id=1, ts_utc=datetime.now(timezone.utc), confidence=0.9))

    dispatcher = OutboxSyncDispatcher(
        storage=storage,
        api_url="http://mock-api/api/v1/sync/batch",
        line_id="lineA",
        http_client=mock_client,
    )
    assert dispatcher.stream_requested is False

    dispatcher.sync_once()
    assert dispatcher.stream_requested is True


def test_live_stream_uploader_submits_and_posts_jpeg():
    mock_client = MagicMock()
    mock_client.post.return_value.status_code = 204

    uploader = LiveStreamUploader(
        api_frame_url="http://mock-api/api/v1/lines/lineA/frame",
        api_token="cdc_live_test_token",
        target_fps=10.0,
        jpeg_quality=70,
        http_client=mock_client,
    )
    uploader.start()

    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    submitted = uploader.submit_frame(dummy_frame)
    assert submitted is True

    # Allow worker thread to pick up frame and send post
    time.sleep(0.1)
    uploader.stop()

    assert mock_client.post.call_count >= 1
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "http://mock-api/api/v1/lines/lineA/frame"
    assert call_args[1]["headers"]["Authorization"] == "Bearer cdc_live_test_token"
    assert call_args[1]["headers"]["Content-Type"] == "image/jpeg"
    body = call_args[1]["content"]
    assert body.startswith(b"\xff\xd8")  # Valid JPEG
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest services/counter/tests/test_streamer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.counter.src.sync.streamer'`

- [ ] **Step 3: Update `OutboxSyncDispatcher` and implement `LiveStreamUploader`**

In `services/counter/src/sync/dispatcher.py`:
In `__init__`, add:
```python
        self.stream_requested: bool = False
```
In `sync_once()`, when `resp.status_code in (200, 201)`:
```python
            if resp.status_code in (200, 201):
                try:
                    data = resp.json()
                    self.stream_requested = bool(data.get("stream_requested", False))
                except Exception:
                    pass
                if event_ids:
```

Create `services/counter/src/sync/streamer.py`:
```python
"""Asynchronous, non-blocking frame uploader for edge live video relay."""

import logging
import queue
import threading
import time
from typing import Any, Optional
import cv2
import httpx
import numpy as np

logger = logging.getLogger("counter.streamer")


class LiveStreamUploader:
    """Encodes and pushes live JPEG preview frames to the central API in a background thread."""

    def __init__(
        self,
        api_frame_url: str,
        api_token: Optional[str] = None,
        target_fps: float = 4.0,
        jpeg_quality: int = 75,
        max_dimensions: tuple[int, int] = (640, 480),
        http_client: Any = None,
        timeout: float = 3.0,
    ) -> None:
        self.api_frame_url = api_frame_url
        self.api_token = api_token
        self.target_fps = max(1.0, min(15.0, target_fps))
        self.min_frame_interval_sec = 1.0 / self.target_fps
        self.jpeg_quality = max(30, min(95, jpeg_quality))
        self.max_dimensions = max_dimensions
        self.timeout = timeout

        self._owns_client = http_client is None
        self.http_client = http_client if http_client is not None else httpx.Client()
        self._frame_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=1)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_submit_time: float = 0.0

    def start(self) -> None:
        """Start the background uploader thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="LiveStreamUploader",
        )
        self._thread.start()
        logger.info("LiveStreamUploader started (target %.1f FPS to %s)", self.target_fps, self.api_frame_url)

    def submit_frame(self, frame: np.ndarray) -> bool:
        """
        Submit a frame for upload. Drops the frame if the upload queue is currently full
        or if the minimum frame interval hasn't elapsed.
        """
        now = time.perf_counter()
        if now - self._last_submit_time < self.min_frame_interval_sec:
            return False

        if not isinstance(frame, np.ndarray) or frame.size == 0:
            return False

        try:
            # Drop older frame if present to always send freshest
            if self._frame_queue.full():
                try:
                    self._frame_queue.get_nowait()
                except queue.Empty:
                    pass
            self._frame_queue.put_nowait(frame.copy())
            self._last_submit_time = now
            return True
        except queue.Full:
            return False

    def _worker_loop(self) -> None:
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

                _, encoded = cv2.imencode(
                    ".jpg",
                    frame,
                    [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality],
                )
                jpeg_bytes = encoded.tobytes()

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
                    logger.debug("Frame upload responded with status %d", resp.status_code)
            except Exception as e:
                logger.debug("Failed to upload frame: %s", e)

    def stop(self) -> None:
        """Stop background worker thread."""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            self._thread = None
        if self._owns_client and hasattr(self.http_client, "close") and callable(self.http_client.close):
            try:
                self.http_client.close()
            except Exception:
                pass
        logger.info("LiveStreamUploader stopped")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest services/counter/tests/test_streamer.py -v`
Expected: PASS (all tests pass)

- [ ] **Step 5: Run existing counter sync test suite**

Run: `py -m pytest services/counter/tests/test_sync.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add services/counter/src/sync/dispatcher.py services/counter/src/sync/streamer.py services/counter/tests/test_streamer.py
git commit -m "feat(counter): add stream_requested tracking and LiveStreamUploader worker"
```

---

### Task 4: Counter Service Integration & End-to-End Pacing

**Files:**
- Modify: `services/counter/main.py`
- Test: `services/counter/tests/test_stream_integration.py`

**Interfaces:**
- Consumes:
  - `LiveStreamUploader` from `services.counter.src.sync.streamer`
  - `dispatcher.stream_requested` from `services.counter.src.sync.dispatcher`
- Produces:
  - `CounterService` with automated on-demand live video streaming relay
  - Configurable CLI parameters `--enable-stream-relay` and `--stream-fps`

- [ ] **Step 1: Write the failing test**

Create `services/counter/tests/test_stream_integration.py`:
```python
from unittest.mock import MagicMock, patch
import numpy as np
import pytest
from services.counter.main import CounterService
from services.counter.src.capture.source import SyntheticVideoSource
from services.counter.src.detection.detector import MockDetector
from services.counter.src.storage.db import LocalStorage
from services.counter.src.sync.dispatcher import OutboxSyncDispatcher


def test_counter_service_initializes_stream_uploader(tmp_path):
    storage = LocalStorage(db_path=str(tmp_path / "sync.db"))
    storage.init_db()

    mock_client = MagicMock()
    dispatcher = OutboxSyncDispatcher(
        storage=storage,
        api_url="http://mock-api/api/v1/sync/batch",
        line_id="line-1",
        http_client=mock_client,
    )

    with patch("services.counter.main.LiveStreamUploader") as mock_uploader_cls:
        mock_uploader = MagicMock()
        mock_uploader_cls.return_value = mock_uploader

        service = CounterService(
            line_id="line-1",
            api_sync_url="http://mock-api/api/v1/sync/batch",
            api_token="test_token",
            storage=storage,
            dispatcher=dispatcher,
            source=SyntheticVideoSource(width=640, height=480, fps=30.0),
            detector=MockDetector(),
            enable_sync=False,
            cli_display=False,
        )

        mock_uploader_cls.assert_called_once()
        uploader_call_kwargs = mock_uploader_cls.call_args[1]
        assert uploader_call_kwargs["api_frame_url"] == "http://mock-api/api/v1/lines/line-1/frame"
        assert uploader_call_kwargs["api_token"] == "test_token"


def test_counter_service_submits_frames_when_stream_requested(tmp_path):
    storage = LocalStorage(db_path=str(tmp_path / "sync.db"))
    storage.init_db()

    mock_client = MagicMock()
    dispatcher = OutboxSyncDispatcher(
        storage=storage,
        api_url="http://mock-api/api/v1/sync/batch",
        line_id="line-1",
        http_client=mock_client,
    )
    # Simulate active viewer watching dashboard
    dispatcher.stream_requested = True

    with patch("services.counter.main.LiveStreamUploader") as mock_uploader_cls:
        mock_uploader = MagicMock()
        mock_uploader_cls.return_value = mock_uploader

        service = CounterService(
            line_id="line-1",
            api_sync_url="http://mock-api/api/v1/sync/batch",
            api_token="test_token",
            storage=storage,
            dispatcher=dispatcher,
            source=SyntheticVideoSource(width=640, height=480, fps=30.0),
            detector=MockDetector(),
            enable_sync=False,
            cli_display=False,
        )

        # Run 5 frames
        service.run(max_frames=5)
        service.stop()

        # Uploader should have been started and received submit_frame calls
        mock_uploader.start.assert_called_once()
        assert mock_uploader.submit_frame.call_count >= 1
        mock_uploader.stop.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest services/counter/tests/test_stream_integration.py -v`
Expected: FAIL with `AssertionError: Expected 'LiveStreamUploader' to be called once. Called 0 times.`

- [ ] **Step 3: Integrate `LiveStreamUploader` in `services/counter/main.py`**

In `services/counter/main.py`:
Import `LiveStreamUploader`:
```python
try:
    from src.sync.streamer import LiveStreamUploader
except ImportError:
    try:
        from services.counter.src.sync.streamer import LiveStreamUploader
    except ImportError:
        LiveStreamUploader = None
```

In `CounterService.__init__`:
Add parameters:
```python
        enable_stream_relay: bool = True,
        stream_fps: float = 4.0,
```
Derive frame URL and initialize uploader:
```python
        self.enable_stream_relay = enable_stream_relay
        self.stream_fps = stream_fps
        self.stream_uploader: Optional[Any] = None

        if self.enable_stream_relay and LiveStreamUploader is not None:
            # Construct frame URL from api_sync_url:
            # e.g. http://host:8000/api/v1/sync/batch -> http://host:8000/api/v1/lines/{line_id}/frame
            base_api = self.api_sync_url.split("/api/v1")[0] if "/api/v1" in self.api_sync_url else "http://localhost:8000"
            api_frame_url = f"{base_api}/api/v1/lines/{self.line_id}/frame"
            self.stream_uploader = LiveStreamUploader(
                api_frame_url=api_frame_url,
                api_token=self.api_token,
                target_fps=self.stream_fps,
            )
```

Extract reusable annotation rendering method:
```python
    def render_annotated_frame(
        self, frame: object, detections: list, events: list
    ) -> Optional[np.ndarray]:
        """Render detection boxes, tracking anchors, virtual line, and HUD overlay onto frame."""
        # [Existing annotation logic from _render_window_frame returned as vis]
```
Have `_render_window_frame` call `self.render_annotated_frame(frame, detections, events)` and display via OpenCV window.

In `run()`:
Start uploader if initialized:
```python
        if self.stream_uploader is not None:
            self.stream_uploader.start()
```
Inside the frame loop after tracking/counting:
```python
                # On-demand live stream frame submission to cloud relay
                if self.stream_uploader is not None and getattr(self.dispatcher, "stream_requested", False):
                    vis_frame = self.render_annotated_frame(frame, detections, events)
                    if vis_frame is not None:
                        self.stream_uploader.submit_frame(vis_frame)
```
In `stop()`:
```python
        if self.stream_uploader is not None:
            self.stream_uploader.stop()
```

In `build_arg_parser()` / CLI arguments:
Add `--enable-stream-relay` (default true or from env `ENABLE_STREAM_RELAY`) and `--stream-fps` (default 4.0 or from env `STREAM_FPS`).

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest services/counter/tests/test_stream_integration.py -v`
Expected: PASS (all tests pass)

- [ ] **Step 5: Run all counter test suites**

Run: `py -m pytest services/counter/tests/ -q`
Expected: PASS (all counter tests pass)

- [ ] **Step 6: Commit**

```bash
git add services/counter/main.py services/counter/tests/test_stream_integration.py
git commit -m "feat(counter): integrate on-demand live video streaming relay into main loop"
```

---

## Plan Review & Verification Checklist

1. **Spec Coverage:**
   - Viewer presence tracking on `/preview`: Covered in Task 1.
   - Dynamic signaling via `/sync/batch` response: Covered in Task 1 & Task 3.
   - Secure frame upload endpoint `POST /lines/{line_id}/frame`: Covered in Task 2.
   - Non-blocking async frame uploader with 1-slot buffer: Covered in Task 3.
   - Pipeline integration with bounding box annotations: Covered in Task 4.
2. **Backward Compatibility:**
   - When no viewer is active, zero frames are encoded or sent (0% overhead).
   - When central API has no fresh frame (<8s), it transparently falls back to synthetic preview without failing.
3. **Execution Commands:**
   - Full API tests: `py -m pytest services/api/tests/`
   - Full Counter tests: `py -m pytest services/counter/tests/`
   - Frontend build: `npm --prefix frontend run build`
