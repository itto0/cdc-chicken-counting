import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import ReactECharts from "echarts-for-react";
import {
  Activity,
  Gauge,
  Video,
  TrendingUp,
  Target,
  Clock,
  Sparkles,
  Server,
  AlertTriangle,
  ArrowRight,
  RotateCw,
  Calendar,
  Radio,
} from "lucide-react";
import type { TabKey, LineSummary, LineSummaryResponse, AggregateItemDTO } from "../types";
import { useAppContext } from "../context/AppContext";
import { apiClient } from "../services/apiClient";
import { useLiveStream } from "../hooks/useLiveStream";

export type PeriodKey = "today" | "shift" | "week";

export interface OverviewViewProps {
  summary?: LineSummary;
  onNavigateTab?: (tab: TabKey) => void;
}

const PERIOD_OPTIONS: Array<{ key: PeriodKey; label: string; periodLabel: string }> = [
  { key: "today", label: "Hari Ini", periodLabel: "Total Hari Ini" },
  { key: "shift", label: "Shift Ini", periodLabel: "Total Shift Ini" },
  { key: "week", label: "7 Hari Terakhir", periodLabel: "Total 7 Hari Terakhir" },
];

const DEFAULT_FALLBACK_SUMMARY: LineSummaryResponse = {
  line_id: "line-1",
  period: "today",
  total_count: 48320,
  target_count: 62000,
  target_attainment_pct: 77.9,
  current_speed_cpm: 118,
  target_speed_cpm: 120,
  active_alarms_count: 1,
  camera_status: "online",
  last_event_time: null,
  fps: 30.0,
  latency_p95_ms: 38.0,
};

// Hourly counts fallback for shifts 08:00 - 17:00 WIB
const HOURLY_FALLBACK = [
  { time: "08:00", count: 5120, rate: 102 },
  { time: "09:00", count: 6840, rate: 124 },
  { time: "10:00", count: 7210, rate: 128 },
  { time: "11:00", count: 6950, rate: 122 },
  { time: "12:00", count: 2100, rate: 45 },
  { time: "13:00", count: 6400, rate: 116 },
  { time: "14:00", count: 7100, rate: 126 },
  { time: "15:00", count: 6600, rate: 119 },
  { time: "16:00", count: 0, rate: 0 },
  { time: "17:00", count: 0, rate: 0 },
];

