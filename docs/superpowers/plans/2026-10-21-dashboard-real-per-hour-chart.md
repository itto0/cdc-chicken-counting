# Dashboard Real Per-Hour Chart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement true hourly aggregation in the backend and a standard 24-hour (`00:00`–`23:00` WIB) timeline in the dashboard's "Tren Penghitungan per Jam" chart.

**Architecture:** The backend endpoint `GET /api/v1/lines/{line_id}/counts` will group `CountEvent`s by 1-hour intervals in Jakarta timezone (`Asia/Jakarta`, UTC+7) when `granularity == "hourly"`, falling back to `CountAggregate` if events are empty. The frontend `HourlyRateChart` maps these hourly aggregates onto a fixed 24-hour timeline (`00:00` to `23:00`), displaying actual counts per hour and `0` for inactive or future hours.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, SQLite/PostgreSQL, TypeScript, React, Apache ECharts (`echarts-for-react`), Vitest, Pytest.

## Global Constraints
- Timezone standard is Jakarta Time (`Asia/Jakarta`, WIB, UTC+7). All hourly buckets must be aligned to Jakarta hour starts (`00:00`, `01:00`, ..., `23:00`).
- No regressions on existing `/api/v1/lines/{line_id}/counts` endpoints (including pagination, event queries, and tie-breaker sorting).
- Keep code clean, DRY, and adhere strictly to project patterns without adding unnecessary third-party libraries.

---

### Task 1: Backend Hourly Aggregation in `services/api/src/api/counts.py`

**Files:**
- Modify: `services/api/src/api/counts.py`
- Test: `services/api/tests/test_counts_api.py`

**Interfaces:**
- Consumes:
  - `shared.time_utils.to_jakarta`: `(dt: datetime) -> datetime`
  - `shared.time_utils.get_jakarta_today_bounds_utc`: `(reference_dt: Optional[datetime]) -> Tuple[datetime, datetime]`
  - `services.api.src.db.models.CountEvent`: SQLAlchemy model
  - `services.api.src.db.models.CountAggregate`: SQLAlchemy model
- Produces:
  - `GET /api/v1/lines/{line_id}/counts` with `granularity="hourly"` returning true hourly buckets in `aggregates: List[AggregateItemDTO]`.
  - Supports optional query parameter `period: Optional[str] = Query(None, pattern="^(today|shift|week)$")`.

- [ ] **Step 1: Write failing tests for hourly bucketing and period filtering**

In `services/api/tests/test_counts_api.py`, append tests:

```python
def test_get_line_counts_hourly_aggregation_from_events(counts_client):
    # Test line with events spread across 2 hours in UTC: 08:15, 08:45, and 09:30
    # In Jakarta time (UTC+7): 15:15, 15:45, and 16:30
    db = next(app.dependency_overrides[get_db]())
    db.add(Line(id="line-hourly", name="Line Hourly", daily_target=5000, is_active=True))
    t1 = datetime(2026, 10, 21, 8, 15, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 10, 21, 8, 45, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 10, 21, 9, 30, 0, tzinfo=timezone.utc)
    db.add(CountEvent(line_id="line-hourly", track_id=1, ts_utc=t1, confidence=0.98))
    db.add(CountEvent(line_id="line-hourly", track_id=2, ts_utc=t2, confidence=0.97))
    db.add(CountEvent(line_id="line-hourly", track_id=3, ts_utc=t3, confidence=0.99))
    db.commit()

    from_time = "2026-10-21T08:00:00Z"
    to_time = "2026-10-21T10:00:00Z"
    response = counts_client.get(f"/api/v1/lines/line-hourly/counts?granularity=hourly&from={from_time}&to={to_time}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["aggregates"]) == 2
    # Hour 15:00 WIB has 2 events
    assert data["aggregates"][0]["count"] == 2
    assert "15:00:00" in data["aggregates"][0]["bucket"]
    # Hour 16:00 WIB has 1 event
    assert data["aggregates"][1]["count"] == 1
    assert "16:00:00" in data["aggregates"][1]["bucket"]


def test_get_line_counts_period_today(counts_client):
    response = counts_client.get("/api/v1/lines/line-hourly/counts?granularity=hourly&period=today")
    assert response.status_code == 200
    data = response.json()
    assert "aggregates" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
& "C:\Users\torino\AppData\Local\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe" run --with fastapi --with httpx --with sqlalchemy --with pytest --with pyjwt --with python-dotenv --with opencv-python-headless --with reportlab --with openpyxl pytest services/api/tests/test_counts_api.py::test_get_line_counts_hourly_aggregation_from_events -v
```
Expected: FAIL because `counts.py` does not aggregate `CountEvent` by hour.

