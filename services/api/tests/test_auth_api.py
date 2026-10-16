import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import jwt

from services.api.src.main import app
from services.api.src.db.session import get_db
from services.api.src.db.models import Base, User
from services.api.src.services.auth import (
    hash_password,
    create_access_token,
    SECRET_KEY,
    ALGORITHM,
)


@pytest.fixture
def auth_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestingSession()
    db.add(User(username="admin", password_hash=hash_password("admin123"), role="ADMIN", is_active=True))
    db.add(User(username="operator", password_hash=hash_password("op123"), role="OPERATOR", is_active=True))
    db.add(User(username="disabled", password_hash=hash_password("dis123"), role="OPERATOR", is_active=False))
    # User with legacy unsalted SHA-256 hash for backwards compatibility testing
    import hashlib
    db.add(User(username="legacy_user", password_hash=hashlib.sha256(b"legacy123").hexdigest(), role="OPERATOR", is_active=True))
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


def test_login_success(auth_client):
    res = auth_client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "admin"
    assert data["user"]["role"] == "ADMIN"
    assert data["user"]["is_active"] is True
    assert isinstance(data["user"]["id"], int)


def test_login_invalid_password(auth_client):
    res = auth_client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrongpassword"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid username or password"


def test_login_nonexistent_user(auth_client):
    res = auth_client.post("/api/v1/auth/login", json={"username": "nonexistent_user", "password": "password"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid username or password"


def test_login_inactive_user(auth_client):
    res = auth_client.post("/api/v1/auth/login", json={"username": "disabled", "password": "dis123"})
    assert res.status_code == 403
    assert res.json()["detail"] == "User account is inactive"


def test_auth_me_success(auth_client):
    login_res = auth_client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    me_res = auth_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    user_data = me_res.json()
    assert user_data["username"] == "admin"
    assert user_data["role"] == "ADMIN"
    assert user_data["is_active"] is True


def test_auth_me_missing_authorization_header(auth_client):
    res = auth_client.get("/api/v1/auth/me")
    assert res.status_code == 401
    assert res.json()["detail"] == "Missing or invalid Authorization header"


@pytest.mark.parametrize(
    "malformed_header",
    [
        "Basic dXNlcjpwYXNz",
        "Bearer",
        "Bearer ",
        "Token some_random_token",
        "bearer invalid_casing_without_space",
    ],
)
def test_auth_me_malformed_authorization_header(auth_client, malformed_header):
    res = auth_client.get("/api/v1/auth/me", headers={"Authorization": malformed_header})
    assert res.status_code == 401
    assert res.json()["detail"] in [
        "Missing or invalid Authorization header",
        "Invalid token",
    ]


def test_auth_me_invalid_token_string(auth_client):
    res = auth_client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-valid-token"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid token"


def test_auth_me_forged_token_signature(auth_client):
    forged_token = jwt.encode(
        {"sub": "admin", "role": "ADMIN", "uid": 1},
        "wrong-secret-key-signature",
        algorithm="HS256",
    )
    res = auth_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged_token}"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid token"


def test_auth_me_expired_token(auth_client):
    expired_token = jwt.encode(
        {
            "sub": "admin",
            "role": "ADMIN",
            "uid": 1,
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    res = auth_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid token"


def test_auth_me_missing_sub_in_token(auth_client):
    token_without_sub = jwt.encode(
        {"role": "ADMIN", "uid": 1},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    res = auth_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_without_sub}"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid token"


def test_auth_me_user_not_found(auth_client):
    ghost_token = create_access_token({"sub": "nonexistent_ghost", "role": "OPERATOR", "uid": 999})
    res = auth_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {ghost_token}"})
    assert res.status_code == 404
    assert res.json()["detail"] == "User not found"


def test_auth_me_inactive_user(auth_client):
    inactive_token = create_access_token({"sub": "disabled", "role": "OPERATOR", "uid": 3})
    res = auth_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {inactive_token}"})
    assert res.status_code == 403
    assert res.json()["detail"] == "User account is inactive"


def test_login_legacy_unsalted_sha256_user(auth_client):
    res = auth_client.post("/api/v1/auth/login", json={"username": "legacy_user", "password": "legacy123"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["username"] == "legacy_user"


def test_hash_and_verify_password_unit():
    import hashlib
    from services.api.src.services.auth import verify_password

    pass1 = "my-secret-pass"
    hashed = hash_password(pass1)
    assert hashed != pass1
    assert "$" in hashed
    parts = hashed.split("$")
    assert len(parts) == 2
    salt, key = parts
    assert len(salt) == 32
    assert len(key) == 64

    # Unique salts per invocation
    hashed2 = hash_password(pass1)
    assert hashed != hashed2

    # Verification of salted PBKDF2
    assert verify_password(pass1, hashed) is True
    assert verify_password(pass1, hashed2) is True
    assert verify_password("wrong-pass", hashed) is False
    assert verify_password("", hashed) is False
    assert verify_password(pass1, "") is False
    assert verify_password(pass1, "malformed$salt$extra") is False

    # Backwards-compatible legacy unsalted SHA-256 verification
    legacy_hash = hashlib.sha256(pass1.encode("utf-8")).hexdigest()
    assert "$" not in legacy_hash
    assert verify_password(pass1, legacy_hash) is True
    assert verify_password("wrong-pass", legacy_hash) is False


def test_decode_access_token_invalid_unit():
    from services.api.src.services.auth import decode_access_token
    assert decode_access_token("invalid-garbage-token") is None
    assert decode_access_token("") is None

