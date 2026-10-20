"""Tests for live stream uploader and dispatcher stream request tracking."""

from datetime import datetime, timezone
import queue
import time
from unittest.mock import MagicMock

import cv2
import httpx
import numpy as np
import pytest

from shared.contracts import CountEventDTO
from services.counter.src.storage.db import LocalStorage
from services.counter.src.sync.dispatcher import OutboxSyncDispatcher
from services.counter.src.sync.streamer import LiveStreamUploader


def test_sync_dispatcher_captures_stream_requested(tmp_path):
    """Verify OutboxSyncDispatcher captures and exposes stream_requested from API responses."""
    storage = LocalStorage(db_path=str(tmp_path / "sync.db"))
    storage.init_db()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "success",
        "stream_requested": True,
    }

    mock_http_client = MagicMock()
    mock_http_client.post.return_value = mock_resp

    dispatcher = OutboxSyncDispatcher(
        storage=storage,
        api_url="http://mock-api/api/v1/sync/batch",
        line_id="lineA",
        http_client=mock_http_client,
    )

    # Initial state should be False
    assert dispatcher.stream_requested is False

    # Insert event to trigger outbox sync
    storage.insert_event(
        "lineA",
        CountEventDTO(
            track_id=1,
            ts_utc=datetime.now(timezone.utc),
            confidence=0.9,
        ),
    )

    synced = dispatcher.sync_once()
    assert synced == 1
    assert dispatcher.stream_requested is True

    # Next sync with stream_requested = False
    mock_resp.json.return_value = {
        "status": "success",
        "stream_requested": False,
    }
    storage.insert_event(
        "lineA",
        CountEventDTO(
            track_id=2,
            ts_utc=datetime.now(timezone.utc),
            confidence=0.85,
        ),
    )

    synced = dispatcher.sync_once()
    assert synced == 1
    assert dispatcher.stream_requested is False

    # Gracefully handle non-dict or invalid JSON without exception
    mock_resp.json.side_effect = ValueError("Invalid JSON payload")
    storage.insert_event(
        "lineA",
        CountEventDTO(
            track_id=3,
            ts_utc=datetime.now(timezone.utc),
            confidence=0.92,
        ),
    )

    synced = dispatcher.sync_once()
    assert synced == 1
    # stream_requested stays at previous state
    assert dispatcher.stream_requested is False


