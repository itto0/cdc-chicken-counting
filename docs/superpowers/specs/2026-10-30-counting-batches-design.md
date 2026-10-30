# Design Specification: Counting Batches Ingestion & Query APIs

**Date:** 2026-10-30  
**Status:** Approved  
**Topic:** Central API & Database Support for Counting Batches from Edge Counter Service

---

## 1. Overview & Context
The edge `counter-service` manages carcass counting in operational batches (starts automatically on conveyor activity, completes on idle timeout). It synchronizes batch records to the central backend API via `POST /api/v1/sync/batch` along with count events, aggregates, and health telemetry.

This specification details the central backend database schema, shared Pydantic contracts, sync ingestion upsert logic, and public query APIs for batch metrics and history.

---

## 2. Shared Data Contracts (`shared/contracts.py`)

### 2.1 New DTO: `CountingBatchDTO`
```python
class CountingBatchDTO(BaseModel):
    batch_id: str                              # Format: [<prefix>_]<line_id>_YYYYMMDD_HHMMSS
    line_id: str = "line-1"
    start_time: datetime                       # UTC
    finish_time: datetime | None = None        # UTC
    total_count: int = Field(default=0, ge=0)
    status: Literal["ACTIVE", "COMPLETED"] = "ACTIVE"
```

### 2.2 Updated DTO: `CountEventDTO`
Include optional `batch_id` association:
```python
class CountEventDTO(BaseModel):
    track_id: int
    ts_utc: datetime
    confidence: float
    line_id: str = "line-1"
    class_name: str = "chicken"
    batch_id: str | None = None
```

### 2.3 Updated DTO: `SyncBatchPayload`
Include optional list of counting batches:
```python
class SyncBatchPayload(BaseModel):
    line_id: str
    events: list[CountEventDTO] = Field(default_factory=list)
    aggregates: list[CountAggregateDTO] = Field(default_factory=list)
    health: HealthSampleDTO | None = None
    batches: list[CountingBatchDTO] = Field(default_factory=list)
```

---

## 3. Database Schema & Migration (`services/api/src/db/models.py`, `services/api/src/main.py`)

### 3.1 ORM Model: `CountingBatch`
Stored in the `batches` table:
* `id`: `Integer`, Primary Key, autoincrement.
* `batch_id`: `String(128)`, unique, indexed, nullable=False.
* `line_id`: `String(64)`, `ForeignKey("lines.id", ondelete="CASCADE")`, indexed, nullable=False.
* `start_time`: `DateTime(timezone=True)`, nullable=False.
* `finish_time`: `DateTime(timezone=True)`, nullable=True.
* `total_count`: `Integer`, default=0, nullable=False.
* `status`: `String(32)`, default="ACTIVE", nullable=False.
* `created_at`: `DateTime(timezone=True)`, default=datetime.utcnow, nullable=False.

### 3.2 Update ORM Model: `CountEvent`
Stored in the `events` table:
* Add column `batch_id = Column(String(128), nullable=True, index=True)`.

### 3.3 Dynamic Schema Migration (`init_db`)
In `services/api/src/main.py`:
* `Base.metadata.create_all(bind=eng)` creates the `batches` table if it does not exist.
* Using `inspect(eng)`, check if `"batch_id"` column exists in the `events` table. If not:
  Execute `ALTER TABLE events ADD COLUMN batch_id VARCHAR(128)`.
  Ensure `ix_events_batch_id` index is created.

---

## 4. Batch Ingestion Logic (`services/api/src/api/sync.py`)

### 4.1 Sync Batch Endpoint (`POST /api/v1/sync/batch` & `POST /api/v1/sync`)
1. **Line Auto-Provisioning**:
   If incoming `batch.line_id` is not present in `lines`, create the line record as done for events/aggregates.
2. **Upsert Logic for `payload.batches`**:
   - Query existing batch records matching all batch IDs:
     ```python
     existing_batches = {
         b.batch_id: b for b in db.query(CountingBatch).filter(
             CountingBatch.batch_id.in_([b.batch_id for b in payload.batches])
         ).all()
     }
     ```
   - For each batch DTO:
     - If `batch_id` exists: update `finish_time = dto.finish_time`, `total_count = dto.total_count`, `status = dto.status`.
     - If new: create a new `CountingBatch` instance with fields from DTO and add to session.
3. **Event Association**:
   - When instantiating `CountEvent` records from `payload.events`, assign `batch_id=event.batch_id`.
4. **Response Payload**:
   ```json
   {
     "status": "ok",
     "ingested_events": int,
     "ingested_aggregates": int,
     "ingested_batches": int,
     "alarms_triggered": int
   }
   ```

---

## 5. Query Endpoints (`services/api/src/api/batches.py`)

Router prefix: `/api/v1/lines/{line_id}/batches`, tags: `["batches"]`.
Authentication: Public (no auth required).

### 5.1 `GET /api/v1/lines/{line_id}/batches`
* **Query Parameters**:
  - `status: Literal["ALL", "COMPLETED", "ACTIVE"] = "COMPLETED"`
  - `start_date: datetime | None = None`
  - `end_date: datetime | None = None`
  - `page: int = Query(default=1, ge=1)`
  - `page_size: int = Query(default=20, ge=1, le=100)`
* **Filtering & Sorting**:
  - Filter `line_id == line_id`.
  - If `status != "ALL"`, filter `status == status`.
  - If `start_date`, filter `start_time >= start_date`.
  - If `end_date`, filter `start_time <= end_date`.
  - Order by `start_time.desc()`.
* **Response**: Paginated JSON object with `items`, `total`, `page`, `page_size`, `pages`.

### 5.2 `GET /api/v1/lines/{line_id}/batches/latest`
* **Filtering & Sorting**:
  - Filter `line_id == line_id`.
  - Order by `start_time.desc()`.
  - Fetch `.first()`.
* **Response**:
  - If found: 200 OK with batch object.
  - If none found: 200 OK with `null`.

### 5.3 `GET /api/v1/lines/{line_id}/batches/{batch_id}`
* **Lookup**:
  - Query single batch by `line_id` and `batch_id`.
  - If not found, raise 404 HTTPException.
* **Summary Metrics**:
  - `events_count`: `SELECT COUNT(id) FROM events WHERE batch_id = :batch_id`.
  - `duration_seconds`: `(finish_time - start_time).total_seconds()` if `finish_time` is set, else `(datetime.now(timezone.utc) - start_time).total_seconds()`.
  - `rate_per_minute`: `round(total_count / (duration_seconds / 60.0), 2)` if `duration_seconds > 0` else `0.0`.
* **Response**: Detailed JSON object with all batch columns plus `duration_seconds`, `rate_per_minute`, `events_count`.

---

## 6. Testing Strategy
1. **Contract Tests**: Verify serialization/deserialization of `CountingBatchDTO` and updated `CountEventDTO`, `SyncBatchPayload`.
2. **Migration Tests**: Verify `init_db()` safely creates `batches` table and adds `batch_id` column to existing `events` table.
3. **Sync Endpoint Tests (`test_sync_endpoint.py`)**:
   - Ingest batches with `POST /api/v1/sync/batch`.
   - Update existing batch (verify upsert behavior: total_count updated, status changed from ACTIVE to COMPLETED).
   - Ingest events tagged with `batch_id` and verify persistence.
4. **Batch Query Endpoint Tests (`test_batches_api.py`)**:
   - Pagination, date range filtering, status filtering.
   - Latest batch endpoint (with records and without records returning 200 null).
   - Detail batch endpoint with accurate duration, rate, and linked events count.
   - 404 error when batch_id does not exist.
