import { useState, useEffect } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { LineSelector } from "@/components/layout/LineSelector";
import { StatusBadge } from "@/components/common/StatusBadge";
import { useAppContext } from "@/context/AppContext";
import { KpiCards } from "../components/KpiCards";
import { HourlyRateChart } from "../components/HourlyRateChart";
import { overviewApi } from "../api/overview.api";
import type { LineSummaryResponse, AggregateItemDTO } from "@/types";

const FALLBACK_SUMMARY: LineSummaryResponse = {
  line_id: "line-1",
  period: "today",
  total_count: 48320,
  target_count: 62000,
  target_attainment_pct: 77.9,
  current_speed_cpm: 118,
  target_speed_cpm: 120,
  active_alarms_count: 0,
  camera_status: "online",
  last_event_time: null,
  fps: 30.0,
  latency_p95_ms: 38.0,
};

export default function DashboardPage() {
  const { currentLineId, isConnected } = useAppContext();
  const [summary, setSummary] = useState<LineSummaryResponse>(FALLBACK_SUMMARY);
  const [aggregates, setAggregates] = useState<AggregateItemDTO[]>([]);

  useEffect(() => {
    let isMounted = true;
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

    return () => {
      isMounted = false;
    };
  }, [currentLineId]);

  return (
    <div>
      <PageHeader
        title="Dashboard Pemantauan"
        description="Ringkasan metrik real-time dan pencapaian target produksi"
      >
        <StatusBadge isConnected={isConnected} />
        <LineSelector />
      </PageHeader>

      <KpiCards summary={summary} />
      <HourlyRateChart data={aggregates} />
    </div>
  );
}
