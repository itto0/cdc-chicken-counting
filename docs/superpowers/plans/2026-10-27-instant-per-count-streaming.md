# Instant Per-Count Real-Time Streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Instantly push every bird count event from the Central API to the Frontend via SSE so operators see the counter increment (+1) in real time without waiting for 1-minute aggregate windows.

**Architecture:** In `services/api/src/api/sync.py`, whenever individual `CountEvent` records are ingested, the API computes the updated `total_today` and rolling CPM speed and immediately broadcasts a `"count"` SSE event via `broadcast_line_update`. A lightweight `POST /api/v1/lines/{line_id}/events` endpoint is added in `services/api/src/api/counts.py` for direct event ingestion. In `frontend/src/hooks/useLiveStream.ts`, the `"count"` SSE listener updates `totalToday` and `countTick` on receipt, updating both `LiniProduksiPage` and `DashboardPage` without delay or layout shifts.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.0 (SQLite), pytest, React 18, TypeScript, Vitest, Testing Library.

## Global Constraints

- Scope: strictly Central API (`services/api`) and Web Frontend (`frontend`); zero changes to `counter-service`.
- Ingestion must deduplicate on `(line_id, track_id, ts_utc)` via `IntegrityError` and never broadcast phantom counts for duplicate events.
- Real-time updates must support up to 150 BPM (~2.5 events/sec) with sub-100ms end-to-end latency.
- UI display behavior: clean numeric increment only (no distracting animations, sound, or layout shifts).
- Existing backend pytest suite and frontend vitest suite must pass without regressions.

---

### Task 1: Instant SSE Broadcast on Event Ingestion in Batch Sync

**Files:**
- Modify: `services/api/src/api/sync.py:25-135`
- Test: `services/api/tests/test_sync_endpoint.py`

**Interfaces:**
- Consumes:
  - `SyncBatchPayload` from `shared.contracts`
  - `broadcast_line_update(line_id: str, event_type: str, data: dict)` from `services.api.src.api.live`
  - `get_jakarta_today_bounds_utc()` from `shared.time_utils`
- Produces:
  - `"count"` SSE broadcast whenever new `CountEvent` items are ingested in `sync_batch`, carrying `{ "total_today": int, "rate_per_min": float, "status": str, "track_id": int, "event_id": int, "ts_utc": str }`.

- [ ] **Step 1: Write failing tests in `services/api/tests/test_sync_endpoint.py`**

Add tests to verify:
1. When `POST /api/v1/sync/batch` receives `events` without `aggregates`, a `"count"` SSE event is broadcast with updated `total_today`.
2. When duplicate events are posted, no extra `"count"` event is broadcast.

```python
def test_sync_batch_broadcasts_count_event_on_ingested_events(setup_test_db):
    client = TestClient(app)
    from services.api.src.api.live import broadcaster
    broadcaster.clear()

    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        "line_id": "line_stream_test",
        "events": [
            {"track_id": 201, "ts_utc": now_iso, "confidence": 0.96}
        ]
    }

    # Subscribe to line_stream_test queue
    queue = broadcaster.subscribe("line_stream_test")

    resp = client.post("/api/v1/sync/batch", json=payload)
    assert resp.status_code == 200
    assert resp.json()["ingested_events"] == 1

    # Verify count SSE event was broadcast
    assert not queue.empty()
    event_type, event_data = queue.get_nowait()
    assert event_type == "count"
    assert event_data["total_today"] == 1
    assert event_data["track_id"] == 201


def test_sync_batch_duplicate_events_do_not_broadcast_count(setup_test_db):
    client = TestClient(app)
    from services.api.src.api.live import broadcaster
    broadcaster.clear()

    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        "line_id": "line_stream_test",
        "events": [
            {"track_id": 202, "ts_utc": now_iso, "confidence": 0.96}
        ]
    }

    resp1 = client.post("/api/v1/sync/batch", json=payload)
    assert resp1.status_code == 200
    assert resp1.json()["ingested_events"] == 1

    queue = broadcaster.subscribe("line_stream_test")

    # Resend identical payload (duplicate)
    resp2 = client.post("/api/v1/sync/batch", json=payload)
    assert resp2.status_code == 200
    assert resp2.json()["ingested_events"] == 0
    assert resp2.json()["duplicates_skipped"] == 1

    # Queue should NOT receive another count event for duplicate
    assert queue.empty()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest services/api/tests/test_sync_endpoint.py -k "test_sync_batch_broadcasts_count_event_on_ingested_events" -v`
