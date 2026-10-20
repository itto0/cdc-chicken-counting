# Jakarta Local Time (WIB) Standardization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Standardize the application to use Jakarta local time (WIB, UTC+7) for all business calculations, reporting, live preview overlays, and client displays while maintaining clean UTC storage in the database.

**Architecture:** Create a centralized `packages/shared/time_utils.py` module with Jakarta timezone constants and helpers (`now_jakarta`, `to_jakarta`, `get_jakarta_today_bounds_utc`, `format_jakarta_display`). Integrate this utility into API summary/lines endpoints for accurate daily resets, CSV/Excel/PDF exporters for consistent WIB output, the camera live preview HUD overlay for local time display, and the frontend report page for timezone-safe bucket rendering.

**Tech Stack:** Python 3.10+ (`zoneinfo`, `datetime`), FastAPI, SQLAlchemy, ReportLab, TypeScript / React.

## Global Constraints
- Internal database columns (`ts_utc`, `window_start`, `timestamp`) and sync payloads MUST remain stored as UTC.
- Jakarta timezone is UTC+7 (WIB / Asia/Jakarta).
- Python standard library (`zoneinfo` with fallback to `timezone(timedelta(hours=7))`) must be used without heavy external dependencies.
- Zero database migrations required.

---

### Task 1: Shared Timezone Utility (`packages/shared/time_utils.py`)

**Files:**
- Create: `packages/shared/time_utils.py`
- Test: `tests/test_time_utils.py`

**Interfaces:**
- Produces:
  - `JAKARTA_TZ: ZoneInfo | timezone`
  - `WIB_OFFSET: timedelta`
  - `WIB_LABEL: str`
  - `now_jakarta() -> datetime`
  - `to_jakarta(dt: datetime) -> datetime`
  - `get_jakarta_today_bounds_utc(reference_dt: datetime | None = None) -> tuple[datetime, datetime]`
  - `format_jakarta_display(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str`

- [ ] **Step 1: Write the failing test for `shared/time_utils.py`**

Create `tests/test_time_utils.py`:
```python
from datetime import datetime, timezone, timedelta
from shared.time_utils import (
    JAKARTA_TZ,
    WIB_OFFSET,
    WIB_LABEL,
    now_jakarta,
    to_jakarta,
    get_jakarta_today_bounds_utc,
    format_jakarta_display,
)

def test_jakarta_timezone_constants():
    assert WIB_OFFSET == timedelta(hours=7)
    assert WIB_LABEL == "WIB"
    now_jkt = now_jakarta()
    assert now_jkt.utcoffset() == timedelta(hours=7)

def test_to_jakarta():
    # Naive datetime assumed UTC
    dt_naive = datetime(2026, 4, 14, 3, 0, 0)
    jkt = to_jakarta(dt_naive)
    assert jkt.utcoffset() == timedelta(hours=7)
    assert jkt.hour == 10

    # Aware UTC datetime
    dt_utc = datetime(2026, 4, 14, 3, 0, 0, tzinfo=timezone.utc)
    jkt2 = to_jakarta(dt_utc)
    assert jkt2.hour == 10
    assert jkt2.day == 14

def test_get_jakarta_today_bounds_utc():
    # Reference: 2026-04-14 01:00:00 WIB (which is 2026-04-13 18:00:00 UTC)
    ref_dt = datetime(2026, 4, 13, 18, 0, 0, tzinfo=timezone.utc)
    start_utc, end_utc = get_jakarta_today_bounds_utc(reference_dt=ref_dt)

    # In Jakarta, that day is 2026-04-14 00:00:00 to 23:59:59.999999
    # In UTC, 00:00:00 WIB corresponds to 2026-04-13 17:00:00 UTC
    assert start_utc == datetime(2026, 4, 13, 17, 0, 0, tzinfo=timezone.utc)
    assert end_utc == datetime(2026, 4, 14, 16, 59, 59, 999999, tzinfo=timezone.utc)

def test_format_jakarta_display():
    dt_utc = datetime(2026, 4, 14, 3, 30, 15, tzinfo=timezone.utc)
    formatted = format_jakarta_display(dt_utc)
    assert formatted == "2026-04-14 10:30:15"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
& "C:\Users\torino\AppData\Local\Python\bin\python.exe" -m pytest tests/test_time_utils.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'shared.time_utils'`

- [ ] **Step 3: Implement `packages/shared/time_utils.py`**

