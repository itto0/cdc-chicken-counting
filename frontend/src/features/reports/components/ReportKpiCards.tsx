import { LineChart, Gauge, Target, Clock } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

export interface ReportSummaryMetrics {
  totalCount: number;
  avgRateCpm: number;
  avgAccuracyPct: number;
  totalOperationMinutes: number;
}

interface ReportKpiCardsProps {
  metrics: ReportSummaryMetrics;
}

export function ReportKpiCards({ metrics }: ReportKpiCardsProps) {
  const totalCount = metrics?.totalCount ?? 0;
  const avgRateCpm = metrics?.avgRateCpm ?? 0;
  const totalOperationMinutes = metrics?.totalOperationMinutes ?? 0;

  const safeMinutes = Math.max(
    0,
    Math.floor(Number.isFinite(totalOperationMinutes) ? totalOperationMinutes : 0)
  );
  const hours = Math.floor(safeMinutes / 60);
  const minutes = safeMinutes % 60;
  const operationTimeDisplay = `${hours} jam ${minutes} mnt`;

  const safeCount = Number.isFinite(totalCount) ? totalCount : 0;
  const formattedCount = safeCount.toLocaleString("id-ID");

  const safeRate = Number.isFinite(avgRateCpm) ? Math.round(avgRateCpm) : 0;
  const formattedRate = safeRate.toLocaleString("id-ID");

  const hasAccuracy =
    (metrics?.totalCount ?? 0) > 0 &&
    metrics?.avgAccuracyPct != null &&
    metrics.avgAccuracyPct > 0;

  const formattedAccuracy = hasAccuracy
    ? `${metrics.avgAccuracyPct.toLocaleString("id-ID", {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
      })}%`
    : "-";

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 1. Total Ayam Terhitung */}
      <Card className="rounded-2xl border-slate-200/80 shadow-sm bg-white">
        <CardContent className="p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Total Ayam Terhitung</span>
            <div
              className="p-2 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center"
              aria-hidden="true"
            >
              <LineChart className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-1.5">
            <span className="text-2xl font-bold tracking-tight text-slate-900">{formattedCount}</span>
            <span className="text-xs font-medium text-slate-500">ekor</span>
          </div>
          <p className="mt-1 text-[11px] text-slate-400">Total periode terpilih</p>
        </CardContent>
      </Card>

      {/* 2. Rata-rata Laju */}
      <Card className="rounded-2xl border-slate-200/80 shadow-sm bg-white">
        <CardContent className="p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Rata-rata Laju</span>
            <div
              className="p-2 rounded-full bg-indigo-50 text-indigo-600 flex items-center justify-center"
              aria-hidden="true"
            >
              <Gauge className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-1.5">
            <span className="text-2xl font-bold tracking-tight text-slate-900">{formattedRate}</span>
            <span className="text-xs font-medium text-slate-500">ekor/menit</span>
          </div>
          <p className="mt-1 text-[11px] text-slate-400">Laju operasional rata-rata</p>
        </CardContent>
      </Card>

      {/* 3. Akurasi Rata-rata */}
      <Card className="rounded-2xl border-slate-200/80 shadow-sm bg-white">
        <CardContent className="p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Akurasi Rata-rata</span>
            <div
              className="p-2 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center"
              aria-hidden="true"
            >
              <Target className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-1.5">
            <span className="text-2xl font-bold tracking-tight text-slate-900">{formattedAccuracy}</span>
          </div>
          {hasAccuracy && (
            <p className="mt-1 text-[11px] text-emerald-600 font-medium">Sangat Baik</p>
          )}
        </CardContent>
      </Card>

      {/* 4. Total Waktu Operasi */}
      <Card className="rounded-2xl border-slate-200/80 shadow-sm bg-white">
        <CardContent className="p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Total Waktu Operasi</span>
            <div
              className="p-2 rounded-full bg-amber-50 text-amber-600 flex items-center justify-center"
              aria-hidden="true"
            >
              <Clock className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-1.5">
            <span className="text-2xl font-bold tracking-tight text-slate-900">{operationTimeDisplay}</span>
          </div>
          <p className="mt-1 text-[11px] text-slate-400">Akumulasi interval aktif</p>
        </CardContent>
      </Card>
    </div>
  );
}
