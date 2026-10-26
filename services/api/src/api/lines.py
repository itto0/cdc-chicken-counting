import math
import re
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from services.api.src.db.models import Line, HealthSample, CountEvent
from services.api.src.db.session import get_db
from services.api.src.api.auth import get_current_user, require_role, UserDTO
from shared.time_utils import get_jakarta_today_bounds_utc

router = APIRouter(prefix="/api/v1/lines", tags=["lines"])

VALID_DIRECTIONS = ("down", "up", "left", "right", "in", "out")

DEFAULT_RATE_WARNING = 130.0
DEFAULT_RATE_CRITICAL = 110.0


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


def validate_threshold_value(v: Optional[float], field_name: str = "threshold") -> Optional[float]:
    if v is not None:
        if not math.isfinite(v) or v <= 0:
            raise ValueError(f"{field_name} must be a finite number greater than 0")
    return v


class LineCreatePayload(BaseModel):
    id: str = Field(..., min_length=2, max_length=50, description="Alphanumeric slug, e.g. 'line-2'")
    name: str = Field(..., min_length=1, max_length=100)
    daily_target: int = Field(60000, gt=0)
    video_url: Optional[str] = Field(None, max_length=500)
    line_coords: Optional[str] = Field(None, max_length=100)
    line_direction: str = Field("down")
    is_active: bool = True
    rate_warning_threshold: Optional[float] = Field(None, gt=0)
    rate_critical_threshold: Optional[float] = Field(None, gt=0)

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

    @field_validator("rate_warning_threshold")
    @classmethod
    def validate_warning_threshold(cls, v: Optional[float]) -> Optional[float]:
        return validate_threshold_value(v, "rate_warning_threshold")

    @field_validator("rate_critical_threshold")
    @classmethod
    def validate_critical_threshold(cls, v: Optional[float]) -> Optional[float]:
        return validate_threshold_value(v, "rate_critical_threshold")

    @model_validator(mode="after")
    def validate_thresholds(self):
        w = self.rate_warning_threshold
        c = self.rate_critical_threshold
        if w is not None and not (math.isfinite(w) and w > 0):
            raise ValueError("rate_warning_threshold must be greater than 0")
        if c is not None and not (math.isfinite(c) and c > 0):
            raise ValueError("rate_critical_threshold must be greater than 0")
        if w is not None and c is not None and c >= w:
            raise ValueError("rate_critical_threshold must be strictly less than rate_warning_threshold")
        return self


