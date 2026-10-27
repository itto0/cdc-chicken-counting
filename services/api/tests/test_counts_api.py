import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from services.api.src.main import app
from services.api.src.db.session import get_db
from services.api.src.db.models import Base, Line, CountEvent, CountAggregate
from services.api.src.api.auth import get_current_user, UserDTO
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

@pytest.fixture
def counts_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestingSession()
    db.add(Line(id="line-1", name="Line 1", daily_target=1000, is_active=True))
    now = datetime(2026, 10, 16, 10, 0, 0, tzinfo=timezone.utc)
    for i in range(15):
        db.add(CountEvent(line_id="line-1", track_id=i + 1, ts_utc=now + timedelta(minutes=i), confidence=0.99))
    db.add(CountAggregate(
        line_id="line-1",
        window_start=now,
        window_end=now + timedelta(minutes=60),
        count=15,
        rate_per_min=0.25,
        confidence_avg=0.99,
        status="NORMAL"
    ))
    db.add(Line(id="line-empty", name="Line Empty", daily_target=500, is_active=True))

    # Line for testing deterministic tie-breaker ordering with identical timestamps
    db.add(Line(id="line-tie", name="Line Tie", daily_target=100, is_active=True))
    same_ts = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)
    db.add(CountEvent(id=101, line_id="line-tie", track_id=1, ts_utc=same_ts, confidence=0.99))
    db.add(CountEvent(id=102, line_id="line-tie", track_id=2, ts_utc=same_ts, confidence=0.99))
    db.add(CountEvent(id=103, line_id="line-tie", track_id=3, ts_utc=same_ts, confidence=0.99))

    # Line for testing >100 aggregate buckets (e.g. 168 hours for 7 days)
    db.add(Line(id="line-7day", name="Line 7 Day", daily_target=10000, is_active=True))
    base_window = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    for h in range(168):
        db.add(
            CountAggregate(
                line_id="line-7day",
                window_start=base_window + timedelta(hours=h),
                window_end=base_window + timedelta(hours=h + 1),
                count=100 + h,
                rate_per_min=1.5,
                confidence_avg=0.99,
                status="NORMAL",
            )
        )

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
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def override_counts_auth():
    app.dependency_overrides[get_current_user] = lambda: UserDTO(
        id="test_user", username="tester", role="operator", is_active=True
    )
    yield
    app.dependency_overrides.pop(get_current_user, None)

