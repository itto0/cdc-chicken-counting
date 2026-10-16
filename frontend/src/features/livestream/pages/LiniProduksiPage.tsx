import { useMemo, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { LineSelector } from "@/components/layout/LineSelector";
import { StatusBadge } from "@/components/common/StatusBadge";
import { useAppContext } from "@/context/AppContext";
import { useLiveStream } from "@/hooks/useLiveStream";
import { API_BASE_URL } from "@/config/env";
import { VideoPlayer } from "../components/VideoPlayer";
import { StreamMetrics } from "../components/StreamMetrics";

export default function LiniProduksiPage() {
  const { currentLineId, isConnected } = useAppContext();
  const { status, fps, latencyMs, reconnect } = useLiveStream(currentLineId);
  const [retryNonce, setRetryNonce] = useState(0);

  const isStreaming = status === "CONNECTED";

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
    <div>
      <PageHeader
        title="Pemantauan Lini Produksi"
        description="Streaming real-time dan deteksi konveyor ayam"
      >
        <StatusBadge isConnected={isConnected} />
        <LineSelector />
      </PageHeader>

      <StreamMetrics
        fps={fps ?? 30}
        latencyMs={latencyMs ?? 42}
        cameraStatus={isStreaming ? "online" : "menghubungkan"}
      />

      <VideoPlayer
        previewUrl={previewUrl}
        isConnected={isStreaming}
        onRetry={handleRetry}
      />
    </div>
  );
}
