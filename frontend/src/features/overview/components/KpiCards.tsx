import { Gauge, Target, LineChart } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import type { LineSummaryResponse } from "@/types";

interface KpiCardsProps {
  summary: LineSummaryResponse;
}

export function KpiCards({ summary }: KpiCardsProps) {
  const status = (summary.camera_status ?? "offline").toLowerCase();
  const isOnline = status === "online";
  const isDegraded = status === "degraded";

  const statusDotClass = isOnline
    ? "bg-emerald-500 ring-4 ring-emerald-100"
    : isDegraded
    ? "bg-amber-500 ring-4 ring-amber-100"
    : "bg-rose-500 ring-4 ring-rose-100";

  const statusLabel = isOnline
    ? "Online"
    : isDegraded
    ? "Degraded"
    : "Offline";

  const accuracy = summary.detection_accuracy_pct ?? 99.2;
  const formattedAccuracy = accuracy.toLocaleString("id-ID", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 1. Total Ayam Terhitung Hari Ini */}
      <Card className="rounded-2xl border-slate-200/80 shadow-sm bg-white">
        <CardContent className="p-5 flex items-center justify-between">
          <div>
            <p className="text-xs font-normal text-slate-500">
              Total Ayam Terhitung Hari Ini
            </p>
            <div className="flex items-baseline gap-2 mt-2">
              <span className="text-2xl font-bold tracking-tight text-slate-900">
                {(summary.total_count ?? 0).toLocaleString("id-ID")}
              </span>
              <span className="text-xs font-semibold text-slate-700">ekor</span>
              <span
                className="inline-flex items-center text-xs font-bold text-slate-900 ml-0.5"
                aria-hidden="true"
              >
                ↗
              </span>
            </div>
          </div>
          <div className="text-slate-800" aria-hidden="true">
            <LineChart className="w-6 h-6 stroke-[1.75]" />
          </div>
        </CardContent>
      </Card>

      {/* 2. Laju Rata-rata */}
      <Card className="rounded-2xl border-slate-200/80 shadow-sm bg-white">
        <CardContent className="p-5 flex items-center justify-between">
          <div>
            <p className="text-xs font-normal text-slate-500">Laju Rata-rata</p>
            <div className="flex items-baseline gap-1.5 mt-2">
              <span className="text-2xl font-bold tracking-tight text-slate-900">
                {Math.round(summary.current_speed_cpm ?? 120).toLocaleString("id-ID")}
              </span>
              <span className="text-xs font-semibold text-slate-700">ekor/menit</span>
            </div>
          </div>
          <div className="text-slate-800" aria-hidden="true">
            <Gauge className="w-6 h-6 stroke-[1.75]" />
          </div>
        </CardContent>
      </Card>

      {/* 3. Status Kamera */}
      <Card className="rounded-2xl border-slate-200/80 shadow-sm bg-white">
        <CardContent className="p-5 flex items-center justify-between">
          <div>
            <p className="text-xs font-normal text-slate-500">Status Kamera</p>
            <div className="flex items-center gap-2 mt-2">
              <span
                className={`w-2.5 h-2.5 rounded-full ${statusDotClass}`}
                aria-hidden="true"
              />
              <span className="text-2xl font-bold tracking-tight text-slate-900">
                {statusLabel}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 4. Akurasi Deteksi */}
      <Card className="rounded-2xl border-slate-200/80 shadow-sm bg-white">
        <CardContent className="p-5 flex items-center justify-between">
          <div>
            <p className="text-xs font-normal text-slate-500">Akurasi Deteksi</p>
            <div className="mt-2">
              <span className="text-2xl font-bold tracking-tight text-slate-900">
                {formattedAccuracy}%
              </span>
            </div>
          </div>
          <div className="text-slate-800" aria-hidden="true">
            <Target className="w-6 h-6 stroke-[1.75]" />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
