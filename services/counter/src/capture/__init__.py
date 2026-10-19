"""Capture pipeline abstractions."""

try:
    from .source import (
        FileVideoSource,
        SyntheticVideoSource,
        VideoSource,
    )
except ImportError:
    try:
        from src.capture.source import (
            FileVideoSource,
            SyntheticVideoSource,
            VideoSource,
        )
    except ImportError:
        from services.counter.src.capture.source import (
            FileVideoSource,
            SyntheticVideoSource,
            VideoSource,
        )

__all__ = ["VideoSource", "SyntheticVideoSource", "FileVideoSource"]