Expected: FAIL because `sync_batch` currently only broadcasts under `if payload.aggregates:`.

- [ ] **Step 3: Implement minimal code in `services/api/src/api/sync.py`**

In `services/api/src/api/sync.py`:
1. Keep track of newly ingested `event_record` objects in a list `newly_ingested: list[CountEvent] = []`.
2. After `db.commit()`:
   If `newly_ingested`:
   - Compute `total_today` using Jakarta timezone bounds:
     ```python
     today_start_utc, today_end_utc = get_jakarta_today_bounds_utc()
     total_today = (
         db.query(func.count(CountEvent.id))
         .filter(
             CountEvent.line_id == payload.line_id,
             CountEvent.ts_utc >= today_start_utc.replace(tzinfo=None),
             CountEvent.ts_utc <= today_end_utc.replace(tzinfo=None),
         )
         .scalar()
         or 0
     )
     ```
   - Retrieve latest CPM rate and status from latest aggregate (or fallback to 0.0 and "NORMAL"):
     ```python
     latest_agg = (
         db.query(CountAggregate)
         .filter(CountAggregate.line_id == payload.line_id)
         .order_by(CountAggregate.window_end.desc())
         .first()
     )
     rate_per_min = float(latest_agg.rate_per_min) if latest_agg else 0.0
     status = latest_agg.status if latest_agg else "NORMAL"
     ```
   - For each event in `newly_ingested`:
     ```python
     broadcast_line_update(
         payload.line_id,
         "count",
         {
             "event_id": ev.id,
             "track_id": ev.track_id,
             "ts_utc": ev.ts_utc.isoformat(),
             "total_today": int(total_today),
             "rate_per_min": rate_per_min,
             "status": status,
         },
     )
     ```
