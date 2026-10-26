# Hybrid Threshold Matrix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a hybrid threshold matrix architecture where plant-wide baseline thresholds serve as defaults while individual production lines can configure custom production rate thresholds, evaluated dynamically in alarm services and reflected in live stream monitoring and line settings.

**Architecture:** Add nullable `rate_warning_threshold` and `rate_critical_threshold` columns to the `Line` SQLite table with automatic schema migration; expose effective and raw thresholds through `/api/v1/lines` DTOs with Pydantic validation; update `AlarmEvaluator.evaluate_rate` and `sync.py` to evaluate rate alarms against line-specific thresholds; provide settings UI in `PengaturanPage.tsx` with reset-to-default and validation; and update `ThresholdMatrixCard.tsx` on `/lini-produksi` to dynamically show active line rate thresholds with a "Kustom" badge when overridden.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Pydantic v2, SQLite, pytest, React 19, TypeScript, Vite, Vitest, Tailwind CSS, Lucide React.

## Global Constraints

- Default system warning threshold: `DEFAULT_RATE_WARNING = 130.0` birds/min.
- Default system critical threshold: `DEFAULT_RATE_CRITICAL = 110.0` birds/min.
- Reference baseline defaults for non-rate metrics (system-wide):
  - Latency: Warning `> 150 ms`, Critical `> 300 ms`
  - FPS: Warning `< 10 FPS`, Critical `< 5 FPS`
  - Accuracy: Warning `< 95%`, Critical `< 90%`
- Invariant 1: Threshold values must be positive floats (`> 0`).
- Invariant 2: When both warning and critical overrides are set on a line, critical must be strictly less than warning (`rate_critical_threshold < rate_warning_threshold`).
- Invariant 3: Setting a threshold to `null` resets the line to inherit the system baseline standard.
- Invariant 4: `AlarmEvaluator.evaluate_rate` falls back to `DEFAULT_RATE_WARNING` / `DEFAULT_RATE_CRITICAL` when line overrides are `None`.
- Invariant 5: When rate recovers to `>= warning_threshold`, any existing OPEN `LOW_RATE` alarm for the line is auto-resolved.
- Invariant 6: `ThresholdMatrixCard` displays active line's effective rate thresholds and renders a "Kustom" badge when either rate override is set.

---

### Task 1: Backend Database Schema Migration & Model Updates

**Files:**
- Modify: `services/api/src/db/models.py`
- Modify: `services/api/src/main.py`
- Create: `services/api/tests/test_line_migration.py`

**Interfaces:**
- Consumes: `services.api.src.db.models.Line`, `services.api.src.main.init_db`
- Produces:
  - `Line.rate_warning_threshold: Mapped[float | None]`
  - `Line.rate_critical_threshold: Mapped[float | None]`
  - SQLite auto-migration in `init_db(target_engine=None)` adding missing columns to `lines` table

- [ ] **Step 1: Write the failing test for Line migration**

Create `services/api/tests/test_line_migration.py`:
```python
import sqlite3
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from services.api.src.db.models import Base, Line
from services.api.src.main import init_db


def test_line_model_has_threshold_columns():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        line = Line(
            id="line-test",
            name="Test Line",
            daily_target=50000,
            rate_warning_threshold=125.0,
            rate_critical_threshold=105.0,
        )
        session.add(line)
        session.commit()

        queried = session.get(Line, "line-test")
        assert queried is not None
        assert queried.rate_warning_threshold == 125.0
        assert queried.rate_critical_threshold == 105.0


def test_init_db_migrates_existing_lines_table(tmp_path):
    db_file = tmp_path / "test_migration.db"
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    # Create legacy lines table without threshold columns
    cursor.execute("""
        CREATE TABLE lines (
            id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            daily_target INTEGER NOT NULL DEFAULT 60000,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            video_url VARCHAR(255),
            line_coords VARCHAR(100),
            line_direction VARCHAR(20) DEFAULT 'down',
            created_at DATETIME
        )
    """)
    cursor.execute(
        "INSERT INTO lines (id, name, daily_target, is_active) VALUES ('line-legacy', 'Legacy Line', 60000, 1)"
    )
    conn.commit()
    conn.close()

    # Run init_db with engine pointing to this db
    engine = create_engine(f"sqlite:///{db_file}")
    init_db(target_engine=engine)

    # Verify columns were added and legacy row is readable
    with Session(engine) as session:
        line = session.get(Line, "line-legacy")
        assert line is not None
        assert line.rate_warning_threshold is None
        assert line.rate_critical_threshold is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest services/api/tests/test_line_migration.py -v`
