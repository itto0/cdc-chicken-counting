import { Target, TrendingUp, Gauge, Sparkles } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import type { LineSummaryResponse } from "@/types";

interface KpiCardsProps {
  summary: LineSummaryResponse;
}

export function KpiCards({ summary }: KpiCardsProps) {
  const attainment = summary.target_attainment_pct ?? 0;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <Card>
        <CardContent className="p-4 flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-slate-500">Total Hari Ini</p>
            <h3 className="text-2xl font-bold text-slate-900 mt-1">
              {summary.total_count.toLocaleString("id-ID")}
            </h3>
            <p className="text-[11px] text-slate-400 mt-0.5">Ekor terhitung</p>
          </div>
          <div className="p-2.5 rounded-lg bg-emerald-50 text-emerald-600">
            <Sparkles className="w-5 h-5" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4 flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-slate-500">Target Harian</p>
            <h3 className="text-2xl font-bold text-slate-900 mt-1">
              {summary.target_count.toLocaleString("id-ID")}
            </h3>
            <p className="text-[11px] text-slate-400 mt-0.5">Ekor</p>
          </div>
          <div className="p-2.5 rounded-lg bg-blue-50 text-blue-600">
            <Target className="w-5 h-5" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4 flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-slate-500">Kecepatan Saat Ini</p>
            <h3 className="text-2xl font-bold text-slate-900 mt-1">
              {summary.current_speed_cpm}{" "}
              <span className="text-xs font-normal text-slate-500">cpm</span>
            </h3>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Target: {summary.target_speed_cpm} cpm
            </p>
          </div>
          <div className="p-2.5 rounded-lg bg-amber-50 text-amber-600">
            <Gauge className="w-5 h-5" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4 flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-slate-500">Pencapaian Target</p>
            <h3 className="text-2xl font-bold text-slate-900 mt-1">
              {attainment.toFixed(1)}%
            </h3>
            <div className="w-28 bg-slate-100 rounded-full h-1.5 mt-2 overflow-hidden">
              <div
                className="bg-emerald-500 h-1.5 rounded-full"
                style={{ width: `${Math.max(0, Math.min(Number(attainment) || 0, 100))}%` }}
              />
            </div>
          </div>
          <div className="p-2.5 rounded-lg bg-purple-50 text-purple-600">
            <TrendingUp className="w-5 h-5" />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