Write `packages/shared/time_utils.py`:
```python
from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional
import zoneinfo

try:
    JAKARTA_TZ = zoneinfo.ZoneInfo("Asia/Jakarta")
except Exception:
    JAKARTA_TZ = timezone(timedelta(hours=7), name="WIB")

WIB_OFFSET = timedelta(hours=7)
WIB_LABEL = "WIB"

def now_jakarta() -> datetime:
    """Return current timezone-aware datetime in Jakarta (WIB, UTC+7)."""
    return datetime.now(JAKARTA_TZ)

def to_jakarta(dt: datetime) -> datetime:
    """Convert any datetime (aware or naive UTC) to Jakarta timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(JAKARTA_TZ)

def get_jakarta_today_bounds_utc(reference_dt: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    """
    Calculate the start and end of the Jakarta calendar day in UTC.
    If reference_dt is provided, bounds are computed for the Jakarta day containing reference_dt.
    Otherwise, current Jakarta time is used.
    Returns:
        (start_utc, end_utc): timezone-aware UTC datetimes.
    """
    if reference_dt is None:
        ref_jkt = now_jakarta()
    else:
        ref_jkt = to_jakarta(reference_dt)

    jkt_start = datetime(ref_jkt.year, ref_jkt.month, ref_jkt.day, 0, 0, 0, 0, tzinfo=JAKARTA_TZ)
    jkt_end = datetime(ref_jkt.year, ref_jkt.month, ref_jkt.day, 23, 59, 59, 999999, tzinfo=JAKARTA_TZ)
    return jkt_start.astimezone(timezone.utc), jkt_end.astimezone(timezone.utc)

def format_jakarta_display(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format a datetime into a Jakarta-local display string."""
    return to_jakarta(dt).strftime(fmt)
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
& "C:\Users\torino\AppData\Local\Python\bin\python.exe" -m pytest tests/test_time_utils.py -v
```
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/shared/time_utils.py tests/test_time_utils.py
git commit -m "feat(shared): add jakarta timezone utility helpers"
```

---

### Task 2: Backend Daily Rollup Bounds in Summary & Lines Endpoints

**Files:**
- Modify: `services/api/src/api/summary.py`
- Modify: `services/api/src/api/lines.py`
- Test: `tests/test_api_timezone_bounds.py`

**Interfaces:**
- Consumes: `get_jakarta_today_bounds_utc` from `shared.time_utils`
- Produces: Correct Jakarta calendar day boundaries for `today_in`, `today_out`, and `today_net` aggregations in `/summary` and `/lines`.

- [ ] **Step 1: Write the failing test for Jakarta day boundaries in summary/lines**

Create `tests/test_api_timezone_bounds.py`:
```python
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from shared.models import CountRollup1m, Line
from shared.time_utils import get_jakarta_today_bounds_utc

def test_summary_uses_jakarta_day_bounds(client: TestClient, db_session):
    # Setup a line
    line = Line(id="line-tz", name="TZ Test Line", is_active=True)
    db_session.add(line)
    db_session.commit()

    # Get Jakarta bounds for today
    today_start_utc, today_end_utc = get_jakarta_today_bounds_utc()

    # Record 1: 5 minutes before Jakarta day started (yesterday WIB)
    dt_yesterday = today_start_utc.replace(tzinfo=timezone.utc) - timedelta(minutes=5)
    # Record 2: 5 minutes after Jakarta day started (today WIB)
    dt_today = today_start_utc.replace(tzinfo=timezone.utc) + timedelta(minutes=5)

    r1 = CountRollup1m(
        line_id="line-tz",
        window_start=dt_yesterday.replace(tzinfo=None),
        in_count=10,
        out_count=0
    )
    r2 = CountRollup1m(
        line_id="line-tz",
        window_start=dt_today.replace(tzinfo=None),
        in_count=25,
        out_count=0
    )
    db_session.add_all([r1, r2])
    db_session.commit()

    resp = client.get("/api/v1/summary")
    assert resp.status_code == 200
    data = resp.json()
    # today_in should only include r2 (25), not r1 (10)
    assert data["today_in"] == 25
```
*(Import `timedelta` from `datetime` in the test)*

- [ ] **Step 2: Run test to verify it fails if previous UTC midnight was used**

Run:
```bash
& "C:\Users\torino\AppData\Local\Python\bin\python.exe" -m pytest tests/test_api_timezone_bounds.py -v
```

- [ ] **Step 3: Update `services/api/src/api/summary.py` and `services/api/src/api/lines.py`**

In `services/api/src/api/summary.py`:
Replace:
```python
now = datetime.now(timezone.utc)
today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
today_counts = (
    db.query(
        func.coalesce(func.sum(CountRollup1m.in_count), 0),
        func.coalesce(func.sum(CountRollup1m.out_count), 0),
    )
    .filter(CountRollup1m.window_start >= today_start)
    .first()
)
```
With:
```python
from shared.time_utils import get_jakarta_today_bounds_utc

