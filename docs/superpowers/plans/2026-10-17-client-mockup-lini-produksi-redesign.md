# Client Mockup Lini Produksi Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the client mockup design for the Live Monitoring page (`/lini-produksi`) with live video overlay count, 3-metric system status card, live line alarms card, and operational threshold matrix table.

**Architecture:** Decompose the Live Monitoring view into modular React components (`SystemStatusCard`, `LiveAlarmsCard`, `ThresholdMatrixCard`, and `LiveVideoMonitor`) in `frontend/src/features/livestream/components/`, assembled into `LiniProduksiPage.tsx` with responsive Tailwind CSS grid layouts and Indonesian localization.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, Lucide React, FastAPI, SQLAlchemy.

## Global Constraints

- Indonesian language and locale conventions: number formatting using `id-ID` (dots for thousands, commas for decimals), dates/times in WIB.
- Tri-state camera and edge status indicators: `Online` (emerald-500), `Degraded` (amber-500), and `Offline` (rose-500).
- Backwards compatibility: Existing endpoints, SSE streams, and routing structures must not break.
- Clean TypeScript compilation: zero errors under strict mode (`npm run build`).

---

### Task 1: Implement `SystemStatusCard.tsx`

**Files:**
- Create: `frontend/src/features/livestream/components/SystemStatusCard.tsx`

**Interfaces:**
- Produces: `SystemStatusCard` component accepting `{ fps: number; latencyMs: number; streamState: "online" | "degraded" | "offline" | string; }`.

- [ ] **Step 1: Write `SystemStatusCard.tsx`**

```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface SystemStatusCardProps {
  fps?: number;
  latencyMs?: number;
  streamState?: "online" | "degraded" | "offline" | string;
}

export function SystemStatusCard({
  fps = 30,
  latencyMs = 42,
  streamState = "online",
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

  return (
    <Card className="rounded-2xl border-slate-200/80 shadow-xs bg-white">
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
            <span className="text-2xl font-bold tracking-tight text-slate-900">
              {Math.round(latencyMs)} <span className="text-sm font-normal text-slate-500">ms</span>
            </span>
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

- [ ] **Step 2: Verify TypeScript build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with 0 errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/livestream/components/SystemStatusCard.tsx
git commit -m "feat(livestream): add SystemStatusCard component"
```

---

### Task 2: Implement `LiveAlarmsCard.tsx`

**Files:**
- Create: `frontend/src/features/livestream/components/LiveAlarmsCard.tsx`

**Interfaces:**
- Consumes: `alarmsApi.list(lineId)` from `@/features/alarms`.
- Produces: `LiveAlarmsCard` component accepting `{ lineId: string; }`.

- [ ] **Step 1: Write `LiveAlarmsCard.tsx`**

