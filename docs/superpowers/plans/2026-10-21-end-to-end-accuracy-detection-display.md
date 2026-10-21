# End-to-End Accuracy Detection Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish end-to-end tracking and visualization of detection accuracy (`accuracy_pct`) from edge ONNX companion metrics to central cloud ingestion and live/dashboard frontend views.

**Architecture:** The edge counter service loads benchmark accuracy (`mAP@50`) from a companion JSON file adjacent to the ONNX model and sends it in periodic health sync payloads. The central API ingests and persists `accuracy_pct`, broadcasts it via SSE to live listeners, and includes it in line summaries. The React frontend consumes this via the SSE hook to display a dedicated metric tile in the Live Monitoring System Status card and show detection accuracy on the Dashboard KPI card.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.0, SQLite / PostgreSQL, Pydantic v2, React 18, TypeScript, Vite, Vitest, Tailwind CSS.

## Global Constraints

- Preserve backward compatibility across contracts: `accuracy_pct` must remain optional (`float | None = Field(default=None, ge=0.0, le=100.0)`).
- Never break existing database schemas: runtime migration must check existing columns before running `ALTER TABLE`.
- UI formatting: Format `accuracy_pct` as a rounded percentage string with 1 decimal place (e.g., `99.3%`) using Indonesian locale formatting (`id-ID`) or fallback to `-` when unavailable.
- Do not suppress accuracy when `total_count == 0` on Dashboard if valid accuracy telemetry is present.
- All existing test suites (Python backend `pytest` and frontend `vitest`) must pass without regression.

---

### Task 1: Edge Model Companion Metrics File (`counter-service`)

**Files:**
- Create: `D:\Project\Python\counter-service\models\carcass_yolov8n_metrics.json`
- Test: `D:\Project\Python\counter-service\tests\test_detector.py`

**Interfaces:**
- Consumes: YOLOv8 model training validation results (`runs/detect/train/results.csv`, epoch 25: mAP50 = 0.9925).
- Produces: JSON metadata file loaded by `load_model_accuracy_pct("models/carcass_yolov8n.onnx")` yielding `99.25`.

- [ ] **Step 1: Write the failing test**

In `D:\Project\Python\counter-service\tests\test_detector.py`, add a test to verify discovery for `models/carcass_yolov8n.onnx`:

```python
def test_production_model_companion_metrics_file():
    from pathlib import Path
    from src.detection.detector import load_model_accuracy_pct

    model_path = Path("models/carcass_yolov8n.onnx")
    if model_path.exists():
        acc = load_model_accuracy_pct(model_path)
        assert acc is not None
        assert 90.0 <= acc <= 100.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_detector.py -k test_production_model_companion_metrics_file -v` (in `D:\Project\Python\counter-service`)
Expected: FAIL with `AssertionError: assert None is not None`

- [ ] **Step 3: Create companion metrics file**

Write `D:\Project\Python\counter-service\models\carcass_yolov8n_metrics.json`:

```json
{
  "map50": 0.9925,
  "map50_95": 0.8142,
  "precision": 0.9850,
  "recall": 0.9780
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_detector.py -k test_production_model_companion_metrics_file -v` (in `D:\Project\Python\counter-service`)
Expected: PASS

- [ ] **Step 5: Commit**

In `D:\Project\Python\counter-service`:
```bash
git add models/carcass_yolov8n_metrics.json tests/test_detector.py
git commit -m "feat: add companion metrics json for carcass_yolov8n model"
```

---

### Task 2: Central Shared Contracts & Database Migration (`cdc-chicken-counting`)

**Files:**
- Modify: `shared/contracts.py:75-95`
- Modify: `services/api/src/db/models.py:59-75`
- Modify: `services/api/src/main.py:26-35`
- Test: `tests/shared/test_contracts.py`
- Test: `services/api/tests/test_db_models.py`

**Interfaces:**
- Consumes: Pydantic v2 `BaseModel`, SQLAlchemy 2.0 `Mapped`, `mapped_column`.
- Produces: `HealthSampleDTO.accuracy_pct: float | None`, `HealthSample.accuracy_pct: Mapped[float | None]`, idempotent SQLite migration in `init_db()`.

