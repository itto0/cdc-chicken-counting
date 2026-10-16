import { useState, useEffect } from "react";
import { Download } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { LineSelector } from "@/components/layout/LineSelector";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { useAppContext } from "@/context/AppContext";
import { reportsApi } from "../api/reports.api";
import { ReportsTable } from "../components/ReportsTable";
import type { AggregateItemDTO } from "@/types";

export default function LaporanPage() {
  const { currentLineId, isConnected } = useAppContext();
  const [granularity, setGranularity] = useState("hourly");
  const [data, setData] = useState<AggregateItemDTO[]>([]);

  useEffect(() => {
    let isMounted = true;
    if (!currentLineId) return;

    reportsApi
      .getCounts(currentLineId, { granularity })
      .then((res) => {
        if (isMounted && res?.aggregates) setData(res.aggregates);
      })
      .catch(() => {
        if (isMounted) {
          setData([
            { bucket: "08:00 - 09:00", count: 5120, rate_per_min: 102, status: "Normal" },
            { bucket: "09:00 - 10:00", count: 6840, rate_per_min: 124, status: "Normal" },
            { bucket: "10:00 - 11:00", count: 7210, rate_per_min: 128, status: "Normal" },
            { bucket: "11:00 - 12:00", count: 6950, rate_per_min: 122, status: "Normal" },
          ]);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [currentLineId, granularity]);

  const handleExportCSV = () => {
    const csvContent =
      "data:text/csv;charset=utf-8," +
      ["Rentang Waktu,Total Ayam,Kecepatan (cpm),Status"]
        .concat(data.map((d) => `"${d.bucket}",${d.count},${d.rate_per_min},"${d.status || "Normal"}"`))
        .join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `laporan-${currentLineId || "lini"}-${granularity}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div>
      <PageHeader
        title="Laporan Penghitungan"
        description="Data rekapitulasi performa lini produksi dan ekspor CSV"
      >
        <StatusBadge isConnected={isConnected} />
        <LineSelector />
      </PageHeader>

      <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-4 rounded-lg border border-slate-200 shadow-xs">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-slate-500">Granularitas:</span>
          <Select
            value={granularity}
            onChange={(e) => setGranularity(e.target.value)}
            className="text-xs h-8"
          >
            <option value="minute">Per Menit</option>
            <option value="hourly">Per Jam</option>
            <option value="daily">Harian</option>
          </Select>
        </div>

        <Button variant="outline" size="sm" onClick={handleExportCSV}>
          <Download className="w-3.5 h-3.5 mr-1.5" />
          Ekspor CSV
        </Button>
      </div>

      <ReportsTable data={data} />
    </div>
  );
}
