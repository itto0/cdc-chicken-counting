# Centralized Production Line Management with PostgreSQL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable users to create and manage production lines from the frontend dashboard, store line metadata and counting data in PostgreSQL on the cloud/VM, and allow edge counter workers to automatically pull their camera and line coordinate configuration on startup with offline fallback.

**Architecture:** The Central API (FastAPI) persists lines in PostgreSQL (with SQLite compatibility for dev/tests). Edge counter instances query the central API on boot for their `LINE_ID` configuration (`video_url`, `line_coords`, `line_direction`) and fall back to local `.env`/CLI parameters when offline. The Vite/React frontend dashboard in `PengaturanPage` provides a line management table and a "+ Tambah Lini Baru" modal with coordinate presets and validation.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0, PostgreSQL (psycopg2-binary), Docker Compose, React 18, TypeScript, TailwindCSS, Vite.

## Global Constraints

- **Python Version:** >= 3.11
- **API Framework:** FastAPI with SQLAlchemy ORM (support both PostgreSQL and SQLite dialect)
- **Edge Storage:** Unchanged SQLite WAL outbox (`counter_outbox.db`) to ensure factory offline resilience
- **Database Engine:** PostgreSQL 15 for cloud/docker deployment; SQLite fallback for local test suite
- **Line ID Constraints:** 2-50 characters, alphanumeric with hyphens/underscores (`^[a-zA-Z0-9_-]+$`)
- **Virtual Line Coordinates:** Format `"x1,y1,x2,y2"` (4 float or integer values)
- **Line Crossing Directions:** `"down"`, `"up"`, `"left"`, `"right"`, `"in"`, `"out"`
- **Frontend Build:** Strict TypeScript typing (`tsc && vite build`) without any compile errors

---

### Task 1: Database Model & Docker PostgreSQL Configuration

**Files:**
- Modify: `services/api/src/db/models.py:10-21`
- Modify: `services/api/src/db/session.py:10-20`
- Modify: `services/api/Dockerfile:10-23`
- Modify: `docker-compose.yml:1-42`
- Test: `services/api/tests/test_db_models.py`

**Interfaces:**
- Consumes: SQLAlchemy DeclarativeBase
- Produces: `Line` model with `video_url`, `line_coords`, `line_direction`, `created_at` attributes; PostgreSQL container configuration in `docker-compose.yml`

- [ ] **Step 1: Write the failing test for extended Line model**

Create `services/api/tests/test_db_models.py`:
```python
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from services.api.src.db.models import Base, Line


def test_line_model_extended_fields():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        line = Line(
            id="line-test",
            name="Test Conveyor",
            daily_target=50000,
            video_url="rtsp://192.168.1.10:554/live",
            line_coords="0,240,640,240",
            line_direction="right",
            is_active=True,
        )
        session.add(line)
        session.commit()

        retrieved = session.get(Line, "line-test")
        assert retrieved is not None
        assert retrieved.name == "Test Conveyor"
        assert retrieved.video_url == "rtsp://192.168.1.10:554/live"
        assert retrieved.line_coords == "0,240,640,240"
        assert retrieved.line_direction == "right"
        assert retrieved.is_active is True
        assert isinstance(retrieved.created_at, datetime)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest services/api/tests/test_db_models.py -v`
Expected: FAIL with `TypeError: 'video_url' is an unexpected keyword argument`

- [ ] **Step 3: Update `Line` model in `services/api/src/db/models.py`**

In `services/api/src/db/models.py`, update `Line`:
```python
class Line(Base):
    __tablename__ = "lines"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    daily_target: Mapped[int] = mapped_column(Integer, default=62000)
    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    line_coords: Mapped[str | None] = mapped_column(String(100), nullable=True)
    line_direction: Mapped[str] = mapped_column(String(20), default="down")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"<Line(id='{self.id}', name='{self.name}', daily_target={self.daily_target}, is_active={self.is_active})>"
```

