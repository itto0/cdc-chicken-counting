import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from services.api.src.main import app
from services.api.src.db.session import get_db
from services.api.src.db.models import Base, Line, HealthSample, CountEvent, Alarm
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def summary_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestingSession()
    db.add(Line(id="line-1", name="Line 1", daily_target=1000, is_active=True))
    now = datetime.now(timezone.utc)
    for i in range(50):
        db.add(CountEvent(line_id="line-1", track_id=i + 1, ts_utc=now - timedelta(minutes=2), confidence=0.95))
    db.add(HealthSample(line_id="line-1", timestamp=now, fps=28.5, latency_p95_ms=18.0, cpu_pct=30.0, mem_pct=45.0, stream_state="ONLINE"))
    db.add(Alarm(line_id="line-1", alarm_type="SPEED_WARNING", severity="WARNING", message="Slow speed", status="OPEN", opened_at=now))

    # Line 2: Empty line with stale health (>60s) and zero target
    db.add(Line(id="line-2", name="Line 2", daily_target=0, is_active=False))
    db.add(HealthSample(line_id="line-2", timestamp=now - timedelta(seconds=90), fps=24.0, latency_p95_ms=22.0, cpu_pct=20.0, mem_pct=30.0, stream_state="ONLINE"))

    # Line 3: Line with no health samples and no events
    db.add(Line(id="line-3", name="Line 3", daily_target=5000, is_active=True))

    db.commit()
    db.close()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_get_line_summary_today(summary_client):
    response = summary_client.get("/api/v1/lines/line-1/summary?period=today")
    assert response.status_code == 200
    data = response.json()
    assert data["line_id"] == "line-1"
    assert data["period"] == "today"
    assert data["total_count"] == 50
    assert data["target_count"] == 1000
    assert data["target_attainment_pct"] == 5.0
    assert data["active_alarms_count"] == 1
    assert data["camera_status"] == "online"
    assert data["fps"] == 28.5
    assert data["latency_p95_ms"] == 18.0
    assert data["current_speed_cpm"] > 0
    assert data["target_speed_cpm"] == 120.0
    assert data["last_event_time"] is not None


def test_get_line_summary_not_found(summary_client):
    response = summary_client.get("/api/v1/lines/non-existent/summary")
    assert response.status_code == 404
    assert response.json()["detail"] == "Line not found"


def test_get_line_summary_shift(summary_client):
    response = summary_client.get("/api/v1/lines/line-1/summary?period=shift")
    assert response.status_code == 200
    data = response.json()
    assert data["period"] == "shift"
    assert data["total_count"] == 50


def test_get_line_summary_week(summary_client):
    response = summary_client.get("/api/v1/lines/line-1/summary?period=week")
    assert response.status_code == 200
    data = response.json()
    assert data["period"] == "week"
    assert data["total_count"] == 50


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