export function OverviewView({ summary: initialPropSummary, onNavigateTab }: OverviewViewProps) {
  const { currentLineId, lines } = useAppContext();
  const currentLine = lines.find((l) => l.id === currentLineId) || lines[0];

  const [period, setPeriod] = useState<PeriodKey>("today");
  const [summaryData, setSummaryData] = useState<LineSummaryResponse>(() => {
    if (initialPropSummary) {
      return {
        line_id: initialPropSummary.line_id || currentLineId || "line-1",
        period: "today",
        total_count: initialPropSummary.total_today ?? 48320,
        target_count: initialPropSummary.target ?? 62000,
        target_attainment_pct: initialPropSummary.attainment_pct ?? 77.9,
        current_speed_cpm: initialPropSummary.avg_rate_per_min ?? 118,
        target_speed_cpm: 120,
        active_alarms_count: 0,
        camera_status: initialPropSummary.camera_status ?? "online",
        last_event_time: null,
        fps: 30.0,
        latency_p95_ms: 38.0,
      };
    }
    return DEFAULT_FALLBACK_SUMMARY;
  });

  const [aggregates, setAggregates] = useState<AggregateItemDTO[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [liveCountDelta, setLiveCountDelta] = useState<number>(0);
  const [isFlashing, setIsFlashing] = useState<boolean>(false);

  const flashTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const prevTickRef = useRef<number>(0);

  // Hook connecting to SSE real-time telemetry stream
  const liveStream = useLiveStream(currentLineId);

  // Load summary and aggregate metrics from API
  const fetchData = useCallback(
    async (lineId: string, currentPeriod: PeriodKey) => {
      setIsLoading(true);
      try {
        const [sumRes, countsRes] = await Promise.allSettled([
          apiClient.getLineSummary(lineId, currentPeriod),
          apiClient.getLineCounts(lineId, { granularity: "hourly" }),
        ]);

        if (sumRes.status === "fulfilled" && sumRes.value) {
          setSummaryData(sumRes.value);
          setLiveCountDelta(0);
        }

        if (countsRes.status === "fulfilled" && countsRes.value) {
          setAggregates(countsRes.value.aggregates || []);
        } else {
          setAggregates([]);
        }
      } catch (err) {
        console.warn("Failed to fetch overview metrics, falling back to cached state:", err);
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  // Trigger fetch when currentLineId or period changes
  useEffect(() => {
    fetchData(currentLineId, period);
  }, [currentLineId, period, fetchData]);

  // Handle SSE count tick increment and pulse animation
  useEffect(() => {
    if (liveStream.countTick > 0 && liveStream.countTick !== prevTickRef.current) {
      prevTickRef.current = liveStream.countTick;
      setLiveCountDelta((prev) => prev + 1);

      setIsFlashing(true);
      if (flashTimeoutRef.current) clearTimeout(flashTimeoutRef.current);
      flashTimeoutRef.current = setTimeout(() => {
        setIsFlashing(false);
      }, 750);
    }
  }, [liveStream.countTick]);

  // Synchronize count if liveStream.totalToday arrives with an absolute count higher than base + delta
  useEffect(() => {
    if (period === "today" && liveStream.totalToday > 0) {
      const currentCalculated = summaryData.total_count + liveCountDelta;
      if (liveStream.totalToday > currentCalculated) {
        setLiveCountDelta(liveStream.totalToday - summaryData.total_count);
        setIsFlashing(true);
        if (flashTimeoutRef.current) clearTimeout(flashTimeoutRef.current);
        flashTimeoutRef.current = setTimeout(() => {
          setIsFlashing(false);
        }, 750);
      }
    }
  }, [liveStream.totalToday, period, summaryData.total_count, liveCountDelta]);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (flashTimeoutRef.current) clearTimeout(flashTimeoutRef.current);
    };
  }, []);

  // Compute calculated metrics
  const effectiveTotalCount = Math.max(0, summaryData.total_count + liveCountDelta);
  const targetCount = summaryData.target_count || currentLine?.daily_target || 62000;
  const remainingBirds = Math.max(0, targetCount - effectiveTotalCount);
  const attainmentPct =
    targetCount > 0 ? Math.round((effectiveTotalCount / targetCount) * 1000) / 10 : 0.0;
  const attainmentRateGauge = Math.min(100, attainmentPct);

  // Effective live speed (CPM)
  const effectiveLiveSpeed =
    liveStream.status === "CONNECTED" && liveStream.liveSpeed > 0
      ? liveStream.liveSpeed
      : summaryData.current_speed_cpm;

  // Effective camera status & system health
  const effectiveCameraStatus =
    liveStream.status === "CONNECTED" && liveStream.streamState
      ? liveStream.streamState.toLowerCase()
      : (summaryData.camera_status || "offline").toLowerCase();

  const effectiveFps = liveStream.fps > 0 ? liveStream.fps : summaryData.fps;
  const effectiveLatency =
    liveStream.latencyMs > 0 ? liveStream.latencyMs : summaryData.latency_p95_ms;

  // Active alarms count
  const activeAlarmsCount = summaryData.active_alarms_count;

  // Period label
  const activePeriodConfig =
    PERIOD_OPTIONS.find((p) => p.key === period) || PERIOD_OPTIONS[0];

  // Conveyor speed status evaluation
  const speedTier = useMemo(() => {
    if (effectiveLiveSpeed <= 0) {
      return {
        label: "Konveyor Siaga",
        badgeClass: "bg-slate-700/80 text-slate-300 border-slate-600/80",
      };
    }
    if (effectiveLiveSpeed < 30) {
      return {
        label: "Under-speed (< 30 CPM)",
        badgeClass: "bg-amber-950/70 text-amber-300 border-amber-800/60",
      };
    }
    if (effectiveLiveSpeed <= 130) {
      return {
        label: "Kecepatan Optimal",
        badgeClass: "bg-emerald-950/70 text-emerald-300 border-emerald-800/60",
      };
    }
    return {
      label: "Over-speed (> 130 CPM)",
      badgeClass: "bg-rose-950/70 text-rose-300 border-rose-800/60",
    };
  }, [effectiveLiveSpeed]);

  // Hourly chart dataset: use real aggregates if available; otherwise fallback to standard shift
  const chartItems = useMemo(() => {
    if (aggregates && aggregates.length > 0) {
      return aggregates.map((agg) => {
        let label = agg.bucket;
        try {
          const d = new Date(agg.bucket);
          if (!isNaN(d.getTime())) {
            label = d.toLocaleTimeString("id-ID", {
              hour: "2-digit",
              minute: "2-digit",
              hour12: false,
              timeZone: "Asia/Jakarta",
            });
          }
        } catch {
          // fallback
        }
        return {
          time: label,
          count: agg.count,
          rate: Math.round(agg.rate_per_min),
        };
      });
    }
    return HOURLY_FALLBACK;
  }, [aggregates]);

  const isUsingRealHourlyData = aggregates.length > 0;

  // ECharts Trend Area Chart Option
  const trendOption = useMemo(() => {
    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        backgroundColor: "#1e293b",
        borderColor: "#475569",
        borderWidth: 1,
        textStyle: { color: "#f8fafc", fontSize: 12 },
        formatter: (params: Array<{ name: string; value: number; dataIndex: number }>) => {
          const item = params[0];
          if (!item) return "";
          const meta = chartItems[item.dataIndex];
          return `
            <div style="font-weight: 600; margin-bottom: 4px; color: #34d399;">
              Pukul ${item.name} WIB
            </div>
            <div>Volume: <strong>${(item.value || 0).toLocaleString()}</strong> ekor</div>
            <div style="color: #94a3b8; font-size: 11px;">Kecepatan: ~${meta?.rate || 0} birds/min</div>
          `;
        },
      },
      grid: {
        top: "12%",
        left: "3%",
        right: "4%",
        bottom: "8%",
        containLabel: true,
      },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: chartItems.map((d) => d.time),
        axisLine: { lineStyle: { color: "#475569" } },
        axisLabel: { color: "#94a3b8", fontSize: 12 },
      },
      yAxis: {
        type: "value",
        name: "Ekor / Jam",
        nameTextStyle: { color: "#64748b", fontSize: 11 },
        splitLine: {
          lineStyle: { color: "#334155", type: "dashed" },
        },
        axisLabel: {
          color: "#94a3b8",
          fontSize: 11,
          formatter: (val: number) => (val >= 1000 ? `${val / 1000}k` : `${val}`),
        },
      },
      series: [
        {
          name: "Penghitungan Ayam",
          type: "line",
          smooth: true,
          showSymbol: true,
          symbolSize: 6,
          itemStyle: {
            color: "#10b981",
            borderWidth: 2,
            borderColor: "#065f46",
          },
          lineStyle: {
            width: 3,
            color: "#10b981",
          },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(16, 185, 129, 0.45)" },
                { offset: 0.8, color: "rgba(16, 185, 129, 0.05)" },
                { offset: 1, color: "rgba(16, 185, 129, 0)" },
              ],
            },
          },
          data: chartItems.map((d) => d.count),
        },
      ],
    };
  }, [chartItems]);

  // ECharts Radial Attainment Gauge Option
  const gaugeOption = useMemo(() => {
    return {
      backgroundColor: "transparent",
      series: [
        {
          type: "gauge",
          startAngle: 200,
          endAngle: -20,
          min: 0,
          max: 100,
          splitNumber: 5,
          itemStyle: {
            color: "#10b981",
          },
          progress: {
            show: true,
            width: 14,
            roundCap: true,
            itemStyle: {
              color: {
                type: "linear",
                x: 0,
                y: 0,
                x2: 1,
                y2: 0,
                colorStops: [
                  { offset: 0, color: "#06b6d4" },
                  { offset: 1, color: "#10b981" },
                ],
              },
            },
          },
          pointer: {
            show: false,
          },
          axisLine: {
            roundCap: true,
            lineStyle: {
              width: 14,
              color: [[1, "#1e293b"]],
            },
          },
          axisTick: {
            show: false,
          },
          splitLine: {
            show: false,
          },
          axisLabel: {
            show: false,
          },
          title: {
            show: true,
            offsetCenter: [0, "30%"],
            fontSize: 12,
            color: "#94a3b8",
          },
          detail: {
            valueAnimation: true,
            offsetCenter: [0, "-10%"],
            fontSize: 28,
            fontWeight: "bold",
            formatter: "{value}%",
            color: "#34d399",
          },
          data: [
            {
              value: attainmentPct,
              name: "Pencapaian Target",
            },
          ],
        },
      ],
    };
  }, [attainmentPct]);

  // Compute footer stats for chart
  const chartStats = useMemo(() => {
    const nonZero = chartItems.filter((item) => item.count > 0);
    const sum = chartItems.reduce((acc, item) => acc + item.count, 0);
    const avg = nonZero.length > 0 ? Math.round(sum / nonZero.length) : 0;
    const peak = chartItems.reduce(
      (max, item) => (item.count > max.count ? item : max),
      chartItems[0] || { count: 0, time: "-" }
    );
    return {
      avgPerHour: avg,
      peakTime: peak?.time || "-",
      peakCount: peak?.count || 0,
    };
  }, [chartItems]);

  return (
    <div className="space-y-6">
      {/* Header Info / Status Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-slate-800/80 border border-slate-700/80 px-5 py-3.5 rounded-lg shadow-sm">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-emerald-500/10 border border-emerald-500/20 rounded-md text-emerald-400">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
              <span>{currentLine?.name || `Conveyor ${currentLineId}`}</span>
              <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-medium">
                Aktif · Produksi Normal
              </span>
            </h3>
            <p className="text-xs text-slate-400">
              Shift Operasional: 08:00 – 17:00 WIB · Target Kuota {targetCount.toLocaleString()} Ekor
            </p>
          </div>
        </div>

        {/* Period Filter Selector & Controls */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Period Filter Selector Pills */}
          <div
            className="flex items-center gap-1 bg-slate-900/90 p-1 rounded-lg border border-slate-700/80"
            role="group"
            aria-label="Filter Periode Waktu"
          >
            <Calendar className="w-3.5 h-3.5 text-slate-400 ml-1.5 mr-0.5" />
            {PERIOD_OPTIONS.map((p) => {
              const isSelected = period === p.key;
              return (
                <button
                  key={p.key}
                  type="button"
                  onClick={() => setPeriod(p.key)}
                  className={`px-2.5 py-1 text-xs font-semibold rounded-md transition ${
                    isSelected
                      ? "bg-emerald-600 text-white shadow-sm"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
                  }`}
                >
                  {p.label}
                </button>
              );
            })}
          </div>

          {/* Refresh Action Button */}
          <button
            type="button"
            onClick={() => fetchData(currentLineId, period)}
            disabled={isLoading}
            title="Muat ulang data ringkasan"
            className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-700/60 rounded-md border border-slate-700 transition"
          >
            <RotateCw className={`w-4 h-4 ${isLoading ? "animate-spin text-emerald-400" : ""}`} />
          </button>

          {/* Live Telemetry Status Pill */}
          <div className="hidden sm:flex items-center gap-2 text-xs text-slate-400 border-l border-slate-700 pl-3">
            <div className="flex items-center gap-1.5">
              <Radio
                className={`w-3.5 h-3.5 ${
                  liveStream.status === "CONNECTED" ? "text-emerald-400 animate-pulse" : "text-amber-400"
                }`}
              />
              <span className="text-slate-300 font-medium">
                {liveStream.status === "CONNECTED" ? "Telemetri Live" : "Telemetri Siaga"}
              </span>
            </div>
            <div className="flex items-center gap-1.5 ml-2">
              <Server className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-slate-300 font-medium">Edge Online</span>
            </div>
          </div>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Total Counts (with Live Increment Pulse) */}
        <div
          className={`bg-slate-800 border p-5 rounded-lg shadow-sm transition-all duration-300 ${
            isFlashing
              ? "border-emerald-400/90 bg-emerald-950/40 ring-2 ring-emerald-500/50 shadow-emerald-500/20"
              : "border-slate-700 hover:border-slate-600"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-slate-400">
              {activePeriodConfig.periodLabel}
            </span>
            <div
              className={`p-2 rounded-md transition-colors duration-300 ${
                isFlashing ? "bg-emerald-400 text-slate-900" : "bg-emerald-500/10 text-emerald-400"
              }`}
            >
              <TrendingUp className="w-4 h-4" />
            </div>
          </div>

          <div className="flex items-baseline gap-2 mt-2">
            <span
              className={`text-3xl font-extrabold transition-all duration-300 ${
                isFlashing
                  ? "text-emerald-300 scale-105 drop-shadow-[0_0_10px_rgba(52,211,153,0.8)]"
                  : "text-emerald-400"
              }`}
            >
              {effectiveTotalCount.toLocaleString()}
            </span>
            {isFlashing && (
              <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-300 bg-emerald-900/80 px-2 py-0.5 rounded-full border border-emerald-500/50 animate-pulse">
                <Sparkles className="w-3 h-3" />
                <span>+1 LIVE</span>
              </span>
            )}
          </div>

          <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-700/60">
            <span className="text-xs text-slate-500">
              {liveCountDelta > 0 ? `+${liveCountDelta} deteksi sesi ini` : "Ekor ayam terhitung"}
            </span>
            <span className="text-xs font-medium text-emerald-400/90 bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-800/40">
              {liveStream.status === "CONNECTED" ? "Live Stream Aktif" : "Tersinkronisasi"}
            </span>
          </div>
        </div>

        {/* Card 2: Kecepatan Konveyor (CPM) */}
        <div className="bg-slate-800 border border-slate-700 p-5 rounded-lg shadow-sm hover:border-slate-600 transition">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-slate-400">Kecepatan Konveyor</span>
            <div className="p-2 bg-cyan-500/10 text-cyan-400 rounded-md">
              <Gauge className="w-4 h-4" />
            </div>
          </div>

          <div className="flex items-baseline gap-1.5 mt-2">
            <span className="text-3xl font-extrabold text-cyan-400">
              {effectiveLiveSpeed.toFixed(effectiveLiveSpeed % 1 === 0 ? 0 : 1)}
            </span>
            <span className="text-sm font-medium text-slate-400">CPM</span>
            {liveStream.liveSpeed > 0 && (
              <span className="ml-1 text-[10px] font-semibold text-cyan-300 bg-cyan-950 px-1.5 py-0.5 rounded border border-cyan-800/60">
                LIVE
              </span>
            )}
          </div>

          <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-700/60">
            <span className="text-xs text-slate-500">
              Rata-rata: {summaryData.current_speed_cpm.toFixed(0)} · Target:{" "}
              {summaryData.target_speed_cpm || 120} CPM
            </span>
            <span className={`text-xs font-medium px-1.5 py-0.5 rounded border ${speedTier.badgeClass}`}>
              {speedTier.label}
            </span>
          </div>
        </div>

        {/* Card 3: Status Kamera & System Health */}
        <div className="bg-slate-800 border border-slate-700 p-5 rounded-lg shadow-sm hover:border-slate-600 transition">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-slate-400">Status Kamera & AI</span>
            <div className="p-2 bg-indigo-500/10 text-indigo-400 rounded-md">
              <Video className="w-4 h-4" />
            </div>
          </div>

          <div className="flex items-center gap-2.5 mt-2">
            <span
              className={`w-3.5 h-3.5 rounded-full ${
                effectiveCameraStatus === "online"
                  ? "bg-emerald-500 shadow-lg shadow-emerald-500/50 animate-pulse"
                  : effectiveCameraStatus === "degraded"
                  ? "bg-amber-500 shadow-lg shadow-amber-500/50"
                  : "bg-red-500 shadow-lg shadow-red-500/50"
              }`}
            />
            <span className="text-2xl font-bold uppercase tracking-wide text-slate-100">
              {effectiveCameraStatus}
            </span>
          </div>

          <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-700/60">
            <span className="text-xs text-slate-500">
              {effectiveFps.toFixed(1)} FPS · Latensi {effectiveLatency.toFixed(0)}ms
            </span>
            <span className="text-xs font-mono text-slate-400">1080p RTSP</span>
          </div>
        </div>

        {/* Card 4: Active Alarms Badge & Link */}
        <div className="bg-slate-800 border border-slate-700 p-5 rounded-lg shadow-sm hover:border-slate-600 transition">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-slate-400">Alarm Sistem</span>
            <div
              className={`p-2 rounded-md ${
                activeAlarmsCount > 0
                  ? "bg-amber-500/20 text-amber-400"
                  : "bg-emerald-500/10 text-emerald-400"
              }`}
            >
              <AlertTriangle className="w-4 h-4" />
            </div>
          </div>

          <div className="flex items-baseline gap-2 mt-2">
            <span
              className={`text-3xl font-extrabold ${
                activeAlarmsCount > 0 ? "text-amber-400" : "text-emerald-400"
              }`}
            >
              {activeAlarmsCount}
            </span>
            <span className="text-sm font-medium text-slate-400">Insiden Aktif</span>
          </div>

          <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-700/60">
            <span className="text-xs text-slate-500">
              {activeAlarmsCount > 0 ? "Perlu perhatian operator" : "Semua parameter normal"}
            </span>
            <button
              type="button"
              onClick={() => onNavigateTab?.("alarms")}
              className={`inline-flex items-center gap-1 text-xs font-medium transition cursor-pointer ${
                activeAlarmsCount > 0
                  ? "text-amber-400 hover:text-amber-300 font-semibold"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <span>{activeAlarmsCount > 0 ? "Buka Tab Alarms" : "Lihat Alarms"}</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Target Progress Bar & Attainment Gauge Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Target Attainment Radial Gauge & Breakdown Card */}
        <div className="bg-slate-800 border border-slate-700 p-6 rounded-lg shadow flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Target className="w-5 h-5 text-emerald-400" />
                <h4 className="font-semibold text-slate-200">Pencapaian Target Produksi</h4>
              </div>
              <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold">
                {activePeriodConfig.label}
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Evaluasi target kuota produksi pemotongan unggas per siklus
            </p>
          </div>

          {/* Radial Attainment Gauge */}
          <div className="h-44 w-full -my-2 flex items-center justify-center">
            <ReactECharts
              option={gaugeOption}
              style={{ height: "100%", width: "100%" }}
              notMerge={true}
              lazyUpdate={true}
            />
          </div>

          {/* Metric Breakdown */}
          <div className="space-y-3 pt-2 border-t border-slate-700/60">
            <div className="flex justify-between items-center text-sm">
              <span className="text-slate-400">Target Kuota:</span>
              <span className="font-semibold text-slate-200">
                {targetCount.toLocaleString()} ekor
              </span>
            </div>
            <div className="flex justify-between items-center text-sm">
              <span className="text-slate-400">Realisasi Saat Ini:</span>
              <span className="font-semibold text-emerald-400">
                {effectiveTotalCount.toLocaleString()} ekor
              </span>
            </div>
            <div className="flex justify-between items-center text-sm">
              <span className="text-slate-400">Sisa Kuota:</span>
              <span className="font-semibold text-amber-400">
                {remainingBirds.toLocaleString()} ekor
              </span>
            </div>

            {/* Attainment Progress Bar */}
            <div className="pt-2">
              <div className="flex justify-between items-center text-xs mb-1.5 text-slate-400">
                <span>Progress: {attainmentPct}%</span>
                <span>Target: 100%</span>
              </div>
              <div className="w-full bg-slate-700 h-3 rounded-full overflow-hidden">
                <div
                  className="bg-gradient-to-r from-cyan-500 to-emerald-500 h-full rounded-full transition-all duration-700"
                  style={{ width: `${attainmentRateGauge}%` }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Hourly Trend Area Chart Card */}
        <div className="lg:col-span-2 bg-slate-800 border border-slate-700 p-6 rounded-lg shadow flex flex-col justify-between">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
            <div>
              <div className="flex items-center gap-2">
                <Activity className="w-5 h-5 text-emerald-400" />
                <h4 className="font-semibold text-slate-200">Distribusi Penghitungan Per Jam</h4>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Volume throughput ayam melewati garis counter kamera
              </p>
            </div>
            <div className="flex items-center gap-2.5 text-xs">
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-sm bg-emerald-500 inline-block" />
                <span className="text-slate-300">
                  {isUsingRealHourlyData ? "Data API Riil" : "Distribusi Standar Shift"}
                </span>
              </div>
              <span className="text-slate-500">·</span>
              <span className="text-slate-400">
                Puncak: {chartStats.peakTime} ({chartStats.peakCount.toLocaleString()} ekor)
              </span>
            </div>
          </div>

          {/* ECharts Area Chart or Clean Empty State */}
          <div className="w-full h-72">
            {chartItems.length > 0 ? (
              <ReactECharts
                option={trendOption}
                style={{ height: "100%", width: "100%" }}
                notMerge={true}
                lazyUpdate={true}
              />
            ) : (
              <div className="w-full h-full flex flex-col items-center justify-center text-center p-6 bg-slate-900/40 rounded-lg border border-dashed border-slate-700">
                <Activity className="w-10 h-10 text-slate-500 mb-2 stroke-[1.5]" />
                <h5 className="text-sm font-medium text-slate-300">Belum Ada Data Agregat Per Jam</h5>
                <p className="text-xs text-slate-500 max-w-sm mt-1">
                  Data agregat per jam akan muncul otomatis setelah konveyor beroperasi dan menghasilkan riwayat penghitungan.
                </p>
              </div>
            )}
          </div>

          {/* Footer Highlights */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-slate-700/60 text-xs">
            <div>
              <span className="text-slate-500 block">Rata-rata/Jam</span>
              <span className="font-semibold text-slate-200 text-sm">
                {chartStats.avgPerHour.toLocaleString()} ekor
              </span>
            </div>
            <div>
              <span className="text-slate-500 block">Jam Puncak</span>
              <span className="font-semibold text-emerald-400 text-sm">
                {chartStats.peakTime}
              </span>
            </div>
            <div>
              <span className="text-slate-500 block">Throughput Aktif</span>
              <span className="font-semibold text-cyan-400 text-sm">
                {effectiveLiveSpeed.toFixed(0)} birds/min
              </span>
            </div>
            <div>
              <span className="text-slate-500 block">Pembaruan Telemetri</span>
              <span className="font-semibold text-slate-200 text-sm flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-slate-400 inline" />
                <span>Real-time</span>
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default OverviewView;
