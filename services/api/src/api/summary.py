from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from services.api.src.db.models import Line, HealthSample, CountEvent, Alarm
from services.api.src.db.session import get_db

router = APIRouter(prefix="/api/v1/lines", tags=["summary"])


class LineSummaryResponse(BaseModel):
    line_id: str
    period: str
    total_count: int
    target_count: int
    target_attainment_pct: float
    current_speed_cpm: float
    target_speed_cpm: float
    active_alarms_count: int
    camera_status: str
    last_event_time: Optional[str]
    fps: float
    latency_p95_ms: float


@router.get("/{line_id}/summary", response_model=LineSummaryResponse)
def get_line_summary(
    line_id: str,
    period: str = Query(default="today", pattern="^(today|shift|week)$"),
    db: Session = Depends(get_db),
):
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

    now = datetime.now(timezone.utc)
    if period == "today":
        start_time = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    elif period == "shift":
        start_time = now - timedelta(hours=8)
    elif period == "week":
        start_time = now - timedelta(days=7)
    else:
        start_time = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

    # Total count in period
    total_count = db.scalar(
        select(func.count(CountEvent.id))
        .where(CountEvent.line_id == line_id)
        .where(CountEvent.ts_utc >= start_time)
    ) or 0

    target = line.daily_target or 62000
    attainment_pct = round((total_count / target) * 100.0, 1) if target > 0 else 0.0

    # Recent speed (count in last 5 minutes)
    five_min_ago = now - timedelta(minutes=5)
    recent_count = db.scalar(
        select(func.count(CountEvent.id))
        .where(CountEvent.line_id == line_id)
        .where(CountEvent.ts_utc >= five_min_ago)
    ) or 0
    current_speed = round(recent_count / 5.0, 1)

    # Active alarms
    active_alarms = db.scalar(
        select(func.count(Alarm.id))
        .where(Alarm.line_id == line_id)
        .where(Alarm.status.in_(["OPEN", "ACKNOWLEDGED"]))
    ) or 0

    # Latest Health
    latest_health = db.scalars(
        select(HealthSample)
        .where(HealthSample.line_id == line_id)
        .order_by(HealthSample.timestamp.desc())
        .limit(1)
    ).first()

    camera_status = "offline"
    fps = 0.0
    latency = 0.0
    if latest_health:
        ts = latest_health.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if 0 <= (now - ts).total_seconds() <= 60:
            camera_status = latest_health.stream_state.lower()
        fps = round(latest_health.fps, 1)
        latency = round(latest_health.latency_p95_ms, 1)

    # Last count event
    last_event = db.scalars(
        select(CountEvent)
        .where(CountEvent.line_id == line_id)
        .order_by(CountEvent.ts_utc.desc())
        .limit(1)
    ).first()
    last_event_str = last_event.ts_utc.isoformat() if last_event else None

    return LineSummaryResponse(
        line_id=line_id,
        period=period,
        total_count=total_count,
        target_count=target,
        target_attainment_pct=attainment_pct,
        current_speed_cpm=current_speed,
        target_speed_cpm=120.0,
        active_alarms_count=active_alarms,
        camera_status=camera_status,
        last_event_time=last_event_str,
        fps=fps,
        latency_p95_ms=latency,
    )