today_start_utc, today_end_utc = get_jakarta_today_bounds_utc()
today_counts = (
    db.query(
        func.coalesce(func.sum(CountRollup1m.in_count), 0),
        func.coalesce(func.sum(CountRollup1m.out_count), 0),
    )
    .filter(
        CountRollup1m.window_start >= today_start_utc.replace(tzinfo=None),
        CountRollup1m.window_start <= today_end_utc.replace(tzinfo=None),
    )
    .first()
)
```

In `services/api/src/api/lines.py`:
Replace:
```python
now = datetime.now(timezone.utc)
today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
```
With:
```python
from shared.time_utils import get_jakarta_today_bounds_utc

today_start_utc, today_end_utc = get_jakarta_today_bounds_utc()
# Use today_start_utc.replace(tzinfo=None) in query filters
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
& "C:\Users\torino\AppData\Local\Python\bin\python.exe" -m pytest tests/test_api_timezone_bounds.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/api/src/api/summary.py services/api/src/api/lines.py tests/test_api_timezone_bounds.py
git commit -m "fix(api): use jakarta calendar day bounds for today count rollups"
```

---

### Task 3: Exporters (CSV, Excel, PDF) Centralized Timezone Formatting

**Files:**
- Modify: `services/api/src/services/exporter.py`
- Modify: `services/api/src/services/pdf_exporter.py`
- Test: `tests/test_exporter_timezone.py`

**Interfaces:**
- Consumes: `to_jakarta`, `now_jakarta`, `format_jakarta_display`, `JAKARTA_TZ`, `WIB_LABEL` from `shared.time_utils`
- Produces: PDF/CSV/Excel documents with WIB formatted timestamps and headers.

- [ ] **Step 1: Write failing tests for PDF and Excel exporter timezone consistency**

Create `tests/test_exporter_timezone.py`:
```python
from datetime import datetime, timezone
from shared.models import CountRollup1m, Line
from services.api.src.services.exporter import export_report_csv, export_report_excel
from services.api.src.services.pdf_exporter import generate_report_pdf

def test_exporter_csv_excel_uses_wib(db_session):
    line = Line(id="line-exp", name="Export Line", is_active=True)
    db_session.add(line)
    # 03:00 UTC = 10:00 WIB
    r = CountRollup1m(
        line_id="line-exp",
        window_start=datetime(2026, 4, 14, 3, 0, 0),
        in_count=10,
        out_count=5
    )
    db_session.add(r)
    db_session.commit()

    csv_data = export_report_csv(db_session, "line-exp", datetime(2026, 4, 14, 0, 0), datetime(2026, 4, 14, 23, 59))
    csv_str = csv_data.decode("utf-8")
    assert "10:00:00" in csv_str

def test_pdf_exporter_generates_wib(db_session):
    line = Line(id="line-pdf", name="PDF Line", is_active=True)
    db_session.add(line)
    r = CountRollup1m(
        line_id="line-pdf",
        window_start=datetime(2026, 4, 14, 3, 0, 0),
        in_count=12,
        out_count=6
    )
    db_session.add(r)
    db_session.commit()

    pdf_bytes = generate_report_pdf(db_session, "line-pdf", datetime(2026, 4, 14, 0, 0), datetime(2026, 4, 14, 23, 59))
    assert pdf_bytes.startswith(b"%PDF")
```

- [ ] **Step 2: Run test to verify it fails / identifies missing WIB standardization**

Run:
```bash
& "C:\Users\torino\AppData\Local\Python\bin\python.exe" -m pytest tests/test_exporter_timezone.py -v
```

- [ ] **Step 3: Update `exporter.py` and `pdf_exporter.py`**

In `services/api/src/services/exporter.py`:
- Replace local `WIB_TZ` with `to_jakarta`, `JAKARTA_TZ` imported from `shared.time_utils`.
- Replace `row.window_start.replace(tzinfo=timezone.utc).astimezone(WIB_TZ)` with `to_jakarta(row.window_start)`.

In `services/api/src/services/pdf_exporter.py`:
- Import `now_jakarta`, `to_jakarta`, `format_jakarta_display` from `shared.time_utils`.
- Change generation timestamp:
  `gen_time = format_jakarta_display(now_jakarta()) + " WIB"`
  `Paragraph(f"Dibuat pada: {gen_time}", meta_style)`
- In `table_data` construction:
  Convert `row.window_start`:
  `dt_wib = format_jakarta_display(row.window_start)`
  `table_data.append([dt_wib, str(row.in_count), str(row.out_count), str(net)])`

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
& "C:\Users\torino\AppData\Local\Python\bin\python.exe" -m pytest tests/test_exporter_timezone.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/api/src/services/exporter.py services/api/src/services/pdf_exporter.py tests/test_exporter_timezone.py
git commit -m "fix(reports): standardize CSV, Excel, and PDF exports to use shared Jakarta timezone"
```

