import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import {
  Activity,
  Gauge,
  Video,
  ShieldCheck,
  TrendingUp,
  Target,
  Clock,
  Sparkles,
  Server,
} from "lucide-react";
import { LineSummary } from "../types";

export interface OverviewViewProps {
  summary?: LineSummary;
}

const DEFAULT_SUMMARY: LineSummary = {
  line_id: "line-1",
  total_today: 48320,
  avg_rate_per_min: 118,
  target: 62000,
  attainment_pct: 77.9,
  camera_status: "online",
  detection_confidence_pct: 98.4,
};

// Hourly counts for shifts 08:00 - 17:00 WIB (sum matches 48,320)
const HOURLY_DATA = [
  { time: "08:00", count: 5120, rate: 102 },
  { time: "09:00", count: 6840, rate: 124 },
  { time: "10:00", count: 7210, rate: 128 },
  { time: "11:00", count: 6950, rate: 122 },
  { time: "12:00", count: 2100, rate: 45 }, // break / conveyor cleaning
  { time: "13:00", count: 6400, rate: 116 },
  { time: "14:00", count: 7100, rate: 126 },
  { time: "15:00", count: 6600, rate: 119 },
  { time: "16:00", count: 0, rate: 0 }, // upcoming
  { time: "17:00", count: 0, rate: 0 }, // upcoming
];

