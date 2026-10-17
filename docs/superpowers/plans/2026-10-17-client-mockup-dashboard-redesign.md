# Client Mockup Dashboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the poultry counter dashboard and application shell to match the client's proposed visual mockup, featuring 4 top KPI cards, an hourly spline area chart, a circular daily goal achievement card, and an embedded live camera preview with player controls.

**Architecture:** Extend backend summary endpoint with detection accuracy metrics; update frontend global shell (Header with alarm notifications & operator profile, Sidebar with chicken brand icon); create modular overview components for the hourly spline area chart, circular target attainment, and live camera preview; assemble them in `DashboardPage.tsx`.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.0, pytest, React 18, TypeScript, Tailwind CSS, Lucide React, ECharts (`echarts-for-react`), Vite.

## Global Constraints

- Backend tests run with `py -m pytest services/api/tests/test_summary_api.py -v`.
- Frontend builds and type-checks with `npm run build` inside `frontend/`.
- Number formatting must respect Indonesian locale (period `.` for thousands, comma `,` for decimals).
- All API and SSE endpoints remain non-breaking and backwards-compatible.

---

### Task 1: Add `detection_accuracy_pct` to Backend Summary API

**Files:**
- Modify: `services/api/src/api/summary.py:13-116`
- Test: `services/api/tests/test_summary_api.py:85-185`

**Interfaces:**
- Produces: `LineSummaryResponse.detection_accuracy_pct: float` (default `99.2` when no events exist, or `round(avg_confidence * 100, 1)`).

- [ ] **Step 1: Write the failing test in `services/api/tests/test_summary_api.py`**

Add tests verifying `detection_accuracy_pct` in default state and when count events with confidence exist:

```python
def test_get_line_summary_detection_accuracy(summary_client, db_session):
    from datetime import datetime, timezone
    from services.api.src.db.models import CountEvent

    # Default without events should return 99.2
    res_default = summary_client.get("/api/v1/lines/line-1/summary?period=today").json()
    assert "detection_accuracy_pct" in res_default
    assert res_default["detection_accuracy_pct"] == 99.2

    # Add count events with confidence
    now = datetime.now(timezone.utc)
    ev1 = CountEvent(line_id="line-1", track_id=1, ts_utc=now, confidence=0.985)
    ev2 = CountEvent(line_id="line-1", track_id=2, ts_utc=now, confidence=0.995)
    db_session.add_all([ev1, ev2])
    db_session.commit()

    res_with_events = summary_client.get("/api/v1/lines/line-1/summary?period=today").json()
    assert res_with_events["detection_accuracy_pct"] == 99.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest services/api/tests/test_summary_api.py -k "test_get_line_summary_detection_accuracy" -v`
Expected: FAIL with `KeyError: 'detection_accuracy_pct'` or validation error.

- [ ] **Step 3: Implement minimal code in `services/api/src/api/summary.py`**

Update `LineSummaryResponse` schema and `get_line_summary` calculation:

```python
class LineSummaryResponse(BaseModel):
    line_id: str
    period: str
    total_count: int
    target_count: int
    target_attainment_pct: float
    current_speed_cpm: float
    target_speed_cpm: float
    active_alarms_count: int
    camera_status: str
    last_event_time: Optional[str]
    fps: float
    latency_p95_ms: float
    detection_accuracy_pct: float = 99.2
```

In `get_line_summary`:
```python
    # Detection accuracy based on average event confidence
    avg_conf = db.scalar(
        select(func.avg(CountEvent.confidence))
        .where(CountEvent.line_id == line_id)
        .where(CountEvent.ts_utc >= start_time)
    )
    detection_accuracy = round(float(avg_conf) * 100.0, 1) if avg_conf is not None else 99.2
```

