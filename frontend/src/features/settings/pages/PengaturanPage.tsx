import { useState, useEffect } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { LineSelector } from "@/components/layout/LineSelector";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useAppContext } from "@/context/AppContext";

export default function PengaturanPage() {
  const { currentLineId, lines, isConnected } = useAppContext();
  const currentLine = lines.find((l) => l.id === currentLineId) || lines[0];

  const [lineName, setLineName] = useState(currentLine?.name || "Lini Konveyor 1");
  const [dailyTarget, setDailyTarget] = useState(currentLine?.daily_target || 60000);
  const [isSaved, setIsSaved] = useState(false);

  useEffect(() => {
    if (currentLine) {
      setLineName(currentLine.name || "Lini Konveyor 1");
      setDailyTarget(currentLine.daily_target || 60000);
    }
  }, [currentLine]);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaved(true);
    setTimeout(() => setIsSaved(false), 2500);
  };

  return (
    <div>
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
              <div>
                <label htmlFor="line-name-input" className="text-xs font-medium text-slate-700 block mb-1">
                  Nama Lini
                </label>
                <Input
                  id="line-name-input"
                  value={lineName}
                  onChange={(e) => setLineName(e.target.value)}
                  placeholder="Contoh: Conveyor Line 1"
                />
              </div>

              <div>
                <label htmlFor="daily-target-input" className="text-xs font-medium text-slate-700 block mb-1">
                  Target Harian (ekor ayam)
                </label>
                <Input
                  id="daily-target-input"
                  type="number"
                  value={dailyTarget}
                  onChange={(e) => setDailyTarget(Number(e.target.value))}
                  placeholder="60000"
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
              <Button type="submit" size="sm">
                Simpan Konfigurasi
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
              <span className="font-mono font-medium text-slate-800">{currentLineId || "-"}</span>
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
    </div>
  );
}
