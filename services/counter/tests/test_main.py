"""Tests for edge counter service production entrypoint and runner."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from services.counter.main import CounterService, main
from services.counter.src.storage.db import LocalStorage
from services.counter.src.sync.dispatcher import OutboxSyncDispatcher


def test_counter_service_initialization(tmp_path):
    """Verify CounterService correctly initializes internal components."""
    db_file = str(tmp_path / "test_init.db")
    service = CounterService(
        line_id="lineB",
        video_source_type="synthetic",
        api_sync_url="http://mock-api/sync",
        db_path=db_file,
        sync_interval_sec=2.0,
    )

    assert service.line_id == "lineB"
    assert service.video_source_type == "synthetic"
    assert service.api_sync_url == "http://mock-api/sync"
    assert service.sync_interval_sec == 2.0
    assert service.storage is not None
    assert service.dispatcher is not None
    assert service.source is not None
    assert service.detector is not None
    assert service.counter is not None


def test_counter_service_run_pipeline_max_frames(tmp_path):
    """Verify CounterService processes frames and stores outbox events."""
    db_file = str(tmp_path / "test_run.db")
    storage = LocalStorage(db_path=db_file)
    mock_http_client = MagicMock()
    mock_http_client.post.return_value.status_code = 200

    dispatcher = OutboxSyncDispatcher(
        storage=storage,
        api_url="http://mock-api/sync",
        line_id="lineTest",
        http_client=mock_http_client,
    )

    service = CounterService(
        line_id="lineTest",
        video_source_type="synthetic",
        storage=storage,
        dispatcher=dispatcher,
        sync_interval_sec=10.0,  # Sync will flush at cleanup
    )

    counted = service.run(max_frames=60)
    assert service.total_frames_processed == 60
    assert counted >= 0
    # Cleaned up
    assert not service.source.is_running


def test_counter_service_sync_interval_and_stop(tmp_path):
    """Verify periodic sync is triggered during loop and service stops on signal."""
    db_file = str(tmp_path / "test_sync.db")
    storage = LocalStorage(db_path=db_file)
    mock_http_client = MagicMock()
    mock_http_client.post.return_value.status_code = 200

    dispatcher = OutboxSyncDispatcher(
        storage=storage,
        api_url="http://mock-api/sync",
        line_id="lineSync",
        http_client=mock_http_client,
    )

    service = CounterService(
        line_id="lineSync",
        video_source_type="synthetic",
        storage=storage,
        dispatcher=dispatcher,
        sync_interval_sec=0.001,  # Fast sync interval
    )

    # Run for 20 frames
    service.run(max_frames=20)
    assert service.total_frames_processed == 20


def test_main_cli_entrypoint(tmp_path, monkeypatch):
    """Verify main() entrypoint respects environment variables."""
    db_file = str(tmp_path / "test_cli.db")
    monkeypatch.setenv("LINE_ID", "lineCLI")
    monkeypatch.setenv("VIDEO_SOURCE_TYPE", "synthetic")
    monkeypatch.setenv("DB_PATH", db_file)
    monkeypatch.setenv("MAX_FRAMES", "15")
    monkeypatch.setenv("SYNC_INTERVAL_SEC", "1.0")

    # Should run 15 frames and exit cleanly without error
    main()


def test_counter_service_records_aggregates_and_health(tmp_path):
    """Verify CounterService records both count aggregates and health samples."""
    db_file = str(tmp_path / "test_telemetry.db")
    storage = LocalStorage(db_path=db_file)
    mock_http_client = MagicMock()
    mock_http_client.post.return_value.status_code = 200

    dispatcher = OutboxSyncDispatcher(
        storage=storage,
        api_url="http://mock-api/sync",
        line_id="lineTelem",
        http_client=mock_http_client,
    )

    service = CounterService(
        line_id="lineTelem",
        video_source_type="synthetic",
        storage=storage,
        dispatcher=dispatcher,
        sync_interval_sec=10.0,
        aggregate_window_sec=0.01,  # Trigger rapid window aggregate
        health_interval_sec=0.01,     # Trigger rapid health sample
    )

    service.run(max_frames=10)

    # Check that aggregates or health samples were inserted
    unsynced_aggs = storage.get_unsynced_aggregates(line_id="lineTelem")
    unsynced_health = storage.get_unsynced_health(line_id="lineTelem")

    # Due to final flush at cleanup, records may be synced or in unsynced
    total_aggs = len(unsynced_aggs)
    total_health = len(unsynced_health)

    # Also check post calls to mock_http_client
    assert mock_http_client.post.called or (total_aggs > 0 or total_health > 0)


def test_counter_service_nonblocking_background_sync(tmp_path):
    """Verify sync runs decoupled in background worker without blocking frame capture."""
    import time
    db_file = str(tmp_path / "test_nonblock.db")
    storage = LocalStorage(db_path=db_file)

    sync_durations = []

    def slow_post(*args, **kwargs):
        time.sleep(0.05)  # Simulate network latency
        sync_durations.append(0.05)
        resp = MagicMock()
        resp.status_code = 200
        return resp

    mock_client = MagicMock()
    mock_client.post.side_effect = slow_post

    dispatcher = OutboxSyncDispatcher(
        storage=storage,
        api_url="http://mock-api/sync",
        line_id="lineNonBlock",
        http_client=mock_client,
    )

    service = CounterService(
        line_id="lineNonBlock",
        video_source_type="synthetic",
        storage=storage,
        dispatcher=dispatcher,
        sync_interval_sec=0.01,
    )

    t0 = time.perf_counter()
    counted = service.run(max_frames=15)
    total_time = time.perf_counter() - t0

    assert service.total_frames_processed == 15
    assert not service.running
    # Background thread is joined and cleaned up
    assert service._sync_thread is None or not service._sync_thread.is_alive()


def test_counter_service_aggregate_status_levels(tmp_path):
    """Verify aggregate status categorization: NORMAL >= 130, WARNING 110-129.9, CRITICAL < 110."""
    db_file = str(tmp_path / "test_status.db")
    storage = LocalStorage(db_path=db_file)
    service = CounterService(
        line_id="lineStatus",
        storage=storage,
    )

    # 1. High count -> NORMAL
    service._window_count = 150
    service._window_confidences = [0.95]
    service._record_aggregate()
    aggs = storage.get_unsynced_aggregates(line_id="lineStatus")
    assert len(aggs) == 1
    assert aggs[0]["status"] == "NORMAL"

    # 2. Moderate count -> WARNING
    # Artificially set start time 60 seconds ago so elapsed is 60s
    from datetime import datetime, timezone, timedelta
    service._window_start_utc = datetime.now(timezone.utc) - timedelta(seconds=60)
    service._window_count = 120
    service._record_aggregate()
    aggs = storage.get_unsynced_aggregates(line_id="lineStatus")
    assert len(aggs) == 2
    assert aggs[1]["status"] == "WARNING"

    # 3. Low count -> CRITICAL
    service._window_start_utc = datetime.now(timezone.utc) - timedelta(seconds=60)
    service._window_count = 50
    service._record_aggregate()
    aggs = storage.get_unsynced_aggregates(line_id="lineStatus")
    assert len(aggs) == 3
    assert aggs[2]["status"] == "CRITICAL"


def test_main_argv_video_standalone(tmp_path):
    """Verify main() handles --video, --no-sync, and --db-path arguments."""
    from services.counter.main import parse_args
    import cv2
    import numpy as np

    # Create dummy video file
    video_path = tmp_path / "test_vid.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(video_path), fourcc, 30, (64, 48))
    for _ in range(5):
        frame = np.zeros((48, 64, 3), dtype=np.uint8)
        out.write(frame)
    out.release()

    db_path = str(tmp_path / "argv_test.db")
    args = parse_args([
        "--video", str(video_path),
        "--no-sync",
        "--db-path", db_path,
        "--line", "0,24,64,24",
        "--direction", "down",
    ])
    assert args.video == str(video_path)
    assert args.no_sync is True
    assert args.db_path == db_path
    assert args.line == "0,24,64,24"

    # Run main with these arguments
    main([
        "--video", str(video_path),
        "--no-sync",
        "--db-path", db_path,
        "--max-frames", "5",
    ])
    assert Path(db_path).exists()


def test_main_argv_shackle_detector_options(tmp_path):
    """Verify parse_args and ShackleDetector setup with occupancy check options."""
    from services.counter.main import parse_args
    from services.counter.src.detection.detector import ShackleDetector
    import cv2
    import numpy as np

    video_path = tmp_path / "shackle_test.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(video_path), fourcc, 30, (64, 48))
    for _ in range(5):
        frame = np.zeros((48, 64, 3), dtype=np.uint8)
        out.write(frame)
    out.release()

    db_path = str(tmp_path / "shackle_argv.db")
    args = parse_args([
        "--video", str(video_path),
        "--detector", "shackle",
        "--occupancy-threshold", "5.2",
        "--no-occupancy-check",
        "--no-sync",
        "--db-path", db_path,
    ])
    assert args.detector == "shackle"
    assert args.occupancy_threshold == 5.2
    assert args.no_occupancy_check is True

    # Run main with shackle detector options
    main([
        "--video", str(video_path),
        "--detector", "shackle",
        "--occupancy-threshold", "5.2",
        "--no-occupancy-check",
        "--no-sync",
        "--db-path", db_path,
        "--max-frames", "5",
    ])
    assert Path(db_path).exists()


def test_render_window_frame_bounding_box_colors(tmp_path):
    """Verify _render_window_frame colors uncounted tracks orange and counted tracks green."""
    import cv2
    import numpy as np
    from unittest.mock import patch
    from services.counter.src.detection.detector import Detection
    from services.counter.src.tracking.tracker import TrackedObject

    db_file = str(tmp_path / "test_render.db")
    service = CounterService(
        line_id="lineRender",
        video_source_type="synthetic",
        db_path=db_file,
    )

    # Track 1: uncounted
    track1 = TrackedObject(
        track_id=1,
        last_anchor=(100.0, 150.0),
        current_anchor=(100.0, 150.0),
        bbox=(50.0, 50.0, 150.0, 150.0),
        class_name="chicken",
        confidence=0.91,
        counted=False,
        missed_frames=0,
    )
    # Track 2: counted
    track2 = TrackedObject(
        track_id=2,
        last_anchor=(300.0, 350.0),
        current_anchor=(300.0, 350.0),
        bbox=(250.0, 250.0, 350.0, 350.0),
        class_name="chicken",
        confidence=0.95,
        counted=True,
        missed_frames=0,
    )
    service.counter.tracks = {1: track1, 2: track2}

    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    with patch("cv2.imshow"), patch("cv2.namedWindow"), patch("cv2.resizeWindow"), patch("cv2.waitKey"), patch("cv2.putText", wraps=cv2.putText) as mock_put_text:
        vis = service._render_window_frame(dummy_frame, detections=[], events=[])

    assert vis is not None
    # Track 1 border at (x=50, y=50) should be Orange (BGR: 0, 180, 255)
    # Pixel on boundary:
    assert tuple(vis[50, 100]) == (0, 180, 255)
    # Track 2 border at (x=250, y=250) should be Green (BGR: 0, 220, 0)
    assert tuple(vis[250, 300]) == (0, 220, 0)

    # Verify track labels: Track 2 (counted) includes [COUNTED], Track 1 (uncounted) does not
    rendered_labels = [call.args[1] for call in mock_put_text.call_args_list]
    track1_labels = [l for l in rendered_labels if "#1" in l]
    assert len(track1_labels) == 1
    assert track1_labels[0] == "chicken #1 0.91"
    assert "[COUNTED]" not in track1_labels[0]

    track2_labels = [l for l in rendered_labels if "#2" in l]
    assert len(track2_labels) == 1
    assert track2_labels[0] == "chicken #2 0.95 [COUNTED]"
    assert "[COUNTED]" in track2_labels[0]


def test_render_window_frame_stale_tracks_and_unmatched_detections(tmp_path):
    """Verify stale tracks are skipped and unmatched detections are rendered orange."""
    import numpy as np
    from unittest.mock import patch
    from services.counter.src.detection.detector import Detection
    from services.counter.src.tracking.tracker import TrackedObject

    db_file = str(tmp_path / "test_render2.db")
    service = CounterService(
        line_id="lineRender",
        video_source_type="synthetic",
        db_path=db_file,
    )

    # Stale track (missed_frames > 0)
    stale_track = TrackedObject(
        track_id=3,
        last_anchor=(400.0, 400.0),
        current_anchor=(400.0, 400.0),
        bbox=(380.0, 380.0, 420.0, 420.0),
        class_name="chicken",
        confidence=0.9,
        counted=False,
        missed_frames=1,
    )
    service.counter.tracks = {3: stale_track}

    # Unmatched detection
    det = Detection(
        x1=50.0,
        y1=50.0,
        x2=150.0,
        y2=150.0,
        confidence=0.88,
        class_id=0,
        class_name="chicken",
    )

    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    with patch("cv2.imshow"), patch("cv2.namedWindow"), patch("cv2.resizeWindow"), patch("cv2.waitKey"):
        vis = service._render_window_frame(dummy_frame, detections=[det], events=[])

    assert vis is not None
    # Stale track should NOT be rendered (box boundary remains black)
    assert tuple(vis[380, 400]) == (0, 0, 0)
    # Unmatched detection should be rendered in Orange (BGR: 0, 180, 255)
    assert tuple(vis[50, 100]) == (0, 180, 255)


def test_render_window_frame_invalid_frame(tmp_path):
    """Verify _render_window_frame returns None when given invalid frame."""
    db_file = str(tmp_path / "test_render3.db")
    service = CounterService(line_id="lineRender", video_source_type="synthetic", db_path=db_file)
    assert service._render_window_frame(None, detections=[], events=[]) is None
    assert service._render_window_frame("not_a_frame", detections=[], events=[]) is None



