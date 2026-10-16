# Dashboard & Data API Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build out the missing Data API REST endpoints (Lines CRUD, KPI Summary, Historical Volume & Logs, Alarms Lifecycle, JWT Auth, PDF Exporter, MJPEG Live Stream) and implement all five production dashboard screens (Overview, Live Stream, Alarms, Reports & Analytics, Settings) wired to real-time SSE telemetry and backend APIs.

**Architecture:** 
- The backend extends the FastAPI SQLite WAL application with domain-specific routers for lines, summary metrics, historical counts, alarm lifecycle, and authentication.
- Reports generation provides both Excel (`.xlsx`) via openpyxl and PDF (`.pdf`) via ReportLab.
- The frontend uses React 18 + TypeScript + Vite + Tailwind CSS with an `AppContext` managing active line selection and role switching, an SSE subscription hook (`useLiveStream`) with exponential backoff reconnects, and typed API services communicating with the backend.

**Tech Stack:**
- Backend: Python 3.14, FastAPI, SQLAlchemy 2.0 (SQLite WAL), PyJWT, ReportLab, openpyxl, pytest, httpx.
- Frontend: React 18, Vite, TypeScript, Tailwind CSS, Lucide React, Recharts.

## Global Constraints

- Backend must maintain 100% compatibility with existing contracts in `shared/contracts.py` and models in `services/api/src/db/models.py`.
- No regression: All 130 existing tests must continue to pass throughout implementation.
- API endpoints must return standard JSON schemas and handle missing database records with appropriate HTTP 404 / 400 responses.
- Frontend TypeScript build (`npm run build`) must compile cleanly with zero errors.
- TDD required: Backend tasks must create failing pytest tests first, then minimal implementation, and commit per task.

---

### Task 1: Lines REST API (`GET /lines`, `GET /lines/{id}`, `PUT /lines/{id}`)

**Files:**
- Create: `services/api/src/api/lines.py`
- Modify: `services/api/src/main.py:20-30`
- Test: `services/api/tests/test_lines_api.py`

**Interfaces:**
- Consumes: `services.api.src.db.models.Line`, `services.api.src.db.models.HealthSample`, `services.api.src.db.models.CountEvent`
- Produces: `router = APIRouter(prefix="/api/v1/lines", tags=["lines"])` with:
  - `GET /api/v1/lines` -> `list[LineStatusDTO]`
  - `GET /api/v1/lines/{id}` -> `LineDetailDTO`
  - `PUT /api/v1/lines/{id}` -> `LineDetailDTO`

- [ ] **Step 1: Write the failing test**

Create `services/api/tests/test_lines_api.py`:
```python
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from services.api.src.main import app
from services.api.src.db.session import get_db
from services.api.src.db.models import Base, Line, HealthSample, CountEvent
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

@pytest.fixture
def lines_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Seed initial test line
    db = TestingSession()
    db.add(Line(id="line-1", name="Main Processing Line", daily_target=62000, is_active=True))
    db.add(HealthSample(line_id="line-1", timestamp=datetime.now(timezone.utc), fps=30.0, latency_p95_ms=15.0, cpu_pct=25.0, mem_pct=40.0, stream_state="ONLINE"))
    db.add(CountEvent(line_id="line-1", track_id=1, ts_utc=datetime.now(timezone.utc), confidence=0.98))
    db.commit()
    db.close()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

def test_list_lines(lines_client):
    response = lines_client.get("/api/v1/lines")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    line1 = next(item for item in data if item["id"] == "line-1")
    assert line1["name"] == "Main Processing Line"
    assert line1["status"] in ["online", "offline", "degraded"]
    assert line1["daily_target"] == 62000
    assert line1["total_today"] == 1

def test_get_line_detail(lines_client):
    response = lines_client.get("/api/v1/lines/line-1")
    assert response.status_code == 200
    assert response.json()["id"] == "line-1"

def test_update_line(lines_client):
    update_payload = {"name": "Updated Line 1", "daily_target": 70000, "is_active": True}
    response = lines_client.put("/api/v1/lines/line-1", json=update_payload)
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Line 1"
    assert response.json()["daily_target"] == 70000

def test_get_nonexistent_line(lines_client):
    response = lines_client.get("/api/v1/lines/non-existent")
    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run:
`python -m pytest services/api/tests/test_lines_api.py -v`
Expected: FAIL (404 Not Found as `/api/v1/lines` is not registered yet).

- [ ] **Step 3: Write minimal implementation**

Create `services/api/src/api/lines.py`:
```python
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
    last_ping: Optional[str]
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
```

In `services/api/src/main.py`:
Add `from services.api.src.api.lines import router as lines_router` and `app.include_router(lines_router)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest services/api/tests/test_lines_api.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add services/api/src/api/lines.py services/api/src/main.py services/api/tests/test_lines_api.py
git commit -m "feat(api): add lines listing, detail, and update REST endpoints"
```

---

### Task 2: Line Summary KPI API (`GET /lines/{id}/summary`)

**Files:**
- Create: `services/api/src/api/summary.py`
- Modify: `services/api/src/main.py`
- Test: `services/api/tests/test_summary_api.py`

**Interfaces:**
- Consumes: `services.api.src.db.models.Line`, `services.api.src.db.models.CountEvent`, `services.api.src.db.models.HealthSample`, `services.api.src.db.models.Alarm`
- Produces: `GET /api/v1/lines/{id}/summary?period=today|shift|week` -> `LineSummaryResponse`

- [ ] **Step 1: Write the failing test**

Create `services/api/tests/test_summary_api.py`:
```python
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from services.api.src.main import app
from services.api.src.db.session import get_db
from services.api.src.db.models import Base, Line, HealthSample, CountEvent, Alarm
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

