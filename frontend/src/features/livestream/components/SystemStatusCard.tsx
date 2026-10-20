import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface SystemStatusCardProps {
  fps?: number;
  latencyMs?: number;
  streamState?: "online" | "degraded" | "offline" | string;
}

export function SystemStatusCard({
  fps = 0,
  latencyMs = 0,
  streamState = "offline",
}: SystemStatusCardProps) {
  const normalizedState = (streamState || "offline").toLowerCase();

  const getStatusColor = () => {
    switch (normalizedState) {
      case "online":
        return {
          dot: "bg-emerald-500 ring-4 ring-emerald-100",
          text: "text-emerald-700",
          label: "Online",
        };
      case "degraded":
        return {
          dot: "bg-amber-500 ring-4 ring-amber-100",
          text: "text-amber-700",
          label: "Degraded",
        };
      default:
        return {
          dot: "bg-rose-500 ring-4 ring-rose-100",
          text: "text-rose-700",
          label: "Offline",
        };
    }
  };

  const statusStyle = getStatusColor();
  const hasLatency = latencyMs > 0 && normalizedState !== "offline";

  return (
    <Card className="rounded-2xl border-slate-200/80 shadow-sm bg-white">
      <CardHeader className="p-4 pb-2">
        <CardTitle className="text-sm font-semibold text-slate-800">
          Status Sistem
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 pt-2">
        <div className="grid grid-cols-3 divide-x divide-slate-100 text-center sm:text-left">
          {/* FPS */}
          <div className="px-2 first:pl-0">
            <span className="text-xs text-slate-500 font-medium block mb-1">
              FPS
            </span>
            <span className="text-2xl font-bold tracking-tight text-slate-900">
              {Math.round(fps)}
            </span>
          </div>

          {/* Latensi */}
          <div className="px-3">
            <span className="text-xs text-slate-500 font-medium block mb-1">
              Latensi
            </span>
            {hasLatency ? (
              <span className="text-2xl font-bold tracking-tight text-slate-900">
                {Math.round(latencyMs)}{" "}
                <span className="text-sm font-normal text-slate-500">ms</span>
              </span>
            ) : (
              <span className="text-2xl font-bold tracking-tight text-slate-900">
                -
              </span>
            )}
          </div>

          {/* Status Edge */}
          <div className="px-3 last:pr-0">
            <span className="text-xs text-slate-500 font-medium block mb-1">
              Status Edge
            </span>
            <div className="flex items-center gap-2 mt-1.5">
              <span
                className={`w-2.5 h-2.5 rounded-full ${statusStyle.dot} shrink-0`}
                aria-hidden="true"
              />
              <span className={`text-base font-bold ${statusStyle.text}`}>
                {statusStyle.label}
              </span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
