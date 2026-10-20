import ReactECharts from "echarts-for-react";
import { LineChart as LineChartIcon } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import type { AggregateItemDTO } from "@/types";
import { formatBucketHour } from "@/utils/time";

interface HourlyRateChartProps {
  data?: AggregateItemDTO[];
}

export function HourlyRateChart({ data = [] }: HourlyRateChartProps) {
  const hasData = (data ?? []).length > 0 && (data ?? []).some((d) => (d.count ?? 0) > 0);
  const times = hasData ? (data ?? []).map((d) => formatBucketHour(d.bucket)) : [];
  const counts = hasData ? (data ?? []).map((d) => d.count) : [];

  const option = {
    tooltip: {
      trigger: "axis",
      backgroundColor: "#ffffff",
      borderColor: "#e2e8f0",
      textStyle: { color: "#0f172a", fontSize: 12 },
      formatter: "{b}<br /><span style='font-weight:600;'>{c} ekor</span>",
    },
    grid: {
      top: "10%",
      left: "2%",
      right: "2%",
      bottom: "5%",
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: times,
      boundaryGap: false,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: "#94a3b8", fontSize: 11 },
    },
    yAxis: {
      type: "value",
      splitLine: {
        show: true,
        lineStyle: { color: "#f1f5f9", width: 1 },
      },
      axisLabel: { show: false },
    },
    series: [
      {
        name: "Penghitungan",
        type: "line",
        smooth: 0.5,
        symbol: "none",
        data: counts,
        lineStyle: {
          color: "#2563eb",
          width: 2.5,
        },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(37, 99, 235, 0.22)" },
              { offset: 1, color: "rgba(37, 99, 235, 0.0)" },
            ],
          },
        },
      },
    ],
  };

  return (
    <Card className="rounded-2xl border-slate-200/80 shadow-sm bg-white">
      <div className="p-5 pb-0">
        <h3 className="text-sm font-semibold text-slate-800">
          Tren Penghitungan per Jam
        </h3>
      </div>
      <CardContent className="p-4 pt-1">
        <div className="h-[210px] w-full flex items-center justify-center">
          {hasData ? (
            <ReactECharts
              option={option}
              notMerge={true}
              style={{ height: "100%", width: "100%" }}
            />
          ) : (
            <div className="flex flex-col items-center justify-center text-center p-6 text-slate-400">
              <LineChartIcon className="w-10 h-10 mb-2 stroke-[1.25] text-slate-300" aria-hidden="true" />
              <p className="text-sm font-medium text-slate-600">Belum ada data penghitungan hari ini</p>
              <p className="text-xs text-slate-400 mt-0.5">Data grafik per jam akan muncul otomatis saat konveyor aktif</p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
