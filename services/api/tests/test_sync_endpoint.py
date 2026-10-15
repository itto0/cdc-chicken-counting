from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from services.api.src.db.models import Base, CountAggregate, CountEvent, HealthSample
from services.api.src.db.session import get_db
from services.api.src.main import app


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    test_db_file = tmp_path / "test_api.db"
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
    app.dependency_overrides.clear()
    test_engine.dispose()


def test_sync_batch_endpoint_ingests_and_deduplicates():
    client = TestClient(app)
    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        "line_id": "lineA",
        "events": [
            {"track_id": 100, "ts_utc": now_iso, "confidence": 0.95}
        ]
    }

    # First sync: event accepted
    resp1 = client.post("/api/v1/sync/batch", json=payload)
    assert resp1.status_code == 200
    assert resp1.json()["ingested_events"] == 1

    # Second sync: duplicate ignored (idempotent)
    resp2 = client.post("/api/v1/sync/batch", json=payload)
    assert resp2.status_code == 200
    assert resp2.json()["ingested_events"] == 0
    assert resp2.json()["duplicates_skipped"] == 1


def test_sync_batch_multiple_events_and_partial_duplicates(setup_test_db):
    client = TestClient(app)
    ts1 = datetime(2026, 10, 15, 10, 0, 0, tzinfo=timezone.utc).isoformat()
    ts2 = datetime(2026, 10, 15, 10, 0, 1, tzinfo=timezone.utc).isoformat()
    ts3 = datetime(2026, 10, 15, 10, 0, 2, tzinfo=timezone.utc).isoformat()

    # Pre-populate event 1
    resp1 = client.post(
        "/api/v1/sync/batch",
        json={
            "line_id": "line1",
            "events": [
                {"track_id": 1, "ts_utc": ts1, "confidence": 0.9}
            ],
        },
    )
    assert resp1.status_code == 200
    assert resp1.json()["ingested_events"] == 1

    # Send batch with event 1 (duplicate), event 2 (new), event 3 (new)
    resp2 = client.post(
        "/api/v1/sync/batch",
        json={
            "line_id": "line1",
            "events": [
                {"track_id": 1, "ts_utc": ts1, "confidence": 0.9},
                {"track_id": 2, "ts_utc": ts2, "confidence": 0.92},
                {"track_id": 3, "ts_utc": ts3, "confidence": 0.88},
            ],
        },
    )
    assert resp2.status_code == 200
    assert resp2.json()["ingested_events"] == 2
    assert resp2.json()["duplicates_skipped"] == 1

    # Verify db contents
    with setup_test_db() as db:
        events = db.scalars(select(CountEvent).where(CountEvent.line_id == "line1")).all()
        assert len(events) == 3


def test_sync_batch_intra_batch_duplicates(setup_test_db):
    client = TestClient(app)
    ts = datetime(2026, 10, 15, 10, 5, 0, tzinfo=timezone.utc).isoformat()
    payload = {
        "line_id": "lineX",
        "events": [
            {"track_id": 50, "ts_utc": ts, "confidence": 0.91},
            {"track_id": 50, "ts_utc": ts, "confidence": 0.91},
        ],
    }
    resp = client.post("/api/v1/sync/batch", json=payload)
    assert resp.status_code == 200
    assert resp.json()["ingested_events"] == 1
    assert resp.json()["duplicates_skipped"] == 1

    with setup_test_db() as db:
        events = db.scalars(select(CountEvent).where(CountEvent.line_id == "lineX")).all()
        assert len(events) == 1