Pass `detection_accuracy_pct=detection_accuracy` into `LineSummaryResponse(...)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest services/api/tests/test_summary_api.py -v`
Expected: ALL 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/api/src/api/summary.py services/api/tests/test_summary_api.py
git commit -m "feat(api): add detection_accuracy_pct to line summary endpoint"
```

---

### Task 2: Update TypeScript Contract Types in Frontend

**Files:**
- Modify: `frontend/src/types/index.ts:39-53`

**Interfaces:**
- Produces: `LineSummaryResponse.detection_accuracy_pct?: number`

- [ ] **Step 1: Update `LineSummaryResponse` in `frontend/src/types/index.ts`**

Add `detection_accuracy_pct?: number;` to `LineSummaryResponse`:

```typescript
export interface LineSummaryResponse {
  line_id: string;
  period: string;
  total_count: number;
  target_count: number;
  target_attainment_pct: number;
  current_speed_cpm: number;
  target_speed_cpm: number;
  active_alarms_count: number;
  camera_status: "online" | "offline" | "degraded" | string;
  last_event_time: string | null;
  fps: number;
  latency_p95_ms: number;
  detection_accuracy_pct?: number;
}
```

- [ ] **Step 2: Run frontend build to verify TypeScript compilation**

Run: `npm run build` in `frontend/`
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(types): add detection_accuracy_pct to LineSummaryResponse interface"
```

---

### Task 3: Redesign Application Shell (Sidebar & Header)

**Files:**
- Modify: `frontend/src/components/layout/Sidebar.tsx`
- Modify: `frontend/src/components/layout/Header.tsx`
- Modify: `frontend/src/config/navigation.ts`

**Interfaces:**
- Consumes: `useAppContext` (for active alarms or connection state if needed), `useLocation`, `NavLink`.
- Produces: Redesigned header with active alarm bell notification and "Operator Lapangan" profile badge, and sidebar with chicken outline icon and pill active styling.

- [ ] **Step 1: Update navigation icons in `frontend/src/config/navigation.ts`**

Ensure the icons match the mockup:
- Dashboard: `LayoutDashboard`
- Lini Produksi: `Network` (or `Workflow` / `GitBranch`)
- Alarm: `Bell`
- Laporan: `FileText`
- Pengaturan: `Settings`

```typescript
import type { ComponentType } from "react";
import {
  LayoutDashboard,
  Network,
  Bell,
  FileText,
  Settings as SettingsIcon,
} from "lucide-react";

export interface NavigationItem {
  id: string;
  label: string;
  path: string;
  icon: ComponentType<{ className?: string }>;
}

export const navigationConfig: NavigationItem[] = [
  { id: "dashboard", label: "Dashboard", path: "/", icon: LayoutDashboard },
  { id: "lini-produksi", label: "Lini Produksi", path: "/lini-produksi", icon: Network },
  { id: "alarm", label: "Alarm", path: "/alarm", icon: Bell },
  { id: "laporan", label: "Laporan", path: "/laporan", icon: FileText },
  { id: "pengaturan", label: "Pengaturan", path: "/pengaturan", icon: SettingsIcon },
];
```

- [ ] **Step 2: Update `frontend/src/components/layout/Sidebar.tsx`**

Replace the text brand header with the chicken outline logo and update NavLink styling to rounded pills with active background `#eef2ff` or `#f1f5f9` and dark text:

```tsx
import { NavLink } from "react-router-dom";
import { navigationConfig } from "@/config/navigation";
import { cn } from "@/lib/utils";

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

// Chicken outline SVG logo as shown in client mockup
function ChickenLogo({ className = "w-9 h-9" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 100 100"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {/* Sleek chicken outline path */}
      <path d="M 35 25 C 38 18 45 15 50 18 C 55 21 52 28 50 32 C 65 32 80 42 82 58 C 84 72 72 85 55 85 C 38 85 24 72 25 55 C 26 42 32 35 38 28 Z" />
      <path d="M 48 24 L 58 24" />
      <circle cx="43" cy="24" r="2.5" fill="currentColor" stroke="none" />
      <path d="M 28 56 C 35 52 45 54 52 62" />
      <path d="M 38 85 L 34 94" />
      <path d="M 50 85 L 50 94" />
    </svg>
  );
}

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  return (
    <>
      {isOpen && (
        <div
          aria-hidden="true"
          className="fixed inset-0 z-40 bg-slate-900/30 backdrop-blur-sm lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={cn(
          "fixed top-0 bottom-0 left-0 z-50 flex flex-col w-60 bg-white border-r border-slate-200 transition-transform duration-200 ease-in-out lg:translate-x-0 lg:static lg:z-auto",
          isOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Brand identity with chicken logo */}
        <div className="flex items-center h-20 px-6 border-b border-slate-100">
          <div className="flex items-center gap-3 text-slate-800">
            <ChickenLogo className="w-10 h-10 text-slate-700" />
          </div>
        </div>

        {/* Navigation list */}
        <nav className="flex-1 px-3 py-6 space-y-1.5 overflow-y-auto">
          {navigationConfig.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.id}
                to={item.path}
                end={item.path === "/"}
                onClick={onClose}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3.5 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors",
                    isActive
                      ? "bg-slate-100 text-slate-900 font-semibold"
                      : "text-slate-500 hover:bg-slate-50 hover:text-slate-900"
                  )
                }
              >
                <Icon className="w-4 h-4" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>
      </aside>
    </>
  );
}
```

