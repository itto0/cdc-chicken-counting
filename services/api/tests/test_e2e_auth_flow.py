import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api.src.main import app, init_db
from services.api.src.db.session import get_db


@pytest.fixture
def e2e_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Seed default lines and accounts
    init_db(target_engine=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        with TestingSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_complete_auth_lifecycle(e2e_client):
    # 1. Unauthenticated request to /me is rejected
    res_me_unauth = e2e_client.get("/api/v1/auth/me")
    assert res_me_unauth.status_code == 401

    # 2. Login as seeded operator
    res_login_op = e2e_client.post(
        "/api/v1/auth/login",
        json={"username": "operator", "password": "operator123"},
    )
    assert res_login_op.status_code == 200
    op_token = res_login_op.json()["access_token"]
    assert res_login_op.json()["user"]["username"] == "operator"
    assert res_login_op.json()["user"]["role"] == "operator"

    # 3. Authenticated request to /me
    res_me_op = e2e_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {op_token}"},
    )
    assert res_me_op.status_code == 200
    assert res_me_op.json()["username"] == "operator"

    # 4. Operator reads lines
    res_lines_op = e2e_client.get(
        "/api/v1/lines",
        headers={"Authorization": f"Bearer {op_token}"},
    )
    assert res_lines_op.status_code == 200
    assert len(res_lines_op.json()) >= 2  # seeded line-1 and lineA

    # 5. Operator attempts to create line (forbidden)
    res_create_op = e2e_client.post(
        "/api/v1/lines",
        json={"id": "line-forbidden", "name": "Illegal Line", "daily_target": 1000},
        headers={"Authorization": f"Bearer {op_token}"},
    )
    assert res_create_op.status_code == 403

    # 6. Login as seeded admin
    res_login_admin = e2e_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert res_login_admin.status_code == 200
    admin_token = res_login_admin.json()["access_token"]

    # 7. Admin creates line (authorized)
    res_create_admin = e2e_client.post(
        "/api/v1/lines",
        json={"id": "line-allowed", "name": "Admin Created Line", "daily_target": 1000},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_create_admin.status_code == 201

    # 8. Unauthenticated edge sync works seamlessly
    res_sync = e2e_client.post(
        "/api/v1/sync/batch",
        json={"line_id": "line-1", "events": [], "aggregates": [], "health": None},
    )
    assert res_sync.status_code == 200
