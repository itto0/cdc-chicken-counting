from unittest.mock import AsyncMock
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from services.api.src.main import app
from services.api.src.api.live import preview_stream
from services.api.src.services.preview import FrameGenerator


def test_mjpeg_preview_stream():
    with TestClient(app) as client:
        # Request with stream=True and take first chunk
        with client.stream("GET", "/api/v1/lines/line-1/preview?max_frames=2") as response:
            assert response.status_code == 200
            assert "multipart/x-mixed-replace" in response.headers["content-type"]
            assert "boundary=frame" in response.headers["content-type"]
            first_chunk = next(response.iter_bytes())
            assert b"--frame" in first_chunk or b"\xff\xd8" in first_chunk


def test_frame_generator_unit():
    # Test valid frame generation
    frame_bytes = FrameGenerator.generate_jpeg_frame("line-test", 0)
    assert isinstance(frame_bytes, bytes)
    assert len(frame_bytes) > 0
    # Standard JPEG SOI marker
    assert frame_bytes.startswith(b"\xff\xd8")
    # Standard JPEG EOI marker
    assert frame_bytes.endswith(b"\xff\xd9")

    # Decode and verify dimensions
    arr = np.frombuffer(frame_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    assert img is not None
    assert img.shape == (480, 640, 3)

    # Frame generator handles negative frame index without crashing
    neg_frame = FrameGenerator.generate_jpeg_frame("line-test", -10)
    assert neg_frame.startswith(b"\xff\xd8")


def test_mjpeg_preview_max_frames():
    with TestClient(app) as client:
        with client.stream("GET", "/api/v1/lines/line-1/preview?max_frames=3") as response:
            assert response.status_code == 200
            all_content = b"".join(response.iter_bytes())
            # Boundary delimiter count should match max_frames
            frame_marker_count = all_content.count(b"--frame\r\n")
            assert frame_marker_count == 3


def test_mjpeg_preview_invalid_empty_line_id():
    with TestClient(app) as client:
        response = client.get("/api/v1/lines/%20%20/preview")
        assert response.status_code == 400
        assert "Invalid line_id" in response.json()["detail"]


def test_mjpeg_preview_negative_max_frames():
    with TestClient(app) as client:
        response = client.get("/api/v1/lines/line-1/preview?max_frames=-1")
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_mjpeg_preview_client_disconnect_handling():
    req = AsyncMock()
    # Emulate client disconnecting after first check
    req.is_disconnected = AsyncMock(side_effect=[False, True])
    response = await preview_stream(line_id="line-1", request=req)
    assert response.status_code == 200
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)
    # Stream terminates when client disconnects
    assert len(chunks) == 1
    assert b"--frame" in chunks[0]


@pytest.mark.asyncio
async def test_mjpeg_preview_uses_asyncio_to_thread(monkeypatch):
    import asyncio
    called_in_thread = []
    orig_to_thread = asyncio.to_thread

    async def mock_to_thread(func, *args, **kwargs):
        called_in_thread.append((func, args))
        return await orig_to_thread(func, *args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", mock_to_thread)
    req = AsyncMock()
    req.is_disconnected = AsyncMock(side_effect=[False, True])
    response = await preview_stream(line_id="line-test", request=req, max_frames=1)
    async for _ in response.body_iterator:
        pass
    assert len(called_in_thread) >= 1
    assert called_in_thread[0][0] == FrameGenerator.generate_jpeg_frame


def test_synthetic_preview_frame_bounding_box_colors():
    """Verify synthetic preview frame generates orange, bright green, and counted green boxes."""
    # Frame 0: x_pos = (0 * 15) % 500 + 70 = 70 (< 300: Approaching/Uncounted)
    frame_uncounted_bytes = FrameGenerator.generate_jpeg_frame("test-line", 0)
    arr0 = np.frombuffer(frame_uncounted_bytes, dtype=np.uint8)
    img0 = cv2.imdecode(arr0, cv2.IMREAD_COLOR)
    # Box rectangle at x_pos=70 is from x=40 to x=100, y=190 to y=310.
    # BGR color for uncounted is (0, 180, 255) (Orange)
    # Check top horizontal border of the box at (y=190, x=70)
    assert img0[190, 70][0] < 50  # Blue channel low
    assert img0[190, 70][1] > 140  # Green channel ~180
    assert img0[190, 70][2] > 200  # Red channel ~255

    # Frame 17: x_pos = (17 * 15) % 500 + 70 = 325 (Crossing virtual line at 320)
    frame_crossing_bytes = FrameGenerator.generate_jpeg_frame("test-line", 17)
    arr17 = np.frombuffer(frame_crossing_bytes, dtype=np.uint8)
    img17 = cv2.imdecode(arr17, cv2.IMREAD_COLOR)
    # BGR color for crossing is (0, 255, 0) (Bright green)
    assert img17[190, 325][0] < 50  # Blue channel low
    assert img17[190, 325][1] > 220  # Green channel high
    assert img17[190, 325][2] < 50  # Red channel low

    # Frame 21: x_pos = (21 * 15) % 500 + 70 = 385 (> 340: Counted)
    frame_counted_bytes = FrameGenerator.generate_jpeg_frame("test-line", 21)
    arr21 = np.frombuffer(frame_counted_bytes, dtype=np.uint8)
    img21 = cv2.imdecode(arr21, cv2.IMREAD_COLOR)
    # BGR color for counted is (0, 220, 0) (Green)
    assert img21[190, 385][0] < 50  # Blue channel low
    assert img21[190, 385][1] > 180  # Green channel ~220
    assert img21[190, 385][2] < 50  # Red channel low

