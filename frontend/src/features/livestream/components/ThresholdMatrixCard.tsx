import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

interface ThresholdRow {
  metric: string;
  warning: string;
  critical: string;
}

const THRESHOLD_DATA: ThresholdRow[] = [
  {
    metric: "Laju Produksi (ekor/menit)",
    warning: "< 130",
    critical: "< 110",
  },
  {
    metric: "Latensi (ms)",
    warning: "130",
    critical: "110",
  },
  {
    metric: "Akurasi Deteksi (%)",
    warning: "0.096",
    critical: "0.075",
  },
  {
    metric: "Downtime (menit)",
    warning: "17",
    critical: "10",
  },
];

export function ThresholdMatrixCard() {
  return (
    <Card className="rounded-2xl border-slate-200/80 shadow-sm bg-white">
      <CardHeader className="p-4 pb-2">
        <CardTitle className="text-sm font-semibold text-slate-800">
          Matriks Ambang Batas (Threshold Matrix)
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 pt-1">
        <div className="overflow-x-auto">
          <Table className="w-full text-xs">
            <TableHeader>
              <TableRow className="border-b border-slate-100 hover:bg-transparent">
                <TableHead className="w-1/2 text-slate-600 font-semibold py-2.5">
                  Metrik
                </TableHead>
                <TableHead className="w-1/4 text-amber-600 font-semibold py-2.5">
                  Peringatan (Amber)
                </TableHead>
                <TableHead className="w-1/4 text-rose-600 font-semibold py-2.5">
                  Kritis (Red)
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {THRESHOLD_DATA.map((row) => (
                <TableRow
                  key={row.metric}
                  className="border-b border-slate-100/80 last:border-b-0 hover:bg-slate-50/50 transition-colors"
                >
                  <TableCell className="font-medium text-slate-800 py-3">
                    {row.metric}
                  </TableCell>
                  <TableCell className="font-semibold text-amber-700 py-3">
                    {row.warning}
                  </TableCell>
                  <TableCell className="font-semibold text-rose-700 py-3">
                    {row.critical}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
