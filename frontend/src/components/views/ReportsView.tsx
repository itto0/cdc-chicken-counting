import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import ReactECharts from "echarts-for-react";
import {
  Calendar,
  FileSpreadsheet,
  FileDown,
  RotateCw,
  Layers,
  Gauge,
  Clock,
  Activity,
  CheckCircle2,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  TrendingUp,
} from "lucide-react";
import { useAppContext } from "../../context/AppContext";
import { apiClient } from "../../services/apiClient";
import type { AggregateItemDTO, CountEventDTO, PaginationMeta } from "../../types";

export type DatePresetKey = "today" | "yesterday" | "last7days";

export interface PresetOption {
  key: DatePresetKey;
  label: string;
}

export const DATE_PRESETS: PresetOption[] = [
  { key: "today", label: "Hari Ini" },
  { key: "yesterday", label: "Kemarin" },
  { key: "last7days", label: "7 Hari Terakhir" },
];

export interface ReportsViewProps {
  lineId?: string;
}

// Fallback aggregates for today (shifts 08:00 - 15:00 WIB)
export const MOCK_HOURLY_TODAY: AggregateItemDTO[] = [
  { bucket: "2026-10-16T08:00:00+07:00", count: 5120, rate_per_min: 102, status: "NORMAL" },
  { bucket: "2026-10-16T09:00:00+07:00", count: 6840, rate_per_min: 124, status: "NORMAL" },
  { bucket: "2026-10-16T10:00:00+07:00", count: 7210, rate_per_min: 128, status: "NORMAL" },
  { bucket: "2026-10-16T11:00:00+07:00", count: 6950, rate_per_min: 122, status: "NORMAL" },
  { bucket: "2026-10-16T12:00:00+07:00", count: 2100, rate_per_min: 45, status: "WARNING" },
  { bucket: "2026-10-16T13:00:00+07:00", count: 6400, rate_per_min: 116, status: "NORMAL" },
  { bucket: "2026-10-16T14:00:00+07:00", count: 7100, rate_per_min: 126, status: "NORMAL" },
  { bucket: "2026-10-16T15:00:00+07:00", count: 6600, rate_per_min: 119, status: "NORMAL" },
];

// Fallback aggregates for yesterday
export const MOCK_HOURLY_YESTERDAY: AggregateItemDTO[] = [
  { bucket: "2026-10-15T08:00:00+07:00", count: 4950, rate_per_min: 99, status: "NORMAL" },
  { bucket: "2026-10-15T09:00:00+07:00", count: 6700, rate_per_min: 121, status: "NORMAL" },
  { bucket: "2026-10-15T10:00:00+07:00", count: 7050, rate_per_min: 125, status: "NORMAL" },
  { bucket: "2026-10-15T11:00:00+07:00", count: 6800, rate_per_min: 120, status: "NORMAL" },
  { bucket: "2026-10-15T12:00:00+07:00", count: 2200, rate_per_min: 47, status: "WARNING" },
  { bucket: "2026-10-15T13:00:00+07:00", count: 6650, rate_per_min: 118, status: "NORMAL" },
  { bucket: "2026-10-15T14:00:00+07:00", count: 7300, rate_per_min: 129, status: "NORMAL" },
  { bucket: "2026-10-15T15:00:00+07:00", count: 6850, rate_per_min: 122, status: "NORMAL" },
  { bucket: "2026-10-15T16:00:00+07:00", count: 5700, rate_per_min: 114, status: "NORMAL" },
];

// Fallback daily aggregates for 7 days
export const MOCK_DAILY_7DAYS: AggregateItemDTO[] = [
  { bucket: "2026-10-10T00:00:00+07:00", count: 51200, rate_per_min: 117, status: "NORMAL" },
  { bucket: "2026-10-11T00:00:00+07:00", count: 54800, rate_per_min: 120, status: "NORMAL" },
  { bucket: "2026-10-12T00:00:00+07:00", count: 52400, rate_per_min: 116, status: "NORMAL" },
  { bucket: "2026-10-13T00:00:00+07:00", count: 53900, rate_per_min: 119, status: "NORMAL" },
  { bucket: "2026-10-14T00:00:00+07:00", count: 55300, rate_per_min: 122, status: "NORMAL" },
  { bucket: "2026-10-15T00:00:00+07:00", count: 54200, rate_per_min: 120, status: "NORMAL" },
  { bucket: "2026-10-16T00:00:00+07:00", count: 48320, rate_per_min: 118, status: "NORMAL" },
];