```tsx
import { useEffect, useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { alarmsApi } from "@/features/alarms";
import type { AlarmDTO } from "@/types";

interface LiveAlarmsCardProps {
  lineId: string;
}

export function LiveAlarmsCard({ lineId }: LiveAlarmsCardProps) {
  const [alarms, setAlarms] = useState<AlarmDTO[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    const fetchAlarms = () => {
      if (!lineId) return;
      alarmsApi
        .list(lineId)
        .then((res) => {
          if (!isMounted) return;
          // Filter out resolved alarms
          const active = (res || []).filter((a) => a.status !== "RESOLVED");
          // Take top 4 most recent
          setAlarms(active.slice(0, 4));
          setLoading(false);
        })
        .catch(() => {
          if (isMounted) setLoading(false);
        });
    };

    fetchAlarms();
    const interval = setInterval(fetchAlarms, 10000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [lineId]);

  const formatTimestamp = (isoStr: string) => {
    if (!isoStr) return "-";
    try {
      const dt = new Date(isoStr);
      if (isNaN(dt.getTime())) return isoStr;
      const pad = (n: number) => String(n).padStart(2, "0");
      return `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())} ${pad(dt.getHours())}:${pad(dt.getMinutes())}:${pad(dt.getSeconds())}`;
    } catch {
      return isoStr;
    }
  };

  return (
    <Card className="rounded-2xl border-slate-200/80 shadow-xs bg-white">
      <CardHeader className="p-4 pb-2">
        <CardTitle className="text-sm font-semibold text-slate-800">
          Alarm &amp; Notifikasi
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 pt-2">
        {alarms.length === 0 ? (
          <div className="flex items-center gap-2.5 py-4 px-3 rounded-xl bg-slate-50 text-slate-500 text-xs">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>Tidak ada alarm aktif pada lini ini</span>
          </div>
        ) : (
          <div className="space-y-3">
            {alarms.map((alarm) => {
              const isCritical = alarm.severity.toUpperCase() === "CRITICAL";
              return (
                <div
                  key={alarm.id}
                  className="flex items-start justify-between gap-3 text-xs"
                >
                  <div className="flex items-start gap-2 min-w-0">
                    <span
                      className={`w-2 h-2 rounded-full mt-1 shrink-0 ${
                        isCritical ? "bg-rose-500 ring-2 ring-rose-100" : "bg-amber-500 ring-2 ring-amber-100"
                      }`}
                      aria-hidden="true"
                    />
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span
                          className={`font-bold ${
                            isCritical ? "text-rose-600" : "text-amber-600"
                          }`}
                        >
                          {isCritical ? "Kritis" : "Peringatan"}
                        </span>
                      </div>
                      <p className="text-slate-700 font-medium truncate mt-0.5">
                        {alarm.message}
                      </p>
                      <span className="text-[11px] text-slate-400 font-mono mt-0.5 block">
                        {formatTimestamp(alarm.opened_at)}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Verify TypeScript build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with 0 errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/livestream/components/LiveAlarmsCard.tsx
git commit -m "feat(livestream): add LiveAlarmsCard component"
```

---

### Task 3: Implement `ThresholdMatrixCard.tsx`

**Files:**
- Create: `frontend/src/features/livestream/components/ThresholdMatrixCard.tsx`

**Interfaces:**
- Produces: `ThresholdMatrixCard` component for plant operational thresholds reference.

- [ ] **Step 1: Write `ThresholdMatrixCard.tsx`**

```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

interface ThresholdRow {
  metric: string;
  warning: string;
  critical: string;
}

const THRESHOLD_DATA: ThresholdRow[] = [
  {
    metric: "Laju Produksi (ekor/menit)",
    warning: "< 130",
    critical: "< 110",
  },
  {
    metric: "Latensi (ms)",
    warning: "130",
    critical: "110",
  },
  {
    metric: "Akurasi Deteksi (%)",
    warning: "0.096",
    critical: "0.075",
  },
  {
    metric: "Downtime (menit)",
    warning: "17",
    critical: "10",
  },
];

export function ThresholdMatrixCard() {
  return (
    <Card className="rounded-2xl border-slate-200/80 shadow-xs bg-white">
      <CardHeader className="p-4 pb-2">
        <CardTitle className="text-sm font-semibold text-slate-800">
          Matriks Ambang Batas (Threshold Matrix)
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 pt-1">
        <div className="overflow-x-auto">
          <Table className="w-full text-xs">
            <TableHeader>
              <TableRow className="border-b border-slate-100 hover:bg-transparent">
                <TableHead className="w-1/2 text-slate-600 font-semibold py-2.5">
                  Metrik
                </TableHead>
                <TableHead className="w-1/4 text-amber-600 font-semibold py-2.5">
                  Peringatan (Amber)
                </TableHead>
                <TableHead className="w-1/4 text-rose-600 font-semibold py-2.5">
                  Kritis (Red)
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {THRESHOLD_DATA.map((row, idx) => (
                <TableRow
                  key={idx}
                  className="border-b border-slate-100/80 last:border-b-0 hover:bg-slate-50/50 transition-colors"
                >
                  <TableCell className="font-medium text-slate-800 py-3">
                    {row.metric}
                  </TableCell>
                  <TableCell className="font-semibold text-amber-700 py-3">
                    {row.warning}
                  </TableCell>
                  <TableCell className="font-semibold text-rose-700 py-3">
                    {row.critical}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Verify TypeScript build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with 0 errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/livestream/components/ThresholdMatrixCard.tsx
git commit -m "feat(livestream): add ThresholdMatrixCard component"
```