Expected: FAIL (`rate_warning_threshold` is an invalid keyword argument for Line)

- [ ] **Step 3: Update `Line` model in `services/api/src/db/models.py` and `init_db` in `services/api/src/main.py`**

In `services/api/src/db/models.py`:
Add `rate_warning_threshold` and `rate_critical_threshold` to `Line`:
```python
    rate_warning_threshold: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    rate_critical_threshold: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
```

In `services/api/src/main.py`:
In `init_db(target_engine=None)` after table creation:
```python
        # Check and migrate columns on lines table
        line_cols = [
            row[1]
            for row in connection.execute(text("PRAGMA table_info(lines)")).fetchall()
        ]
        if line_cols and "rate_warning_threshold" not in line_cols:
            connection.execute(
                text("ALTER TABLE lines ADD COLUMN rate_warning_threshold REAL NULL")
            )
        if line_cols and "rate_critical_threshold" not in line_cols:
            connection.execute(
                text("ALTER TABLE lines ADD COLUMN rate_critical_threshold REAL NULL")
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest services/api/tests/test_line_migration.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit changes**

```bash
git add services/api/src/db/models.py services/api/src/main.py services/api/tests/test_line_migration.py
git commit -m "feat(db): add rate threshold columns and sqlite migration for Line model"
```

---

### Task 2: Shared Contracts & Lines API Validation and Endpoints

**Files:**
- Modify: `shared/contracts.py`
- Modify: `services/api/src/api/lines.py`
- Create: `services/api/tests/test_lines_thresholds_api.py`

**Interfaces:**
- Consumes: `services.api.src.db.models.Line`, `DEFAULT_RATE_WARNING = 130.0`, `DEFAULT_RATE_CRITICAL = 110.0`
- Produces:
  - `LineCreatePayload` with optional `rate_warning_threshold: float | None`, `rate_critical_threshold: float | None`
  - `LineUpdatePayload` with optional `rate_warning_threshold: float | None`, `rate_critical_threshold: float | None`
  - Validation: thresholds must be `> 0`, and when both provided, `rate_critical_threshold < rate_warning_threshold`
  - `LineDetailDTO` & `LineStatusDTO` include:
    - `rate_warning_threshold: float | None`
    - `rate_critical_threshold: float | None`
    - `effective_rate_warning: float`
    - `effective_rate_critical: float`
  - Endpoints:
    - `GET /api/v1/lines`
    - `POST /api/v1/lines`
    - `GET /api/v1/lines/{line_id}`
    - `PUT /api/v1/lines/{line_id}`

- [ ] **Step 1: Write the failing tests for Line threshold validation and endpoints**

Create `services/api/tests/test_lines_thresholds_api.py`:
```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api.src.main import app
from services.api.src.db.session import get_db
from services.api.src.db.models import Base, Line
from services.api.src.api.auth import require_role


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        with TestingSession() as session:
            yield session

    # Bypass auth for testing lines API
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_role(["admin"])] = lambda: {"username": "admin", "role": "admin"}
    app.dependency_overrides[require_role(["admin", "operator"])] = lambda: {"username": "operator", "role": "operator"}

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_create_line_with_custom_thresholds(client: TestClient):
    payload = {
        "id": "line-custom-1",
        "name": "Custom Line 1",
        "daily_target": 50000,
        "rate_warning_threshold": 125.0,
        "rate_critical_threshold": 100.0,
    }
    res = client.post("/api/v1/lines", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["rate_warning_threshold"] == 125.0
    assert data["rate_critical_threshold"] == 100.0
    assert data["effective_rate_warning"] == 125.0
    assert data["effective_rate_critical"] == 100.0


def test_create_line_default_thresholds(client: TestClient):
    payload = {
        "id": "line-default-1",
        "name": "Default Line 1",
        "daily_target": 50000,
    }
    res = client.post("/api/v1/lines", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["rate_warning_threshold"] is None
    assert data["rate_critical_threshold"] is None
    assert data["effective_rate_warning"] == 130.0
    assert data["effective_rate_critical"] == 110.0


def test_create_line_validation_fails_when_critical_greater_or_equal_warning(client: TestClient):
    payload = {
        "id": "line-invalid",
        "name": "Invalid Line",
        "daily_target": 50000,
        "rate_warning_threshold": 100.0,
        "rate_critical_threshold": 120.0,
    }
    res = client.post("/api/v1/lines", json=payload)
    assert res.status_code == 422


def test_create_line_validation_fails_for_non_positive_threshold(client: TestClient):
    payload = {
        "id": "line-invalid-pos",
        "name": "Invalid Non-Positive",
        "daily_target": 50000,
        "rate_warning_threshold": -10.0,
    }
    res = client.post("/api/v1/lines", json=payload)
    assert res.status_code == 422


def test_update_line_thresholds_and_reset_to_null(client: TestClient):
    # First create line
    create_res = client.post("/api/v1/lines", json={
        "id": "line-update-1",
        "name": "Update Line",
        "daily_target": 50000,
    })
    assert create_res.status_code == 201

    # Update with custom thresholds
    update_res = client.put("/api/v1/lines/line-update-1", json={
        "rate_warning_threshold": 140.0,
        "rate_critical_threshold": 120.0,
    })
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["rate_warning_threshold"] == 140.0
    assert updated["rate_critical_threshold"] == 120.0
    assert updated["effective_rate_warning"] == 140.0
    assert updated["effective_rate_critical"] == 120.0

    # Reset back to null (inherit system default)
    reset_res = client.put("/api/v1/lines/line-update-1", json={
        "rate_warning_threshold": None,
        "rate_critical_threshold": None,
    })
    assert reset_res.status_code == 200
    reset_data = reset_res.json()
    assert reset_data["rate_warning_threshold"] is None
    assert reset_data["rate_critical_threshold"] is None
    assert reset_data["effective_rate_warning"] == 130.0
    assert reset_data["effective_rate_critical"] == 110.0


def test_get_lines_includes_effective_thresholds(client: TestClient):
    client.post("/api/v1/lines", json={
        "id": "line-list-1",
        "name": "List Line 1",
        "daily_target": 50000,
        "rate_warning_threshold": 150.0,
        "rate_critical_threshold": 125.0,
    })
    res = client.get("/api/v1/lines")
    assert res.status_code == 200
    lines = res.json()
    match = next(l for l in lines if l["id"] == "line-list-1")
    assert match["rate_warning_threshold"] == 150.0
    assert match["rate_critical_threshold"] == 125.0
    assert match["effective_rate_warning"] == 150.0
    assert match["effective_rate_critical"] == 125.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest services/api/tests/test_lines_thresholds_api.py -v`
Expected: FAIL (`rate_warning_threshold` missing from DTO or 422 extra field forbidden)

- [ ] **Step 3: Update contracts and lines API**

In `shared/contracts.py`:
Update `LineConfigDTO`:
```python
class LineConfigDTO(BaseModel):
    id: str
    name: str
    daily_target: int = 60000
    is_active: bool = True
    video_url: str | None = None
    line_coords: str | None = None
    line_direction: str = "down"
    rate_warning_threshold: float | None = None
    rate_critical_threshold: float | None = None
```

In `services/api/src/api/lines.py`:
1. Define constants at top:
```python
DEFAULT_RATE_WARNING = 130.0
DEFAULT_RATE_CRITICAL = 110.0
```
2. Update `LineCreatePayload` and `LineUpdatePayload` with threshold fields and Pydantic validator:
```python
class LineCreatePayload(BaseModel):
    id: str
    name: str
    daily_target: int = 60000
    video_url: str | None = None
    line_coords: str | None = None
    line_direction: str = "down"
    rate_warning_threshold: float | None = None
    rate_critical_threshold: float | None = None

    @model_validator(mode="after")
    def validate_thresholds(self):
        w = self.rate_warning_threshold
        c = self.rate_critical_threshold
        if w is not None and w <= 0:
            raise ValueError("rate_warning_threshold must be greater than 0")
        if c is not None and c <= 0:
            raise ValueError("rate_critical_threshold must be greater than 0")
        if w is not None and c is not None and c >= w:
            raise ValueError("rate_critical_threshold must be strictly less than rate_warning_threshold")
        return self


class LineUpdatePayload(BaseModel):
    name: str | None = None
    daily_target: int | None = None
    is_active: bool | None = None
    video_url: str | None = None
    line_coords: str | None = None
    line_direction: str | None = None
    rate_warning_threshold: float | None = None
    rate_critical_threshold: float | None = None

    @model_validator(mode="after")
    def validate_thresholds(self):
        w = self.rate_warning_threshold
        c = self.rate_critical_threshold
        if w is not None and w <= 0:
            raise ValueError("rate_warning_threshold must be greater than 0")
        if c is not None and c <= 0:
            raise ValueError("rate_critical_threshold must be greater than 0")
        if w is not None and c is not None and c >= w:
            raise ValueError("rate_critical_threshold must be strictly less than rate_warning_threshold")
        return self
```
3. Update `LineDetailDTO` and `LineStatusDTO`:
```python
class LineDetailDTO(BaseModel):
    id: str
    name: str
    daily_target: int
    is_active: bool
    video_url: str | None
    line_coords: str | None
    line_direction: str
    rate_warning_threshold: float | None = None
    rate_critical_threshold: float | None = None
    effective_rate_warning: float = DEFAULT_RATE_WARNING
    effective_rate_critical: float = DEFAULT_RATE_CRITICAL
```
Add helper function to construct `LineDetailDTO` from a `Line` ORM model:
```python
def line_to_detail_dto(line: Line) -> LineDetailDTO:
    eff_warning = (
        line.rate_warning_threshold
        if line.rate_warning_threshold is not None
        else DEFAULT_RATE_WARNING
    )
    eff_critical = (
        line.rate_critical_threshold
        if line.rate_critical_threshold is not None
        else DEFAULT_RATE_CRITICAL
    )
    return LineDetailDTO(
        id=line.id,
        name=line.name,
        daily_target=line.daily_target,
        is_active=line.is_active,
        video_url=line.video_url,
        line_coords=line.line_coords,
        line_direction=line.line_direction,
        rate_warning_threshold=line.rate_warning_threshold,
        rate_critical_threshold=line.rate_critical_threshold,
        effective_rate_warning=eff_warning,
        effective_rate_critical=eff_critical,
    )
```
And update `LineStatusDTO` similarly to include `rate_warning_threshold`, `rate_critical_threshold`, `effective_rate_warning`, and `effective_rate_critical`.
4. In `create_line`, `update_line`, `get_lines`, and `get_line`, use the helper and persist `rate_warning_threshold` and `rate_critical_threshold`.
Note: In `update_line`, use `exclude_unset=True` when checking which fields are provided so passing explicit `None` properly sets the column to `None`.
```python
    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(line, field, val)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest services/api/tests/test_lines_thresholds_api.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit changes**

```bash
git add shared/contracts.py services/api/src/api/lines.py services/api/tests/test_lines_thresholds_api.py
git commit -m "feat(api): add line rate threshold payloads, validators, and effective calculation"
```

---

### Task 3: Alarm Evaluation Engine with Line Overrides & Sync Integration

**Files:**
- Modify: `services/api/src/services/alarms.py`
- Modify: `services/api/src/api/sync.py`
- Modify: `services/api/tests/test_alarm_evaluator.py`

**Interfaces:**
- Consumes: `services.api.src.db.models.Line`, `services.api.src.db.models.Alarm`
- Produces:
  - `AlarmEvaluator.evaluate_rate(line_id: str, rate_per_min: float, warning_threshold: float | None = None, critical_threshold: float | None = None) -> Alarm | None`
  - Constants: `DEFAULT_RATE_WARNING = 130.0`, `DEFAULT_RATE_CRITICAL = 110.0`
  - Auto-resolution of open `LOW_RATE` alarms when `rate_per_min >= effective_warning`

- [ ] **Step 1: Write the failing tests in `test_alarm_evaluator.py`**

Add tests to `services/api/tests/test_alarm_evaluator.py`:
```python
def test_alarm_evaluator_uses_custom_line_thresholds(db_session: Session):
    evaluator = AlarmEvaluator(db=db_session)
    # Line custom threshold: warning 140, critical 120
    # A rate of 125 is below warning 140 -> should trigger WARNING
    alarm = evaluator.evaluate_rate(
        line_id="customLine",
        rate_per_min=125.0,
        warning_threshold=140.0,
        critical_threshold=120.0,
    )
    assert alarm is not None
    assert alarm.severity == "WARNING"

    # A rate of 115 is below critical 120 -> should trigger CRITICAL
    alarm_crit = evaluator.evaluate_rate(
        line_id="customLine2",
        rate_per_min=115.0,
        warning_threshold=140.0,
        critical_threshold=120.0,
    )
    assert alarm_crit is not None
    assert alarm_crit.severity == "CRITICAL"


def test_alarm_evaluator_auto_resolves_low_rate_on_recovery(db_session: Session):
    evaluator = AlarmEvaluator(db=db_session)

    # 1. Trigger WARNING alarm at 120.0 (default warning 130)
    alarm = evaluator.evaluate_rate(line_id="lineRecover", rate_per_min=120.0)
    assert alarm is not None
    assert alarm.status == "OPEN"

    # 2. Rate recovers to 135.0 (>= 130.0)
    recovered_alarm = evaluator.evaluate_rate(line_id="lineRecover", rate_per_min=135.0)
    assert recovered_alarm is None

    # Verify existing DB alarm is now RESOLVED
    saved = db_session.query(Alarm).filter_by(line_id="lineRecover", alarm_type="LOW_RATE").first()
    assert saved is not None
    assert saved.status == "RESOLVED"
    assert saved.resolved_at is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest services/api/tests/test_alarm_evaluator.py -k "custom_line_thresholds or auto_resolves" -v`
Expected: FAIL (evaluate_rate got unexpected keyword arguments or alarm not resolved)

- [ ] **Step 3: Update `services/api/src/services/alarms.py` and `services/api/src/api/sync.py`**

In `services/api/src/services/alarms.py`:
```python
DEFAULT_RATE_WARNING = 130.0
DEFAULT_RATE_CRITICAL = 110.0
```
Update `evaluate_rate`:
```python
    def evaluate_rate(
        self,
        line_id: str,
        rate_per_min: float,
        warning_threshold: float | None = None,
        critical_threshold: float | None = None,
    ) -> Alarm | None:
        """Evaluate line production rate against warning/critical thresholds.

        Uses line-specific overrides when provided, falling back to system defaults
        (DEFAULT_RATE_WARNING = 130.0, DEFAULT_RATE_CRITICAL = 110.0).

        When rate returns to normal (>= warning threshold), any OPEN LOW_RATE alarm
        for this line is auto-resolved.
        """
        warning = warning_threshold if warning_threshold is not None else DEFAULT_RATE_WARNING
        critical = critical_threshold if critical_threshold is not None else DEFAULT_RATE_CRITICAL

        if rate_per_min < critical:
            severity = "CRITICAL"
        elif rate_per_min < warning:
            severity = "WARNING"
        else:
            # Auto-resolve existing open LOW_RATE alarm for this line if present
            open_alarm = (
                self.db.query(Alarm)
                .filter_by(line_id=line_id, alarm_type="LOW_RATE", status="OPEN")
                .first()
            )
            if open_alarm is not None:
                open_alarm.status = "RESOLVED"
                open_alarm.resolved_at = datetime.now(timezone.utc)
                self.db.commit()
            return None

        message = f"Production rate fell to {rate_per_min:.1f} birds/min"
        return self._record_or_update_alarm(
            line_id=line_id,
            alarm_type="LOW_RATE",
            severity=severity,
            message=message,
        )
```

In `services/api/src/api/sync.py`:
Import `Line` from `services.api.src.db.models`:
In `sync_data` route where `evaluate_rate` is called:
```python
        line = session.get(Line, payload.line_id)
        w_thresh = line.rate_warning_threshold if line else None
        c_thresh = line.rate_critical_threshold if line else None

        for agg in payload.aggregates:
            alarm = evaluator.evaluate_rate(
                payload.line_id,
                agg.rate_per_min,
                warning_threshold=w_thresh,
                critical_threshold=c_thresh,
            )
            if alarm is not None:
                broadcast_line_update(
                    payload.line_id,
                    "alarm",
                    {
                        "type": alarm.alarm_type,
                        "severity": alarm.severity,
                        "msg": alarm.message,
                    },
                )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest services/api/tests/test_alarm_evaluator.py -v`
Expected: PASS (all tests pass)

- [ ] **Step 5: Commit changes**

```bash
git add services/api/src/services/alarms.py services/api/src/api/sync.py services/api/tests/test_alarm_evaluator.py
git commit -m "feat(alarms): support per-line rate thresholds and auto-resolve on recovery"
```

---

### Task 4: Frontend Types & Line Settings Page Threshold Management

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/features/settings/pages/PengaturanPage.tsx`
- Create: `frontend/src/features/settings/pages/__tests__/PengaturanPage.test.tsx`

**Interfaces:**
- Consumes: `Line`, `CreateLinePayload`, `UpdateLinePayload` from `frontend/src/types`
- Produces:
  - Extended `Line` type with `rate_warning_threshold`, `rate_critical_threshold`, `effective_rate_warning`, `effective_rate_critical`
  - UI inputs in `PengaturanPage` for:
    - Ambang Batas Kecepatan Peringatan (Warning)
    - Ambang Batas Kecepatan Kritis (Critical)
    - "Gunakan Standar Sistem" action button
    - Form validation: values > 0, critical < warning if both provided
    - Save action submitting `rate_warning_threshold: value ? Number(value) : null`

- [ ] **Step 1: Write the failing test for `PengaturanPage` threshold settings**

Create `frontend/src/features/settings/pages/__tests__/PengaturanPage.test.tsx`:
```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import PengaturanPage from "../PengaturanPage";

const mockUpdateLine = vi.fn();
const mockCreateLine = vi.fn();

const defaultLine = {
  id: "line-1",
  name: "Lini Konveyor 1",
  daily_target: 60000,
  is_active: true,
  video_url: "",
  line_coords: "0,240,640,240",
  line_direction: "down",
  rate_warning_threshold: 135.0,
  rate_critical_threshold: 115.0,
  effective_rate_warning: 135.0,
  effective_rate_critical: 115.0,
};

vi.mock("@/context/AppContext", () => ({
  useAppContext: () => ({
    currentLineId: "line-1",
    lines: [defaultLine],
    isConnected: true,
    updateLine: mockUpdateLine,
    createLine: mockCreateLine,
  }),
}));

vi.mock("@/components/layout/PageHeader", () => ({
  PageHeader: ({ title, description }: any) => (
    <div>
      <h1>{title}</h1>
      <p>{description}</p>
    </div>
  ),
}));

vi.mock("@/components/layout/LineSelector", () => ({
  LineSelector: () => <div data-testid="line-selector" />,
}));

describe("PengaturanPage Thresholds", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders threshold inputs with active line custom values", () => {
    render(<PengaturanPage />);
    const warningInput = screen.getByLabelText(/Peringatan.*Warning/i) as HTMLInputElement;
    const criticalInput = screen.getByLabelText(/Kritis.*Critical/i) as HTMLInputElement;

    expect(warningInput).toBeDefined();
    expect(criticalInput).toBeDefined();
    expect(warningInput.value).toBe("135");
    expect(criticalInput.value).toBe("115");
  });

  it("clears inputs when 'Gunakan Standar Sistem' button is clicked", () => {
    render(<PengaturanPage />);
    const warningInput = screen.getByLabelText(/Peringatan.*Warning/i) as HTMLInputElement;
    const criticalInput = screen.getByLabelText(/Kritis.*Critical/i) as HTMLInputElement;
    const resetBtn = screen.getByRole("button", { name: /Gunakan Standar Sistem/i });

    fireEvent.click(resetBtn);
    expect(warningInput.value).toBe("");
    expect(criticalInput.value).toBe("");
  });

  it("shows error if critical threshold is greater than or equal to warning", async () => {
    render(<PengaturanPage />);
    const warningInput = screen.getByLabelText(/Peringatan.*Warning/i) as HTMLInputElement;
    const criticalInput = screen.getByLabelText(/Kritis.*Critical/i) as HTMLInputElement;
    const submitBtn = screen.getByRole("button", { name: /Simpan Konfigurasi/i });

    fireEvent.change(warningInput, { target: { value: "110" } });
    fireEvent.change(criticalInput, { target: { value: "120" } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/Ambang batas kritis harus lebih kecil dari ambang batas peringatan/i)).toBeDefined();
    });
    expect(mockUpdateLine).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test --prefix frontend frontend/src/features/settings/pages/__tests__/PengaturanPage.test.tsx`
Expected: FAIL (Cannot find element with text /Peringatan.*Warning/i)

- [ ] **Step 3: Update `frontend/src/types/index.ts` and `frontend/src/features/settings/pages/PengaturanPage.tsx`**

In `frontend/src/types/index.ts`:
Update `Line`, `CreateLinePayload`, `UpdateLinePayload`:
```typescript
export interface Line {
  id: string;
  name: string;
  daily_target?: number;
  is_active: boolean;
  video_url?: string | null;
  line_coords?: string | null;
  line_direction?: string;
  rate_warning_threshold?: number | null;
  rate_critical_threshold?: number | null;
  effective_rate_warning?: number;
  effective_rate_critical?: number;
}

export interface CreateLinePayload {
  id: string;
  name: string;
  daily_target?: number;
  video_url?: string | null;
  line_coords?: string | null;
  line_direction?: string;
  rate_warning_threshold?: number | null;
  rate_critical_threshold?: number | null;
}

export interface UpdateLinePayload {
  name?: string;
  daily_target?: number;
  is_active?: boolean;
  video_url?: string | null;
  line_coords?: string | null;
  line_direction?: string;
  rate_warning_threshold?: number | null;
  rate_critical_threshold?: number | null;
}
```

In `frontend/src/features/settings/pages/PengaturanPage.tsx`:
1. Add state:
```typescript
  const [rateWarning, setRateWarning] = useState<number | string>(
    currentLine?.rate_warning_threshold ?? ""
  );
  const [rateCritical, setRateCritical] = useState<number | string>(
    currentLine?.rate_critical_threshold ?? ""
  );
```
2. In `useEffect` on `currentLine`:
```typescript
  setRateWarning(currentLine.rate_warning_threshold ?? "");
  setRateCritical(currentLine.rate_critical_threshold ?? "");
```
3. In `handleSave`:
Validate:
```typescript
    const warningVal = rateWarning === "" ? null : Number(rateWarning);
    const criticalVal = rateCritical === "" ? null : Number(rateCritical);

    if (warningVal !== null && (isNaN(warningVal) || warningVal <= 0)) {
      setSaveError("Ambang batas peringatan harus lebih besar dari 0");
      return;
    }
    if (criticalVal !== null && (isNaN(criticalVal) || criticalVal <= 0)) {
      setSaveError("Ambang batas kritis harus lebih besar dari 0");
      return;
    }
    if (warningVal !== null && criticalVal !== null && criticalVal >= warningVal) {
      setSaveError("Ambang batas kritis harus lebih kecil dari ambang batas peringatan");
      return;
    }
```
And in `updateLine` call:
```typescript
      await updateLine(currentLine.id, {
        name: trimmedName,
        daily_target: target,
        video_url: videoUrl.trim() || null,
        line_coords: lineCoords.trim() || null,
        line_direction: lineDirection,
        rate_warning_threshold: warningVal,
        rate_critical_threshold: criticalVal,
      });
```
4. Render UI section in "Konfigurasi Lini Terpilih" form:
```tsx
              <div className="border-t border-slate-100 pt-4 mt-2 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="text-xs font-semibold text-slate-800">
                      Ambang Batas Kecepatan (Speed Thresholds)
                    </h4>
                    <p className="text-[11px] text-slate-400">
                      Kosongkan untuk mengikuti standar sistem (130 /mnt warning, 110 /mnt critical).
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setRateWarning("");
                      setRateCritical("");
                    }}
                    className="text-[11px] text-slate-500 hover:text-slate-800 underline transition-colors cursor-pointer"
                  >
                    Gunakan Standar Sistem
                  </button>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label
                      htmlFor="rate-warning-input"
                      className="text-xs font-medium text-slate-700 block mb-1"
                    >
                      Peringatan / Warning (ekor/menit)
                    </label>
                    <Input
                      id="rate-warning-input"
                      type="number"
                      value={rateWarning}
                      onChange={(e) => setRateWarning(e.target.value === "" ? "" : Number(e.target.value))}
                      placeholder="130.0 (Standar)"
                      min={1}
                      step="any"
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="rate-critical-input"
                      className="text-xs font-medium text-slate-700 block mb-1"
                    >
                      Kritis / Critical (ekor/menit)
                    </label>
                    <Input
                      id="rate-critical-input"
                      type="number"
                      value={rateCritical}
                      onChange={(e) => setRateCritical(e.target.value === "" ? "" : Number(e.target.value))}
                      placeholder="110.0 (Standar)"
                      min={1}
                      step="any"
                    />
                  </div>
                </div>
              </div>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test --prefix frontend frontend/src/features/settings/pages/__tests__/PengaturanPage.test.tsx`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit changes**

```bash
git add frontend/src/types/index.ts frontend/src/features/settings/pages/PengaturanPage.tsx frontend/src/features/settings/pages/__tests__/PengaturanPage.test.tsx
git commit -m "feat(settings): add speed threshold overrides and reset action on line settings page"
```

---

### Task 5: Frontend Live Stream ThresholdMatrixCard Dynamic Overrides & Badge

**Files:**
- Modify: `frontend/src/features/livestream/components/ThresholdMatrixCard.tsx`
- Create: `frontend/src/features/livestream/components/__tests__/ThresholdMatrixCard.test.tsx`

**Interfaces:**
- Consumes: `Line` type, `useAppContext()`
- Produces:
  - `ThresholdMatrixCard({ className, line }: { className?: string; line?: Line })`
  - Dynamic display for "Kecepatan Produksi" thresholds:
    - Warning: `< {effectiveWarning} /mnt`
    - Critical: `< {effectiveCritical} /mnt`
    - Custom badge: `<Badge>Kustom</Badge>` (or "Standar")

- [ ] **Step 1: Write the failing test for `ThresholdMatrixCard`**

Create `frontend/src/features/livestream/components/__tests__/ThresholdMatrixCard.test.tsx`:
```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ThresholdMatrixCard } from "../ThresholdMatrixCard";
import type { Line } from "@/types";

