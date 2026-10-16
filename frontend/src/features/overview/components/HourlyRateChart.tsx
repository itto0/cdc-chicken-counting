import ReactECharts from "echarts-for-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import type { AggregateItemDTO } from "@/types";

interface HourlyRateChartProps {
  data: AggregateItemDTO[];
}

export function HourlyRateChart({ data }: HourlyRateChartProps) {
  const times = data.map((d) => d.bucket);
  const counts = data.map((d) => d.count);
  const rates = data.map((d) => d.rate_per_min);

  const option = {
    tooltip: {
      trigger: "axis",
      backgroundColor: "#ffffff",
      borderColor: "#e2e8f0",
      textStyle: { color: "#0f172a", fontSize: 12 },
    },
    legend: {
      data: ["Jumlah Ayam", "Kecepatan (cpm)"],
      bottom: 0,
      textStyle: { color: "#64748b" },
    },
    grid: {
      top: "12%",
      left: "3%",
      right: "4%",
      bottom: "15%",
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: times.length > 0 ? times : ["08:00", "09:00", "10:00", "11:00", "12:00"],
      axisLine: { lineStyle: { color: "#cbd5e1" } },
      axisLabel: { color: "#64748b" },
    },
    yAxis: [
      {
        type: "value",
        name: "Jumlah (ekor)",
        splitLine: { lineStyle: { color: "#f1f5f9" } },
        axisLabel: { color: "#64748b" },
      },
      {
        type: "value",
        name: "cpm",
        splitLine: { show: false },
        axisLabel: { color: "#64748b" },
      },
    ],
    series: [
      {
        name: "Jumlah Ayam",
        type: "bar",
        data: counts.length > 0 ? counts : [5120, 6840, 7210, 6950, 2100],
        itemStyle: { color: "#10b981", borderRadius: [4, 4, 0, 0] },
      },
      {
        name: "Kecepatan (cpm)",
        type: "line",
        yAxisIndex: 1,
        smooth: true,
        data: rates.length > 0 ? rates : [102, 124, 128, 122, 45],
        itemStyle: { color: "#3b82f6" },
        lineStyle: { width: 3 },
      },
    ],
  };

  return (
    <Card className="mt-4">
      <CardHeader>
        <CardTitle>Laju Penghitungan per Jam</CardTitle>
      </CardHeader>
      <CardContent>
        <ReactECharts option={option} style={{ height: "320px", width: "100%" }} />
      </CardContent>
    </Card>
  );
}
