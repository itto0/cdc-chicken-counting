import time
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.api.src.db.models import Base
from services.api.src.db.session import get_db
from services.api.src.main import app
from services.api.src.services.preview import (
    clear_relay_buffer,
    get_live_frame,
    is_stream_requested,
    record_viewer_activity,
    store_live_frame,
    FrameGenerator,
)


@pytest.fixture(autouse=True)
def clean_relay_buffer():
    """Ensure in-memory viewer presence and relay frames are cleared before and after each test."""
    clear_relay_buffer()
    yield
    clear_relay_buffer()


@pytest.fixture
def setup_test_db(tmp_path):
    test_db_file = tmp_path / "test_relay.db"
    test_engine = create_engine(
        f"sqlite:///{test_db_file}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestingSessionLocal
    app.dependency_overrides.pop(get_db, None)
    test_engine.dispose()


def test_viewer_activity_presence_and_expiration():
    """Validates presence recording, expiration after timeout, and line isolation."""
    # Initially no viewer requested
    assert is_stream_requested("line-1") is False
    assert is_stream_requested("line-2") is False

    # Record activity for line-1
    record_viewer_activity("line-1")
    assert is_stream_requested("line-1") is True
    # Line isolation: line-2 should remain unrequested
    assert is_stream_requested("line-2") is False

    # Expiration: verify that moving beyond timeout_sec marks stream as unrequested
    now = time.time()
    with patch("time.time", return_value=now + 10.5):
        assert is_stream_requested("line-1", timeout_sec=10.0) is False

    # Within timeout_sec it should still be requested
    with patch("time.time", return_value=now + 5.0):
        assert is_stream_requested("line-1", timeout_sec=10.0) is True

    # After expiration, re-recording refreshes presence
    record_viewer_activity("line-1")
    assert is_stream_requested("line-1") is True


def test_store_and_retrieve_live_frame():
    """Validates storage, retrieval of valid JPEG bytes, and line isolation."""
    # Initially empty
    assert get_live_frame("line-1") is None
    assert get_live_frame("line-2") is None

    jpeg_data_line1 = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01line1\xff\xd9"
    jpeg_data_line2 = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01line2\xff\xd9"

    store_live_frame("line-1", jpeg_data_line1)
    assert get_live_frame("line-1") == jpeg_data_line1
    assert get_live_frame("line-2") is None

    store_live_frame("line-2", jpeg_data_line2)
    assert get_live_frame("line-1") == jpeg_data_line1
    assert get_live_frame("line-2") == jpeg_data_line2

    # Overwrite line-1 frame
    updated_jpeg_line1 = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01line1_updated\xff\xd9"
    store_live_frame("line-1", updated_jpeg_line1)
    assert get_live_frame("line-1") == updated_jpeg_line1

    # Check max_age_sec expiration
    now = time.time()
    with patch("time.time", return_value=now + 8.5):
        assert get_live_frame("line-1", max_age_sec=8.0) is None
        assert get_live_frame("line-2", max_age_sec=8.0) is None

    with patch("time.time", return_value=now + 3.0):
        assert get_live_frame("line-1", max_age_sec=8.0) == updated_jpeg_line1


def test_live_frame_expiration_falls_back_to_synthetic():
    """Validates that FrameGenerator.generate_jpeg_frame returns uploaded live bytes within freshness window, and returns synthetic frame when stale (> max_age_sec)."""
    with patch.object(FrameGenerator, "_resolve_video_path", return_value=None):
        # Case 1: No live frame in buffer -> returns synthetic frame
        initial_frame = FrameGenerator.generate_jpeg_frame("line-1", 0)
        assert isinstance(initial_frame, bytes)
        assert initial_frame.startswith(b"\xff\xd8")
        assert initial_frame.endswith(b"\xff\xd9")

        # Case 2: Fresh live frame stored -> returns live frame bytes directly
        mock_live_jpeg = b"\xff\xd8\xff\xe0live_edge_frame_payload\xff\xd9"
        store_live_frame("line-1", mock_live_jpeg)

        fresh_frame = FrameGenerator.generate_jpeg_frame("line-1", 0)
        assert fresh_frame == mock_live_jpeg

        # Unrelated line still falls back to synthetic frame
        other_line_frame = FrameGenerator.generate_jpeg_frame("line-2", 0)
        assert other_line_frame != mock_live_jpeg
        assert other_line_frame.startswith(b"\xff\xd8")

        # Case 3: Live frame becomes stale (> 8.0s) -> falls back to synthetic frame
        now = time.time()
        with patch("time.time", return_value=now + 8.5):
            stale_frame = FrameGenerator.generate_jpeg_frame("line-1", 0)
            assert stale_frame != mock_live_jpeg
            assert stale_frame.startswith(b"\xff\xd8")
            assert stale_frame.endswith(b"\xff\xd9")


def test_sync_batch_returns_stream_requested_status(setup_test_db):
    """Validates that calling /api/v1/sync/batch returns 'stream_requested': True when viewer is active, and False when no viewer is active."""
    client = TestClient(app)

    # 1. No active viewer -> stream_requested is False
    resp1 = client.post("/api/v1/sync/batch", json={"line_id": "line-sync-test", "events": []})
    assert resp1.status_code == 200
    assert resp1.json()["stream_requested"] is False

    # 2. Record active viewer -> stream_requested is True
    record_viewer_activity("line-sync-test")
    resp2 = client.post("/api/v1/sync/batch", json={"line_id": "line-sync-test", "events": []})
    assert resp2.status_code == 200
    assert resp2.json()["stream_requested"] is True

    # 3. Line isolation -> another line has stream_requested False
    resp3 = client.post("/api/v1/sync/batch", json={"line_id": "other-line", "events": []})
    assert resp3.status_code == 200
    assert resp3.json()["stream_requested"] is False

    # 4. Timeout expiration -> stream_requested reverts to False
    now = time.time()
    with patch("time.time", return_value=now + 12.0):
        resp4 = client.post("/api/v1/sync/batch", json={"line_id": "line-sync-test", "events": []})
        assert resp4.status_code == 200
        assert resp4.json()["stream_requested"] is False

    # 5. Integration: actual preview streaming request triggers viewer presence
    with client.stream("GET", "/api/v1/lines/preview-integrated/preview?max_frames=1") as preview_res:
        assert preview_res.status_code == 200
        _ = next(preview_res.iter_bytes())

    resp5 = client.post("/api/v1/sync/batch", json={"line_id": "preview-integrated", "events": []})
    assert resp5.status_code == 200
    assert resp5.json()["stream_requested"] is True
