import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from fastapi.testclient import TestClient
from services.api.src.main import app
from services.api.src.db.session import get_db
from services.api.src.db.models import Base, Line, HealthSample, CountEvent, Alarm
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

FIXED_NOW = datetime(2026, 10, 15, 19, 0, 0, tzinfo=timezone.utc)  # 02:00:00 WIB (Jakarta) on 2026-10-16


class MockDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return FIXED_NOW


@pytest.fixture
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def db_session(test_engine):
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def summary_client(test_engine, db_session):
    # Line 1: Active line with distributed events and alarms
    db_session.add(Line(id="line-1", name="Line 1", daily_target=1000, is_active=True))

    # Event distribution across time windows:
    # 20 events 2 minutes ago (within last 5 min, today, shift, week)
    for i in range(20):
        db_session.add(CountEvent(line_id="line-1", track_id=i + 1, ts_utc=FIXED_NOW - timedelta(minutes=2), confidence=0.95))
    # 20 events 4 hours ago (yesterday in Jakarta WIB at 02:00, within shift [8h] and week [7d], outside today [2h])
    for i in range(20):
        db_session.add(CountEvent(line_id="line-1", track_id=20 + i + 1, ts_utc=FIXED_NOW - timedelta(hours=4), confidence=0.95))
    # 20 events 2 days ago (within week [7d], outside shift and today)
    for i in range(20):
        db_session.add(CountEvent(line_id="line-1", track_id=40 + i + 1, ts_utc=FIXED_NOW - timedelta(days=2), confidence=0.95))
    # 20 events 10 days ago (outside week [7d], shift, and today)
    for i in range(20):
        db_session.add(CountEvent(line_id="line-1", track_id=60 + i + 1, ts_utc=FIXED_NOW - timedelta(days=10), confidence=0.95))

    # Health sample: fresh sample at FIXED_NOW
    db_session.add(HealthSample(line_id="line-1", timestamp=FIXED_NOW, fps=28.5, latency_p95_ms=18.0, cpu_pct=30.0, mem_pct=45.0, stream_state="ONLINE"))

    # Alarms: 1 OPEN + 1 ACKNOWLEDGED (counted as active) + 1 RESOLVED (excluded)
    db_session.add(Alarm(line_id="line-1", alarm_type="SPEED_WARNING", severity="WARNING", message="Slow speed", status="OPEN", opened_at=FIXED_NOW))
    db_session.add(Alarm(line_id="line-1", alarm_type="CAMERA_DROP", severity="CRITICAL", message="Camera dropped", status="ACKNOWLEDGED", opened_at=FIXED_NOW, ack_at=FIXED_NOW))
    db_session.add(Alarm(line_id="line-1", alarm_type="DISCONNECT", severity="INFO", message="Reconnected", status="RESOLVED", opened_at=FIXED_NOW - timedelta(hours=1), resolved_at=FIXED_NOW))

    # Line 2: Empty line with stale health (>60s) and zero target
    db_session.add(Line(id="line-2", name="Line 2", daily_target=0, is_active=False))
    db_session.add(HealthSample(line_id="line-2", timestamp=FIXED_NOW - timedelta(seconds=90), fps=24.0, latency_p95_ms=22.0, cpu_pct=20.0, mem_pct=30.0, stream_state="ONLINE"))

    # Line 3: Line with no health samples and no events
    db_session.add(Line(id="line-3", name="Line 3", daily_target=5000, is_active=True))

    # Line 4: Line with future health sample timestamp (> 0s in the future)
    db_session.add(Line(id="line-4", name="Line 4", daily_target=2000, is_active=True))
    db_session.add(HealthSample(line_id="line-4", timestamp=FIXED_NOW + timedelta(seconds=30), fps=30.0, latency_p95_ms=15.0, cpu_pct=25.0, mem_pct=35.0, stream_state="ONLINE"))

    db_session.commit()

    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with patch("services.api.src.api.summary.datetime", MockDatetime):
        client = TestClient(app)
        yield client
    app.dependency_overrides.clear()


def test_get_line_summary_today(summary_client):
    response = summary_client.get("/api/v1/lines/line-1/summary?period=today")
    assert response.status_code == 200
    data = response.json()
    assert data["line_id"] == "line-1"
    assert data["period"] == "today"
    assert data["total_count"] == 20
    assert data["target_count"] == 1000
    assert data["target_attainment_pct"] == 2.0
    assert data["active_alarms_count"] == 2
    assert data["camera_status"] == "online"
    assert data["fps"] == 28.5
    assert data["latency_p95_ms"] == 18.0
    assert data["current_speed_cpm"] == 4.0
    assert data["target_speed_cpm"] == 120.0
    assert data["last_event_time"] is not None