- [ ] **Step 3: Implement hourly aggregation and period parameter in `services/api/src/api/counts.py`**

Update `services/api/src/api/counts.py`:
- Import `to_jakarta`, `get_jakarta_today_bounds_utc` from `shared.time_utils`.
- Add `period: Optional[str] = Query(None, pattern="^(today|shift|week)$")` to `get_line_counts`.
- If `period == "today"` and `from_time is None and to_time is None`:
  Resolve Jakarta today UTC bounds and assign to `f_dt` and `t_dt`.
- When `granularity == "hourly"`:
  - Query `CountEvent.ts_utc` where `line_id == line_id` (and bounded by `f_dt` and `t_dt` if present).
  - If events exist, group by Jakarta hour start (`to_jakarta(ts).replace(minute=0, second=0, microsecond=0)`), sum counts, calculate rate per min, and sort ascending.
  - If no events exist, query `CountAggregate` bounded by `f_dt` and `t_dt`, group by Jakarta hour start, sum counts, and average rate per min.
- For other granularities (`minute`, `daily`), keep the direct query on `CountAggregate`.

Exact implementation in `services/api/src/api/counts.py`:
```python
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from services.api.src.db.models import Line, CountEvent, CountAggregate
from services.api.src.db.session import get_db
from services.api.src.api.auth import get_current_user, UserDTO
from shared.time_utils import to_jakarta, get_jakarta_today_bounds_utc

router = APIRouter(prefix="/api/v1/lines", tags=["counts"])


class AggregateItemDTO(BaseModel):
    bucket: str
    count: int
    rate_per_min: float
    status: str


class CountEventDTO(BaseModel):
    id: int
    track_id: int
    ts_utc: str
    confidence: float


class PaginationMeta(BaseModel):
    total: int
    page: int
    limit: int


class LineCountsResponse(BaseModel):
    line_id: str
    aggregates: List[AggregateItemDTO]
    events: List[CountEventDTO]
    pagination: PaginationMeta


def _parse_filter_datetime(dt_str: str, param: str) -> datetime:
    try:
        clean_str = dt_str.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid datetime format for {param}. Expected ISO 8601 format.",
        ) from exc


@router.get("/{line_id}/counts", response_model=LineCountsResponse)
def get_line_counts(
    line_id: str,
    from_time: Optional[str] = Query(None, alias="from"),
    to_time: Optional[str] = Query(None, alias="to"),
    period: Optional[str] = Query(None, pattern="^(today|shift|week)$"),
    granularity: str = Query(default="hourly", pattern="^(minute|hourly|daily)$"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: UserDTO = Depends(get_current_user),
):
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

    f_dt: Optional[datetime] = None
    if from_time is not None:
        f_dt = _parse_filter_datetime(from_time, "from_time")

    t_dt: Optional[datetime] = None
    if to_time is not None:
        t_dt = _parse_filter_datetime(to_time, "to_time")

    if period == "today" and f_dt is None and t_dt is None:
        today_start_utc, today_end_utc = get_jakarta_today_bounds_utc()
        f_dt = today_start_utc.replace(tzinfo=None)
        t_dt = today_end_utc.replace(tzinfo=None)

    aggregates_dto: List[AggregateItemDTO] = []

    if granularity == "hourly":
        # First attempt: aggregate directly from CountEvents
        events_query = select(CountEvent.ts_utc).where(CountEvent.line_id == line_id)
        if f_dt is not None:
            events_query = events_query.where(CountEvent.ts_utc >= f_dt)
        if t_dt is not None:
            events_query = events_query.where(CountEvent.ts_utc <= t_dt)
        events_query = events_query.order_by(CountEvent.ts_utc.asc())
        event_timestamps = db.scalars(events_query).all()

        if event_timestamps:
            hour_counts: dict[datetime, int] = {}
            for ts in event_timestamps:
                jkt_dt = to_jakarta(ts)
                bucket_dt = jkt_dt.replace(minute=0, second=0, microsecond=0)
                hour_counts[bucket_dt] = hour_counts.get(bucket_dt, 0) + 1

            aggregates_dto = [
                AggregateItemDTO(
                    bucket=bucket_dt.isoformat(),
                    count=cnt,
                    rate_per_min=round(cnt / 60.0, 1),
                    status="NORMAL",
                )
                for bucket_dt, cnt in sorted(hour_counts.items(), key=lambda x: x[0])
            ]
        else:
            # Fallback to CountAggregate table if no CountEvents present
            agg_query = select(CountAggregate).where(CountAggregate.line_id == line_id)
            if f_dt is not None:
                agg_query = agg_query.where(CountAggregate.window_start >= f_dt)
            if t_dt is not None:
                agg_query = agg_query.where(CountAggregate.window_start <= t_dt)
            agg_query = agg_query.order_by(CountAggregate.window_start.asc()).limit(500)
            aggs = db.scalars(agg_query).all()

            if aggs:
                hour_agg_counts: dict[datetime, int] = {}
                hour_agg_rates: dict[datetime, list[float]] = {}
                for a in aggs:
                    jkt_dt = to_jakarta(a.window_start)
                    bucket_dt = jkt_dt.replace(minute=0, second=0, microsecond=0)
                    hour_agg_counts[bucket_dt] = hour_agg_counts.get(bucket_dt, 0) + a.count
                    if bucket_dt not in hour_agg_rates:
                        hour_agg_rates[bucket_dt] = []
                    hour_agg_rates[bucket_dt].append(a.rate_per_min)

                aggregates_dto = [
                    AggregateItemDTO(
                        bucket=bucket_dt.isoformat(),
                        count=cnt,
                        rate_per_min=round(sum(hour_agg_rates[bucket_dt]) / len(hour_agg_rates[bucket_dt]), 1)
                        if hour_agg_rates.get(bucket_dt)
                        else round(cnt / 60.0, 1),
                        status="NORMAL",
                    )
                    for bucket_dt, cnt in sorted(hour_agg_counts.items(), key=lambda x: x[0])
                ]
    else:
        # Non-hourly granularities (minute, daily)
        agg_query = select(CountAggregate).where(CountAggregate.line_id == line_id)
        if f_dt is not None:
            agg_query = agg_query.where(CountAggregate.window_start >= f_dt)
        if t_dt is not None:
            agg_query = agg_query.where(CountAggregate.window_start <= t_dt)
        agg_query = agg_query.order_by(CountAggregate.window_start.asc()).limit(500)
        aggs = db.scalars(agg_query).all()

        aggregates_dto = [
            AggregateItemDTO(
                bucket=a.window_start.isoformat(),
                count=a.count,
                rate_per_min=a.rate_per_min,
                status=a.status,
            )
            for a in aggs
        ]

    # Fetch raw events paginated
    events_query = select(CountEvent).where(CountEvent.line_id == line_id)
    if f_dt is not None:
        events_query = events_query.where(CountEvent.ts_utc >= f_dt)
    if t_dt is not None:
        events_query = events_query.where(CountEvent.ts_utc <= t_dt)

    total_events = db.scalar(select(func.count()).select_from(events_query.subquery())) or 0
    offset = (page - 1) * limit
    events = db.scalars(
        events_query.order_by(CountEvent.ts_utc.desc(), CountEvent.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    events_dto = [
        CountEventDTO(
            id=e.id,
            track_id=e.track_id,
            ts_utc=e.ts_utc.isoformat(),
            confidence=round(e.confidence, 3),
        )
        for e in events
    ]

    return LineCountsResponse(
        line_id=line_id,
        aggregates=aggregates_dto,
        events=events_dto,
        pagination=PaginationMeta(total=total_events, page=page, limit=limit),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
& "C:\Users\torino\AppData\Local\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe" run --with fastapi --with httpx --with sqlalchemy --with pytest --with pyjwt --with python-dotenv --with opencv-python-headless --with reportlab --with openpyxl pytest services/api/tests/test_counts_api.py -v
```
Expected: PASS for all tests.

