import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api.src.main import app
from services.api.src.db.session import get_db
from services.api.src.db.models import Base, Line
from services.api.src.api.auth import require_role


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        with TestingSession() as session:
            yield session

    # Bypass auth for testing lines API
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_role(["admin"])] = lambda: {"username": "admin", "role": "admin"}
    app.dependency_overrides[require_role(["admin", "operator"])] = lambda: {"username": "operator", "role": "operator"}

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_create_line_with_custom_thresholds(client: TestClient):
    payload = {
        "id": "line-custom-1",
        "name": "Custom Line 1",
        "daily_target": 50000,
        "rate_warning_threshold": 125.0,
        "rate_critical_threshold": 100.0,
    }
    res = client.post("/api/v1/lines", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["rate_warning_threshold"] == 125.0
    assert data["rate_critical_threshold"] == 100.0
    assert data["effective_rate_warning"] == 125.0
    assert data["effective_rate_critical"] == 100.0


def test_create_line_default_thresholds(client: TestClient):
    payload = {
        "id": "line-default-1",
        "name": "Default Line 1",
        "daily_target": 50000,
    }
    res = client.post("/api/v1/lines", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["rate_warning_threshold"] is None
    assert data["rate_critical_threshold"] is None
    assert data["effective_rate_warning"] == 130.0
    assert data["effective_rate_critical"] == 110.0


def test_create_line_validation_fails_when_critical_greater_or_equal_warning(client: TestClient):
    payload = {
        "id": "line-invalid",
        "name": "Invalid Line",
        "daily_target": 50000,
        "rate_warning_threshold": 100.0,
        "rate_critical_threshold": 120.0,
    }
    res = client.post("/api/v1/lines", json=payload)
    assert res.status_code == 422


def test_create_line_validation_fails_for_non_positive_threshold(client: TestClient):
    payload = {
        "id": "line-invalid-pos",
        "name": "Invalid Non-Positive",
        "daily_target": 50000,
        "rate_warning_threshold": -10.0,
    }
    res = client.post("/api/v1/lines", json=payload)
    assert res.status_code == 422


def test_update_line_thresholds_and_reset_to_null(client: TestClient):
    # First create line
    create_res = client.post("/api/v1/lines", json={
        "id": "line-update-1",
        "name": "Update Line",
        "daily_target": 50000,
    })
    assert create_res.status_code == 201

    # Update with custom thresholds
    update_res = client.put("/api/v1/lines/line-update-1", json={
        "rate_warning_threshold": 140.0,
        "rate_critical_threshold": 120.0,
    })
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["rate_warning_threshold"] == 140.0
    assert updated["rate_critical_threshold"] == 120.0
    assert updated["effective_rate_warning"] == 140.0
    assert updated["effective_rate_critical"] == 120.0

    # Reset back to null (inherit system default)
    reset_res = client.put("/api/v1/lines/line-update-1", json={
        "rate_warning_threshold": None,
        "rate_critical_threshold": None,
    })
    assert reset_res.status_code == 200
    reset_data = reset_res.json()
    assert reset_data["rate_warning_threshold"] is None
    assert reset_data["rate_critical_threshold"] is None
    assert reset_data["effective_rate_warning"] == 130.0
    assert reset_data["effective_rate_critical"] == 110.0


def test_get_lines_includes_effective_thresholds(client: TestClient):
    client.post("/api/v1/lines", json={
        "id": "line-list-1",
        "name": "List Line 1",
        "daily_target": 50000,
        "rate_warning_threshold": 150.0,
        "rate_critical_threshold": 125.0,
    })
    res = client.get("/api/v1/lines")
    assert res.status_code == 200
    lines = res.json()
    match = next(l for l in lines if l["id"] == "line-list-1")
    assert match["rate_warning_threshold"] == 150.0
    assert match["rate_critical_threshold"] == 125.0
    assert match["effective_rate_warning"] == 150.0
    assert match["effective_rate_critical"] == 125.0
