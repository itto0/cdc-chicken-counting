import { useState, useEffect, useMemo } from "react";
import { AlertCircle, X } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { useAppContext } from "@/context/AppContext";
import { reportsApi } from "../api/reports.api";
import { ReportFilterBar } from "../components/ReportFilterBar";
import { ReportKpiCards, type ReportSummaryMetrics } from "../components/ReportKpiCards";
import { ReportsTable, type ReportRowItem } from "../components/ReportsTable";

export const formatBucketHour = (bucketStr: string): string => {
  try {
    const isoStr =
      bucketStr.includes("T") &&
      !bucketStr.endsWith("Z") &&
      !/[+-]\d{2}(:?\d{2})?$/.test(bucketStr)
        ? `${bucketStr}Z`
        : bucketStr;
    const d = new Date(isoStr);
    if (!isNaN(d.getTime())) {
      return d
        .toLocaleTimeString("id-ID", {
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
          timeZone: "Asia/Jakarta",
        })
        .replace(".", ":");
    }
  } catch {
    // Fallback to substring slicing if not a valid ISO date
  }
  return bucketStr.includes("T") ? bucketStr.split("T")[1].slice(0, 5) : bucketStr;
};

export const formatBucketDate = (bucketStr: string): string => {
  try {
    const isoStr =
      bucketStr.includes("T") &&
      !bucketStr.endsWith("Z") &&
      !/[+-]\d{2}(:?\d{2})?$/.test(bucketStr)
        ? `${bucketStr}Z`
        : bucketStr;
    const d = new Date(isoStr);
    if (!isNaN(d.getTime())) {
      return d.toLocaleDateString("id-ID", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        timeZone: "Asia/Jakarta",
      });
    }
  } catch {
    // Fallback
  }
  return "Hari Ini";
};

export default function LaporanPage() {
  const { currentLineId, lines, isConnected } = useAppContext();
  const [period, setPeriod] = useState<"today" | "7d" | "30d">("today");
  const [selectedLineId, setSelectedLineId] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [rawRows, setRawRows] = useState<ReportRowItem[]>([]);
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  // Compute time range for filters
  const { startTime, endTime } = useMemo(() => {
    const now = new Date();
    const end = now.toISOString();
    let start = new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString();

    if (period === "7d") {
      const d7 = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      start = d7.toISOString();
    } else if (period === "30d") {
      const d30 = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
      start = d30.toISOString();
    }

    return { startTime: start, endTime: end };
  }, [period]);

  // Fetch counts from lines
  useEffect(() => {
    let isMounted = true;
    const targetLines =
      selectedLineId === "all"
        ? lines
        : lines.filter((l) => l.id === selectedLineId);
    const activeLines =
      targetLines.length > 0
        ? targetLines
        : [
            {
              id: selectedLineId !== "all" ? selectedLineId : currentLineId || "line-1",
              name: selectedLineId !== "all" ? selectedLineId : "Lini 1 - Utama",
            },
          ];

    Promise.all(
      activeLines.map((line) =>
        reportsApi
          .getCounts(line.id, { from: startTime, to: endTime, granularity: "hourly" })
          .then((res) => ({ line, res }))
          .catch(() => ({ line, res: null }))
      )
    ).then((results) => {
      if (!isMounted) return;

      const items: ReportRowItem[] = [];
      results.forEach(({ line, res }) => {
        if (res?.aggregates && res.aggregates.length > 0) {
          res.aggregates.forEach((agg, idx) => {
            const dateStr = formatBucketDate(agg.bucket);
            const hourStr = formatBucketHour(agg.bucket);

            items.push({
              id: `${line.id}-${agg.bucket}-${idx}`,
              timestamp: `${dateStr}, ${hourStr}`,
              rawTimestamp: agg.bucket,
              lineName: line.name || line.id,
              count: agg.count ?? 0,
              ratePerMin: agg.rate_per_min ?? 0,
              accuracyPct: 0,
              status: agg.status || "Normal",
            });
          });
        }
      });

      // Chronological Sorting: sort items descending by rawTimestamp so newest intervals appear first across all lines
      items.sort((a, b) => {
        const timeA = a.rawTimestamp ? new Date(a.rawTimestamp).getTime() : 0;
        const timeB = b.rawTimestamp ? new Date(b.rawTimestamp).getTime() : 0;
        return timeB - timeA;
      });

      setRawRows(items);
    });

    return () => {
      isMounted = false;
    };
  }, [selectedLineId, lines, currentLineId, startTime, endTime]);

  // Client-side search filtering
  const filteredRows = useMemo(() => {
    if (!searchQuery.trim()) return rawRows;
    const q = searchQuery.toLowerCase().trim();
    return rawRows.filter(
      (r) =>
        r.lineName.toLowerCase().includes(q) ||
        r.timestamp.toLowerCase().includes(q) ||
        r.status.toLowerCase().includes(q)
    );
  }, [rawRows, searchQuery]);

  // Summary Metrics for the 4 KPI cards
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

  const handleExport = async (format: "pdf" | "xlsx") => {
    try {
      setExportError(null);
      setIsExporting(true);
      await reportsApi.downloadReport({
        lineId: selectedLineId,
        format,
        startTime,
        endTime,
      });
    } catch (err) {
      console.error("Failed to export report:", err);
      setExportError(err instanceof Error ? err.message : "Gagal mengunduh laporan");
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="Laporan dan Data Historis"
        description="Rekapitulasi performa lini, ekspor data, dan riwayat penghitungan"
      >
        <StatusBadge isConnected={isConnected} />
      </PageHeader>

      {exportError && (
        <div
          role="alert"
          className="flex items-center justify-between gap-3 p-3.5 px-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-sm animate-in fade-in"
        >
          <div className="flex items-center gap-2.5 min-w-0">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" aria-hidden="true" />
            <span className="truncate">{exportError}</span>
          </div>
          <button
            type="button"
            onClick={() => setExportError(null)}
            className="p-1 rounded-lg text-rose-500 hover:text-rose-700 hover:bg-rose-100 transition-colors shrink-0"
            aria-label="Tutup pesan kesalahan"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      <ReportFilterBar
        period={period}
        onPeriodChange={setPeriod}
        selectedLineId={selectedLineId}
        onLineChange={setSelectedLineId}
        lines={lines}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onExportPdf={() => handleExport("pdf")}
        onExportExcel={() => handleExport("xlsx")}
        isExporting={isExporting}
      />

      <ReportKpiCards metrics={summaryMetrics} />

      <ReportsTable
        key={`${selectedLineId}-${searchQuery}-${period}`}
        data={filteredRows}
      />
    </div>
  );
}