def test_live_stream_uploader_submits_and_posts_jpeg():
    """Verify JPEG encoding, headers (Bearer token & image/jpeg), target URL, and background HTTP POST."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    mock_http_client = MagicMock()
    mock_http_client.post.return_value = mock_resp

    target_url = "http://mock-api/api/v1/lines/line1/frame"
    uploader = LiveStreamUploader(
        api_frame_url=target_url,
        api_token="test-secret-token",
        target_fps=10.0,
        jpeg_quality=80,
        http_client=mock_http_client,
        timeout=2.5,
    )

    uploader.start()
    try:
        frame = np.full((480, 640, 3), 120, dtype=np.uint8)
        accepted = uploader.submit_frame(frame)
        assert accepted is True

        # Wait up to 2 seconds for worker to process and post
        deadline = time.time() + 2.0
        while not mock_http_client.post.called and time.time() < deadline:
            time.sleep(0.02)

        assert mock_http_client.post.called, "Worker failed to make HTTP POST call"

        call_args, call_kwargs = mock_http_client.post.call_args
        assert call_args[0] == target_url
        assert call_kwargs["timeout"] == 2.5
        assert call_kwargs["headers"] == {
            "Content-Type": "image/jpeg",
            "Authorization": "Bearer test-secret-token",
        }

        # Verify content is valid JPEG payload
        content = call_kwargs["content"]
        assert isinstance(content, bytes)
        assert len(content) > 0
        assert content[:2] == b"\xff\xd8", "Payload does not start with JPEG SOI marker"

        decoded = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_COLOR)
        assert decoded is not None
        assert decoded.shape == (480, 640, 3)
    finally:
        uploader.stop()


def test_live_stream_uploader_rate_limiting(monkeypatch):
    """Verify submit_frame returns False when called faster than 1 / target_fps."""
    current_time = 1000.0
    monkeypatch.setattr(time, "time", lambda: current_time)

    mock_http_client = MagicMock()
    uploader = LiveStreamUploader(
        api_frame_url="http://mock-api/frame",
        target_fps=4.0,  # min interval = 0.25s
        http_client=mock_http_client,
    )

    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # First call succeeds
    assert uploader.submit_frame(frame) is True

    # Immediately afterwards (0.05s elapsed < 0.25s) -> False
    current_time += 0.05
    assert uploader.submit_frame(frame) is False

    # Still before interval (0.20s elapsed < 0.25s) -> False
    current_time += 0.15
    assert uploader.submit_frame(frame) is False

    # After interval (0.26s elapsed >= 0.25s) -> True
    current_time += 0.06
    assert uploader.submit_frame(frame) is True

    # Immediate call again -> False
    current_time += 0.01
    assert uploader.submit_frame(frame) is False

    # Another full interval -> True
    current_time += 0.25
    assert uploader.submit_frame(frame) is True


def test_live_stream_uploader_queue_drop_lagging_frames(monkeypatch):
    """Verify queue maxsize=1 discards stale frames so only freshest frame is retained."""
    current_time = 1000.0
    monkeypatch.setattr(time, "time", lambda: current_time)

    mock_http_client = MagicMock()
    uploader = LiveStreamUploader(
        api_frame_url="http://mock-api/frame",
        target_fps=4.0,
        http_client=mock_http_client,
    )

    # Note: Worker is NOT started, so items remain in _frame_queue
    frame1 = np.full((100, 100, 3), 10, dtype=np.uint8)
    frame2 = np.full((100, 100, 3), 20, dtype=np.uint8)
    frame3 = np.full((100, 100, 3), 30, dtype=np.uint8)

    # Submit frame 1
    assert uploader.submit_frame(frame1) is True
    assert uploader._frame_queue.qsize() == 1

    # Advance time and submit frame 2 (discards frame 1)
    current_time += 0.3
    assert uploader.submit_frame(frame2) is True
    assert uploader._frame_queue.qsize() == 1

    # Advance time and submit frame 3 (discards frame 2)
    current_time += 0.3
    assert uploader.submit_frame(frame3) is True
    assert uploader._frame_queue.qsize() == 1

    # Queue should contain only the freshest frame (frame 3)
    queued_frame = uploader._frame_queue.get_nowait()
    assert np.array_equal(queued_frame, frame3)
    assert uploader._frame_queue.empty()


def test_live_stream_uploader_resizes_dimensions():
    """Verify frames larger than max_dimensions (e.g. 1280x720) are scaled to (640x480)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    mock_http_client = MagicMock()
    mock_http_client.post.return_value = mock_resp

    uploader = LiveStreamUploader(
        api_frame_url="http://mock-api/frame",
        max_dimensions=(640, 480),
        http_client=mock_http_client,
    )

    uploader.start()
    try:
        # High resolution frame: 1280 (width) x 720 (height)
        oversized_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        assert uploader.submit_frame(oversized_frame) is True

        deadline = time.time() + 2.0
        while not mock_http_client.post.called and time.time() < deadline:
            time.sleep(0.02)

        assert mock_http_client.post.called

        content = mock_http_client.post.call_args[1]["content"]
        decoded = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_COLOR)
        assert decoded is not None
        assert decoded.shape == (480, 640, 3)
    finally:
        uploader.stop()


