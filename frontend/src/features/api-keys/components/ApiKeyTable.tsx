import { KeyRound, CheckCircle2, XCircle, ShieldAlert, Loader2 } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ApiKeyItem } from "../types";

export interface ApiKeyTableProps {
  keys: ApiKeyItem[];
  isLoading: boolean;
  onRevokeClick: (keyItem: ApiKeyItem) => void;
}

function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return "-";
  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return "-";
    return new Intl.DateTimeFormat("id-ID", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  } catch {
    return "-";
  }
}

export function ApiKeyTable({ keys, isLoading, onRevokeClick }: ApiKeyTableProps) {
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center text-slate-500">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-600 mb-2" />
        <p className="text-xs">Memuat daftar kunci API...</p>
      </div>
    );
  }

  if (keys.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50/50 p-8 text-center flex flex-col items-center justify-center">
        <div className="p-3 bg-white rounded-full shadow-xs border border-slate-200 text-slate-400 mb-3">
          <KeyRound className="w-8 h-8" />
        </div>
        <h3 className="text-sm font-semibold text-slate-900 mb-1">Belum Ada Kunci API</h3>
        <p className="text-xs text-slate-500 max-w-sm">
          Belum ada kunci API yang dibuat. Klik tombol "+ Buat Kunci Baru" di atas untuk menambahkan token autentikasi perangkat edge counter.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-md border border-slate-200 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Nama Kunci / Perangkat</TableHead>
            <TableHead>Awalan (Prefix)</TableHead>
            <TableHead>Peran</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Dibuat Pada</TableHead>
            <TableHead>Terakhir Digunakan</TableHead>
            <TableHead className="text-right">Aksi</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {keys.map((keyItem) => (
            <TableRow key={keyItem.id}>
              <TableCell className="font-medium text-slate-900">
                <div className="flex items-center gap-2">
                  <KeyRound className="w-4 h-4 text-slate-400 shrink-0" />
                  <span>{keyItem.name}</span>
                </div>
              </TableCell>
              <TableCell>
                <code className="font-mono text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-800 border border-slate-200 font-medium">
                  {keyItem.prefix ? (keyItem.prefix.endsWith("...") ? keyItem.prefix : `${keyItem.prefix}...`) : "-"}
                </code>
              </TableCell>
              <TableCell>
                {keyItem.role === "ADMIN" ? (
                  <Badge variant="default" className="text-[11px] font-semibold">
                    ADMIN
                  </Badge>
                ) : (
                  <Badge variant="secondary" className="text-[11px] font-semibold">
                    OPERATOR
                  </Badge>
                )}
              </TableCell>
              <TableCell>
                {keyItem.is_active ? (
                  <Badge variant="success" className="inline-flex items-center gap-1 text-[11px]">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Aktif</span>
                  </Badge>
                ) : (
                  <Badge
                    variant="secondary"
                    className="inline-flex items-center gap-1 text-slate-500 bg-slate-100 border border-slate-200 text-[11px]"
                  >
                    <XCircle className="w-3.5 h-3.5 text-slate-400" />
                    <span>Dicabut</span>
                  </Badge>
                )}
              </TableCell>
              <TableCell className="text-xs text-slate-500 whitespace-nowrap">
                {formatDate(keyItem.created_at)}
              </TableCell>
              <TableCell className="text-xs text-slate-500 whitespace-nowrap">
                {formatDate(keyItem.last_used_at)}
              </TableCell>
              <TableCell className="text-right">
                {keyItem.is_active ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onRevokeClick(keyItem)}
                    className="text-rose-600 hover:text-rose-700 hover:bg-rose-50 border-rose-200 cursor-pointer"
                  >
                    <ShieldAlert className="w-3.5 h-3.5 mr-1" />
                    <span>Cabut Akses</span>
                  </Button>
                ) : (
                  <span className="text-xs text-slate-400 italic">Nonaktif</span>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
