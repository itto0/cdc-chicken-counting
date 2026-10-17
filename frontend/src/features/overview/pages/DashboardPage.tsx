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