@pytest.fixture
def summary_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestingSession()
    db.add(Line(id="line-1", name="Line 1", daily_target=1000, is_active=True))
    now = datetime.now(timezone.utc)
    for i in range(50):
        db.add(CountEvent(line_id="line-1", track_id=i + 1, ts_utc=now - timedelta(minutes=2), confidence=0.95))
    db.add(HealthSample(line_id="line-1", timestamp=now, fps=28.5, latency_p95_ms=18.0, cpu_pct=30.0, mem_pct=45.0, stream_state="ONLINE"))
    db.add(Alarm(line_id="line-1", alarm_type="SPEED_WARNING", severity="WARNING", message="Slow speed", status="OPEN", opened_at=now))
    db.commit()
    db.close()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

def test_get_line_summary_today(summary_client):
    response = summary_client.get("/api/v1/lines/line-1/summary?period=today")
    assert response.status_code == 200
    data = response.json()
    assert data["line_id"] == "line-1"
    assert data["total_count"] == 50
    assert data["target_count"] == 1000
    assert data["target_attainment_pct"] == 5.0
    assert data["active_alarms_count"] == 1
    assert data["camera_status"] == "online"
    assert data["fps"] == 28.5
    assert data["latency_p95_ms"] == 18.0
    assert data["current_speed_cpm"] > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest services/api/tests/test_summary_api.py -v`
Expected: FAIL (404 Not Found).

- [ ] **Step 3: Write minimal implementation**

Create `services/api/src/api/summary.py`:
```python
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
    period: str = Query(default="today"),
    db: Session = Depends(get_db),
):
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

    now = datetime.now(timezone.utc)
    if period == "today":
        start_time = datetime(now.year, now.month, now.day)
    elif period == "shift":
        start_time = now - timedelta(hours=8)
    elif period == "week":
        start_time = now - timedelta(days=7)
    else:
        start_time = datetime(now.year, now.month, now.day)

    # Total count in period
    total_count = db.scalar(
        select(func.count(CountEvent.id))
        .where(CountEvent.line_id == line_id)
        .where(CountEvent.ts_utc >= start_time)
    ) or 0

    target = line.daily_target or 62000
    attainment_pct = round((total_count / target) * 100.0, 1) if target > 0 else 0.0

    # Recent speed (count in last 5 minutes * 12)
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
        if now - ts <= timedelta(seconds=60):
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
```

In `services/api/src/main.py`:
Include `summary_router`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest services/api/tests/test_summary_api.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add services/api/src/api/summary.py services/api/src/main.py services/api/tests/test_summary_api.py
git commit -m "feat(api): add line KPI summary REST endpoint"
```

---

### Task 3: Historical Counts & Logs API (`GET /lines/{id}/counts`)

**Files:**
- Create: `services/api/src/api/counts.py`
- Modify: `services/api/src/main.py`
- Test: `services/api/tests/test_counts_api.py`

