# Design Specification: Dashboard Real Per-Hour Counting Chart

- **Date:** 2026-10-21
- **Topic:** Real Per-Hour Hourly Rate Trend Chart in Overview Dashboard
- **Status:** Approved

---

## 1. Executive Summary & Goals

The poultry counting system dashboard ("Ringkasan Hari Ini") includes an area spline chart labeled **"Tren Penghitungan per Jam"** (Hourly Counting Trend).
Previously:
1. The backend endpoint `GET /api/v1/lines/{line_id}/counts` accepted `granularity="hourly"`, but simply returned raw rows from `CountAggregate` (which are 10-second/1-minute edge batch sync records) rather than calculating true hourly buckets.
2. If `CountAggregate` records were empty or sparse, the chart either displayed an empty state or plotted fragmented minute-by-minute intervals.
3. The X-axis did not represent a standard 24-hour operational timeline (`00:00` to `23:00` in Jakarta Timezone, WIB).

### Goals:
1. **Real Hourly Aggregation:** When querying `GET /api/v1/lines/{line_id}/counts?granularity=hourly`, compute true hourly aggregates. Each bucket represents a 1-hour window (e.g., `08:00–08:59 WIB`) with the exact sum of chickens detected.
2. **Reliable Data Sourcing:** Aggregate directly from `CountEvent` records (the source of truth for all detections), falling back to `CountAggregate` if `CountEvent` has no records.
3. **Fixed 24-Hour Timeline on Frontend:** Standardize `HourlyRateChart.tsx` to display all 24 hours of today (`00:00` to `23:00` WIB). Populate each hour with its true count, or `0` for inactive/future hours.

---

## 2. Architecture & Data Flow

```
+-------------------------------------------------------------+
|                      Edge Counter                           |
|       Detects poultry -> Sends CountEvent / Batches         |
+-------------------------------------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|               Data API: SQLite / PostgreSQL                 |
|   - count_events (ts_utc, line_id, track_id)                |
|   - count_aggregates (window_start, window_end, count)      |
+-------------------------------------------------------------+
                               |
                               v  GET /api/v1/lines/{line_id}/counts?granularity=hourly
+-------------------------------------------------------------+
|                 Backend Aggregation Layer                   |
|   - Resolves Jakarta day bounds [today_start, today_end]    |
|   - Queries CountEvent in range (fallback: CountAggregate)  |
|   - Groups into hourly buckets (WIB, UTC+7)                 |
|   - Returns AggregateItemDTO[] with hour-level buckets      |
+-------------------------------------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                  Frontend: DashboardPage                    |
|   - Polls GET /api/v1/lines/{currentLineId}/counts          |
|   - Passes hourly aggregates to HourlyRateChart             |
|   - Merges into 24-hour slots [00:00, 01:00, ..., 23:00]   |
|   - Renders smooth blue area spline chart via ECharts       |
+-------------------------------------------------------------+
```

---

## 3. Backend Implementation Details

### 3.1 Endpoint `GET /api/v1/lines/{line_id}/counts` (`services/api/src/api/counts.py`)
- **Default Time Bounds:**
  - If `from_time` is `None` and `to_time` is `None` when `granularity == "hourly"`, default the filter range to today's Jakarta day bounds:
    ```python
    today_start_utc, today_end_utc = get_jakarta_today_bounds_utc()
    f_dt = today_start_utc.replace(tzinfo=None)
    t_dt = today_end_utc.replace(tzinfo=None)
    ```
