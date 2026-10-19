import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api.src.main import app
from services.api.src.db.models import Base, User, Line
from services.api.src.db.session import get_db
from services.api.src.services.auth import hash_password, create_access_token


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = TestingSession()
    session.add(User(username="admin", password_hash=hash_password("admin123"), role="admin", is_active=True))
    session.add(User(username="operator", password_hash=hash_password("op123"), role="operator", is_active=True))
    session.add(Line(id="line-1", name="Line 1", daily_target=60000, is_active=True))
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def api_client(test_db):
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_api_key_crud_lifecycle(api_client):
    admin_token = create_access_token({"sub": "admin", "role": "admin"})
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Create API Key
    create_resp = api_client.post(
        "/api/v1/auth/api-keys",
        json={"name": "Line 1 Edge", "role": "OPERATOR"},
        headers=admin_headers,
    )
    assert create_resp.status_code == 201
    data = create_resp.json()
    assert data["name"] == "Line 1 Edge"
    assert data["api_key"].startswith("cdc_live_")
    assert len(data["api_key"]) == 73
    assert data["prefix"] == data["api_key"][:16]
    key_id = data["id"]
    api_key = data["api_key"]

    # 2. List API Keys
    list_resp = api_client.get("/api/v1/auth/api-keys", headers=admin_headers)
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert any(k["id"] == key_id for k in items)
    # Ensure raw api_key is not exposed in list
    assert "api_key" not in items[0]
    assert items[0]["prefix"] == api_key[:16]

    # 3. Authenticate with Bearer API Key
    auth_resp = api_client.get(
        "/api/v1/lines/line-1",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    assert auth_resp.status_code == 200
    assert auth_resp.json()["id"] == "line-1"

    # 4. Authenticate with X-API-Key Header
    header_resp = api_client.get(
        "/api/v1/lines/line-1",
        headers={"X-API-Key": api_key},
    )
    assert header_resp.status_code == 200
    assert header_resp.json()["id"] == "line-1"

    # 5. Revoke API Key
    del_resp = api_client.delete(f"/api/v1/auth/api-keys/{key_id}", headers=admin_headers)
    assert del_resp.status_code == 200

    # 6. Verify revoked key returns 401
    revoked_resp = api_client.get(
        "/api/v1/lines/line-1",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    assert revoked_resp.status_code == 401

    # 7. Verify revoked key returns 401 via X-API-Key
    revoked_x_resp = api_client.get(
        "/api/v1/lines/line-1",
        headers={"X-API-Key": api_key},
    )
    assert revoked_x_resp.status_code == 401


def test_api_key_updates_last_used_at(api_client):
    admin_token = create_access_token({"sub": "admin", "role": "admin"})
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    create_resp = api_client.post(
        "/api/v1/auth/api-keys",
        json={"name": "Tracking Edge", "role": "OPERATOR"},
        headers=admin_headers,
    )
    assert create_resp.status_code == 201
    api_key = create_resp.json()["api_key"]
    key_id = create_resp.json()["id"]

    # Before use, last_used_at should be None
    list_before = api_client.get("/api/v1/auth/api-keys", headers=admin_headers).json()
    item_before = next(k for k in list_before if k["id"] == key_id)
    assert item_before["last_used_at"] is None

    # Use the key
    resp = api_client.get("/api/v1/lines/line-1", headers={"X-API-Key": api_key})
    assert resp.status_code == 200

    # After use, last_used_at should be updated
    list_after = api_client.get("/api/v1/auth/api-keys", headers=admin_headers).json()
    item_after = next(k for k in list_after if k["id"] == key_id)
    assert item_after["last_used_at"] is not None


def test_api_key_role_restriction_and_management_rbac(api_client):
    operator_token = create_access_token({"sub": "operator", "role": "operator"})
    op_headers = {"Authorization": f"Bearer {operator_token}"}
    admin_token = create_access_token({"sub": "admin", "role": "admin"})
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Operator cannot create API keys
    resp = api_client.post(
        "/api/v1/auth/api-keys",
        json={"name": "Forbidden Key", "role": "OPERATOR"},
        headers=op_headers,
    )
    assert resp.status_code == 403

    # Operator cannot list API keys
    resp = api_client.get("/api/v1/auth/api-keys", headers=op_headers)
    assert resp.status_code == 403

    # Admin creates operator key
    create_resp = api_client.post(
        "/api/v1/auth/api-keys",
        json={"name": "Worker Key", "role": "OPERATOR"},
        headers=admin_headers,
    )
    key_id = create_resp.json()["id"]
    api_key = create_resp.json()["api_key"]

    # Operator cannot delete API keys
    del_resp = api_client.delete(f"/api/v1/auth/api-keys/{key_id}", headers=op_headers)
    assert del_resp.status_code == 403

    # Operator API key cannot create a line (admin only)
    line_resp = api_client.post(
        "/api/v1/lines",
        json={"id": "line-2", "name": "Line 2"},
        headers={"X-API-Key": api_key},
    )
    assert line_resp.status_code == 403


def test_invalid_api_keys(api_client):
    # Unknown Bearer cdc_live key
    resp = api_client.get(
        "/api/v1/lines/line-1",
        headers={"Authorization": "Bearer cdc_live_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"},
    )
    assert resp.status_code == 401

    # Unknown X-API-Key
    resp2 = api_client.get(
        "/api/v1/lines/line-1",
        headers={"X-API-Key": "cdc_live_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"},
    )
    assert resp2.status_code == 401


def test_delete_nonexistent_api_key(api_client):
    admin_token = create_access_token({"sub": "admin", "role": "admin"})
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    del_resp = api_client.delete("/api/v1/auth/api-keys/99999", headers=admin_headers)
    assert del_resp.status_code == 404


def test_auth_me_with_api_key(api_client):
    admin_token = create_access_token({"sub": "admin", "role": "admin"})
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    create_resp = api_client.post(
        "/api/v1/auth/api-keys",
        json={"name": "Edge Cam 1"},
        headers=admin_headers,
    )
    assert create_resp.status_code == 201
    key_data = create_resp.json()
    assert key_data["role"] == "OPERATOR"
    api_key = key_data["api_key"]

    # Call /auth/me with X-API-Key
    me_resp = api_client.get("/api/v1/auth/me", headers={"X-API-Key": api_key})
    assert me_resp.status_code == 200
    data = me_resp.json()
    assert data["username"] == "device:Edge Cam 1"
    assert data["role"] == "OPERATOR"
    assert data["is_active"] is True

    # Call /auth/me with Bearer API Key
    me_resp_bearer = api_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {api_key}"})
    assert me_resp_bearer.status_code == 200
    assert me_resp_bearer.json()["username"] == "device:Edge Cam 1"


def test_empty_or_whitespace_x_api_key(api_client):
    resp = api_client.get("/api/v1/lines/line-1", headers={"X-API-Key": "   "})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid or revoked API key"