---

### Task 4: Implement `LiveVideoMonitor.tsx`

**Files:**
- Create: `frontend/src/features/livestream/components/LiveVideoMonitor.tsx`

**Interfaces:**
- Produces: `LiveVideoMonitor` component accepting:
  - `lineId: string`
  - `previewUrl: string`
  - `totalToday: number`
  - `isConnected: boolean`
  - `onRetry?: () => void`

- [ ] **Step 1: Write `LiveVideoMonitor.tsx`**

```tsx
import { useState, useEffect } from "react";
import { Play, Pause, RefreshCw, AlertCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface LiveVideoMonitorProps {
  lineId: string;
  previewUrl: string;
  totalToday: number;
  isConnected: boolean;
  onRetry?: () => void;
}

export function LiveVideoMonitor({
  lineId,
  previewUrl,
  totalToday,
  isConnected,
  onRetry,
}: LiveVideoMonitorProps) {
  const [isPlaying, setIsPlaying] = useState(true);
  const [imgError, setImgError] = useState(false);

  // Reset error when URL changes
  useEffect(() => {
    setImgError(false);
  }, [previewUrl]);

  const togglePlayback = () => {
    setIsPlaying((prev) => !prev);
  };

  const showOverlay = !isConnected || !previewUrl || imgError || !isPlaying;

  return (
    <Card className="rounded-2xl border-slate-200/80 shadow-xs bg-white overflow-hidden" data-line-id={lineId}>
      <CardHeader className="p-4 pb-2">
        <CardTitle className="text-sm font-semibold text-slate-800">
          Pratinjau Kamera Langsung
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 pt-1">
        <div className="relative aspect-[16/10] sm:aspect-[16/9] w-full rounded-xl bg-slate-950 overflow-hidden flex flex-col justify-between">
          {/* MJPEG Stream Image */}
          {isPlaying && previewUrl && !imgError && (
            <img
              src={previewUrl}
              alt="Live video stream"
              className="absolute inset-0 w-full h-full object-cover"
              onError={() => setImgError(true)}
            />
          )}

          {/* Overlay fallback for paused or disconnected states */}
          {showOverlay && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-950/85 text-slate-300 p-6 text-center z-10 backdrop-blur-xs">
              {!isPlaying ? (
                <div className="flex flex-col items-center gap-2">
                  <Pause className="w-8 h-8 text-slate-400" />
                  <p className="text-sm font-medium">Streaming Dijeda</p>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-3">
                  <AlertCircle className="w-8 h-8 text-rose-400" />
                  <div>
                    <p className="text-sm font-semibold text-slate-100">
                      Kamera Offline / Terputus
                    </p>
                    <p className="text-xs text-slate-400 mt-1 max-w-sm">
                      Menghubungi endpoint pratinjau deteksi ayam konveyor...
                    </p>
                  </div>
                  {onRetry && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setImgError(false);
                        onRetry();
                      }}
                      className="mt-1 bg-slate-800/80 border-slate-700 text-slate-200 hover:bg-slate-700 hover:text-white"
                    >
                      <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
                      Hubungkan Ulang
                    </Button>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Top LIVE Tag */}
          <div className="relative z-20 p-3 flex items-center justify-between pointer-events-none">
            <div className="flex items-center gap-1.5 bg-slate-900/80 backdrop-blur-xs px-2.5 py-1 rounded-full text-[11px] font-semibold text-white">
              <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
              <span>LIVE</span>
            </div>
          </div>

          {/* Overlay Bar Bottom: Terhitung Count */}
          <div className="relative z-20 w-full bg-[#1e293b]/90 backdrop-blur-xs text-white py-2.5 px-4 flex items-center justify-center border-t border-slate-800/60 shadow-md">
            <span className="text-lg sm:text-2xl font-bold tracking-tight text-white">
              Terhitung: {(totalToday ?? 0).toLocaleString("id-ID")}
            </span>
          </div>
        </div>

        {/* Player Controls Bar */}
        <div className="flex items-center justify-between mt-3 pt-2 border-t border-slate-100 text-xs text-slate-500">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={togglePlayback}
              className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-700 transition-colors"
              aria-label={isPlaying ? "Jeda streaming" : "Putar streaming"}
            >
              {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            </button>
            <span className="font-medium text-slate-700">
              {isPlaying ? "Live Streaming Aktif" : "Streaming Dijeda"}
            </span>
          </div>

          {onRetry && (
            <button
              type="button"
              onClick={() => {
                setImgError(false);
                onRetry();
              }}
              className="flex items-center gap-1.5 hover:text-slate-800 transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Muat Ulang</span>
            </button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Verify TypeScript build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with 0 errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/livestream/components/LiveVideoMonitor.tsx
git commit -m "feat(livestream): add LiveVideoMonitor component with count overlay"
```

