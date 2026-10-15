"""Capture pipeline abstractions."""

from services.counter.src.capture.source import (
    FileVideoSource,
    SyntheticVideoSource,
    VideoSource,
)

__all__ = ["VideoSource", "SyntheticVideoSource", "FileVideoSource"]
