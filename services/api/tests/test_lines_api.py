import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from services.api.src.main import app
from services.api.src.db.session import get_db
from services.api.src.db.models import Base, Line, HealthSample, CountEvent
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def lines_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Seed initial test line
    db = TestingSession()
    db.add(Line(id="line-1", name="Main Processing Line", daily_target=62000, is_active=True))
    db.add(HealthSample(line_id="line-1", timestamp=datetime.now(timezone.utc), fps=30.0, latency_p95_ms=15.0, cpu_pct=25.0, mem_pct=40.0, stream_state="ONLINE"))
    db.add(CountEvent(line_id="line-1", track_id=1, ts_utc=datetime.now(timezone.utc), confidence=0.98))

    # Line 2: stale health sample (>60s ago)
    db.add(Line(id="line-2", name="Secondary Line", daily_target=45000, is_active=True))
    db.add(HealthSample(line_id="line-2", timestamp=datetime.now(timezone.utc) - timedelta(seconds=120), fps=30.0, latency_p95_ms=15.0, cpu_pct=25.0, mem_pct=40.0, stream_state="ONLINE"))

    # Line 3: no health sample, no events
    db.add(Line(id="line-3", name="Idle Line", daily_target=30000, is_active=False))

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


def test_list_lines(lines_client):
    response = lines_client.get("/api/v1/lines")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    line1 = next(item for item in data if item["id"] == "line-1")
    assert line1["name"] == "Main Processing Line"
    assert line1["status"] in ["online", "offline", "degraded"]
    assert line1["daily_target"] == 62000
    assert line1["total_today"] == 1


def test_list_lines_stale_and_empty(lines_client):
    response = lines_client.get("/api/v1/lines")
    assert response.status_code == 200
    data = response.json()
    line2 = next(item for item in data if item["id"] == "line-2")
    assert line2["status"] == "offline"
    assert line2["total_today"] == 0

    line3 = next(item for item in data if item["id"] == "line-3")
    assert line3["status"] == "offline"
    assert line3["last_ping"] is None
    assert line3["total_today"] == 0


def test_get_line_detail(lines_client):
    response = lines_client.get("/api/v1/lines/line-1")
    assert response.status_code == 200
    assert response.json()["id"] == "line-1"
    assert response.json()["name"] == "Main Processing Line"
    assert response.json()["daily_target"] == 62000
    assert response.json()["is_active"] is True


def test_update_line(lines_client):
    update_payload = {"name": "Updated Line 1", "daily_target": 70000, "is_active": True}
    response = lines_client.put("/api/v1/lines/line-1", json=update_payload)
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Line 1"
    assert response.json()["daily_target"] == 70000
    assert response.json()["is_active"] is True


def test_update_line_partial(lines_client):
    update_payload = {"daily_target": 80000}
    response = lines_client.put("/api/v1/lines/line-1", json=update_payload)
    assert response.status_code == 200
    assert response.json()["name"] == "Main Processing Line"
    assert response.json()["daily_target"] == 80000
    assert response.json()["is_active"] is True


def test_get_nonexistent_line(lines_client):
    response = lines_client.get("/api/v1/lines/non-existent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Line not found"


def test_update_nonexistent_line(lines_client):
    response = lines_client.put("/api/v1/lines/non-existent", json={"name": "Ghost"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Line not found"


def test_update_line_daily_target_validation(lines_client):
    # daily_target <= 0 should fail validation with 422
    res_zero = lines_client.put("/api/v1/lines/line-1", json={"daily_target": 0})
    assert res_zero.status_code == 422

    res_negative = lines_client.put("/api/v1/lines/line-1", json={"daily_target": -100})
    assert res_negative.status_code == 422

    # daily_target > 0 succeeds
    res_valid = lines_client.put("/api/v1/lines/line-1", json={"daily_target": 90000})
    assert res_valid.status_code == 200
    assert res_valid.json()["daily_target"] == 90000