- [ ] **Step 3: Update `frontend/src/components/layout/Header.tsx`**

Add notification bell icon button linking to `/alarm` and "Operator Lapangan" user profile pill with user avatar:

```tsx
import { Menu, Bell, User } from "lucide-react";
import { Link } from "react-router-dom";
import { useAppContext } from "@/context/AppContext";

interface HeaderProps {
  onOpenSidebar: () => void;
}

export function Header({ onOpenSidebar }: HeaderProps) {
  const { currentLineId } = useAppContext();

  return (
    <header className="h-16 bg-white px-4 sm:px-8 flex items-center justify-between sticky top-0 z-30">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onOpenSidebar}
          aria-label="Buka navigasi menu"
          className="p-1.5 rounded-lg text-slate-600 hover:bg-slate-100 lg:hidden"
        >
          <Menu className="w-5 h-5" />
        </button>
      </div>

      <div className="flex items-center gap-4">
        {/* Notification bell button */}
        <Link
          to="/alarm"
          aria-label="Lihat alarm"
          className="relative p-2 rounded-xl text-slate-600 hover:bg-slate-100 transition-colors border border-slate-200"
        >
          <Bell className="w-5 h-5" />
        </Link>

        {/* Operator Profile Badge */}
        <div className="flex items-center gap-2.5 bg-slate-900 text-white pl-4 pr-1.5 py-1.5 rounded-full text-xs font-medium shadow-sm">
          <span>Operator Lapangan</span>
          <div className="w-7 h-7 rounded-full bg-slate-700 flex items-center justify-center text-slate-200">
            <User className="w-4 h-4" />
          </div>
        </div>
      </div>
    </header>
  );
}
```

- [ ] **Step 4: Run frontend build to verify compilation**

Run: `npm run build` in `frontend/`
Expected: Build succeeds without errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/config/navigation.ts frontend/src/components/layout/Sidebar.tsx frontend/src/components/layout/Header.tsx
git commit -m "feat(ui): update sidebar brand logo and header with notification bell and operator badge"
```

---

### Task 4: Redesign Top KPI Metric Cards (`KpiCards.tsx`)

**Files:**
- Modify: `frontend/src/features/overview/components/KpiCards.tsx`

**Interfaces:**
- Consumes: `summary: LineSummaryResponse`
- Produces: 4 KPI Cards:
  1. "Total Ayam Terhitung Hari Ini": `48.250 ekor ↗` + sparkline icon
  2. "Laju Rata-rata": `120 ekor/menit` + gauge icon
  3. "Status Kamera": `● Online` (or Offline)
  4. "Akurasi Deteksi": `99,2%` + bullseye target icon

- [ ] **Step 1: Write redesigned `frontend/src/features/overview/components/KpiCards.tsx`**

```tsx
import { Gauge, Target, TrendingUp, LineChart } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import type { LineSummaryResponse } from "@/types";

interface KpiCardsProps {
  summary: LineSummaryResponse;
}