- [ ] **Step 5: Commit**

```bash
git add services/api/src/api/counts.py services/api/tests/test_counts_api.py
git commit -m "feat(api): implement true hourly aggregation and period filtering in counts endpoint"
```

---

### Task 2: Frontend 24-Hour Timeline in `HourlyRateChart` & `DashboardPage`

**Files:**
- Modify: `frontend/src/types/index.ts:84-92`
- Modify: `frontend/src/features/overview/api/overview.api.ts:7-14`
- Modify: `frontend/src/features/overview/pages/DashboardPage.tsx:52-59`
- Modify: `frontend/src/features/overview/components/HourlyRateChart.tsx`
- Test: `frontend/src/features/overview/components/__tests__/HourlyRateChart.test.tsx`

**Interfaces:**
- Consumes:
  - `AggregateItemDTO` from `@/types`
  - `formatBucketHour` from `@/utils/time`
- Produces:
  - `HourlyRateChart` component rendering a fixed 24-hour timeline (`00:00` - `23:00`) with smooth spline curve and area gradient.

- [ ] **Step 1: Write failing unit tests for 24-hour timeline rendering**

In `frontend/src/features/overview/components/__tests__/HourlyRateChart.test.tsx`, add a test to inspect option data passed to ECharts:

```tsx
  it("maps counts onto the 24-hour timeline with zeroes for missing hours", () => {
    let capturedOption: any = null;
    vi.mocked(ReactECharts).mockImplementationOnce(({ option }: any) => {
      capturedOption = option;
      return <div data-testid="echarts-mock" />;
    });

    render(
      <HourlyRateChart
        data={[
          { bucket: "2026-10-21T08:00:00+07:00", count: 250, rate_per_min: 4.2, status: "NORMAL" },
          { bucket: "2026-10-21T09:00:00+07:00", count: 300, rate_per_min: 5.0, status: "NORMAL" },
        ]}
      />
    );

    expect(screen.getByTestId("echarts-mock")).toBeDefined();
    expect(capturedOption).not.toBeNull();
    expect(capturedOption.xAxis.data).toHaveLength(24);
    expect(capturedOption.xAxis.data[0]).toBe("00:00");
    expect(capturedOption.xAxis.data[8]).toBe("08:00");
    expect(capturedOption.xAxis.data[23]).toBe("23:00");

    expect(capturedOption.series[0].data).toHaveLength(24);
    expect(capturedOption.series[0].data[8]).toBe(250);
    expect(capturedOption.series[0].data[9]).toBe(300);
    expect(capturedOption.series[0].data[0]).toBe(0);
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
npm --prefix frontend run test -- src/features/overview/components/__tests__/HourlyRateChart.test.tsx
```
Expected: FAIL because `capturedOption.xAxis.data` has length 2, not 24.

