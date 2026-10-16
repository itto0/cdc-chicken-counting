import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from services.api.src.main import app
from services.api.src.db.session import get_db
from services.api.src.db.models import Base, Alarm
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def alarms_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    now = datetime.now(timezone.utc)
    db = TestingSession()
    db.add(
        Alarm(
            id=1,
            line_id="line-1",
            alarm_type="SPEED_WARNING",
            severity="WARNING",
            message="Slow conveyor",
            status="OPEN",
            opened_at=now - timedelta(minutes=10),
        )
    )
    db.add(
        Alarm(
            id=2,
            line_id="line-2",
            alarm_type="CAMERA_DROP",
            severity="CRITICAL",
            message="Camera stream offline",
            status="OPEN",
            opened_at=now,
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
    app.dependency_overrides.clear()


def test_list_alarms(alarms_client):
    response = alarms_client.get("/api/v1/alarms?status=OPEN")
    assert response.status_code == 200
    alarms = response.json()
    assert len(alarms) == 2
    # Ordered by opened_at desc
    assert alarms[0]["id"] == 2
    assert alarms[0]["status"] == "OPEN"
    assert alarms[1]["id"] == 1
    assert alarms[1]["status"] == "OPEN"


def test_list_alarms_filtering(alarms_client):
    # Filter by line_id
    res_line = alarms_client.get("/api/v1/alarms?line_id=line-1")
    assert res_line.status_code == 200
    data = res_line.json()
    assert len(data) == 1
    assert data[0]["line_id"] == "line-1"

    # Filter by severity
    res_sev = alarms_client.get("/api/v1/alarms?severity=CRITICAL")
    assert res_sev.status_code == 200
    data = res_sev.json()
    assert len(data) == 1
    assert data[0]["severity"] == "CRITICAL"

    # Filter by severity case-insensitive
    res_sev_lower = alarms_client.get("/api/v1/alarms?severity=critical")
    assert res_sev_lower.status_code == 200
    assert len(res_sev_lower.json()) == 1

    # Filter by active (alias for open)
    res_active = alarms_client.get("/api/v1/alarms?status=active")
    assert res_active.status_code == 200
    assert len(res_active.json()) == 2

    # Filter with no matching records
    res_none = alarms_client.get("/api/v1/alarms?line_id=line-999")
    assert res_none.status_code == 200
    assert res_none.json() == []


def test_acknowledge_and_resolve_alarm(alarms_client):
    # Acknowledge
    ack_res = alarms_client.patch(
        "/api/v1/alarms/1",
        json={"status": "ACKNOWLEDGED", "notes": "Inspecting belt"},
    )
    assert ack_res.status_code == 200
    data = ack_res.json()
    assert data["status"] == "ACKNOWLEDGED"
    assert data["ack_at"] is not None
    assert "+00:00" in data["ack_at"] or "Z" in data["ack_at"] or "T" in data["ack_at"]
    assert "[Ack Note: Inspecting belt]" in data["message"]

    # Resolve
    resolve_res = alarms_client.patch(
        "/api/v1/alarms/1",
        json={"status": "RESOLVED", "notes": "Belt speed fixed"},
    )
    assert resolve_res.status_code == 200
    data = resolve_res.json()
    assert data["status"] == "RESOLVED"
    assert data["resolved_at"] is not None
    assert "[Resolution: Belt speed fixed]" in data["message"]


def test_acknowledge_without_notes(alarms_client):
    ack_res = alarms_client.patch(
        "/api/v1/alarms/2",
        json={"status": "acknowledged"},
    )
    assert ack_res.status_code == 200
    data = ack_res.json()
    assert data["status"] == "ACKNOWLEDGED"
    assert data["ack_at"] is not None
    assert data["message"] == "Camera stream offline"


def test_patch_alarm_not_found(alarms_client):
    res = alarms_client.patch(
        "/api/v1/alarms/9999",
        json={"status": "ACKNOWLEDGED"},
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "Alarm not found"


def test_patch_alarm_invalid_status(alarms_client):
    res = alarms_client.patch(
        "/api/v1/alarms/1",
        json={"status": "CANCELLED"},
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "Invalid target status: CANCELLED"


def test_list_alarms_unfiltered_no_params(alarms_client):
    """GET /api/v1/alarms with NO query parameters returns all alarms ordered newest first."""
    response = alarms_client.get("/api/v1/alarms")
    assert response.status_code == 200
    alarms = response.json()
    assert len(alarms) == 2
    assert alarms[0]["id"] == 2
    assert alarms[0]["message"] == "Camera stream offline"
    assert alarms[1]["id"] == 1
    assert alarms[1]["message"] == "Slow conveyor"


def test_resolve_without_notes_does_not_append_none(alarms_client):
    """PATCH with status=RESOLVED and no notes does not append notes or 'None'."""
    # Omitted notes field
    resolve_res = alarms_client.patch(
        "/api/v1/alarms/2",
        json={"status": "RESOLVED"},
    )
    assert resolve_res.status_code == 200
    data = resolve_res.json()
    assert data["status"] == "RESOLVED"
    assert data["resolved_at"] is not None
    assert data["message"] == "Camera stream offline"
    assert "None" not in data["message"]
    assert "Resolution" not in data["message"]

    # Explicit notes=None
    resolve_none = alarms_client.patch(
        "/api/v1/alarms/1",
        json={"status": "RESOLVED", "notes": None},
    )
    assert resolve_none.status_code == 200
    data_none = resolve_none.json()
    assert data_none["status"] == "RESOLVED"
    assert data_none["resolved_at"] is not None
    assert data_none["message"] == "Slow conveyor"
    assert "None" not in data_none["message"]
    assert "Resolution" not in data_none["message"]


def test_alarm_note_truncation_and_operator_attribution(alarms_client):
    """Verify operator attribution is included and long note is truncated to <= 255 chars."""
    # 1. Verify operator attribution (acknowledged_by) is included in audit note
    ack_res = alarms_client.patch(
        "/api/v1/alarms/1",
        json={
            "status": "ACKNOWLEDGED",
            "acknowledged_by": "operator_jane",
            "notes": "Checking sensor calibration",
        },
    )
    assert ack_res.status_code == 200
    data = ack_res.json()
    assert data["status"] == "ACKNOWLEDGED"
    assert "by operator_jane" in data["message"]
    assert "Checking sensor calibration" in data["message"]
    assert "[Ack Note: Checking sensor calibration by operator_jane]" in data["message"]
    assert len(data["message"]) <= 255

    # 2. Verify operator attribution when notes is omitted
    ack_op_only = alarms_client.patch(
        "/api/v1/alarms/2",
        json={
            "status": "ACKNOWLEDGED",
            "acknowledged_by": "operator_tom",
        },
    )
    assert ack_op_only.status_code == 200
    assert "[Ack Note: by operator_tom]" in ack_op_only.json()["message"]

    # 3. Verify long note truncation to <= 255 chars preventing DB constraint violations
    long_note = "A" * 300
    res_long = alarms_client.patch(
        "/api/v1/alarms/2",
        json={
            "status": "RESOLVED",
            "acknowledged_by": "operator_bob",
            "notes": long_note,
        },
    )
    assert res_long.status_code == 200
    data_long = res_long.json()
    assert data_long["status"] == "RESOLVED"
    assert len(data_long["message"]) <= 255
    assert len(data_long["message"]) == 255
