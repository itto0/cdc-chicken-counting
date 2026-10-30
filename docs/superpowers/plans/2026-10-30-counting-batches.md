# Counting Batches Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement central backend database support, shared contracts, sync ingestion upsert logic, and public query APIs for operational counting batches received from edge counter services.

**Architecture:** 
1. Shared DTO contracts in `shared/contracts.py` define `CountingBatchDTO` and extend `CountEventDTO` and `SyncBatchPayload`.
2. SQLAlchemy ORM models in `services/api/src/db/models.py` define `CountingBatch` on table `batches` and add `batch_id` to `CountEvent`. `init_db()` in `services/api/src/main.py` provides dynamic schema migration for adding missing columns to existing SQLite/Postgres schemas.
3. `services/api/src/api/sync.py` implements dialect-agnostic ORM bulk-query upsert for incoming batches and passes `batch_id` to event persistence.
4. Dedicated public router `services/api/src/api/batches.py` provides list, latest, and detail endpoints with summary metrics (`duration_seconds`, `rate_per_minute`, `events_count`).

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.x, SQLite / PostgreSQL, pytest.

## Global Constraints
- Python interpreter path in this environment: `C:\Users\torino\AppData\Local\Python\bin\python.exe`.
- All batch query endpoints must be public (no JWT auth required).
- `GET /api/v1/lines/{line_id}/batches/latest` returns HTTP 200 with `null` if no batches exist for the line.
- `GET /api/v1/lines/{line_id}/batches` defaults to filtering `status="COMPLETED"`, but supports `status="ALL"` or `status="ACTIVE"`.
- `POST /api/v1/sync/batch` includes `ingested_batches: int` in its response dictionary.
- No dialect-specific SQL upsert syntax (`ON CONFLICT DO UPDATE`); use ORM query-then-update/insert.

---

### Task 1: Shared Contracts Update

**Files:**
- Modify: `shared/contracts.py`
- Test: `services/api/tests/test_batch_contracts.py`

**Interfaces:**
- Consumes: None
- Produces: `CountingBatchDTO`, updated `CountEventDTO(batch_id=...)`, updated `SyncBatchPayload(batches=...)`

- [ ] **Step 1: Write the failing test**

Create `services/api/tests/test_batch_contracts.py`:
```python
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from shared.contracts import CountingBatchDTO, CountEventDTO, SyncBatchPayload

def test_counting_batch_dto_valid():
    now = datetime.now(timezone.utc)
    dto = CountingBatchDTO(
        batch_id="line-1_20261030_120000",
        line_id="line-1",
        start_time=now,
        finish_time=now,
        total_count=120,
        status="COMPLETED"
    )
    assert dto.batch_id == "line-1_20261030_120000"
    assert dto.status == "COMPLETED"
    assert dto.total_count == 120

def test_counting_batch_dto_defaults_and_validation():
    now = datetime.now(timezone.utc)
    dto = CountingBatchDTO(
        batch_id="line-1_20261030_120000",
        start_time=now,
    )
    assert dto.line_id == "line-1"
    assert dto.status == "ACTIVE"
    assert dto.total_count == 0
    assert dto.finish_time is None

    with pytest.raises(ValidationError):
        CountingBatchDTO(
            batch_id="b1",
            start_time=now,
            total_count=-1
        )

def test_count_event_dto_with_batch_id():
    now = datetime.now(timezone.utc)
    event_with_batch = CountEventDTO(
        track_id=1,
        ts_utc=now,
        confidence=0.95,
        batch_id="batch_123"
    )
    assert event_with_batch.batch_id == "batch_123"

    event_without_batch = CountEventDTO(
        track_id=2,
        ts_utc=now,
        confidence=0.90
    )
    assert event_without_batch.batch_id is None

def test_sync_batch_payload_with_batches():
    now = datetime.now(timezone.utc)
    payload = SyncBatchPayload(
        line_id="line-1",
        batches=[
            CountingBatchDTO(
                batch_id="b1",
                start_time=now,
                total_count=50,
                status="COMPLETED"
            )
        ]
    )
    assert len(payload.batches) == 1
    assert payload.batches[0].batch_id == "b1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\torino\AppData\Local\Python\bin\python.exe -m pytest services/api/tests/test_batch_contracts.py -v`
