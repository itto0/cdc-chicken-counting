# Hybrid Threshold Matrix Design (System Baseline + Per-Line Overrides)

- **Date**: 2026-10-26
- **Status**: Approved
- **Scope**: Database schema (`lines`), backend alarm evaluation & API endpoints (`services/api`), shared DTOs (`shared/contracts.py`), and frontend UI (`PengaturanPage` & `ThresholdMatrixCard`).

---

## 1. Problem Statement & Motivation
Currently, operational thresholds (such as production rate limits for warning and critical alarms) are:
1. Hardcoded in the backend alarm evaluator (`AlarmEvaluator.evaluate_rate` uses static `< 130` warning and `< 110` critical).
2. Hardcoded in the frontend UI (`ThresholdMatrixCard.tsx` renders static values on `/lini-produksi`).
3. Not configurable per conveyor line in settings (`PengaturanPage.tsx`).

In real poultry processing facilities, different conveyor lines often have different physical speeds or daily throughput requirements. PRD Section 6.2 explicitly notes that *"targets and thresholds are per line"*. A **Hybrid Model** provides standard plant-wide baseline defaults (130 / 110 birds/min) while allowing managers and admins to optionally configure line-specific operational rate thresholds.

---

## 2. Architecture & Data Flow

```
+---------------------------------------------------------------------------------+
| System Baseline Constants (Default)                                             |
|  - DEFAULT_RATE_WARNING: 130.0 birds/min                                        |
|  - DEFAULT_RATE_CRITICAL: 110.0 birds/min                                       |
+---------------------------------------+-----------------------------------------+
                                        | Fallback when line overrides are null
                                        v
+---------------------------------------------------------------------------------+
| Database: `lines` Table (`services/api/src/db/models.py`)                       |
|  - rate_warning_threshold: Float | None (Nullable override)                     |
|  - rate_critical_threshold: Float | None (Nullable override)                    |
+-------------------+-----------------------------------+-------------------------+
                    |                                   |
                    v                                   v
+------------------------------------+   +----------------------------------------+
| Backend Alarm Evaluation           |   | Central REST API (`/api/v1/lines`)     |
| (services/api/src/services/alarms) |   |  - GET returns overrides + effective   |
|  - Resolves line thresholds vs def |   |  - PUT validates & saves line overrides|
|  - Triggers LOW_RATE alarm per-line|   +-------------------+--------------------+
+------------------------------------+                       |
                                                             v
                    +----------------------------------------+--------------------+
                    | Frontend Web Application                                    |
                    |  - PengaturanPage: View & edit per-line overrides (or reset)|
                    |  - ThresholdMatrixCard: Shows active line's rate threshold  |
                    |    (displays '(Kustom)' badge if overridden)                |
                    |  - LiveAlarmsCard: Displays alarms tuned to the active line |
                    +-------------------------------------------------------------+
```

---

## 3. Detailed Component Design

### 3.1 Baseline Defaults & Shared Contracts

#### Baseline System Constants
Defined in `services/api/src/services/alarms.py` (and re-exported/referenced as appropriate):
```python
DEFAULT_RATE_WARNING: float = 130.0   # birds/min
DEFAULT_RATE_CRITICAL: float = 110.0  # birds/min
```

#### Shared Contracts (`shared/contracts.py`)
Update `LineDTO`, `LineCreateDTO`, and `LineUpdateDTO`:
```python
class LineDTO(BaseModel):
    id: str
    name: str
    daily_target: int
    video_url: str | None = None
    line_coords: str | None = None
    line_direction: str = "down"
    is_active: bool = True
    rate_warning_threshold: float | None = None
    rate_critical_threshold: float | None = None
    effective_rate_warning: float = 130.0
    effective_rate_critical: float = 110.0
    created_at: datetime
```

### 3.2 Database Schema & Dynamic Migration

#### Model Update (`services/api/src/db/models.py`)
Add nullable float columns to `Line`:
```python
rate_warning_threshold: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
rate_critical_threshold: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
```

#### Idempotent Schema Migration (`services/api/src/main.py`)
In `init_db(target_engine=None)`:
```python
if "lines" in inspector.get_table_names():
    line_cols = [c["name"] for c in inspector.get_columns("lines")]
    with eng.connect() as conn:
        if "rate_warning_threshold" not in line_cols:
            conn.execute(text("ALTER TABLE lines ADD COLUMN rate_warning_threshold REAL NULL"))
        if "rate_critical_threshold" not in line_cols:
            conn.execute(text("ALTER TABLE lines ADD COLUMN rate_critical_threshold REAL NULL"))
        conn.commit()
```

### 3.3 Backend API & Alarm Evaluation

#### Pydantic Validation (`services/api/src/api/v1/schemas.py`)
In `LineCreateDTO` and `LineUpdateDTO`:
- `rate_warning_threshold: float | None = None`
- `rate_critical_threshold: float | None = None`
- Validator ensures:
  1. If either threshold is provided, both must be provided (or both null).
  2. Both must be positive numbers (`> 0.0`).
  3. `rate_critical_threshold < rate_warning_threshold`.
  4. Returns `422 Unprocessable Entity` with message: `"Ambang batas kritis harus lebih kecil dari ambang batas peringatan"`.