**Interfaces:**
- Consumes: `services.api.src.db.models.CountEvent`, `services.api.src.db.models.CountAggregate`
- Produces: `GET /api/v1/lines/{id}/counts?from=&to=&granularity=minute|hourly|daily&page=1&limit=50`

- [ ] **Step 1: Write the failing test**

Create `services/api/tests/test_counts_api.py`:
```python
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from services.api.src.main import app
from services.api.src.db.session import get_db
from services.api.src.db.models import Base, Line, CountEvent, CountAggregate
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

@pytest.fixture
def counts_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestingSession()
    db.add(Line(id="line-1", name="Line 1", daily_target=1000, is_active=True))
    now = datetime(2026, 10, 16, 10, 0, 0, tzinfo=timezone.utc)
    for i in range(15):
        db.add(CountEvent(line_id="line-1", track_id=i + 1, ts_utc=now + timedelta(minutes=i), confidence=0.99))
    db.add(CountAggregate(
        line_id="line-1",
        window_start=now,
        window_end=now + timedelta(minutes=60),
        count=15,
        rate_per_min=0.25,
        confidence_avg=0.99,
        status="NORMAL"
    ))
    db.commit()
    db.close()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

def test_get_line_counts(counts_client):
    response = counts_client.get("/api/v1/lines/line-1/counts?page=1&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "aggregates" in data
    assert "events" in data
    assert "pagination" in data
    assert len(data["events"]) == 10
    assert data["pagination"]["total"] == 15
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest services/api/tests/test_counts_api.py -v`
Expected: FAIL (404 Not Found).

- [ ] **Step 3: Write minimal implementation**

Create `services/api/src/api/counts.py`:
```python
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

    # Fetch aggregates
    agg_query = select(CountAggregate).where(CountAggregate.line_id == line_id)
    if from_time:
        try:
            f_dt = datetime.fromisoformat(from_time.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
            agg_query = agg_query.where(CountAggregate.window_start >= f_dt)
        except Exception:
            pass
    if to_time:
        try:
            t_dt = datetime.fromisoformat(to_time.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
            agg_query = agg_query.where(CountAggregate.window_start <= t_dt)
        except Exception:
            pass
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
    if from_time:
        events_query = events_query.where(CountEvent.ts_utc >= f_dt)
    if to_time:
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
```

In `services/api/src/main.py`:
Include `counts_router`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest services/api/tests/test_counts_api.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add services/api/src/api/counts.py services/api/src/main.py services/api/tests/test_counts_api.py
git commit -m "feat(api): add historical count aggregates and paginated logs REST endpoint"
```

---

### Task 4: Alarms Management Lifecycle API (`GET /alarms`, `PATCH /alarms/{id}`)

**Files:**
- Create: `services/api/src/api/alarms.py`
- Modify: `services/api/src/main.py`
- Test: `services/api/tests/test_alarms_lifecycle_api.py`

**Interfaces:**
- Consumes: `services.api.src.db.models.Alarm`
- Produces: `router = APIRouter(prefix="/api/v1/alarms", tags=["alarms"])`

- [ ] **Step 1: Write the failing test**

Create `services/api/tests/test_alarms_lifecycle_api.py`:
```python
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from services.api.src.main import app
from services.api.src.db.session import get_db
from services.api.src.db.models import Base, Alarm
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

@pytest.fixture
def alarms_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestingSession()
    db.add(Alarm(id=1, line_id="line-1", alarm_type="SPEED_WARNING", severity="WARNING", message="Slow conveyor", status="OPEN", opened_at=datetime.now(timezone.utc)))
    db.commit()
    db.close()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

def test_list_alarms(alarms_client):
    response = alarms_client.get("/api/v1/alarms?status=OPEN")
    assert response.status_code == 200
    alarms = response.json()
    assert len(alarms) == 1
    assert alarms[0]["id"] == 1
    assert alarms[0]["status"] == "OPEN"

