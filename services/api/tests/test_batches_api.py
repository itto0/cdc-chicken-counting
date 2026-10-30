from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from services.api.src.db.models import Base, Line, CountingBatch, CountEvent
from services.api.src.db.session import get_db
from services.api.src.main import app, init_db


@pytest.fixture
def client_and_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(target_engine=engine)
    TestingSession = sessionmaker(bind=engine)
    db = TestingSession()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    # Seed data
    line = db.query(Line).filter_by(id="line-1").first()
    if not line:
        line = Line(id="line-1", name="Line 1")
        db.add(line)
        db.flush()

    t0 = datetime(2026, 10, 30, 10, 0, 0, tzinfo=timezone.utc)
    b1 = CountingBatch(
        batch_id="batch_1",
        line_id="line-1",
        start_time=t0,
        finish_time=t0 + timedelta(minutes=10),
        total_count=300,
        status="COMPLETED",
    )
    b2 = CountingBatch(
        batch_id="batch_2",
        line_id="line-1",
        start_time=t0 + timedelta(hours=1),
        finish_time=None,
        total_count=50,
        status="ACTIVE",
    )
    db.add_all([b1, b2])

    # Add 2 events linked to batch_1
    ev1 = CountEvent(track_id=1, ts_utc=t0, confidence=0.9, line_id="line-1", class_name="chicken", batch_id="batch_1")
    ev2 = CountEvent(track_id=2, ts_utc=t0 + timedelta(minutes=1), confidence=0.9, line_id="line-1", class_name="chicken", batch_id="batch_1")
    db.add_all([ev1, ev2])
    db.commit()

    yield client, db

    app.dependency_overrides.clear()


def test_get_batches_list_default_completed(client_and_db):
    client, _ = client_and_db
    resp = client.get("/api/v1/lines/line-1/batches")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["batch_id"] == "batch_1"
    assert data["items"][0]["status"] == "COMPLETED"


def test_get_batches_list_all_and_active(client_and_db):
    client, _ = client_and_db
    resp_all = client.get("/api/v1/lines/line-1/batches?status=ALL")
    assert resp_all.status_code == 200
    assert resp_all.json()["total"] == 2

    resp_active = client.get("/api/v1/lines/line-1/batches?status=ACTIVE")
    assert resp_active.status_code == 200
    assert resp_active.json()["total"] == 1
    assert resp_active.json()["items"][0]["batch_id"] == "batch_2"


def test_get_batches_date_range_filter(client_and_db):
    client, _ = client_and_db
    resp = client.get("/api/v1/lines/line-1/batches?status=ALL&start_date=2026-10-30T10:30:00Z")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["batch_id"] == "batch_2"


def test_get_latest_batch(client_and_db):
    client, _ = client_and_db
    resp = client.get("/api/v1/lines/line-1/batches/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["batch_id"] == "batch_2"


def test_get_latest_batch_empty(client_and_db):
    client, db = client_and_db
    line2 = Line(id="line-2", name="Line 2")
    db.add(line2)
    db.commit()

    resp = client.get("/api/v1/lines/line-2/batches/latest")
    assert resp.status_code == 200
    assert resp.json() is None


def test_get_batch_detail(client_and_db):
    client, _ = client_and_db
    resp = client.get("/api/v1/lines/line-1/batches/batch_1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["batch_id"] == "batch_1"
    assert data["duration_seconds"] == 600.0
    assert data["rate_per_minute"] == 30.0
    assert data["events_count"] == 2


def test_get_batch_detail_not_found(client_and_db):
    client, _ = client_and_db
    resp = client.get("/api/v1/lines/line-1/batches/nonexistent")
    assert resp.status_code == 404


def test_get_batch_detail_active_duration(client_and_db):
    client, _ = client_and_db
    resp = client.get("/api/v1/lines/line-1/batches/batch_2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["batch_id"] == "batch_2"
    assert data["status"] == "ACTIVE"
    assert data["finish_time"] is None
    assert data["duration_seconds"] >= 0.0
    assert data["events_count"] == 0
    assert data["rate_per_minute"] >= 0.0


def test_get_batches_pagination(client_and_db):
    client, _ = client_and_db
    resp_p1 = client.get("/api/v1/lines/line-1/batches?status=ALL&page=1&page_size=1")
    assert resp_p1.status_code == 200
    d1 = resp_p1.json()
    assert d1["total"] == 2
    assert d1["pages"] == 2
    assert d1["page"] == 1
    assert d1["page_size"] == 1
    assert len(d1["items"]) == 1
    # Sorted by start_time descending, so batch_2 (started 1hr later) is first
    assert d1["items"][0]["batch_id"] == "batch_2"

    resp_p2 = client.get("/api/v1/lines/line-1/batches?status=ALL&page=2&page_size=1")
    assert resp_p2.status_code == 200
    d2 = resp_p2.json()
    assert d2["page"] == 2
    assert len(d2["items"]) == 1
    assert d2["items"][0]["batch_id"] == "batch_1"


def test_get_batches_end_date_filter(client_and_db):
    client, _ = client_and_db
    resp = client.get("/api/v1/lines/line-1/batches?status=ALL&end_date=2026-10-30T10:30:00Z")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["batch_id"] == "batch_1"


def test_get_batches_list_trailing_slash(client_and_db):
    client, _ = client_and_db
    resp = client.get("/api/v1/lines/line-1/batches/")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

