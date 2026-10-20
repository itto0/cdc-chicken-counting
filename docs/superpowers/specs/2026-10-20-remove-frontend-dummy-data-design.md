# Design Specification: Removal of Frontend Dummy Data

- **Date:** 2026-10-20
- **Status:** Approved
- **Scope:** Frontend Application (`frontend/src/`)

## 1. Overview & Objective

During initial mockup prototyping and interface development, several frontend components incorporated mock datasets and synthetic fallback numbers to demonstrate visual appearances when disconnected from a live backend.

In production and operational poultry slaughterhouse environments, displaying simulated chicken counts (e.g. 520 birds/hr), phantom alarms (e.g. fabricated low speed alert), or synthetic baseline metrics (e.g. 120 cpm, 99.2% accuracy) is confusing and misleading to plant operators.

This specification outlines the removal of all hardcoded mock curves, fake report entries, fabricated alarms, and synthetic fallback numbers, replacing them with authentic zero-states, honest unmeasured indicators (`-`), and clean empty-state placeholders.

---

## 2. Component Specifications

### 2.1 `HourlyRateChart.tsx` (Dashboard Hourly Rate Spline Chart)
- **Current Behavior:** If `data` is empty, it injects `defaultTimes` (`["08:00", ..., "17:00"]`) and `defaultCounts` (`[120, 280, 240, 390, 310, 520, 380, 420, 260, 410]`).
- **New Behavior:**
  - Remove `defaultTimes` and `defaultCounts`.
  - When `data` is empty or all counts are zero, render a clean card-level empty state:
    - An empty chart container with an informative message: *"Belum ada data penghitungan hari ini"* and a subtle icon (`BarChart3` or `LineChart`).
  - When real aggregates exist, render the standard ECharts area spline chart with actual hours and counts.

### 2.2 `LaporanPage.tsx` (Reports & Historical Logs)
- **Current Behavior:** If all line requests fail (`allFailed && items.length === 0`), it injects 4 hardcoded sample rows (`sample-1` through `sample-4`) with fake dates (`17 Okt 2026`), counts (`7120`, `6840`, `7300`, `5950`), and statuses.
- **New Behavior:**
  - Completely remove the injection block of `sample-1` .. `sample-4`.
  - When API calls fail or return no aggregates, `rawRows` remains `[]`.
  - The table renders the genuine empty state: *"Belum ada riwayat data penghitungan untuk filter yang dipilih"*.
  - `summaryMetrics` calculates strictly from filtered real rows:
    - `totalCount`: 0
    - `avgRateCpm`: 0
    - `avgAccuracyPct`: 0 (or null)
    - `totalOperationMinutes`: 0

### 2.3 `AlarmPage.tsx` (Alarms & Anomalies)
- **Current Behavior:** When `alarmsApi.list()` fails in `.catch()`, it sets a fabricated active alarm (`LOW_SPEED`, `Kecepatan di bawah target (84 cpm < 120 cpm)`).
- **New Behavior:**
  - Remove the fallback sample alarm injection in `.catch()`.
  - On error or empty list, `alarms` remains `[]`.
  - The table renders the standard empty state: *"Tidak ada data alarm yang tercatat"*.

### 2.4 `KpiCards.tsx` & `DashboardPage.tsx` (Top Summary Cards)
- **Current Behavior:**
  - `KpiCards.tsx`: `Math.round(summary.current_speed_cpm ?? 120)`
  - `KpiCards.tsx`: `summary.detection_accuracy_pct ?? 99.2`
  - `DashboardPage.tsx`: `FALLBACK_SUMMARY` has `target_speed_cpm: 120.0`, `detection_accuracy_pct: 99.2`.
- **New Behavior:**
  - `current_speed_cpm`: fallback to `0` instead of `120`.
  - `detection_accuracy_pct`: if `summary.total_count === 0` or accuracy is not recorded, display `"-"` instead of fabricating `99.2%`.
  - `FALLBACK_SUMMARY.detection_accuracy_pct` set to `0.0`.

### 2.5 `SystemStatusCard.tsx` & `LiniProduksiPage.tsx` (Live Video & Telemetry)
- **Current Behavior:**
  - `LiniProduksiPage.tsx`: `fps={fps ?? 30}`, `latencyMs={latencyMs ?? 42}`.
  - `SystemStatusCard.tsx`: default props `fps = 30`, `latencyMs = 42`.
- **New Behavior:**
  - In `LiniProduksiPage.tsx`: pass real values `fps={fps ?? 0}` and `latencyMs={latencyMs ?? 0}`.
  - In `SystemStatusCard.tsx`: default props `fps = 0`, `latencyMs = 0`, `streamState = "offline"`.
  - Display `-` for latency when offline or latency is 0.

### 2.6 `AppContext.tsx` (Offline Line Fallback)
- **Current Behavior:** `FALLBACK_MOCK_LINE` sets `status: "online"`.
- **New Behavior:** If `FALLBACK_MOCK_LINE` is needed as an emergency fallback object, set its `status: "offline"` and total to 0, ensuring offline lines are never presented as online.

---

## 3. Data Flow & State Diagram

```
[ Backend API / SSE ]
        │
        ├── Real Data Received ───► Render Authentic Values (Counts, Rates, Alarms, Curves)
        │
        ├── Empty Data ([]) ──────► Render Clean Empty States (0 Birds, 0 CPM, "-" Accuracy, Empty Table)
        │
        └── Network / API Error ──► StatusBadge ("Terputus") + Empty Lists (NO fake sample injections)
```

---

## 4. Verification & Testing

1. **Unit & Component Testing:**
   - Test `HourlyRateChart` with empty array `[]` -> verifies empty state message is shown without error.
   - Test `LaporanPage` when API returns empty or rejects -> verifies `rawRows` is empty and no sample IDs exist.
   - Test `AlarmPage` when API rejects -> verifies `alarms` is empty.
   - Test `KpiCards` with zero/null speed and accuracy -> verifies 0 and `-` display.
2. **Build Verification:**
   - Execute `npm run build` in `frontend/` to guarantee TypeScript types and bundle integrity.
