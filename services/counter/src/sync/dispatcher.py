"""Outbox synchronization worker pushing batches to central API with backoff."""

from typing import Any
import httpx
from services.counter.src.storage.db import LocalStorage


class OutboxSyncDispatcher:
    """Dispatches unsynced events, aggregates, and health metrics to cloud API."""

    def __init__(
        self,
        storage: LocalStorage,
        api_url: str,
        line_id: str,
        http_client: Any = None,
        batch_limit: int = 100,
        timeout: float = 5.0,
        max_backoff_sec: float = 30.0,
    ) -> None:
        self.storage = storage
        self.api_url = api_url
        self.line_id = line_id
        self._owns_client = http_client is None
        self.http_client = http_client if http_client is not None else httpx.Client()
        self.batch_limit = batch_limit
        self.timeout = timeout
        self.backoff_sec = 1.0
        self.max_backoff_sec = max_backoff_sec

    def sync_once(self) -> int:
        """
        Attempt to sync a single batch of unsynced items from outbox storage.

        Returns:
            The total number of synced records (events + aggregates + health) on success,
            or 0 if outbox was empty or dispatch failed.
        """
        payload, item_ids = self.storage.get_unsynced_batch(
            line_id=self.line_id, limit=self.batch_limit
        )
        if payload is None:
            return 0

        event_ids = item_ids.get("event_ids", [])
        aggregate_ids = item_ids.get("aggregate_ids", [])
        health_ids = item_ids.get("health_ids", [])

        total_items = len(event_ids) + len(aggregate_ids) + len(health_ids)
        if total_items == 0:
            return 0

        try:
            resp = self.http_client.post(
                self.api_url,
                json=payload.model_dump(mode="json"),
                timeout=self.timeout,
            )
            if resp.status_code in (200, 201):
                if event_ids:
                    self.storage.mark_events_synced(event_ids)
                if aggregate_ids:
                    self.storage.mark_aggregates_synced(aggregate_ids)
                if health_ids:
                    self.storage.mark_health_synced(health_ids)
                self.backoff_sec = 1.0
                return total_items
            else:
                self._apply_backoff()
                return 0
        except Exception:
            self._apply_backoff()
            return 0

    def _apply_backoff(self) -> None:
        """Double backoff delay up to max_backoff_sec."""
        self.backoff_sec = min(self.max_backoff_sec, self.backoff_sec * 2.0)

    def close(self) -> None:
        """Close the underlying HTTP client if managed by dispatcher."""
        if hasattr(self.http_client, "close") and callable(self.http_client.close):
            self.http_client.close()

    def __enter__(self) -> "OutboxSyncDispatcher":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