---

### Task 5: Assemble `LiniProduksiPage.tsx` and End-to-End Verification

**Files:**
- Modify: `frontend/src/features/livestream/pages/LiniProduksiPage.tsx`

**Interfaces:**
- Consumes: `LiveVideoMonitor`, `SystemStatusCard`, `LiveAlarmsCard`, `ThresholdMatrixCard`.

- [ ] **Step 1: Update `LiniProduksiPage.tsx`**

```tsx
import { useMemo, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { LineSelector } from "@/components/layout/LineSelector";
import { StatusBadge } from "@/components/common/StatusBadge";
import { useAppContext } from "@/context/AppContext";
import { useLiveStream } from "@/hooks/useLiveStream";
import { API_BASE_URL } from "@/config/env";
import { LiveVideoMonitor } from "../components/LiveVideoMonitor";
import { SystemStatusCard } from "../components/SystemStatusCard";
import { LiveAlarmsCard } from "../components/LiveAlarmsCard";
import { ThresholdMatrixCard } from "../components/ThresholdMatrixCard";

export default function LiniProduksiPage() {
  const { currentLineId, lines, isConnected } = useAppContext();
  const { status, totalToday, fps, latencyMs, reconnect } =
    useLiveStream(currentLineId);
  const [retryNonce, setRetryNonce] = useState(0);

  const isStreaming = status === "CONNECTED";

  const selectedLine = useMemo(
    () => lines.find((l) => l.id === currentLineId),
    [lines, currentLineId]
  );

  const lineTitle = selectedLine?.name || currentLineId || "Lini A";

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
    <div className="space-y-5">
      <PageHeader
        title={`Live Monitoring: ${lineTitle}`}
        description="Streaming real-time dan deteksi konveyor ayam"
      >
        <StatusBadge isConnected={isConnected} />
        <LineSelector />
      </PageHeader>

      {/* Row 1: Video Monitor (Left) & Status + Alarms (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left Column: Live Video Monitor with Count Overlay */}
        <div className="lg:col-span-7">
          <LiveVideoMonitor
            lineId={currentLineId}
            previewUrl={previewUrl}
            totalToday={totalToday}
            isConnected={isStreaming}
            onRetry={handleRetry}
          />
        </div>

        {/* Right Column: System Status + Alarms & Notifikasi */}
        <div className="lg:col-span-5 space-y-4">
          <SystemStatusCard
            fps={fps ?? 30}
            latencyMs={latencyMs ?? 42}
            streamState={isStreaming ? "online" : "offline"}
          />
          <LiveAlarmsCard lineId={currentLineId} />
        </div>
      </div>

      {/* Row 2: Threshold Matrix Card (Full Width) */}
      <div>
        <ThresholdMatrixCard />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Run full backend and frontend validation**

Run: `npm run build` in `frontend/`
Expected: 0 errors, TypeScript compiles cleanly.

Run: `py -m pytest services/api/tests/ -v`
Expected: 143/143 tests pass.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/livestream/pages/LiniProduksiPage.tsx
git commit -m "feat(livestream): assemble client mockup layout for LiniProduksiPage"
```
