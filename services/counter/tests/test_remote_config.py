import httpx
import pytest
from unittest.mock import patch, MagicMock
from services.counter.main import fetch_remote_line_config


def test_fetch_remote_config_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "line-2",
        "name": "Line 2",
        "video_url": "rtsp://camera2/stream",
        "line_coords": "100,200,500,200",
        "line_direction": "up",
    }

    with patch("httpx.get", return_value=mock_resp) as mock_get:
        config = fetch_remote_line_config(
            api_sync_url="http://central-api:8070/api/v1/sync/batch",
            line_id="line-2",
            timeout=2.0,
        )
        assert config is not None
        assert config["video_url"] == "rtsp://camera2/stream"
        assert config["line_coords"] == "100,200,500,200"
        assert config["line_direction"] == "up"
        mock_get.assert_called_once_with(
            "http://central-api:8070/api/v1/lines/line-2",
            timeout=2.0,
        )


def test_fetch_remote_config_offline_or_error_returns_none():
    with patch("httpx.get", side_effect=httpx.ConnectError("Failed to connect")):
        config = fetch_remote_line_config(
            api_sync_url="http://unreachable-api:8070/api/v1/sync/batch",
            line_id="line-2",
            timeout=1.0,
        )
        assert config is None


def test_fetch_remote_config_http_non_200_returns_none():
    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with patch("httpx.get", return_value=mock_resp):
        config = fetch_remote_line_config(
            api_sync_url="http://central-api:8070/api/v1/sync/batch",
            line_id="nonexistent-line",
        )
        assert config is None


def test_fetch_remote_config_url_without_api_v1():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": "line-x"}

    with patch("httpx.get", return_value=mock_resp) as mock_get:
        config = fetch_remote_line_config(
            api_sync_url="http://central-api:8070/",
            line_id="line-x",
        )
        assert config == {"id": "line-x"}
        mock_get.assert_called_once_with(
            "http://central-api:8070/lines/line-x",
            timeout=3.0,
        )


def test_main_startup_remote_config_applied(monkeypatch):
    from services.counter.main import main

    monkeypatch.setenv("LINE_ID", "line-remote")
    monkeypatch.setenv("API_SYNC_URL", "http://central:8000/api/v1/sync/batch")
    monkeypatch.setenv("VIDEO_PATH", "")
    monkeypatch.delenv("LINE_DIRECTION", raising=False)

    mock_remote_config = {
        "id": "line-remote",
        "video_url": "rtsp://camera/remote_stream",
        "line_coords": "10,20,30,40",
        "line_direction": "left",
    }

    with patch("services.counter.main.fetch_remote_line_config", return_value=mock_remote_config), \
         patch("services.counter.main.CounterService") as mock_service_cls:
        mock_instance = MagicMock()
        mock_service_cls.return_value = mock_instance

        main([])

        mock_service_cls.assert_called_once()
        kwargs = mock_service_cls.call_args.kwargs
        assert kwargs["video_path"] == "rtsp://camera/remote_stream"
        assert kwargs["video_source_type"] == "file"
        assert kwargs["line_coords"] == (10.0, 20.0, 30.0, 40.0)
        assert kwargs["line_direction"] == "left"


def test_main_startup_remote_config_local_override_precedence(monkeypatch):
    """Local CLI or environment arguments take precedence over remote config."""
    from services.counter.main import main

    monkeypatch.setenv("LINE_ID", "line-remote")
    monkeypatch.setenv("API_SYNC_URL", "http://central:8000/api/v1/sync/batch")
    monkeypatch.setenv("VIDEO_PATH", "local_file.mp4")
    monkeypatch.setenv("LINE_COORDS", "1,2,3,4")
    monkeypatch.setenv("LINE_DIRECTION", "up")

    mock_remote_config = {
        "id": "line-remote",
        "video_url": "rtsp://remote/stream",
        "line_coords": "100,200,300,400",
        "line_direction": "down",
    }

    with patch("services.counter.main.fetch_remote_line_config", return_value=mock_remote_config), \
         patch("services.counter.main.CounterService") as mock_service_cls:
        mock_instance = MagicMock()
        mock_service_cls.return_value = mock_instance

        main([])

        mock_service_cls.assert_called_once()
        kwargs = mock_service_cls.call_args.kwargs
        # Local settings are preserved
        assert kwargs["video_path"] == "local_file.mp4"
        assert kwargs["line_coords"] == (1.0, 2.0, 3.0, 4.0)
        assert kwargs["line_direction"] == "up"


def test_main_startup_remote_config_disabled_when_no_sync(monkeypatch):
    from services.counter.main import main

    monkeypatch.setenv("NO_SYNC", "true")

    with patch("services.counter.main.fetch_remote_line_config") as mock_fetch, \
         patch("services.counter.main.CounterService") as mock_service_cls:
        mock_instance = MagicMock()
        mock_service_cls.return_value = mock_instance

        main([])

        mock_fetch.assert_not_called()