#### Alarm Evaluation (`services/api/src/services/alarms.py`)
In `evaluate_rate(line_id: str, rate_per_min: float)`:
1. Lookup the `Line` instance by `line_id`.
2. Compute effective thresholds:
   ```python
   warning_th = line.rate_warning_threshold if (line and line.rate_warning_threshold is not None) else DEFAULT_RATE_WARNING
   critical_th = line.rate_critical_threshold if (line and line.rate_critical_threshold is not None) else DEFAULT_RATE_CRITICAL
   ```
3. Evaluate:
   - If `rate_per_min < critical_th` → record or update alarm `LOW_RATE` with severity `CRITICAL`.
   - Else if `rate_per_min < warning_th` → record or update alarm `LOW_RATE` with severity `WARNING`.
   - Else → if an open `LOW_RATE` alarm exists for this line, resolve it (set status to `RESOLVED` and `resolved_at` to current UTC time).

### 3.4 Frontend UI & Integration

#### TypeScript Types (`frontend/src/types/index.ts`)
Update `Line`, `CreateLinePayload`, and `UpdateLinePayload`:
```typescript
export interface Line {
  id: string;
  name: string;
  daily_target: number;
  video_url?: string | null;
  line_coords?: string | null;
  line_direction?: string;
  is_active: boolean;
  rate_warning_threshold?: number | null;
  rate_critical_threshold?: number | null;
  effective_rate_warning?: number;
  effective_rate_critical?: number;
  created_at?: string;
}
```

#### Settings View (`frontend/src/features/settings/pages/PengaturanPage.tsx`)
1. Add state fields:
   - `rateWarningThreshold: number | string` (initialized from `currentLine?.rate_warning_threshold ?? ""`)
   - `rateCriticalThreshold: number | string` (initialized from `currentLine?.rate_critical_threshold ?? ""`)
2. Render input section in the form:
   - **Ambang Batas Kecepatan (Opsional / Override)**
   - Input `Peringatan / Amber (< ekor/menit)` with placeholder `130 (Default)`
   - Input `Kritis / Red (< ekor/menit)` with placeholder `110 (Default)`
   - Quick action button: `"Gunakan Standar Sistem"` to reset both inputs to empty (`null`).
3. Handle form submission:
   - Sends numeric values or `null` if empty.
   - Client-side validation checks `critical < warning`.

#### Live Monitoring Matrix (`frontend/src/features/livestream/components/ThresholdMatrixCard.tsx`)
1. Access selected line from `useAppContext()`.
2. Compute displayed thresholds:
   - Effective Warning = `selectedLine?.rate_warning_threshold ?? 130`
   - Effective Critical = `selectedLine?.rate_critical_threshold ?? 110`
   - Has Custom Override = `selectedLine?.rate_warning_threshold != null && selectedLine?.rate_critical_threshold != null`
3. In the "Laju Produksi (ekor/menit)" row:
   - Metrik column: `Laju Produksi (ekor/menit)` + (if custom: `<Badge variant="secondary" className="ml-2 text-[10px]">Kustom</Badge>`)
   - Warning column: `< ${effectiveWarning}`
   - Critical column: `< ${effectiveCritical}`
4. Retain standard benchmark rows for Latensi, Akurasi Deteksi, and Downtime.

---

## 4. Error Handling & Edge Cases

| Scenario | Behavior |
|----------|----------|
| User enters `critical >= warning` in Settings | Validation error blocked on client; rejected with 422 if sent to API. |
| User inputs negative or zero value | Form prevents submit; API rejects with 422 validation error. |
| User sets only one threshold (e.g. warning only) | Form requires both or clears both to ensure consistent limit pairing. |
| Line has `null` in DB | Defaults seamlessly to 130 / 110 without errors. |
| Line deleted or nonexistent in `evaluate_rate` | Fallback to default constants without raising exceptions. |
| Rate recovers above warning threshold | Existing open `LOW_RATE` alarm is resolved automatically. |

---

## 5. Verification & Testing Strategy

### 5.1 Backend Automated Tests (`services/api/tests/`)
1. `test_alarm_evaluator_rate_defaults`:
   - Line with no overrides (`None`). Rate `120` produces `WARNING`; rate `100` produces `CRITICAL`; rate `140` produces no alarm.
2. `test_alarm_evaluator_rate_custom_overrides`:
   - Line with overrides (warning `80.0`, critical `60.0`). Rate `85` produces no alarm; rate `75` produces `WARNING`; rate `55` produces `CRITICAL`.
3. `test_alarm_auto_resolve_on_rate_recovery`:
   - Open `LOW_RATE` alarm is resolved when rate returns above threshold.
4. `test_line_threshold_crud_and_validation`:
   - `PUT /api/v1/lines/{id}` with valid overrides succeeds and returns updated thresholds.
   - `PUT /api/v1/lines/{id}` with `critical >= warning` returns HTTP 422.
   - `PUT /api/v1/lines/{id}` with `null` resets overrides back to null.

### 5.2 Frontend Automated Tests (`frontend/src/`)
1. `ThresholdMatrixCard.test.tsx`:
   - Renders default `130` and `110` when line has no overrides.
   - Renders custom values and the `Kustom` badge when line has overrides.
2. `PengaturanPage.test.tsx`:
   - Entering custom threshold values submits correct payload.
   - Clicking "Gunakan Standar Sistem" clears inputs and saves `null`.
   - Invalid threshold inputs trigger validation message.
