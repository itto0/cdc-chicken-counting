"""Tests for VideoSource capture abstractions."""

from pathlib import Path
import cv2
import numpy as np
import pytest

from services.counter.src.capture.source import (
    FileVideoSource,
    SyntheticVideoSource,
    VideoSource,
)


def test_cannot_instantiate_abstract_video_source():
    """Verify VideoSource cannot be instantiated directly."""
    with pytest.raises(TypeError):
        VideoSource()  # type: ignore[abstract]


def test_synthetic_video_source_generates_frames():
    """Verify SyntheticVideoSource starts, generates valid frames, and stops."""
    source = SyntheticVideoSource(width=640, height=480, fps=30)
    source.start()
    success, frame = source.read()
    source.stop()

    assert success is True
    assert isinstance(frame, np.ndarray)
    assert frame.shape == (480, 640, 3)
    assert frame.dtype == np.uint8


def test_synthetic_video_source_stopped_returns_false():
    """Verify SyntheticVideoSource returns (False, None) when stopped or not started."""
    source = SyntheticVideoSource(width=320, height=240)
    # Before start
    success, frame = source.read()
    assert success is False
    assert frame is None

    # After start and stop
    source.start()
    source.stop()
    success, frame = source.read()
    assert success is False
    assert frame is None


def test_synthetic_video_source_moving_object():
    """Verify that successive frames simulate movement (pixels change)."""
    source = SyntheticVideoSource(width=320, height=240, fps=30)
    source.start()
    ret1, frame1 = source.read()
    ret2, frame2 = source.read()
    source.stop()

    assert ret1 is True and ret2 is True
    assert frame1 is not None and frame2 is not None
    # Verify the frames are not identical because of moving target
    assert not np.array_equal(frame1, frame2)


def test_synthetic_video_source_context_manager():
    """Verify SyntheticVideoSource works as a context manager."""
    with SyntheticVideoSource(width=320, height=240, fps=30) as source:
        assert source.is_running is True
        ret, frame = source.read()
        assert ret is True
        assert frame is not None

    assert source.is_running is False
    ret, frame = source.read()
    assert ret is False
    assert frame is None


def test_file_video_source_handles_non_existent_file():
    """Verify FileVideoSource handles non-existent file cleanly without crashing."""
    source = FileVideoSource("non_existent_dummy_video.mp4")
    # Before start
    ret, frame = source.read()
    assert ret is False
    assert frame is None

    # After start
    source.start()
    ret, frame = source.read()
    assert ret is False
    assert frame is None

    # After stop
    source.stop()
    ret, frame = source.read()
    assert ret is False
    assert frame is None


@pytest.fixture
def sample_video_path(tmp_path: Path) -> Path:
    """Create a temporary valid MP4 video with 5 frames."""
    video_path = tmp_path / "test_feed.mp4"
    width, height = 160, 120
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(video_path), fourcc, 30.0, (width, height))

    for i in range(5):
        frame = np.full((height, width, 3), i * 40, dtype=np.uint8)
        writer.write(frame)
    writer.release()
    return video_path


def test_file_video_source_read_video(sample_video_path: Path):
    """Verify FileVideoSource reads frames from a valid video file."""
    source = FileVideoSource(str(sample_video_path), loop=False)
    source.start()

    frames_read = 0
    while True:
        ret, frame = source.read()
        if not ret:
            break
        assert isinstance(frame, np.ndarray)
        assert frame.shape == (120, 160, 3)
        assert frame.dtype == np.uint8
        frames_read += 1

    source.stop()
    assert frames_read == 5

    # Reading after stop returns False
    ret, frame = source.read()
    assert ret is False
    assert frame is None


def test_file_video_source_looping(sample_video_path: Path):
    """Verify FileVideoSource loops back to the start when loop=True."""
    source = FileVideoSource(str(sample_video_path), loop=True)
    source.start()

    # Read more frames than the 5 frames in the file (e.g. 12 frames)
    frames_read = 0
    for _ in range(12):
        ret, frame = source.read()
        assert ret is True
        assert isinstance(frame, np.ndarray)
        frames_read += 1

    source.stop()
    assert frames_read == 12


def test_file_video_source_context_manager(sample_video_path: Path):
    """Verify FileVideoSource works as a context manager."""
    with FileVideoSource(str(sample_video_path)) as source:
        assert source.is_running is True
        ret, frame = source.read()
        assert ret is True
        assert frame is not None

    assert source.is_running is False
    ret, frame = source.read()
    assert ret is False
    assert frame is None
