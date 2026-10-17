import { useState, useEffect, useMemo } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { LineSelector } from "@/components/layout/LineSelector";
import { StatusBadge } from "@/components/common/StatusBadge";
import { useAppContext } from "@/context/AppContext";
import { useLiveStream } from "@/hooks/useLiveStream";
import { KpiCards } from "../components/KpiCards";
import { HourlyRateChart } from "../components/HourlyRateChart";
import { overviewApi } from "../api/overview.api";
import type { LineSummaryResponse, AggregateItemDTO } from "@/types";

const FALLBACK_SUMMARY: LineSummaryResponse = {
  line_id: "line-1",
  period: "today",
  total_count: 0,
  target_count: 60000,
  target_attainment_pct: 0.0,
  current_speed_cpm: 0,
  target_speed_cpm: 120,
  active_alarms_count: 0,
  camera_status: "online",
  last_event_time: null,
  fps: 30.0,
  latency_p95_ms: 5.0,
};

export default function DashboardPage() {
  const { currentLineId, isConnected } = useAppContext();
  const { totalToday, liveSpeed, fps, latencyMs } = useLiveStream(currentLineId);
  const [summary, setSummary] = useState<LineSummaryResponse>(FALLBACK_SUMMARY);
  const [aggregates, setAggregates] = useState<AggregateItemDTO[]>([]);

  useEffect(() => {
    let isMounted = true;

    const loadData = () => {
      overviewApi
        .getSummary(currentLineId, "today")
        .then((data) => {
          if (isMounted && data) setSummary(data);
        })
        .catch(() => {
          // use fallback gracefully
        });

      overviewApi
        .getCounts(currentLineId, { granularity: "hourly" })
        .then((res) => {
          if (isMounted && res?.aggregates) setAggregates(res.aggregates);
        })
        .catch(() => {
          // use fallback
        });
    };

    loadData();
    // Periodically refresh aggregates so hourly chart updates with synced batches
    const pollTimer = setInterval(loadData, 10000);

    return () => {
      isMounted = false;
      clearInterval(pollTimer);
    };
  }, [currentLineId]);

  // Merge server baseline summary with instant real-time SSE telemetry
  const liveSummary = useMemo<LineSummaryResponse>(() => {
    const total = totalToday > 0 ? totalToday : summary.total_count;
    const speed = liveSpeed > 0 ? liveSpeed : summary.current_speed_cpm;
    const target = summary.target_count || 60000;
    const attainment = target > 0 ? Number(((total / target) * 100).toFixed(1)) : 0;

    return {
      ...summary,
      total_count: total,
      current_speed_cpm: speed,
      target_attainment_pct: attainment,
      fps: fps > 0 ? fps : summary.fps,
      latency_p95_ms: latencyMs > 0 ? latencyMs : summary.latency_p95_ms,
    };
  }, [summary, totalToday, liveSpeed, fps, latencyMs]);

  return (
    <div>
      <PageHeader
        title="Dashboard Pemantauan"
        description="Ringkasan metrik real-time dan pencapaian target produksi"
      >
        <StatusBadge isConnected={isConnected} />
        <LineSelector />
      </PageHeader>

      <KpiCards summary={liveSummary} />
      <HourlyRateChart data={aggregates} />
    </div>
  );
}
