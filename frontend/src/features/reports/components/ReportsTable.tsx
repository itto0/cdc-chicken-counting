import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { AggregateItemDTO } from "@/types";

interface ReportsTableProps {
  data: AggregateItemDTO[];
}

export function ReportsTable({ data }: ReportsTableProps) {
  if (data.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-slate-200 p-8 text-center text-slate-500 text-sm mt-4">
        Tidak ada data laporan untuk rentang waktu ini.
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-slate-200 overflow-hidden shadow-xs mt-4">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Rentang Waktu</TableHead>
            <TableHead>Total Ayam (Ekor)</TableHead>
            <TableHead>Kecepatan Rata-rata (cpm)</TableHead>
            <TableHead>Status Operasional</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((row, idx) => (
            <TableRow key={idx}>
              <TableCell className="font-medium text-slate-900">{row.bucket}</TableCell>
              <TableCell>{row.count.toLocaleString("id-ID")}</TableCell>
              <TableCell>{row.rate_per_min} cpm</TableCell>
              <TableCell>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-50 text-emerald-700">
                  {row.status || "Normal"}
                </span>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