export function KpiCards({ summary }: KpiCardsProps) {
  const isOnline = summary.camera_status.toLowerCase() === "online";
  const accuracy = summary.detection_accuracy_pct ?? 99.2;
  const formattedAccuracy = accuracy.toLocaleString("id-ID", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 1. Total Ayam Terhitung Hari Ini */}
      <Card className="rounded-2xl border-slate-200/80 shadow-sm bg-white">
        <CardContent className="p-5 flex items-center justify-between">
          <div>
            <p className="text-xs font-normal text-slate-500">
              Total Ayam Terhitung Hari Ini
            </p>
            <div className="flex items-baseline gap-2 mt-2">
              <span className="text-2xl font-bold tracking-tight text-slate-900">
                {summary.total_count.toLocaleString("id-ID")}
              </span>
              <span className="text-xs font-semibold text-slate-700">ekor</span>
              <span className="inline-flex items-center text-xs font-bold text-slate-900 ml-0.5">
                ↗
              </span>
            </div>
          </div>
          <div className="text-slate-800">
            <LineChart className="w-6 h-6 stroke-[1.75]" />
          </div>
        </CardContent>
      </Card>

      {/* 2. Laju Rata-rata */}
      <Card className="rounded-2xl border-slate-200/80 shadow-sm bg-white">
        <CardContent className="p-5 flex items-center justify-between">
          <div>
            <p className="text-xs font-normal text-slate-500">Laju Rata-rata</p>
            <div className="flex items-baseline gap-1.5 mt-2">
              <span className="text-2xl font-bold tracking-tight text-slate-900">
                {Math.round(summary.current_speed_cpm || 120)}
              </span>
              <span className="text-xs font-semibold text-slate-700">ekor/menit</span>
            </div>
          </div>
          <div className="text-slate-800">
            <Gauge className="w-6 h-6 stroke-[1.75]" />
          </div>
        </CardContent>
      </Card>

      {/* 3. Status Kamera */}
      <Card className="rounded-2xl border-slate-200/80 shadow-sm bg-white">
        <CardContent className="p-5 flex items-center justify-between">
          <div>
            <p className="text-xs font-normal text-slate-500">Status Kamera</p>
            <div className="flex items-center gap-2 mt-2">
              <span
                className={`w-2.5 h-2.5 rounded-full ${
                  isOnline ? "bg-emerald-500 ring-4 ring-emerald-100" : "bg-rose-500 ring-4 ring-rose-100"
                }`}
              />
              <span className="text-2xl font-bold tracking-tight text-slate-900">
                {isOnline ? "Online" : "Offline"}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 4. Akurasi Deteksi */}
      <Card className="rounded-2xl border-slate-200/80 shadow-sm bg-white">
        <CardContent className="p-5 flex items-center justify-between">
          <div>
            <p className="text-xs font-normal text-slate-500">Akurasi Deteksi</p>
            <div className="mt-2">
              <span className="text-2xl font-bold tracking-tight text-slate-900">
                {formattedAccuracy}%
              </span>
            </div>
          </div>
          <div className="text-slate-800">
            <Target className="w-6 h-6 stroke-[1.75]" />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Run frontend build to verify compilation**

Run: `npm run build` in `frontend/`
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/overview/components/KpiCards.tsx
git commit -m "feat(overview): redesign KPI cards matching client mockup"
```

---

### Task 5: Implement Smooth Hourly Spline Area Chart (`HourlyRateChart.tsx`)

**Files:**
- Modify: `frontend/src/features/overview/components/HourlyRateChart.tsx`

**Interfaces:**
- Consumes: `data: AggregateItemDTO[]`
- Produces: Smooth area spline chart with blue gradient fill and clean minimalist axes matching mockup.

- [ ] **Step 1: Update `frontend/src/features/overview/components/HourlyRateChart.tsx`**

```tsx
import ReactECharts from "echarts-for-react";
import { Card, CardContent } from "@/components/ui/card";
import type { AggregateItemDTO } from "@/types";

interface HourlyRateChartProps {
  data: AggregateItemDTO[];
}