- [ ] **Step 3: Update `CountQueryParams`, `overview.api.ts`, and `DashboardPage.tsx`**

1. In `frontend/src/types/index.ts`, add `period?: "today" | "shift" | "week" | string;` to `CountQueryParams`:
```typescript
export interface CountQueryParams {
  from?: string;
  to?: string;
  from_time?: string;
  to_time?: string;
  period?: "today" | "shift" | "week" | string;
  granularity?: "minute" | "hourly" | "daily" | string;
  page?: number;
  limit?: number;
}
```

2. In `frontend/src/features/overview/api/overview.api.ts`:
```typescript
  getCounts: (lineId: string, params: CountQueryParams = {}) => {
    const searchParams = new URLSearchParams();
    if (params.from) searchParams.set("from", params.from);
    if (params.to) searchParams.set("to", params.to);
    if (params.period) searchParams.set("period", params.period);
    if (params.granularity) searchParams.set("granularity", params.granularity);
    const query = searchParams.toString();
    return http<LineCountsResponse>(`/api/v1/lines/${encodeURIComponent(lineId)}/counts${query ? `?${query}` : ""}`);
  },
```

3. In `frontend/src/features/overview/pages/DashboardPage.tsx` line 53:
```typescript
      overviewApi
        .getCounts(currentLineId, { granularity: "hourly", period: "today" })
        .then((res) => {
          if (isMounted && res?.aggregates) setAggregates(res.aggregates);
        })
        .catch(() => {
          // fallback remains active
        });
```

- [ ] **Step 4: Update `HourlyRateChart.tsx` to generate the 24-hour timeline**

