"""SQLite outbox storage with WAL mode for local edge resilience."""

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import threading
from typing import Any
try:
    from src.contracts import (
        CountAggregateDTO,
        CountEventDTO,
        HealthSampleDTO,
        SyncBatchPayload,
    )
except ImportError:
    try:
        from services.counter.src.contracts import (
            CountAggregateDTO,
            CountEventDTO,
            HealthSampleDTO,
            SyncBatchPayload,
        )
    except ImportError:
        from shared.contracts import (
            CountAggregateDTO,
            CountEventDTO,
            HealthSampleDTO,
            SyncBatchPayload,
        )


class LocalStorage:
    """Manages local SQLite WAL outbox queue for events, aggregates, and health metrics."""

    def __init__(self, db_path: str = "counter_outbox.db") -> None:
        self.db_path = db_path
        self._lock = threading.RLock()

    def _get_connection(self) -> sqlite3.Connection:
        if self.db_path != ":memory:":
            parent = Path(self.db_path).parent
            if str(parent) not in ("", "."):
                parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def init_db(self) -> None:
        """Initialize database tables and indices with WAL journal mode."""
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.executescript("""
                    CREATE TABLE IF NOT EXISTS outbox_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        line_id TEXT NOT NULL,
                        track_id INTEGER NOT NULL,
                        ts_utc TEXT NOT NULL,
                        confidence REAL NOT NULL,
                        synced_at TEXT NULL
                    );

                    CREATE TABLE IF NOT EXISTS outbox_aggregates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        line_id TEXT NOT NULL,
                        window_start TEXT NOT NULL,
                        window_end TEXT NOT NULL,
                        count INTEGER NOT NULL,
                        rate_per_min REAL NOT NULL,
                        confidence_avg REAL NOT NULL,
                        status TEXT NOT NULL DEFAULT 'NORMAL',
                        synced_at TEXT NULL
                    );

                    CREATE TABLE IF NOT EXISTS health_samples (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        line_id TEXT NOT NULL,
                        ts_utc TEXT NOT NULL,
                        fps REAL NOT NULL,
                        latency_p95_ms REAL NOT NULL,
                        cpu_pct REAL NOT NULL,
                        mem_pct REAL NOT NULL,
                        stream_state TEXT NOT NULL,
                        model_name TEXT NOT NULL DEFAULT 'yolo26n',
                        model_version TEXT NOT NULL DEFAULT 'v1.0',
                        synced_at TEXT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_outbox_events_synced ON outbox_events(synced_at);
                    CREATE INDEX IF NOT EXISTS idx_outbox_events_line ON outbox_events(line_id);

                    CREATE INDEX IF NOT EXISTS idx_outbox_aggregates_synced ON outbox_aggregates(synced_at);
                    CREATE INDEX IF NOT EXISTS idx_outbox_aggregates_line ON outbox_aggregates(line_id);

                    CREATE INDEX IF NOT EXISTS idx_health_samples_synced ON health_samples(synced_at);
                    CREATE INDEX IF NOT EXISTS idx_health_samples_line ON health_samples(line_id);
                    """)
            finally:
                conn.close()

    def insert_event(self, line_id: str, event: CountEventDTO) -> int:
        """Insert a count event into outbox_events table."""
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    cursor = conn.execute(
                        """
                        INSERT INTO outbox_events (line_id, track_id, ts_utc, confidence)
                        VALUES (?, ?, ?, ?)
                        """,
                        (line_id, event.track_id, event.ts_utc.isoformat(), event.confidence),
                    )
                    return cursor.lastrowid or 0
            finally:
                conn.close()

    def insert_aggregate(self, line_id: str, aggregate: CountAggregateDTO) -> int:
        """Insert a window aggregate into outbox_aggregates table."""
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    cursor = conn.execute(
                        """
                        INSERT INTO outbox_aggregates (
                            line_id, window_start, window_end, count, rate_per_min,
                            confidence_avg, status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            line_id,
                            aggregate.window_start.isoformat(),
                            aggregate.window_end.isoformat(),
                            aggregate.count,
                            aggregate.rate_per_min,
                            aggregate.confidence_avg,
                            aggregate.status,
                        ),
                    )
                    return cursor.lastrowid or 0
            finally:
                conn.close()

    def insert_health(
        self,
        line_id: str,
        health: HealthSampleDTO,
        ts_utc: datetime | None = None,
    ) -> int:
        """Insert a health sample into health_samples table."""
        ts = ts_utc or datetime.now(timezone.utc)
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    cursor = conn.execute(
                        """
                        INSERT INTO health_samples (
                            line_id, ts_utc, fps, latency_p95_ms, cpu_pct, mem_pct,
                            stream_state, model_name, model_version
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            line_id,
                            ts.isoformat(),
                            health.fps,
                            health.latency_p95_ms,
                            health.cpu_pct,
                            health.mem_pct,
                            health.stream_state,
                            health.model_name,
                            health.model_version,
                        ),
                    )
                    return cursor.lastrowid or 0
            finally:
                conn.close()

    def get_unsynced_events(
        self, limit: int = 100, line_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Retrieve unsynced count events up to limit, optionally filtered by line_id."""
        query = "SELECT id, line_id, track_id, ts_utc, confidence FROM outbox_events WHERE synced_at IS NULL"
        params: list[Any] = []
        if line_id is not None:
            query += " AND line_id = ?"
            params.append(line_id)
        query += " ORDER BY id ASC LIMIT ?"
        params.append(limit)

        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
            finally:
                conn.close()

    def get_unsynced_aggregates(
        self, limit: int = 100, line_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Retrieve unsynced window aggregates up to limit, optionally filtered by line_id."""
        query = (
            "SELECT id, line_id, window_start, window_end, count, rate_per_min, confidence_avg, status "
            "FROM outbox_aggregates WHERE synced_at IS NULL"
        )
        params: list[Any] = []
        if line_id is not None:
            query += " AND line_id = ?"
            params.append(line_id)
        query += " ORDER BY id ASC LIMIT ?"
        params.append(limit)

        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
            finally:
                conn.close()

    def get_unsynced_health(
        self, limit: int = 100, line_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Retrieve unsynced health samples up to limit, optionally filtered by line_id."""
        query = (
            "SELECT id, line_id, ts_utc, fps, latency_p95_ms, cpu_pct, mem_pct, stream_state, model_name, model_version "
            "FROM health_samples WHERE synced_at IS NULL"
        )
        params: list[Any] = []
        if line_id is not None:
            query += " AND line_id = ?"
            params.append(line_id)
        query += " ORDER BY id ASC LIMIT ?"
        params.append(limit)

        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
            finally:
                conn.close()

    def mark_events_synced(self, event_ids: list[int]) -> None:
        """Mark the specified event IDs as synced."""
        if not event_ids:
            return
        placeholders = ",".join("?" for _ in event_ids)
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute(
                        f"UPDATE outbox_events SET synced_at = ? WHERE id IN ({placeholders})",
                        [now_iso, *event_ids],
                    )
            finally:
                conn.close()

    def mark_aggregates_synced(self, aggregate_ids: list[int]) -> None:
        """Mark the specified aggregate IDs as synced."""
        if not aggregate_ids:
            return
        placeholders = ",".join("?" for _ in aggregate_ids)
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute(
                        f"UPDATE outbox_aggregates SET synced_at = ? WHERE id IN ({placeholders})",
                        [now_iso, *aggregate_ids],
                    )
            finally:
                conn.close()

    def mark_health_synced(self, health_ids: list[int]) -> None:
        """Mark the specified health sample IDs as synced."""
        if not health_ids:
            return
        placeholders = ",".join("?" for _ in health_ids)
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute(
                        f"UPDATE health_samples SET synced_at = ? WHERE id IN ({placeholders})",
                        [now_iso, *health_ids],
                    )
            finally:
                conn.close()

    def get_unsynced_batch(
        self, line_id: str, limit: int = 100
    ) -> tuple[SyncBatchPayload | None, dict[str, list[int]]]:
        """
        Package pending items for line_id into a SyncBatchPayload and return their IDs.

        Returns (payload, {"event_ids": [...], "aggregate_ids": [...], "health_ids": [...]})
        If nothing is pending, returns (None, empty_ids_dict).
        """
        with self._lock:
            unsynced_events = self.get_unsynced_events(limit=limit, line_id=line_id)
            unsynced_aggs = self.get_unsynced_aggregates(limit=limit, line_id=line_id)
            unsynced_health = self.get_unsynced_health(limit=1, line_id=line_id)

            event_ids = [row["id"] for row in unsynced_events]
            agg_ids = [row["id"] for row in unsynced_aggs]
            health_ids = [row["id"] for row in unsynced_health]

            empty_ids: dict[str, list[int]] = {
                "event_ids": [],
                "aggregate_ids": [],
                "health_ids": [],
            }

            if not event_ids and not agg_ids and not health_ids:
                return None, empty_ids

            events = [
                CountEventDTO(
                    track_id=row["track_id"],
                    ts_utc=datetime.fromisoformat(row["ts_utc"]),
                    confidence=row["confidence"],
                )
                for row in unsynced_events
            ]

            aggregates = [
                CountAggregateDTO(
                    window_start=datetime.fromisoformat(row["window_start"]),
                    window_end=datetime.fromisoformat(row["window_end"]),
                    count=row["count"],
                    rate_per_min=row["rate_per_min"],
                    confidence_avg=row["confidence_avg"],
                    status=row["status"],
                )
                for row in unsynced_aggs
            ]

            health_dto: HealthSampleDTO | None = None
            if unsynced_health:
                h = unsynced_health[0]
                health_dto = HealthSampleDTO(
                    fps=h["fps"],
                    latency_p95_ms=h["latency_p95_ms"],
                    cpu_pct=h["cpu_pct"],
                    mem_pct=h["mem_pct"],
                    stream_state=h["stream_state"],
                    model_name=h["model_name"],
                    model_version=h["model_version"],
                )

            payload = SyncBatchPayload(
                line_id=line_id,
                events=events,
                aggregates=aggregates,
                health=health_dto,
            )

            return payload, {
                "event_ids": event_ids,
                "aggregate_ids": agg_ids,
                "health_ids": health_ids,
            }

