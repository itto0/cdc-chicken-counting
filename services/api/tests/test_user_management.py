import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api.src.api.auth import get_current_user
from services.api.src.main import app
from services.api.src.db.session import get_db
from services.api.src.db.models import Base, User
from services.api.src.services.auth import hash_password


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestingSession()
    db.add(User(username="admin", password_hash=hash_password("admin123"), role="admin", is_active=True))
    db.add(User(username="admin2", password_hash=hash_password("admin456"), role="admin", is_active=True))
    db.add(User(username="operator", password_hash=hash_password("op123"), role="operator", is_active=True))
    db.commit()
    db.close()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides.pop(get_current_user, None)
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def get_token(client, username, password):
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_list_users_as_admin(client):
    token = get_token(client, "admin", "admin123")
    res = client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    users = res.json()
    assert len(users) == 3
    usernames = [u["username"] for u in users]
    assert "admin" in usernames
    assert "admin2" in usernames
    assert "operator" in usernames


def test_list_users_as_operator_forbidden(client):
    token = get_token(client, "operator", "op123")
    res = client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_create_user_success(client):
    token = get_token(client, "admin", "admin123")
    res = client.post(
        "/api/v1/auth/users",
        json={"username": "newuser", "password": "password123", "role": "operator"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["username"] == "newuser"
    assert data["role"].lower() == "operator"
    assert data["is_active"] is True
    assert isinstance(data["id"], int)


def test_create_user_duplicate_username(client):
    token = get_token(client, "admin", "admin123")
    res = client.post(
        "/api/v1/auth/users",
        json={"username": "operator", "password": "password123", "role": "operator"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert "Username already exists" in res.json()["detail"]


def test_update_user_role_and_status(client):
    token = get_token(client, "admin", "admin123")
    # Get operator ID
    users = client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {token}"}).json()
    op = next(u for u in users if u["username"] == "operator")

    res = client.put(
        f"/api/v1/auth/users/{op['id']}",
        json={"role": "admin", "is_active": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["role"].lower() == "admin"
    assert data["is_active"] is False


def test_admin_cannot_deactivate_self(client):
    token = get_token(client, "admin", "admin123")
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    res = client.put(
        f"/api/v1/auth/users/{me['id']}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert "Cannot deactivate own account" in res.json()["detail"]


def test_cannot_deactivate_or_demote_last_admin(client):
    token = get_token(client, "admin", "admin123")
    users = client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {token}"}).json()
    admin2 = next(u for u in users if u["username"] == "admin2")

    # Demote admin2 so admin is the only active admin left
    res = client.put(
        f"/api/v1/auth/users/{admin2['id']}",
        json={"role": "operator"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200

    # Now trying to demote the only remaining admin (admin) should fail
    admin1 = next(u for u in users if u["username"] == "admin")
    res_demote = client.put(
        f"/api/v1/auth/users/{admin1['id']}",
        json={"role": "operator"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_demote.status_code == 400
    assert "Cannot deactivate or demote the last remaining active admin" in res_demote.json()["detail"]


def test_admin_reset_user_password(client):
    token = get_token(client, "admin", "admin123")
    users = client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {token}"}).json()
    op = next(u for u in users if u["username"] == "operator")

    res = client.put(
        f"/api/v1/auth/users/{op['id']}/password",
        json={"new_password": "new_operator_pass"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200

    # Verify operator can login with new password
    login_res = client.post("/api/v1/auth/login", json={"username": "operator", "password": "new_operator_pass"})
    assert login_res.status_code == 200


def test_admin_cannot_delete_self(client):
    token = get_token(client, "admin", "admin123")
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    res = client.delete(
        f"/api/v1/auth/users/{me['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert "Cannot delete own account" in res.json()["detail"]


def test_cannot_delete_last_active_admin(client):
    token = get_token(client, "admin", "admin123")
    users = client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {token}"}).json()
    admin2 = next(u for u in users if u["username"] == "admin2")

    # Delete admin2
    res_del2 = client.delete(
        f"/api/v1/auth/users/{admin2['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_del2.status_code == 200

    # Delete operator
    op = next(u for u in users if u["username"] == "operator")
    res_del_op = client.delete(
        f"/api/v1/auth/users/{op['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_del_op.status_code == 200

    # Now admin is the last admin: delete should fail
    admin1 = next(u for u in users if u["username"] == "admin")
    res_last = client.delete(
        f"/api/v1/auth/users/{admin1['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    # Self delete fails with 400
    assert res_last.status_code == 400


def test_cannot_delete_last_active_admin_via_api_key(client):
    token = get_token(client, "admin", "admin123")
    # Create an admin API key
    key_res = client.post(
        "/api/v1/auth/api-keys",
        json={"name": "test-admin-key", "role": "ADMIN"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert key_res.status_code == 201
    api_key = key_res.json()["api_key"]

    users = client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {token}"}).json()
    admin1 = next(u for u in users if u["username"] == "admin")
    admin2 = next(u for u in users if u["username"] == "admin2")

    # Delete admin2 using the API key
    res_del2 = client.delete(
        f"/api/v1/auth/users/{admin2['id']}",
        headers={"X-API-Key": api_key},
    )
    assert res_del2.status_code == 200

    # Now admin1 is the last active admin. API key trying to delete admin1 must fail with invariant 4
    res_del1 = client.delete(
        f"/api/v1/auth/users/{admin1['id']}",
        headers={"X-API-Key": api_key},
    )
    assert res_del1.status_code == 400
    assert "Cannot delete the last remaining active admin" in res_del1.json()["detail"]


def test_cannot_deactivate_last_active_admin_via_api_key(client):
    token = get_token(client, "admin", "admin123")
    key_res = client.post(
        "/api/v1/auth/api-keys",
        json={"name": "test-admin-key2", "role": "ADMIN"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert key_res.status_code == 201
    api_key = key_res.json()["api_key"]

    users = client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {token}"}).json()
    admin1 = next(u for u in users if u["username"] == "admin")
    admin2 = next(u for u in users if u["username"] == "admin2")

    # Demote admin2
    res_demote = client.put(
        f"/api/v1/auth/users/{admin2['id']}",
        json={"role": "operator"},
        headers={"X-API-Key": api_key},
    )
    assert res_demote.status_code == 200

    # Trying to deactivate admin1 via API key should fail with invariant 3
    res_deact = client.put(
        f"/api/v1/auth/users/{admin1['id']}",
        json={"is_active": False},
        headers={"X-API-Key": api_key},
    )
    assert res_deact.status_code == 400
    assert "Cannot deactivate or demote the last remaining active admin" in res_deact.json()["detail"]


def test_user_not_found_crud(client):
    token = get_token(client, "admin", "admin123")
    non_existent_id = 99999

    res_put = client.put(
        f"/api/v1/auth/users/{non_existent_id}",
        json={"role": "operator"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_put.status_code == 404

    res_pass = client.put(
        f"/api/v1/auth/users/{non_existent_id}/password",
        json={"new_password": "newpassword123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_pass.status_code == 404

    res_del = client.delete(
        f"/api/v1/auth/users/{non_existent_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_del.status_code == 404


def test_operator_forbidden_on_all_user_management(client):
    token = get_token(client, "operator", "op123")
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/v1/auth/users", headers=headers).status_code == 403
    assert client.post("/api/v1/auth/users", json={"username": "u1", "password": "p1"}, headers=headers).status_code == 403
    assert client.put("/api/v1/auth/users/1", json={"role": "admin"}, headers=headers).status_code == 403
    assert client.put("/api/v1/auth/users/1/password", json={"new_password": "newpassword123"}, headers=headers).status_code == 403
    assert client.delete("/api/v1/auth/users/1", headers=headers).status_code == 403


def test_change_password_success(client):
    token = get_token(client, "operator", "op123")
    res = client.put(
        "/api/v1/auth/password",
        json={"current_password": "op123", "new_password": "new_op_password_456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["message"] == "Password changed successfully"

    # Verify old password fails
    res_old = client.post("/api/v1/auth/login", json={"username": "operator", "password": "op123"})
    assert res_old.status_code == 401

    # Verify new password works
    res_new = client.post("/api/v1/auth/login", json={"username": "operator", "password": "new_op_password_456"})
    assert res_new.status_code == 200


def test_change_password_as_admin_success(client):
    token = get_token(client, "admin", "admin123")
    res = client.put(
        "/api/v1/auth/password",
        json={"current_password": "admin123", "new_password": "new_admin_password_789"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["message"] == "Password changed successfully"

    res_old = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert res_old.status_code == 401

    res_new = client.post("/api/v1/auth/login", json={"username": "admin", "password": "new_admin_password_789"})
    assert res_new.status_code == 200


def test_change_password_wrong_current_password(client):
    token = get_token(client, "operator", "op123")
    res = client.put(
        "/api/v1/auth/password",
        json={"current_password": "wrong_password", "new_password": "new_op_password_456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert "Current password is incorrect" in res.json()["detail"]


def test_change_password_same_password_rejected(client):
    token = get_token(client, "admin", "admin123")
    res = client.put(
        "/api/v1/auth/password",
        json={"current_password": "admin123", "new_password": "admin123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert "New password must be different from current password" in res.json()["detail"]


def test_change_password_too_short(client):
    token = get_token(client, "operator", "op123")
    res = client.put(
        "/api/v1/auth/password",
        json={"current_password": "op123", "new_password": "123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422


def test_change_password_via_api_key_not_found(client):
    token = get_token(client, "admin", "admin123")
    key_res = client.post(
        "/api/v1/auth/api-keys",
        json={"name": "test-key-pw", "role": "OPERATOR"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert key_res.status_code == 201
    api_key = key_res.json()["api_key"]

    res = client.put(
        "/api/v1/auth/password",
        json={"current_password": "op123", "new_password": "new_op_password_456"},
        headers={"X-API-Key": api_key},
    )
    assert res.status_code == 404
    assert "User not found" in res.json()["detail"]


def test_create_user_username_strip_before_length_validation(client):
    token = get_token(client, "admin", "admin123")
    # "  ab  " has length 6 unstripped, but stripped is 2 chars (< min_length=3)
    res_short = client.post(
        "/api/v1/auth/users",
        json={"username": "  ab  ", "password": "password123", "role": "operator"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_short.status_code == 422

    # "  gooduser  " stripped is "gooduser"
    res_good = client.post(
        "/api/v1/auth/users",
        json={"username": "  gooduser  ", "password": "password123", "role": "operator"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_good.status_code == 201
    assert res_good.json()["username"] == "gooduser"


def test_create_user_case_insensitive_duplicate_username(client):
    token = get_token(client, "admin", "admin123")
    res = client.post(
        "/api/v1/auth/users",
        json={"username": "OPERATOR", "password": "password123", "role": "operator"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert "Username already exists" in res.json()["detail"]


def test_create_user_invalid_characters_in_username(client):
    token = get_token(client, "admin", "admin123")
    # Username with spaces and special character '!'
    res = client.post(
        "/api/v1/auth/users",
        json={"username": "bad user!", "password": "password123", "role": "operator"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422


def test_change_password_current_password_exceeding_max_length(client):
    token = get_token(client, "operator", "op123")
    res = client.put(
        "/api/v1/auth/password",
        json={"current_password": "a" * 129, "new_password": "newpassword123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422


def test_create_user_integrity_error_race_condition(client, monkeypatch):
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session

    token = get_token(client, "admin", "admin123")
    real_commit = Session.commit

    def fake_commit(self):
        for obj in self.new:
            if isinstance(obj, User):
                raise IntegrityError("mock integrity error", "params", "orig")
        return real_commit(self)

    monkeypatch.setattr(Session, "commit", fake_commit)

    res = client.post(
        "/api/v1/auth/users",
        json={"username": "raceuser", "password": "password123", "role": "operator"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert "Username already exists" in res.json()["detail"]