def test_sync_batch_ingests_aggregates_and_health(setup_test_db):
    client = TestClient(app)
    start = datetime(2026, 10, 15, 8, 0, 0, tzinfo=timezone.utc).isoformat()
    end = datetime(2026, 10, 15, 8, 1, 0, tzinfo=timezone.utc).isoformat()
    ev_ts = datetime(2026, 10, 15, 8, 0, 30, tzinfo=timezone.utc).isoformat()

    payload = {
        "line_id": "line1",
        "events": [
            {"track_id": 201, "ts_utc": ev_ts, "confidence": 0.97}
        ],
        "aggregates": [
            {
                "window_start": start,
                "window_end": end,
                "count": 42,
                "rate_per_min": 42.0,
                "confidence_avg": 0.96,
                "status": "NORMAL",
            }
        ],
        "health": {
            "fps": 29.5,
            "latency_p95_ms": 18.2,
            "cpu_pct": 32.5,
            "mem_pct": 45.0,
            "stream_state": "ONLINE",
            "model_name": "yolo26n",
            "model_version": "v1.0",
        },
    }

    resp = client.post("/api/v1/sync/batch", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["line_id"] == "line1"
    assert data["ingested_events"] == 1
    assert data["duplicates_skipped"] == 0
    assert data["ingested_aggregates"] == 1
    assert data["health_ingested"] is True

    # Verify db records
    with setup_test_db() as db:
        events = db.scalars(select(CountEvent).where(CountEvent.line_id == "line1")).all()
        assert len(events) == 1

        aggs = db.scalars(select(CountAggregate).where(CountAggregate.line_id == "line1")).all()
        assert len(aggs) == 1
        assert aggs[0].count == 42
        assert aggs[0].rate_per_min == 42.0
        assert aggs[0].status == "NORMAL"

        healths = db.scalars(select(HealthSample).where(HealthSample.line_id == "line1")).all()
        assert len(healths) == 1
        assert healths[0].fps == 29.5
        assert healths[0].cpu_pct == 32.5
        assert healths[0].stream_state == "ONLINE"
        assert healths[0].model_name == "yolo26n"


def test_sync_batch_empty_payload():
    client = TestClient(app)
    payload = {
        "line_id": "lineEmpty",
        "events": [],
        "aggregates": [],
        "health": None,
    }
    resp = client.post("/api/v1/sync/batch", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ingested_events"] == 0
    assert data["duplicates_skipped"] == 0
    assert data["ingested_aggregates"] == 0
    assert data["health_ingested"] is False


def test_sync_batch_invalid_payload():
    client = TestClient(app)
    # Invalid confidence (> 1.0)
    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        "line_id": "lineA",
        "events": [
            {"track_id": 100, "ts_utc": now_iso, "confidence": 1.5}
        ]
    }
    resp = client.post("/api/v1/sync/batch", json=payload)
    assert resp.status_code == 422


def test_sync_batch_evaluates_alarms_and_broadcasts(setup_test_db, monkeypatch):
    """Verify that ingest sync evaluates alarms and broadcasts SSE telemetry."""
    from services.api.src.db.models import Alarm
    from services.api.src.api.live import broadcaster

    broadcasted_events = []

    def mock_publish(line_id, event_type, data):
        broadcasted_events.append((line_id, event_type, data))
        return 1

    monkeypatch.setattr(broadcaster, "publish", mock_publish)

    client = TestClient(app)
    start = datetime(2026, 10, 15, 9, 0, 0, tzinfo=timezone.utc).isoformat()
    end = datetime(2026, 10, 15, 9, 1, 0, tzinfo=timezone.utc).isoformat()

    payload = {
        "line_id": "lineAlarmTest",
        "events": [],
        "aggregates": [
            {
                "window_start": start,
                "window_end": end,
                "count": 95,
                "rate_per_min": 95.0,  # Below 110 -> CRITICAL LOW_RATE
                "confidence_avg": 0.95,
                "status": "CRITICAL",
            }
        ],
        "health": {
            "fps": 0.0,
            "latency_p95_ms": 250.0,
            "cpu_pct": 10.0,
            "mem_pct": 20.0,
            "stream_state": "OFFLINE",  # OFFLINE -> CRITICAL STREAM_OFFLINE
            "model_name": "yolo26n",
            "model_version": "v1.0",
        },
    }

    resp = client.post("/api/v1/sync/batch", json=payload)
    assert resp.status_code == 200

    # 1. Verify Alarms recorded in DB
    with setup_test_db() as db:
        alarms = db.scalars(select(Alarm).where(Alarm.line_id == "lineAlarmTest")).all()
        assert len(alarms) >= 1
        alarm_types = {a.alarm_type for a in alarms}
        assert "LOW_RATE" in alarm_types
        assert "STREAM_OFFLINE" in alarm_types

    # 2. Verify broadcasted events
    event_types = [item[1] for item in broadcasted_events]
    assert "alarm" in event_types
    assert "count" in event_types
    assert "health" in event_types

    # Check payload details
    count_broadcasts = [item[2] for item in broadcasted_events if item[1] == "count"]
    assert count_broadcasts[0]["rate_per_min"] == 95.0
    assert count_broadcasts[0]["status"] == "CRITICAL"
    assert count_broadcasts[0]["total_today"] >= 95

    health_broadcasts = [item[2] for item in broadcasted_events if item[1] == "health"]
    assert health_broadcasts[0]["fps"] == 0.0
    assert health_broadcasts[0]["status"] == "OFFLINE"

