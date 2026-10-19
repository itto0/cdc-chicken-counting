"""Detector abstractions and implementations."""

try:
    from .detector import (
        Detection,
        Detector,
        MockDetector,
        ONNXDetector,
        ShackleDetector,
    )
except ImportError:
    try:
        from src.detection.detector import (
            Detection,
            Detector,
            MockDetector,
            ONNXDetector,
            ShackleDetector,
        )
    except ImportError:
        from services.counter.src.detection.detector import (
            Detection,
            Detector,
            MockDetector,
            ONNXDetector,
            ShackleDetector,
        )

__all__ = [
    "Detection",
    "Detector",
    "MockDetector",
    "ONNXDetector",
    "ShackleDetector",
]