Expected: FAIL with `ImportError: cannot import name 'CountingBatchDTO'`

- [ ] **Step 3: Update `shared/contracts.py`**

In `shared/contracts.py`, add `CountingBatchDTO`, update `CountEventDTO` to include `batch_id: str | None = None`, and update `SyncBatchPayload` to include `batches: list[CountingBatchDTO] = Field(default_factory=list)`.

```python
class CountingBatchDTO(BaseModel):
    batch_id: str                              # Format: [<prefix>_]<line_id>_YYYYMMDD_HHMMSS
    line_id: str = "line-1"
    start_time: datetime                       # UTC
    finish_time: datetime | None = None        # UTC
    total_count: int = Field(default=0, ge=0)
    status: Literal["ACTIVE", "COMPLETED"] = "ACTIVE"

class CountEventDTO(BaseModel):
    track_id: int
    ts_utc: datetime
    confidence: float
    line_id: str = "line-1"
    class_name: str = "chicken"
    batch_id: str | None = None

class SyncBatchPayload(BaseModel):
    line_id: str
    events: list[CountEventDTO] = Field(default_factory=list)
    aggregates: list[CountAggregateDTO] = Field(default_factory=list)
    health: HealthSampleDTO | None = None
    batches: list[CountingBatchDTO] = Field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\torino\AppData\Local\Python\bin\python.exe -m pytest services/api/tests/test_batch_contracts.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add shared/contracts.py services/api/tests/test_batch_contracts.py
git commit -m "feat(contracts): add CountingBatchDTO and update SyncBatchPayload"
```

---

### Task 2: Database Models & Schema Migration

**Files:**
- Modify: `services/api/src/db/models.py`
- Modify: `services/api/src/main.py`
- Test: `services/api/tests/test_batch_models.py`

**Interfaces:**
- Consumes: `shared/contracts.py`
- Produces: `CountingBatch` model (`batches` table), `CountEvent.batch_id` column, dynamic migration in `init_db`

- [ ] **Step 1: Write the failing test**

Create `services/api/tests/test_batch_models.py`:
```python
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from services.api.src.db.models import Base, Line, CountEvent, CountingBatch
from services.api.src.main import init_db

def test_counting_batch_model_creation():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    line = Line(id="line-1", name="Line 1")
    session.add(line)
    session.commit()

    now = datetime.now(timezone.utc)
    batch = CountingBatch(
        batch_id="batch_001",
        line_id="line-1",
        start_time=now,
        finish_time=now,
        total_count=42,
        status="COMPLETED"
    )
    session.add(batch)

    event = CountEvent(
        track_id=10,
        ts_utc=now,
        confidence=0.98,
        line_id="line-1",
        class_name="chicken",
        batch_id="batch_001"
    )
    session.add(event)
    session.commit()

    saved_batch = session.query(CountingBatch).filter_by(batch_id="batch_001").first()
    assert saved_batch is not None
    assert saved_batch.total_count == 42
    assert saved_batch.status == "COMPLETED"

    saved_event = session.query(CountEvent).filter_by(track_id=10).first()
    assert saved_event is not None
    assert saved_event.batch_id == "batch_001"

def test_init_db_migrates_events_batch_id():
    engine = create_engine("sqlite:///:memory:")
    # Simulate old schema without batch_id in events
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE lines (id VARCHAR(64) PRIMARY KEY, name VARCHAR(128) NOT NULL, status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE', target_speed FLOAT NOT NULL DEFAULT 60.0, created_at TIMESTAMP NOT NULL, updated_at TIMESTAMP NOT NULL)"))
        conn.execute(text("CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, track_id INTEGER NOT NULL, ts_utc TIMESTAMP NOT NULL, confidence FLOAT NOT NULL, line_id VARCHAR(64) NOT NULL, class_name VARCHAR(64) NOT NULL, created_at TIMESTAMP NOT NULL)"))

    # Run init_db on the simulated engine
    init_db(target_engine=engine)

    inspector = inspect(engine)
    event_cols = [c["name"] for c in inspector.get_columns("events")]
    assert "batch_id" in event_cols
    assert "batches" in inspector.get_table_names()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\torino\AppData\Local\Python\bin\python.exe -m pytest services/api/tests/test_batch_models.py -v`
Expected: FAIL with `ImportError: cannot import name 'CountingBatch'`