// Fallback count events (30 items for pagination demonstration)
export const MOCK_COUNT_EVENTS: CountEventDTO[] = Array.from({ length: 30 }, (_, i) => {
  const minsAgo = (30 - i) * 3;
  const d = new Date(Date.now() - minsAgo * 60 * 1000);
  return {
    id: 1001 + i,
    track_id: 2000 + ((i * 7) % 50),
    ts_utc: d.toISOString(),
    confidence: Math.round((0.965 + ((i * 13) % 30) * 0.001) * 1000) / 1000,
  };
}).reverse();

/**
 * Compute start and end ISO timestamps for date presets.
 */
export function computeDateRange(preset: DatePresetKey): { from: string; to: string } {
  const now = new Date();
  if (preset === "today") {
    const start = new Date(now);
    start.setHours(0, 0, 0, 0);
    const end = new Date(now);
    end.setHours(23, 59, 59, 999);
    return { from: start.toISOString(), to: end.toISOString() };
  }
  if (preset === "yesterday") {
    const start = new Date(now);
    start.setDate(start.getDate() - 1);
    start.setHours(0, 0, 0, 0);
    const end = new Date(now);
    end.setDate(end.getDate() - 1);
    end.setHours(23, 59, 59, 999);
    return { from: start.toISOString(), to: end.toISOString() };
  }
  // last7days
  const start = new Date(now);
  start.setDate(start.getDate() - 6);
  start.setHours(0, 0, 0, 0);
  const end = new Date(now);
  end.setHours(23, 59, 59, 999);
  return { from: start.toISOString(), to: end.toISOString() };
}

/**
 * Format WIB datetime string: "16 Okt 2026, 14:28:15 WIB"
 */
export function formatWibDateTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return isoString;
    return (
      new Intl.DateTimeFormat("id-ID", {
        timeZone: "Asia/Jakarta",
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      }).format(date) + " WIB"
    );
  } catch {
    return isoString;
  }
}

/**
 * Format WIB time only: "10:00 WIB"
 */
export function formatWibTimeOnly(isoString: string): string {
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return isoString;
    return (
      new Intl.DateTimeFormat("id-ID", {
        timeZone: "Asia/Jakarta",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }).format(date) + " WIB"
    );
  } catch {
    return isoString;
  }
}

/**
 * Format date range description label for headers.
 */
export function formatDateRangeLabel(preset: DatePresetKey, range: { from: string; to: string }): string {
  try {
    const fromDate = new Date(range.from);
    const toDate = new Date(range.to);
    const dateOpts: Intl.DateTimeFormatOptions = {
      timeZone: "Asia/Jakarta",
      day: "2-digit",
      month: "short",
      year: "numeric",
    };
    const fromStr = new Intl.DateTimeFormat("id-ID", dateOpts).format(fromDate);
    const toStr = new Intl.DateTimeFormat("id-ID", dateOpts).format(toDate);
    if (preset === "today" || preset === "yesterday") {
      return `${fromStr} (00:00 - 23:59 WIB)`;
    }
    return `${fromStr} s/d ${toStr} (WIB)`;
  } catch {
    return "";
  }
}

/**
 * Format bucket timestamp for bar chart x-axis.
 */
