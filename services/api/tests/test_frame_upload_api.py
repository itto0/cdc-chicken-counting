import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api.src.api.auth import get_current_user
from services.api.src.db.models import ApiKey, Base, Line, User
from services.api.src.db.session import get_db
from services.api.src.main import app
from services.api.src.services.auth import (
    create_access_token,
    generate_api_key,
    hash_password,
)
from services.api.src.services.preview import (
    clear_relay_buffer,
    get_live_frame,
)

SAMPLE_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\xff\xd9"


@pytest.fixture(autouse=True)
def clean_test_environment():
    """Ensure in-memory buffer is clear and default auth overrides do not bypass auth."""
    clear_relay_buffer()
    app.dependency_overrides.pop(get_current_user, None)
    yield
    clear_relay_buffer()
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def test_db_session():
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
    session.add(User(username="viewer", password_hash=hash_password("viewer123"), role="viewer", is_active=True))
    session.add(Line(id="line-1", name="Line 1", daily_target=60000, is_active=True))
    session.add(Line(id="line-2", name="Line 2", daily_target=60000, is_active=True))
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(test_db_session):
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


def test_frame_upload_success_with_operator_token(client):
    """Validates 204 response and frame stored in get_live_frame."""
    token = create_access_token({"sub": "operator", "role": "operator"})
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"}

    response = client.post("/api/v1/lines/line-1/frame", content=SAMPLE_JPEG, headers=headers)
    assert response.status_code == 204
    assert response.content == b""
    assert get_live_frame("line-1") == SAMPLE_JPEG


def test_frame_upload_device_mismatched_line_forbidden(client, test_db_session):
    """Validates that device:line-1 token posting to line-2 receives 403."""
    raw_key_1, key_hash_1, prefix_1 = generate_api_key()
    device_key = ApiKey(
        name="line-1",
        key_hash=key_hash_1,
        prefix=prefix_1,
        role="OPERATOR",
        is_active=True,
    )
    test_db_session.add(device_key)
    test_db_session.commit()

    # Posting to authorized line (line-1) succeeds
    success_resp = client.post(
        "/api/v1/lines/line-1/frame",
        content=SAMPLE_JPEG,
        headers={"X-API-Key": raw_key_1, "Content-Type": "image/jpeg"},
    )
    assert success_resp.status_code == 204
    assert get_live_frame("line-1") == SAMPLE_JPEG

    # Posting to mismatched line (line-2) is forbidden
    mismatch_resp = client.post(
        "/api/v1/lines/line-2/frame",
        content=SAMPLE_JPEG,
        headers={"X-API-Key": raw_key_1, "Content-Type": "image/jpeg"},
    )
    assert mismatch_resp.status_code == 403
    assert mismatch_resp.json()["detail"] == "Token not authorized for this line (authorized: 'line-1')"
    assert get_live_frame("line-2") is None

    # Bearer format for device API key also enforces mismatched line restriction
    mismatch_bearer_resp = client.post(
        "/api/v1/lines/line-2/frame",
        content=SAMPLE_JPEG,
        headers={"Authorization": f"Bearer {raw_key_1}", "Content-Type": "image/jpeg"},
    )
    assert mismatch_bearer_resp.status_code == 403
    assert mismatch_bearer_resp.json()["detail"] == "Token not authorized for this line (authorized: 'line-1')"


def test_frame_upload_admin_can_post_any_line(client):
    """Validates that an admin token can post to any line."""
    admin_token = create_access_token({"sub": "admin", "role": "admin"})
    headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "image/jpeg"}

    jpeg_line1 = SAMPLE_JPEG + b"_1"
    jpeg_line2 = SAMPLE_JPEG + b"_2"

    resp1 = client.post("/api/v1/lines/line-1/frame", content=jpeg_line1, headers=headers)
    assert resp1.status_code == 204
    assert get_live_frame("line-1") == jpeg_line1

    resp2 = client.post("/api/v1/lines/line-2/frame", content=jpeg_line2, headers=headers)
    assert resp2.status_code == 204
    assert get_live_frame("line-2") == jpeg_line2