- [ ] **Step 1: Write the failing tests**

In `tests/shared/test_contracts.py`, add a test:

```python
def test_health_sample_dto_accuracy_pct():
    from shared.contracts import HealthSampleDTO

    sample = HealthSampleDTO(
        fps=30.0,
        latency_p95_ms=25.0,
        cpu_pct=15.0,
        mem_pct=40.0,
        stream_state="ONLINE",
        accuracy_pct=99.25,
    )
    assert sample.accuracy_pct == 99.25

    with pytest.raises(ValidationError):
        HealthSampleDTO(
            fps=30.0,
            latency_p95_ms=25.0,
            cpu_pct=15.0,
            mem_pct=40.0,
            stream_state="ONLINE",
            accuracy_pct=105.0,
        )
```

In `services/api/tests/test_db_models.py`, add a test:

```python
def test_health_sample_model_accuracy_pct(session):
    from services.api.src.db.models import HealthSample

    sample = HealthSample(
        line_id="line-1",
        fps=29.8,
        latency_p95_ms=35.0,
        cpu_pct=10.0,
        mem_pct=20.0,
        stream_state="ONLINE",
        accuracy_pct=98.75,
    )
    session.add(sample)
    session.commit()

    retrieved = session.query(HealthSample).filter_by(id=sample.id).first()
    assert retrieved.accuracy_pct == 98.75
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/shared/test_contracts.py -k test_health_sample_dto_accuracy_pct -v`
Expected: FAIL (Unexpected keyword argument `accuracy_pct` or validation failure)

- [ ] **Step 3: Update contract, model, and init_db**

1. In `shared/contracts.py`:
Update `HealthSampleDTO`:
```python
class HealthSampleDTO(BaseModel):
    fps: float = Field(ge=0.0)
    latency_p95_ms: float = Field(ge=0.0)
    cpu_pct: float = Field(ge=0.0, le=100.0)
    mem_pct: float = Field(ge=0.0, le=100.0)
    stream_state: str = Field(pattern="^(ONLINE|DEGRADED|OFFLINE)$")
    model_name: str | None = None
    model_version: str | None = None
    accuracy_pct: float | None = Field(default=None, ge=0.0, le=100.0)
```

2. In `services/api/src/db/models.py`:
Update `HealthSample`:
```python
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
    accuracy_pct: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
```

3. In `services/api/src/main.py`:
In `init_db(target_engine=None)`, add idempotent migration check for SQLite:
```python
    # Dynamic SQLite migration for health_samples.accuracy_pct
    with eng.connect() as conn:
        try:
            from sqlalchemy import text
            res = conn.execute(text("PRAGMA table_info(health_samples)"))
            cols = [r[1] for r in res.fetchall()]
            if cols and "accuracy_pct" not in cols:
                conn.execute(text("ALTER TABLE health_samples ADD COLUMN accuracy_pct REAL NULL"))
                conn.commit()
        except Exception:
            pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/shared/test_contracts.py services/api/tests/test_db_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add shared/contracts.py services/api/src/db/models.py services/api/src/main.py tests/shared/test_contracts.py services/api/tests/test_db_models.py
git commit -m "feat: add accuracy_pct to HealthSampleDTO and database model"
```

---

### Task 3: Central API Sync Ingestion, SSE Broadcast & Summary (`cdc-chicken-counting`)

**Files:**
- Modify: `services/api/src/api/sync.py:53-65, 135-144`
- Modify: `services/api/src/api/summary.py:114-124`
- Test: `services/api/tests/test_sync_endpoint.py`
- Test: `services/api/tests/test_summary_api.py`

**Interfaces:**
- Consumes: `SyncBatchPayload.health.accuracy_pct`, `latest_health.accuracy_pct`.
- Produces: Persisted `HealthSample(accuracy_pct=...)`, SSE `health` payload containing `accuracy_pct`, and `LineSummaryResponse.detection_accuracy_pct`.

- [ ] **Step 1: Write the failing tests**

In `services/api/tests/test_sync_endpoint.py`, add a test:

```python
def test_sync_health_with_accuracy_pct(client, test_db):
    from services.api.src.db.models import HealthSample

    payload = {
        "line_id": "lineA",
        "events": [],
        "aggregates": [],
        "health": {
            "fps": 30.0,
            "latency_p95_ms": 22.5,
            "cpu_pct": 12.0,
            "mem_pct": 45.0,
            "stream_state": "ONLINE",
            "accuracy_pct": 99.25,
        },
    }
    resp = client.post("/api/v1/sync", json=payload)
    assert resp.status_code == 200

    record = test_db.query(HealthSample).filter_by(line_id="lineA").order_by(HealthSample.id.desc()).first()
    assert record is not None
    assert record.accuracy_pct == 99.25
```

In `services/api/tests/test_summary_api.py`, add a test:

```python
def test_summary_uses_latest_health_accuracy_pct(client, db_session):
    from services.api.src.db.models import HealthSample
    from datetime import datetime, timezone

    sample = HealthSample(
        line_id="line1",
        timestamp=datetime.now(timezone.utc),
        fps=30.0,
        latency_p95_ms=20.0,
        cpu_pct=10.0,
        mem_pct=30.0,
        stream_state="ONLINE",
        accuracy_pct=97.8,
    )
    db_session.add(sample)
    db_session.commit()

    res = client.get("/api/v1/lines/line1/summary?period=today").json()
    assert res["detection_accuracy_pct"] == 97.8
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest services/api/tests/test_sync_endpoint.py services/api/tests/test_summary_api.py -k "test_sync_health_with_accuracy_pct or test_summary_uses_latest_health_accuracy_pct" -v`
Expected: FAIL

- [ ] **Step 3: Implement sync ingestion, SSE broadcast, and summary resolution**

1. In `services/api/src/api/sync.py`:
In `sync_batch()` where `health_record` is instantiated:
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
        health_ingested = True
```
And in `broadcast_line_update`:
```python
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

2. In `services/api/src/api/summary.py`:
Update detection accuracy resolution:
```python
    # Detection accuracy prioritized from latest health sample, then average confidence, then fallback
    if latest_health and latest_health.accuracy_pct is not None:
        detection_accuracy = round(latest_health.accuracy_pct, 1)
    else:
        conf_query = (
            select(func.avg(CountEvent.confidence))
            .where(CountEvent.line_id == line_id)
            .where(CountEvent.ts_utc >= start_time)
        )
        if end_time is not None:
            conf_query = conf_query.where(CountEvent.ts_utc <= end_time)
        avg_conf = db.scalar(conf_query)
        detection_accuracy = round(float(avg_conf) * 100.0, 1) if avg_conf is not None else 99.2
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest services/api/tests/test_sync_endpoint.py services/api/tests/test_summary_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/api/src/api/sync.py services/api/src/api/summary.py services/api/tests/test_sync_endpoint.py services/api/tests/test_summary_api.py
git commit -m "feat: persist accuracy_pct on sync, broadcast over SSE, and expose in summary"
```

---

### Task 4: Frontend LiveStream SSE Hook & SystemStatusCard (`cdc-chicken-counting`)

**Files:**
- Modify: `frontend/src/hooks/useLiveStream.ts:6-16, 176-195`
- Modify: `frontend/src/features/livestream/components/SystemStatusCard.tsx:1-98`
- Modify: `frontend/src/features/livestream/pages/LiniProduksiPage.tsx:13-75`
- Test: `frontend/src/features/livestream/components/__tests__/SystemStatusCard.test.tsx`

**Interfaces:**
- Consumes: SSE `"health"` payload `{ fps, latency_ms, status, accuracy_pct }`.
- Produces: `useLiveStream` exposing `accuracyPct: number | null`, `SystemStatusCard` accepting `accuracyPct?: number | null`.

- [ ] **Step 1: Write the failing tests**

