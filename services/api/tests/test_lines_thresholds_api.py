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


def test_get_line_detail_asserts_threshold_fields_and_effective_rates(client: TestClient):
    # Test line with custom overrides
    create_custom = client.post("/api/v1/lines", json={
        "id": "line-detail-custom",
        "name": "Detail Custom",
        "daily_target": 55000,
        "rate_warning_threshold": 145.0,
        "rate_critical_threshold": 115.0,
    })
    assert create_custom.status_code == 201

    res_custom = client.get("/api/v1/lines/line-detail-custom")
    assert res_custom.status_code == 200
    data_custom = res_custom.json()
    assert data_custom["id"] == "line-detail-custom"
    assert data_custom["rate_warning_threshold"] == 145.0
    assert data_custom["rate_critical_threshold"] == 115.0
    assert data_custom["effective_rate_warning"] == 145.0
    assert data_custom["effective_rate_critical"] == 115.0

    # Test line with default thresholds (None overrides)
    create_default = client.post("/api/v1/lines", json={
        "id": "line-detail-default",
        "name": "Detail Default",
        "daily_target": 55000,
    })
    assert create_default.status_code == 201

    res_default = client.get("/api/v1/lines/line-detail-default")
    assert res_default.status_code == 200
    data_default = res_default.json()
    assert data_default["id"] == "line-detail-default"
    assert data_default["rate_warning_threshold"] is None
    assert data_default["rate_critical_threshold"] is None
    assert data_default["effective_rate_warning"] == 130.0
    assert data_default["effective_rate_critical"] == 110.0


def test_update_line_partial_fails_when_critical_ge_existing_warning(client: TestClient):
    client.post("/api/v1/lines", json={
        "id": "line-partial-test-1",
        "name": "Partial Test 1",
        "daily_target": 50000,
        "rate_warning_threshold": 130.0,
        "rate_critical_threshold": 110.0,
    })

    # Partial update: new critical (135.0) >= existing warning (130.0) -> fails 422
    update_res = client.put("/api/v1/lines/line-partial-test-1", json={
        "rate_critical_threshold": 135.0,
    })
    assert update_res.status_code == 422
    assert "rate_critical_threshold must be strictly less than rate_warning_threshold" in update_res.json()["detail"]


def test_update_line_partial_fails_when_warning_le_existing_critical(client: TestClient):
    client.post("/api/v1/lines", json={
        "id": "line-partial-test-2",
        "name": "Partial Test 2",
        "daily_target": 50000,
        "rate_warning_threshold": 130.0,
        "rate_critical_threshold": 110.0,
    })

    # Partial update: new warning (105.0) <= existing critical (110.0) -> fails 422
    update_res = client.put("/api/v1/lines/line-partial-test-2", json={
        "rate_warning_threshold": 105.0,
    })
    assert update_res.status_code == 422
    assert "rate_critical_threshold must be strictly less than rate_warning_threshold" in update_res.json()["detail"]


def test_threshold_boundary_equal_fails_validation(client: TestClient):
    # Create with equal warning and critical
    res_create = client.post("/api/v1/lines", json={
        "id": "line-boundary-create",
        "name": "Boundary Create",
        "daily_target": 50000,
        "rate_warning_threshold": 120.0,
        "rate_critical_threshold": 120.0,
    })
    assert res_create.status_code == 422

    # Line setup for PUT boundary tests
    client.post("/api/v1/lines", json={
        "id": "line-boundary-put",
        "name": "Boundary Line",
        "daily_target": 50000,
        "rate_warning_threshold": 130.0,
        "rate_critical_threshold": 110.0,
    })

    # Full PUT with equal values
    put_both = client.put("/api/v1/lines/line-boundary-put", json={
        "rate_warning_threshold": 120.0,
        "rate_critical_threshold": 120.0,
    })
    assert put_both.status_code == 422

    # Partial PUT: critical equal to existing line warning (130.0)
    put_crit_equal = client.put("/api/v1/lines/line-boundary-put", json={
        "rate_critical_threshold": 130.0,
    })
    assert put_crit_equal.status_code == 422
    assert "rate_critical_threshold must be strictly less than rate_warning_threshold" in put_crit_equal.json()["detail"]

    # Partial PUT: warning equal to existing line critical (110.0)
    put_warn_equal = client.put("/api/v1/lines/line-boundary-put", json={
        "rate_warning_threshold": 110.0,
    })
    assert put_warn_equal.status_code == 422
    assert "rate_critical_threshold must be strictly less than rate_warning_threshold" in put_warn_equal.json()["detail"]


def test_put_line_rejects_non_positive_and_non_finite_thresholds(client: TestClient):
    client.post("/api/v1/lines", json={
        "id": "line-put-val",
        "name": "Val Line",
        "daily_target": 50000,
        "rate_warning_threshold": 140.0,
        "rate_critical_threshold": 120.0,
    })

    # Zero values
    assert client.put("/api/v1/lines/line-put-val", json={"rate_warning_threshold": 0.0}).status_code == 422
    assert client.put("/api/v1/lines/line-put-val", json={"rate_critical_threshold": 0.0}).status_code == 422

    # Negative values
    assert client.put("/api/v1/lines/line-put-val", json={"rate_warning_threshold": -15.0}).status_code == 422
    assert client.put("/api/v1/lines/line-put-val", json={"rate_critical_threshold": -10.0}).status_code == 422

    # Non-finite values via string
    for non_finite in ["nan", "-nan", "inf", "-inf", "infinity", "-infinity"]:
        assert client.put("/api/v1/lines/line-put-val", json={"rate_warning_threshold": non_finite}).status_code == 422
        assert client.put("/api/v1/lines/line-put-val", json={"rate_critical_threshold": non_finite}).status_code == 422


def test_single_sided_threshold_inversion_fails(client: TestClient):
    # Single-sided POST: warning <= default critical (110.0)
    res_post_warn = client.post("/api/v1/lines", json={
        "id": "line-single-warn",
        "name": "Single Warn Inverted",
        "rate_warning_threshold": 100.0,
    })
    assert res_post_warn.status_code == 422
    assert "rate_warning_threshold must be strictly greater than default rate_critical_threshold (110.0)" in str(res_post_warn.json())

    # Single-sided POST: critical >= default warning (130.0)
    res_post_crit = client.post("/api/v1/lines", json={
        "id": "line-single-crit",
        "name": "Single Crit Inverted",
        "rate_critical_threshold": 135.0,
    })
    assert res_post_crit.status_code == 422
    assert "rate_critical_threshold must be strictly less than default rate_warning_threshold (130.0)" in str(res_post_crit.json())

    # Create line with default thresholds
    res_default = client.post("/api/v1/lines", json={
        "id": "line-default-inverted",
        "name": "Default Inversion Target",
    })
    assert res_default.status_code == 201

    # Single-sided PUT: warning to 100 on default line (effective critical is 110.0) -> fails 422
    res_put_warn = client.put("/api/v1/lines/line-default-inverted", json={
        "rate_warning_threshold": 100.0,
    })
    assert res_put_warn.status_code == 422
    assert "rate_critical_threshold must be strictly less than rate_warning_threshold" in res_put_warn.json()["detail"]

    # Single-sided PUT: critical to 135 on default line (effective warning is 130.0) -> fails 422
    res_put_crit = client.put("/api/v1/lines/line-default-inverted", json={
        "rate_critical_threshold": 135.0,
    })
    assert res_put_crit.status_code == 422
    assert "rate_critical_threshold must be strictly less than rate_warning_threshold" in res_put_crit.json()["detail"]