export function OverviewView({ summary = DEFAULT_SUMMARY }: OverviewViewProps) {
  const currentSummary = summary ?? DEFAULT_SUMMARY;
  const remainingBirds = Math.max(0, currentSummary.target - currentSummary.total_today);
  const attainmentRate = Math.min(100, currentSummary.attainment_pct);

  // ECharts Trend Area Chart Option
  const trendOption = useMemo(() => {
    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        backgroundColor: "#1e293b",
        borderColor: "#475569",
        borderWidth: 1,
        textStyle: { color: "#f8fafc", fontSize: 12 },
        formatter: (params: Array<{ name: string; value: number; dataIndex: number }>) => {
          const item = params[0];
          if (!item) return "";
          const meta = HOURLY_DATA[item.dataIndex];
          return `
            <div style="font-weight: 600; margin-bottom: 4px; color: #34d399;">
              Pukul ${item.name} WIB
            </div>
            <div>Volume: <strong>${item.value.toLocaleString()}</strong> ekor</div>
            <div style="color: #94a3b8; font-size: 11px;">Kecepatan: ~${meta?.rate || 0} birds/min</div>
          `;
        },
      },
      grid: {
        top: "12%",
        left: "3%",
        right: "4%",
        bottom: "8%",
        containLabel: true,
      },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: HOURLY_DATA.map((d) => d.time),
        axisLine: { lineStyle: { color: "#475569" } },
        axisLabel: { color: "#94a3b8", fontSize: 12 },
      },
      yAxis: {
        type: "value",
        name: "Ekor / Jam",
        nameTextStyle: { color: "#64748b", fontSize: 11 },
        splitLine: {
          lineStyle: { color: "#334155", type: "dashed" },
        },
        axisLabel: {
          color: "#94a3b8",
          fontSize: 11,
          formatter: (val: number) => (val >= 1000 ? `${val / 1000}k` : `${val}`),
        },
      },
      series: [
        {
          name: "Penghitungan Ayam",
          type: "line",
          smooth: true,
          showSymbol: true,
          symbolSize: 6,
          itemStyle: {
            color: "#10b981",
            borderWidth: 2,
            borderColor: "#065f46",
          },
          lineStyle: {
            width: 3,
            color: "#10b981",
          },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(16, 185, 129, 0.45)" },
                { offset: 0.8, color: "rgba(16, 185, 129, 0.05)" },
                { offset: 1, color: "rgba(16, 185, 129, 0)" },
              ],
            },
          },
          data: HOURLY_DATA.map((d) => d.count),
        },
      ],
    };
  }, []);

  // ECharts Radial Attainment Gauge Option
  const gaugeOption = useMemo(() => {
    return {
      backgroundColor: "transparent",
      series: [
        {
          type: "gauge",
          startAngle: 200,
          endAngle: -20,
          min: 0,
          max: 100,
          splitNumber: 5,
          itemStyle: {
            color: "#10b981",
          },
          progress: {
            show: true,
            width: 14,
            roundCap: true,
            itemStyle: {
              color: {
                type: "linear",
                x: 0,
                y: 0,
                x2: 1,
                y2: 0,
                colorStops: [
                  { offset: 0, color: "#06b6d4" },
                  { offset: 1, color: "#10b981" },
                ],
              },
            },
          },
          pointer: {
            show: false,
          },
          axisLine: {
            roundCap: true,
            lineStyle: {
              width: 14,
              color: [[1, "#1e293b"]],
            },
          },
          axisTick: {
            show: false,
          },
          splitLine: {
            show: false,
          },
          axisLabel: {
            show: false,
          },
          title: {
            show: true,
            offsetCenter: [0, "30%"],
            fontSize: 12,
            color: "#94a3b8",
          },
          detail: {
            valueAnimation: true,
            offsetCenter: [0, "-10%"],
            fontSize: 28,
            fontWeight: "bold",
            formatter: "{value}%",
            color: "#34d399",
          },
          data: [
            {
              value: currentSummary.attainment_pct,
              name: "Pencapaian Target",
            },
          ],
        },
      ],
    };
  }, [currentSummary.attainment_pct]);

  return (
    <div className="space-y-6">
      {/* Header Info / Status Banner */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-800/80 border border-slate-700/80 px-5 py-3 rounded-lg shadow-sm">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-emerald-500/10 border border-emerald-500/20 rounded-md text-emerald-400">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
              <span>Conveyor Line 1</span>
              <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-medium">
                Aktif · Produksi Normal
              </span>
            </h3>
            <p className="text-xs text-slate-400">
              Shift Operasional: 08:00 – 17:00 WIB · Target Harian 62.000 Ekor
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4 text-xs text-slate-400">
          <div className="flex items-center gap-1.5">
            <Clock className="w-4 h-4 text-slate-500" />
            <span>Pembaruan Terakhir: Real-time</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Server className="w-4 h-4 text-emerald-400" />
            <span className="text-slate-300 font-medium">Edge Node Online</span>
          </div>
        </div>
      </div>

      {/* KPI Cards (Mobile-first responsive grid: 1 col on mobile, 2 on tablet, 4 on desktop) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Total Hari Ini */}
        <div className="bg-slate-800 border border-slate-700 p-5 rounded-lg shadow-sm hover:border-slate-600 transition">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-slate-400">Total Hari Ini</span>
            <div className="p-2 bg-emerald-500/10 text-emerald-400 rounded-md">
              <TrendingUp className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl font-extrabold text-emerald-400 mt-2">
            {currentSummary.total_today.toLocaleString()}
          </div>
          <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-700/60">
            <span className="text-xs text-slate-500">Ekor ayam terhitung</span>
            <span className="text-xs font-medium text-emerald-400/90 bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-800/40">
              +12.4% vs kemarin
            </span>
          </div>
        </div>

        {/* Card 2: Kecepatan Rata-rata */}
        <div className="bg-slate-800 border border-slate-700 p-5 rounded-lg shadow-sm hover:border-slate-600 transition">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-slate-400">Kecepatan Rata-rata</span>
            <div className="p-2 bg-cyan-500/10 text-cyan-400 rounded-md">
              <Gauge className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl font-extrabold text-cyan-400 mt-2">
            {currentSummary.avg_rate_per_min} <span className="text-lg font-normal text-slate-400">/min</span>
          </div>
          <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-700/60">
            <span className="text-xs text-slate-500">Target: ~120 birds/min</span>
            <span className="text-xs font-medium text-cyan-300 bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-800/40">
              Optimal
            </span>
          </div>
        </div>

        {/* Card 3: Status Kamera */}
        <div className="bg-slate-800 border border-slate-700 p-5 rounded-lg shadow-sm hover:border-slate-600 transition">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-slate-400">Status Kamera</span>
            <div className="p-2 bg-indigo-500/10 text-indigo-400 rounded-md">
              <Video className="w-4 h-4" />
            </div>
          </div>
          <div className="flex items-center gap-2.5 mt-2">
            <span
              className={`w-3.5 h-3.5 rounded-full ${
                currentSummary.camera_status === "online"
                  ? "bg-emerald-500 shadow-lg shadow-emerald-500/50 animate-pulse"
                  : currentSummary.camera_status === "degraded"
                  ? "bg-amber-500 shadow-lg shadow-amber-500/50"
                  : "bg-red-500 shadow-lg shadow-red-500/50"
              }`}
            />
            <span className="text-2xl font-bold uppercase tracking-wide text-slate-100">
              {currentSummary.camera_status}
            </span>
          </div>
          <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-700/60">
            <span className="text-xs text-slate-500">30.0 FPS · Latensi 38ms</span>
            <span className="text-xs font-mono text-slate-400">1080p RTSP</span>
          </div>
        </div>

        {/* Card 4: Akurasi Deteksi */}
        <div className="bg-slate-800 border border-slate-700 p-5 rounded-lg shadow-sm hover:border-slate-600 transition">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-slate-400">Akurasi Deteksi</span>
            <div className="p-2 bg-amber-500/10 text-amber-400 rounded-md">
              <ShieldCheck className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl font-extrabold text-amber-400 mt-2">
            {currentSummary.detection_confidence_pct}%
          </div>
          <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-700/60">
            <span className="text-xs text-slate-500">YOLO26 nano inference</span>
            <span className="text-xs font-medium text-amber-300 bg-amber-950/60 px-1.5 py-0.5 rounded border border-amber-800/40 flex items-center gap-1">
              <Sparkles className="w-3 h-3" /> NPU ONNX
            </span>
          </div>
        </div>
      </div>

      {/* Target Progress Bar & Attainment Gauge Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Target Attainment Radial Gauge & Breakdown Card */}
        <div className="bg-slate-800 border border-slate-700 p-6 rounded-lg shadow flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Target className="w-5 h-5 text-emerald-400" />
                <h4 className="font-semibold text-slate-200">Pencapaian Target Harian</h4>
              </div>
              <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold">
                Shift 1 & 2
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Evaluasi target kuota produksi pemotongan unggas per hari
            </p>
          </div>

          {/* Radial Attainment Gauge */}
          <div className="h-44 w-full -my-2 flex items-center justify-center">
            <ReactECharts
              option={gaugeOption}
              style={{ height: "100%", width: "100%" }}
              notMerge={true}
              lazyUpdate={true}
            />
          </div>

          {/* Metric Breakdown */}
          <div className="space-y-3 pt-2 border-t border-slate-700/60">
            <div className="flex justify-between items-center text-sm">
              <span className="text-slate-400">Target Kuota:</span>
              <span className="font-semibold text-slate-200">
                {currentSummary.target.toLocaleString()} ekor
              </span>
            </div>
            <div className="flex justify-between items-center text-sm">
              <span className="text-slate-400">Realisasi Saat Ini:</span>
              <span className="font-semibold text-emerald-400">
                {currentSummary.total_today.toLocaleString()} ekor
              </span>
            </div>
            <div className="flex justify-between items-center text-sm">
              <span className="text-slate-400">Sisa Kuota:</span>
              <span className="font-semibold text-amber-400">
                {remainingBirds.toLocaleString()} ekor
              </span>
            </div>

            {/* Quick Attainment Progress Bar */}
            <div className="pt-2">
              <div className="flex justify-between items-center text-xs mb-1.5 text-slate-400">
                <span>Progress: {currentSummary.attainment_pct}%</span>
                <span>Target: 100%</span>
              </div>
              <div className="w-full bg-slate-700 h-3 rounded-full overflow-hidden">
                <div
                  className="bg-gradient-to-r from-cyan-500 to-emerald-500 h-full rounded-full transition-all duration-700"
                  style={{ width: `${attainmentRate}%` }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Hourly Trend Area Chart Card */}
        <div className="lg:col-span-2 bg-slate-800 border border-slate-700 p-6 rounded-lg shadow flex flex-col justify-between">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
            <div>
              <div className="flex items-center gap-2">
                <Activity className="w-5 h-5 text-emerald-400" />
                <h4 className="font-semibold text-slate-200">Distribusi Penghitungan Per Jam</h4>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Volume throughput ayam melewati garis counter (08:00 – 17:00 WIB)
              </p>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-sm bg-emerald-500 inline-block" />
                <span className="text-slate-300">Total Terhitung</span>
              </div>
              <span className="text-slate-500">·</span>
              <span className="text-slate-400">Puncak: 10:00 (7.210 ekor)</span>
            </div>
          </div>

          {/* ECharts Area Chart */}
          <div className="w-full h-72">
            <ReactECharts
              option={trendOption}
              style={{ height: "100%", width: "100%" }}
              notMerge={true}
              lazyUpdate={true}
            />
          </div>

          {/* Footer Highlights */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-slate-700/60 text-xs">
            <div>
              <span className="text-slate-500 block">Rata-rata/Jam</span>
              <span className="font-semibold text-slate-200 text-sm">6.040 ekor</span>
            </div>
            <div>
              <span className="text-slate-500 block">Jam Puncak</span>
              <span className="font-semibold text-emerald-400 text-sm">10:00 - 11:00</span>
            </div>
            <div>
              <span className="text-slate-500 block">Throughput Aktif</span>
              <span className="font-semibold text-cyan-400 text-sm">118 birds/min</span>
            </div>
            <div>
              <span className="text-slate-500 block">Estimasi Target Selesai</span>
              <span className="font-semibold text-slate-200 text-sm">~16:45 WIB</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default OverviewView;
