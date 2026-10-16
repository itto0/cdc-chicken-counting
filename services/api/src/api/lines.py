from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from services.api.src.db.models import Line, HealthSample, CountEvent
from services.api.src.db.session import get_db

router = APIRouter(prefix="/api/v1/lines", tags=["lines"])


class LineUpdatePayload(BaseModel):
    name: Optional[str] = None
    daily_target: Optional[int] = None
    is_active: Optional[bool] = None


class LineStatusDTO(BaseModel):
    id: str
    name: str
    daily_target: int
    is_active: bool
    status: str
    last_ping: Optional[str] = None
    total_today: int


class LineDetailDTO(BaseModel):
    id: str
    name: str
    daily_target: int
    is_active: bool


@router.get("", response_model=list[LineStatusDTO])
def list_lines(db: Session = Depends(get_db)):
    lines = db.scalars(select(Line)).all()
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day)

    result = []
    for line in lines:
        # Latest health sample
        latest_health = db.scalars(
            select(HealthSample)
            .where(HealthSample.line_id == line.id)
            .order_by(HealthSample.timestamp.desc())
            .limit(1)
        ).first()

        status = "offline"
        last_ping_str = None
        if latest_health:
            last_ping_str = latest_health.timestamp.isoformat()
            ts = latest_health.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if now - ts <= timedelta(seconds=60):
                status = latest_health.stream_state.lower()
            else:
                status = "offline"

        # Count today
        count = db.scalar(
            select(func.count(CountEvent.id))
            .where(CountEvent.line_id == line.id)
            .where(CountEvent.ts_utc >= today_start)
        ) or 0

        result.append(
            LineStatusDTO(
                id=line.id,
                name=line.name,
                daily_target=line.daily_target,
                is_active=line.is_active,
                status=status,
                last_ping=last_ping_str,
                total_today=count,
            )
        )
    return result


@router.get("/{line_id}", response_model=LineDetailDTO)
def get_line(line_id: str, db: Session = Depends(get_db)):
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")
    return LineDetailDTO(
        id=line.id,
        name=line.name,
        daily_target=line.daily_target,
        is_active=line.is_active,
    )


@router.put("/{line_id}", response_model=LineDetailDTO)
def update_line(line_id: str, payload: LineUpdatePayload, db: Session = Depends(get_db)):
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")
    if payload.name is not None:
        line.name = payload.name
    if payload.daily_target is not None:
        line.daily_target = payload.daily_target
    if payload.is_active is not None:
        line.is_active = payload.is_active
    db.commit()
    db.refresh(line)
    return LineDetailDTO(
        id=line.id,
        name=line.name,
        daily_target=line.daily_target,
        is_active=line.is_active,
    )
