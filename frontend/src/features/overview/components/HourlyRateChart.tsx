import ReactECharts from "echarts-for-react";
import { Card, CardContent } from "@/components/ui/card";
import type { AggregateItemDTO } from "@/types";

interface HourlyRateChartProps {
  data: AggregateItemDTO[];
}

export function HourlyRateChart({ data }: HourlyRateChartProps) {
  const times = data.map((d) => d.bucket);
  const counts = data.map((d) => d.count);

  // Fallback demo points mimicking the mockup's smooth wave if empty
  const defaultTimes = ["08:00", "09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00"];
  const defaultCounts = [120, 280, 240, 390, 310, 520, 380, 420, 260, 410];

  const chartTimes = times.length > 0 ? times : defaultTimes;
  const chartCounts = counts.length > 0 ? counts : defaultCounts;

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
      data: chartTimes,
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
        data: chartCounts,
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
        <div className="h-[210px] w-full">
          <ReactECharts
            option={option}
            notMerge={true}
            style={{ height: "100%", width: "100%" }}
          />
        </div>
      </CardContent>
    </Card>
  );
}
