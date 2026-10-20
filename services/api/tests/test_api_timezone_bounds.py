from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api.src.main import app
from services.api.src.db.session import get_db
from services.api.src.db.models import Base, Line, CountEvent
from shared.time_utils import get_jakarta_today_bounds_utc


@pytest.fixture
def tz_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = TestingSession()
    line = Line(id="line-tz", name="Timezone Test Line", daily_target=1000, is_active=True)
    session.add(line)

    today_start_utc, _ = get_jakarta_today_bounds_utc()
    ev1 = CountEvent(
        line_id="line-tz",
        track_id=1,
        ts_utc=today_start_utc - timedelta(minutes=5),
        confidence=0.95,
    )
    ev2 = CountEvent(
        line_id="line-tz",
        track_id=2,
        ts_utc=today_start_utc + timedelta(minutes=5),
        confidence=0.95,
    )
    session.add_all([ev1, ev2])
    session.commit()
    session.close()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client, "line-tz"
    app.dependency_overrides.clear()


def test_summary_today_uses_jakarta_day_bounds(tz_client):
    client, line_id = tz_client
    resp = client.get(f"/api/v1/lines/{line_id}/summary?period=today")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] == 1


def test_lines_total_today_uses_jakarta_day_bounds(tz_client):
    client, line_id = tz_client
    resp = client.get("/api/v1/lines")
    assert resp.status_code == 200
    data = resp.json()
    target_line = next((line for line in data if line["id"] == line_id), None)
    assert target_line is not None
    assert target_line["total_today"] == 1
