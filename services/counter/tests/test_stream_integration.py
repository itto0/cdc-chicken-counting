"""Tests for LiveStreamUploader integration into CounterService and end-to-end streaming pacing."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from services.counter.main import (
    CounterService,
    LiveStreamUploader,
    build_arg_parser,
    parse_args,
)
from services.counter.src.contracts import CountEventDTO
from services.counter.src.detection.detector import Detection
from services.counter.src.storage.db import LocalStorage
from services.counter.src.sync.dispatcher import OutboxSyncDispatcher
from services.counter.src.tracking.tracker import TrackedObject


def test_counter_service_initializes_stream_uploader(tmp_path):
    """Verify CounterService constructs api_frame_url and initializes LiveStreamUploader."""
    db_file = str(tmp_path / "test_stream_init.db")

    # Case 1: Standard URL with /api/v1
    service = CounterService(
        line_id="lineAlpha",
        video_source_type="synthetic",
        api_sync_url="http://central-server:8000/api/v1/sync/batch",
        api_token="alpha-token",
        db_path=db_file,
        enable_stream_relay=True,
        stream_fps=6.0,
    )

    try:
        assert service.enable_stream_relay is True
        assert service.stream_fps == 6.0
        assert service.stream_uploader is not None
        assert isinstance(service.stream_uploader, LiveStreamUploader)
        assert (
            service.stream_uploader.api_frame_url
            == "http://central-server:8000/api/v1/lines/lineAlpha/frame"
        )
        assert service.stream_uploader.api_token == "alpha-token"
        assert service.stream_uploader.target_fps == 6.0
    finally:
        service.stop()

    # Case 2: Custom URL without /api/v1 (fallback to default http://localhost:8000)
    db_file2 = str(tmp_path / "test_stream_init2.db")
    service2 = CounterService(
        line_id="lineBeta",
        video_source_type="synthetic",
        api_sync_url="http://custom-host/legacy/sync",
        db_path=db_file2,
        enable_stream_relay=True,
        stream_fps=3.0,
    )

    try:
        assert service2.stream_uploader is not None
        assert (
            service2.stream_uploader.api_frame_url
            == "http://localhost:8000/api/v1/lines/lineBeta/frame"
        )
        assert service2.stream_uploader.target_fps == 3.0
    finally:
        service2.stop()


def test_counter_service_submits_frames_when_stream_requested(tmp_path):
    """Verify frames are rendered and submitted to uploader when dispatcher.stream_requested is True."""
    db_file = str(tmp_path / "test_stream_active.db")
    storage = LocalStorage(db_path=db_file)

    mock_uploader = MagicMock()
    mock_uploader.submit_frame.return_value = True

    dispatcher = OutboxSyncDispatcher(
        storage=storage,
        api_url="http://mock-api/api/v1/sync/batch",
        line_id="lineStreamActive",
    )
    dispatcher.stream_requested = True

    service = CounterService(
        line_id="lineStreamActive",
        video_source_type="synthetic",
        storage=storage,
        dispatcher=dispatcher,
        stream_uploader=mock_uploader,
        enable_stream_relay=True,
    )

    with patch.object(
        service, "render_annotated_frame", wraps=service.render_annotated_frame
    ) as spy_render:
        service.run(max_frames=5)

    assert service.total_frames_processed == 5
    # Uploader must be started at beginning of run
    assert mock_uploader.start.called
    # When stream_requested is True, render_annotated_frame and submit_frame MUST be called
    assert spy_render.call_count >= 1
    assert mock_uploader.submit_frame.call_count >= 1

    # Verify frame submitted is a valid 3-channel ndarray
    submitted_frame = mock_uploader.submit_frame.call_args[0][0]
    assert isinstance(submitted_frame, np.ndarray)
    assert submitted_frame.ndim == 3
    assert submitted_frame.shape[2] == 3

    # Uploader must be stopped at end of run / cleanup
    assert mock_uploader.stop.called


def test_counter_service_skips_frame_submission_when_stream_not_requested(tmp_path):
    """Verify frame rendering and submission are skipped when dispatcher.stream_requested is False."""
    db_file = str(tmp_path / "test_stream_idle.db")
    storage = LocalStorage(db_path=db_file)

    mock_uploader = MagicMock()

    dispatcher = OutboxSyncDispatcher(
        storage=storage,
        api_url="http://mock-api/api/v1/sync/batch",
        line_id="lineStreamIdle",
    )
    dispatcher.stream_requested = False

    service = CounterService(
        line_id="lineStreamIdle",
        video_source_type="synthetic",
        storage=storage,
        dispatcher=dispatcher,
        stream_uploader=mock_uploader,
        enable_stream_relay=True,
        show_window=False,
    )

    with patch.object(
        service, "render_annotated_frame", wraps=service.render_annotated_frame
    ) as spy_render:
        service.run(max_frames=5)

    assert service.total_frames_processed == 5
    # When stream_requested is False, frame rendering and submission MUST be skipped to avoid wasting CPU/GPU
    assert mock_uploader.submit_frame.call_count == 0
    assert spy_render.call_count == 0


def test_counter_service_disabled_stream_relay_flag(tmp_path):
    """Verify when enable_stream_relay=False, no uploader is created and no frames are submitted."""
    db_file = str(tmp_path / "test_stream_disabled.db")
    storage = LocalStorage(db_path=db_file)

    dispatcher = OutboxSyncDispatcher(
        storage=storage,
        api_url="http://mock-api/api/v1/sync/batch",
        line_id="lineStreamDisabled",
    )
    dispatcher.stream_requested = True  # Even if requested, relay is disabled

    service = CounterService(
        line_id="lineStreamDisabled",
        video_source_type="synthetic",
        storage=storage,
        dispatcher=dispatcher,
        enable_stream_relay=False,
        show_window=False,
    )

    assert service.enable_stream_relay is False
    assert service.stream_uploader is None

    with patch.object(
        service, "render_annotated_frame", wraps=service.render_annotated_frame
    ) as spy_render:
        service.run(max_frames=5)

    assert service.total_frames_processed == 5
    assert spy_render.call_count == 0


def test_render_annotated_frame_produces_annotated_image(tmp_path):
    """Verify render_annotated_frame returns a valid 3-channel annotated image."""
    db_file = str(tmp_path / "test_render_annotated.db")
    service = CounterService(
        line_id="lineAnnotated",
        video_source_type="synthetic",
        db_path=db_file,
    )

    # Active track (uncounted)
    track1 = TrackedObject(
        track_id=1,
        last_anchor=(150.0, 200.0),
        current_anchor=(150.0, 200.0),
        bbox=(100.0, 100.0, 200.0, 300.0),
        class_name="chicken",
        confidence=0.94,
        counted=False,
        missed_frames=0,
    )
    service.counter.tracks = {1: track1}

    det = Detection(
        x1=300.0,
        y1=100.0,
        x2=400.0,
        y2=250.0,
        confidence=0.85,
        class_id=0,
        class_name="chicken",
    )

    ev = CountEventDTO(
        track_id=1,
        ts_utc=datetime.now(timezone.utc),
        confidence=0.94,
    )

    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    annotated = service.render_annotated_frame(dummy_frame, detections=[det], events=[ev])

    assert annotated is not None
    assert isinstance(annotated, np.ndarray)
    assert annotated.shape == (480, 640, 3)
    # Ensure drawing occurred by checking non-zero pixels
    assert np.count_nonzero(annotated) > 0

    # Ensure invalid frames return None safely
    assert service.render_annotated_frame(None, detections=[], events=[]) is None
    assert service.render_annotated_frame("not_an_image", detections=[], events=[]) is None
    assert service.render_annotated_frame(np.array([]), detections=[], events=[]) is None


def test_cli_args_for_stream_relay():
    """Verify CLI parser supports --enable-stream-relay, --no-stream-relay, and --stream-fps."""
    parser = build_arg_parser()
    assert parser is not None

    args1 = parse_args(["--enable-stream-relay", "--stream-fps", "8.5"])
    assert args1.enable_stream_relay is True
    assert args1.stream_fps == 8.5

    args2 = parse_args(["--no-stream-relay"])
    assert args2.enable_stream_relay is False

    args3 = parse_args([])
    # Default is enabled with 4.0 fps
    assert args3.enable_stream_relay is True
    assert args3.stream_fps == 4.0


def test_counter_service_stop_stops_uploader(tmp_path):
    """Verify service.stop() explicitly triggers uploader.stop()."""
    db_file = str(tmp_path / "test_stop_uploader.db")
    mock_uploader = MagicMock()

    service = CounterService(
        line_id="lineStop",
        video_source_type="synthetic",
        db_path=db_file,
        stream_uploader=mock_uploader,
    )

    service.stop()
    assert mock_uploader.stop.called
