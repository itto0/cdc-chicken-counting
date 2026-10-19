"""Outbox synchronization package for edge-to-API telemetry dispatch."""

try:
    from .dispatcher import OutboxSyncDispatcher
except ImportError:
    try:
        from src.sync.dispatcher import OutboxSyncDispatcher
    except ImportError:
        from services.counter.src.sync.dispatcher import OutboxSyncDispatcher

__all__ = ["OutboxSyncDispatcher"]
