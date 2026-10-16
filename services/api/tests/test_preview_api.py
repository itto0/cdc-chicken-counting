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
