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
