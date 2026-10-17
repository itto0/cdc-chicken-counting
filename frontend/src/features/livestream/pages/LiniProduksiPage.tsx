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
