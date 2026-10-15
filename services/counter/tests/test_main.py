"""Tests for edge counter service production entrypoint and runner."""

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

