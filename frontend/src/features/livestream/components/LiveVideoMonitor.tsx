import { useState, useEffect } from "react";
import { Play, Pause, RefreshCw, AlertCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface LiveVideoMonitorProps {
  lineId: string;
  previewUrl: string;
  totalToday: number;
  isConnected: boolean;
  onRetry?: () => void;
}

export function LiveVideoMonitor({
  lineId,
  previewUrl,
  totalToday,
  isConnected,
  onRetry,
}: LiveVideoMonitorProps) {
  const [isPlaying, setIsPlaying] = useState(true);
  const [imgError, setImgError] = useState(false);

  // Reset error when URL changes
  useEffect(() => {
    setImgError(false);
  }, [previewUrl]);

  const togglePlayback = () => {
    setIsPlaying((prev) => !prev);
  };

  const showOverlay = !isConnected || !previewUrl || imgError || !isPlaying;

  return (
    <Card className="rounded-2xl border-slate-200/80 shadow-xs bg-white overflow-hidden" data-line-id={lineId}>
      <CardHeader className="p-4 pb-2">
        <CardTitle className="text-sm font-semibold text-slate-800">
          Pratinjau Kamera Langsung
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 pt-1">
        <div className="relative aspect-[16/10] sm:aspect-[16/9] w-full rounded-xl bg-slate-950 overflow-hidden flex flex-col justify-between">
          {/* MJPEG Stream Image */}
          {isPlaying && previewUrl && !imgError && (
            <img
              src={previewUrl}
              alt="Live video stream"
              className="absolute inset-0 w-full h-full object-cover"
              onError={() => setImgError(true)}
            />
          )}

          {/* Overlay fallback for paused or disconnected states */}
          {showOverlay && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-950/85 text-slate-300 p-6 text-center z-10 backdrop-blur-xs">
              {!isPlaying ? (
                <div className="flex flex-col items-center gap-2">
                  <Pause className="w-8 h-8 text-slate-400" />
                  <p className="text-sm font-medium">Streaming Dijeda</p>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-3">
                  <AlertCircle className="w-8 h-8 text-rose-400" />
                  <div>
                    <p className="text-sm font-semibold text-slate-100">
                      Kamera Offline / Terputus
                    </p>
                    <p className="text-xs text-slate-400 mt-1 max-w-sm">
                      Menghubungi endpoint pratinjau deteksi ayam konveyor...
                    </p>
                  </div>
                  {onRetry && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setImgError(false);
                        onRetry();
                      }}
                      className="mt-1 bg-slate-800/80 border-slate-700 text-slate-200 hover:bg-slate-700 hover:text-white"
                    >
                      <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
                      Hubungkan Ulang
                    </Button>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Top LIVE Tag */}
          <div className="relative z-20 p-3 flex items-center justify-between pointer-events-none">
            <div className="flex items-center gap-1.5 bg-slate-900/80 backdrop-blur-xs px-2.5 py-1 rounded-full text-[11px] font-semibold text-white">
              <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
              <span>LIVE</span>
            </div>
          </div>

          {/* Overlay Bar Bottom: Terhitung Count */}
          <div className="relative z-20 w-full bg-[#1e293b]/90 backdrop-blur-xs text-white py-2.5 px-4 flex items-center justify-center border-t border-slate-800/60 shadow-md">
            <span className="text-lg sm:text-2xl font-bold tracking-tight text-white">
              Terhitung: {(totalToday ?? 0).toLocaleString("id-ID")}
            </span>
          </div>
        </div>

        {/* Player Controls Bar */}
        <div className="flex items-center justify-between mt-3 pt-2 border-t border-slate-100 text-xs text-slate-500">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={togglePlayback}
              className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-700 transition-colors"
              aria-label={isPlaying ? "Jeda streaming" : "Putar streaming"}
            >
              {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            </button>
            <span className="font-medium text-slate-700">
              {isPlaying ? "Live Streaming Aktif" : "Streaming Dijeda"}
            </span>
          </div>

          {onRetry && (
            <button
              type="button"
              onClick={() => {
                setImgError(false);
                onRetry();
              }}
              className="flex items-center gap-1.5 hover:text-slate-800 transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Muat Ulang</span>
            </button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
