# Removal of Frontend Dummy Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all hardcoded dummy data, synthetic demo curves, fabricated report rows, phantom alarms, and arbitrary metric fallbacks (such as 120 cpm, 99.2% accuracy, and 42 ms latency) from the frontend, replacing them with authentic zero states, honest unmeasured indicators (`-`), and clean empty states.

**Architecture:** Frontend components in `frontend/src/features/` and `frontend/src/context/` are updated to strictly consume real API/stream responses. Where data is empty or unavailable, components gracefully render localized empty state placeholders (`"Belum ada data..."`) or zero/unmeasured metrics (`"-"`) instead of synthesizing mock records.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, Lucide React, Vitest, `@testing-library/react`.

## Global Constraints

- Indonesian language and locale conventions (`id-ID`) for text labels and number formatting.
- All API and data contracts must maintain 100% backwards compatibility with backend schemas.
- Clean TypeScript strict mode with zero compile errors under `tsc` (`npm run build`).
- Do not fabricate data on API or connection errors; display honest empty/disconnected states.

---

### Task 1: HourlyRateChart Empty State & Mock Data Removal

**Files:**
- Modify: `frontend/src/features/overview/components/HourlyRateChart.tsx`
- Test: `frontend/src/features/overview/components/__tests__/HourlyRateChart.test.tsx`

**Interfaces:**
- Consumes: `AggregateItemDTO[]` from `@/types`
- Produces: `HourlyRateChart({ data }: { data?: AggregateItemDTO[] })`
  - When `data` is empty or all counts are 0, renders empty state *"Belum ada data penghitungan hari ini"*.
  - When valid data is provided, renders the ECharts spline.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/overview/components/__tests__/HourlyRateChart.test.tsx`:
```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { HourlyRateChart } from "../HourlyRateChart";

// Mock echarts-for-react to avoid canvas rendering requirements in jsdom
vi.mock("echarts-for-react", () => ({
  default: () => <div data-testid="echarts-mock" />,
}));

