"""Outbox synchronization package for edge-to-API telemetry dispatch."""

from services.counter.src.sync.dispatcher import OutboxSyncDispatcher

__all__ = ["OutboxSyncDispatcher"]
