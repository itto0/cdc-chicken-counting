# End-to-End Accuracy Detection Display Design

- **Date**: 2026-10-21
- **Status**: Approved
- **Scope**: Edge companion metrics (`counter-service`), central API contracts & schema (`cdc-chicken-counting`), real-time SSE ingestion, and frontend display (Live Monitoring & Dashboard).

---

## 1. Problem Statement
The edge service (`counter-service`) was recently equipped with detection accuracy discovery (`load_model_accuracy_pct`) and outbox tracking via `HealthSampleDTO.accuracy_pct`. However:
1. The production model companion metrics file (`carcass_yolov8n_metrics.json`) is missing in `counter-service/models/`, causing the edge service to load `accuracy_pct = None`.
2. The central API (`cdc-chicken-counting`) does not define `accuracy_pct` on `HealthSampleDTO` or the `HealthSample` database table, dropping the metric during sync ingestion.
3. The real-time SSE telemetry broadcaster does not include `accuracy_pct` in the `"health"` event.
4. The frontend Live Monitoring page (`LiniProduksiPage` / `SystemStatusCard`) does not display accuracy, and the Dashboard KPI card suppresses accuracy if `total_count == 0`.

---

## 2. Architecture & Data Flow

```
+-------------------------------------------------------------------+
| counter-service (Edge Device)                                     |
|  - models/carcass_yolov8n.onnx + carcass_yolov8n_metrics.json     |
|  - load_model_accuracy_pct() -> 99.25%                            |
|  - Recorded in health_samples DB outbox                           |
+---------------------------------+---------------------------------+
                                  | SyncBatchPayload (health.accuracy_pct)
                                  v
+-------------------------------------------------------------------+
| cdc-chicken-counting API (Cloud / Central Server)                 |
|  - shared/contracts.py: HealthSampleDTO.accuracy_pct              |
|  - db/models.py: health_samples.accuracy_pct                      |
|  - api/sync.py: Ingests & stores accuracy_pct                     |
|  - api/sync.py: Broadcasts SSE 'health' with accuracy_pct         |
|  - api/summary.py: Uses latest_health.accuracy_pct for summary    |
+---------------------------------+---------------------------------+
                                  | SSE ("health") & REST (/summary)
                                  v
+-------------------------------------------------------------------+
| Frontend (React / Vite)                                           |
|  - useLiveStream hook captures accuracy_pct from 'health' event    |
|  - Live Monitoring: SystemStatusCard shows [FPS | Latensi | Akurasi | Status] |
|  - Dashboard: KpiCards displays Akurasi Deteksi immediately       |
+-------------------------------------------------------------------+
```

---

## 3. Detailed Component Design

### 3.1 Edge Metrics Companion (`counter-service`)
- **Path**: `D:\Project\Python\counter-service\models\carcass_yolov8n_metrics.json`
- **Metrics derived from training epoch 25 (`runs/detect/train/results.csv`)**:
  ```json
  {
    "map50": 0.9925,
    "map50_95": 0.8142,
    "precision": 0.9850,
    "recall": 0.9780
  }
  ```
- **Effect**: `load_model_accuracy_pct("models/carcass_yolov8n.onnx")` parses `map50` (0.9925), scales to percentage, and yields `99.25`.

### 3.2 Shared Contracts (`cdc-chicken-counting/shared/contracts.py`)
- Add field to `HealthSampleDTO`:
  ```python
  accuracy_pct: float | None = Field(default=None, ge=0.0, le=100.0)
  ```

### 3.3 Database Model & Schema Migration (`services/api/src/db/`)
- Update `services/api/src/db/models.py`:
  ```python
  class HealthSample(Base):
      ...
      accuracy_pct: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
  ```
- Startup Migration in `services/api/src/db/session.py` (or SQLite check):
  Ensure `ALTER TABLE health_samples ADD COLUMN accuracy_pct REAL NULL` runs idempotently if SQLite table lacks the column.