- [ ] **Step 4: Update `services/api/src/db/session.py` for PostgreSQL connection pooling**

In `services/api/src/db/session.py`:
```python
import os
from collections.abc import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from shared.env import init_env

init_env()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///api_central.db")

connect_args = {}
engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
else:
    # PostgreSQL pool settings
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_engine(DATABASE_URL, connect_args=connect_args, **engine_kwargs)


if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()
        except Exception:
            pass


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 5: Add `psycopg2-binary` to Dockerfile & PostgreSQL to `docker-compose.yml`**

In `services/api/Dockerfile`, add `"psycopg2-binary>=2.9.9"`:
```dockerfile
# Install python dependencies
RUN pip install --no-cache-dir \
    "fastapi>=0.110.0" \
    "uvicorn[standard]>=0.28.0" \
    "sqlalchemy>=2.0.0" \
    "psycopg2-binary>=2.9.9" \
    "pydantic>=2.5.0" \
    "httpx>=0.27.0" \
    "openpyxl>=3.1.0" \
    "PyJWT>=2.8.0" \
    "python-dotenv>=1.0.0" \
    "reportlab>=4.0.0" \
    "opencv-python-headless>=4.8.0" \
    "numpy>=1.24.0"
```

In `docker-compose.yml`, add postgres service:
```yaml
version: "3.8"

services:
  postgres:
    image: postgres:15-alpine
    container_name: cdc_postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgrespassword
      POSTGRES_DB: chicken_counting
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d chicken_counting"]
      interval: 5s
      timeout: 5s
      retries: 5

  api:
    build:
      context: .
      dockerfile: services/api/Dockerfile
    env_file:
      - .env
    ports:
      - "${PORT:-8070}:${PORT:-8070}"
    environment:
      - DATABASE_URL=postgresql://postgres:postgrespassword@postgres:5432/chicken_counting
      - VIDEO_PATH=/samples/Rekaman_2.MOV
    volumes:
      - ./samples:/samples:ro
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped

  counter:
    build:
      context: .
      dockerfile: services/counter/Dockerfile
    env_file:
      - .env
    environment:
      - API_SYNC_URL=http://api:${PORT:-8070}/api/v1/sync/batch
      - LINE_ID=line-1
      - DB_PATH=/data/counter_outbox.db
      - VIDEO_PATH=/samples/Rekaman_2.MOV
      - LOOP_VIDEO=1
      - LINE_DIRECTION=right
      - TARGET_FPS=30.0
    volumes:
      - counter_data:/data
      - ./samples:/samples:ro
    restart: unless-stopped
    depends_on:
      - api

volumes:
  postgres_data:
  counter_data:
```

- [ ] **Step 6: Run test to verify it passes**

Run: `py -m pytest services/api/tests/test_db_models.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add services/api/src/db/models.py services/api/src/db/session.py services/api/Dockerfile docker-compose.yml services/api/tests/test_db_models.py
git commit -m "feat(db): extend Line model and configure PostgreSQL in docker-compose"
```

---

### Task 2: Central API Endpoints (Create, Update, Delete Line)

**Files:**
- Modify: `services/api/src/api/lines.py:10-116`
- Modify: `services/api/src/main.py:50-70`
- Modify: `services/api/tests/test_lines_api.py:1-120`

**Interfaces:**
- Consumes: `Line` model, `Session` from `services.api.src.db.session`
- Produces: `POST /api/v1/lines`, `PUT /api/v1/lines/{line_id}`, `DELETE /api/v1/lines/{line_id}`, extended `LineDetailDTO` & `LineStatusDTO`

- [ ] **Step 1: Write failing tests for line creation, coordinates validation, and soft-delete**

In `services/api/tests/test_lines_api.py`, add:
```python
def test_create_line_success():
    client = TestClient(app)
    payload = {
        "id": "line-new-1",
        "name": "New Conveyor 1",
        "daily_target": 75000,
        "video_url": "rtsp://camera1/stream",
        "line_coords": "0,240,640,240",
        "line_direction": "down",
        "is_active": True,
    }
    resp = client.post("/api/v1/lines", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] == "line-new-1"
    assert data["name"] == "New Conveyor 1"
    assert data["daily_target"] == 75000
    assert data["video_url"] == "rtsp://camera1/stream"
    assert data["line_coords"] == "0,240,640,240"
    assert data["line_direction"] == "down"
    assert data["is_active"] is True