- **Hourly Bucket Calculation:**
  1. Query `CountEvent.ts_utc` within `[f_dt, t_dt]` for `line_id`.
  2. If events are found:
     - Group events by hourly window in Jakarta timezone (`Asia/Jakarta`).
     - For each hour with events, compute:
       - `bucket`: ISO 8601 string for start of that hour in Jakarta timezone (e.g. `2026-10-21T08:00:00+07:00` or UTC equivalent).
       - `count`: count of events in that hour.
       - `rate_per_min`: `round(count / 60.0, 1)`.
       - `status`: `"NORMAL"`.
  3. Fallback:
     - If `CountEvent` has no records in `[f_dt, t_dt]`, query `CountAggregate` within `[f_dt, t_dt]`.
     - Group `CountAggregate.count` by hourly bucket in Jakarta timezone.
     - Compute sum of counts and average rate per minute.
  4. Non-hourly Granularities (`minute`, `daily`):
     - Maintain existing behavior or bucket appropriately without breaking compatibility.

---

## 4. Frontend Implementation Details

### 4.1 Dashboard Overview (`frontend/src/features/overview/pages/DashboardPage.tsx`)
- Continues calling `overviewApi.getCounts(currentLineId, { granularity: "hourly" })` every 10 seconds.
- Passes the received `aggregates` into `<HourlyRateChart data={aggregates} />`.

### 4.2 Chart Component (`frontend/src/features/overview/components/HourlyRateChart.tsx`)
- **24-Hour Timeline Definition:**
  - Fixed X-axis categories:
    ```typescript
    const HOURS_24 = Array.from({ length: 24 }, (_, i) => `${String(i).padStart(2, "0")}:00`);
    ```
- **Bucket Mapping:**
  - Build a lookup map `{ [hourStr: string]: number }` from incoming `data`:
    - For each item `d` in `data`:
      - Extract hour string via `formatBucketHour(d.bucket)`.
      - Normalize to `HH:00` (e.g., `08:00`).
      - Accumulate `count` into the slot.
  - Generate the 24 count values for the series:
    - For each slot in `HOURS_24`: value is `slotMap[slot] || 0`.
- **ECharts Configuration:**
  - `xAxis.data`: `HOURS_24`.
  - `series[0].data`: the 24 numeric count values.
  - Display smooth line with gradient fill (`#2563eb`).
  - Tooltip: `{b}<br /><span style='font-weight:600;'>{c} ekor</span>`.
  - Empty state fallback: Only display empty state if `data` is empty and line is completely inactive; once initialized, the full 24-hour curve displays with 0 baseline for clear visibility.

---

## 5. Edge Cases & Error Handling

1. **New Day Rollover:**
   - At 00:00 WIB, `get_jakarta_today_bounds_utc()` rolls over cleanly. The chart displays 0s for the new day until events arrive.
2. **Timezone Accuracy:**
   - Database stores UTC timestamps (`ts_utc`). Conversion to Jakarta time (+7 hours) ensures poultry counted at 08:30 WIB is placed in bucket `08:00` regardless of server deployment timezone.
3. **Sparse or Missing Hours:**
   - If production runs only from 07:00 to 15:00, hours 00:00-06:00 and 16:00-23:00 cleanly show `0 ekor` on the chart without gaps or breaking the curve.
4. **Offline Line:**
   - If no events or aggregates exist for a selected line today, the chart displays a flat line at 0 or the informative empty state.

---

## 6. Testing & Verification Plan

### Backend Unit & Integration Tests (`services/api/tests/test_counts_api.py`)
1. **Hourly Bucketing Test:**
   - Add multiple `CountEvent`s spread across distinct hours (e.g., 08:15, 08:45, 09:10).
   - Verify `GET /api/v1/lines/{line_id}/counts?granularity=hourly` returns distinct buckets for `08:00` and `09:00` with expected counts (2 and 1).
2. **Fallback to CountAggregate:**
   - Test when `CountEvent` has no records but `CountAggregate` records exist.
3. **Regression Testing:**
   - Run existing suite: `pytest services/api/tests/test_counts_api.py` and `pytest services/api/tests/test_summary_api.py`.

### Frontend Build & Test
1. **Time utility tests:** `npm --prefix frontend run test` (or vitest).
2. **Frontend build validation:** `npm --prefix frontend run build`.