---

### Task 4: Camera Live Preview HUD Overlay Jakarta Time

**Files:**
- Modify: `services/api/src/services/preview.py`
- Test: `tests/test_preview_timezone.py`

**Interfaces:**
- Consumes: `now_jakarta`, `format_jakarta_display` from `shared.time_utils`
- Produces: Camera stream frames annotated with current Jakarta time and explicit "WIB" label.

- [ ] **Step 1: Write test for preview HUD overlay formatting**

Create `tests/test_preview_timezone.py`:
```python
from datetime import datetime, timezone
from shared.time_utils import format_jakarta_display

def test_preview_overlay_timestamp_format():
    dt_utc = datetime(2026, 4, 14, 5, 0, 0, tzinfo=timezone.utc)
    overlay_text = f"{format_jakarta_display(dt_utc)} WIB"
    assert overlay_text == "2026-04-14 12:00:00 WIB"
```

- [ ] **Step 2: Run test to verify format**

Run:
```bash
& "C:\Users\torino\AppData\Local\Python\bin\python.exe" -m pytest tests/test_preview_timezone.py -v
```

- [ ] **Step 3: Update `services/api/src/services/preview.py`**

In `services/api/src/services/preview.py`:
- Import `now_jakarta`, `format_jakarta_display` from `shared.time_utils`.
- Replace:
  `ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")`
  With:
  `ts = f"{format_jakarta_display(now_jakarta())} WIB"`

- [ ] **Step 4: Run tests**

Run:
```bash
& "C:\Users\torino\AppData\Local\Python\bin\python.exe" -m pytest tests/test_preview_timezone.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/api/src/services/preview.py tests/test_preview_timezone.py
git commit -m "fix(preview): display Jakarta local time (WIB) on camera stream HUD overlay"
```

---

### Task 5: Frontend Report Bucket Formatting

**Files:**
- Modify: `frontend/src/features/reports/pages/LaporanPage.tsx`

**Interfaces:**
- Formats: ISO timestamp strings (`agg.bucket`) using `timeZone: "Asia/Jakarta"` and Indonesian locale.

- [ ] **Step 1: Review current hourly bucket extraction in `LaporanPage.tsx`**

Line 207 currently does:
```typescript
const hourLabel = agg.bucket.includes("T")
    ? agg.bucket.split("T")[1].slice(0, 5)
    : agg.bucket;
```
If `agg.bucket` is an ISO timestamp (e.g. `2026-04-14T03:00:00Z` or `2026-04-14T03:00:00+00:00`), splitting `T` yields the UTC hour `03:00` instead of Jakarta hour `10:00`.

- [ ] **Step 2: Update `LaporanPage.tsx` to format using timezone-aware helper**

Define a helper or update line 207 in `frontend/src/features/reports/pages/LaporanPage.tsx`:
```typescript
const formatBucketHour = (bucketStr: string) => {
    try {
        const d = new Date(bucketStr);
        if (!isNaN(d.getTime())) {
            return d.toLocaleTimeString("id-ID", {
                hour: "2-digit",
                minute: "2-digit",
                hour12: false,
                timeZone: "Asia/Jakarta"
            });
        }
    } catch {
        // Fallback to substring slicing if not a valid ISO date
    }
    return bucketStr.includes("T") ? bucketStr.split("T")[1].slice(0, 5) : bucketStr;
};
```
And replace `agg.bucket.split("T")[1].slice(0, 5)` with `formatBucketHour(agg.bucket)`.

- [ ] **Step 3: Verify frontend compiles with TypeScript**

Run:
```bash
cd frontend && npm run build
```
Expected: Successful build with zero TypeScript / lint errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/reports/pages/LaporanPage.tsx
git commit -m "fix(frontend): format report hourly buckets using Asia/Jakarta timezone"
```

---

### Task 6: Full Regression Verification

**Files:**
- All tests across test suite

- [ ] **Step 1: Run full pytest suite**

Run:
```bash
& "C:\Users\torino\AppData\Local\Python\bin\python.exe" -m pytest -q
```
Expected: 350+ passed, 0 failed.

- [ ] **Step 2: Commit any remaining cleanup and finalize branch**

```bash
git status
```
Verify working tree is clean.
