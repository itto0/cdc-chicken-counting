from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


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
    model_name: str = "yolo26n"
    model_version: str = "v1.0"


class SyncBatchPayload(BaseModel):
    line_id: str
    events: list[CountEventDTO] = Field(default_factory=list)
    aggregates: list[CountAggregateDTO] = Field(default_factory=list)
    health: HealthSampleDTO | None = None


class LineConfigDTO(BaseModel):
    line_id: str
    line_name: str = ""
    direction: str = "IN"
    coordinates: list[list[int]] = Field(default_factory=list)
    status: str = "ACTIVE"


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
