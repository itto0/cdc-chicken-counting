from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Line(Base):
    __tablename__ = "lines"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    daily_target: Mapped[int] = mapped_column(Integer, default=62000)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:
        return f"<Line(id='{self.id}', name='{self.name}', daily_target={self.daily_target}, is_active={self.is_active})>"


class CountEvent(Base):
    __tablename__ = "count_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    line_id: Mapped[str] = mapped_column(String(50), index=True)
    track_id: Mapped[int] = mapped_column(Integer)
    ts_utc: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    confidence: Mapped[float] = mapped_column(Float)

    __table_args__ = (
        UniqueConstraint("line_id", "track_id", "ts_utc", name="uq_line_track_ts"),
    )

    def __repr__(self) -> str:
        return f"<CountEvent(id={self.id}, line_id='{self.line_id}', track_id={self.track_id}, ts_utc='{self.ts_utc}')>"


class CountAggregate(Base):
    __tablename__ = "count_aggregates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    line_id: Mapped[str] = mapped_column(String(50), index=True)
    window_start: Mapped[datetime] = mapped_column(DateTime)
    window_end: Mapped[datetime] = mapped_column(DateTime)
    count: Mapped[int] = mapped_column(Integer)
    rate_per_min: Mapped[float] = mapped_column(Float)
    confidence_avg: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20))

    def __repr__(self) -> str:
        return f"<CountAggregate(id={self.id}, line_id='{self.line_id}', count={self.count}, status='{self.status}')>"


class HealthSample(Base):
    __tablename__ = "health_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    line_id: Mapped[str] = mapped_column(String(50), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    fps: Mapped[float] = mapped_column(Float)
    latency_p95_ms: Mapped[float] = mapped_column(Float)
    cpu_pct: Mapped[float] = mapped_column(Float)
    mem_pct: Mapped[float] = mapped_column(Float)
    stream_state: Mapped[str] = mapped_column(String(20))
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)

    def __repr__(self) -> str:
        return f"<HealthSample(id={self.id}, line_id='{self.line_id}', state='{self.stream_state}', fps={self.fps})>"


class Alarm(Base):
    __tablename__ = "alarms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    line_id: Mapped[str] = mapped_column(String(50), index=True)
    alarm_type: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    ack_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

    def __repr__(self) -> str:
        return f"<Alarm(id={self.id}, line_id='{self.line_id}', type='{self.alarm_type}', status='{self.status}')>"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="OPERATOR")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}', active={self.is_active})>"
