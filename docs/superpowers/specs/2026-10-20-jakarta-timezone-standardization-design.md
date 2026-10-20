# Jakarta Local Time (WIB) Standardization Design

## 1. Overview
The CDC Chicken Counting application currently processes and stores timestamps in UTC. However, several parts of the system either assume UTC for calendar-day boundaries (causing a 7-hour discrepancy between 00:00 and 06:59 WIB in Jakarta) or use host-machine local time (which varies between local development and containerized cloud deployments).

This design standardizes the entire application to use Jakarta local time (WIB, UTC+7) for all business calculations, reporting, live preview overlays, and client displays, while keeping internal database storage and synchronization protocols cleanly in UTC.

---

## 2. Goals & Non-Goals

### Goals
- Centralize all timezone operations in a dedicated `packages/shared/time_utils.py` module.
- Fix daily rollup / "today" calculation boundaries in `/summary` and `/lines` so "today" corresponds strictly to Jakarta's calendar day (00:00:00 to 23:59:59 WIB).
- Ensure reports (CSV, Excel, PDF) consistently display timestamps and aggregate interval windows in WIB (+07:00).
- Standardize camera live preview HUD overlays to render current Jakarta time with explicit `WIB` labeling.
- Fix frontend table and chart displays to reliably format timestamps according to Asia/Jakarta time rather than slicing raw ISO strings.
- Maintain full backward compatibility and zero database migration requirement.

### Non-Goals
- Altering internal SQLite database columns or counter outbox sync payloads to store local time instead of UTC (UTC storage remains best practice).
- Introducing third-party heavy timezone dependencies when standard Python library (`zoneinfo`, `datetime`) suffices.

---

## 3. Architecture & Shared Helper

### Shared Helper: `packages/shared/time_utils.py`
A new module in the shared package will serve both the edge counter and API services:

```python
from datetime import datetime, timezone, timedelta
from typing import Tuple
import zoneinfo

try:
    JAKARTA_TZ = zoneinfo.ZoneInfo("Asia/Jakarta")
except Exception:
    # Fallback if tzdata is not installed on stripped OS environments
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

def get_jakarta_today_bounds_utc() -> Tuple[datetime, datetime]:
    """
    Calculate the start and end of the current Jakarta calendar day in UTC.
    Returns:
        (start_utc, end_utc): timezone-aware UTC datetimes.
    """
    now_jkt = now_jakarta()
    jkt_start = datetime(now_jkt.year, now_jkt.month, now_jkt.day, 0, 0, 0, 0, tzinfo=JAKARTA_TZ)
    jkt_end = datetime(now_jkt.year, now_jkt.month, now_jkt.day, 23, 59, 59, 999999, tzinfo=JAKARTA_TZ)
    return jkt_start.astimezone(timezone.utc), jkt_end.astimezone(timezone.utc)

def format_jakarta_display(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format a datetime into a Jakarta-local display string."""
    return to_jakarta(dt).strftime(fmt)
```

---

## 4. Subsystem Implementations

### 4.1 Backend Business Logic
- **`services/api/src/api/summary.py`**:
  - Replace naive UTC midnight calculation with `start_utc, end_utc = get_jakarta_today_bounds_utc()`.
  - Filter `CountRollup1m.window_start >= start_utc` and `<= end_utc` so today's totals match Jakarta day reset.
- **`services/api/src/api/lines.py`**:
  - Replace naive UTC midnight in `get_line_stats` with `start_utc, end_utc = get_jakarta_today_bounds_utc()`.

### 4.2 Reporting & Exports
- **`services/api/src/services/exporter.py`**:
  - Deprecate local `WIB_TZ` constant and import `to_jakarta` and `JAKARTA_TZ` from `shared.time_utils`.
- **`services/api/src/services/pdf_exporter.py`**:
  - Replace `datetime.now()` report generation timestamp with `format_jakarta_display(now_jakarta()) + " WIB"`.
  - In table row generation (`Tabel Rincian`), convert `row.window_start` using `to_jakarta(row.window_start).strftime("%Y-%m-%d %H:%M:%S")`.

### 4.3 Live Preview Overlay
- **`services/api/src/services/preview.py`**:
  - Update HUD timestamp string on frame overlays from `datetime.now().strftime("%Y-%m-%d %H:%M:%S")` to `format_jakarta_display(now_jakarta()) + " WIB"`.

### 4.4 Frontend Report Display
- **`frontend/src/features/reports/pages/LaporanPage.tsx`**:
  - Replace naive string substring slicing (`agg.bucket.split("T")[1].slice(0, 5)`) with timezone-aware formatting:
    `new Date(agg.bucket).toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Jakarta" })`.

---

## 5. Testing & Verification Plan

1. **Unit Tests (`tests/test_time_utils.py`)**:
   - Verify `now_jakarta()` produces aware datetimes with +07:00 offset.
   - Verify `to_jakarta()` correctly handles both UTC-aware and naive timestamps.
   - Verify `get_jakarta_today_bounds_utc()` correctly maps:
     - 00:01 WIB on Oct 20 -> 17:01 UTC on Oct 19.
     - 23:59 WIB on Oct 20 -> 16:59 UTC on Oct 20.
2. **Endpoint Tests (`tests/test_summary_tz.py`)**:
   - Insert records right around the Jakarta midnight transition (e.g. 16:59 UTC and 17:01 UTC) and verify `/summary` aggregates only records falling within the current Jakarta calendar day.
3. **Export Tests**:
   - Verify PDF, CSV, and Excel exports format timestamps in WIB with "+07:00" or explicit "WIB" suffix.
4. **Regression Run**:
   - Execute complete test suite (`pytest`) to verify all 346+ tests continue passing.
