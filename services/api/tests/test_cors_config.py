import os
from services.api.src.main import get_cors_origins


def test_cors_origins_wildcard():
    assert get_cors_origins("*") == ["*"]
    assert get_cors_origins("") == ["*"]
    assert get_cors_origins(None) == ["*"]


def test_cors_origins_multiple_domains():
    env_str = "https://cdc-frontend.onrender.com, http://localhost:3000, https://custom.com/"
    expected = ["https://cdc-frontend.onrender.com", "http://localhost:3000", "https://custom.com/"]
    assert get_cors_origins(env_str) == expected


def test_cors_origins_from_env_var(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://cdc-frontend.onrender.com, http://localhost:3000")
    assert get_cors_origins() == ["https://cdc-frontend.onrender.com", "http://localhost:3000"]
