import { useState, useEffect, useRef } from "react";
import { Plus } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { LineSelector } from "@/components/layout/LineSelector";
import { StatusBadge } from "@/components/common/StatusBadge";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useAppContext } from "@/context/AppContext";
import { AddLineModal } from "../components/AddLineModal";
import type { CreateLinePayload, Line } from "@/types";

const DIRECTION_LABELS: Record<string, string> = {
  down: "Ke Bawah (Down)",
  up: "Ke Atas (Up)",
  right: "Ke Kanan (Right)",
  left: "Ke Kiri (Left)",
  in: "Masuk (In)",
  out: "Keluar (Out)",
};

const formatDirection = (dir?: string) => {
  if (!dir) return "Ke Bawah (Down)";
  return DIRECTION_LABELS[dir] || dir;
};

export default function PengaturanPage() {
  const {
    currentLineId,
    setCurrentLineId,
    lines,
    isConnected,
    createLine,
    updateLine,
  } = useAppContext();

  const currentLine = lines.find((l) => l.id === currentLineId) || lines[0];

  const [lineName, setLineName] = useState(currentLine?.name || "Lini Konveyor 1");
  const [dailyTarget, setDailyTarget] = useState<number | string>(currentLine?.daily_target || 60000);
  const [isSaving, setIsSaving] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  useEffect(() => {
    if (currentLine) {
      setLineName(currentLine.name || "Lini Konveyor 1");
      setDailyTarget(currentLine.daily_target || 60000);
    }
  }, [currentLine]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentLine?.id) return;
    setSaveError(null);

    const trimmedName = lineName.trim();
    if (!trimmedName) {
      setSaveError("Nama lini wajib diisi");
      return;
    }
    const target = Number(dailyTarget);
    if (isNaN(target) || target <= 0) {
      setSaveError("Target harian harus lebih besar dari 0");
      return;
    }

    setIsSaving(true);
    try {
      await updateLine(currentLine.id, {
        name: trimmedName,
        daily_target: target,
      });
      setIsSaved(true);
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => setIsSaved(false), 2500);
    } catch (err: unknown) {
      let msg = "Gagal menyimpan konfigurasi lini";
      if (err && typeof err === "object") {
        const errorObj = err as Record<string, unknown>;
        if (errorObj.message && typeof errorObj.message === "string") {
          msg = errorObj.message;
        }
      }
      setSaveError(msg);
    } finally {
      setIsSaving(false);
    }
  };

  const handleToggleActive = async (line: Line) => {
    try {
      setTogglingId(line.id);
      setActionError(null);
      await updateLine(line.id, { is_active: !line.is_active });
    } catch (err: unknown) {
      let msg = `Gagal mengubah status lini ${line.id}`;
      if (err && typeof err === "object") {
        const errorObj = err as Record<string, unknown>;
        if (errorObj.message && typeof errorObj.message === "string") {
          msg = errorObj.message;
        }
      }
      setActionError(msg);
    } finally {
      setTogglingId(null);
    }
  };

  const handleCreateLine = async (payload: CreateLinePayload) => {
    await createLine(payload);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Pengaturan Sistem"
        description="Kelola parameter lini konveyor, target produksi, dan koneksi"
      >
        <StatusBadge isConnected={isConnected} />
        <LineSelector />
      </PageHeader>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Parameter Lini Produksi</CardTitle>
            <CardDescription>
              Ubah konfigurasi nama lini dan kuota target harian
            </CardDescription>
          </CardHeader>
          <form onSubmit={handleSave}>
            <CardContent className="space-y-4">
              {saveError && (
                <div className="p-2.5 bg-rose-50 border border-rose-200 text-rose-700 rounded-md text-xs">
                  {saveError}
                </div>
              )}
              <div>
                <label
                  htmlFor="line-name-input"
                  className="text-xs font-medium text-slate-700 block mb-1"
                >
                  Nama Lini
                </label>
                <Input
                  id="line-name-input"
                  value={lineName}
                  onChange={(e) => setLineName(e.target.value)}
                  placeholder="Contoh: Conveyor Line 1"
                  required
                />
              </div>

              <div>
                <label
                  htmlFor="daily-target-input"
                  className="text-xs font-medium text-slate-700 block mb-1"
                >
                  Target Harian (ekor ayam)
                </label>
                <Input
                  id="daily-target-input"
                  type="number"
                  value={dailyTarget}
                  onChange={(e) =>
                    setDailyTarget(e.target.value === "" ? "" : Number(e.target.value))
                  }
                  placeholder="60000"
                  min={1}
                  required
                />
              </div>
            </CardContent>
            <CardFooter className="flex justify-between items-center">
              {isSaved ? (
                <span className="text-xs text-emerald-600 font-medium">
                  Pengaturan berhasil disimpan!
                </span>
              ) : (
                <span />
              )}
              <Button type="submit" size="sm" disabled={isSaving}>
                {isSaving ? "Menyimpan..." : "Simpan Konfigurasi"}
              </Button>
            </CardFooter>
          </form>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Informasi Sistem & Kamera</CardTitle>
            <CardDescription>
              Detail perangkat deteksi dan koneksi edge counter
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-xs text-slate-600">
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">ID Lini:</span>
              <span className="font-mono font-medium text-slate-800">
                {currentLine?.id || currentLineId || "-"}
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">URL Video / Kamera:</span>
              <span
                className="font-mono font-medium text-slate-800 truncate max-w-[200px]"
                title={currentLine?.video_url || "Default / Edge local"}
              >
                {currentLine?.video_url || "Default / Edge local"}
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Koordinat Garis:</span>
              <span className="font-mono font-medium text-slate-800">
                {currentLine?.line_coords || "0,240,640,240"}
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Arah Hitung:</span>
              <span className="font-medium text-slate-800">
                {formatDirection(currentLine?.line_direction)}
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Protokol Deteksi:</span>
              <span className="font-medium text-slate-800">YOLOv8 + ByteTrack (Edge)</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Mode Sinkronisasi:</span>
              <span className="font-medium text-slate-800">CDC Outbox SQLite + REST/SSE</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Versi UI:</span>
              <span className="font-medium text-slate-800">v0.2.0 (React + Shadcn Light)</span>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <CardTitle>Manajemen Lini Produksi</CardTitle>
            <CardDescription>
              Daftar seluruh lini konveyor yang terdaftar dan kontrol operasional aktif/nonaktif
            </CardDescription>
          </div>
          <Button
            onClick={() => setIsAddModalOpen(true)}
            size="sm"
            className="flex items-center gap-1.5 self-start sm:self-auto cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Tambah Lini Baru</span>
          </Button>
        </CardHeader>
        <CardContent>
          {actionError && (
            <div className="mb-4 p-3 bg-rose-50 border border-rose-200 text-rose-700 rounded-md text-xs flex justify-between items-center">
              <span>{actionError}</span>
              <button
                type="button"
                onClick={() => setActionError(null)}
                aria-label="Tutup pemberitahuan"
                className="text-rose-500 hover:text-rose-700 font-bold ml-2 cursor-pointer"
              >
                ✕
              </button>
            </div>
          )}
          <div className="rounded-md border border-slate-200 overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID Lini</TableHead>
                  <TableHead>Nama Lini</TableHead>
                  <TableHead>Target Harian</TableHead>
                  <TableHead>Garis & Arah</TableHead>
                  <TableHead>URL Video / Kamera</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Aksi</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {lines.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center py-6 text-slate-500">
                      Belum ada data lini produksi.
                    </TableCell>
                  </TableRow>
                ) : (
                  lines.map((line) => {
                    const isSelected = line.id === currentLineId;
                    return (
                      <TableRow
                        key={line.id}
                        className={isSelected ? "bg-emerald-50/50 hover:bg-emerald-50/70" : undefined}
                      >
                        <TableCell className="font-mono font-medium text-slate-800">
                          {line.id}
                        </TableCell>
                        <TableCell className="font-medium text-slate-900">
                          <div className="flex items-center gap-2">
                            <span>{line.name}</span>
                            {isSelected && (
                              <Badge
                                variant="outline"
                                className="text-[10px] text-emerald-700 border-emerald-300 bg-emerald-50 py-0 px-1.5"
                              >
                                Terpilih
                              </Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          {line.daily_target != null
                            ? `${line.daily_target.toLocaleString("id-ID")} ekor`
                            : "-"}
                        </TableCell>
                        <TableCell>
                          <div className="text-xs">
                            <span className="font-mono text-slate-700 block">
                              {line.line_coords || "0,240,640,240"}
                            </span>
                            <span className="text-[11px] text-slate-500">
                              Arah: {formatDirection(line.line_direction)}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="max-w-[200px]">
                          <span
                            className="font-mono text-xs text-slate-600 truncate block"
                            title={line.video_url || "Default / Edge local"}
                          >
                            {line.video_url || "-"}
                          </span>
                        </TableCell>
                        <TableCell>
                          {line.is_active ? (
                            <Badge variant="success">Aktif</Badge>
                          ) : (
                            <Badge variant="secondary">Non-aktif</Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-2">
                            <Button
                              variant={isSelected ? "secondary" : "outline"}
                              size="sm"
                              disabled={isSelected}
                              onClick={() => setCurrentLineId(line.id)}
                              title="Pilih lini ini sebagai lini aktif dashboard"
                            >
                              {isSelected ? "Terpilih" : "Pilih"}
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={togglingId === line.id}
                              onClick={() => handleToggleActive(line)}
                              className={
                                line.is_active
                                  ? "text-amber-700 hover:text-amber-800 hover:bg-amber-50"
                                  : "text-emerald-700 hover:text-emerald-800 hover:bg-emerald-50"
                              }
                            >
                              {togglingId === line.id
                                ? "Memproses..."
                                : line.is_active
                                ? "Nonaktifkan"
                                : "Aktifkan"}
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <AddLineModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onSubmit={handleCreateLine}
      />
    </div>
  );
}
