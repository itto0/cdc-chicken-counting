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


def test_create_line_success(lines_client):
    client = lines_client
    payload = {
        "id": "line-new-1",
        "name": "New Conveyor 1",
        "daily_target": 75000,
        "video_url": "rtsp://camera1/stream",
        "line_coords": "0,240,640,240",
        "line_direction": "down",
        "is_active": True,
    }
    resp = client.post("/api/v1/lines", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] == "line-new-1"
    assert data["name"] == "New Conveyor 1"
    assert data["daily_target"] == 75000
    assert data["video_url"] == "rtsp://camera1/stream"
    assert data["line_coords"] == "0,240,640,240"
    assert data["line_direction"] == "down"
    assert data["is_active"] is True


def test_create_line_duplicate_id(lines_client):
    client = lines_client
    payload = {
        "id": "line-dup",
        "name": "Conveyor Duplicate",
        "daily_target": 50000,
    }
    resp1 = client.post("/api/v1/lines", json=payload)
    assert resp1.status_code == 201

    resp2 = client.post("/api/v1/lines", json=payload)
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"].lower()


def test_create_line_invalid_coords_and_direction(lines_client):
    client = lines_client
    # Bad coordinates (only 2 numbers)
    resp = client.post("/api/v1/lines", json={
        "id": "line-bad-coords",
        "name": "Bad Coords",
        "line_coords": "100,200",
    })
    assert resp.status_code == 422

    # Bad direction
    resp2 = client.post("/api/v1/lines", json={
        "id": "line-bad-dir",
        "name": "Bad Dir",
        "line_direction": "diagonal_up",
    })
    assert resp2.status_code == 422


def test_soft_delete_line(lines_client):
    client = lines_client
    line_id = "line-to-delete"
    client.post("/api/v1/lines", json={"id": line_id, "name": "Line To Delete"})

    resp = client.delete(f"/api/v1/lines/{line_id}")
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    # Check detail shows is_active is False
    detail = client.get(f"/api/v1/lines/{line_id}").json()
    assert detail["is_active"] is False


def test_delete_nonexistent_line(lines_client):
    client = lines_client
    resp = client.delete("/api/v1/lines/non-existent-line")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Line not found"


def test_update_line_extended_fields(lines_client):
    client = lines_client
    update_payload = {
        "video_url": "rtsp://camera2/stream",
        "line_coords": "10,20,300,400",
        "line_direction": "up",
        "is_active": False,
    }
    resp = client.put("/api/v1/lines/line-1", json=update_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["video_url"] == "rtsp://camera2/stream"
    assert data["line_coords"] == "10,20,300,400"
    assert data["line_direction"] == "up"
    assert data["is_active"] is False


def test_update_line_invalid_coords_and_direction(lines_client):
    client = lines_client
    # Invalid coords on update
    resp1 = client.put("/api/v1/lines/line-1", json={"line_coords": "not,valid,coords,abc"})
    assert resp1.status_code == 422

    # Invalid direction on update
    resp2 = client.put("/api/v1/lines/line-1", json={"line_direction": "diagonal"})
    assert resp2.status_code == 422