def test_acknowledge_and_resolve_alarm(alarms_client):
    # Acknowledge
    ack_res = alarms_client.patch("/api/v1/alarms/1", json={"status": "ACKNOWLEDGED", "notes": "Inspecting belt"})
    assert ack_res.status_code == 200
    assert ack_res.json()["status"] == "ACKNOWLEDGED"
    assert ack_res.json()["ack_at"] is not None

    # Resolve
    resolve_res = alarms_client.patch("/api/v1/alarms/1", json={"status": "RESOLVED", "notes": "Belt speed fixed"})
    assert resolve_res.status_code == 200
    assert resolve_res.json()["status"] == "RESOLVED"
    assert resolve_res.json()["resolved_at"] is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest services/api/tests/test_alarms_lifecycle_api.py -v`
Expected: FAIL (404 Not Found).

- [ ] **Step 3: Write minimal implementation**

Create `services/api/src/api/alarms.py`:
```python
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from services.api.src.db.models import Alarm
from services.api.src.db.session import get_db

router = APIRouter(prefix="/api/v1/alarms", tags=["alarms"])

class AlarmDTO(BaseModel):
    id: int
    line_id: str
    alarm_type: str
    severity: str
    message: str
    status: str
    opened_at: str
    ack_at: Optional[str]
    resolved_at: Optional[str]

class AlarmPatchPayload(BaseModel):
    status: str  # "ACKNOWLEDGED" or "RESOLVED"
    notes: Optional[str] = None
    acknowledged_by: Optional[str] = None