Update `frontend/src/features/livestream/components/__tests__/SystemStatusCard.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SystemStatusCard } from "../SystemStatusCard";

describe("SystemStatusCard", () => {
  it("defaults to 0 FPS, - Latensi, - Akurasi, and Offline when no props are provided", () => {
    render(<SystemStatusCard />);
    expect(screen.getByText("0")).toBeDefined();
    expect(screen.getAllByText("-").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Offline")).toBeDefined();
  });

  it("renders genuine FPS, latency, and accuracy when stream is online", () => {
    render(<SystemStatusCard fps={25} latencyMs={18} accuracyPct={99.25} streamState="online" />);
    expect(screen.getByText("25")).toBeDefined();
    expect(screen.getByText("18")).toBeDefined();
    expect(screen.getByText("99.3%")).toBeDefined();
    expect(screen.getByText("Online")).toBeDefined();
  });

  it("hides latency and accuracy with '-' when streamState is offline even if values provided", () => {
    render(<SystemStatusCard fps={0} latencyMs={50} accuracyPct={98.5} streamState="offline" />);
    const dashes = screen.getAllByText("-");
    expect(dashes.length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText("98.5%")).toBeNull();
    expect(screen.getByText("Offline")).toBeDefined();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test SystemStatusCard.test.tsx` (in `frontend/`)
Expected: FAIL

- [ ] **Step 3: Update hook, card component, and page**

1. In `frontend/src/hooks/useLiveStream.ts`:
Add `accuracyPct: number | null` to `LiveStreamState`:
```ts
export interface LiveStreamState {
  status: StreamStatus;
  liveSpeed: number; // CPM (Chickens per minute)
  lastCountTime: string | null;
  fps: number;
  latencyMs: number;
  accuracyPct: number | null;
  streamState: string;
  totalToday: number;
  countTick: number;
  reconnect: () => void;
}
```
In `useLiveStream`:
```ts
  const [accuracyPct, setAccuracyPct] = useState<number | null>(null);
```
In the `"health"` event listener:
```ts
        if (typeof data.accuracy_pct === "number") {
          setAccuracyPct(data.accuracy_pct);
        }
```
Return `accuracyPct` from `useLiveStream`.

2. In `frontend/src/features/livestream/components/SystemStatusCard.tsx`:
Update interface and render 4 columns:
```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface SystemStatusCardProps {
  fps?: number;
  latencyMs?: number;
  accuracyPct?: number | null;
  streamState?: "online" | "degraded" | "offline" | string;
}

export function SystemStatusCard({
  fps = 0,
  latencyMs = 0,
  accuracyPct = null,
  streamState = "offline",
}: SystemStatusCardProps) {
  const normalizedState = (streamState || "offline").toLowerCase();
  const isAvailable = normalizedState === "online" || normalizedState === "degraded";

  const getStatusColor = () => {
    switch (normalizedState) {
      case "online":
        return {
          dot: "bg-emerald-500 ring-4 ring-emerald-100",
          text: "text-emerald-700",
          label: "Online",
        };
      case "degraded":
        return {
          dot: "bg-amber-500 ring-4 ring-amber-100",
          text: "text-amber-700",
          label: "Degraded",
        };
      default:
        return {
          dot: "bg-rose-500 ring-4 ring-rose-100",
          text: "text-rose-700",
          label: "Offline",
        };
    }
  };

  const statusStyle = getStatusColor();
  const hasLatency = latencyMs > 0 && isAvailable;
  const hasAccuracy = accuracyPct != null && accuracyPct > 0 && isAvailable;

  return (
    <Card className="rounded-2xl border-slate-200/80 shadow-sm bg-white">
      <CardHeader className="p-4 pb-2">
        <CardTitle className="text-sm font-semibold text-slate-800">
          Status Sistem
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 pt-2">
        <div className="grid grid-cols-2 sm:grid-cols-4 divide-y sm:divide-y-0 sm:divide-x divide-slate-100 text-center sm:text-left gap-y-3 sm:gap-y-0">
          {/* FPS */}
          <div className="px-2 first:pl-0">
            <span className="text-xs text-slate-500 font-medium block mb-1">
              FPS
            </span>
            <span className="text-2xl font-bold tracking-tight text-slate-900">
              {Math.round(fps)}
            </span>
          </div>

          {/* Latensi */}
          <div className="px-3">
            <span className="text-xs text-slate-500 font-medium block mb-1">
              Latensi
            </span>
            {hasLatency ? (
              <span className="text-2xl font-bold tracking-tight text-slate-900">
                {Math.round(latencyMs)}{" "}
                <span className="text-sm font-normal text-slate-500">ms</span>
              </span>
            ) : (
              <span className="text-2xl font-bold tracking-tight text-slate-900">
                -
              </span>
            )}
          </div>

          {/* Akurasi */}
          <div className="px-3 pt-3 sm:pt-0">
            <span className="text-xs text-slate-500 font-medium block mb-1">
              Akurasi
            </span>
            {hasAccuracy ? (
              <span className="text-2xl font-bold tracking-tight text-slate-900">
                {accuracyPct.toFixed(1)}%
              </span>
            ) : (
              <span className="text-2xl font-bold tracking-tight text-slate-900">
                -
              </span>
            )}
          </div>

          {/* Status Edge */}
          <div className="px-3 last:pr-0 pt-3 sm:pt-0">
            <span className="text-xs text-slate-500 font-medium block mb-1">
              Status Edge
            </span>
            <div className="flex items-center gap-2 mt-1.5 justify-center sm:justify-start">
              <span
                className={`w-2.5 h-2.5 rounded-full ${statusStyle.dot} shrink-0`}
                aria-hidden="true"
              />
              <span className={`text-base font-bold ${statusStyle.text}`}>
                {statusStyle.label}
              </span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
```

