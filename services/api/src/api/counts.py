from datetime import datetime, timezone, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from services.api.src.db.models import Line, CountEvent, CountAggregate
from services.api.src.db.session import get_db
from services.api.src.api.auth import get_current_user, UserDTO
from services.api.src.api.live import broadcast_line_update
from shared.time_utils import to_jakarta, get_jakarta_today_bounds_utc

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


class SingleCountEventRequest(BaseModel):
    track_id: int = Field(ge=1)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    ts_utc: str


class SingleCountEventResponse(BaseModel):
    success: bool
    ingested: bool
    total_today: int
    line_id: str


def _parse_filter_datetime(dt_str: str, param: str) -> datetime:
    try:
        clean_str = dt_str.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid datetime format for {param}. Expected ISO 8601 format.",
        ) from exc


@router.get("/{line_id}/counts", response_model=LineCountsResponse)
def get_line_counts(
    line_id: str,
    from_time: Optional[str] = Query(None, alias="from"),
    to_time: Optional[str] = Query(None, alias="to"),
    period: Optional[str] = Query(None, pattern="^(today|shift|week)$"),
    granularity: str = Query(default="hourly", pattern="^(minute|hourly|daily)$"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: UserDTO = Depends(get_current_user),
):
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

    f_dt: Optional[datetime] = None
    if from_time is not None:
        f_dt = _parse_filter_datetime(from_time, "from_time")

    t_dt: Optional[datetime] = None
    if to_time is not None:
        t_dt = _parse_filter_datetime(to_time, "to_time")

    if period and f_dt is None and t_dt is None:
        if period == "today":
            today_start_utc, today_end_utc = get_jakarta_today_bounds_utc()
            f_dt = today_start_utc.replace(tzinfo=None)
            t_dt = today_end_utc.replace(tzinfo=None)
        elif period == "shift":
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            f_dt = now_utc - timedelta(hours=8)
            t_dt = now_utc
        elif period == "week":
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            f_dt = now_utc - timedelta(days=7)
            t_dt = now_utc

    aggregates_dto: List[AggregateItemDTO] = []

    if granularity == "hourly":
        # First attempt: aggregate directly from CountEvents
        events_query = select(CountEvent.ts_utc).where(CountEvent.line_id == line_id)
        if f_dt is not None:
            events_query = events_query.where(CountEvent.ts_utc >= f_dt)
        if t_dt is not None:
            events_query = events_query.where(CountEvent.ts_utc <= t_dt)
        events_query = events_query.order_by(CountEvent.ts_utc.asc()).limit(100000)
        event_timestamps = db.scalars(events_query).all()

        if event_timestamps:
            hour_counts: dict[datetime, int] = {}
            for ts in event_timestamps:
                jkt_dt = to_jakarta(ts)
                bucket_dt = jkt_dt.replace(minute=0, second=0, microsecond=0)
                hour_counts[bucket_dt] = hour_counts.get(bucket_dt, 0) + 1

            aggregates_dto = [
                AggregateItemDTO(
                    bucket=bucket_dt.isoformat(),
                    count=cnt,
                    rate_per_min=round(cnt / 60.0, 1),
                    status="NORMAL",
                )
                for bucket_dt, cnt in sorted(hour_counts.items(), key=lambda x: x[0])
            ]
        else:
            # Fallback to CountAggregate table if no CountEvents present
            agg_query = select(CountAggregate).where(CountAggregate.line_id == line_id)
            if f_dt is not None:
                agg_query = agg_query.where(CountAggregate.window_start >= f_dt)
            if t_dt is not None:
                agg_query = agg_query.where(CountAggregate.window_start <= t_dt)
            agg_query = agg_query.order_by(CountAggregate.window_start.asc()).limit(10000)
            aggs = db.scalars(agg_query).all()

            if aggs:
                hour_agg_counts: dict[datetime, int] = {}
                hour_agg_rates: dict[datetime, list[float]] = {}
                for a in aggs:
                    jkt_dt = to_jakarta(a.window_start)
                    bucket_dt = jkt_dt.replace(minute=0, second=0, microsecond=0)
                    hour_agg_counts[bucket_dt] = hour_agg_counts.get(bucket_dt, 0) + a.count
                    if bucket_dt not in hour_agg_rates:
                        hour_agg_rates[bucket_dt] = []
                    hour_agg_rates[bucket_dt].append(a.rate_per_min)

                aggregates_dto = [
                    AggregateItemDTO(
                        bucket=bucket_dt.isoformat(),
                        count=cnt,
                        rate_per_min=round(sum(hour_agg_rates[bucket_dt]) / len(hour_agg_rates[bucket_dt]), 1)
                        if hour_agg_rates.get(bucket_dt)
                        else round(cnt / 60.0, 1),
                        status="NORMAL",
                    )
                    for bucket_dt, cnt in sorted(hour_agg_counts.items(), key=lambda x: x[0])
                ]
    else:
        # Non-hourly granularities (minute, daily)
        agg_query = select(CountAggregate).where(CountAggregate.line_id == line_id)
        if f_dt is not None:
            agg_query = agg_query.where(CountAggregate.window_start >= f_dt)
        if t_dt is not None:
            agg_query = agg_query.where(CountAggregate.window_start <= t_dt)
        agg_query = agg_query.order_by(CountAggregate.window_start.asc()).limit(500)
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
    events = db.scalars(
        events_query.order_by(CountEvent.ts_utc.desc(), CountEvent.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()

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


@router.post("/{line_id}/events", response_model=SingleCountEventResponse)
def create_single_count_event(
    line_id: str,
    payload: SingleCountEventRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: UserDTO = Depends(get_current_user),
):
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

    dt = _parse_filter_datetime(payload.ts_utc, "ts_utc")

    event_record = CountEvent(
        line_id=line_id,
        track_id=payload.track_id,
        ts_utc=dt,
        confidence=payload.confidence,
    )

    ingested = False
    try:
        with db.begin_nested():
            db.add(event_record)
            db.flush()
        ingested = True
        response.status_code = 201
    except IntegrityError:
        response.status_code = 200

    db.commit()

    # Query total today
    today_start_utc, today_end_utc = get_jakarta_today_bounds_utc()
    total_today = (
        db.query(func.count(CountEvent.id))
        .filter(
            CountEvent.line_id == line_id,
            CountEvent.ts_utc >= today_start_utc.replace(tzinfo=None),
            CountEvent.ts_utc <= today_end_utc.replace(tzinfo=None),
        )
        .scalar()
        or 0
    )

    if ingested:
        latest_agg = (
            db.query(CountAggregate)
            .filter(CountAggregate.line_id == line_id)
            .order_by(CountAggregate.window_end.desc())
            .first()
        )
        rate = float(latest_agg.rate_per_min) if latest_agg else 0.0
        status = latest_agg.status if latest_agg else "NORMAL"

        broadcast_line_update(
            line_id,
            "count",
            {
                "event_id": event_record.id,
                "track_id": event_record.track_id,
                "ts_utc": f"{event_record.ts_utc.isoformat()}Z",
                "total_today": int(total_today),
                "rate_per_min": rate,
                "status": status,
            },
        )

    return SingleCountEventResponse(
        success=True,
        ingested=ingested,
        total_today=int(total_today),
        line_id=line_id,
    )