### 3.4 Sync Ingestion & SSE Broadcasting (`services/api/src/api/sync.py`)
- In `sync_batch()`:
  ```python
  if payload.health is not None:
      health_record = HealthSample(
          line_id=payload.line_id,
          fps=payload.health.fps,
          latency_p95_ms=payload.health.latency_p95_ms,
          cpu_pct=payload.health.cpu_pct,
          mem_pct=payload.health.mem_pct,
          stream_state=payload.health.stream_state,
          model_name=payload.health.model_name,
          model_version=payload.health.model_version,
          accuracy_pct=payload.health.accuracy_pct,
      )
      db.add(health_record)
      ...
      broadcast_line_update(
          payload.line_id,
          "health",
          {
              "fps": payload.health.fps,
              "latency_ms": payload.health.latency_p95_ms,
              "status": payload.health.stream_state,
              "accuracy_pct": payload.health.accuracy_pct,
          },
      )
  ```

### 3.5 Central Summary Endpoint (`services/api/src/api/summary.py`)
- In `get_line_summary()`:
  When calculating `detection_accuracy_pct`:
  1. If `latest_health` exists and `latest_health.accuracy_pct is not None`:
     `detection_accuracy = round(latest_health.accuracy_pct, 1)`
  2. Otherwise fallback to `avg_conf * 100.0` from `CountEvent` (if events exist).
  3. Otherwise default to `99.2`.

### 3.6 Frontend Telemetry Hook (`frontend/src/hooks/useLiveStream.ts`)
- Update `LiveStreamState`:
  ```ts
  export interface LiveStreamState {
    ...
    accuracyPct: number | null;
  }
  ```
- Initialize `accuracyPct` state to `null`.
- In `health` event listener:
  ```ts
  if (typeof data.accuracy_pct === "number") {
    setAccuracyPct(data.accuracy_pct);
  }
  ```

### 3.7 Live Monitoring UI (`SystemStatusCard.tsx` & `LiniProduksiPage.tsx`)
- Props in `SystemStatusCardProps`:
  ```ts
  interface SystemStatusCardProps {
    fps?: number;
    latencyMs?: number;
    accuracyPct?: number | null;
    streamState?: "online" | "degraded" | "offline" | string;
  }
  ```
- Grid layout updated from `grid-cols-3` to `grid-cols-2 sm:grid-cols-4`:
  - Tile 1: **FPS** (rounded number)
  - Tile 2: **Latensi** (`{latencyMs} ms` or `-`)
  - Tile 3: **Akurasi** (`{accuracyPct.toFixed(1)}%` or `-`)
  - Tile 4: **Status Edge** (colored indicator + text)
- Pass `accuracyPct={accuracyPct}` from `useLiveStream` in `LiniProduksiPage.tsx`.

### 3.8 Dashboard KPI Cards (`KpiCards.tsx`)
- Update formatting condition for **Akurasi Deteksi**:
  ```ts
  const accuracy = summary.detection_accuracy_pct;
  const hasAccuracy = accuracy != null && accuracy > 0;
  const formattedAccuracy = hasAccuracy
    ? `${accuracy.toLocaleString("id-ID", {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
      })}%`
    : "-";
  ```
  (Removes the requirement that `total_count > 0` before displaying accuracy).

---

## 4. Error Handling & Edge Cases
- **Missing or corrupted companion file**: If the metrics file is absent or corrupted, `load_model_accuracy_pct()` gracefully returns `None`. Contracts and database columns accept `None` / `NULL`.
- **Offline Edge Stream**: Frontend gracefully displays `-` when `accuracyPct` is `null` or edge is offline.
- **Out of Range Values**: Contract validates `0.0 <= accuracy_pct <= 100.0`. NaN, Inf, and booleans are rejected safely.
- **Backward Compatibility**: Sync payloads without `accuracy_pct` continue to work without errors.

---

## 5. Testing & Verification Plan
1. **Edge Service Tests**: Run pytest on `counter-service` to confirm companion JSON loading and health serialization.
2. **Backend Unit & Integration Tests**:
   - `test_contracts.py`: Validate `HealthSampleDTO` with `accuracy_pct`.
   - `test_sync_endpoint.py`: Test sync payload with `accuracy_pct` and verify database persistence & SSE broadcast data.
   - `test_summary_api.py`: Verify summary endpoint uses `latest_health.accuracy_pct`.
3. **Frontend Tests**:
   - `SystemStatusCard.test.tsx`: Test 4-column rendering with null/present `accuracyPct`.
   - `KpiCards.test.tsx`: Test accuracy rendering when count is 0.
   - Run `npm test` / Vitest.
