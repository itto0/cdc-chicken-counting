import os
import tempfile
from pathlib import Path
from shared.env import init_env


def test_init_env_loads_file_into_os_environ():
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("TEST_CDC_ENV_KEY=chicken_farm_123\n", encoding="utf-8")

        # Ensure env var is not currently set
        os.environ.pop("TEST_CDC_ENV_KEY", None)

        loaded = init_env(dotenv_path=str(env_file))
        assert loaded is True
        assert os.environ.get("TEST_CDC_ENV_KEY") == "chicken_farm_123"

        # Cleanup
        os.environ.pop("TEST_CDC_ENV_KEY", None)


def test_init_env_does_not_override_by_default():
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("TEST_CDC_EXISTING=new_value\n", encoding="utf-8")

        os.environ["TEST_CDC_EXISTING"] = "original_value"

        init_env(dotenv_path=str(env_file), override=False)
        assert os.environ.get("TEST_CDC_EXISTING") == "original_value"

        # Cleanup
        os.environ.pop("TEST_CDC_EXISTING", None)


def test_init_env_overrides_when_override_true():
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("TEST_CDC_EXISTING=override_value\n", encoding="utf-8")

        os.environ["TEST_CDC_EXISTING"] = "original_value"

        init_env(dotenv_path=str(env_file), override=True)
        assert os.environ.get("TEST_CDC_EXISTING") == "override_value"

        # Cleanup
        os.environ.pop("TEST_CDC_EXISTING", None)


def test_init_env_returns_false_when_file_not_found():
    loaded = init_env(dotenv_path="/nonexistent/path/to/.env")
    assert loaded is False


def test_session_reads_database_url_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test_custom_api.db")
    import importlib
    import services.api.src.db.session as session_mod
    importlib.reload(session_mod)
    try:
        assert session_mod.DATABASE_URL == "sqlite:///test_custom_api.db"
    finally:
        monkeypatch.undo()
        importlib.reload(session_mod)