function formatBucketAxisLabel(bucketIso: string, preset: DatePresetKey): string {
  try {
    const d = new Date(bucketIso);
    if (isNaN(d.getTime())) return bucketIso;
    if (preset === "last7days") {
      return new Intl.DateTimeFormat("id-ID", {
        timeZone: "Asia/Jakarta",
        day: "2-digit",
        month: "short",
      }).format(d);
    }
    return new Intl.DateTimeFormat("id-ID", {
      timeZone: "Asia/Jakarta",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(d);
  } catch {
    return bucketIso;
  }
}

export function ReportsView({ lineId }: ReportsViewProps) {
  const { currentLineId: contextLineId, lines } = useAppContext();
  const activeLineId = lineId || contextLineId || "line-1";
  const currentLine = lines.find((l) => l.id === activeLineId) || lines[0];

  const [preset, setPreset] = useState<DatePresetKey>("today");
  const [dateRange, setDateRange] = useState(() => computeDateRange("today"));
  const [currentPage, setCurrentPage] = useState<number>(1);
  const pageSize = 10;

  const [aggregates, setAggregates] = useState<AggregateItemDTO[]>([]);
  const [events, setEvents] = useState<CountEventDTO[]>([]);
  const [paginationMeta, setPaginationMeta] = useState<PaginationMeta>({
    total: 0,
    page: 1,
    limit: pageSize,
  });

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isFallback, setIsFallback] = useState<boolean>(false);
  const [isExporting, setIsExporting] = useState<"xlsx" | "pdf" | null>(null);
  const [exportFeedback, setExportFeedback] = useState<string | null>(null);
  const exportFeedbackTimeoutRef = useRef<NodeJS.Timeout | number | null>(null);

  // Clear export feedback timer on unmount
  useEffect(() => {
    return () => {
      if (exportFeedbackTimeoutRef.current) {
        clearTimeout(exportFeedbackTimeoutRef.current);
      }
    };
  }, []);

  // Recompute date range whenever preset changes
  useEffect(() => {
    const newRange = computeDateRange(preset);
    setDateRange(newRange);
    setCurrentPage(1);
  }, [preset]);

  // Reset pagination when activeLineId changes
  useEffect(() => {
    setCurrentPage(1);
  }, [activeLineId]);

  // Fetch count aggregates and raw events
  const fetchData = useCallback(
    async (pageToLoad: number) => {
      setIsLoading(true);
      const fromIso = dateRange.from;
      const toIso = dateRange.to;
      const granularity = preset === "last7days" ? "daily" : "hourly";

      try {
        const response = await apiClient.getLineCounts(activeLineId, {
          from_time: fromIso,
          to_time: toIso,
          page: pageToLoad,
          limit: pageSize,
          granularity,
        });

        if (response && Array.isArray(response.aggregates)) {
          setAggregates(response.aggregates);
          setEvents(response.events || []);
          setPaginationMeta(
            response.pagination || {
              total: response.events?.length || 0,
              page: pageToLoad,
              limit: pageSize,
            }
          );
          setIsFallback(false);
        }
      } catch (err) {
        console.warn("Failed to fetch reports counts from API, falling back to mock data:", err);
        applyMockFallback(preset, pageToLoad);
      } finally {
        setIsLoading(false);
      }
    },
    [activeLineId, dateRange.from, dateRange.to, preset]
  );

  // Apply fallback mock dataset for offline resilience
  const applyMockFallback = useCallback((currentPreset: DatePresetKey, pageToLoad: number) => {
    setIsFallback(true);
    let mockAggs: AggregateItemDTO[];
    if (currentPreset === "yesterday") {
      mockAggs = MOCK_HOURLY_YESTERDAY;
    } else if (currentPreset === "last7days") {
      mockAggs = MOCK_DAILY_7DAYS;
    } else {
      mockAggs = MOCK_HOURLY_TODAY;
    }

    setAggregates(mockAggs);

    // Paginate mock events
    const startIdx = (pageToLoad - 1) * pageSize;
    const endIdx = startIdx + pageSize;
    const paginatedEvents = MOCK_COUNT_EVENTS.slice(startIdx, endIdx);

    setEvents(paginatedEvents);
    setPaginationMeta({
      total: MOCK_COUNT_EVENTS.length,
      page: pageToLoad,
      limit: pageSize,
    });
  }, []);

  // Fetch data on activeLineId, dateRange, or currentPage change
  useEffect(() => {
    fetchData(currentPage);
  }, [fetchData, currentPage]);

  // Page change handler
  const handlePageChange = (newPage: number) => {
    if (newPage < 1) return;
    const totalPages = Math.ceil(paginationMeta.total / pageSize) || 1;
    if (newPage > totalPages) return;
    setCurrentPage(newPage);
  };

  // Export report download handler
  const handleExport = (format: "xlsx" | "pdf") => {
    if (exportFeedbackTimeoutRef.current) {
      clearTimeout(exportFeedbackTimeoutRef.current);
      exportFeedbackTimeoutRef.current = null;
    }

    setIsExporting(format);
    try {
      const url = apiClient.getExportUrl(format, activeLineId, dateRange.from, dateRange.to);

      // Create download trigger element
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `laporan_${activeLineId}_${preset}.${format}`);
      link.target = "_blank";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      setExportFeedback(
        `Laporan format ${format.toUpperCase()} berhasil diekspor untuk ${currentLine?.name || activeLineId}.`
      );
      exportFeedbackTimeoutRef.current = setTimeout(() => {
        setExportFeedback(null);
        exportFeedbackTimeoutRef.current = null;
      }, 4000);
    } catch (err) {
      console.error(`Gagal mengekspor laporan ${format}:`, err);
      setExportFeedback(`Gagal mengekspor file ${format.toUpperCase()}.`);
      exportFeedbackTimeoutRef.current = setTimeout(() => {
        setExportFeedback(null);
        exportFeedbackTimeoutRef.current = null;
      }, 4000);
    } finally {
      setIsExporting(null);
    }
  };

  // Compute metric cards data
  const summaryMetrics = useMemo(() => {
    if (!aggregates || aggregates.length === 0) {
      return {
        totalCount: 0,
        avgSpeed: 0,
        peakHour: { time: "-", count: 0 },
        totalIntervals: 0,
      };
    }

    const total = aggregates.reduce((acc, curr) => acc + (curr.count || 0), 0);

    const activeIntervals = aggregates.filter((agg) => (agg.count || 0) > 0);
    const avg =
      activeIntervals.length > 0
        ? Math.round(
            activeIntervals.reduce((acc, curr) => acc + (curr.rate_per_min || 0), 0) /
              activeIntervals.length
          )
        : 0;

    // If totalCount === 0 or all intervals have count === 0, return time: "-"
    if (total === 0 || activeIntervals.length === 0) {
      return {
        totalCount: 0,
        avgSpeed: 0,
        peakHour: { time: "-", count: 0 },
        totalIntervals: aggregates.length,
      };
    }

    let peak = activeIntervals[0];
    for (const agg of activeIntervals) {
      if ((agg.count || 0) > (peak.count || 0)) {
        peak = agg;
      }
    }

    let peakTimeStr = "-";
    if (peak && peak.bucket) {
      if (preset === "last7days") {
        peakTimeStr = formatBucketAxisLabel(peak.bucket, preset);
      } else {
        peakTimeStr = formatWibTimeOnly(peak.bucket);
      }
    }

    return {
      totalCount: total,
      avgSpeed: avg,
      peakHour: { time: peakTimeStr, count: peak?.count || 0 },
      totalIntervals: aggregates.length,
    };
  }, [aggregates, preset]);

  const { totalCount, avgSpeed, peakHour, totalIntervals } = summaryMetrics;

  // Chart datasets
  const chartItems = useMemo(() => {
    return aggregates.map((agg) => {
      const label = formatBucketAxisLabel(agg.bucket, preset);
      return {
        label,
        count: agg.count,
        rate: Math.round(agg.rate_per_min),
      };
    });
  }, [aggregates, preset]);

  // ECharts Bar Chart Option
  const barChartOption = useMemo(() => {
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
          const periodUnit = preset === "last7days" ? "" : " WIB";
          return `
            <div style="font-weight: 600; margin-bottom: 4px; color: #34d399;">
              ${item.name}${periodUnit}
            </div>
            <div>Volume: <strong>${(item.value || 0).toLocaleString("id-ID")}</strong> ekor</div>
            <div style="color: #94a3b8; font-size: 11px; margin-top: 2px;">
              Kecepatan: ~${meta?.rate || 0} ekor/mnt
            </div>
          `;
        },
      },
      grid: {
        top: "14%",
        left: "3%",
        right: "4%",
        bottom: "8%",
        containLabel: true,
      },
      xAxis: {
        type: "category",
        data: chartItems.map((d) => d.label),
        axisLine: { lineStyle: { color: "#475569" } },
        axisLabel: { color: "#94a3b8", fontSize: 11 },
      },
      yAxis: {
        type: "value",
        name: "Volume (Ekor)",
        nameTextStyle: { color: "#64748b", fontSize: 11 },
        splitLine: {
          lineStyle: { color: "#334155", type: "dashed" },
        },
        axisLabel: {
          color: "#94a3b8",
          fontSize: 11,
          formatter: (val: number) => (val >= 1000 ? `${Math.round(val / 1000)}k` : `${val}`),
        },
      },
      series: [
        {
          name: "Volume Penghitungan",
          type: "bar",
          data: chartItems.map((d) => d.count),
          barWidth: preset === "last7days" ? "35%" : "42%",
          itemStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "#34d399" }, // light emerald
                { offset: 1, color: "#059669" }, // deep emerald
              ],
            },
            borderRadius: [4, 4, 0, 0],
          },
          emphasis: {
            itemStyle: {
              color: "#6ee7b7",
            },
          },
        },
      ],
    };
  }, [chartItems, preset]);

  const totalPages = Math.max(1, Math.ceil(paginationMeta.total / pageSize));
  const activePresetConfig = DATE_PRESETS.find((p) => p.key === preset) || DATE_PRESETS[0];

  return (
    <div className="space-y-6">
      {/* Top Controls: Preset Filter, WIB Range Indicator, and 1-Click Export Buttons */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 bg-slate-800/80 p-4 rounded-xl border border-slate-700/80 shadow-sm">
        {/* Left: Date Preset Pills */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold text-slate-400 mr-1 flex items-center gap-1.5">
            <Calendar className="w-3.5 h-3.5 text-emerald-400" />
            <span>Periode:</span>
          </span>
          <div
            className="flex items-center gap-1 bg-slate-900/90 p-1 rounded-lg border border-slate-700/80"
            role="radiogroup"
            aria-label="Filter Rentang Waktu"
          >
            {DATE_PRESETS.map((p) => {
              const isSelected = preset === p.key;
              return (
                <button
                  key={p.key}
                  type="button"
                  role="radio"
                  aria-checked={isSelected}
                  onClick={() => setPreset(p.key)}
                  className={`px-3 py-1.5 text-xs sm:text-sm font-semibold rounded-md transition ${
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

          {/* Active Range WIB Badge */}
          <span className="text-[11px] sm:text-xs text-slate-400 bg-slate-900/50 border border-slate-700/50 px-2.5 py-1.5 rounded-md font-mono hidden md:inline">
            {formatDateRangeLabel(preset, dateRange)}
          </span>
        </div>

        {/* Right: Export Excel & PDF Buttons + Refresh */}
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Ekspor Excel */}
          <button
            type="button"
            onClick={() => handleExport("xlsx")}
            disabled={isExporting !== null}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs sm:text-sm font-semibold bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white shadow-sm transition disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            aria-label="Ekspor Excel (.xlsx)"
            title="Unduh laporan dalam format Microsoft Excel"
          >
            <FileSpreadsheet className="w-4 h-4 text-emerald-100" />
            <span>{isExporting === "xlsx" ? "Mengunduh..." : "Ekspor Excel (.xlsx)"}</span>
          </button>

          {/* Ekspor PDF */}
          <button
            type="button"
            onClick={() => handleExport("pdf")}
            disabled={isExporting !== null}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs sm:text-sm font-semibold bg-slate-700 hover:bg-slate-600 active:bg-slate-800 text-white border border-slate-600 shadow-sm transition disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            aria-label="Ekspor PDF (.pdf)"
            title="Unduh laporan resmi format PDF"
          >
            <FileDown className="w-4 h-4 text-rose-300" />
            <span>{isExporting === "pdf" ? "Mengunduh..." : "Ekspor PDF (.pdf)"}</span>
          </button>

          {/* Refresh Data */}
          <button
            type="button"
            onClick={() => fetchData(currentPage)}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs sm:text-sm font-medium bg-slate-900/70 hover:bg-slate-800 text-slate-300 border border-slate-700 transition disabled:opacity-50 cursor-pointer"
            aria-label="Segarkan Data"
            title="Segarkan data laporan"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin text-emerald-400" : ""}`} />
            <span className="hidden sm:inline">Segarkan</span>
          </button>
        </div>
      </div>

      {/* Export Success Feedback Notification */}
      {exportFeedback && (
        <div
          role="status"
          className="flex items-center gap-2 px-4 py-2.5 bg-emerald-950/80 border border-emerald-500/40 text-emerald-300 text-xs sm:text-sm rounded-xl animate-in fade-in transition"
        >
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{exportFeedback}</span>
        </div>
      )}

      {/* Offline / Fallback Notice */}
      {isFallback && (
        <div
          role="status"
          className="flex items-center gap-2 px-4 py-2.5 bg-amber-950/60 border border-amber-600/40 text-amber-300 text-xs rounded-xl"
        >
          <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
          <span>
            Mode Cadangan Offline: Menggunakan data agregat dan log lokal untuk simulasi analisis data.
          </span>
        </div>
      )}

      {/* 4 Metric Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Total Ayam */}
        <div className="bg-slate-800 border border-slate-700/80 rounded-xl p-4 sm:p-5 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Total Ayam
            </span>
            <Layers className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              {totalCount.toLocaleString("id-ID")}
            </span>
            <span className="text-xs font-medium text-slate-400">ekor</span>
          </div>
          <div className="text-[11px] text-slate-400 mt-2 flex items-center justify-between">
            <span className="text-emerald-400 font-medium">Periode {activePresetConfig.label}</span>
            <span className="text-slate-500 font-mono text-[10px]">{currentLine?.name || activeLineId}</span>
          </div>
        </div>

        {/* Card 2: Kecepatan Rata-Rata */}
        <div className="bg-slate-800 border border-slate-700/80 rounded-xl p-4 sm:p-5 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Kecepatan Rata-Rata
            </span>
            <Gauge className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              {avgSpeed}
            </span>
            <span className="text-xs font-medium text-slate-400">ekor/mnt</span>
          </div>
          <div className="text-[11px] text-slate-400 mt-2">
            <span>Rata-rata konveyor beroperasi</span>
          </div>
        </div>

        {/* Card 3: Jam Puncak */}
        <div className="bg-slate-800 border border-slate-700/80 rounded-xl p-4 sm:p-5 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Jam Puncak
            </span>
            <Clock className="w-4 h-4 text-amber-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-xl sm:text-2xl font-extrabold text-amber-300 tracking-tight">
              {peakHour.time}
            </span>
          </div>
          <div className="text-[11px] text-slate-400 mt-2">
            <span>
              Volume tertinggi:{" "}
              <strong className="text-slate-200">{peakHour.count.toLocaleString("id-ID")}</strong> ekor
            </span>
          </div>
        </div>

        {/* Card 4: Interval Terdata */}
        <div className="bg-slate-800 border border-slate-700/80 rounded-xl p-4 sm:p-5 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Interval Terdata
            </span>
            <Calendar className="w-4 h-4 text-violet-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              {totalIntervals}
            </span>
            <span className="text-xs font-medium text-slate-400">interval</span>
          </div>
          <div className="text-[11px] text-slate-400 mt-2">
            <span>Bucket waktu tercatat sistem</span>
          </div>
        </div>
      </div>

      {/* Volume Breakdown Bar Chart */}
      <div className="bg-slate-800 rounded-xl border border-slate-700/80 p-4 sm:p-5 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
          <div>
            <h3 className="text-base sm:text-lg font-semibold text-slate-100 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-emerald-400" />
              Distribusi Volume Penghitungan
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Rincian kuantitas karkas ayam per interval waktu ({preset === "last7days" ? "Harian" : "Per Jam WIB"})
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span className="inline-block w-3 h-3 rounded-sm bg-emerald-500"></span>
            <span>Volume (Ekor)</span>
          </div>
        </div>

        <div className="w-full h-72 sm:h-80">
          <ReactECharts
            option={barChartOption}
            style={{ height: "100%", width: "100%" }}
            notMerge={true}
            lazyUpdate={true}
          />
        </div>
      </div>

      {/* Raw Event Log Paginated Table */}
      <div className="bg-slate-800 rounded-xl border border-slate-700/80 shadow-sm overflow-hidden">
        <div className="p-4 sm:p-5 border-b border-slate-700 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-base sm:text-lg font-semibold text-slate-100 flex items-center gap-2">
              <Activity className="w-5 h-5 text-emerald-400" />
              Log Deteksi Karkas (Raw Events)
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Catatan individual per shackle yang tertangkap oleh kamera visi komputer
            </p>
          </div>
          <div className="text-xs text-slate-400 font-medium">
            Total tercatat:{" "}
            <span className="text-slate-200 font-semibold">
              {paginationMeta.total.toLocaleString("id-ID")}
            </span>{" "}
            event
          </div>
        </div>

        <div className="overflow-x-auto">
          <table
            className="w-full text-left text-xs sm:text-sm text-slate-300"
            aria-label="Tabel Log Deteksi Karkas Mentah"
          >
            <thead className="bg-slate-900/70 text-slate-400 font-semibold uppercase tracking-wider text-[11px] border-b border-slate-700">
              <tr>
                <th scope="col" className="px-4 py-3">
                  No. / ID
                </th>
                <th scope="col" className="px-4 py-3">
                  ID Pelacakan
                </th>
                <th scope="col" className="px-4 py-3">
                  Timestamp (WIB)
                </th>
                <th scope="col" className="px-4 py-3 text-right">
                  Tingkat Akurasi
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/60">
              {events.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-slate-400">
                    Tidak ada catatan event deteksi untuk rentang waktu yang dipilih.
                  </td>
                </tr>
              ) : (
                events.map((evt, idx) => {
                  const confPct = Math.round(evt.confidence * 1000) / 10;
                  const isHighConf = confPct >= 95;
                  const rowNumber = (paginationMeta.page - 1) * paginationMeta.limit + idx + 1;
                  return (
                    <tr key={evt.id ?? idx} className="hover:bg-slate-750 transition-colors">
                      <td className="px-4 py-3 font-mono text-slate-400 text-xs">
                        #{evt.id ?? rowNumber}
                      </td>
                      <td className="px-4 py-3 font-mono text-slate-200">
                        <span className="inline-flex items-center px-2 py-0.5 rounded bg-slate-700/60 text-slate-300 text-xs">
                          Track #{evt.track_id}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-300">{formatWibDateTime(evt.ts_utc)}</td>
                      <td className="px-4 py-3 text-right">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${
                            isHighConf
                              ? "bg-emerald-950/80 text-emerald-300 border border-emerald-800/60"
                              : "bg-amber-950/80 text-amber-300 border border-amber-800/60"
                          }`}
                        >
                          {confPct.toFixed(1)}%
                        </span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="p-4 border-t border-slate-700 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-400">
          <div>
            Menampilkan{" "}
            <span className="text-slate-200 font-medium">
              {paginationMeta.total === 0 ? 0 : (paginationMeta.page - 1) * paginationMeta.limit + 1}
            </span>{" "}
            sampai{" "}
            <span className="text-slate-200 font-medium">
              {Math.min(paginationMeta.page * paginationMeta.limit, paginationMeta.total)}
            </span>{" "}
            dari{" "}
            <span className="text-slate-200 font-medium">
              {paginationMeta.total.toLocaleString("id-ID")}
            </span>{" "}
            entri
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => handlePageChange(paginationMeta.page - 1)}
              disabled={paginationMeta.page <= 1 || isLoading}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md bg-slate-700 hover:bg-slate-600 active:bg-slate-800 text-slate-200 disabled:opacity-40 disabled:cursor-not-allowed transition font-medium cursor-pointer"
              aria-label="Halaman Sebelumnya"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              <span>Sebelumnya</span>
            </button>

            <span className="px-2 py-1 text-slate-300 font-medium">
              Halaman {paginationMeta.page} dari {totalPages}
            </span>

            <button
              type="button"
              onClick={() => handlePageChange(paginationMeta.page + 1)}
              disabled={paginationMeta.page >= totalPages || isLoading}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md bg-slate-700 hover:bg-slate-600 active:bg-slate-800 text-slate-200 disabled:opacity-40 disabled:cursor-not-allowed transition font-medium cursor-pointer"
              aria-label="Halaman Berikutnya"
            >
              <span>Berikutnya</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ReportsView;
