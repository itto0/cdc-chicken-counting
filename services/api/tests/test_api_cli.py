import subprocess
import sys
from sqlalchemy import select
from services.api.src.db.models import ApiKey
from services.api.src.db.session import SessionLocal
from services.api.src.services.auth import hash_api_key


def test_cli_create_api_key():
    cmd = [
        sys.executable,
        "-m",
        "services.api.src.cli",
        "create-api-key",
        "--name",
        "CLI Test Key",
        "--role",
        "OPERATOR",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    output = res.stdout
    assert "cdc_live_" in output
    assert "API Key created successfully" in output


def test_cli_create_api_key_default_role():
    cmd = [
        sys.executable,
        "-m",
        "services.api.src.cli",
        "create-api-key",
        "--name",
        "CLI Default Role Key",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    output = res.stdout
    assert "cdc_live_" in output
    assert "API Key created successfully for 'CLI Default Role Key' [OPERATOR]" in output


def test_cli_create_api_key_admin_role():
    cmd = [
        sys.executable,
        "-m",
        "services.api.src.cli",
        "create-api-key",
        "--name",
        "CLI Admin Role Key",
        "--role",
        "ADMIN",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    output = res.stdout
    assert "cdc_live_" in output
    assert "API Key created successfully for 'CLI Admin Role Key' [ADMIN]" in output


def test_cli_create_api_key_lowercase_role():
    cmd = [
        sys.executable,
        "-m",
        "services.api.src.cli",
        "create-api-key",
        "--name",
        "CLI Lowercase Role Key",
        "--role",
        "operator",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    output = res.stdout
    assert "cdc_live_" in output
    assert "API Key created successfully for 'CLI Lowercase Role Key' [OPERATOR]" in output



def test_cli_missing_name_fails():
    cmd = [
        sys.executable,
        "-m",
        "services.api.src.cli",
        "create-api-key",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode != 0
    assert "required" in res.stderr.lower() or "--name" in res.stderr.lower()


def test_cli_invalid_role_fails():
    cmd = [
        sys.executable,
        "-m",
        "services.api.src.cli",
        "create-api-key",
        "--name",
        "Invalid Key",
        "--role",
        "SUPERUSER",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode != 0
    assert "invalid choice" in res.stderr.lower() or "error" in res.stderr.lower()


def test_create_api_key_cmd_persists_in_db():
    from services.api.src.cli import create_api_key_cmd
    import uuid

    key_name = f"Direct DB Test Key {uuid.uuid4().hex[:8]}"
    raw_key = create_api_key_cmd(name=key_name, role="OPERATOR")

    assert raw_key.startswith("cdc_live_")
    assert len(raw_key) == 73

    expected_hash = hash_api_key(raw_key)
    with SessionLocal() as db:
        record = db.execute(select(ApiKey).where(ApiKey.key_hash == expected_hash)).scalar_one_or_none()
        assert record is not None
        assert record.name == key_name
        assert record.role == "OPERATOR"
        assert record.key_hash == expected_hash
        assert record.prefix == raw_key[:16]
        assert record.is_active is True



def test_main_function_direct_invocation(capsys):
    from services.api.src.cli import main

    main(["create-api-key", "--name", "Direct Main Key", "--role", "OPERATOR"])
    captured = capsys.readouterr()
    assert "API Key created successfully for 'Direct Main Key' [OPERATOR]:" in captured.out
    assert "cdc_live_" in captured.out
    assert "Store this key securely" in captured.out

