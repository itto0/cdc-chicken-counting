import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api.src.main import app
from services.api.src.db.session import get_db
from services.api.src.db.models import Base, User, Line, Alarm
from services.api.src.services.auth import hash_password, create_access_token


@pytest.fixture
def rbac_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with TestingSession() as db:
        db.add(Line(id="line-1", name="Test Line", daily_target=50000, is_active=True))
        db.add(User(username="admin", password_hash=hash_password("admin123"), role="admin", is_active=True))
        db.add(User(username="operator", password_hash=hash_password("op123"), role="operator", is_active=True))
        db.add(
            Alarm(
                id=1,
                line_id="line-1",
                alarm_type="SYSTEM_DEGRADED",
                severity="WARNING",
                message="Test warning",
                status="OPEN",
                opened_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

    def override_get_db():
        with TestingSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_lines_unauthenticated_returns_401(rbac_client):
    res = rbac_client.get("/api/v1/lines")
    assert res.status_code == 401


def test_lines_detail_unauthenticated_returns_401(rbac_client):
    res = rbac_client.get("/api/v1/lines/line-1")
    assert res.status_code == 401


def test_lines_authenticated_operator_can_read(rbac_client):
    token = create_access_token({"sub": "operator", "role": "operator"})
    headers = {"Authorization": f"Bearer {token}"}
    res = rbac_client.get("/api/v1/lines", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) >= 1

    res_detail = rbac_client.get("/api/v1/lines/line-1", headers=headers)
    assert res_detail.status_code == 200
    assert res_detail.json()["id"] == "line-1"


def test_lines_create_forbidden_for_operator(rbac_client):
    token = create_access_token({"sub": "operator", "role": "operator"})
    res = rbac_client.post(
        "/api/v1/lines",
        json={"id": "line-2", "name": "Line 2", "daily_target": 10000},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
    assert "Required role: admin" in res.json()["detail"]


def test_lines_update_forbidden_for_operator(rbac_client):
    token = create_access_token({"sub": "operator", "role": "operator"})
    res = rbac_client.put(
        "/api/v1/lines/line-1",
        json={"name": "Operator Renamed Line"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
    assert "Required role: admin" in res.json()["detail"]


def test_lines_delete_forbidden_for_operator(rbac_client):
    token = create_access_token({"sub": "operator", "role": "operator"})
    res = rbac_client.delete(
        "/api/v1/lines/line-1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
    assert "Required role: admin" in res.json()["detail"]


def test_lines_create_allowed_for_admin(rbac_client):
    token = create_access_token({"sub": "admin", "role": "admin"})
    res = rbac_client.post(
        "/api/v1/lines",
        json={"id": "line-2", "name": "Line 2", "daily_target": 10000},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    assert res.json()["id"] == "line-2"


def test_lines_update_allowed_for_admin(rbac_client):
    token = create_access_token({"sub": "admin", "role": "admin"})
    res = rbac_client.put(
        "/api/v1/lines/line-1",
        json={"name": "Admin Renamed Line"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["name"] == "Admin Renamed Line"


def test_lines_delete_allowed_for_admin(rbac_client):
    token = create_access_token({"sub": "admin", "role": "admin"})
    res = rbac_client.delete(
        "/api/v1/lines/line-1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["is_active"] is False


def test_summary_endpoint_requires_auth(rbac_client):
    res_unauth = rbac_client.get("/api/v1/lines/line-1/summary")
    assert res_unauth.status_code == 401

    token = create_access_token({"sub": "operator", "role": "operator"})
    res_auth = rbac_client.get("/api/v1/lines/line-1/summary", headers={"Authorization": f"Bearer {token}"})
    assert res_auth.status_code == 200
    assert res_auth.json()["line_id"] == "line-1"


def test_counts_endpoint_requires_auth(rbac_client):
    res_unauth = rbac_client.get("/api/v1/lines/line-1/counts")
    assert res_unauth.status_code == 401

    token = create_access_token({"sub": "operator", "role": "operator"})
    res_auth = rbac_client.get("/api/v1/lines/line-1/counts", headers={"Authorization": f"Bearer {token}"})
    assert res_auth.status_code == 200
    assert res_auth.json()["line_id"] == "line-1"


def test_alarms_endpoints_require_auth(rbac_client):
    res_list_unauth = rbac_client.get("/api/v1/alarms")
    assert res_list_unauth.status_code == 401

    token = create_access_token({"sub": "operator", "role": "operator"})
    headers = {"Authorization": f"Bearer {token}"}
    res_list_auth = rbac_client.get("/api/v1/alarms", headers=headers)
    assert res_list_auth.status_code == 200

    res_patch_unauth = rbac_client.patch(
        "/api/v1/alarms/1",
        json={"status": "ACKNOWLEDGED", "notes": "Acked"},
    )
    assert res_patch_unauth.status_code == 401

    res_patch_auth = rbac_client.patch(
        "/api/v1/alarms/1",
        json={"status": "ACKNOWLEDGED", "notes": "Acked"},
        headers=headers,
    )
    assert res_patch_auth.status_code == 200
    assert res_patch_auth.json()["status"] == "ACKNOWLEDGED"


def test_reports_export_requires_auth(rbac_client):
    res_unauth = rbac_client.get("/api/v1/reports/export")
    assert res_unauth.status_code == 401

    token = create_access_token({"sub": "operator", "role": "operator"})
    res_auth = rbac_client.get(
        "/api/v1/reports/export?format=xlsx",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_auth.status_code == 200


def test_preview_remains_open_without_auth(rbac_client):
    with rbac_client.stream("GET", "/api/v1/lines/line-1/preview?max_frames=1") as res:
        assert res.status_code == 200


def test_sync_batch_remains_open_without_auth(rbac_client):
    res = rbac_client.post(
        "/api/v1/sync/batch",
        json={"line_id": "line-1", "events": [], "aggregates": [], "health": None},
    )
    assert res.status_code == 200