def test_frame_upload_unauthorized(client):
    """Validates that missing or invalid authorization header receives 401."""
    # Missing authorization
    resp_missing = client.post(
        "/api/v1/lines/line-1/frame",
        content=SAMPLE_JPEG,
        headers={"Content-Type": "image/jpeg"},
    )
    assert resp_missing.status_code == 401

    # Invalid Bearer token
    resp_invalid = client.post(
        "/api/v1/lines/line-1/frame",
        content=SAMPLE_JPEG,
        headers={"Authorization": "Bearer invalid-token", "Content-Type": "image/jpeg"},
    )
    assert resp_invalid.status_code == 401

    # Inactive/revoked API key
    resp_revoked_key = client.post(
        "/api/v1/lines/line-1/frame",
        content=SAMPLE_JPEG,
        headers={"X-API-Key": "cdc_live_unknownkey12345678901234567890", "Content-Type": "image/jpeg"},
    )
    assert resp_revoked_key.status_code == 401

    # Forbidden role (viewer) receives 403
    viewer_token = create_access_token({"sub": "viewer", "role": "viewer"})
    resp_viewer = client.post(
        "/api/v1/lines/line-1/frame",
        content=SAMPLE_JPEG,
        headers={"Authorization": f"Bearer {viewer_token}", "Content-Type": "image/jpeg"},
    )
    assert resp_viewer.status_code == 403


def test_frame_upload_payload_too_large(client):
    """Validates that payloads > 1 MB receive 413."""
    token = create_access_token({"sub": "operator", "role": "operator"})
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"}

    # 1 MB + 1 byte (1048577 bytes)
    oversized_payload = b"\xff\xd8" + b"\x00" * (1024 * 1024 - 1)
    assert len(oversized_payload) == 1048577

    response = client.post("/api/v1/lines/line-1/frame", content=oversized_payload, headers=headers)
    assert response.status_code == 413
    assert response.json()["detail"] == "Frame exceeds maximum size limit of 1048576 bytes"
    assert get_live_frame("line-1") is None


def test_frame_upload_invalid_non_jpeg(client):
    """Validates that PNG or arbitrary non-JPEG data receives 400."""
    token = create_access_token({"sub": "operator", "role": "operator"})
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"}

    # PNG format
    png_payload = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    resp_png = client.post("/api/v1/lines/line-1/frame", content=png_payload, headers=headers)
    assert resp_png.status_code == 400
    assert resp_png.json()["detail"] == "Invalid image format: must be JPEG (SOI marker missing)"

    # Short garbage payload (< 4 bytes)
    resp_short = client.post("/api/v1/lines/line-1/frame", content=b"\x01\x02\x03", headers=headers)
    assert resp_short.status_code == 400
    assert resp_short.json()["detail"] == "Invalid image format: must be JPEG (SOI marker missing)"

    # Garbage without JPEG SOI
    resp_garbage = client.post(
        "/api/v1/lines/line-1/frame",
        content=b"not-a-jpeg-payload-data",
        headers=headers,
    )
    assert resp_garbage.status_code == 400
    assert resp_garbage.json()["detail"] == "Invalid image format: must be JPEG (SOI marker missing)"


def test_frame_upload_empty_body(client):
    """Validates that empty request body receives 400."""
    token = create_access_token({"sub": "operator", "role": "operator"})
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"}

    response = client.post("/api/v1/lines/line-1/frame", content=b"", headers=headers)
    assert response.status_code == 400
    assert response.json()["detail"] == "Empty frame body"


def test_frame_upload_empty_or_whitespace_line_id(client):
    """Validates that blank or whitespace-only line_id receives 400."""
    token = create_access_token({"sub": "operator", "role": "operator"})
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"}

    response = client.post("/api/v1/lines/%20%20/frame", content=SAMPLE_JPEG, headers=headers)
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid line_id"


def test_frame_upload_exact_max_size_success(client):
    """Validates that payload exactly 1 MB (1048576 bytes) succeeds with 204."""
    token = create_access_token({"sub": "operator", "role": "operator"})
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"}

    exact_1mb_payload = b"\xff\xd8" + b"\x00" * (1024 * 1024 - 2)
    assert len(exact_1mb_payload) == 1048576

    response = client.post("/api/v1/lines/line-1/frame", content=exact_1mb_payload, headers=headers)
    assert response.status_code == 204
    assert get_live_frame("line-1") == exact_1mb_payload
