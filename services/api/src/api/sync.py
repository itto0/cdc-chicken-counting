from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.src.db.models import CountAggregate, CountEvent, HealthSample
from services.api.src.db.session import get_db
from shared.contracts import SyncBatchPayload

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])


@router.post("/batch")
def sync_batch(payload: SyncBatchPayload, db: Session = Depends(get_db)):
    ingested_events = 0
    duplicates_skipped = 0
    ingested_aggregates = 0
    health_ingested = False

    for ev in payload.events:
        event_record = CountEvent(
            line_id=payload.line_id,
            track_id=ev.track_id,
            ts_utc=ev.ts_utc,
            confidence=ev.confidence,
        )
        try:
            with db.begin_nested():
                db.add(event_record)
                db.flush()
            ingested_events += 1
        except IntegrityError:
            duplicates_skipped += 1

    for agg in payload.aggregates:
        agg_record = CountAggregate(
            line_id=payload.line_id,
            window_start=agg.window_start,
            window_end=agg.window_end,
            count=agg.count,
            rate_per_min=agg.rate_per_min,
            confidence_avg=agg.confidence_avg,
            status=agg.status,
        )
        db.add(agg_record)
        ingested_aggregates += 1

    if payload.health is not None:
        health_record = HealthSample(
            line_id=payload.line_id,
            fps=payload.health.fps,
            latency_p95_ms=payload.health.latency_p95_ms,
            cpu_pct=payload.health.cpu_pct,
            mem_pct=payload.health.mem_pct,
            stream_state=payload.health.stream_state,
            model_name=payload.health.model_name,
            model_version=payload.health.model_version,
        )
        db.add(health_record)
        health_ingested = True

    db.commit()

    return {
        "status": "success",
        "line_id": payload.line_id,
        "ingested_events": ingested_events,
        "duplicates_skipped": duplicates_skipped,
        "ingested_aggregates": ingested_aggregates,
        "health_ingested": health_ingested,
    }