def test_create_line_duplicate_id():
    client = TestClient(app)
    payload = {
        "id": "line-dup",
        "name": "Conveyor Duplicate",
        "daily_target": 50000,
    }
    resp1 = client.post("/api/v1/lines", json=payload)
    assert resp1.status_code == 201

    resp2 = client.post("/api/v1/lines", json=payload)
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"].lower()


def test_create_line_invalid_coords_and_direction():
    client = TestClient(app)
    # Bad coordinates (only 2 numbers)
    resp = client.post("/api/v1/lines", json={
        "id": "line-bad-coords",
        "name": "Bad Coords",
        "line_coords": "100,200",
    })
    assert resp.status_code == 422

    # Bad direction
    resp2 = client.post("/api/v1/lines", json={
        "id": "line-bad-dir",
        "name": "Bad Dir",
        "line_direction": "diagonal_up",
    })
    assert resp2.status_code == 422


def test_soft_delete_line():
    client = TestClient(app)
    line_id = "line-to-delete"
    client.post("/api/v1/lines", json={"id": line_id, "name": "Line To Delete"})

    resp = client.delete(f"/api/v1/lines/{line_id}")
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    # Check detail shows is_active is False
    detail = client.get(f"/api/v1/lines/{line_id}").json()
    assert detail["is_active"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest services/api/tests/test_lines_api.py -k "test_create_line" -v`
Expected: FAIL with 405 Method Not Allowed or 404 Not Found

- [ ] **Step 3: Implement `LineCreatePayload` and endpoints in `services/api/src/api/lines.py`**

In `services/api/src/api/lines.py`:
```python
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func
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
            float(p)
        except ValueError:
            raise ValueError("All coordinates in line_coords must be valid numbers")
    return coords.strip()


class LineCreatePayload(BaseModel):
    id: str = Field(..., min_length=2, max_length=50, description="Alphanumeric slug, e.g. 'line-2'")
    name: str = Field(..., min_length=1, max_length=100)
    daily_target: int = Field(60000, gt=0)
    video_url: Optional[str] = Field(None, max_length=500)
    line_coords: Optional[str] = Field(None, max_length=100)
    line_direction: str = Field("down")
    is_active: bool = True

    @field_validator("id")
    @classmethod
    def validate_id_slug(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("id must contain only letters, numbers, hyphens, and underscores")
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
    name: Optional[str] = None
    daily_target: Optional[int] = Field(None, gt=0)
    video_url: Optional[str] = None
    line_coords: Optional[str] = None
    line_direction: Optional[str] = None
    is_active: Optional[bool] = None

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
    db.add(new_line)
    db.commit()
    db.refresh(new_line)
    return LineDetailDTO(
        id=new_line.id,
        name=new_line.name,
        daily_target=new_line.daily_target,
        video_url=new_line.video_url,
        line_coords=new_line.line_coords,
        line_direction=new_line.line_direction,
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
    if payload.name is not None:
        line.name = payload.name
    if payload.daily_target is not None:
        line.daily_target = payload.daily_target
    if payload.video_url is not None:
        line.video_url = payload.video_url
    if payload.line_coords is not None:
        line.line_coords = payload.line_coords
    if payload.line_direction is not None:
        line.line_direction = payload.line_direction
    if payload.is_active is not None:
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
```

- [ ] **Step 4: Update `services/api/src/main.py` seed logic**

In `services/api/src/main.py`, update initial seed lines so default `line-1` has `line_direction="right"` and `line_coords="0,240,640,240"`:
```python
if not db.get(Line, "line-1"):
    db.add(
        Line(
            id="line-1",
            name="Lini Konveyor 1",
            daily_target=62000,
            line_direction="right",
            line_coords="0,240,640,240",
            is_active=True,
        )
    )
    db.commit()
```

- [ ] **Step 5: Run tests to verify all line API tests pass**

Run: `py -m pytest services/api/tests/test_lines_api.py -v`
Expected: PASS (all 12+ tests pass)

- [ ] **Step 6: Commit**

```bash
git add services/api/src/api/lines.py services/api/src/main.py services/api/tests/test_lines_api.py
git commit -m "feat(api): implement line creation, update, and soft deletion endpoints"
```

---

### Task 3: Edge Counter Startup Remote Configuration Pull

**Files:**
- Modify: `services/counter/main.py:750-880`
- Create: `services/counter/tests/test_remote_config.py`

**Interfaces:**
- Consumes: Central API `GET /api/v1/lines/{line_id}`
- Produces: `fetch_remote_line_config(api_sync_url: str, line_id: str)` function and initialization wiring in `services/counter/main.py`

- [ ] **Step 1: Write failing unit test for `fetch_remote_line_config`**

Create `services/counter/tests/test_remote_config.py`:
```python
import httpx
import pytest
from unittest.mock import patch, MagicMock
from services.counter.main import fetch_remote_line_config


def test_fetch_remote_config_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "line-2",
        "name": "Line 2",
        "video_url": "rtsp://camera2/stream",
        "line_coords": "100,200,500,200",
        "line_direction": "up",
    }

    with patch("httpx.get", return_value=mock_resp) as mock_get:
        config = fetch_remote_line_config(
            api_sync_url="http://central-api:8070/api/v1/sync/batch",
            line_id="line-2",
            timeout=2.0,
        )
        assert config is not None
        assert config["video_url"] == "rtsp://camera2/stream"
        assert config["line_coords"] == "100,200,500,200"
        assert config["line_direction"] == "up"
        mock_get.assert_called_once_with(
            "http://central-api:8070/api/v1/lines/line-2",
            timeout=2.0,
        )


def test_fetch_remote_config_offline_or_error_returns_none():
    with patch("httpx.get", side_effect=httpx.ConnectError("Failed to connect")):
        config = fetch_remote_line_config(
            api_sync_url="http://unreachable-api:8070/api/v1/sync/batch",
            line_id="line-2",
            timeout=1.0,
        )
        assert config is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest services/counter/tests/test_remote_config.py -v`
Expected: FAIL with `ImportError: cannot import name 'fetch_remote_line_config' from 'services.counter.main'`

- [ ] **Step 3: Implement `fetch_remote_line_config` and startup pull in `services/counter/main.py`**

In `services/counter/main.py`:
```python
def fetch_remote_line_config(
    api_sync_url: str,
    line_id: str,
    timeout: float = 3.0,
) -> dict | None:
    """Fetches line configuration from central API on startup.
    Returns None if unreachable or on error (enabling offline fallback).
    """
    try:
        import httpx
        # Deduce base URL from api_sync_url (e.g., http://host:port/api/v1/sync/batch -> http://host:port/api/v1/lines/{line_id})
        if "/api/v1/" in api_sync_url:
            base_api = api_sync_url.split("/api/v1/")[0] + "/api/v1"
        else:
            base_api = api_sync_url.rstrip("/")
        
        target_url = f"{base_api}/lines/{line_id}"
        resp = httpx.get(target_url, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
        logger.warning("Remote line config returned HTTP %s for line %s", resp.status_code, line_id)
        return None
    except Exception as exc:
        logger.info("Could not fetch remote line config (%s). Using local parameters.", exc)
        return None
```

In `services/counter/main.py` `run_counter` function around line 850:
```python
    # Remote config startup pull
    if enable_sync and args.api_sync_url:
        remote_config = fetch_remote_line_config(args.api_sync_url, args.line_id)
        if remote_config:
            if not args.video and remote_config.get("video_url"):
                args.video = remote_config["video_url"]
                logger.info("[RemoteConfig] Applied video source: %s", args.video)
            if not args.line and remote_config.get("line_coords"):
                args.line = remote_config["line_coords"]
                logger.info("[RemoteConfig] Applied line coordinates: %s", args.line)
            if (not os.getenv("LINE_DIRECTION") or args.direction == "down") and remote_config.get("line_direction"):
                args.direction = remote_config["line_direction"]
                logger.info("[RemoteConfig] Applied line direction: %s", args.direction)
```

- [ ] **Step 4: Run unit tests to verify they pass**

Run: `py -m pytest services/counter/tests/test_remote_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/counter/main.py services/counter/tests/test_remote_config.py
git commit -m "feat(counter): add startup configuration pull from central API with offline fallback"
```

---

### Task 4: Frontend API Client & State Management

**Files:**
- Modify: `frontend/src/types/index.ts:1-25`
- Modify: `frontend/src/services/apiClient.ts:30-80`
- Modify: `frontend/src/context/AppContext.tsx:20-100`

**Interfaces:**
- Consumes: `POST /api/v1/lines`, `PUT /api/v1/lines/{id}`, `DELETE /api/v1/lines/{id}`
- Produces: `createLine`, `updateLine`, `deleteLine` functions in `apiClient` and `AppContext`

- [ ] **Step 1: Update `Line` type in `frontend/src/types/index.ts`**

In `frontend/src/types/index.ts`:
```typescript
export interface Line {
  id: string;
  name: string;
  daily_target: number;
  video_url?: string | null;
  line_coords?: string | null;
  line_direction?: string;
  is_active?: boolean;
  status?: string;
  last_ping?: string | null;
  total_today?: number;
}

export interface CreateLinePayload {
  id: string;
  name: string;
  daily_target: number;
  video_url?: string;
  line_coords?: string;
  line_direction?: string;
  is_active?: boolean;
}

export interface UpdateLinePayload {
  name?: string;
  daily_target?: number;
  video_url?: string;
  line_coords?: string;
  line_direction?: string;
  is_active?: boolean;
}
```

- [ ] **Step 2: Add API client functions in `frontend/src/services/apiClient.ts`**

In `frontend/src/services/apiClient.ts`:
```typescript
  async createLine(payload: CreateLinePayload): Promise<Line> {
    const { data } = await api.post<Line>("/api/v1/lines", payload);
    return data;
  },

  async updateLine(lineId: string, payload: UpdateLinePayload): Promise<Line> {
    const { data } = await api.put<Line>(`/api/v1/lines/${encodeURIComponent(lineId)}`, payload);
    return data;
  },

  async deleteLine(lineId: string): Promise<Line> {
    const { data } = await api.delete<Line>(`/api/v1/lines/${encodeURIComponent(lineId)}`);
    return data;
  },
```

- [ ] **Step 3: Expose line actions in `frontend/src/context/AppContext.tsx`**

In `frontend/src/context/AppContext.tsx`:
Add `createLine`, `updateLine`, `deleteLine` to context interface and implementation, automatically re-fetching lines after creation:
```typescript
  const createLine = useCallback(async (payload: CreateLinePayload) => {
    const newLine = await apiClient.createLine(payload);
    await fetchLines();
    setCurrentLineId(newLine.id);
    return newLine;
  }, [fetchLines]);

  const updateLine = useCallback(async (lineId: string, payload: UpdateLinePayload) => {
    const updated = await apiClient.updateLine(lineId, payload);
    await fetchLines();
    return updated;
  }, [fetchLines]);

  const deleteLine = useCallback(async (lineId: string) => {
    const deleted = await apiClient.deleteLine(lineId);
    await fetchLines();
    return deleted;
  }, [fetchLines]);
```

- [ ] **Step 4: Verify TypeScript compilation**

Run: `npm --prefix frontend run build`
Expected: Build succeeds with 0 TypeScript errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/services/apiClient.ts frontend/src/context/AppContext.tsx
git commit -m "feat(frontend): add line creation and management methods in apiClient and AppContext"
```

---

### Task 5: Frontend "Tambah Lini" Modal & Lines Management UI

**Files:**
- Create: `frontend/src/features/settings/components/AddLineModal.tsx`
- Modify: `frontend/src/features/settings/pages/PengaturanPage.tsx:1-120`

**Interfaces:**
- Consumes: `useAppContext().createLine`, `useAppContext().lines`
- Produces: Line creation modal dialog with presets and comprehensive Lines Management table

- [ ] **Step 1: Create `AddLineModal.tsx`**

Create `frontend/src/features/settings/components/AddLineModal.tsx`:
```tsx
import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { CreateLinePayload } from "@/types";

interface AddLineModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (payload: CreateLinePayload) => Promise<void>;
}

export function AddLineModal({ isOpen, onClose, onSubmit }: AddLineModalProps) {
  const [id, setId] = useState("");
  const [name, setName] = useState("");
  const [dailyTarget, setDailyTarget] = useState(60000);
  const [videoUrl, setVideoUrl] = useState("");
  const [lineCoords, setLineCoords] = useState("0,240,640,240");
  const [lineDirection, setLineDirection] = useState("down");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    const cleanId = id.trim().toLowerCase().replace(/\s+/g, "-");
    if (!cleanId) {
      setErrorMsg("ID Lini wajib diisi");
      return;
    }
    if (!name.trim()) {
      setErrorMsg("Nama Lini wajib diisi");
      return;
    }

    try {
      setIsSubmitting(true);
      await onSubmit({
        id: cleanId,
        name: name.trim(),
        daily_target: Number(dailyTarget) || 60000,
        video_url: videoUrl.trim() || undefined,
        line_coords: lineCoords.trim() || undefined,
        line_direction: lineDirection,
        is_active: true,
      });
      onClose();
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || "Gagal membuat lini baru";
      setErrorMsg(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg border border-slate-200 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center">
          <div>
            <h3 className="font-semibold text-slate-800 text-base">Tambah Lini Produksi Baru</h3>
            <p className="text-xs text-slate-500">Konfigurasi lini baru, target kuota, dan sumber video kamera</p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 text-lg leading-none p-1 rounded hover:bg-slate-100"
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="p-6 space-y-4 max-h-[75vh] overflow-y-auto text-xs">
            {errorMsg && (
              <div className="p-3 bg-rose-50 border border-rose-200 text-rose-700 rounded-lg text-xs">
                {errorMsg}
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="font-medium text-slate-700 block mb-1">
                  ID Lini <span className="text-rose-500">*</span>
                </label>
                <Input
                  value={id}
                  onChange={(e) => setId(e.target.value)}
                  placeholder="contoh: line-2"
                  required
                />
                <span className="text-[10px] text-slate-400 mt-0.5 block">Slug unik (huruf, angka, strip)</span>
              </div>
              <div>
                <label className="font-medium text-slate-700 block mb-1">
                  Nama Lini <span className="text-rose-500">*</span>
                </label>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Lini Konveyor 2"
                  required
                />
              </div>
            </div>

            <div>
              <label className="font-medium text-slate-700 block mb-1">
                Target Harian (ekor ayam)
              </label>
              <Input
                type="number"
                value={dailyTarget}
                onChange={(e) => setDailyTarget(Number(e.target.value))}
                placeholder="60000"
                min={1}
              />
            </div>

            <div>
              <label className="font-medium text-slate-700 block mb-1">
                URL Stream Kamera / RTSP
              </label>
              <Input
                value={videoUrl}
                onChange={(e) => setVideoUrl(e.target.value)}
                placeholder="rtsp://192.168.1.100:554/stream1 atau /samples/video.mp4"
              />
              <span className="text-[10px] text-slate-400 mt-0.5 block">Opsional. Digunakan untuk live streaming kamera di cloud.</span>
            </div>

            <div className="space-y-1.5">
              <label className="font-medium text-slate-700 block">
                Koordinat Garis Virtual (x1, y1, x2, y2)
              </label>
              <Input
                value={lineCoords}
                onChange={(e) => setLineCoords(e.target.value)}
                placeholder="0,240,640,240"
              />
              <div className="flex gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setLineCoords("0,240,640,240")}
                  className="px-2 py-0.5 text-[10px] bg-slate-100 text-slate-600 rounded hover:bg-slate-200 border border-slate-200"
                >
                  Preset Horizontal Tengah
                </button>
                <button
                  type="button"
                  onClick={() => setLineCoords("320,0,320,480")}
                  className="px-2 py-0.5 text-[10px] bg-slate-100 text-slate-600 rounded hover:bg-slate-200 border border-slate-200"
                >
                  Preset Vertikal Tengah
                </button>
              </div>
            </div>

            <div>
              <label className="font-medium text-slate-700 block mb-1">
                Arah Hitung Perlintasan
              </label>
              <select
                value={lineDirection}
                onChange={(e) => setLineDirection(e.target.value)}
                className="w-full h-9 rounded-md border border-slate-200 bg-white px-3 py-1 text-xs text-slate-800 shadow-sm focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="down">Ke Bawah (Down)</option>
                <option value="up">Ke Atas (Up)</option>
                <option value="right">Ke Kanan (Right)</option>
                <option value="left">Ke Kiri (Left)</option>
                <option value="in">Masuk (In)</option>
                <option value="out">Keluar (Out)</option>
              </select>
            </div>
          </div>

          <div className="px-6 py-3.5 bg-slate-50 border-t border-slate-100 flex justify-end gap-2">
            <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={isSubmitting}>
              Batal
            </Button>
            <Button type="submit" size="sm" disabled={isSubmitting}>
              {isSubmitting ? "Menyimpan..." : "Simpan Lini"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Update `PengaturanPage.tsx` to include "Manajemen Lini Produksi" table and Modal**

In `frontend/src/features/settings/pages/PengaturanPage.tsx`:
- Render a complete management table of all lines (`lines` from `useAppContext()`).
- Include columns: ID Lini, Nama Lini, Target Harian, Status, Arah & Garis, Aksi.
- Include "+ Tambah Lini Baru" button opening `AddLineModal`.
- Support toggling `is_active` via `updateLine`.

- [ ] **Step 3: Test frontend build with `npm run build`**

Run: `npm --prefix frontend run build`
Expected: PASS with 0 build or lint errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/settings/components/AddLineModal.tsx frontend/src/features/settings/pages/PengaturanPage.tsx
git commit -m "feat(frontend): add line management table and AddLineModal in PengaturanPage"
```

---

### Task 6: End-to-End System Integration Verification

**Files:**
- Test all: `services/api/tests/test_lines_api.py`, `services/api/tests/test_db_models.py`, `services/counter/tests/test_remote_config.py`, frontend build

- [ ] **Step 1: Run all Python unit and API tests**

Run: `py -m pytest services/api/tests/test_lines_api.py services/api/tests/test_db_models.py services/counter/tests/test_remote_config.py -v`
Expected: PASS (all tests green)

- [ ] **Step 2: Run frontend production build**

Run: `npm --prefix frontend run build`
Expected: Build succeeds cleanly

- [ ] **Step 3: Commit final integration verification**

```bash
git commit --allow-empty -m "chore: verify centralized line creation with postgresql across api, edge, and frontend"
```
