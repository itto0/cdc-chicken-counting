import math
import re
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from services.api.src.db.models import Line, HealthSample, CountEvent
from services.api.src.db.session import get_db

router = APIRouter(prefix="/api/v1/lines", tags=["lines"])

VALID_DIRECTIONS = ("down", "up", "left", "right", "in", "out")


def validate_coords_format(coords: Optional[str]) -> Optional[str]:
    if coords is None or coords.strip() == "":
        return None
    parts = [p.strip() for p in coords.split(",")]
    if len(parts) != 4:
        raise ValueError("line_coords must contain 4 comma-separated numbers (x1,y1,x2,y2)")
    for p in parts:
        try:
            val = float(p)
        except ValueError:
            raise ValueError("All coordinates in line_coords must be valid numbers")
        if not math.isfinite(val):
            raise ValueError("All coordinates in line_coords must be finite numbers")
    return ",".join(parts)


class LineCreatePayload(BaseModel):
    id: str = Field(..., min_length=2, max_length=50, description="Alphanumeric slug, e.g. 'line-2'")
    name: str = Field(..., min_length=1, max_length=100)
    daily_target: int = Field(60000, gt=0)
    video_url: Optional[str] = Field(None, max_length=500)
    line_coords: Optional[str] = Field(None, max_length=100)
    line_direction: str = Field("down")
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty or whitespace only")
        return v

    @field_validator("id")
    @classmethod
    def validate_id_slug(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^[a-zA-Z0-9_-]{2,50}$", v):
            raise ValueError("id must contain only letters, numbers, hyphens, and underscores, between 2 and 50 characters")
        return v

    @field_validator("line_coords")
    @classmethod
    def validate_coords(cls, v: Optional[str]) -> Optional[str]:
        return validate_coords_format(v)

    @field_validator("line_direction")
    @classmethod
    def validate_direction(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in VALID_DIRECTIONS:
            raise ValueError(f"line_direction must be one of {VALID_DIRECTIONS}")
        return v


class LineUpdatePayload(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    daily_target: Optional[int] = Field(None, gt=0)
    video_url: Optional[str] = Field(None, max_length=500)
    line_coords: Optional[str] = Field(None, max_length=100)
    line_direction: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty or whitespace only")
        return v

    @field_validator("line_coords")
    @classmethod
    def validate_coords(cls, v: Optional[str]) -> Optional[str]:
        return validate_coords_format(v)

    @field_validator("line_direction")
    @classmethod
    def validate_direction(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.lower().strip()
        if v not in VALID_DIRECTIONS:
            raise ValueError(f"line_direction must be one of {VALID_DIRECTIONS}")
        return v


class LineStatusDTO(BaseModel):
    id: str
    name: str
    daily_target: int
    video_url: Optional[str] = None
    line_coords: Optional[str] = None
    line_direction: str = "down"
    is_active: bool
    status: str
    last_ping: Optional[str] = None
    total_today: int


class LineDetailDTO(BaseModel):
    id: str
    name: str
    daily_target: int
    video_url: Optional[str] = None
    line_coords: Optional[str] = None
    line_direction: str = "down"
    is_active: bool


@router.post("", response_model=LineDetailDTO, status_code=status.HTTP_201_CREATED)
def create_line(payload: LineCreatePayload, db: Session = Depends(get_db)):
    existing = db.get(Line, payload.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Line with ID '{payload.id}' already exists",
        )

    new_line = Line(
        id=payload.id,
        name=payload.name,
        daily_target=payload.daily_target,
        video_url=payload.video_url,
        line_coords=payload.line_coords,
        line_direction=payload.line_direction,
        is_active=payload.is_active,
    )
    try:
        db.add(new_line)
        db.commit()
        db.refresh(new_line)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Line with ID '{payload.id}' already exists",
        )
    return LineDetailDTO(
        id=new_line.id,
        name=new_line.name,
        daily_target=new_line.daily_target,
        video_url=new_line.video_url,
        line_coords=new_line.line_coords,
        line_direction=new_line.line_direction or "down",
        is_active=new_line.is_active,
    )


@router.get("", response_model=list[LineStatusDTO])
def list_lines(db: Session = Depends(get_db)):
    lines = db.scalars(select(Line)).all()
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

    result = []
    for line in lines:
        latest_health = db.scalars(
            select(HealthSample)
            .where(HealthSample.line_id == line.id)
            .order_by(HealthSample.timestamp.desc())
            .limit(1)
        ).first()

        status_str = "offline"
        last_ping_str = None
        if latest_health:
            last_ping_str = latest_health.timestamp.isoformat()
            ts = latest_health.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if now - ts <= timedelta(seconds=60):
                status_str = latest_health.stream_state.lower()
            else:
                status_str = "offline"

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
                video_url=line.video_url,
                line_coords=line.line_coords,
                line_direction=line.line_direction or "down",
                is_active=line.is_active,
                status=status_str,
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
        video_url=line.video_url,
        line_coords=line.line_coords,
        line_direction=line.line_direction or "down",
        is_active=line.is_active,
    )


@router.put("/{line_id}", response_model=LineDetailDTO)
def update_line(line_id: str, payload: LineUpdatePayload, db: Session = Depends(get_db)):
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")
    fields_set = payload.model_fields_set
    if "name" in fields_set and payload.name is not None:
        line.name = payload.name
    if "daily_target" in fields_set and payload.daily_target is not None:
        line.daily_target = payload.daily_target
    if "video_url" in fields_set:
        line.video_url = payload.video_url
    if "line_coords" in fields_set:
        line.line_coords = payload.line_coords
    if "line_direction" in fields_set and payload.line_direction is not None:
        line.line_direction = payload.line_direction
    if "is_active" in fields_set and payload.is_active is not None:
        line.is_active = payload.is_active
    db.commit()
    db.refresh(line)
    return LineDetailDTO(
        id=line.id,
        name=line.name,
        daily_target=line.daily_target,
        video_url=line.video_url,
        line_coords=line.line_coords,
        line_direction=line.line_direction or "down",
        is_active=line.is_active,
    )


@router.delete("/{line_id}", response_model=LineDetailDTO)
def delete_line(line_id: str, db: Session = Depends(get_db)):
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")
    line.is_active = False
    db.commit()
    db.refresh(line)
    return LineDetailDTO(
        id=line.id,
        name=line.name,
        daily_target=line.daily_target,
        video_url=line.video_url,
        line_coords=line.line_coords,
        line_direction=line.line_direction or "down",
        is_active=line.is_active,
    )
