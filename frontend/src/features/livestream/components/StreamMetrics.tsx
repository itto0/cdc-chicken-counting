import { Activity, Clock, Gauge, Sparkles, Video } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

interface StreamMetricsProps {
  totalToday?: number;
  liveSpeed?: number;
  fps: number;
  latencyMs: number;
  cameraStatus: string;
}

export function StreamMetrics({
  totalToday = 0,
  liveSpeed = 0,
  fps,
  latencyMs,
  cameraStatus,
}: StreamMetricsProps) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-4">
      {/* Total Chickens Counted Live */}
      <Card className="col-span-2 sm:col-span-1 border-emerald-200 bg-emerald-50/30">
        <CardContent className="p-3.5 flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-emerald-800">Total Hari Ini</p>
            <p className="text-xl font-bold text-emerald-950 mt-0.5">
              {totalToday.toLocaleString("id-ID")}
              <span className="text-xs font-normal text-emerald-700 ml-1">ekor</span>
            </p>
          </div>
          <div className="p-2 rounded-lg bg-emerald-100 text-emerald-700">
            <Sparkles className="w-4 h-4" />
          </div>
        </CardContent>
      </Card>

      {/* Live Conveyor Speed */}
      <Card>
        <CardContent className="p-3.5 flex items-center justify-between">
          <div>
            <p className="text-xs text-slate-500">Laju Konveyor</p>
            <p className="text-xl font-bold text-slate-800 mt-0.5">
              {liveSpeed.toFixed(1)}
              <span className="text-xs font-normal text-slate-500 ml-1">cpm</span>
            </p>
          </div>
          <div className="p-2 rounded-lg bg-amber-50 text-amber-600">
            <Gauge className="w-4 h-4" />
          </div>
        </CardContent>
      </Card>

      {/* Camera Status */}
      <Card>
        <CardContent className="p-3.5 flex items-center justify-between">
          <div>
            <p className="text-xs text-slate-500">Status Kamera</p>
            <p className="text-sm font-semibold capitalize text-slate-800 mt-1">{cameraStatus}</p>
          </div>
          <div className="p-2 rounded-lg bg-slate-100 text-slate-600">
            <Video className="w-4 h-4 text-emerald-600" />
          </div>
        </CardContent>
      </Card>

      {/* Processing FPS */}
      <Card>
        <CardContent className="p-3.5 flex items-center justify-between">
          <div>
            <p className="text-xs text-slate-500">Frame Rate</p>
            <p className="text-sm font-semibold text-slate-800 mt-1">{fps.toFixed(1)} FPS</p>
          </div>
          <div className="p-2 rounded-lg bg-blue-50 text-blue-600">
            <Activity className="w-4 h-4" />
          </div>
        </CardContent>
      </Card>

      {/* Latency */}
      <Card>
        <CardContent className="p-3.5 flex items-center justify-between">
          <div>
            <p className="text-xs text-slate-500">Latensi Pemrosesan</p>
            <p className="text-sm font-semibold text-slate-800 mt-1">{latencyMs} ms</p>
          </div>
          <div className="p-2 rounded-lg bg-slate-50 text-slate-600">
            <Clock className="w-4 h-4 text-amber-600" />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