- [ ] **Step 3: Update `models.py` and `main.py`**

In `services/api/src/db/models.py`:
1. Add `batch_id = Column(String(128), nullable=True, index=True)` to `CountEvent`.
2. Define `CountingBatch`:
```python
class CountingBatch(Base):
    __tablename__ = "batches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String(128), unique=True, index=True, nullable=False)
    line_id = Column(String(64), ForeignKey("lines.id", ondelete="CASCADE"), index=True, nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    finish_time = Column(DateTime(timezone=True), nullable=True)
    total_count = Column(Integer, default=0, nullable=False)
    status = Column(String(32), default="ACTIVE", nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    line = relationship("Line", back_populates="batches", lazy="joined")
```
And add `batches = relationship("CountingBatch", back_populates="line", cascade="all, delete-orphan")` to `Line`.

In `services/api/src/main.py` inside `init_db(target_engine=None)`:
```python
# Check and add batch_id to events table if missing
if "events" in tables:
    event_cols = [c["name"] for c in inspector.get_columns("events")]
    if "batch_id" not in event_cols:
        with eng.begin() as conn:
            conn.execute(text("ALTER TABLE events ADD COLUMN batch_id VARCHAR(128)"))
            try:
                conn.execute(text("CREATE INDEX ix_events_batch_id ON events (batch_id)"))
            except Exception:
                pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\torino\AppData\Local\Python\bin\python.exe -m pytest services/api/tests/test_batch_models.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add services/api/src/db/models.py services/api/src/main.py services/api/tests/test_batch_models.py
git commit -m "feat(db): add CountingBatch model and dynamic schema migration for batch_id"
```

---

### Task 3: Batch Ingestion & Event Association in Sync API

**Files:**
- Modify: `services/api/src/api/sync.py`
- Modify: `services/api/tests/test_sync_endpoint.py`

**Interfaces:**
- Consumes: `CountingBatchDTO`, `CountingBatch`, `CountEvent(batch_id=...)`
- Produces: Ingestion of `payload.batches` (upsert), `event.batch_id` saved, `ingested_batches` in response

- [ ] **Step 1: Write the failing tests in `services/api/tests/test_sync_endpoint.py`**

Add tests to `services/api/tests/test_sync_endpoint.py`:
```python
def test_sync_batch_ingests_and_upserts_counting_batches(client, db_session):
    now = datetime.now(timezone.utc)
    payload = {
        "line_id": "line-1",
        "events": [
            {
                "track_id": 101,
                "ts_utc": now.isoformat(),
                "confidence": 0.95,
                "line_id": "line-1",
                "class_name": "chicken",
                "batch_id": "batch_test_001"
            }
        ],
        "aggregates": [],
        "batches": [
            {
                "batch_id": "batch_test_001",
                "line_id": "line-1",
                "start_time": now.isoformat(),
                "finish_time": None,
                "total_count": 1,
                "status": "ACTIVE"
            }
        ]
    }

    # Initial sync: inserts batch and event with batch_id
    resp = client.post("/api/v1/sync/batch", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["ingested_events"] == 1
    assert data["ingested_batches"] == 1

    # Verify batch in DB
    batch = db_session.query(CountingBatch).filter_by(batch_id="batch_test_001").first()
    assert batch is not None
    assert batch.status == "ACTIVE"
    assert batch.total_count == 1

    # Verify event has batch_id
    event = db_session.query(CountEvent).filter_by(track_id=101).first()
    assert event is not None
    assert event.batch_id == "batch_test_001"

    # Subsequent sync: updates existing batch to COMPLETED
    finish_now = datetime.now(timezone.utc)
    payload_update = {
        "line_id": "line-1",
        "events": [],
        "aggregates": [],
        "batches": [
            {
                "batch_id": "batch_test_001",
                "line_id": "line-1",
                "start_time": now.isoformat(),
                "finish_time": finish_now.isoformat(),
                "total_count": 50,
                "status": "COMPLETED"
            }
        ]
    }
    resp_update = client.post("/api/v1/sync/batch", json=payload_update)
    assert resp_update.status_code == 200
    assert resp_update.json()["ingested_batches"] == 1

    db_session.expire_all()
    updated_batch = db_session.query(CountingBatch).filter_by(batch_id="batch_test_001").first()
    assert updated_batch.status == "COMPLETED"
    assert updated_batch.total_count == 50
    assert updated_batch.finish_time is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\torino\AppData\Local\Python\bin\python.exe -m pytest services/api/tests/test_sync_endpoint.py::test_sync_batch_ingests_and_upserts_counting_batches -v`
