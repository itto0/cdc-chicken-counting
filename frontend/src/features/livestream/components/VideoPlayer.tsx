import React, { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Eye, RotateCw } from "lucide-react";

interface VideoPlayerProps {
  canvasRef?: React.RefObject<HTMLCanvasElement | null>;
  previewUrl?: string;
  isConnected: boolean;
  onRetry?: () => void;
}

export function VideoPlayer({ canvasRef, previewUrl, isConnected, onRetry }: VideoPlayerProps) {
  const [imgError, setImgError] = useState(false);

  return (
    <Card className="overflow-hidden bg-slate-900 border-slate-300 shadow-sm">
      <CardContent className="p-0 relative flex items-center justify-center min-h-[380px] bg-slate-950">
        {previewUrl ? (
          <img
            src={previewUrl}
            alt="Live stream feed"
            className="max-w-full max-h-[600px] object-contain"
            onLoad={() => setImgError(false)}
            onError={() => setImgError(true)}
          />
        ) : canvasRef ? (
          <canvas ref={canvasRef as any} className="max-w-full h-auto object-contain" />
        ) : null}

        {(!isConnected || imgError) && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-900/85 text-white p-4 text-center">
            <Eye className="w-10 h-10 text-slate-400 mb-2 animate-pulse" />
            <p className="text-sm font-medium">Menghubungkan ke aliran video lini...</p>
            <p className="text-xs text-slate-400 mt-1 max-w-sm">
              Pastikan servis kamera RTSP aktif di backend untuk melihat umpan visual secara langsung
            </p>
            {onRetry && (
              <button
                type="button"
                onClick={() => {
                  setImgError(false);
                  onRetry();
                }}
                className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-md border border-slate-600 transition"
              >
                <RotateCw className="w-3.5 h-3.5" />
                <span>Coba Hubungkan Ulang</span>
              </button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
