from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from shared.contracts import (
    AlarmDTO,
    CountAggregateDTO,
    CountEventDTO,
    HealthSampleDTO,
    LineConfigDTO,
    SyncBatchPayload,
)


def test_sync_batch_payload_serialization():
    now = datetime.now(timezone.utc)
    event = CountEventDTO(
        track_id=101,
        ts_utc=now,
        confidence=0.985,
    )
    aggregate = CountAggregateDTO(
        window_start=now,
        window_end=now,
        count=15,
        rate_per_min=15.0,
        confidence_avg=0.97,
    )
    health = HealthSampleDTO(
        fps=30.0,
        latency_p95_ms=32.4,
        cpu_pct=18.5,
        mem_pct=42.1,
        stream_state="ONLINE",
    )
    batch = SyncBatchPayload(
        line_id="lineA",
        events=[event],
        aggregates=[aggregate],
        health=health,
    )

    data = batch.model_dump()
    assert data["line_id"] == "lineA"
    assert len(data["events"]) == 1
    assert data["events"][0]["track_id"] == 101
    assert data["health"]["stream_state"] == "ONLINE"


def test_sync_batch_payload_defaults():
    batch = SyncBatchPayload(line_id="lineB")
    data = batch.model_dump()
    assert data["line_id"] == "lineB"
    assert data["events"] == []
    assert data["aggregates"] == []
    assert data["health"] is None


def test_line_config_dto():
    line = LineConfigDTO(line_id="line_1")
    assert line.line_id == "line_1"
    assert line.line_name == ""
    assert line.direction == "IN"
    assert line.coordinates == []
    assert line.status == "ACTIVE"

    custom_line = LineConfigDTO(
        line_id="line_2",
        line_name="Conveyor North",
        direction="OUT",
        coordinates=[[10, 20], [30, 40]],
        status="INACTIVE",
    )
    data = custom_line.model_dump()
    assert data["line_id"] == "line_2"
    assert data["line_name"] == "Conveyor North"
    assert data["direction"] == "OUT"
    assert data["coordinates"] == [[10, 20], [30, 40]]
    assert data["status"] == "INACTIVE"


def test_alarm_dto():
    now = datetime.now(timezone.utc)
    alarm = AlarmDTO(
        id="alarm-001",
        line_id="line_1",
        alarm_type="FPS_DROP",
        message="FPS dropped below 15",
        ts_utc=now,
    )
    assert alarm.id == "alarm-001"
    assert alarm.severity == "WARNING"
    assert alarm.acknowledged is False

    data = alarm.model_dump()
    assert data["id"] == "alarm-001"
    assert data["line_id"] == "line_1"
    assert data["severity"] == "WARNING"
    assert data["acknowledged"] is False


def test_validation_constraints():
    now = datetime.now(timezone.utc)

    # confidence must be <= 1.0 and >= 0.0
    with pytest.raises(ValidationError):
        CountEventDTO(track_id=1, ts_utc=now, confidence=1.5)

    with pytest.raises(ValidationError):
        CountEventDTO(track_id=1, ts_utc=now, confidence=-0.1)

    # count must be >= 0
    with pytest.raises(ValidationError):
        CountAggregateDTO(
            window_start=now,
            window_end=now,
            count=-1,
            rate_per_min=0.0,
            confidence_avg=0.5,
        )

    # cpu_pct must be <= 100.0
    with pytest.raises(ValidationError):
        HealthSampleDTO(
            fps=30.0,
            latency_p95_ms=10.0,
            cpu_pct=105.0,
            mem_pct=50.0,
        )

    # severity must be INFO, WARNING, or CRITICAL
    with pytest.raises(ValidationError):
        AlarmDTO(
            id="a1",
            line_id="line1",
            alarm_type="TYPE",
            severity="FATAL",  # type: ignore[arg-type]
            message="bad",
            ts_utc=now,
        )


def test_contracts_independent_of_counter_service():
    import sys
    import shared.contracts
    counter_modules = [m for m in sys.modules if m.startswith("services.counter")]
    assert counter_modules == [], f"shared.contracts leaked counter dependencies: {counter_modules}"


def test_health_sample_dto_accuracy_pct():
    from shared.contracts import HealthSampleDTO

    sample = HealthSampleDTO(
        fps=30.0,
        latency_p95_ms=25.0,
        cpu_pct=15.0,
        mem_pct=40.0,
        stream_state="ONLINE",
        accuracy_pct=99.25,
    )
    assert sample.accuracy_pct == 99.25

    with pytest.raises(ValidationError):
        HealthSampleDTO(
            fps=30.0,
            latency_p95_ms=25.0,
            cpu_pct=15.0,
            mem_pct=40.0,
            stream_state="ONLINE",
            accuracy_pct=105.0,
        )