Expected: FAIL (KeyError: 'ingested_batches' or missing batch persistence)

- [ ] **Step 3: Update `services/api/src/api/sync.py`**

1. Import `CountingBatch` from `..db.models`.
2. In `sync_batch` (and `/sync` endpoint handler):
   - When constructing `CountEvent`: pass `batch_id=ev.batch_id`.
   - Process `payload.batches`:
     ```python
     ingested_batches = 0
     if payload.batches:
         batch_ids = [b.batch_id for b in payload.batches]
         existing_batches = {
             b.batch_id: b for b in db.query(CountingBatch).filter(CountingBatch.batch_id.in_(batch_ids)).all()
         }
         for b_dto in payload.batches:
             # Ensure line exists
             line = db.query(Line).filter(Line.id == b_dto.line_id).first()
             if not line:
                 line = Line(id=b_dto.line_id, name=f"Line {b_dto.line_id}")
                 db.add(line)
                 db.flush()

             if b_dto.batch_id in existing_batches:
                 batch = existing_batches[b_dto.batch_id]
                 batch.finish_time = b_dto.finish_time
                 batch.total_count = b_dto.total_count
                 batch.status = b_dto.status
             else:
                 batch = CountingBatch(
                     batch_id=b_dto.batch_id,
                     line_id=b_dto.line_id,
                     start_time=b_dto.start_time,
                     finish_time=b_dto.finish_time,
                     total_count=b_dto.total_count,
                     status=b_dto.status,
                 )
                 db.add(batch)
             ingested_batches += 1
     ```
   - In return response dict, include `"ingested_batches": ingested_batches`.

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\torino\AppData\Local\Python\bin\python.exe -m pytest services/api/tests/test_sync_endpoint.py -v`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/api/src/api/sync.py services/api/tests/test_sync_endpoint.py
git commit -m "feat(api): ingest batches and record batch_id on events in sync endpoint"
```

---

### Task 4: Batch Query APIs

**Files:**
- Create: `services/api/src/api/batches.py`
- Modify: `services/api/src/main.py`
- Test: `services/api/tests/test_batches_api.py`

**Interfaces:**
- Consumes: `CountingBatch`, `CountEvent`, `Line`
- Produces:
  - `GET /api/v1/lines/{line_id}/batches`
  - `GET /api/v1/lines/{line_id}/batches/latest`
  - `GET /api/v1/lines/{line_id}/batches/{batch_id}`

- [ ] **Step 1: Write the failing tests**