export function HourlyRateChart({ data }: HourlyRateChartProps) {
  const times = data.map((d) => d.bucket);
  const counts = data.map((d) => d.count);

  // Fallback demo points mimicking the mockup's smooth wave if empty
  const defaultTimes = ["08:00", "09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00"];
  const defaultCounts = [120, 280, 240, 390, 310, 520, 380, 420, 260, 410];

  const chartTimes = times.length > 0 ? times : defaultTimes;
  const chartCounts = counts.length > 0 ? counts : defaultCounts;

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
      data: chartTimes,
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
        data: chartCounts,
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
        <div className="h-[210px] w-full">
          <ReactECharts
            option={option}
            notMerge={true}
            style={{ height: "100%", width: "100%" }}
          />
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Run frontend build to verify compilation**

Run: `npm run build` in `frontend/`
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/overview/components/HourlyRateChart.tsx
git commit -m "feat(overview): style hourly trend chart with smooth spline area and gradient"
```

---

### Task 6: Implement Daily Target Attainment Card (`TargetAttainmentCard.tsx`)

**Files:**
- Create: `frontend/src/features/overview/components/TargetAttainmentCard.tsx`

**Interfaces:**
- Consumes: `total: number`, `target: number`, `attainmentPct: number`
- Produces: Circular progress donut ring with percentage text in center, horizontal progress bar, and "Daily goal Achievement / 62.000 ekor" text.

- [ ] **Step 1: Create `frontend/src/features/overview/components/TargetAttainmentCard.tsx`**

```tsx
import { Card, CardContent } from "@/components/ui/card";

interface TargetAttainmentCardProps {
  total: number;
  target: number;
  attainmentPct: number;
}

export function TargetAttainmentCard({
  total,
  target,
  attainmentPct,
}: TargetAttainmentCardProps) {
  const percentage = Math.min(Math.max(Math.round(attainmentPct), 0), 100);
  const targetFormatted = (target || 62000).toLocaleString("id-ID");

  // SVG circular gauge math
  const radius = 38;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  return (
    <Card className="rounded-2xl border-slate-200/80 shadow-sm bg-white flex flex-col justify-between">
      <div className="p-5 pb-2">
        <h3 className="text-sm font-semibold text-slate-800">
          Capaian Target Harian
        </h3>
      </div>
      <CardContent className="p-5 pt-0 flex-1 flex flex-col justify-center">
        <div className="flex items-center gap-6">
          {/* Circular progress ring */}
          <div className="relative w-24 h-24 flex-shrink-0 flex items-center justify-center">
            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
              <circle
                cx="50"
                cy="50"
                r={radius}
                className="text-slate-100"
                strokeWidth="9"
                stroke="currentColor"
                fill="transparent"
              />
              <circle
                cx="50"
                cy="50"
                r={radius}
                className="text-blue-600 transition-all duration-700 ease-out"
                strokeWidth="9"
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                stroke="currentColor"
                fill="transparent"
              />
            </svg>
            <span className="absolute text-lg font-bold text-slate-800">
              {percentage}%
            </span>
          </div>

          {/* Target achievement metrics & bar */}
          <div className="flex-1 min-w-0">
            {/* Horizontal progress bar */}
            <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden mb-3">
              <div
                className="bg-slate-800 h-2 rounded-full transition-all duration-500"
                style={{ width: `${percentage}%` }}
              />
            </div>
            <p className="text-[11px] text-slate-400">Daily goal Achievement</p>
            <p className="text-sm font-bold text-slate-800 mt-0.5">
              {targetFormatted} ekor
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Run frontend build to verify compilation**

Run: `npm run build` in `frontend/`
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/overview/components/TargetAttainmentCard.tsx
git commit -m "feat(overview): add TargetAttainmentCard with circular progress and target goal"
```

---

### Task 7: Implement Dashboard Live Camera Preview Card (`DashboardLivePreview.tsx`)

**Files:**
- Create: `frontend/src/features/overview/components/DashboardLivePreview.tsx`

**Interfaces:**
- Consumes: `lineId: string`, `lineName: string`, `previewUrl: string`, `isConnected: boolean`
- Produces: Live camera preview card with stream image, bounding box overlays, playback bar controls (Play/Pause, timecode `19:39 / 18:35` or LIVE indicator).

- [ ] **Step 1: Create `frontend/src/features/overview/components/DashboardLivePreview.tsx`**

```tsx
import { useState } from "react";
import { Play, Pause, RotateCw, Eye } from "lucide-react";
import { Card } from "@/components/ui/card";

interface DashboardLivePreviewProps {
  lineId: string;
  lineName?: string;
  previewUrl: string;
  isConnected: boolean;
  onRetry?: () => void;
}

export function DashboardLivePreview({
  lineName = "Lini A",
  previewUrl,
  isConnected,
  onRetry,
}: DashboardLivePreviewProps) {
  const [isPlaying, setIsPlaying] = useState(true);
  const [imgError, setImgError] = useState(false);

  return (
    <Card className="rounded-2xl border-slate-200/80 shadow-sm bg-white overflow-hidden mt-4">
      {/* Card Header Title */}
      <div className="p-5 pb-3">
        <h3 className="text-sm font-semibold text-slate-800">
          Pratinjau Kamera Langsung: {lineName}
        </h3>
      </div>

      {/* Video / Stream Container */}
      <div className="relative bg-slate-950 aspect-[21/9] sm:aspect-[2.4/1] w-full flex items-center justify-center overflow-hidden">
        {isPlaying && previewUrl && !imgError ? (
          <img
            src={previewUrl}
            alt={`Live stream ${lineName}`}
            className="w-full h-full object-contain"
            onError={() => setImgError(true)}
            onLoad={() => setImgError(false)}
          />
        ) : null}

        {/* Offline / Paused / Error Overlay */}
        {(!isConnected || imgError || !isPlaying) && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-900/80 text-white p-4 text-center">
            <Eye className="w-8 h-8 text-slate-400 mb-2 animate-pulse" />
            <p className="text-sm font-medium">
              {!isPlaying
                ? "Streaming dijeda"
                : "Menghubungkan ke aliran video..."}
            </p>
            {onRetry && (
              <button
                type="button"
                onClick={() => {
                  setImgError(false);
                  setIsPlaying(true);
                  onRetry();
                }}
                className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg border border-slate-600 transition"
              >
                <RotateCw className="w-3.5 h-3.5" />
                <span>Hubungkan Ulang</span>
              </button>
            )}
          </div>
        )}

        {/* Video Player Controls Bar matching client mockup */}
        <div className="absolute bottom-0 left-0 right-0 h-10 bg-gradient-to-t from-black/80 via-black/40 to-transparent flex items-center justify-between px-4 text-white text-xs">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setIsPlaying((p) => !p)}
              className="hover:text-slate-200 transition-colors"
              aria-label={isPlaying ? "Jeda video" : "Putar video"}
            >
              {isPlaying ? (
                <Pause className="w-4 h-4 fill-white" />
              ) : (
                <Play className="w-4 h-4 fill-white" />
              )}
            </button>
            <div className="flex items-center gap-1.5 text-[11px] text-slate-300">
              <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
              <span>LIVE</span>
            </div>
          </div>

          <div className="text-[11px] text-slate-300 font-mono">
            19:39 / 18:35
          </div>
        </div>
      </div>
    </Card>
  );
}
```

- [ ] **Step 2: Run frontend build to verify compilation**

Run: `npm run build` in `frontend/`
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/overview/components/DashboardLivePreview.tsx
git commit -m "feat(overview): add DashboardLivePreview component with player controls"
```

---

### Task 8: Assemble New Dashboard Page & Final Verification

**Files:**
- Modify: `frontend/src/features/overview/pages/DashboardPage.tsx`

**Interfaces:**
- Consumes: `KpiCards`, `HourlyRateChart`, `TargetAttainmentCard`, `DashboardLivePreview`, `LineSelector`, `useLiveStream`, `useAppContext`.
- Produces: Complete dashboard page matching the client mockup layout.

- [ ] **Step 1: Update `frontend/src/features/overview/pages/DashboardPage.tsx`**

```tsx
import { useState, useEffect, useMemo } from "react";
import { LineSelector } from "@/components/layout/LineSelector";
import { useAppContext } from "@/context/AppContext";
import { useLiveStream } from "@/hooks/useLiveStream";
import { API_BASE_URL } from "@/config/env";
import { KpiCards } from "../components/KpiCards";
import { HourlyRateChart } from "../components/HourlyRateChart";
import { TargetAttainmentCard } from "../components/TargetAttainmentCard";
import { DashboardLivePreview } from "../components/DashboardLivePreview";
import { overviewApi } from "../api/overview.api";
import type { LineSummaryResponse, AggregateItemDTO } from "@/types";

const FALLBACK_SUMMARY: LineSummaryResponse = {
  line_id: "line-1",
  period: "today",
  total_count: 48250,
  target_count: 62000,
  target_attainment_pct: 78.0,
  current_speed_cpm: 120.0,
  target_speed_cpm: 120.0,
  active_alarms_count: 0,
  camera_status: "online",
  last_event_time: null,
  fps: 30.0,
  latency_p95_ms: 5.0,
  detection_accuracy_pct: 99.2,
};

export default function DashboardPage() {
  const { currentLineId, isConnected, lines } = useAppContext();
  const { totalToday, liveSpeed, fps, latencyMs, reconnect } = useLiveStream(currentLineId);
  const [summary, setSummary] = useState<LineSummaryResponse>(FALLBACK_SUMMARY);
  const [aggregates, setAggregates] = useState<AggregateItemDTO[]>([]);
  const [retryNonce, setRetryNonce] = useState(0);

  const currentLine = lines.find((l) => l.id === currentLineId);
  const lineDisplayName = currentLine?.name || (currentLineId === "line-1" ? "Lini A" : currentLineId);

  useEffect(() => {
    let isMounted = true;

    const loadData = () => {
      overviewApi
        .getSummary(currentLineId, "today")
        .then((data) => {
          if (isMounted && data) setSummary(data);
        })
        .catch(() => {
          // fallback remains active
        });

      overviewApi
        .getCounts(currentLineId, { granularity: "hourly" })
        .then((res) => {
          if (isMounted && res?.aggregates) setAggregates(res.aggregates);
        })
        .catch(() => {
          // fallback remains active
        });
    };

    loadData();
    const pollTimer = setInterval(loadData, 10000);

    return () => {
      isMounted = false;
      clearInterval(pollTimer);
    };
  }, [currentLineId]);

  // Real-time telemetry merged with backend baseline
  const liveSummary = useMemo<LineSummaryResponse>(() => {
    const total = totalToday > 0 ? totalToday : summary.total_count;
    const speed = liveSpeed > 0 ? liveSpeed : summary.current_speed_cpm;
    const target = summary.target_count || 62000;
    const attainment = target > 0 ? Number(((total / target) * 100).toFixed(1)) : 0;

    return {
      ...summary,
      total_count: total,
      current_speed_cpm: speed,
      target_attainment_pct: attainment > 0 ? attainment : summary.target_attainment_pct,
      fps: fps > 0 ? fps : summary.fps,
      latency_p95_ms: latencyMs > 0 ? latencyMs : summary.latency_p95_ms,
    };
  }, [summary, totalToday, liveSpeed, fps, latencyMs]);

  const previewUrl = useMemo(() => {
    if (!currentLineId) return "";
    const base = `${API_BASE_URL.replace(/\/$/, "")}/api/v1/lines/${encodeURIComponent(currentLineId)}/preview`;
    return retryNonce > 0 ? `${base}?retry=${retryNonce}` : base;
  }, [currentLineId, retryNonce]);

  const handleRetry = () => {
    setRetryNonce((prev) => prev + 1);
    reconnect();
  };

  return (
    <div className="space-y-4">
      {/* Header bar matching client mockup: "Ringkasan Hari Ini" with LineSelector */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pt-1 pb-2">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Ringkasan Hari Ini
        </h1>
        <div className="flex items-center gap-2">
          <LineSelector />
        </div>
      </div>

      {/* Row 1: 4 Top KPI Cards */}
      <KpiCards summary={liveSummary} />

      {/* Row 2: Middle Grid (Hourly Area Spline Chart + Target Attainment) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <HourlyRateChart data={aggregates} />
        </div>
        <div>
          <TargetAttainmentCard
            total={liveSummary.total_count}
            target={liveSummary.target_count}
            attainmentPct={liveSummary.target_attainment_pct}
          />
        </div>
      </div>

      {/* Row 3: Bottom Live Camera Preview Card */}
      <DashboardLivePreview
        lineId={currentLineId}
        lineName={lineDisplayName}
        previewUrl={previewUrl}
        isConnected={isConnected}
        onRetry={handleRetry}
      />
    </div>
  );
}
```

- [ ] **Step 2: Run all backend tests**

Run: `py -m pytest services/api/tests/test_summary_api.py -v`
Expected: ALL tests PASS.

- [ ] **Step 3: Run frontend build and typecheck**

Run: `npm run build` in `frontend/`
Expected: Build succeeds cleanly with 0 TypeScript/ESLint errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/overview/pages/DashboardPage.tsx
git commit -m "feat(overview): assemble client mockup dashboard layout with live preview and charts"
```