@router.get("", response_model=List[AlarmDTO])
def list_alarms(
    line_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = select(Alarm)
    if line_id:
        query = query.where(Alarm.line_id == line_id)
    if status:
        query = query.where(Alarm.status == status.upper())
    if severity:
        query = query.where(Alarm.severity == severity.upper())
    
    query = query.order_by(Alarm.opened_at.desc())
    alarms = db.scalars(query).all()

    return [
        AlarmDTO(
            id=a.id,
            line_id=a.line_id,
            alarm_type=a.alarm_type,
            severity=a.severity,
            message=a.message,
            status=a.status,
            opened_at=a.opened_at.isoformat() if a.opened_at else "",
            ack_at=a.ack_at.isoformat() if a.ack_at else None,
            resolved_at=a.resolved_at.isoformat() if a.resolved_at else None,
        )
        for a in alarms
    ]

@router.patch("/{alarm_id}", response_model=AlarmDTO)
def patch_alarm(
    alarm_id: int,
    payload: AlarmPatchPayload,
    db: Session = Depends(get_db),
):
    alarm = db.get(Alarm, alarm_id)
    if not alarm:
        raise HTTPException(status_code=404, detail="Alarm not found")

    target_status = payload.status.upper()
    now = datetime.now(timezone.utc)

    if target_status == "ACKNOWLEDGED":
        alarm.status = "ACKNOWLEDGED"
        alarm.ack_at = now
        if payload.notes:
            alarm.message = f"{alarm.message} [Ack Note: {payload.notes}]"
    elif target_status == "RESOLVED":
        alarm.status = "RESOLVED"
        alarm.resolved_at = now
        if payload.notes:
            alarm.message = f"{alarm.message} [Resolution: {payload.notes}]"
    else:
        raise HTTPException(status_code=400, detail=f"Invalid target status: {target_status}")

    db.commit()
    db.refresh(alarm)

    return AlarmDTO(
        id=alarm.id,
        line_id=alarm.line_id,
        alarm_type=alarm.alarm_type,
        severity=alarm.severity,
        message=alarm.message,
        status=alarm.status,
        opened_at=alarm.opened_at.isoformat() if alarm.opened_at else "",
        ack_at=alarm.ack_at.isoformat() if alarm.ack_at else None,
        resolved_at=alarm.resolved_at.isoformat() if alarm.resolved_at else None,
    )
```

In `services/api/src/main.py`:
Include `alarms_router`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest services/api/tests/test_alarms_lifecycle_api.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add services/api/src/api/alarms.py services/api/src/main.py services/api/tests/test_alarms_lifecycle_api.py
git commit -m "feat(api): add alarms filtering and acknowledge/resolve lifecycle REST endpoints"
```

---

### Task 5: Authentication & User Profile API (`POST /auth/login`, `GET /auth/me`)

**Files:**
- Create: `services/api/src/services/auth.py`
- Create: `services/api/src/api/auth.py`
- Modify: `services/api/src/main.py`
- Test: `services/api/tests/test_auth_api.py`

**Interfaces:**
- Consumes: `services.api.src.db.models.User`, `jwt`
- Produces: `router = APIRouter(prefix="/api/v1/auth", tags=["auth"])`

- [ ] **Step 1: Write the failing test**

Create `services/api/tests/test_auth_api.py`:
```python
import pytest
from fastapi.testclient import TestClient
from services.api.src.main import app
from services.api.src.db.session import get_db
from services.api.src.db.models import Base, User
from services.api.src.services.auth import hash_password
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

@pytest.fixture
def auth_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestingSession()
    db.add(User(username="admin", password_hash=hash_password("admin123"), role="ADMIN", is_active=True))
    db.commit()
    db.close()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

def test_login_success(auth_client):
    res = auth_client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200
    token = res.json()["access_token"]
    assert token

    me_res = auth_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "admin"
    assert me_res.json()["role"] == "ADMIN"

def test_login_invalid_password(auth_client):
    res = auth_client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert res.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest services/api/tests/test_auth_api.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

Create `services/api/src/services/auth.py`:
```python
import hashlib
import jwt
from datetime import datetime, timezone, timedelta
from typing import Optional

SECRET_KEY = "cdc-poultry-counter-secret-key"
ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return hash_password(plain_password) == hashed_password

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=24))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None
```

Create `services/api/src/api/auth.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from services.api.src.db.models import User
from services.api.src.db.session import get_db
from services.api.src.services.auth import (
    verify_password,
    create_access_token,
    decode_access_token,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

class UserDTO(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserDTO

@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalars(select(User).where(User.username == payload.username)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is inactive")

    token = create_access_token({"sub": user.username, "role": user.role, "uid": user.id})
    return LoginResponse(
        access_token=token,
        user=UserDTO(id=user.id, username=user.username, role=user.role, is_active=user.is_active),
    )

@router.get("/me", response_model=UserDTO)
def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ")[1]
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.scalars(select(User).where(User.username == payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserDTO(id=user.id, username=user.username, role=user.role, is_active=user.is_active)
```

In `services/api/src/main.py`:
Include `auth_router`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest services/api/tests/test_auth_api.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add services/api/src/services/auth.py services/api/src/api/auth.py services/api/src/main.py services/api/tests/test_auth_api.py
git commit -m "feat(api): add JWT authentication and user profile endpoints"
```

---

### Task 6: PDF Report Generator via ReportLab (`GET /reports/export?format=pdf`)

**Files:**
- Create: `services/api/src/services/pdf_exporter.py`
- Modify: `services/api/src/api/reports.py`
- Test: `services/api/tests/test_pdf_report_api.py`

**Interfaces:**
- Consumes: `reportlab`
- Produces: `PDFReportGenerator.generate_line_report(...) -> bytes` and `/api/v1/reports/export?format=pdf`

- [ ] **Step 1: Write the failing test**

Create `services/api/tests/test_pdf_report_api.py`:
```python
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from services.api.src.main import app
from services.api.src.db.session import get_db
from services.api.src.db.models import Base, CountAggregate
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

@pytest.fixture
def pdf_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestingSession()
    now = datetime(2026, 10, 16, 8, 0, 0, tzinfo=timezone.utc)
    db.add(CountAggregate(line_id="line-1", window_start=now, window_end=now, count=120, rate_per_min=120.0, confidence_avg=0.98, status="NORMAL"))
    db.commit()
    db.close()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

def test_export_pdf_report(pdf_client):
    res = pdf_client.get("/api/v1/reports/export?line_id=line-1&format=pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest services/api/tests/test_pdf_report_api.py -v`
Expected: FAIL (400 Unsupported format).

- [ ] **Step 3: Write minimal implementation**

Create `services/api/src/services/pdf_exporter.py`:
```python
import io
from datetime import datetime
from typing import Any, Sequence
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

class PDFReportGenerator:
    def generate_line_report(self, line_id: str, records: Sequence[dict[str, Any]]) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        elements = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            name="TitleStyle",
            parent=styles["Heading1"],
            fontSize=18,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=12,
        )
        elements.append(Paragraph(f"Lihat.id Poultry Counter - Production Report", title_style))
        elements.append(Paragraph(f"Line ID: <b>{line_id}</b> | Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))
        elements.append(Spacer(1, 16))

        # Summary
        total_count = sum(r.get("count", 0) for r in records)
        avg_rate = round(sum(r.get("rate_per_min", 0) for r in records) / len(records), 1) if records else 0

        summary_data = [
            ["Metric", "Value"],
            ["Total Birds Counted", str(total_count)],
            ["Average Speed (chickens/min)", f"{avg_rate} cpm"],
            ["Total Intervals", str(len(records))],
        ]
        summary_table = Table(summary_data, colWidths=[200, 200])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0284c7")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 20))

        # Details Table
        table_data = [["Interval Start", "Count", "Speed (cpm)", "Status"]]
        for r in records[:50]:  # limit for PDF layout
            ws = r.get("window_start")
            ws_str = ws.strftime("%Y-%m-%d %H:%M") if hasattr(ws, "strftime") else str(ws)
            table_data.append([
                ws_str,
                str(r.get("count", 0)),
                str(round(r.get("rate_per_min", 0), 1)),
                str(r.get("status", "NORMAL")),
            ])

        records_table = Table(table_data, colWidths=[180, 100, 120, 100])
        records_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ]))
        elements.append(records_table)

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()
```

In `services/api/src/api/reports.py`:
Update `export_report` to support `format.lower() in ["xlsx", "pdf"]`. When format is `"pdf"`, use `PDFReportGenerator` and return `application/pdf`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest services/api/tests/test_pdf_report_api.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add services/api/src/services/pdf_exporter.py services/api/src/api/reports.py services/api/tests/test_pdf_report_api.py
git commit -m "feat(api): add downloadable PDF report export via ReportLab"
```

---

### Task 7: MJPEG Live Video Preview Endpoint (`GET /lines/{id}/preview`)

**Files:**
- Create: `services/api/src/services/preview.py`
- Modify: `services/api/src/api/live.py`
- Test: `services/api/tests/test_preview_api.py`

**Interfaces:**
- Produces: `GET /api/v1/lines/{line_id}/preview` delivering `multipart/x-mixed-replace; boundary=frame`

- [ ] **Step 1: Write the failing test**

Create `services/api/tests/test_preview_api.py`:
```python
import pytest
from fastapi.testclient import TestClient
from services.api.src.main import app

def test_mjpeg_preview_stream():
    with TestClient(app) as client:
        # Request with stream=True and take first chunk
        with client.stream("GET", "/api/v1/lines/line-1/preview?max_frames=2") as response:
            assert response.status_code == 200
            assert "multipart/x-mixed-replace" in response.headers["content-type"]
            first_chunk = next(response.iter_bytes())
            assert b"--frame" in first_chunk or b"\xff\xd8" in first_chunk
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest services/api/tests/test_preview_api.py -v`
Expected: FAIL (404 Not Found).

- [ ] **Step 3: Write minimal implementation**

Create `services/api/src/services/preview.py`:
```python
import io
import cv2
import numpy as np
from datetime import datetime

class FrameGenerator:
    """Generates synthetic annotated frames with chicken conveyor and virtual line for preview."""

    @staticmethod
    def generate_jpeg_frame(line_id: str, frame_num: int = 0) -> bytes:
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img[:] = (30, 30, 40)  # dark background

        # Draw conveyor rail
        cv2.line(img, (50, 180), (590, 180), (120, 120, 120), 4)

        # Draw virtual counting line (green)
        cv2.line(img, (320, 100), (320, 400), (0, 220, 100), 2)
        cv2.putText(img, "COUNTING LINE", (260, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 100), 1)

        # Animated shackle / chicken moving across
        x_pos = int((frame_num * 15) % 500 + 70)
        cv2.rectangle(img, (x_pos - 30, 190), (x_pos + 30, 310), (0, 180, 255), 2)
        cv2.putText(img, f"Chicken #{(frame_num // 33) + 1} (98%)", (x_pos - 35, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 180, 255), 1)

        # HUD overlay
        ts_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(img, f"LIVE PREVIEW - {line_id.upper()} | {ts_str}", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        cv2.putText(img, f"Status: ACTIVE | 120 cpm", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 255, 100), 1)

        _, encoded = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return encoded.tobytes()
```

In `services/api/src/api/live.py`:
Add:
```python
import asyncio
from services.api.src.services.preview import FrameGenerator

@router.get("/{line_id}/preview")
async def preview_stream(line_id: str, max_frames: int | None = Query(None)):
    async def frame_stream():
        frame_idx = 0
        while True:
            if max_frames is not None and frame_idx >= max_frames:
                break
            jpeg_bytes = FrameGenerator.generate_jpeg_frame(line_id, frame_idx)
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"
            )
            frame_idx += 1
            await asyncio.sleep(0.066)  # ~15 fps

    return StreamingResponse(
        frame_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest services/api/tests/test_preview_api.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add services/api/src/services/preview.py services/api/src/api/live.py services/api/tests/test_preview_api.py
git commit -m "feat(api): add annotated MJPEG live preview video stream"
```

---

### Task 8: Frontend Data Client, Models, and AppContext

**Files:**
- Modify: `frontend/src/types/index.ts`
- Create: `frontend/src/services/apiClient.ts`
- Create: `frontend/src/context/AppContext.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `npm run build` in `frontend/`

**Interfaces:**
- Produces: `apiClient` with typed fetch methods and `useAppContext()` hook providing `{ currentLineId, setLineId, currentRole, setRole, lines, isConnected }`

- [ ] **Step 1: Expand TypeScript interfaces**

In `frontend/src/types/index.ts`:
Add `UserRole = "ADMIN" | "MANAGER" | "OPERATOR" | "VIEWER"`, `LineItem`, `CountsHistoryResponse`, etc.

- [ ] **Step 2: Implement apiClient**

Create `frontend/src/services/apiClient.ts`:
Standard fetch client pointing to `http://localhost:8000` with functions:
- `getLines()`
- `getLineSummary(lineId, period)`
- `getLineCounts(lineId, params)`
- `getAlarms(params)`
- `patchAlarm(alarmId, payload)`
- `updateLine(lineId, payload)`
- `login(username, password)`
- `getMe()`

- [ ] **Step 3: Implement AppContext**

Create `frontend/src/context/AppContext.tsx` providing active line, user role, lines list, and online status.

- [ ] **Step 4: Update App Header**

In `frontend/src/App.tsx`:
Add Line Selector dropdown, Role Switcher pills, and Connection status pulse.

- [ ] **Step 5: Verify build**

Run: `cd frontend && npm run build`
Expected: Succeeded with 0 errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/services/apiClient.ts frontend/src/context/AppContext.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add apiClient, AppContext, and top navigation header controls"
```

---

### Task 9: Real-Time LiveStream Hook & LiveStream Screen

**Files:**
- Create: `frontend/src/hooks/useLiveStream.ts`
- Create: `frontend/src/components/views/LiveStreamView.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `npm run build` in `frontend/`

**Interfaces:**
- Produces: `LiveStreamView` rendering the `/api/v1/lines/{id}/preview` video player, telemetry HUD (speed, last count, FPS), and threshold status tags.

- [ ] **Step 1: Implement useLiveStream hook**

Create `frontend/src/hooks/useLiveStream.ts`:
Handles `EventSource` connection to `/api/v1/lines/{lineId}/live`, automatic exponential backoff reconnection, and state management for `liveSpeed`, `lastCountTime`, and `fps`.

- [ ] **Step 2: Implement LiveStreamView**

Create `frontend/src/components/views/LiveStreamView.tsx`:
- Video player tag rendering `http://localhost:8000/api/v1/lines/{lineId}/preview`.
- Overlay controls: Show/Hide line, Show/Hide bounding boxes.
- Status HUD card: Live Speed (CPM), Last detection, Video resolution/FPS, Stream status badge.
- Threshold Matrix indicator: Under-speed warning / Normal / Over-speed.

- [ ] **Step 3: Mount LiveStreamView in App.tsx**

Update `App.tsx` to render `LiveStreamView` when `activeTab === "live"`.

- [ ] **Step 4: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useLiveStream.ts frontend/src/components/views/LiveStreamView.tsx frontend/src/App.tsx
git commit -m "feat(frontend): implement LiveStreamView with MJPEG stream and real-time telemetry HUD"
```

---

### Task 10: Overview Screen Live Integration

**Files:**
- Modify: `frontend/src/components/OverviewView.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `npm run build` in `frontend/`

**Interfaces:**
- Updates `OverviewView` to dynamically consume data from `apiClient.getLineSummary(lineId)` and live increments from `useLiveStream`.

- [ ] **Step 1: Wire OverviewView to API & Live Events**

Update `OverviewView.tsx` to load summary on line change, update total count in real-time when new counts arrive, render hourly pace chart from API counts, and display live system health metrics.

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/OverviewView.tsx frontend/src/App.tsx
git commit -m "feat(frontend): wire OverviewView to live summary API and real-time SSE updates"
```

---

### Task 11: Alarms Management Screen

**Files:**
- Create: `frontend/src/components/views/AlarmsView.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `npm run build` in `frontend/`

**Interfaces:**
- Produces: `AlarmsView` with status filter tabs (All, Open, Acknowledged, Resolved), incidents table, and Acknowledge / Resolve action modal.

- [ ] **Step 1: Implement AlarmsView**

Create `frontend/src/components/views/AlarmsView.tsx`:
- Filter buttons: Status (All, Open, Acknowledged, Resolved) and Severity (All, Critical, Warning).
- Table showing ID, Type, Severity badge, Message, Timestamp, Status, Ack At, Resolved At.
- Action Modal: "Acknowledge" and "Resolve with Note".
- Role check: If current role is `VIEWER`, actions are disabled.

- [ ] **Step 2: Mount AlarmsView in App.tsx**

Update `App.tsx` to render `AlarmsView` when `activeTab === "alarms"`.

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/views/AlarmsView.tsx frontend/src/App.tsx
git commit -m "feat(frontend): implement AlarmsView with status filters and acknowledge/resolve modal"
```

---

### Task 12: Reports & Analytics Screen

**Files:**
- Create: `frontend/src/components/views/ReportsView.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `npm run build` in `frontend/`

**Interfaces:**
- Produces: `ReportsView` with date preset picker, volume distribution chart, raw event log table, and 1-click Excel / PDF export buttons.

- [ ] **Step 1: Implement ReportsView**

Create `frontend/src/components/views/ReportsView.tsx`:
- Date Preset filter (Today, Yesterday, Last 7 Days).
- Metric summary cards (Total Count, Avg Speed, Peak Hour, Total Intervals).
- Recharts bar chart showing volume breakdown.
- Paginated table of raw count events.
- Export buttons:
  - "Export Excel (.xlsx)" -> triggers download from `/api/v1/reports/export?format=xlsx`.
  - "Export PDF (.pdf)" -> triggers download from `/api/v1/reports/export?format=pdf`.

- [ ] **Step 2: Mount ReportsView in App.tsx**

Update `App.tsx` to render `ReportsView` when `activeTab === "reports"`.

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/views/ReportsView.tsx frontend/src/App.tsx
git commit -m "feat(frontend): implement ReportsView with volume charts, event log, and Excel/PDF exports"
```

---

### Task 13: Settings Screen

**Files:**
- Create: `frontend/src/components/views/SettingsView.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `npm run build` in `frontend/`

**Interfaces:**
- Produces: `SettingsView` allowing configuration of line parameters, threshold matrices, and role permissions reference.

- [ ] **Step 1: Implement SettingsView**

Create `frontend/src/components/views/SettingsView.tsx`:
- Line Configuration form: Line Name, Daily Target (birds), Target Speed (chickens/min).
- Threshold Limits Matrix: Under-speed warning (cpm), Under-speed critical (cpm), Camera timeout (seconds).
- Role Permissions Matrix table (Admin, Manager, Operator, Viewer).
- Save action with feedback banner.

- [ ] **Step 2: Mount SettingsView in App.tsx**

Update `App.tsx` to render `SettingsView` when `activeTab === "settings"`.

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/views/SettingsView.tsx frontend/src/App.tsx
git commit -m "feat(frontend): implement SettingsView with line settings and threshold matrix editor"
```

---

### Task 14: End-to-End System Integration & Regression Verification

**Files:**
- Test all backend endpoints: `services/api/tests/`
- Build frontend: `frontend/`

- [ ] **Step 1: Run full backend test suite**

Run: `python -m pytest`
Expected: All tests pass (130 existing + new API tests, total ~142+ passing).

- [ ] **Step 2: Run frontend production build**

Run: `cd frontend && npm run build`
Expected: Production build succeeds with 0 errors.

- [ ] **Step 3: Commit any final integration adjustments**

```bash
git commit --allow-empty -m "chore(release): verify all tests pass and frontend builds cleanly"
```
