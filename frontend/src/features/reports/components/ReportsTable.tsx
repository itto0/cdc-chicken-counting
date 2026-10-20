import { useState } from "react";
import { ChevronLeft, ChevronRight, Inbox } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import type { AggregateItemDTO } from "@/types";

export interface ReportRowItem {
  id: string;
  timestamp: string;
  rawTimestamp?: string;
  lineName: string;
  count: number;
  ratePerMin: number;
  accuracyPct: number;
  status: "Normal" | "Warning" | "Critical" | string;
}

export interface ReportsTableProps {
  data?: (ReportRowItem | AggregateItemDTO)[];
  emptyMessage?: string;
}

const ITEMS_PER_PAGE = 10;

function isAggregateItem(item: ReportRowItem | AggregateItemDTO): item is AggregateItemDTO {
  return "bucket" in item && !("timestamp" in item);
}

function normalizeRow(item: ReportRowItem | AggregateItemDTO, index: number): ReportRowItem {
  if (isAggregateItem(item)) {
    return {
      id: `agg-${index}`,
      timestamp: item.bucket,
      rawTimestamp: item.bucket,
      lineName: "Lini Utama",
      count: item.count ?? 0,
      ratePerMin: item.rate_per_min ?? 0,
      accuracyPct: (item as any).accuracy_pct ?? 0,
      status: item.status || "Normal",
    };
  }
  return item;
}

export function ReportsTable({
  data = [],
  emptyMessage = "Belum ada riwayat data penghitungan untuk filter yang dipilih",
}: ReportsTableProps) {
  const [currentPage, setCurrentPage] = useState(1);

  const normalizedRows = data.map((item, idx) => normalizeRow(item, idx));
  const totalCount = normalizedRows.length;
  const totalPages = Math.max(1, Math.ceil(totalCount / ITEMS_PER_PAGE));
  const safePage = Math.min(Math.max(1, currentPage), totalPages);
  const startIndex = (safePage - 1) * ITEMS_PER_PAGE;
  const currentRows = normalizedRows.slice(startIndex, startIndex + ITEMS_PER_PAGE);

  const getStatusBadge = (status: string) => {
    const s = (status || "").toLowerCase();
    if (s === "critical" || s === "kritis") {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700">
          Kritis
        </span>
      );
    }
    if (s === "warning" || s === "peringatan") {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700">
          Peringatan
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700">
        Normal
      </span>
    );
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden mt-4">
      {/* Table Header Section */}
      <div className="p-4 px-6 border-b border-slate-100 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-800">Riwayat Data Penghitungan</h3>
          <p className="text-xs text-slate-400 mt-0.5">Catatan agregasi penghitungan dan laju konveyor</p>
        </div>
        <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-slate-100 text-slate-700">
          {totalCount.toLocaleString("id-ID")} Data
        </span>
      </div>

      {totalCount === 0 ? (
        <div className="p-12 text-center">
          <div
            className="w-12 h-12 rounded-2xl bg-slate-50 flex items-center justify-center mx-auto text-slate-400 mb-3"
            aria-hidden="true"
          >
            <Inbox className="w-6 h-6" />
          </div>
          <p className="text-sm font-medium text-slate-700">{emptyMessage}</p>
          <p className="text-xs text-slate-400 mt-1">Coba ubah filter periode, lini, atau kata kunci pencarian Anda.</p>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="border-slate-100 bg-slate-50/50 hover:bg-slate-50/50">
                  <TableHead className="font-semibold text-slate-700 text-xs py-3.5 normal-case tracking-normal">
                    Waktu / Tanggal
                  </TableHead>
                  <TableHead className="font-semibold text-slate-700 text-xs py-3.5 normal-case tracking-normal">
                    Lini Produksi
                  </TableHead>
                  <TableHead className="font-semibold text-slate-700 text-xs py-3.5 normal-case tracking-normal">
                    Jumlah Terhitung
                  </TableHead>
                  <TableHead className="font-semibold text-slate-700 text-xs py-3.5 normal-case tracking-normal">
                    Laju Rata-rata
                  </TableHead>
                  <TableHead className="font-semibold text-slate-700 text-xs py-3.5 normal-case tracking-normal">
                    Akurasi
                  </TableHead>
                  <TableHead className="font-semibold text-slate-700 text-xs py-3.5 normal-case tracking-normal">
                    Status
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {currentRows.map((row) => (
                  <TableRow key={row.id} className="border-slate-100 hover:bg-slate-50/80 transition-colors">
                    <TableCell className="font-medium text-slate-800 text-xs py-3.5">{row.timestamp}</TableCell>
                    <TableCell className="text-slate-600 text-xs py-3.5">{row.lineName}</TableCell>
                    <TableCell className="font-semibold text-slate-900 text-xs py-3.5">
                      {(row.count ?? 0).toLocaleString("id-ID")} ekor
                    </TableCell>
                    <TableCell className="text-slate-700 text-xs py-3.5">{Math.round(row.ratePerMin ?? 0)} cpm</TableCell>
                    <TableCell className="text-slate-700 text-xs py-3.5">
                      {`${(row.accuracyPct ?? 0).toLocaleString("id-ID", {
                        minimumFractionDigits: 1,
                        maximumFractionDigits: 1,
                      })}%`}
                    </TableCell>
                    <TableCell className="py-3.5">{getStatusBadge(row.status)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Pagination Footer */}
          <div className="p-4 px-6 border-t border-slate-100 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500">
            <div>
              Menampilkan <span className="font-semibold text-slate-800">{startIndex + 1}</span> -{" "}
              <span className="font-semibold text-slate-800">{Math.min(startIndex + ITEMS_PER_PAGE, totalCount)}</span>{" "}
              dari <span className="font-semibold text-slate-800">{totalCount.toLocaleString("id-ID")}</span> data
            </div>

            <div className="flex items-center gap-1.5">
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={safePage <= 1}
                onClick={() => setCurrentPage(Math.max(1, safePage - 1))}
                aria-label="Halaman sebelumnya"
                className="h-8 px-2.5 rounded-lg text-xs"
              >
                <ChevronLeft className="w-3.5 h-3.5 mr-1" aria-hidden="true" />
                Sebelumnya
              </Button>

              <span className="px-3 py-1 font-semibold text-slate-800 text-xs">
                {safePage} / {totalPages}
              </span>

              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={safePage >= totalPages}
                onClick={() => setCurrentPage(Math.min(totalPages, safePage + 1))}
                aria-label="Halaman berikutnya"
                className="h-8 px-2.5 rounded-lg text-xs"
              >
                Berikutnya
                <ChevronRight className="w-3.5 h-3.5 ml-1" aria-hidden="true" />
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
