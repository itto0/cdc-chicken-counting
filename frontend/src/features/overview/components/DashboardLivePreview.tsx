import { useState, useEffect } from "react";
import { Play, Pause, RotateCw, Eye } from "lucide-react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface DashboardLivePreviewProps {
  lineId: string;
  lineName?: string;
  previewUrl: string;
  isConnected: boolean;
  onRetry?: () => void;
  className?: string;
}

export function DashboardLivePreview({
  lineId,
  lineName,
  previewUrl,
  isConnected,
  onRetry,
  className,
}: DashboardLivePreviewProps) {
  const [isPlaying, setIsPlaying] = useState(true);
  const [imgError, setImgError] = useState(false);
  const formatClock = () => {
    const d = new Date();
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  };

  const [clock, setClock] = useState(formatClock);

  useEffect(() => {
    const timer = setInterval(() => {
      setClock(formatClock());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    setImgError(false);
  }, [previewUrl]);

  const displayName = lineName || lineId || "Lini A";

  return (
    <Card
      className={cn("rounded-2xl border-slate-200/80 shadow-sm bg-white overflow-hidden", className)}
      data-line-id={lineId}
    >
      {/* Card Header Title */}
      <div className="p-5 pb-3">
        <h3 className="text-sm font-semibold text-slate-800">
          Pratinjau Kamera Langsung: {displayName}
        </h3>
      </div>

      {/* Video / Stream Container */}
      <div className="relative bg-slate-950 aspect-[21/9] sm:aspect-[2.4/1] w-full flex items-center justify-center overflow-hidden">
        {isPlaying && previewUrl && !imgError ? (
          <img
            src={previewUrl}
            alt={`Live stream ${displayName}`}
            className="w-full h-full object-contain"
            onError={() => setImgError(true)}
            onLoad={() => setImgError(false)}
          />
        ) : null}

        {/* Offline / Paused / Error Overlay */}
        {(!isConnected || !previewUrl || imgError || !isPlaying) && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-900/80 text-white p-4 text-center">
            <Eye className="w-8 h-8 text-slate-400 mb-2 animate-pulse" />
            <p className="text-sm font-medium">
              {!isPlaying
                ? "Streaming dijeda"
                : "Menghubungkan ke aliran video..."}
            </p>
            {onRetry && (
              <button
                type="button"
                onClick={() => {
                  setImgError(false);
                  setIsPlaying(true);
                  onRetry();
                }}
                className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg border border-slate-600 transition"
              >
                <RotateCw className="w-3.5 h-3.5" />
                <span>Hubungkan Ulang</span>
              </button>
            )}
          </div>
        )}

        {/* Video Player Controls Bar matching client mockup */}
        <div className="absolute bottom-0 left-0 right-0 h-10 bg-gradient-to-t from-black/80 via-black/40 to-transparent flex items-center justify-between px-4 text-white text-xs">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setIsPlaying((p) => !p)}
              className="hover:text-slate-200 transition-colors"
              aria-label={isPlaying ? "Jeda video" : "Putar video"}
            >
              {isPlaying ? (
                <Pause className="w-4 h-4 fill-white" />
              ) : (
                <Play className="w-4 h-4 fill-white" />
              )}
            </button>
            <div className="flex items-center gap-1.5 text-[11px] text-slate-300">
              <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
              <span>LIVE</span>
            </div>
          </div>

          <div className="text-[11px] text-slate-300 font-mono">
            {clock}
          </div>
        </div>
      </div>
    </Card>
  );
}
