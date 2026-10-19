"""Object tracking and virtual line crossing counter module."""

try:
    from .tracker import (
        ChickenCounter,
        TrackedObject,
        VirtualLineZone,
    )
except ImportError:
    try:
        from src.tracking.tracker import (
            ChickenCounter,
            TrackedObject,
            VirtualLineZone,
        )
    except ImportError:
        from services.counter.src.tracking.tracker import (
            ChickenCounter,
            TrackedObject,
            VirtualLineZone,
        )

__all__ = ["ChickenCounter", "TrackedObject", "VirtualLineZone"]
