import { Activity, Clock, Video } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

interface StreamMetricsProps {
  fps: number;
  latencyMs: number;
  cameraStatus: string;
}

export function StreamMetrics({ fps, latencyMs, cameraStatus }: StreamMetricsProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
      <Card>
        <CardContent className="p-3.5 flex items-center justify-between">
          <div>
            <p className="text-xs text-slate-500">Status Kamera</p>
            <p className="text-sm font-semibold capitalize text-slate-800">{cameraStatus}</p>
          </div>
          <Video className="w-4 h-4 text-emerald-600" />
        </CardContent>
      </Card>
      <Card>
        <CardContent className="p-3.5 flex items-center justify-between">
          <div>
            <p className="text-xs text-slate-500">Frame Rate</p>
            <p className="text-sm font-semibold text-slate-800">{fps.toFixed(1)} FPS</p>
          </div>
          <Activity className="w-4 h-4 text-blue-600" />
        </CardContent>
      </Card>
      <Card>
        <CardContent className="p-3.5 flex items-center justify-between">
          <div>
            <p className="text-xs text-slate-500">Latensi Stream</p>
            <p className="text-sm font-semibold text-slate-800">{latencyMs} ms</p>
          </div>
          <Clock className="w-4 h-4 text-amber-600" />
        </CardContent>
      </Card>
    </div>
  );
}
