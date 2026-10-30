from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from shared.contracts import CountingBatchDTO, CountEventDTO, SyncBatchPayload


def test_counting_batch_dto_valid():
    now = datetime.now(timezone.utc)
    dto = CountingBatchDTO(
        batch_id="line-1_20261030_120000",
        line_id="line-1",
        start_time=now,
        finish_time=now,
        total_count=120,
        status="COMPLETED",
    )
    assert dto.batch_id == "line-1_20261030_120000"
    assert dto.status == "COMPLETED"
    assert dto.total_count == 120


def test_counting_batch_dto_defaults_and_validation():
    now = datetime.now(timezone.utc)
    dto = CountingBatchDTO(
        batch_id="line-1_20261030_120000",
        start_time=now,
    )
    assert dto.line_id == "line-1"
    assert dto.status == "ACTIVE"
    assert dto.total_count == 0
    assert dto.finish_time is None

    with pytest.raises(ValidationError):
        CountingBatchDTO(
            batch_id="b1",
            start_time=now,
            total_count=-1,
        )


def test_count_event_dto_with_batch_id():
    now = datetime.now(timezone.utc)
    event_with_batch = CountEventDTO(
        track_id=1,
        ts_utc=now,
        confidence=0.95,
        batch_id="batch_123",
    )
    assert event_with_batch.batch_id == "batch_123"

    event_without_batch = CountEventDTO(
        track_id=2,
        ts_utc=now,
        confidence=0.90,
    )
    assert event_without_batch.batch_id is None


def test_sync_batch_payload_with_batches():
    now = datetime.now(timezone.utc)
    payload = SyncBatchPayload(
        line_id="line-1",
        batches=[
            CountingBatchDTO(
                batch_id="b1",
                start_time=now,
                total_count=50,
                status="COMPLETED",
            )
        ],
    )
    assert len(payload.batches) == 1
    assert payload.batches[0].batch_id == "b1"
