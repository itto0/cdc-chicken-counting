from datetime import datetime, timezone, timedelta
import sqlite3
import pytest
from shared.contracts import (
    CountEventDTO,
    CountAggregateDTO,
    HealthSampleDTO,
    SyncBatchPayload,
)
from services.counter.src.storage.db import LocalStorage


@pytest.fixture
def storage(tmp_path) -> LocalStorage:
    db_file = tmp_path / "test_outbox.db"
    store = LocalStorage(db_path=str(db_file))
    store.init_db()
    return store


def test_init_db_creates_tables_indices_and_wal_mode(tmp_path):
    db_file = tmp_path / "init_check.db"
    store = LocalStorage(db_path=str(db_file))
    store.init_db()

    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()

    # Check WAL mode
    cursor.execute("PRAGMA journal_mode;")
    mode = cursor.fetchone()[0]
    assert mode.lower() == "wal"

    # Check tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cursor.fetchall()}
    assert "outbox_events" in tables
    assert "outbox_aggregates" in tables
    assert "health_samples" in tables

    # Check indices exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
    indices = {row[0] for row in cursor.fetchall()}
    assert any("events" in idx and "synced" in idx for idx in indices)
    assert any("events" in idx and "line" in idx for idx in indices)

    conn.close()

    # Idempotent re-init
    store.init_db()


def test_insert_and_get_unsynced_events(storage):
    now = datetime.now(timezone.utc)
    ev1 = CountEventDTO(track_id=101, ts_utc=now, confidence=0.92)
    ev2 = CountEventDTO(track_id=102, ts_utc=now + timedelta(seconds=1), confidence=0.88)

    id1 = storage.insert_event("line1", ev1)
    id2 = storage.insert_event("line2", ev2)
    assert id1 > 0
    assert id2 > 0

    # Fetch unsynced all
    unsynced = storage.get_unsynced_events(limit=10)
    assert len(unsynced) == 2
    assert unsynced[0]["track_id"] == 101
    assert unsynced[0]["line_id"] == "line1"
    assert unsynced[1]["track_id"] == 102
    assert unsynced[1]["line_id"] == "line2"

    # Filter by line_id
    unsynced_line1 = storage.get_unsynced_events(limit=10, line_id="line1")
    assert len(unsynced_line1) == 1
    assert unsynced_line1[0]["track_id"] == 101

    # Mark id1 as synced
    storage.mark_events_synced([id1])

    # Only id2 remains unsynced
    remaining = storage.get_unsynced_events(limit=10)
    assert len(remaining) == 1
    assert remaining[0]["id"] == id2

    # Mark remaining
    storage.mark_events_synced([id2])
    assert len(storage.get_unsynced_events(limit=10)) == 0


def test_insert_and_get_unsynced_aggregates(storage):
    now = datetime.now(timezone.utc)
    agg = CountAggregateDTO(
        window_start=now - timedelta(minutes=1),
        window_end=now,
        count=15,
        rate_per_min=15.0,
        confidence_avg=0.94,
        status="NORMAL",
    )

    agg_id = storage.insert_aggregate("line1", agg)
    assert agg_id > 0

    unsynced = storage.get_unsynced_aggregates(limit=10)
    assert len(unsynced) == 1
    assert unsynced[0]["line_id"] == "line1"
    assert unsynced[0]["count"] == 15
    assert unsynced[0]["rate_per_min"] == 15.0
    assert unsynced[0]["status"] == "NORMAL"

    storage.mark_aggregates_synced([agg_id])
    assert len(storage.get_unsynced_aggregates(limit=10)) == 0


def test_insert_and_get_unsynced_health(storage):
    now = datetime.now(timezone.utc)
    health = HealthSampleDTO(
        fps=29.9,
        latency_p95_ms=33.5,
        cpu_pct=24.5,
        mem_pct=42.1,
        stream_state="ONLINE",
        model_name="yolo26n",
        model_version="v1.0",
    )

    health_id = storage.insert_health("line1", health, ts_utc=now)
    assert health_id > 0

    unsynced = storage.get_unsynced_health(limit=10)
    assert len(unsynced) == 1
    assert unsynced[0]["line_id"] == "line1"
    assert unsynced[0]["fps"] == 29.9
    assert unsynced[0]["stream_state"] == "ONLINE"
    assert unsynced[0]["model_name"] == "yolo26n"

    storage.mark_health_synced([health_id])
    assert len(storage.get_unsynced_health(limit=10)) == 0


