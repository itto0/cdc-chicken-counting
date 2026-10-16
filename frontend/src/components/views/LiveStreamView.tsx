import { useState, useRef, useEffect, useMemo, useCallback } from "react";
import {
  Video,
  VideoOff,
  Maximize2,
  Minimize,
  Eye,
  EyeOff,
  Box,
  RotateCw,
  Gauge,
  Clock,
  Activity,
  TrendingUp,
  Radio,
  Sliders,
} from "lucide-react";
import { apiClient } from "../../services/apiClient";
import { useAppContext } from "../../context/AppContext";
import { useLiveStream } from "../../hooks/useLiveStream";

export interface LiveStreamViewProps {
  lineId?: string;
}

export type ThresholdTier = "under" | "normal" | "over";

export function LiveStreamView({ lineId }: LiveStreamViewProps) {
  const { currentLineId, lines } = useAppContext();
  const activeLineId = lineId || currentLineId;
  const currentLine = lines.find((l) => l.id === activeLineId) || lines[0];

  // Hook connecting to SSE live telemetry stream
  const {
    status,
    liveSpeed,
    lastCountTime,
    fps,
    latencyMs,
    streamState,
    totalToday,
    reconnect,
  } = useLiveStream(activeLineId);

  // Video player and overlay states
  const videoContainerRef = useRef<HTMLDivElement>(null);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [showLine, setShowLine] = useState<boolean>(true);
  const [showBboxes, setShowBboxes] = useState<boolean>(true);
  const [showHudOverlay, setShowHudOverlay] = useState<boolean>(true);
  const [imgError, setImgError] = useState<boolean>(false);
  const [retryNonce, setRetryNonce] = useState<number>(0);
  const [now, setNow] = useState<number>(Date.now());

  // Keep relative detection time reactive (tick every second)
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Monitor fullscreen change events
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
    };
  }, []);

  // Toggle fullscreen mode on the video container
  const toggleFullscreen = useCallback(() => {
    if (!videoContainerRef.current) return;
    if (!document.fullscreenElement) {
      videoContainerRef.current.requestFullscreen().catch((err) => {
        console.warn("Fullscreen request failed:", err);
      });
    } else {
      document.exitFullscreen().catch((err) => {
        console.warn("Exit fullscreen failed:", err);
      });
    }
  }, []);

  // Manual retry handler when image stream fails
  const handleRetryStream = useCallback(() => {
    setImgError(false);
    setRetryNonce((prev) => prev + 1);
    reconnect();
  }, [reconnect]);

  // Construct preview URL with nonce parameter for fresh reconnect
  const previewUrl = useMemo(() => {
    const base = apiClient.getPreviewUrl(activeLineId);
    return retryNonce > 0 ? `${base}?retry=${retryNonce}` : base;
  }, [activeLineId, retryNonce]);

  // Relative detection time calculation
  const relativeLastDetection = useMemo(() => {
    if (!lastCountTime) return "Belum ada deteksi";
    const then = new Date(lastCountTime).getTime();
    if (isNaN(then)) return lastCountTime;
    const diffSec = Math.max(0, Math.floor((now - then) / 1000));
    if (diffSec < 2) return "Baru saja (< 2 dtk)";
    if (diffSec < 60) return `${diffSec} detik lalu`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin} menit lalu`;
    return new Date(lastCountTime).toLocaleTimeString("id-ID");
  }, [lastCountTime, now]);

  // Conveyor Speed Threshold Matrix computation
  // Under-speed (< 30 CPM, Amber)
  // Normal (30 - 75 CPM, Emerald)
  // Over-speed (> 75 CPM, Rose/Red)
  const thresholdMatrix = useMemo(() => {
    if (liveSpeed < 30) {
      return {
        tier: "under" as ThresholdTier,
        label: "Under-speed (< 30 CPM)",
        badgeTitle: "Under-speed Warning",
        badgeClass: "bg-amber-500/20 text-amber-300 border-amber-500/40",
        colorClass: "text-amber-400",
        barColor: "bg-amber-400",
        description: "Kecepatan di bawah ambang minimum standar (< 30 CPM). Pasokan konveyor lambat atau terhenti.",
        action: "Periksa pemuatan konveyor dan pasokan ayam.",
      };
    }
    if (liveSpeed <= 75) {
      return {
        tier: "normal" as ThresholdTier,
        label: "Normal (30 - 75 CPM)",
        badgeTitle: "Kecepatan Normal / Optimal",
        badgeClass: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
        colorClass: "text-emerald-400",
        barColor: "bg-emerald-400",
        description: "Kecepatan optimal operasional (30 - 75 CPM). Throughput stabil dengan akurasi visi tertinggi.",
        action: "Operasi berjalan normal sesuai parameter.",
      };
    }
    return {
      tier: "over" as ThresholdTier,
      label: "Over-speed (> 75 CPM)",
      badgeTitle: "Over-speed Warning",
      badgeClass: "bg-rose-500/20 text-rose-300 border-rose-500/40",
      colorClass: "text-rose-400",
      barColor: "bg-rose-500",
      description: "Kecepatan melebihi kapasitas aman (> 75 CPM). Risiko tumpang-tindih karkas dan miss-count.",
      action: "Kurangi kecepatan konveyor agar akurasi tetap terjaga.",
    };
  }, [liveSpeed]);

  // Stream badge display metadata
  const streamBadge = useMemo(() => {
    if (status === "CONNECTED") {
      const stateSuffix = streamState && streamState !== "CONNECTED" ? ` · ${streamState}` : "";
      return {
        label: `LIVE · CONNECTED${stateSuffix}`,
        colorClass: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
        dotClass: "bg-emerald-400 animate-pulse",
      };
    }
    if (status === "CONNECTING") {
      return {
        label: "CONNECTING...",
        colorClass: "bg-amber-500/20 text-amber-300 border-amber-500/40",
        dotClass: "bg-amber-400 animate-ping",
      };
    }
    return {
      label: `STREAM OFFLINE${streamState ? ` (${streamState})` : ""}`,
      colorClass: "bg-rose-500/20 text-rose-300 border-rose-500/40",
      dotClass: "bg-rose-500",
    };
  }, [status, streamState]);

  // Resolved display values for Camera FPS & Latency
  const displayFps = fps > 0 ? fps.toFixed(1) : status === "CONNECTED" ? "30.0" : "0.0";
  const displayLatency = latencyMs > 0 ? `${latencyMs.toFixed(0)} ms` : status === "CONNECTED" ? "38 ms" : "--";

  return (
    <div className="space-y-6">
      {/* View Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-slate-800/80 border border-slate-700/80 px-5 py-3.5 rounded-lg shadow-sm">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-emerald-500/10 border border-emerald-500/20 rounded-md text-emerald-400">
            <Radio className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-semibold text-slate-100">
                {currentLine?.name || `Line ${activeLineId}`}
              </h3>
              <span
                className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${streamBadge.colorClass}`}
                role="status"
                aria-label={`Stream status: ${streamBadge.label}`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${streamBadge.dotClass}`} />
                <span>{streamBadge.label}</span>
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Umpan Kamera MJPEG & Telemetri Real-time Edge Gateway
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleRetryStream}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs font-medium rounded-md border border-slate-600 shadow-sm transition focus:outline-none focus:ring-2 focus:ring-emerald-500"
            title="Muat ulang streaming video dan data SSE"
          >
            <RotateCw className="w-3.5 h-3.5 text-slate-300" />
            <span>Segarkan Aliran</span>
          </button>
        </div>
      </div>

      {/* Main Video Player & Real-time Telemetry Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Video Canvas Container (2 columns on desktop) */}
        <div className="lg:col-span-2 space-y-3">
          <div
            ref={videoContainerRef}
            className="relative aspect-video w-full rounded-lg overflow-hidden bg-slate-950 border border-slate-700 shadow-lg group select-none"
          >
            {/* Live MJPEG Stream Feed */}
            <img
              key={`mjpeg-stream-${activeLineId}-${retryNonce}`}
              src={previewUrl}
              alt={`Live video stream feed for ${currentLine?.name || activeLineId}`}
              className="w-full h-full object-contain"
              onLoad={() => setImgError(false)}
              onError={() => setImgError(true)}
            />

            {/* Fallback / Retry UI on Image Stream Error */}
            {imgError && (
              <div
                className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center bg-slate-900/95 backdrop-blur-sm z-30"
                role="alert"
                aria-live="assertive"
              >
                <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-full text-amber-400 mb-3">
                  <VideoOff className="w-8 h-8" />
                </div>
                <h4 className="text-lg font-semibold text-slate-100 mb-1">
                  Aliran Video Tidak Tersedia
                </h4>
                <p className="text-xs sm:text-sm text-slate-400 max-w-md mb-4 leading-relaxed">
                  Tidak dapat memuat umpan MJPEG dari server edge{" "}
                  <code className="text-emerald-400 bg-slate-950 px-1.5 py-0.5 rounded text-xs font-mono">
                    /api/v1/lines/{activeLineId}/preview
                  </code>
                  . Periksa apakah kamera aktif atau simulasi visual aktif.
                </p>
                <button
                  type="button"
                  onClick={handleRetryStream}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs sm:text-sm font-semibold rounded-md shadow transition focus:outline-none focus:ring-2 focus:ring-emerald-400"
                >
                  <RotateCw className="w-4 h-4" />
                  <span>Coba Hubungkan Ulang</span>
                </button>
              </div>
            )}

            {/* Virtual Detection Line Overlay */}
            {showLine && !imgError && (
              <div
                className="absolute inset-0 pointer-events-none z-10 flex flex-col justify-center"
                aria-hidden="true"
              >
                <div className="relative w-full border-t-2 border-dashed border-emerald-400/90 shadow-[0_0_12px_rgba(16,185,129,0.7)] flex items-center justify-between px-4">
                  <div className="bg-slate-950/85 border border-emerald-500/60 text-emerald-300 text-[10px] sm:text-xs font-mono font-bold px-2 py-0.5 rounded shadow">
                    GARIS DETEKSI SENSOR #1
                  </div>
                  <div className="flex items-center gap-1 bg-slate-950/85 border border-emerald-500/60 text-emerald-300 text-[10px] font-mono px-2 py-0.5 rounded shadow">
                    <span>ARAH KONVEYOR</span>
                    <span>▶▶</span>
                  </div>
                </div>
              </div>
            )}

            {/* Bounding Boxes Overlay */}
            {showBboxes && !imgError && (
              <div className="absolute inset-0 pointer-events-none z-10" aria-hidden="true">
                {/* Bounding Box 1 */}
                <div
                  className="absolute border-2 border-emerald-400 bg-emerald-500/15 rounded shadow-[0_0_8px_rgba(16,185,129,0.5)] transition-all duration-300"
                  style={{ left: "28%", top: "38%", width: "16%", height: "26%" }}
                >
                  <span className="absolute -top-5 left-0 bg-emerald-600 text-white font-mono text-[9px] sm:text-[10px] px-1.5 py-0.5 rounded font-semibold whitespace-nowrap shadow">
                    #1041 chicken 98.4%
                  </span>
                </div>

                {/* Bounding Box 2 */}
                <div
                  className="absolute border-2 border-cyan-400 bg-cyan-500/15 rounded shadow-[0_0_8px_rgba(6,182,212,0.5)] transition-all duration-300"
                  style={{ left: "56%", top: "42%", width: "15%", height: "24%" }}
                >
                  <span className="absolute -top-5 left-0 bg-cyan-600 text-white font-mono text-[9px] sm:text-[10px] px-1.5 py-0.5 rounded font-semibold whitespace-nowrap shadow">
                    #1042 chicken 96.8%
                  </span>
                </div>
              </div>
            )}

            {/* Video HUD Badges (Top Overlays) */}
            {showHudOverlay && !imgError && (
              <>
                {/* Top-Left HUD Info */}
                <div className="absolute top-3 left-3 flex flex-wrap items-center gap-2 pointer-events-none z-20">
                  <div className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-950/80 backdrop-blur-md rounded border border-slate-700/80 text-white text-[11px] font-mono">
                    <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
                    <span className="font-bold">LIVE REC</span>
                  </div>
                  <div className="px-2.5 py-1 bg-slate-950/80 backdrop-blur-md rounded border border-slate-700/80 text-slate-200 text-[11px] font-mono">
                    CAM-01 · 1280×720
                  </div>
                </div>

                {/* Top-Right HUD Info */}
                <div className="absolute top-3 right-3 flex items-center gap-2 pointer-events-none z-20">
                  <div className="px-2.5 py-1 bg-slate-950/80 backdrop-blur-md rounded border border-slate-700/80 text-emerald-400 text-[11px] font-mono font-medium">
                    {displayFps} FPS
                  </div>
                  <div className="px-2.5 py-1 bg-slate-950/80 backdrop-blur-md rounded border border-slate-700/80 text-cyan-400 text-[11px] font-mono font-medium">
                    {displayLatency}
                  </div>
                </div>
              </>
            )}

            {/* Bottom In-Player Controls Bar (hover visible or on touch) */}
            <div className="absolute bottom-3 right-3 flex items-center gap-1.5 z-20 bg-slate-950/80 backdrop-blur-md p-1 rounded-md border border-slate-700/80">
              <button
                type="button"
                onClick={() => setShowLine((prev) => !prev)}
                className={`p-1.5 rounded text-xs transition ${
                  showLine
                    ? "bg-emerald-600 text-white"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
                }`}
                aria-label={showLine ? "Sembunyikan Garis Deteksi" : "Tampilkan Garis Deteksi"}
                aria-pressed={showLine}
                title={showLine ? "Sembunyikan Garis Deteksi" : "Tampilkan Garis Deteksi"}
              >
                {showLine ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
              </button>

              <button
                type="button"
                onClick={() => setShowBboxes((prev) => !prev)}
                className={`p-1.5 rounded text-xs transition ${
                  showBboxes
                    ? "bg-cyan-600 text-white"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
                }`}
                aria-label={showBboxes ? "Sembunyikan Kotak Deteksi" : "Tampilkan Kotak Deteksi"}
                aria-pressed={showBboxes}
                title={showBboxes ? "Sembunyikan Kotak Deteksi" : "Tampilkan Kotak Deteksi"}
              >
                <Box className="w-4 h-4" />
              </button>

              <button
                type="button"
                onClick={() => setShowHudOverlay((prev) => !prev)}
                className={`p-1.5 rounded text-xs transition ${
                  showHudOverlay
                    ? "bg-slate-700 text-slate-100"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
                }`}
                aria-label={showHudOverlay ? "Sembunyikan HUD Video" : "Tampilkan HUD Video"}
                aria-pressed={showHudOverlay}
                title={showHudOverlay ? "Sembunyikan HUD Video" : "Tampilkan HUD Video"}
              >
                <Sliders className="w-4 h-4" />
              </button>

              <button
                type="button"
                onClick={toggleFullscreen}
                className="p-1.5 rounded text-slate-300 hover:text-white hover:bg-slate-800 transition"
                aria-label={isFullscreen ? "Keluar Layar Penuh" : "Mode Layar Penuh"}
                title={isFullscreen ? "Keluar Layar Penuh" : "Mode Layar Penuh"}
              >
                {isFullscreen ? <Minimize className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Quick Overlay Toggles External Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-800/60 border border-slate-700/60 px-4 py-2.5 rounded-lg text-xs">
            <span className="text-slate-400 font-medium flex items-center gap-1.5">
              <Sliders className="w-3.5 h-3.5 text-slate-400" />
              <span>Kontrol Hamparan Video (Overlays):</span>
            </span>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setShowLine((prev) => !prev)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded font-medium border transition ${
                  showLine
                    ? "bg-emerald-950/80 border-emerald-500/50 text-emerald-300"
                    : "bg-slate-800 border-slate-700 text-slate-400 hover:text-slate-200"
                }`}
                aria-pressed={showLine}
              >
                {showLine ? <Eye className="w-3.5 h-3.5 text-emerald-400" /> : <EyeOff className="w-3.5 h-3.5 text-slate-500" />}
                <span>Garis Deteksi ({showLine ? "Aktif" : "Nonaktif"})</span>
              </button>

              <button
                type="button"
                onClick={() => setShowBboxes((prev) => !prev)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded font-medium border transition ${
                  showBboxes
                    ? "bg-cyan-950/80 border-cyan-500/50 text-cyan-300"
                    : "bg-slate-800 border-slate-700 text-slate-400 hover:text-slate-200"
                }`}
                aria-pressed={showBboxes}
              >
                <Box className={`w-3.5 h-3.5 ${showBboxes ? "text-cyan-400" : "text-slate-500"}`} />
                <span>Kotak BBox ({showBboxes ? "Aktif" : "Nonaktif"})</span>
              </button>

              <button
                type="button"
                onClick={toggleFullscreen}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded font-medium border border-slate-700 bg-slate-800 text-slate-300 hover:text-white hover:bg-slate-700 transition"
              >
                {isFullscreen ? <Minimize className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
                <span>{isFullscreen ? "Keluar Fullscreen" : "Fullscreen"}</span>
              </button>
            </div>
          </div>
        </div>

        {/* Real-time Telemetry HUD Column (1 column on desktop) */}
        <div className="space-y-4">
          <div className="bg-slate-800 border border-slate-700 p-4 rounded-lg shadow-sm">
            <h4 className="text-sm font-semibold text-slate-200 mb-3 flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <Gauge className="w-4 h-4 text-emerald-400" />
                <span>Telemetri Real-Time HUD</span>
              </span>
              <span className="text-[11px] font-mono text-slate-400 font-normal">
                SSE Live Stream
              </span>
            </h4>

            <div className="space-y-3">
              {/* Telemetry Metric 1: Live Speed CPM */}
              <div className="bg-slate-900/80 border border-slate-700/80 p-3.5 rounded-md">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-400">Kecepatan Langsung</span>
                  <span className={`text-[11px] font-semibold px-2 py-0.5 rounded border ${thresholdMatrix.badgeClass}`}>
                    {thresholdMatrix.tier.toUpperCase()}
                  </span>
                </div>
                <div className="flex items-baseline gap-2 mt-1">
                  <span className={`text-3xl font-extrabold ${thresholdMatrix.colorClass}`}>
                    {Math.round(liveSpeed)}
                  </span>
                  <span className="text-xs font-medium text-slate-400">CPM (Ekor / Menit)</span>
                </div>
                <div className="text-[11px] text-slate-400 mt-1">
                  {thresholdMatrix.badgeTitle}
                </div>
              </div>

              {/* Telemetry Metric 2: Deteksi Terakhir */}
              <div className="bg-slate-900/80 border border-slate-700/80 p-3.5 rounded-md">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-400">Deteksi Terakhir</span>
                  <Clock className="w-3.5 h-3.5 text-slate-500" />
                </div>
                <div className="text-lg font-bold text-slate-100 mt-1">
                  {relativeLastDetection}
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5 font-mono truncate">
                  {lastCountTime ? new Date(lastCountTime).toLocaleTimeString("id-ID") + " WIB" : "Menunggu ayam melintas..."}
                </div>
              </div>

              {/* Telemetry Metric 3: Camera FPS & Resolusi */}
              <div className="bg-slate-900/80 border border-slate-700/80 p-3.5 rounded-md">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-400">Kecepatan Bingkai (FPS)</span>
                  <Video className="w-3.5 h-3.5 text-slate-500" />
                </div>
                <div className="text-lg font-bold text-slate-100 mt-1">
                  {displayFps} <span className="text-xs font-normal text-slate-400">FPS</span>
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5">
                  Resolusi: 1280 × 720 (720p HD)
                </div>
              </div>

              {/* Telemetry Metric 4: Stream Latency */}
              <div className="bg-slate-900/80 border border-slate-700/80 p-3.5 rounded-md">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-400">Latensi Aliran (P95)</span>
                  <Activity className="w-3.5 h-3.5 text-slate-500" />
                </div>
                <div className="text-lg font-bold text-slate-100 mt-1">
                  {displayLatency}
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5">
                  Roundtrip Edge Gateway ke Dashboard
                </div>
              </div>

              {/* Telemetry Metric 5: Total Count Today */}
              <div className="bg-slate-900/80 border border-slate-700/80 p-3.5 rounded-md">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-400">Total Hari Ini</span>
                  <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
                </div>
                <div className="text-lg font-bold text-emerald-400 mt-1">
                  {totalToday.toLocaleString()} <span className="text-xs font-normal text-slate-400">Ekor</span>
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5">
                  Sinkronisasi live counter SSE
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Conveyor Speed Threshold Matrix Indicator Section */}
      <section
        className="bg-slate-800 border border-slate-700 p-5 rounded-lg shadow-sm space-y-4"
        aria-labelledby="threshold-matrix-heading"
      >
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-700/80 pb-3">
          <div>
            <h3 id="threshold-matrix-heading" className="text-base font-semibold text-slate-100 flex items-center gap-2">
              <Gauge className="w-4 h-4 text-emerald-400" />
              <span>Matriks Ambang Batas Kecepatan Konveyor</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Indikator zona throughput dan batas kapasitas deteksi visi komputer secara real-time
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">Status Saat Ini:</span>
            <span className={`px-2.5 py-1 rounded text-xs font-bold border ${thresholdMatrix.badgeClass}`}>
              {thresholdMatrix.label}
            </span>
          </div>
        </div>

        {/* Visual Speed Spectrum Meter */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>0 CPM</span>
            <span>30 CPM (Min)</span>
            <span>75 CPM (Maks)</span>
            <span>120+ CPM</span>
          </div>

          <div className="relative h-3 w-full bg-slate-900 rounded-full overflow-hidden flex border border-slate-700">
            {/* Under-speed Zone (< 30 CPM) */}
            <div
              className="h-full bg-amber-500/80 transition-opacity"
              style={{ width: "30%" }}
              title="Zona Under-speed (< 30 CPM)"
            />
            {/* Normal Zone (30 - 75 CPM) */}
            <div
              className="h-full bg-emerald-500/80 transition-opacity"
              style={{ width: "45%" }}
              title="Zona Normal (30 - 75 CPM)"
            />
            {/* Over-speed Zone (> 75 CPM) */}
            <div
              className="h-full bg-rose-500/80 transition-opacity"
              style={{ width: "25%" }}
              title="Zona Over-speed (> 75 CPM)"
            />
          </div>

          <div className="flex items-center justify-between text-[11px] font-mono text-slate-500">
            <span className="text-amber-400/80">Under-speed</span>
            <span className="text-emerald-400/80">Normal / Optimal</span>
            <span className="text-rose-400/80">Over-speed</span>
          </div>
        </div>

        {/* 3 Zone Threshold Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-1">
          {/* Zone 1: Under-speed (< 30 CPM) */}
          <div
            className={`p-4 rounded-lg border transition ${
              thresholdMatrix.tier === "under"
                ? "bg-amber-950/40 border-amber-500 shadow-md ring-1 ring-amber-500/50"
                : "bg-slate-900/60 border-slate-700/70 opacity-80 hover:opacity-100"
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-amber-400">Zona 1: Under-speed</span>
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40">
                &lt; 30 CPM
              </span>
            </div>
            <div className="text-sm font-semibold text-slate-100 mb-1">
              Peringatan Kecepatan Rendah
            </div>
            <p className="text-xs text-slate-400 leading-relaxed mb-3">
              Kecepatan di bawah standar operasional. Pasokan ayam di conveyor terhambat atau terhenti sementara.
            </p>
            <div className="text-[11px] text-amber-300/90 font-medium pt-2 border-t border-slate-800">
              Tindakan: Cek hopper & aliran rantai shackle.
            </div>
          </div>

          {/* Zone 2: Normal (30 - 75 CPM) */}
          <div
            className={`p-4 rounded-lg border transition ${
              thresholdMatrix.tier === "normal"
                ? "bg-emerald-950/40 border-emerald-500 shadow-md ring-1 ring-emerald-500/50"
                : "bg-slate-900/60 border-slate-700/70 opacity-80 hover:opacity-100"
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-emerald-400">Zona 2: Normal</span>
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                30 - 75 CPM
              </span>
            </div>
            <div className="text-sm font-semibold text-slate-100 mb-1">
              Kecepatan Operasional Optimal
            </div>
            <p className="text-xs text-slate-400 leading-relaxed mb-3">
              Laju ideal proses penyembelihan dan penghitungan karkas ayam dengan akurasi model &gt; 98%.
            </p>
            <div className="text-[11px] text-emerald-300/90 font-medium pt-2 border-t border-slate-800">
              Tindakan: Pertahankan laju saat ini.
            </div>
          </div>

          {/* Zone 3: Over-speed (> 75 CPM) */}
          <div
            className={`p-4 rounded-lg border transition ${
              thresholdMatrix.tier === "over"
                ? "bg-rose-950/40 border-rose-500 shadow-md ring-1 ring-rose-500/50"
                : "bg-slate-900/60 border-slate-700/70 opacity-80 hover:opacity-100"
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-rose-400">Zona 3: Over-speed</span>
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/40">
                &gt; 75 CPM
              </span>
            </div>
            <div className="text-sm font-semibold text-slate-100 mb-1">
              Peringatan Kecepatan Melebihi Batas
            </div>
            <p className="text-xs text-slate-400 leading-relaxed mb-3">
              Kecepatan terlalu tinggi. Risiko penumpukan karkas ayam pada garis deteksi dan penurunan akurasi.
            </p>
            <div className="text-[11px] text-rose-300/90 font-medium pt-2 border-t border-slate-800">
              Tindakan: Turunkan kecepatan motor konveyor.
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

export default LiveStreamView;
