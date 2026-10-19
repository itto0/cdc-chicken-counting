from datetime import datetime, timezone
from unittest.mock import MagicMock
import httpx
import pytest

from shared.contracts import (
    CountAggregateDTO,
    CountEventDTO,
    HealthSampleDTO,
)
from services.counter.src.storage.db import LocalStorage
from services.counter.src.sync.dispatcher import OutboxSyncDispatcher


def test_sync_dispatcher_pushes_batch_and_marks_synced(tmp_path):
    storage = LocalStorage(db_path=str(tmp_path / "sync.db"))
    storage.init_db()
    storage.insert_event(
        "lineA",
        CountEventDTO(
            track_id=1,
            ts_utc=datetime.now(timezone.utc),
            confidence=0.9,
        ),
    )

    mock_http_client = MagicMock()
    mock_http_client.post.return_value.status_code = 200

    dispatcher = OutboxSyncDispatcher(
        storage=storage,
        api_url="http://mock-api/api/v1/sync/batch",
        line_id="lineA",
        http_client=mock_http_client,
    )

    synced_count = dispatcher.sync_once()
    assert synced_count == 1
    assert len(storage.get_unsynced_events()) == 0
    mock_http_client.post.assert_called_once()


def test_sync_dispatcher_empty_outbox_returns_zero_and_no_http_call(tmp_path):
    storage = LocalStorage(db_path=str(tmp_path / "sync.db"))
    storage.init_db()

    mock_http_client = MagicMock()
    dispatcher = OutboxSyncDispatcher(
        storage=storage,
        api_url="http://mock-api/api/v1/sync/batch",
        line_id="lineA",
        http_client=mock_http_client,
    )

    count = dispatcher.sync_once()
    assert count == 0
    mock_http_client.post.assert_not_called()


def test_sync_dispatcher_http_error_applies_exponential_backoff(tmp_path):
    storage = LocalStorage(db_path=str(tmp_path / "sync.db"))
    storage.init_db()
    storage.insert_event(
        "lineA",
        CountEventDTO(
            track_id=1,
            ts_utc=datetime.now(timezone.utc),
            confidence=0.9,
        ),
    )

    mock_http_client = MagicMock()
    mock_http_client.post.return_value.status_code = 500

    dispatcher = OutboxSyncDispatcher(
        storage=storage,
        api_url="http://mock-api/api/v1/sync/batch",
        line_id="lineA",
        http_client=mock_http_client,
    )

    assert dispatcher.backoff_sec == 1.0

    # 1st failure: doubles to 2.0
    synced = dispatcher.sync_once()
    assert synced == 0
    assert dispatcher.backoff_sec == 2.0

    # 2nd failure: doubles to 4.0
    synced = dispatcher.sync_once()
    assert synced == 0
    assert dispatcher.backoff_sec == 4.0

    # 3rd failure: doubles to 8.0
    synced = dispatcher.sync_once()
    assert synced == 0
    assert dispatcher.backoff_sec == 8.0

    # Event should remain unsynced
    assert len(storage.get_unsynced_events()) == 1


def test_sync_dispatcher_network_exception_applies_backoff_and_caps_at_max(tmp_path):
    storage = LocalStorage(db_path=str(tmp_path / "sync.db"))
    storage.init_db()
    storage.insert_event(
        "lineA",
        CountEventDTO(
            track_id=1,
            ts_utc=datetime.now(timezone.utc),
            confidence=0.9,
        ),
    )

    mock_http_client = MagicMock()
    mock_http_client.post.side_effect = httpx.ConnectError("Network unreachable")

    dispatcher = OutboxSyncDispatcher(
        storage=storage,
        api_url="http://mock-api/api/v1/sync/batch",
        line_id="lineA",
        http_client=mock_http_client,
        max_backoff_sec=30.0,
    )

    # Trigger multiple failures: 1.0 -> 2.0 -> 4.0 -> 8.0 -> 16.0 -> 30.0 (capped) -> 30.0
    delays = []
    for _ in range(6):
        dispatcher.sync_once()
        delays.append(dispatcher.backoff_sec)

    assert delays == [2.0, 4.0, 8.0, 16.0, 30.0, 30.0]
    assert len(storage.get_unsynced_events()) == 1


