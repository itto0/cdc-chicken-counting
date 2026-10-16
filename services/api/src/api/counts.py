from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from services.api.src.db.models import Line, CountEvent, CountAggregate
from services.api.src.db.session import get_db

router = APIRouter(prefix="/api/v1/lines", tags=["counts"])


class AggregateItemDTO(BaseModel):
    bucket: str
    count: int
    rate_per_min: float
    status: str


class CountEventDTO(BaseModel):
    id: int
    track_id: int
    ts_utc: str
    confidence: float


class PaginationMeta(BaseModel):
    total: int
    page: int
    limit: int


class LineCountsResponse(BaseModel):
    line_id: str
    aggregates: List[AggregateItemDTO]
    events: List[CountEventDTO]
    pagination: PaginationMeta


@router.get("/{line_id}/counts", response_model=LineCountsResponse)
def get_line_counts(
    line_id: str,
    from_time: Optional[str] = Query(None, alias="from"),
    to_time: Optional[str] = Query(None, alias="to"),
    granularity: str = Query(default="hourly"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

    f_dt: Optional[datetime] = None
    if from_time:
        try:
            f_dt = (
                datetime.fromisoformat(from_time.replace("Z", "+00:00"))
                .astimezone(timezone.utc)
                .replace(tzinfo=None)
            )
        except Exception:
            f_dt = None

    t_dt: Optional[datetime] = None
    if to_time:
        try:
            t_dt = (
                datetime.fromisoformat(to_time.replace("Z", "+00:00"))
                .astimezone(timezone.utc)
                .replace(tzinfo=None)
            )
        except Exception:
            t_dt = None

    # Fetch aggregates
    agg_query = select(CountAggregate).where(CountAggregate.line_id == line_id)
    if f_dt is not None:
        agg_query = agg_query.where(CountAggregate.window_start >= f_dt)
    if t_dt is not None:
        agg_query = agg_query.where(CountAggregate.window_start <= t_dt)
    agg_query = agg_query.order_by(CountAggregate.window_start.asc()).limit(100)
    aggs = db.scalars(agg_query).all()

    aggregates_dto = [
        AggregateItemDTO(
            bucket=a.window_start.isoformat(),
            count=a.count,
            rate_per_min=a.rate_per_min,
            status=a.status,
        )
        for a in aggs
    ]

    # Fetch raw events paginated
    events_query = select(CountEvent).where(CountEvent.line_id == line_id)
    if f_dt is not None:
        events_query = events_query.where(CountEvent.ts_utc >= f_dt)
    if t_dt is not None:
        events_query = events_query.where(CountEvent.ts_utc <= t_dt)

    total_events = db.scalar(select(func.count()).select_from(events_query.subquery())) or 0
    offset = (page - 1) * limit
    events = db.scalars(events_query.order_by(CountEvent.ts_utc.desc()).offset(offset).limit(limit)).all()

    events_dto = [
        CountEventDTO(
            id=e.id,
            track_id=e.track_id,
            ts_utc=e.ts_utc.isoformat(),
            confidence=round(e.confidence, 3),
        )
        for e in events
    ]

    return LineCountsResponse(
        line_id=line_id,
        aggregates=aggregates_dto,
        events=events_dto,
        pagination=PaginationMeta(total=total_events, page=page, limit=limit),
    )