def test_get_unsynced_batch_packaging_and_marking(storage):
    now = datetime.now(timezone.utc)
    ev = CountEventDTO(track_id=1, ts_utc=now, confidence=0.95)
    agg = CountAggregateDTO(
        window_start=now - timedelta(minutes=1),
        window_end=now,
        count=5,
        rate_per_min=5.0,
        confidence_avg=0.9,
        status="NORMAL",
    )
    health = HealthSampleDTO(
        fps=30.0,
        latency_p95_ms=20.0,
        cpu_pct=15.0,
        mem_pct=30.0,
        stream_state="ONLINE",
    )

    storage.insert_event("lineA", ev)
    storage.insert_aggregate("lineA", agg)
    storage.insert_health("lineA", health)

    # Insert items for lineB to ensure batch packaging isolates by line_id
    ev_b = CountEventDTO(track_id=99, ts_utc=now, confidence=0.8)
    storage.insert_event("lineB", ev_b)

    payload, ids = storage.get_unsynced_batch(line_id="lineA", limit=100)
    assert payload is not None
    assert isinstance(payload, SyncBatchPayload)
    assert payload.line_id == "lineA"
    assert len(payload.events) == 1
    assert payload.events[0].track_id == 1
    assert len(payload.aggregates) == 1
    assert payload.aggregates[0].count == 5
    assert payload.health is not None
    assert payload.health.fps == 30.0

    assert len(ids["event_ids"]) == 1
    assert len(ids["aggregate_ids"]) == 1
    assert len(ids["health_ids"]) == 1

    # Mark batch synced
    storage.mark_events_synced(ids["event_ids"])
    storage.mark_aggregates_synced(ids["aggregate_ids"])
    storage.mark_health_synced(ids["health_ids"])

    # LineA has nothing left unsynced
    payload_after, ids_after = storage.get_unsynced_batch(line_id="lineA")
    assert payload_after is None
    assert ids_after == {"event_ids": [], "aggregate_ids": [], "health_ids": []}

    # LineB still has its event
    payload_b, ids_b = storage.get_unsynced_batch(line_id="lineB")
    assert payload_b is not None
    assert len(payload_b.events) == 1
    assert payload_b.events[0].track_id == 99


def test_empty_storage_and_idempotent_marks(storage):
    assert storage.get_unsynced_events() == []
    assert storage.get_unsynced_aggregates() == []
    assert storage.get_unsynced_health() == []

    payload, ids = storage.get_unsynced_batch(line_id="empty_line")
    assert payload is None
    assert ids == {"event_ids": [], "aggregate_ids": [], "health_ids": []}

    # Empty marks should not raise
    storage.mark_events_synced([])
    storage.mark_aggregates_synced([])
    storage.mark_health_synced([])

    # Non-existent IDs mark should not raise
    storage.mark_events_synced([99999])
    storage.mark_aggregates_synced([99999])
    storage.mark_health_synced([99999])


def test_nested_directory_creation(tmp_path):
    nested_db = tmp_path / "deep" / "nested" / "dir" / "outbox.db"
    store = LocalStorage(db_path=str(nested_db))
    store.init_db()

    ev = CountEventDTO(track_id=1, ts_utc=datetime.now(timezone.utc), confidence=0.9)
    row_id = store.insert_event("line1", ev)
    assert row_id > 0
    assert len(store.get_unsynced_events()) == 1


def test_health_sample_defaults_and_filtering(storage):
    # Insert without explicit ts_utc
    h1 = HealthSampleDTO(
        fps=25.0, latency_p95_ms=40.0, cpu_pct=50.0, mem_pct=60.0, stream_state="ONLINE"
    )
    h2 = HealthSampleDTO(
        fps=20.0, latency_p95_ms=50.0, cpu_pct=55.0, mem_pct=65.0, stream_state="DEGRADED"
    )
    storage.insert_health("lineA", h1)
    storage.insert_health("lineB", h2)

    unsynced_a = storage.get_unsynced_health(line_id="lineA")
    assert len(unsynced_a) == 1
    assert unsynced_a[0]["line_id"] == "lineA"
    assert unsynced_a[0]["stream_state"] == "ONLINE"
    assert unsynced_a[0]["ts_utc"] is not None

    unsynced_b = storage.get_unsynced_health(line_id="lineB")
    assert len(unsynced_b) == 1
    assert unsynced_b[0]["line_id"] == "lineB"
    assert unsynced_b[0]["stream_state"] == "DEGRADED"


def test_limit_enforcement_on_unsynced_queries(storage):
    now = datetime.now(timezone.utc)
    for i in range(10):
        storage.insert_event("line1", CountEventDTO(track_id=i, ts_utc=now, confidence=0.9))
        storage.insert_aggregate(
            "line1",
            CountAggregateDTO(
                window_start=now,
                window_end=now,
                count=i,
                rate_per_min=float(i),
                confidence_avg=0.9,
            ),
        )

    assert len(storage.get_unsynced_events(limit=3)) == 3
    assert len(storage.get_unsynced_aggregates(limit=4)) == 4


def test_batch_packaging_picks_single_health_sample(storage):
    h1 = HealthSampleDTO(
        fps=15.0, latency_p95_ms=10.0, cpu_pct=20.0, mem_pct=30.0, stream_state="ONLINE"
    )
    h2 = HealthSampleDTO(
        fps=16.0, latency_p95_ms=12.0, cpu_pct=22.0, mem_pct=32.0, stream_state="ONLINE"
    )
    id1 = storage.insert_health("line1", h1)
    id2 = storage.insert_health("line1", h2)

    payload, ids = storage.get_unsynced_batch("line1", limit=100)
    assert payload is not None
    assert payload.health is not None
    assert payload.health.fps == 15.0
    assert ids["health_ids"] == [id1]

    # Sync first batch
    storage.mark_health_synced(ids["health_ids"])

    # Second batch should pick h2
    payload2, ids2 = storage.get_unsynced_batch("line1", limit=100)
    assert payload2 is not None
    assert payload2.health is not None
    assert payload2.health.fps == 16.0
    assert ids2["health_ids"] == [id2]