def test_sync_dispatcher_resets_backoff_after_success(tmp_path):
    storage = LocalStorage(db_path=str(tmp_path / "sync.db"))
    storage.init_db()
    storage.insert_event(
        "lineA",
        CountEventDTO(
            track_id=1,
            ts_utc=datetime.now(timezone.utc),
            confidence=0.9,
        ),
    )

    mock_http_client = MagicMock()
    mock_http_client.post.return_value.status_code = 201

    dispatcher = OutboxSyncDispatcher(
        storage=storage,
        api_url="http://mock-api/api/v1/sync/batch",
        line_id="lineA",
        http_client=mock_http_client,
    )
    dispatcher.backoff_sec = 16.0  # Simulate prior failures

    synced = dispatcher.sync_once()
    assert synced == 1
    assert dispatcher.backoff_sec == 1.0
    assert len(storage.get_unsynced_events()) == 0


def test_sync_dispatcher_syncs_events_aggregates_and_health_together(tmp_path):
    storage = LocalStorage(db_path=str(tmp_path / "sync.db"))
    storage.init_db()

    now = datetime.now(timezone.utc)
    storage.insert_event(
        "lineA",
        CountEventDTO(track_id=101, ts_utc=now, confidence=0.88),
    )
    storage.insert_aggregate(
        "lineA",
        CountAggregateDTO(
            window_start=now,
            window_end=now,
            count=45,
            rate_per_min=90.0,
            confidence_avg=0.92,
            status="NORMAL",
        ),
    )
    storage.insert_health(
        "lineA",
        HealthSampleDTO(
            fps=29.5,
            latency_p95_ms=12.0,
            cpu_pct=35.0,
            mem_pct=42.0,
            stream_state="ONLINE",
            model_name="yolo26n",
            model_version="v1.0",
        ),
    )

    mock_http_client = MagicMock()
    mock_http_client.post.return_value.status_code = 200

    dispatcher = OutboxSyncDispatcher(
        storage=storage,
        api_url="http://mock-api/api/v1/sync/batch",
        line_id="lineA",
        http_client=mock_http_client,
    )

    synced = dispatcher.sync_once()
    assert synced == 3

    # All items should now be marked synced
    assert len(storage.get_unsynced_events()) == 0
    assert len(storage.get_unsynced_aggregates()) == 0
    assert len(storage.get_unsynced_health()) == 0

    # Verify posted payload structure
    mock_http_client.post.assert_called_once()
    _, kwargs = mock_http_client.post.call_args
    posted_json = kwargs["json"]
    assert posted_json["line_id"] == "lineA"
    assert len(posted_json["events"]) == 1
    assert posted_json["events"][0]["track_id"] == 101
    assert len(posted_json["aggregates"]) == 1
    assert posted_json["aggregates"][0]["count"] == 45
    assert posted_json["health"]["fps"] == 29.5


def test_sync_dispatcher_default_http_client_and_context_manager(tmp_path):
    storage = LocalStorage(db_path=str(tmp_path / "sync.db"))
    storage.init_db()

    with OutboxSyncDispatcher(
        storage=storage,
        api_url="http://mock-api/api/v1/sync/batch",
        line_id="lineA",
    ) as dispatcher:
        assert isinstance(dispatcher.http_client, httpx.Client)

    # Calling close on already closed or with mock client should be safe
    mock_client = MagicMock()
    d2 = OutboxSyncDispatcher(
        storage=storage,
        api_url="http://mock-api/api/v1/sync/batch",
        line_id="lineA",
        http_client=mock_client,
    )
    d2.close()
    mock_client.close.assert_called_once()


def test_sync_dispatcher_sends_authorization_header_when_api_token_set(tmp_path):
    storage = LocalStorage(db_path=str(tmp_path / "sync.db"))
    storage.init_db()
    storage.insert_event(
        "lineA",
        CountEventDTO(
            track_id=1,
            ts_utc=datetime.now(timezone.utc),
            confidence=0.9,
        ),
    )

    mock_http_client = MagicMock()
    mock_http_client.post.return_value.status_code = 200

    dispatcher = OutboxSyncDispatcher(
        storage=storage,
        api_url="http://mock-api/api/v1/sync/batch",
        line_id="lineA",
        http_client=mock_http_client,
        api_token="cdc_live_test_token_123",
    )

    synced_count = dispatcher.sync_once()
    assert synced_count == 1
    mock_http_client.post.assert_called_once()
    _, kwargs = mock_http_client.post.call_args
    assert kwargs.get("headers") == {"Authorization": "Bearer cdc_live_test_token_123"}

