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


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def test_db(setup_test_db):
    db = setup_test_db()
    try:
        yield db
    finally:
        db.close()


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


def test_sync_batch_broadcast_total_today_uses_jakarta_bounds(monkeypatch, setup_test_db):
    from shared.time_utils import get_jakarta_today_bounds_utc
    from datetime import timedelta

    start_utc, end_utc = get_jakarta_today_bounds_utc()
    # Event before today's Jakarta day: 1 hour before start_utc
    outside_ts = (start_utc - timedelta(hours=1)).replace(tzinfo=None)
    # Event inside today's Jakarta day: 2 hours after start_utc
    inside_ts = (start_utc + timedelta(hours=2)).replace(tzinfo=None)

    with setup_test_db() as db:
        ev_outside = CountEvent(
            line_id="line-jkt-sync",
            track_id=501,
            ts_utc=outside_ts,
            confidence=0.9,
        )
        ev_inside = CountEvent(
            line_id="line-jkt-sync",
            track_id=502,
            ts_utc=inside_ts,
            confidence=0.9,
        )
        db.add_all([ev_outside, ev_inside])
        db.commit()

    broadcasted_counts = []

    def mock_broadcast(line_id, event_type, payload):
        if event_type == "count":
            broadcasted_counts.append((line_id, payload))

    monkeypatch.setattr("services.api.src.api.sync.broadcast_line_update", mock_broadcast)

    client = TestClient(app)
    payload = {
        "line_id": "line-jkt-sync",
        "events": [],
        "aggregates": [
            {
                "window_start": inside_ts.isoformat(),
                "window_end": (inside_ts + timedelta(minutes=1)).isoformat(),
                "count": 10,
                "rate_per_min": 10.0,
                "confidence_avg": 0.95,
                "status": "NORMAL",
            }
        ],
    }
    resp = client.post("/api/v1/sync/batch", json=payload)
    assert resp.status_code == 200
    assert len(broadcasted_counts) == 1
    # total_today should count ONLY the inside event (1 event), ignoring outside_ts
    assert broadcasted_counts[0][1]["total_today"] == 1


def test_sync_health_with_accuracy_pct(client, test_db):
    from services.api.src.db.models import HealthSample

    payload = {
        "line_id": "lineA",
        "events": [],
        "aggregates": [],
        "health": {
            "fps": 30.0,
            "latency_p95_ms": 22.5,
            "cpu_pct": 12.0,
            "mem_pct": 45.0,
            "stream_state": "ONLINE",
            "accuracy_pct": 99.25,
        },
    }
    resp = client.post("/api/v1/sync", json=payload)
    assert resp.status_code == 200

    record = test_db.query(HealthSample).filter_by(line_id="lineA").order_by(HealthSample.id.desc()).first()
    assert record is not None
    assert record.accuracy_pct == 99.25


def test_sync_health_broadcasts_accuracy_pct(client, monkeypatch):
    from services.api.src.api.live import broadcaster

    broadcasted = []
    monkeypatch.setattr(
        broadcaster,
        "publish",
        lambda line_id, ev_type, data: broadcasted.append((line_id, ev_type, data)) or 1,
    )

    payload = {
        "line_id": "lineA",
        "events": [],
        "aggregates": [],
        "health": {
            "fps": 30.0,
            "latency_p95_ms": 22.5,
            "cpu_pct": 12.0,
            "mem_pct": 45.0,
            "stream_state": "ONLINE",
            "accuracy_pct": 99.25,
        },
    }
    resp = client.post("/api/v1/sync", json=payload)
    assert resp.status_code == 200

    health_events = [data for line, ev_type, data in broadcasted if ev_type == "health"]
    assert len(health_events) == 1
    assert health_events[0]["accuracy_pct"] == 99.25


def test_sync_batch_uses_line_threshold_overrides_and_resolves_alarm(setup_test_db):
    from services.api.src.db.models import Line, Alarm

    # Create a line with custom thresholds: warning 150.0, critical 120.0
    with setup_test_db() as db:
        line = Line(
            id="lineCustomThresh",
            name="Line Custom Thresh",
            rate_warning_threshold=150.0,
            rate_critical_threshold=120.0,
        )
        db.add(line)
        db.commit()

    client = TestClient(app)
    start = datetime(2026, 10, 15, 9, 0, 0, tzinfo=timezone.utc).isoformat()
    end = datetime(2026, 10, 15, 9, 1, 0, tzinfo=timezone.utc).isoformat()

    # 1. Ingest rate of 140.0. Under default (130/110), 140 is normal. But for this line, warning is 150!
    # So rate 140.0 should trigger WARNING alarm.
    payload1 = {
        "line_id": "lineCustomThresh",
        "events": [],
        "aggregates": [
            {
                "window_start": start,
                "window_end": end,
                "count": 140,
                "rate_per_min": 140.0,
                "confidence_avg": 0.95,
                "status": "NORMAL",
            }
        ],
    }
    resp1 = client.post("/api/v1/sync/batch", json=payload1)
    assert resp1.status_code == 200

    with setup_test_db() as db:
        alarm = db.scalars(select(Alarm).where(Alarm.line_id == "lineCustomThresh")).first()
        assert alarm is not None
        assert alarm.severity == "WARNING"
        assert alarm.status == "OPEN"

    # 2. Ingest rate of 155.0 (>= 150.0) -> Auto-resolves the alarm
    start2 = datetime(2026, 10, 15, 9, 1, 0, tzinfo=timezone.utc).isoformat()
    end2 = datetime(2026, 10, 15, 9, 2, 0, tzinfo=timezone.utc).isoformat()
    payload2 = {
        "line_id": "lineCustomThresh",
        "events": [],
        "aggregates": [
            {
                "window_start": start2,
                "window_end": end2,
                "count": 155,
                "rate_per_min": 155.0,
                "confidence_avg": 0.95,
                "status": "NORMAL",
            }
        ],
    }
    resp2 = client.post("/api/v1/sync/batch", json=payload2)
    assert resp2.status_code == 200

    with setup_test_db() as db:
        alarm = db.scalars(select(Alarm).where(Alarm.line_id == "lineCustomThresh")).first()
        assert alarm is not None
        assert alarm.status == "RESOLVED"
        assert alarm.resolved_at is not None