Create `services/api/tests/test_batches_api.py`:
```python
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from services.api.src.db.models import Base, Line, CountingBatch, CountEvent
from services.api.src.db.session import get_db
from services.api.src.main import app, init_db

@pytest.fixture
def client_and_db():
    engine = create_engine("sqlite:///:memory:")
    init_db(target_engine=engine)
    TestingSession = sessionmaker(bind=engine)
    db = TestingSession()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    # Seed data
    line = Line(id="line-1", name="Line 1")
    db.add(line)
    
    t0 = datetime(2026, 10, 30, 10, 0, 0, tzinfo=timezone.utc)
    b1 = CountingBatch(
        batch_id="batch_1",
        line_id="line-1",
        start_time=t0,
        finish_time=t0 + timedelta(minutes=10),
        total_count=300,
        status="COMPLETED"
    )
    b2 = CountingBatch(
        batch_id="batch_2",
        line_id="line-1",
        start_time=t0 + timedelta(hours=1),
        finish_time=None,
        total_count=50,
        status="ACTIVE"
    )
    db.add_all([b1, b2])

    # Add 2 events linked to batch_1
    ev1 = CountEvent(track_id=1, ts_utc=t0, confidence=0.9, line_id="line-1", class_name="chicken", batch_id="batch_1")
    ev2 = CountEvent(track_id=2, ts_utc=t0 + timedelta(minutes=1), confidence=0.9, line_id="line-1", class_name="chicken", batch_id="batch_1")
    db.add_all([ev1, ev2])
    db.commit()

    yield client, db

    app.dependency_overrides.clear()

def test_get_batches_list_default_completed(client_and_db):
    client, _ = client_and_db
    resp = client.get("/api/v1/lines/line-1/batches")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["batch_id"] == "batch_1"
    assert data["items"][0]["status"] == "COMPLETED"

def test_get_batches_list_all_and_active(client_and_db):
    client, _ = client_and_db
    resp_all = client.get("/api/v1/lines/line-1/batches?status=ALL")
    assert resp_all.status_code == 200
    assert resp_all.json()["total"] == 2

    resp_active = client.get("/api/v1/lines/line-1/batches?status=ACTIVE")
    assert resp_active.status_code == 200
    assert resp_active.json()["total"] == 1
    assert resp_active.json()["items"][0]["batch_id"] == "batch_2"

def test_get_batches_date_range_filter(client_and_db):
    client, _ = client_and_db
    resp = client.get("/api/v1/lines/line-1/batches?status=ALL&start_date=2026-10-30T10:30:00Z")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["batch_id"] == "batch_2"

def test_get_latest_batch(client_and_db):
    client, _ = client_and_db
    resp = client.get("/api/v1/lines/line-1/batches/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["batch_id"] == "batch_2"

def test_get_latest_batch_empty(client_and_db):
    client, db = client_and_db
    line2 = Line(id="line-2", name="Line 2")
    db.add(line2)
    db.commit()

    resp = client.get("/api/v1/lines/line-2/batches/latest")
    assert resp.status_code == 200
    assert resp.json() is None

def test_get_batch_detail(client_and_db):
    client, _ = client_and_db
    resp = client.get("/api/v1/lines/line-1/batches/batch_1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["batch_id"] == "batch_1"
    assert data["duration_seconds"] == 600.0
    assert data["rate_per_minute"] == 30.0
    assert data["events_count"] == 2

def test_get_batch_detail_not_found(client_and_db):
    client, _ = client_and_db
    resp = client.get("/api/v1/lines/line-1/batches/nonexistent")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\torino\AppData\Local\Python\bin\python.exe -m pytest services/api/tests/test_batches_api.py -v`
Expected: FAIL with 404 Not Found on router paths.

- [ ] **Step 3: Implement `services/api/src/api/batches.py` and register in `main.py`**

Create `services/api/src/api/batches.py`:
- Use `APIRouter(prefix="/api/v1/lines/{line_id}/batches", tags=["batches"])`.
- Endpoints:
  1. `list_batches(line_id: str, status: Literal["ALL", "COMPLETED", "ACTIVE"] = "COMPLETED", start_date: datetime | None = None, end_date: datetime | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db))`
  2. `get_latest_batch(line_id: str, db: Session = Depends(get_db))`
  3. `get_batch_detail(line_id: str, batch_id: str, db: Session = Depends(get_db))`
- Detail calculation:
  ```python
  events_count = db.query(func.count(CountEvent.id)).filter(CountEvent.batch_id == batch.batch_id).scalar() or 0
  if batch.finish_time:
      duration_seconds = max((batch.finish_time - batch.start_time).total_seconds(), 0.0)
  else:
      duration_seconds = max((datetime.now(timezone.utc) - batch.start_time).total_seconds(), 0.0)
  rate_per_minute = round(batch.total_count / (duration_seconds / 60.0), 2) if duration_seconds > 0 else 0.0
  ```

In `services/api/src/main.py`:
- Import `batches_router` from `services.api.src.api.batches`.
- Include router `app.include_router(batches_router)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\torino\AppData\Local\Python\bin\python.exe -m pytest services/api/tests/test_batches_api.py -v`
Expected: All 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/api/src/api/batches.py services/api/src/main.py services/api/tests/test_batches_api.py
git commit -m "feat(api): implement batch query endpoints (list, latest, detail)"
```

---

### Task 5: End-to-End Verification & Regression Testing

**Files:**
- Test: All API test suites

- [ ] **Step 1: Run complete API test suite**

Run: `C:\Users\torino\AppData\Local\Python\bin\python.exe -m pytest services/api/tests/ -v`
Expected: All tests pass (including existing sync, lines, alarms, auth, etc.).

- [ ] **Step 2: Commit any cleanups and update documentation if necessary**

```bash
git status
git commit -m "chore: finalize counting batches central API integration"
```
