import { Search, FileText, FileSpreadsheet, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

export interface ReportFilterBarProps {
  period: "today" | "7d" | "30d";
  onPeriodChange: (period: "today" | "7d" | "30d") => void;
  selectedLineId: string;
  onLineChange: (lineId: string) => void;
  lines: Array<{ id: string; name: string }>;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  onExportPdf: () => void;
  onExportExcel: () => void;
  isExporting: boolean;
}

export function ReportFilterBar({
  period,
  onPeriodChange,
  selectedLineId,
  onLineChange,
  lines,
  searchQuery,
  onSearchChange,
  onExportPdf,
  onExportExcel,
  isExporting,
}: ReportFilterBarProps) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-4 flex flex-wrap items-center justify-between gap-4">
      {/* Left controls: Periode, Lini, Search */}
      <div className="flex flex-wrap items-center gap-3 flex-1 min-w-[280px]">
        {/* Periode Selector */}
        <div className="flex items-center gap-2">
          <label htmlFor="period-select" className="text-xs font-medium text-slate-500 whitespace-nowrap">
            Periode:
          </label>
          <select
            id="period-select"
            value={period}
            onChange={(e) => onPeriodChange(e.target.value as "today" | "7d" | "30d")}
            className="h-9 text-xs rounded-xl border border-slate-200 bg-white px-3 py-1 font-medium text-slate-800 shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-900/10 cursor-pointer"
          >
            <option value="today">Hari Ini</option>
            <option value="7d">7 Hari Terakhir</option>
            <option value="30d">30 Hari Terakhir</option>
          </select>
        </div>

        {/* Lini Selector */}
        <div className="flex items-center gap-2">
          <label htmlFor="line-select" className="text-xs font-medium text-slate-500 whitespace-nowrap">
            Lini:
          </label>
          <select
            id="line-select"
            value={selectedLineId}
            onChange={(e) => onLineChange(e.target.value)}
            className="h-9 text-xs rounded-xl border border-slate-200 bg-white px-3 py-1 font-medium text-slate-800 shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-900/10 cursor-pointer"
          >
            <option value="all">Semua Lini</option>
            {lines.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name || l.id}
              </option>
            ))}
          </select>
        </div>

        {/* Search Input */}
        <div className="relative flex-1 min-w-[180px] max-w-xs">
          <Search
            className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
            aria-hidden="true"
          />
          <input
            id="report-search-input"
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Cari data..."
            aria-label="Cari data laporan"
            className="w-full h-9 pl-9 pr-3 text-xs rounded-xl border border-slate-200 bg-white placeholder:text-slate-400 font-medium text-slate-800 shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-900/10"
          />
        </div>
      </div>

      {/* Right controls: Ekspor PDF & Ekspor Excel */}
      <div className="flex items-center gap-2.5">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={isExporting}
          onClick={onExportPdf}
          className="rounded-xl border-rose-200 text-rose-700 hover:bg-rose-50 h-9 text-xs font-medium shadow-sm transition-colors"
        >
          {isExporting ? (
            <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" aria-hidden="true" />
          ) : (
            <FileText className="w-3.5 h-3.5 mr-1.5 text-rose-600" aria-hidden="true" />
          )}
          Ekspor PDF
        </Button>

        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={isExporting}
          onClick={onExportExcel}
          className="rounded-xl border-emerald-200 text-emerald-700 hover:bg-emerald-50 h-9 text-xs font-medium shadow-sm transition-colors"
        >
          {isExporting ? (
            <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" aria-hidden="true" />
          ) : (
            <FileSpreadsheet className="w-3.5 h-3.5 mr-1.5 text-emerald-600" aria-hidden="true" />
          )}
          Ekspor Excel
        </Button>
      </div>
    </div>
  );
}
