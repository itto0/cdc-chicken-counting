import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { AlarmDTO } from "@/types";

interface AlarmsTableProps {
  alarms: AlarmDTO[];
  onAcknowledge: (id: number) => void;
  onResolve: (id: number) => void;
}

export function AlarmsTable({ alarms, onAcknowledge, onResolve }: AlarmsTableProps) {
  if (alarms.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-slate-200 p-8 text-center text-slate-500 text-sm">
        Tidak ada alarm aktif untuk lini ini.
      </div>
    );
  }

  const getSeverityBadge = (severity: string) => {
    switch (severity.toLowerCase()) {
      case "critical":
      case "high":
        return <Badge variant="destructive">Tinggi</Badge>;
      case "warning":
      case "medium":
        return <Badge variant="warning">Sedang</Badge>;
      default:
        return <Badge variant="secondary">Rendah</Badge>;
    }
  };

  return (
    <div className="bg-white rounded-lg border border-slate-200 overflow-hidden shadow-xs">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Waktu</TableHead>
            <TableHead>Tipe</TableHead>
            <TableHead>Tingkat</TableHead>
            <TableHead>Pesan</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Aksi</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {alarms.map((alarm) => {
            const timeString = alarm.opened_at
              ? new Date(alarm.opened_at).toLocaleString("id-ID")
              : "-";
            return (
              <TableRow key={alarm.id}>
                <TableCell className="text-xs text-slate-500 whitespace-nowrap">
                  {timeString}
                </TableCell>
                <TableCell className="font-medium text-slate-900">{alarm.alarm_type}</TableCell>
                <TableCell>{getSeverityBadge(alarm.severity)}</TableCell>
                <TableCell className="text-slate-600">{alarm.message}</TableCell>
                <TableCell>
                  <Badge variant={alarm.status === "ACTIVE" ? "destructive" : "secondary"}>
                    {alarm.status}
                  </Badge>
                </TableCell>
                <TableCell className="text-right space-x-2">
                  {alarm.status === "ACTIVE" && (
                    <Button size="sm" variant="outline" onClick={() => onAcknowledge(alarm.id)}>
                      Konfirmasi
                    </Button>
                  )}
                  {alarm.status !== "RESOLVED" && (
                    <Button size="sm" variant="default" onClick={() => onResolve(alarm.id)}>
                      Selesaikan
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