describe("HourlyRateChart", () => {
  it("renders empty state placeholder when data is empty", () => {
    render(<HourlyRateChart data={[]} />);
    expect(screen.getByText("Belum ada data penghitungan hari ini")).toBeDefined();
    expect(screen.queryByTestId("echarts-mock")).toBeNull();
  });

  it("renders empty state placeholder when data is undefined", () => {
    render(<HourlyRateChart />);
    expect(screen.getByText("Belum ada data penghitungan hari ini")).toBeDefined();
    expect(screen.queryByTestId("echarts-mock")).toBeNull();
  });

  it("renders chart when data is populated", () => {
    render(
      <HourlyRateChart
        data={[
          { bucket: "2026-10-20T08:00:00Z", count: 150, rate_per_min: 25 },
        ]}
      />
    );
    expect(screen.queryByText("Belum ada data penghitungan hari ini")).toBeNull();
    expect(screen.getByTestId("echarts-mock")).toBeDefined();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test frontend/src/features/overview/components/__tests__/HourlyRateChart.test.tsx`
Expected: FAIL because `HourlyRateChart` currently falls back to `defaultTimes` and `defaultCounts` and renders `echarts-mock`.

- [ ] **Step 3: Update `HourlyRateChart.tsx`**

Modify `frontend/src/features/overview/components/HourlyRateChart.tsx`:
```tsx
import ReactECharts from "echarts-for-react";
import { LineChart as LineChartIcon } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import type { AggregateItemDTO } from "@/types";

interface HourlyRateChartProps {
  data?: AggregateItemDTO[];
}

export function HourlyRateChart({ data = [] }: HourlyRateChartProps) {
  const formatBucketHour = (bucket: string) => {
    if (!bucket) return "";
    if (bucket.includes("T")) {
      return bucket.split("T")[1].slice(0, 5);
    }
    return bucket;
  };

  const hasData = (data ?? []).length > 0;
  const times = hasData ? (data ?? []).map((d) => formatBucketHour(d.bucket)) : [];
  const counts = hasData ? (data ?? []).map((d) => d.count) : [];

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
      data: times,
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
        data: counts,
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

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test frontend/src/features/overview/components/__tests__/HourlyRateChart.test.tsx`
Expected: PASS (all 3 tests pass).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/overview/components/HourlyRateChart.tsx frontend/src/features/overview/components/__tests__/HourlyRateChart.test.tsx
git commit -m "fix(overview): remove fake fallback curve and display clean empty state in HourlyRateChart"
```

---

### Task 2: LaporanPage Mock Samples Removal & Real Zero KPI Fallbacks

**Files:**
- Modify: `frontend/src/features/reports/pages/LaporanPage.tsx`
- Test: `frontend/src/features/reports/pages/__tests__/LaporanPage.test.tsx`

**Interfaces:**
- Consumes: `reportsApi.getSummary()`, `reportsApi.getAggregates()`
- Produces: `LaporanPage`
  - On error or empty list, `rawRows` is `[]`.
  - `summaryMetrics` averages `accuracyPct` using real records (`curr.accuracyPct ?? 0`) or 0 when empty.
  - No `sample-1`..`sample-4` entries injected.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/reports/pages/__tests__/LaporanPage.test.tsx`:
```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
import LaporanPage from "../LaporanPage";
import { reportsApi } from "../../api/reports.api";

vi.mock("@/context/AppContext", () => ({
  useAppContext: () => ({
    currentLineId: "line-1",
    lines: [{ id: "line-1", name: "Conveyor Line 1", status: "online" }],
    isConnected: true,
  }),
}));

vi.mock("@/components/layout/PageHeader", () => ({
  PageHeader: ({ title, children }: any) => (
    <div data-testid="page-header">
      <h1>{title}</h1>
      {children}
    </div>
  ),
}));

vi.mock("@/components/common/StatusBadge", () => ({
  StatusBadge: () => <div data-testid="status-badge" />,
}));

vi.mock("@/components/layout/LineSelector", () => ({
  LineSelector: () => <div data-testid="line-selector" />,
}));

describe("LaporanPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("does not inject sample-1..sample-4 when report api calls fail", async () => {
    vi.spyOn(reportsApi, "getAggregates").mockRejectedValue(new Error("Network Error"));

    render(<LaporanPage />);

    await waitFor(() => {
      expect(screen.queryByText("sample-1")).toBeNull();
      expect(screen.queryByText("Lini 2 - Pemotongan")).toBeNull();
      expect(screen.queryByText("7.120")).toBeNull();
    });

    expect(screen.getByText("Belum ada riwayat data penghitungan untuk filter yang dipilih")).toBeDefined();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test frontend/src/features/reports/pages/__tests__/LaporanPage.test.tsx`
Expected: FAIL because `sample-1`, `Lini 2 - Pemotongan`, and `7.120` are currently injected when API calls fail.

- [ ] **Step 3: Modify `frontend/src/features/reports/pages/LaporanPage.tsx`**

Remove lines 102-155 (the fallback sample rows injection) and update `summaryMetrics`:
```tsx
// Remove the block:
// const allFailed = results.length > 0 && results.every(({ res }) => res === null);
// if (allFailed && items.length === 0) { ... items.push(sample-1, sample-2, sample-3, sample-4) ... }

// And in summaryMetrics calculation:
const summaryMetrics: ReportSummaryMetrics = useMemo(() => {
  const totalCount = filteredRows.reduce((acc, curr) => acc + (curr.count || 0), 0);
  const avgRateCpm =
    filteredRows.length > 0
      ? filteredRows.reduce((acc, curr) => acc + (curr.ratePerMin || 0), 0) /
        filteredRows.length
      : 0;
  const avgAccuracyPct =
    filteredRows.length > 0
      ? filteredRows.reduce((acc, curr) => acc + (curr.accuracyPct ?? 0), 0) /
        filteredRows.length
      : 0;
  const totalOperationMinutes = filteredRows.length * 60;

  return {
    totalCount,
    avgRateCpm,
    avgAccuracyPct,
    totalOperationMinutes,
  };
}, [filteredRows]);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test frontend/src/features/reports/pages/__tests__/LaporanPage.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/reports/pages/LaporanPage.tsx frontend/src/features/reports/pages/__tests__/LaporanPage.test.tsx
git commit -m "fix(reports): remove fake sample rows and compute genuine kpis in LaporanPage"
```

---

### Task 3: AlarmPage Fallback Mock Alarm Removal

**Files:**
- Modify: `frontend/src/features/alarms/pages/AlarmPage.tsx`
- Test: `frontend/src/features/alarms/pages/__tests__/AlarmPage.test.tsx`

**Interfaces:**
- Consumes: `alarmsApi.list()`
- Produces: `AlarmPage`
  - On error, `alarms` remains empty (`[]`).
  - Renders empty state *"Tidak ada data alarm yang tercatat"*.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/alarms/pages/__tests__/AlarmPage.test.tsx`:
```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
import AlarmPage from "../AlarmPage";
import { alarmsApi } from "../../api/alarms.api";

vi.mock("@/context/AppContext", () => ({
  useAppContext: () => ({
    currentLineId: "line-1",
    isConnected: true,
  }),
}));

vi.mock("@/components/layout/PageHeader", () => ({
  PageHeader: ({ title, children }: any) => (
    <div>
      <h1>{title}</h1>
      {children}
    </div>
  ),
}));

vi.mock("@/components/common/StatusBadge", () => ({
  StatusBadge: () => <div />,
}));

vi.mock("@/components/layout/LineSelector", () => ({
  LineSelector: () => <div />,
}));

describe("AlarmPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("does not inject fake LOW_SPEED alarm when api list fails", async () => {
    vi.spyOn(alarmsApi, "list").mockRejectedValue(new Error("API Error"));

    render(<AlarmPage />);

    await waitFor(() => {
      expect(screen.queryByText(/Kecepatan di bawah target/i)).toBeNull();
      expect(screen.queryByText("LOW_SPEED")).toBeNull();
    });

    expect(screen.getByText("Tidak ada data alarm yang tercatat")).toBeDefined();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test frontend/src/features/alarms/pages/__tests__/AlarmPage.test.tsx`
Expected: FAIL because `AlarmPage` currently sets `LOW_SPEED` alarm on error.

- [ ] **Step 3: Modify `frontend/src/features/alarms/pages/AlarmPage.tsx`**

In `frontend/src/features/alarms/pages/AlarmPage.tsx`, update the `.catch()` block:
```tsx
      .then((data) => {
        if (isCurrent && Array.isArray(data)) {
          setAlarms(data);
        }
      })
      .catch(() => {
        if (isCurrent) {
          setAlarms([]);
        }
      });
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test frontend/src/features/alarms/pages/__tests__/AlarmPage.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/alarms/pages/AlarmPage.tsx frontend/src/features/alarms/pages/__tests__/AlarmPage.test.tsx
git commit -m "fix(alarms): remove fabricated fallback alarm on api failure in AlarmPage"
```

---

### Task 4: KpiCards & DashboardPage Accuracy and Speed Zero Fallbacks

**Files:**
- Modify: `frontend/src/features/overview/components/KpiCards.tsx`
- Modify: `frontend/src/features/overview/pages/DashboardPage.tsx`
- Test: `frontend/src/features/overview/components/__tests__/KpiCards.test.tsx`

**Interfaces:**
- Consumes: `LineSummaryResponse`
- Produces: `KpiCards({ summary })`
  - Speed displays `0 ekor/menit` when `current_speed_cpm` is 0 or null.
  - Accuracy displays `"-"` when `total_count === 0` or accuracy is 0 or null.
  - `FALLBACK_SUMMARY.detection_accuracy_pct` is `0.0`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/overview/components/__tests__/KpiCards.test.tsx`:
```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { KpiCards } from "../KpiCards";
import type { LineSummaryResponse } from "@/types";

describe("KpiCards", () => {
  it("renders 0 ekor/menit and - for unmeasured accuracy when summary is zeroed", () => {
    const summary: LineSummaryResponse = {
      line_id: "line-1",
      period: "today",
      total_count: 0,
      target_count: 60000,
      target_attainment_pct: 0,
      current_speed_cpm: 0,
      target_speed_cpm: 120,
      active_alarms_count: 0,
      camera_status: "offline",
      last_event_time: null,
      fps: 0,
      latency_p95_ms: 0,
      detection_accuracy_pct: 0,
    };

    render(<KpiCards summary={summary} />);

    // Speed should not be 120
    expect(screen.getByText("0")).toBeDefined();
    expect(screen.queryByText("120")).toBeNull();

    // Accuracy should not be 99.2%
    expect(screen.queryByText(/99[,.]2%/)).toBeNull();
    expect(screen.getByText("-")).toBeDefined();
  });

  it("renders genuine speed and accuracy when data is present", () => {
    const summary: LineSummaryResponse = {
      line_id: "line-1",
      period: "today",
      total_count: 500,
      target_count: 60000,
      target_attainment_pct: 0.8,
      current_speed_cpm: 85,
      target_speed_cpm: 120,
      active_alarms_count: 0,
      camera_status: "online",
      last_event_time: "2026-10-20T10:00:00Z",
      fps: 30,
      latency_p95_ms: 15,
      detection_accuracy_pct: 98.5,
    };

    render(<KpiCards summary={summary} />);

    expect(screen.getByText("85")).toBeDefined();
    expect(screen.getByText("98,5%")).toBeDefined();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test frontend/src/features/overview/components/__tests__/KpiCards.test.tsx`
Expected: FAIL because `KpiCards` currently displays `120` and `99,2%` when speed or accuracy are 0.

- [ ] **Step 3: Modify `KpiCards.tsx` and `DashboardPage.tsx`**

In `frontend/src/features/overview/components/KpiCards.tsx`:
```tsx
  const hasAccuracy =
    (summary.total_count ?? 0) > 0 &&
    summary.detection_accuracy_pct != null &&
    summary.detection_accuracy_pct > 0;

  const formattedAccuracy = hasAccuracy
    ? `${summary.detection_accuracy_pct!.toLocaleString("id-ID", {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
      })}%`
    : "-";
```
And for speed:
```tsx
  {Math.round(summary.current_speed_cpm ?? 0).toLocaleString("id-ID")}
```
And in accuracy display:
```tsx
  <span className="text-2xl font-bold tracking-tight text-slate-900">
    {formattedAccuracy}
  </span>
```

In `frontend/src/features/overview/pages/DashboardPage.tsx`:
```tsx
const FALLBACK_SUMMARY: LineSummaryResponse = {
  line_id: "line-1",
  period: "today",
  total_count: 0,
  target_count: 62000,
  target_attainment_pct: 0.0,
  current_speed_cpm: 0.0,
  target_speed_cpm: 120.0,
  active_alarms_count: 0,
  camera_status: "offline",
  last_event_time: null,
  fps: 0.0,
  latency_p95_ms: 0.0,
  detection_accuracy_pct: 0.0,
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test frontend/src/features/overview/components/__tests__/KpiCards.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/overview/components/KpiCards.tsx frontend/src/features/overview/pages/DashboardPage.tsx frontend/src/features/overview/components/__tests__/KpiCards.test.tsx
git commit -m "fix(overview): remove synthetic 120 cpm and 99.2% accuracy fallbacks in KpiCards and DashboardPage"
```

---

### Task 5: Telemetry Fallbacks in Live Monitoring & AppContext Offline Status

**Files:**
- Modify: `frontend/src/features/livestream/components/SystemStatusCard.tsx`
- Modify: `frontend/src/features/livestream/pages/LiniProduksiPage.tsx`
- Modify: `frontend/src/context/AppContext.tsx`
- Test: `frontend/src/features/livestream/components/__tests__/SystemStatusCard.test.tsx`

**Interfaces:**
- Consumes: `fps`, `latencyMs`, `streamState`
- Produces: `SystemStatusCard`
  - Default props: `fps = 0`, `latencyMs = 0`, `streamState = "offline"`.
  - Latency displays `"-"` when `latencyMs <= 0` or offline.
  - `FALLBACK_MOCK_LINE.status = "offline"`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/livestream/components/__tests__/SystemStatusCard.test.tsx`:
```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { SystemStatusCard } from "../SystemStatusCard";

describe("SystemStatusCard", () => {
  it("defaults to 0 FPS, - Latensi, and Offline when no props are provided", () => {
    render(<SystemStatusCard />);
    expect(screen.getByText("0")).toBeDefined();
    expect(screen.getByText("-")).toBeDefined();
    expect(screen.getByText("Offline")).toBeDefined();
    expect(screen.queryByText("42")).toBeNull();
    expect(screen.queryByText("30")).toBeNull();
  });

  it("renders genuine FPS and latency when stream is online", () => {
    render(<SystemStatusCard fps={25} latencyMs={18} streamState="online" />);
    expect(screen.getByText("25")).toBeDefined();
    expect(screen.getByText("18")).toBeDefined();
    expect(screen.getByText("Online")).toBeDefined();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test frontend/src/features/livestream/components/__tests__/SystemStatusCard.test.tsx`
Expected: FAIL because `SystemStatusCard` currently defaults to `fps = 30`, `latencyMs = 42`, `streamState = "online"`.

- [ ] **Step 3: Modify `SystemStatusCard.tsx`, `LiniProduksiPage.tsx`, and `AppContext.tsx`**

In `frontend/src/features/livestream/components/SystemStatusCard.tsx`:
```tsx
interface SystemStatusCardProps {
  fps?: number;
  latencyMs?: number;
  streamState?: "online" | "degraded" | "offline" | string;
}

export function SystemStatusCard({
  fps = 0,
  latencyMs = 0,
  streamState = "offline",
}: SystemStatusCardProps) {
  const normalizedState = (streamState || "offline").toLowerCase();

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
  const hasLatency = latencyMs > 0 && normalizedState !== "offline";

  return (
    <Card className="rounded-2xl border-slate-200/80 shadow-sm bg-white">
      <CardHeader className="p-4 pb-2">
        <CardTitle className="text-sm font-semibold text-slate-800">
          Status Sistem
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 pt-2">
        <div className="grid grid-cols-3 divide-x divide-slate-100 text-center sm:text-left">
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

          {/* Status Edge */}
          <div className="px-3 last:pr-0">
            <span className="text-xs text-slate-500 font-medium block mb-1">
              Status Edge
            </span>
            <div className="flex items-center gap-2 mt-1.5">
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

In `frontend/src/features/livestream/pages/LiniProduksiPage.tsx`:
```tsx
<SystemStatusCard
  fps={fps ?? 0}
  latencyMs={latencyMs ?? 0}
  streamState={isStreaming ? (streamState?.toLowerCase() || "online") : "offline"}
/>
```

In `frontend/src/context/AppContext.tsx`:
```tsx
export const FALLBACK_MOCK_LINE: Line = {
  id: "line-1",
  name: "Conveyor Line 1",
  is_active: true,
  daily_target: 60000,
  status: "offline",
  total_today: 0,
  last_ping: null,
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test frontend/src/features/livestream/components/__tests__/SystemStatusCard.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/livestream/components/SystemStatusCard.tsx frontend/src/features/livestream/pages/LiniProduksiPage.tsx frontend/src/context/AppContext.tsx frontend/src/features/livestream/components/__tests__/SystemStatusCard.test.tsx
git commit -m "fix(livestream): remove synthetic 30 fps, 42 ms latency, and online mock status fallbacks"
```

---

### Task 6: Full Regression Verification & Build Check

**Files:**
- All modified and test files

- [ ] **Step 1: Run complete test suite**

Run: `npm test`
Expected: All test suites in `frontend/src/` PASS.

- [ ] **Step 2: Run production build**

Run: `npm run build`
Expected: `tsc && vite build` succeeds with 0 errors.

- [ ] **Step 3: Verification commit (if needed)**

Ensure working tree is clean.
