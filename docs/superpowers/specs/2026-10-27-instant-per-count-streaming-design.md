# Instant Per-Count Real-Time Streaming Design Spec

**Date**: 2026-10-27  
**Scope**: Central API (`services/api`) and Web Frontend (`frontend`)  
**Status**: Approved  

---

## 1. Problem Statement & Goals

### 1.1 Context
In poultry processing facilities operating at speeds up to 150 BPM (birds per minute, or ~2.5 birds per second), operators observing the Cloud Web Dashboard need to see every bird counted in real time.

### 1.2 Identified Gap
Currently, `services/api/src/api/sync.py` only triggers SSE broadcast (`broadcast_line_update`) when aggregate windows (`payload.aggregates`) are submitted (typically once every 1 minute). When individual count events (`payload.events`) are ingested into the database, no SSE update is broadcast to the frontend. As a result, the frontend counter appears static until an aggregate window closes.

### 1.3 Scope Constraint
This implementation is strictly scoped to the **Central Cloud API** (`services/api`) and the **React Frontend** (`frontend`). No changes are required in the edge service (`counter-service`).

---

## 2. Central API Design (`services/api`)

### 2.1 Instant SSE Broadcast in Batch Sync (`POST /api/v1/sync/batch`)
In `services/api/src/api/sync.py`:
1. When `payload.events` contains new events:
   * Each event is saved to `CountEvent` with track ID deduplication (`IntegrityError` skipping).
   * After ingesting the events, compute:
     - `total_today`: Total counts recorded for the line today (using Jakarta timezone day bounds).
     - `rate_per_min`: Instant speed (CPM), derived either from the latest aggregate or calculated from recent event intervals.
     - `status`: Operational status ("NORMAL", "SLOW", "STOP").
   * Trigger `broadcast_line_update`:
     ```python
     broadcast_line_update(
         payload.line_id,
         "count",
         {
             "event_id": last_event.id,
             "track_id": last_event.track_id,
             "ts_utc": last_event.ts_utc.isoformat(),
             "total_today": int(total_today),
             "rate_per_min": float(rate_per_min),
             "status": status,
         },
     )
     ```

### 2.2 Dedicated Real-Time Event Endpoint (`POST /api/v1/lines/{line_id}/events`)
Provide a lightweight direct ingestion endpoint in `services/api/src/api/counts.py` or `sync.py`:
* **Path**: `POST /api/v1/lines/{line_id}/events`
* **Auth**: Edge Bearer Token / API Key (`X-API-Key` or `Authorization: Bearer cdc_live_...`).
* **Request Schema**:
  ```json
  {
    "track_id": 142,
    "confidence": 0.94,
    "ts_utc": "2026-10-27T10:15:30.400000Z"
  }
  ```
* **Behavior**:
  1. Validates line existence and auth.
  2. Persists `CountEvent` record (with deduplication on `(line_id, track_id, ts_utc)`).
  3. Re-calculates `total_today` and rolling CPM.
  4. Calls `broadcast_line_update(line_id, "count", {...})`.
  5. Returns HTTP 201 with `{ "success": true, "total_today": 4821 }`.

---

## 3. Frontend Architecture (`frontend`)

### 3.1 Hook Updates (`frontend/src/hooks/useLiveStream.ts`)
Update the `"count"` event listener in `useLiveStream.ts`:
```typescript
es.addEventListener("count", (event: MessageEvent) => {
  if (!isMountedRef.current) return;
  const data = parsePayload(event);
  if (data) {
    if (typeof data.total_today === "number") {
      setTotalToday(data.total_today);
    } else {
      setTotalToday((prev) => prev + 1);
    }
    if (typeof data.rate_per_min === "number") {
      setLiveSpeed(data.rate_per_min);
    } else if (typeof data.live_speed === "number") {
      setLiveSpeed(data.live_speed);
    }
    const timeVal = data.ts_utc || data.timestamp || new Date().toISOString();
    setLastCountTime(timeVal);
    setCountTick((c) => c + 1);
  }
});
```

### 3.2 Display Across Views
1. **Live Monitoring Page (`LiniProduksiPage` & `LiveVideoMonitor`)**:
   - `totalToday` is passed directly into `LiveVideoMonitor`.
   - The overlay bar (`Terhitung: {totalToday.toLocaleString("id-ID")}`) increments instantaneously on every count event received.
2. **Dashboard Overview (`DashboardPage` & `KpiCards`)**:
   - `liveSummary.total_count` derives from `totalToday`, immediately updating "Total Ayam Terhitung Hari Ini".
   - `liveSummary.current_speed_cpm` reflects latest speed.
3. **Visual Feedback**:
   - Clean, immediate numeric increment without layout shift or disruptive animations.

---

## 4. Resilience & Deduplication

1. **Duplicate Prevention**: If an edge gateway re-sends a batch or an event due to network retries, `IntegrityError` catches the duplicate `track_id` in DB insertion. Duplicate events do not increment `total_today` and do not trigger extra broadcast messages.
2. **SSE Reconnection**: If the browser's SSE connection disconnects, `useLiveStream`'s exponential backoff reconnects automatically. On reconnect, the initial `"status"` event restores the baseline `total_today` without desynchronization.
3. **High Frequency Ingestion**: Central API `LineBroadcaster` uses non-blocking asynchronous queue dispatch to ensure broadcasting up to 150 BPM (2-3 events/sec) introduces sub-5ms overhead.

---

## 5. Verification Plan

1. **Automated Backend Tests (`pytest`)**:
   - Test `POST /api/v1/sync/batch` with `events` array verifies `broadcast_line_update` is called with `"count"` event and updated `total_today`.
   - Test `POST /api/v1/lines/{line_id}/events` verifies record persistence and SSE broadcasting.
   - Test duplicate events do not broadcast phantom counts.
2. **Automated Frontend Tests (`vitest`)**:
   - Test `useLiveStream` correctly handles incoming `"count"` SSE messages with both absolute `total_today` and relative ticks.
   - Test `LiveVideoMonitor` and `DashboardPage` render updated totals immediately.
