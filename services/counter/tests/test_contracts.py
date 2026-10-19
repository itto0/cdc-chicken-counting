from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
import pytest


def test_standalone_contracts_import():
    from services.counter.src.contracts import (
        CountAggregateDTO,
        CountEventDTO,
        HealthSampleDTO,
        SyncBatchPayload,
    )

    now = datetime.now(timezone.utc)
    event = CountEventDTO(track_id=1, ts_utc=now, confidence=0.95)
    assert event.track_id == 1
    assert event.confidence == 0.95

    agg = CountAggregateDTO(
        window_start=now,
        window_end=now,
        count=10,
        rate_per_min=120.0,
        confidence_avg=0.92,
        status="NORMAL",
    )
    assert agg.count == 10

    health = HealthSampleDTO(
        fps=30.0,
        latency_p95_ms=5.0,
        cpu_pct=15.0,
        mem_pct=25.0,
        stream_state="ONLINE",
    )
    assert health.stream_state == "ONLINE"

    batch = SyncBatchPayload(line_id="line-1", events=[event], aggregates=[agg], health=health)
    assert batch.line_id == "line-1"
    assert len(batch.events) == 1


def test_standalone_env_init():
    from services.counter.src.env import init_env

    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("STANDALONE_COUNTER_TEST_VAR=chicken_farm_456\n", encoding="utf-8")

        os.environ.pop("STANDALONE_COUNTER_TEST_VAR", None)
        try:
            loaded = init_env(dotenv_path=str(env_file))
            assert loaded is True
            assert os.environ.get("STANDALONE_COUNTER_TEST_VAR") == "chicken_farm_456"
        finally:
            os.environ.pop("STANDALONE_COUNTER_TEST_VAR", None)