def test_get_line_summary_shift(summary_client):
    response = summary_client.get("/api/v1/lines/line-1/summary?period=shift")
    assert response.status_code == 200
    data = response.json()
    assert data["period"] == "shift"
    assert data["total_count"] == 40


def test_get_line_summary_week(summary_client):
    response = summary_client.get("/api/v1/lines/line-1/summary?period=week")
    assert response.status_code == 200
    data = response.json()
    assert data["period"] == "week"
    assert data["total_count"] == 60


def test_get_line_summary_distinct_periods(summary_client):
    res_today = summary_client.get("/api/v1/lines/line-1/summary?period=today").json()
    res_shift = summary_client.get("/api/v1/lines/line-1/summary?period=shift").json()
    res_week = summary_client.get("/api/v1/lines/line-1/summary?period=week").json()

    assert res_today["total_count"] == 20
    assert res_shift["total_count"] == 40
    assert res_week["total_count"] == 60
    assert len({res_today["total_count"], res_shift["total_count"], res_week["total_count"]}) == 3


def test_get_line_summary_active_alarms(summary_client):
    response = summary_client.get("/api/v1/lines/line-1/summary")
    assert response.status_code == 200
    data = response.json()
    # 1 OPEN + 1 ACKNOWLEDGED = 2 active alarms, 1 RESOLVED is excluded
    assert data["active_alarms_count"] == 2


def test_get_line_summary_invalid_period(summary_client):
    response = summary_client.get("/api/v1/lines/line-1/summary?period=invalid")
    assert response.status_code == 422


def test_get_line_summary_future_health(summary_client):
    # Future timestamp (now - ts < 0) should be offline
    response = summary_client.get("/api/v1/lines/line-4/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["camera_status"] == "offline"


def test_get_line_summary_not_found(summary_client):
    response = summary_client.get("/api/v1/lines/non-existent/summary")
    assert response.status_code == 404
    assert response.json()["detail"] == "Line not found"


def test_get_line_summary_stale_health(summary_client):
    response = summary_client.get("/api/v1/lines/line-2/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["line_id"] == "line-2"
    assert data["camera_status"] == "offline"
    assert data["fps"] == 24.0
    assert data["latency_p95_ms"] == 22.0
    assert data["total_count"] == 0
    assert data["target_count"] == 62000  # Default fallback when daily_target is 0 or not set
    assert data["target_attainment_pct"] == 0.0
    assert data["active_alarms_count"] == 0
    assert data["last_event_time"] is None


def test_get_line_summary_no_health_no_events(summary_client):
    response = summary_client.get("/api/v1/lines/line-3/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["line_id"] == "line-3"
    assert data["camera_status"] == "offline"
    assert data["fps"] == 0.0
    assert data["latency_p95_ms"] == 0.0
    assert data["total_count"] == 0
    assert data["target_count"] == 5000
    assert data["target_attainment_pct"] == 0.0
    assert data["current_speed_cpm"] == 0.0
    assert data["active_alarms_count"] == 0
    assert data["last_event_time"] is None


def test_get_line_summary_detection_accuracy(summary_client, db_session):
    from datetime import datetime, timezone
    from services.api.src.db.models import CountEvent

    # Clear pre-seeded events so line-1 has no events initially
    db_session.query(CountEvent).filter_by(line_id="line-1").delete()
    db_session.commit()

    # Default without events should return 99.2
    res_default = summary_client.get("/api/v1/lines/line-1/summary?period=today").json()
    assert "detection_accuracy_pct" in res_default
    assert res_default["detection_accuracy_pct"] == 99.2

    # Add count events with confidence
    now = FIXED_NOW
    ev1 = CountEvent(line_id="line-1", track_id=1, ts_utc=now, confidence=0.985)
    ev2 = CountEvent(line_id="line-1", track_id=2, ts_utc=now, confidence=0.995)
    db_session.add_all([ev1, ev2])
    db_session.commit()

    res_with_events = summary_client.get("/api/v1/lines/line-1/summary?period=today").json()
    assert res_with_events["detection_accuracy_pct"] == 99.0