def test_get_line_counts(counts_client):
    response = counts_client.get("/api/v1/lines/line-1/counts?page=1&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "aggregates" in data
    assert "events" in data
    assert "pagination" in data
    assert len(data["events"]) == 10
    assert data["pagination"]["total"] == 15
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["limit"] == 10
    assert len(data["aggregates"]) == 1
    assert data["aggregates"][0]["count"] == 15
    assert data["aggregates"][0]["status"] == "NORMAL"

def test_get_line_counts_pagination_page_2(counts_client):
    response = counts_client.get("/api/v1/lines/line-1/counts?page=2&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["events"]) == 5
    assert data["pagination"]["total"] == 15
    assert data["pagination"]["page"] == 2
    assert data["pagination"]["limit"] == 10

def test_get_line_counts_time_filtering(counts_client):
    from_time = "2026-10-16T10:05:00Z"
    to_time = "2026-10-16T10:10:00Z"
    response = counts_client.get(f"/api/v1/lines/line-1/counts?from={from_time}&to={to_time}")
    assert response.status_code == 200
    data = response.json()
    # Timestamps are 10:00 to 10:14. Between 10:05 and 10:10 inclusive, there are 6 events (10:05, 10:06, 10:07, 10:08, 10:09, 10:10)
    assert data["pagination"]["total"] == 6
    assert len(data["events"]) == 6

def test_get_line_counts_not_found(counts_client):
    response = counts_client.get("/api/v1/lines/non-existent-line/counts")
    assert response.status_code == 404
    assert response.json()["detail"] == "Line not found"

def test_get_line_counts_empty(counts_client):
    response = counts_client.get("/api/v1/lines/line-empty/counts")
    assert response.status_code == 200
    data = response.json()
    assert data["aggregates"] == []
    assert data["events"] == []
    assert data["pagination"]["total"] == 0


def test_get_line_counts_invalid_from_datetime(counts_client):
    response = counts_client.get("/api/v1/lines/line-1/counts?from=invalid-date")
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Invalid datetime format for from_time. Expected ISO 8601 format." in detail


def test_get_line_counts_invalid_to_datetime(counts_client):
    response = counts_client.get("/api/v1/lines/line-1/counts?to=invalid-date")
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Invalid datetime format for to_time. Expected ISO 8601 format." in detail


def test_get_line_counts_invalid_page(counts_client):
    response = counts_client.get("/api/v1/lines/line-1/counts?page=0")
    assert response.status_code == 422


def test_get_line_counts_invalid_granularity(counts_client):
    response = counts_client.get("/api/v1/lines/line-1/counts?granularity=invalid_val")
    assert response.status_code == 422


def test_get_line_counts_valid_granularity(counts_client):
    for gran in ["minute", "hourly", "daily"]:
        response = counts_client.get(f"/api/v1/lines/line-1/counts?granularity={gran}")
        assert response.status_code == 200


def test_get_line_counts_deterministic_tie_breaker_ordering(counts_client):
    response = counts_client.get("/api/v1/lines/line-tie/counts")
    assert response.status_code == 200
    events = response.json()["events"]
    assert len(events) == 3
    # Same ts_utc, ordered descending by id (103, 102, 101)
    assert [e["id"] for e in events] == [103, 102, 101]


def test_get_line_counts_aggregates_supports_up_to_500_buckets(counts_client):
    response = counts_client.get("/api/v1/lines/line-7day/counts")
    assert response.status_code == 200
    aggregates = response.json()["aggregates"]
    # All 168 hourly buckets returned without 100-bucket truncation
    assert len(aggregates) == 168
    assert aggregates[0]["count"] == 100
    assert aggregates[-1]["count"] == 267


def test_get_line_counts_hourly_aggregation_from_events(counts_client):
    # Test line with events spread across 2 hours in UTC: 08:15, 08:45, and 09:30
    # In Jakarta time (UTC+7): 15:15, 15:45, and 16:30
    db = next(app.dependency_overrides[get_db]())
    db.add(Line(id="line-hourly", name="Line Hourly", daily_target=5000, is_active=True))
    t1 = datetime(2026, 10, 21, 8, 15, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 10, 21, 8, 45, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 10, 21, 9, 30, 0, tzinfo=timezone.utc)
    db.add(CountEvent(line_id="line-hourly", track_id=1, ts_utc=t1, confidence=0.98))
    db.add(CountEvent(line_id="line-hourly", track_id=2, ts_utc=t2, confidence=0.97))
    db.add(CountEvent(line_id="line-hourly", track_id=3, ts_utc=t3, confidence=0.99))
    db.commit()

    from_time = "2026-10-21T08:00:00Z"
    to_time = "2026-10-21T10:00:00Z"
    response = counts_client.get(f"/api/v1/lines/line-hourly/counts?granularity=hourly&from={from_time}&to={to_time}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["aggregates"]) == 2
    # Hour 15:00 WIB has 2 events
    assert data["aggregates"][0]["count"] == 2
    assert "15:00:00" in data["aggregates"][0]["bucket"]
    # Hour 16:00 WIB has 1 event
    assert data["aggregates"][1]["count"] == 1
    assert "16:00:00" in data["aggregates"][1]["bucket"]


def test_get_line_counts_period_today(counts_client):
    response = counts_client.get("/api/v1/lines/line-1/counts?granularity=hourly&period=today")
    assert response.status_code == 200
    data = response.json()
    assert "aggregates" in data


def test_get_line_counts_period_today_filtering(counts_client):
    db = next(app.dependency_overrides[get_db]())
    db.add(Line(id="line-period", name="Line Period", daily_target=5000, is_active=True))
    now_utc = datetime.now(timezone.utc)
    # Event today in Jakarta
    db.add(CountEvent(line_id="line-period", track_id=1, ts_utc=now_utc, confidence=0.98))
    # Event 2 days ago in Jakarta
    db.add(CountEvent(line_id="line-period", track_id=2, ts_utc=now_utc - timedelta(days=2), confidence=0.98))
    db.commit()

    response = counts_client.get("/api/v1/lines/line-period/counts?granularity=hourly&period=today")
    assert response.status_code == 200
    data = response.json()
    assert "aggregates" in data
    # Only today's event should be returned
    assert data["pagination"]["total"] == 1
    assert len(data["aggregates"]) == 1
    assert data["aggregates"][0]["count"] == 1


def test_get_line_counts_period_shift_filtering(counts_client):
    db = next(app.dependency_overrides[get_db]())
    db.add(Line(id="line-shift", name="Line Shift", daily_target=5000, is_active=True))
    now_utc = datetime.now(timezone.utc)
    # Event within 8 hours
    db.add(CountEvent(line_id="line-shift", track_id=1, ts_utc=now_utc - timedelta(hours=2), confidence=0.98))
    # Event outside 8 hours (e.g. 10 hours ago)
    db.add(CountEvent(line_id="line-shift", track_id=2, ts_utc=now_utc - timedelta(hours=10), confidence=0.98))
    db.commit()

    response = counts_client.get("/api/v1/lines/line-shift/counts?granularity=hourly&period=shift")
    assert response.status_code == 200
    data = response.json()
    assert "aggregates" in data
    assert data["pagination"]["total"] == 1
    assert len(data["aggregates"]) == 1
    assert data["aggregates"][0]["count"] == 1


def test_get_line_counts_period_week_filtering(counts_client):
    db = next(app.dependency_overrides[get_db]())
    db.add(Line(id="line-week", name="Line Week", daily_target=5000, is_active=True))
    now_utc = datetime.now(timezone.utc)
    # Event within 7 days
    db.add(CountEvent(line_id="line-week", track_id=1, ts_utc=now_utc - timedelta(days=3), confidence=0.98))
    # Event outside 7 days (e.g. 9 days ago)
    db.add(CountEvent(line_id="line-week", track_id=2, ts_utc=now_utc - timedelta(days=9), confidence=0.98))
    db.commit()

    response = counts_client.get("/api/v1/lines/line-week/counts?granularity=hourly&period=week")
    assert response.status_code == 200
    data = response.json()
    assert "aggregates" in data
    assert data["pagination"]["total"] == 1
    assert len(data["aggregates"]) == 1
    assert data["aggregates"][0]["count"] == 1


def test_get_line_counts_hourly_fallback_to_aggregates(counts_client):
    db = next(app.dependency_overrides[get_db]())
    db.add(Line(id="line-fallback", name="Line Fallback", daily_target=5000, is_active=True))
    # No CountEvents, only CountAggregate records in the same Jakarta hour
    t1 = datetime(2026, 10, 21, 8, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 10, 21, 8, 20, 0, tzinfo=timezone.utc)
    db.add(CountAggregate(
        line_id="line-fallback",
        window_start=t1,
        window_end=t1 + timedelta(minutes=10),
        count=10,
        rate_per_min=1.0,
        confidence_avg=0.98,
        status="NORMAL"
    ))
    db.add(CountAggregate(
        line_id="line-fallback",
        window_start=t2,
        window_end=t2 + timedelta(minutes=10),
        count=20,
        rate_per_min=2.0,
        confidence_avg=0.99,
        status="NORMAL"
    ))
    db.commit()

    from_time = "2026-10-21T08:00:00Z"
    to_time = "2026-10-21T09:00:00Z"
    response = counts_client.get(f"/api/v1/lines/line-fallback/counts?granularity=hourly&from={from_time}&to={to_time}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["aggregates"]) == 1
    # Both records merged into the 15:00 WIB bucket
    assert data["aggregates"][0]["count"] == 30
    assert data["aggregates"][0]["rate_per_min"] == 1.5
    assert "15:00:00" in data["aggregates"][0]["bucket"]


def test_get_line_counts_invalid_period(counts_client):
    response = counts_client.get("/api/v1/lines/line-1/counts?period=invalid")
    assert response.status_code == 422


@pytest.fixture
def test_db_session(tmp_path):
    test_db_file = tmp_path / "test_single_counts.db"
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
    app.dependency_overrides.pop(get_db, None)
    test_engine.dispose()


@pytest.fixture
def client(test_db_session):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return TestClient(app)


@pytest.fixture
def test_db(test_db_session):
    db = test_db_session()
    try:
        yield db
    finally:
        db.close()


def test_create_single_count_event_broadcasts_and_updates_total(client, test_db):
    from services.api.src.api.live import broadcaster
    from services.api.src.db.models import Line

    # Ensure line exists
    line = Line(id="line_single_test", name="Line Single Test", is_active=True)
    test_db.add(line)
    test_db.commit()

    broadcaster.clear()
    queue = broadcaster.subscribe("line_single_test")

    payload = {
        "track_id": 501,
        "confidence": 0.98,
        "ts_utc": datetime.now(timezone.utc).isoformat(),
    }

    resp = client.post("/api/v1/lines/line_single_test/events", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["success"] is True
    assert data["ingested"] is True
    assert data["total_today"] == 1

    # Verify SSE broadcast
    assert not queue.empty()
    event_type, event_data = queue.get_nowait()
    assert event_type == "count"
    assert event_data["track_id"] == 501
    assert event_data["total_today"] == 1
    assert event_data["rate_per_min"] == 0.0
    assert event_data["status"] == "NORMAL"
    assert event_data["ts_utc"].endswith("Z")


def test_create_single_count_event_unauthenticated_returns_401(client, test_db):
    from services.api.src.db.models import Line

    line = Line(id="line_single_test_auth", name="Line Auth Test", is_active=True)
    test_db.add(line)
    test_db.commit()

    app.dependency_overrides.pop(get_current_user, None)
    try:
        payload = {
            "track_id": 501,
            "confidence": 0.98,
            "ts_utc": datetime.now(timezone.utc).isoformat(),
        }
        resp = client.post("/api/v1/lines/line_single_test_auth/events", json=payload)
        assert resp.status_code == 401
    finally:
        app.dependency_overrides[get_current_user] = lambda: UserDTO(
            id="test_user", username="tester", role="operator", is_active=True
        )


def test_create_single_count_event_duplicate_skips_broadcast(client, test_db):
    from services.api.src.api.live import broadcaster
    from services.api.src.db.models import Line

    line = Line(id="line_single_test", name="Line Single Test", is_active=True)
    test_db.add(line)
    test_db.commit()

    broadcaster.clear()
    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {"track_id": 502, "confidence": 0.98, "ts_utc": now_iso}

    resp1 = client.post("/api/v1/lines/line_single_test/events", json=payload)
    assert resp1.status_code == 201
    assert resp1.json()["ingested"] is True

    queue = broadcaster.subscribe("line_single_test")

    # Resend identical
    resp2 = client.post("/api/v1/lines/line_single_test/events", json=payload)
    assert resp2.status_code == 200
    assert resp2.json()["ingested"] is False
    assert queue.empty()


def test_create_single_count_event_nonexistent_line_returns_404(client, test_db):
    payload = {
        "track_id": 999,
        "confidence": 0.98,
        "ts_utc": datetime.now(timezone.utc).isoformat(),
    }
    resp = client.post("/api/v1/lines/non_existent_line/events", json=payload)
    assert resp.status_code == 404


def test_create_single_count_event_missing_ts_utc_returns_422(client, test_db):
    from services.api.src.db.models import Line

    line = Line(id="line_single_test_no_ts", name="Line No TS", is_active=True)
    test_db.add(line)
    test_db.commit()

    payload = {"track_id": 601, "confidence": 0.95}

    resp = client.post("/api/v1/lines/line_single_test_no_ts/events", json=payload)
    assert resp.status_code == 422


def test_create_single_count_event_field_validations_return_422(client, test_db):
    from services.api.src.db.models import Line

    line = Line(id="line_single_test_val", name="Line Validation Test", is_active=True)
    test_db.add(line)
    test_db.commit()

    now_iso = datetime.now(timezone.utc).isoformat()

    # track_id < 1
    resp1 = client.post(
        "/api/v1/lines/line_single_test_val/events",
        json={"track_id": 0, "confidence": 0.95, "ts_utc": now_iso},
    )
    assert resp1.status_code == 422

    resp2 = client.post(
        "/api/v1/lines/line_single_test_val/events",
        json={"track_id": -5, "confidence": 0.95, "ts_utc": now_iso},
    )
    assert resp2.status_code == 422

    # confidence < 0.0
    resp3 = client.post(
        "/api/v1/lines/line_single_test_val/events",
        json={"track_id": 1, "confidence": -0.1, "ts_utc": now_iso},
    )
    assert resp3.status_code == 422

    # confidence > 1.0
    resp4 = client.post(
        "/api/v1/lines/line_single_test_val/events",
        json={"track_id": 1, "confidence": 1.1, "ts_utc": now_iso},
    )
    assert resp4.status_code == 422


def test_create_single_count_event_invalid_ts_utc_returns_400(client, test_db):
    from services.api.src.db.models import Line

    line = Line(id="line_single_test_bad_ts", name="Line Bad TS", is_active=True)
    test_db.add(line)
    test_db.commit()

    payload = {"track_id": 701, "confidence": 0.95, "ts_utc": "not-a-valid-datetime"}
    resp = client.post("/api/v1/lines/line_single_test_bad_ts/events", json=payload)
    assert resp.status_code == 400
    assert "Invalid datetime format for ts_utc" in resp.json()["detail"]


def test_create_single_count_event_with_existing_aggregate_rates(client, test_db):
    from services.api.src.api.live import broadcaster
    from services.api.src.db.models import Line, CountAggregate

    line = Line(id="line_with_agg", name="Line With Agg", is_active=True)
    test_db.add(line)
    now = datetime.now(timezone.utc)
    agg = CountAggregate(
        line_id="line_with_agg",
        window_start=now - timedelta(minutes=5),
        window_end=now,
        count=50,
        rate_per_min=10.0,
        confidence_avg=0.99,
        status="WARNING",
    )
    test_db.add(agg)
    test_db.commit()

    broadcaster.clear()
    queue = broadcaster.subscribe("line_with_agg")

    payload = {
        "track_id": 801,
        "confidence": 0.99,
        "ts_utc": now.isoformat(),
    }

    resp = client.post("/api/v1/lines/line_with_agg/events", json=payload)
    assert resp.status_code == 201

    assert not queue.empty()
    event_type, event_data = queue.get_nowait()
    assert event_type == "count"
    assert event_data["rate_per_min"] == 10.0
    assert event_data["status"] == "WARNING"