class LineUpdatePayload(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    daily_target: Optional[int] = Field(None, gt=0)
    video_url: Optional[str] = Field(None, max_length=500)
    line_coords: Optional[str] = Field(None, max_length=100)
    line_direction: Optional[str] = None
    is_active: Optional[bool] = None
    rate_warning_threshold: Optional[float] = Field(None, gt=0)
    rate_critical_threshold: Optional[float] = Field(None, gt=0)

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

    @field_validator("rate_warning_threshold")
    @classmethod
    def validate_warning_threshold(cls, v: Optional[float]) -> Optional[float]:
        return validate_threshold_value(v, "rate_warning_threshold")

    @field_validator("rate_critical_threshold")
    @classmethod
    def validate_critical_threshold(cls, v: Optional[float]) -> Optional[float]:
        return validate_threshold_value(v, "rate_critical_threshold")

    @model_validator(mode="after")
    def validate_thresholds(self):
        w = self.rate_warning_threshold
        c = self.rate_critical_threshold
        if w is not None and not (math.isfinite(w) and w > 0):
            raise ValueError("rate_warning_threshold must be greater than 0")
        if c is not None and not (math.isfinite(c) and c > 0):
            raise ValueError("rate_critical_threshold must be greater than 0")
        if w is not None and c is not None and c >= w:
            raise ValueError("rate_critical_threshold must be strictly less than rate_warning_threshold")
        return self


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
    rate_warning_threshold: float | None = None
    rate_critical_threshold: float | None = None
    effective_rate_warning: float = DEFAULT_RATE_WARNING
    effective_rate_critical: float = DEFAULT_RATE_CRITICAL


class LineDetailDTO(BaseModel):
    id: str
    name: str
    daily_target: int
    video_url: Optional[str] = None
    line_coords: Optional[str] = None
    line_direction: str = "down"
    is_active: bool
    rate_warning_threshold: float | None = None
    rate_critical_threshold: float | None = None
    effective_rate_warning: float = DEFAULT_RATE_WARNING
    effective_rate_critical: float = DEFAULT_RATE_CRITICAL


def get_effective_thresholds(line: Line) -> tuple[float, float]:
    eff_warning = (
        line.rate_warning_threshold
        if line.rate_warning_threshold is not None
        else DEFAULT_RATE_WARNING
    )
    eff_critical = (
        line.rate_critical_threshold
        if line.rate_critical_threshold is not None
        else DEFAULT_RATE_CRITICAL
    )
    return eff_warning, eff_critical


def line_to_detail_dto(line: Line) -> LineDetailDTO:
    eff_warning, eff_critical = get_effective_thresholds(line)
    return LineDetailDTO(
        id=line.id,
        name=line.name,
        daily_target=line.daily_target,
        video_url=line.video_url,
        line_coords=line.line_coords,
        line_direction=line.line_direction or "down",
        is_active=line.is_active,
        rate_warning_threshold=line.rate_warning_threshold,
        rate_critical_threshold=line.rate_critical_threshold,
        effective_rate_warning=eff_warning,
        effective_rate_critical=eff_critical,
    )


def line_to_status_dto(
    line: Line,
    status: str,
    last_ping: Optional[str],
    total_today: int,
) -> LineStatusDTO:
    eff_warning, eff_critical = get_effective_thresholds(line)
    return LineStatusDTO(
        id=line.id,
        name=line.name,
        daily_target=line.daily_target,
        video_url=line.video_url,
        line_coords=line.line_coords,
        line_direction=line.line_direction or "down",
        is_active=line.is_active,
        status=status,
        last_ping=last_ping,
        total_today=total_today,
        rate_warning_threshold=line.rate_warning_threshold,
        rate_critical_threshold=line.rate_critical_threshold,
        effective_rate_warning=eff_warning,
        effective_rate_critical=eff_critical,
    )


@router.post("", response_model=LineDetailDTO, status_code=status.HTTP_201_CREATED)
def create_line(
    payload: LineCreatePayload,
    db: Session = Depends(get_db),
    current_user: UserDTO = Depends(require_role(["admin"])),
):
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
        rate_warning_threshold=payload.rate_warning_threshold,
        rate_critical_threshold=payload.rate_critical_threshold,
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
    return line_to_detail_dto(new_line)


@router.get("", response_model=list[LineStatusDTO])
def list_lines(
    db: Session = Depends(get_db),
    current_user: UserDTO = Depends(get_current_user),
):
    lines = db.scalars(select(Line)).all()
    now = datetime.now(timezone.utc)
    today_start_utc, today_end_utc = get_jakarta_today_bounds_utc(now)

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
            .where(CountEvent.ts_utc >= today_start_utc)
            .where(CountEvent.ts_utc <= today_end_utc)
        ) or 0

        result.append(
            line_to_status_dto(
                line=line,
                status=status_str,
                last_ping=last_ping_str,
                total_today=count,
            )
        )
    return result


@router.get("/{line_id}", response_model=LineDetailDTO)
def get_line(
    line_id: str,
    db: Session = Depends(get_db),
    current_user: UserDTO = Depends(get_current_user),
):
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")
    return line_to_detail_dto(line)


@router.put("/{line_id}", response_model=LineDetailDTO)
def update_line(
    line_id: str,
    payload: LineUpdatePayload,
    db: Session = Depends(get_db),
    current_user: UserDTO = Depends(require_role(["admin"])),
):
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")
    fields_set = payload.model_fields_set

    target_warning = (
        payload.rate_warning_threshold
        if "rate_warning_threshold" in fields_set
        else line.rate_warning_threshold
    )
    target_critical = (
        payload.rate_critical_threshold
        if "rate_critical_threshold" in fields_set
        else line.rate_critical_threshold
    )
    if (
        target_warning is not None
        and target_critical is not None
        and target_critical >= target_warning
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="rate_critical_threshold must be strictly less than rate_warning_threshold",
        )

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
    if "rate_warning_threshold" in fields_set:
        line.rate_warning_threshold = payload.rate_warning_threshold
    if "rate_critical_threshold" in fields_set:
        line.rate_critical_threshold = payload.rate_critical_threshold
    db.commit()
    db.refresh(line)
    return line_to_detail_dto(line)


@router.delete("/{line_id}", response_model=LineDetailDTO)
def delete_line(
    line_id: str,
    db: Session = Depends(get_db),
    current_user: UserDTO = Depends(require_role(["admin"])),
):
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")
    line.is_active = False
    db.commit()
    db.refresh(line)
    return line_to_detail_dto(line)