In `frontend/src/features/overview/components/HourlyRateChart.tsx`:
```tsx
import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import { LineChart as LineChartIcon } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import type { AggregateItemDTO } from "@/types";
import { formatBucketHour } from "@/utils/time";

interface HourlyRateChartProps {
  data?: AggregateItemDTO[];
}

const HOURS_24 = Array.from({ length: 24 }, (_, i) => `${String(i).padStart(2, "0")}:00`);

export function HourlyRateChart({ data = [] }: HourlyRateChartProps) {
  const hasData = (data ?? []).length > 0 && (data ?? []).some((d) => (d.count ?? 0) > 0);

  const counts24 = useMemo(() => {
    if (!hasData) return [];
    const hourMap: Record<string, number> = {};
    for (const item of data ?? []) {
      const formatted = formatBucketHour(item.bucket);
      // Normalize to HH:00
      const hourKey = formatted.includes(":") ? `${formatted.split(":")[0]}:00` : formatted;
      hourMap[hourKey] = (hourMap[hourKey] || 0) + (item.count || 0);
    }
    return HOURS_24.map((hour) => hourMap[hour] || 0);
  }, [data, hasData]);

  const option = {
    tooltip: {
      trigger: "axis",
      backgroundColor: "#ffffff",
      borderColor: "#e2e8f0",
      textStyle: { color: "#0f172a", fontSize: 12 },
      formatter: "{b}<br /><span style='font-weight:600;'>{c} ekor</span>",
    },
    grid: {
      top: "10%",
      left: "2%",
      right: "2%",
      bottom: "5%",
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: HOURS_24,
      boundaryGap: false,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: "#94a3b8", fontSize: 11 },
    },
    yAxis: {
      type: "value",
      splitLine: {
        show: true,
        lineStyle: { color: "#f1f5f9", width: 1 },
      },
      axisLabel: { show: false },
    },
    series: [
      {
        name: "Penghitungan",
        type: "line",
        smooth: 0.5,
        symbol: "none",
        data: counts24,
        lineStyle: {
          color: "#2563eb",
          width: 2.5,
        },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(37, 99, 235, 0.22)" },
              { offset: 1, color: "rgba(37, 99, 235, 0.0)" },
            ],
          },
        },
      },
    ],
  };

  return (
    <Card className="rounded-2xl border-slate-200/80 shadow-sm bg-white">
      <div className="p-5 pb-0">
        <h3 className="text-sm font-semibold text-slate-800">
          Tren Penghitungan per Jam
        </h3>
      </div>
      <CardContent className="p-4 pt-1">
        <div className="h-[210px] w-full flex items-center justify-center">
          {hasData ? (
            <ReactECharts
              option={option}
              notMerge={true}
              style={{ height: "100%", width: "100%" }}
            />
          ) : (
            <div className="flex flex-col items-center justify-center text-center p-6 text-slate-400">
              <LineChartIcon className="w-10 h-10 mb-2 stroke-[1.25] text-slate-300" aria-hidden="true" />
              <p className="text-sm font-medium text-slate-600">Belum ada data penghitungan hari ini</p>
              <p className="text-xs text-slate-400 mt-0.5">Data grafik per jam akan muncul otomatis saat konveyor aktif</p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run:
```powershell
npm --prefix frontend run test
```
Expected: PASS for all test suites.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/features/overview/api/overview.api.ts frontend/src/features/overview/pages/DashboardPage.tsx frontend/src/features/overview/components/HourlyRateChart.tsx frontend/src/features/overview/components/__tests__/HourlyRateChart.test.tsx
git commit -m "feat(dashboard): render true 24-hour timeline in hourly rate chart"
```

---

### Task 3: Full End-to-End Verification

**Files:**
- Test all backend and frontend suites

- [ ] **Step 1: Run full backend test suite**

Run:
```powershell
& "C:\Users\torino\AppData\Local\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe" run --with fastapi --with httpx --with sqlalchemy --with pytest --with pyjwt --with python-dotenv --with opencv-python-headless --with reportlab --with openpyxl pytest services/api/tests/ -v
```
Expected: All tests PASS.

- [ ] **Step 2: Run full frontend test suite**

Run:
```powershell
npm --prefix frontend run test
```
Expected: All tests PASS.

- [ ] **Step 3: Run production frontend build**

Run:
```powershell
npm --prefix frontend run build
```
Expected: `tsc && vite build` succeeds with exit code 0.
