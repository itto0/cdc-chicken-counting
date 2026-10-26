from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator


class CountEventDTO(BaseModel):
    track_id: int
    ts_utc: datetime
    confidence: float = Field(ge=0.0, le=1.0)


class CountAggregateDTO(BaseModel):
    window_start: datetime
    window_end: datetime
    count: int = Field(ge=0)
    rate_per_min: float = Field(ge=0.0)
    confidence_avg: float = Field(ge=0.0, le=1.0)
    status: Literal["NORMAL", "WARNING", "CRITICAL"] = "NORMAL"


class HealthSampleDTO(BaseModel):
    fps: float = Field(ge=0.0)
    latency_p95_ms: float = Field(ge=0.0)
    cpu_pct: float = Field(ge=0.0, le=100.0)
    mem_pct: float = Field(ge=0.0, le=100.0)
    stream_state: Literal["ONLINE", "OFFLINE", "DEGRADED"] = "ONLINE"
    accuracy_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    model_name: str = "yolo26n"
    model_version: str = "v1.0"


class SyncBatchPayload(BaseModel):
    line_id: str
    events: list[CountEventDTO] = Field(default_factory=list)
    aggregates: list[CountAggregateDTO] = Field(default_factory=list)
    health: HealthSampleDTO | None = None


class LineConfigDTO(BaseModel):
    id: str = ""
    name: str = ""
    daily_target: int = 60000
    is_active: bool = True
    video_url: str | None = None
    line_coords: str | None = None
    line_direction: str = "down"
    rate_warning_threshold: float | None = None
    rate_critical_threshold: float | None = None

    # Backward compatibility with legacy callers and contracts tests
    line_id: str | None = None
    line_name: str = ""
    direction: str = "IN"
    coordinates: list[list[int]] = Field(default_factory=list)
    status: str = "ACTIVE"

    @model_validator(mode="before")
    @classmethod
    def sync_legacy_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "line_id" in data and not data.get("id"):
                data["id"] = data["line_id"]
            elif "id" in data and not data.get("line_id"):
                data["line_id"] = data["id"]
            if "line_name" in data and not data.get("name"):
                data["name"] = data["line_name"]
            elif "name" in data and not data.get("line_name"):
                data["line_name"] = data["name"]
        return data


class AlarmDTO(BaseModel):
    id: str
    line_id: str
    alarm_type: str
    severity: Literal["INFO", "WARNING", "CRITICAL"] = "WARNING"
    message: str
    ts_utc: datetime
    acknowledged: bool = False


__all__ = [
    "CountEventDTO",
    "CountAggregateDTO",
    "HealthSampleDTO",
    "SyncBatchPayload",
    "LineConfigDTO",
    "AlarmDTO",
]