3. In `frontend/src/features/livestream/pages/LiniProduksiPage.tsx`:
Destructure `accuracyPct` from `useLiveStream(currentLineId)`:
```tsx
  const { status, streamState, totalToday, fps, latencyMs, accuracyPct, reconnect } =
    useLiveStream(currentLineId);
```
Pass it to `SystemStatusCard`:
```tsx
  <SystemStatusCard
    fps={fps ?? 0}
    latencyMs={latencyMs ?? 0}
    accuracyPct={accuracyPct}
    streamState={isStreaming ? (streamState?.toLowerCase() || "online") : "offline"}
  />
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test SystemStatusCard.test.tsx` (in `frontend/`)
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useLiveStream.ts frontend/src/features/livestream/components/SystemStatusCard.tsx frontend/src/features/livestream/pages/LiniProduksiPage.tsx frontend/src/features/livestream/components/__tests__/SystemStatusCard.test.tsx
git commit -m "feat: show accuracy_pct in Live Monitoring SystemStatusCard"
```

---

### Task 5: Frontend Dashboard KPI Card (`cdc-chicken-counting`)

**Files:**
- Modify: `frontend/src/features/overview/components/KpiCards.tsx:26-35`
- Modify: `frontend/src/features/overview/components/__tests__/KpiCards.test.tsx:54-65`

**Interfaces:**
- Consumes: `summary.detection_accuracy_pct`.
- Produces: Formatted accuracy string even when `total_count == 0` if `detection_accuracy_pct > 0`.

- [ ] **Step 1: Write the updated test**

In `frontend/src/features/overview/components/__tests__/KpiCards.test.tsx`, update the test at line 54 to assert that accuracy renders when provided, even if `total_count == 0`:

```tsx
  it("renders accuracy when provided even if total_count is 0", () => {
    const summary: LineSummaryResponse = {
      ...baseSummary,
      total_count: 0,
      detection_accuracy_pct: 98.5,
    };

    render(<KpiCards summary={summary} />);

    const accuracyCard = screen.getByText("Akurasi Deteksi").closest("div");
    expect(accuracyCard?.textContent).toContain("98,5%");
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test KpiCards.test.tsx` (in `frontend/`)
Expected: FAIL with `expected '-' to contain '98,5%'`

- [ ] **Step 3: Update KpiCards condition**

In `frontend/src/features/overview/components/KpiCards.tsx`:
Change lines 26-35:
```tsx
  const accuracy = summary.detection_accuracy_pct;
  const hasAccuracy = accuracy != null && accuracy > 0;
  const formattedAccuracy = hasAccuracy
    ? `${accuracy.toLocaleString("id-ID", {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
      })}%`
    : "-";
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test KpiCards.test.tsx` (in `frontend/`)
Expected: PASS

- [ ] **Step 5: Run full frontend test suite**

Run: `npm test` (in `frontend/`)
Expected: All test suites PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/overview/components/KpiCards.tsx frontend/src/features/overview/components/__tests__/KpiCards.test.tsx
git commit -m "feat: show accuracy on Dashboard KPI card even when total_count is 0"
```