def test_live_stream_uploader_clamps_fps_and_quality():
    """Verify target_fps and jpeg_quality are clamped to valid ranges."""
    uploader_low = LiveStreamUploader(
        api_frame_url="http://mock-api/frame",
        target_fps=0.1,
        jpeg_quality=10,
        http_client=MagicMock(),
    )
    assert uploader_low.target_fps == 1.0
    assert uploader_low.jpeg_quality == 30
    assert uploader_low.min_frame_interval_sec == 1.0

    uploader_high = LiveStreamUploader(
        api_frame_url="http://mock-api/frame",
        target_fps=50.0,
        jpeg_quality=150,
        http_client=MagicMock(),
    )
    assert uploader_high.target_fps == 15.0
    assert uploader_high.jpeg_quality == 95
    assert uploader_high.min_frame_interval_sec == pytest.approx(1.0 / 15.0)


def test_live_stream_uploader_validates_invalid_frames():
    """Verify submit_frame returns False on non-array, empty, or 1D inputs."""
    uploader = LiveStreamUploader(
        api_frame_url="http://mock-api/frame",
        http_client=MagicMock(),
    )

    assert uploader.submit_frame(None) is False  # type: ignore[arg-type]
    assert uploader.submit_frame("not an array") is False  # type: ignore[arg-type]
    assert uploader.submit_frame(np.array([])) is False
    assert uploader.submit_frame(np.array([1, 2, 3])) is False


def test_live_stream_uploader_idempotent_start_and_stop():
    """Verify start and stop methods are idempotent."""
    mock_client = MagicMock()
    uploader = LiveStreamUploader(
        api_frame_url="http://mock-api/frame",
        http_client=mock_client,
    )

    uploader.start()
    thread1 = uploader._thread
    assert thread1 is not None and thread1.is_alive()

    # Second start does not replace existing active thread
    uploader.start()
    assert uploader._thread is thread1

    uploader.stop()
    assert not thread1.is_alive()
    assert uploader._thread is None

    # Second stop should not raise
    uploader.stop()


def test_live_stream_uploader_network_error_resilience():
    """Verify worker survives network exceptions and non-200 responses without crashing."""
    mock_http_client = MagicMock()
    mock_http_client.post.side_effect = [
        httpx.ConnectError("Network unreachable"),
        MagicMock(status_code=500),
        MagicMock(status_code=204),
    ]

    uploader = LiveStreamUploader(
        api_frame_url="http://mock-api/frame",
        target_fps=15.0,
        http_client=mock_http_client,
    )

    uploader.start()
    try:
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        for _ in range(3):
            uploader.submit_frame(frame)
            time.sleep(0.08)

        # Worker thread should still be alive despite 3 failed/non-standard responses
        assert uploader._thread is not None
        assert uploader._thread.is_alive()
        assert mock_http_client.post.call_count == 3
    finally:
        uploader.stop()


def test_live_stream_uploader_no_token_omits_authorization_header():
    """Verify Authorization header is omitted when api_token is None or empty."""
    mock_http_client = MagicMock()
    mock_http_client.post.return_value = MagicMock(status_code=200)

    uploader = LiveStreamUploader(
        api_frame_url="http://mock-api/frame",
        api_token=None,
        http_client=mock_http_client,
    )

    uploader.start()
    try:
        uploader.submit_frame(np.zeros((50, 50, 3), dtype=np.uint8))
        deadline = time.time() + 2.0
        while not mock_http_client.post.called and time.time() < deadline:
            time.sleep(0.02)

        assert mock_http_client.post.called
        headers = mock_http_client.post.call_args[1]["headers"]
        assert "Authorization" not in headers
        assert headers["Content-Type"] == "image/jpeg"
    finally:
        uploader.stop()


def test_live_stream_uploader_owns_client_closes_on_stop():
    """Verify uploader closes its internally created httpx.Client upon stop."""
    uploader = LiveStreamUploader(
        api_frame_url="http://mock-api/frame",
    )
    assert uploader._owns_client is True
    assert isinstance(uploader.http_client, httpx.Client)

    uploader.stop()
    assert uploader.http_client.is_closed