3. Keep the existing `if payload.aggregates:` and `if payload.health:` logic intact. Note: in `if payload.aggregates:`, if events were also broadcast in the same batch, the aggregate broadcast continues to update the 1-minute summary.

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest services/api/tests/test_sync_endpoint.py -v`
Expected: ALL 13 tests in `test_sync_endpoint.py` PASS.

- [ ] **Step 5: Commit**

```bash
git add services/api/src/api/sync.py services/api/tests/test_sync_endpoint.py
git commit -m "feat(api): broadcast count SSE event immediately on count event ingestion"
```

---

### Task 2: Dedicated Real-Time Single Count Event Endpoint

**Files:**
- Modify: `services/api/src/api/counts.py`
- Test: `services/api/tests/test_counts_api.py`

**Interfaces:**
- Consumes:
  - `Line` and `CountEvent` models from `services.api.src.db.models`
  - `broadcast_line_update` from `services.api.src.api.live`
  - `get_jakarta_today_bounds_utc` from `shared.time_utils`
- Produces:
  - `POST /api/v1/lines/{line_id}/events` returning `{ "success": bool, "ingested": bool, "total_today": int, "line_id": str }`

- [ ] **Step 1: Write failing tests in `services/api/tests/test_counts_api.py`**

Add tests in `services/api/tests/test_counts_api.py`:
1. `POST /api/v1/lines/{line_id}/events` with valid event records event and broadcasts `"count"`.
2. Duplicate event returns 200/201 with `ingested: False` and does not duplicate count.
3. Non-existent `line_id` returns 404.

```python
def test_create_single_count_event_broadcasts_and_updates_total(client, test_db):
    from services.api.src.api.live import broadcaster
    from services.api.src.db.models import Line

    # Ensure line exists
    line = Line(id="line_single_test", name="Line Single Test", status="active")
    test_db.add(line)
    test_db.commit()

    broadcaster.clear()
    queue = broadcaster.subscribe("line_single_test")

    payload = {
        "track_id": 501,
        "confidence": 0.98,
        "ts_utc": datetime.now(timezone.utc).isoformat(),
    }

    resp = client.post("/api/v1/lines/line_single_test/events", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["success"] is True
    assert data["ingested"] is True
    assert data["total_today"] == 1

    # Verify SSE broadcast
    assert not queue.empty()
    event_type, event_data = queue.get_nowait()
    assert event_type == "count"
    assert event_data["track_id"] == 501
    assert event_data["total_today"] == 1


def test_create_single_count_event_duplicate_skips_broadcast(client, test_db):
    from services.api.src.api.live import broadcaster
    from services.api.src.db.models import Line

    line = Line(id="line_single_test", name="Line Single Test", status="active")
    test_db.add(line)
    test_db.commit()

    broadcaster.clear()
    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {"track_id": 502, "confidence": 0.98, "ts_utc": now_iso}

    resp1 = client.post("/api/v1/lines/line_single_test/events", json=payload)
    assert resp1.status_code == 201
    assert resp1.json()["ingested"] is True

    queue = broadcaster.subscribe("line_single_test")

    # Resend identical
    resp2 = client.post("/api/v1/lines/line_single_test/events", json=payload)
    assert resp2.status_code == 200
    assert resp2.json()["ingested"] is False
    assert queue.empty()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest services/api/tests/test_counts_api.py -k "test_create_single_count_event" -v`
Expected: FAIL with 404 or 405 Method Not Allowed because endpoint does not exist.

- [ ] **Step 3: Implement `POST /api/v1/lines/{line_id}/events` in `services/api/src/api/counts.py`**

In `services/api/src/api/counts.py`:
1. Define request and response schemas:
```python
class SingleCountEventRequest(BaseModel):
    track_id: int
    confidence: float = 1.0
    ts_utc: Optional[str] = None


class SingleCountEventResponse(BaseModel):
    success: bool
    ingested: bool
    total_today: int
    line_id: str
```
2. Implement router method:
```python
@router.post("/{line_id}/events", response_model=SingleCountEventResponse)
def create_single_count_event(
    line_id: str,
    payload: SingleCountEventRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

    if payload.ts_utc:
        dt = _parse_filter_datetime(payload.ts_utc, "ts_utc")
    else:
        dt = datetime.now(timezone.utc).replace(tzinfo=None)

    event_record = CountEvent(
        line_id=line_id,
        track_id=payload.track_id,
        ts_utc=dt,
        confidence=payload.confidence,
    )

    ingested = False
    try:
        with db.begin_nested():
            db.add(event_record)
            db.flush()
        ingested = True
        response.status_code = 201
    except IntegrityError:
        response.status_code = 200

    db.commit()

    # Query total today
    today_start_utc, today_end_utc = get_jakarta_today_bounds_utc()
    total_today = (
        db.query(func.count(CountEvent.id))
        .filter(
            CountEvent.line_id == line_id,
            CountEvent.ts_utc >= today_start_utc.replace(tzinfo=None),
            CountEvent.ts_utc <= today_end_utc.replace(tzinfo=None),
        )
        .scalar()
        or 0
    )

    if ingested:
        latest_agg = (
            db.query(CountAggregate)
            .filter(CountAggregate.line_id == line_id)
            .order_by(CountAggregate.window_end.desc())
            .first()
        )
        rate = float(latest_agg.rate_per_min) if latest_agg else 0.0
        status = latest_agg.status if latest_agg else "NORMAL"

        broadcast_line_update(
            line_id,
            "count",
            {
                "event_id": event_record.id,
                "track_id": event_record.track_id,
                "ts_utc": event_record.ts_utc.isoformat(),
                "total_today": int(total_today),
                "rate_per_min": rate,
                "status": status,
            },
        )

    return SingleCountEventResponse(
        success=True,
        ingested=ingested,
        total_today=int(total_today),
        line_id=line_id,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest services/api/tests/test_counts_api.py -v`
Expected: ALL tests in `test_counts_api.py` PASS.

- [ ] **Step 5: Commit**

```bash
git add services/api/src/api/counts.py services/api/tests/test_counts_api.py
git commit -m "feat(api): add POST /api/v1/lines/{line_id}/events endpoint with live broadcast"
```

---

### Task 3: Frontend `useLiveStream` Real-Time Counter Hook Updates

**Files:**
- Modify: `frontend/src/hooks/useLiveStream.ts:123-156`
- Create: `frontend/src/hooks/__tests__/useLiveStream.test.ts`

**Interfaces:**
- Consumes:
  - `apiClient.getLiveStreamUrl(lineId)`
  - Browser `EventSource`
- Produces:
  - `LiveStreamState` with real-time `totalToday`, `liveSpeed`, `lastCountTime`, `countTick`.

- [ ] **Step 1: Write unit tests in `frontend/src/hooks/__tests__/useLiveStream.test.ts`**

Create test file mocking `EventSource`:
1. Verify `"status"` event initializes `totalToday` when `total_today >= 0`.
2. Verify `"count"` event sets `totalToday` when `total_today` is provided.
3. Verify `"count"` event increments `totalToday` when `total_today` is absent/undefined (tick mode).
4. Verify `countTick` increments on every `"count"` event.

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useLiveStream } from "../useLiveStream";

class MockEventSource {
  static instances: MockEventSource[] = [];
  listeners: Record<string, ((event: any) => void)[]> = {};
  url: string;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
    setTimeout(() => {
      if (this.onopen) this.onopen();
    }, 0);
  }

  addEventListener(type: string, listener: (event: any) => void) {
    if (!this.listeners[type]) this.listeners[type] = [];
    this.listeners[type].push(listener);
  }

  emit(type: string, data: any) {
    const listeners = this.listeners[type] || [];
    listeners.forEach((fn) => fn({ data: JSON.stringify(data) }));
  }

  close() {
    this.listeners = {};
  }
}

describe("useLiveStream hook", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("updates totalToday when count event arrives with total_today", async () => {
    const { result } = renderHook(() => useLiveStream("line-1"));

    // Wait for connection
    await vi.waitFor(() => expect(result.current.status).toBe("CONNECTED"));

    const instance = MockEventSource.instances[0];

    act(() => {
      instance.emit("count", {
        total_today: 42,
        rate_per_min: 125.5,
        ts_utc: "2026-10-27T10:00:00Z",
      });
    });

    expect(result.current.totalToday).toBe(42);
    expect(result.current.liveSpeed).toBe(125.5);
    expect(result.current.countTick).toBe(1);
    expect(result.current.lastCountTime).toBe("2026-10-27T10:00:00Z");
  });

  it("increments totalToday if count event omits total_today", async () => {
    const { result } = renderHook(() => useLiveStream("line-1"));

    await vi.waitFor(() => expect(result.current.status).toBe("CONNECTED"));
    const instance = MockEventSource.instances[0];

    // Initial status event sets baseline
    act(() => {
      instance.emit("status", { total_today: 10, status: "ONLINE" });
    });
    expect(result.current.totalToday).toBe(10);

    // Count tick without absolute total
    act(() => {
      instance.emit("count", { rate_per_min: 130 });
    });

    expect(result.current.totalToday).toBe(11);
    expect(result.current.countTick).toBe(1);
  });
});
```

- [ ] **Step 2: Run test to verify it fails or needs hook adjustments**

Run: `npm test --prefix frontend -- src/hooks/__tests__/useLiveStream.test.ts`
Expected: FAIL or missing features (such as `data.total_today >= 0` check or increment fallback).

- [ ] **Step 3: Update `frontend/src/hooks/useLiveStream.ts`**

Ensure in `useLiveStream.ts`:
1. Status event:
   ```typescript
   if (typeof data.total_today === "number" && data.total_today >= 0) {
     setTotalToday(data.total_today);
   }
   ```
2. Count event:
   ```typescript
   es.addEventListener("count", (event: MessageEvent) => {
     if (!isMountedRef.current) return;
     const data = parsePayload(event);
     if (data) {
       if (typeof data.rate_per_min === "number") {
         setLiveSpeed(data.rate_per_min);
       } else if (typeof data.live_speed === "number") {
         setLiveSpeed(data.live_speed);
       }
       if (typeof data.total_today === "number") {
         setTotalToday(data.total_today);
       } else {
         setTotalToday((prev) => prev + 1);
       }
       const timeVal = data.ts_utc || data.timestamp || new Date().toISOString();
       setLastCountTime(timeVal);
       setCountTick((c) => c + 1);
     }
   });
   ```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test --prefix frontend -- src/hooks/__tests__/useLiveStream.test.ts`
Expected: PASS (all tests pass).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useLiveStream.ts frontend/src/hooks/__tests__/useLiveStream.test.ts
git commit -m "feat(frontend): enhance useLiveStream to support immediate count ticks and absolute totals"
```

---

### Task 4: Full System Verification & Regression Testing

**Files:**
- Test: All backend pytest tests
- Test: All frontend unit tests
- Build: Frontend production build

- [ ] **Step 1: Run complete backend pytest suite**

Run: `py -m pytest services/api/tests/ -v`
Expected: ALL backend tests pass (100% green).

- [ ] **Step 2: Run frontend tests for affected components & hook**

Run: `npm test --prefix frontend -- src/hooks/__tests__/useLiveStream.test.ts src/features/overview/components/__tests__/KpiCards.test.tsx`
Expected: ALL tests pass.

- [ ] **Step 3: Run frontend production build**

Run: `npm run build --prefix frontend`
Expected: Build succeeds with zero TypeScript or bundle errors.

- [ ] **Step 4: Commit and finish**

```bash
git commit --allow-empty -m "chore: verify full backend and frontend instant counting integration"
```
