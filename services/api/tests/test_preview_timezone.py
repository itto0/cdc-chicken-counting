from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import cv2
import numpy as np
import pytest

import services.api.src.services.preview as preview_module
from services.api.src.services.preview import FrameGenerator
import shared.time_utils as shared_time_utils


def test_shared_time_utils_imported():
    """Verify that preview module imports standardized time utilities from shared.time_utils."""
    assert hasattr(preview_module, "format_jakarta_display")
    assert preview_module.format_jakarta_display is shared_time_utils.format_jakarta_display
    assert hasattr(preview_module, "now_jakarta")
    assert preview_module.now_jakarta is shared_time_utils.now_jakarta
    assert hasattr(preview_module, "WIB_LABEL")
    assert preview_module.WIB_LABEL is shared_time_utils.WIB_LABEL


def test_format_jakarta_display_utc_conversion():
    """Test that format_jakarta_display converts UTC datetimes to WIB formatted string."""
    utc_dt = datetime(2026, 4, 14, 5, 0, 0, tzinfo=timezone.utc)
    formatted = f"{shared_time_utils.format_jakarta_display(utc_dt)} {shared_time_utils.WIB_LABEL}"
    assert formatted == "2026-04-14 12:00:00 WIB"


def test_frame_generator_synthetic_overlay_wib():
    """Verify that synthetic fallback frame branch stamps Jakarta time and WIB label in HUD overlay."""
    fixed_time = datetime(2026, 4, 14, 12, 0, 0, tzinfo=shared_time_utils.JAKARTA_TZ)
    expected_text = "LIVE PREVIEW - TEST-LINE | 2026-04-14 12:00:00 WIB"

    put_text_calls = []
    original_put_text = cv2.putText

    def mock_put_text(img, text, org, fontFace, fontScale, color, thickness=1, lineType=None):
        put_text_calls.append(text)
        return original_put_text(img, text, org, fontFace, fontScale, color, thickness)

    with patch.object(FrameGenerator, "_resolve_video_path", return_value=None):
        with patch.object(preview_module, "now_jakarta", return_value=fixed_time):
            with patch("cv2.putText", side_effect=mock_put_text):
                frame_bytes = FrameGenerator.generate_jpeg_frame("test-line", 0)

    assert isinstance(frame_bytes, bytes)
    assert any(expected_text in t for t in put_text_calls), f"Expected '{expected_text}' in putText calls: {put_text_calls}"


def test_frame_generator_video_overlay_wib():
    """Verify that video frame branch stamps Jakarta time and WIB label in HUD overlay."""
    fixed_time = datetime(2026, 4, 14, 12, 0, 0, tzinfo=shared_time_utils.JAKARTA_TZ)
    expected_text = "LIVE FEED - TEST-LINE | 2026-04-14 12:00:00 WIB"

    put_text_calls = []
    original_put_text = cv2.putText

    def mock_put_text(img, text, org, fontFace, fontScale, color, thickness=1, lineType=None):
        put_text_calls.append(text)
        return original_put_text(img, text, org, fontFace, fontScale, color, thickness)

    mock_cap = MagicMock()
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    mock_cap.read.return_value = (True, dummy_frame)

    with patch.object(FrameGenerator, "_resolve_video_path", return_value="/mock/video.mp4"):
        with patch.object(FrameGenerator, "_get_capture", return_value=mock_cap):
            with patch.object(FrameGenerator, "_detect_chickens_on_frame", return_value=[]):
                with patch.object(preview_module, "now_jakarta", return_value=fixed_time):
                    with patch("cv2.putText", side_effect=mock_put_text):
                        frame_bytes = FrameGenerator.generate_jpeg_frame("test-line", 0)

    assert isinstance(frame_bytes, bytes)
    assert any(expected_text in t for t in put_text_calls), f"Expected '{expected_text}' in putText calls: {put_text_calls}"


def test_frame_generator_valid_jpeg_bytes():
    """Verify that FrameGenerator.generate_jpeg_frame produces valid JPEG bytes."""
    frame_bytes = FrameGenerator.generate_jpeg_frame("test-line", 0)
    assert isinstance(frame_bytes, bytes)
    assert len(frame_bytes) > 0
    assert frame_bytes.startswith(b"\xff\xd8")
    assert frame_bytes.endswith(b"\xff\xd9")