vi.mock("@/context/AppContext", () => ({
  useAppContext: () => ({
    currentLineId: "line-1",
    lines: [
      {
        id: "line-1",
        name: "Lini Konveyor 1",
        is_active: true,
        effective_rate_warning: 130,
        effective_rate_critical: 110,
        rate_warning_threshold: null,
        rate_critical_threshold: null,
      },
    ],
  }),
}));

describe("ThresholdMatrixCard", () => {
  it("renders standard thresholds when active line has no overrides", () => {
    render(<ThresholdMatrixCard />);
    expect(screen.getByText("Matriks Ambang Batas")).toBeDefined();
    expect(screen.getByText("< 130 /mnt")).toBeDefined();
    expect(screen.getByText("< 110 /mnt")).toBeDefined();
    expect(screen.queryByText("Kustom")).toBeNull();
  });

  it("renders custom thresholds and Kustom badge when line has overrides", () => {
    const customLine: Line = {
      id: "line-custom",
      name: "Lini Khusus",
      is_active: true,
      rate_warning_threshold: 145,
      rate_critical_threshold: 120,
      effective_rate_warning: 145,
      effective_rate_critical: 120,
    };

    render(<ThresholdMatrixCard line={customLine} />);
    expect(screen.getByText("< 145 /mnt")).toBeDefined();
    expect(screen.getByText("< 120 /mnt")).toBeDefined();
    expect(screen.getByText("Kustom")).toBeDefined();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test --prefix frontend frontend/src/features/livestream/components/__tests__/ThresholdMatrixCard.test.tsx`
Expected: FAIL (Cannot find custom thresholds or badge)

- [ ] **Step 3: Update `frontend/src/features/livestream/components/ThresholdMatrixCard.tsx`**

Update `ThresholdMatrixCard.tsx`:
1. Accept optional `line?: Line` prop and consume `useAppContext`:
```tsx
import { useAppContext } from "@/context/AppContext";
import { Badge } from "@/components/ui/badge";
import type { Line } from "@/types";

interface ThresholdMatrixCardProps {
  className?: string;
  line?: Line;
}

export function ThresholdMatrixCard({ className = "", line }: ThresholdMatrixCardProps) {
  const { currentLineId, lines } = useAppContext();
  const activeLine = line ?? lines.find((l) => l.id === currentLineId) ?? lines[0];

  const hasCustomOverride =
    activeLine?.rate_warning_threshold != null ||
    activeLine?.rate_critical_threshold != null;

  const effectiveWarning =
    activeLine?.effective_rate_warning ??
    activeLine?.rate_warning_threshold ??
    130;

  const effectiveCritical =
    activeLine?.effective_rate_critical ??
    activeLine?.rate_critical_threshold ??
    110;

  const thresholds = [
    {
      metric: "Kecepatan Produksi",
      warning: `< ${effectiveWarning} /mnt`,
      critical: `< ${effectiveCritical} /mnt`,
      action: "Periksa konveyor & pasokan",
      isCustom: hasCustomOverride,
    },
    {
      metric: "Latensi Pipeline",
      warning: "> 150 ms",
      critical: "> 300 ms",
      action: "Restart engine inferensi",
      isCustom: false,
    },
    {
      metric: "Frame Rate (FPS)",
      warning: "< 10 FPS",
      critical: "< 5 FPS",
      action: "Periksa beban GPU & RTSP",
      isCustom: false,
    },
    {
      metric: "Akurasi Deteksi",
      warning: "< 95%",
      critical: "< 90%",
      action: "Kalibrasi sudut kamera",
      isCustom: false,
    },
  ];
...
```
2. In table row rendering for `Kecepatan Produksi` or when `item.isCustom` is true, render a badge:
```tsx
              <td className="py-2.5 px-3 font-medium text-slate-800">
                <div className="flex items-center gap-1.5">
                  <span>{item.metric}</span>
                  {item.isCustom && (
                    <Badge variant="outline" className="text-[9px] px-1.5 py-0 border-amber-300 bg-amber-50 text-amber-700">
                      Kustom
                    </Badge>
                  )}
                </div>
              </td>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test --prefix frontend frontend/src/features/livestream/components/__tests__/ThresholdMatrixCard.test.tsx`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit changes**

```bash
git add frontend/src/features/livestream/components/ThresholdMatrixCard.tsx frontend/src/features/livestream/components/__tests__/ThresholdMatrixCard.test.tsx
git commit -m "feat(livestream): dynamically render active line rate thresholds with custom badge"
```

---

### Task 6: Full Verification & Integration Sanity Test

**Files:**
- Verification only

- [ ] **Step 1: Run complete backend pytest suite**

Run: `.\.venv\Scripts\python.exe -m pytest -v`
Expected: ALL backend tests pass.

- [ ] **Step 2: Run complete frontend vitest suite**

Run: `npm test --prefix frontend`
Expected: ALL frontend unit & component tests pass.

- [ ] **Step 3: Run frontend typecheck and build**

Run: `npm run build --prefix frontend`
Expected: Successful build with zero TypeScript or Vite errors.

- [ ] **Step 4: Final Git Status Verification & Clean Commit**

Run: `git status`
Expected: Clean working tree.
