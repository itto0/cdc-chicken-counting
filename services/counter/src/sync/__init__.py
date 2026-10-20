"""Outbox synchronization package for edge-to-API telemetry dispatch."""

try:
    from .dispatcher import OutboxSyncDispatcher
    from .streamer import LiveStreamUploader
except ImportError:
    try:
        from src.sync.dispatcher import OutboxSyncDispatcher
        from src.sync.streamer import LiveStreamUploader
    except ImportError:
        from services.counter.src.sync.dispatcher import OutboxSyncDispatcher
        from services.counter.src.sync.streamer import LiveStreamUploader

__all__ = ["OutboxSyncDispatcher", "LiveStreamUploader"]
