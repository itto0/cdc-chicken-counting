import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { useAppContext } from "@/context/AppContext";
import { cn } from "@/lib/utils";
import type { Line } from "@/types";

interface ThresholdMatrixCardProps {
  className?: string;
  line?: Line;
}

export function ThresholdMatrixCard({ className = "", line }: ThresholdMatrixCardProps) {
  const { currentLineId, lines } = useAppContext();
  const activeLine = line ?? lines.find((l) => l.id === currentLineId) ?? lines[0];

  const hasCustomOverride =
    activeLine?.rate_warning_threshold != null ||
    activeLine?.rate_critical_threshold != null;

  const effectiveWarning =
    activeLine?.effective_rate_warning ??
    activeLine?.rate_warning_threshold ??
    130;

  const effectiveCritical =
    activeLine?.effective_rate_critical ??
    activeLine?.rate_critical_threshold ??
    110;

  const thresholds = [
    {
      metric: "Kecepatan Produksi",
      warning: `< ${effectiveWarning} /mnt`,
      critical: `< ${effectiveCritical} /mnt`,
      action: "Periksa konveyor & pasokan",
      isCustom: hasCustomOverride,
    },
    {
      metric: "Latensi Pipeline",
      warning: "> 150 ms",
      critical: "> 300 ms",
      action: "Restart engine inferensi",
      isCustom: false,
    },
    {
      metric: "Frame Rate (FPS)",
      warning: "< 10 FPS",
      critical: "< 5 FPS",
      action: "Periksa beban GPU & RTSP",
      isCustom: false,
    },
    {
      metric: "Akurasi Deteksi",
      warning: "< 95%",
      critical: "< 90%",
      action: "Kalibrasi sudut kamera",
      isCustom: false,
    },
  ];

  return (
    <Card className={cn("rounded-2xl border-slate-200/80 shadow-sm bg-white", className)}>
      <CardHeader className="p-4 pb-2">
        <CardTitle className="text-sm font-semibold text-slate-800">
          Matriks Ambang Batas
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
              {thresholds.map((row) => (
                <TableRow
                  key={row.metric}
                  className="border-b border-slate-100/80 last:border-b-0 hover:bg-slate-50/50 transition-colors"
                >
                  <TableCell className="font-medium text-slate-800 py-2.5 px-3">
                    <div className="flex items-center gap-1.5">
                      <span>{row.metric}</span>
                      {row.isCustom && (
                        <Badge
                          variant="outline"
                          className="text-[9px] px-1.5 py-0 border-amber-300 bg-amber-50 text-amber-700"
                        >
                          Kustom
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="font-semibold text-amber-700 py-2.5 px-3">
                    {row.warning}
                  </TableCell>
                  <TableCell className="font-semibold text-rose-700 py-2.5 px-3">
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
