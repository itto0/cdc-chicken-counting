import React, { useState, useEffect } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import type { CreateLinePayload } from "@/types";

export interface AddLineModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (payload: CreateLinePayload) => Promise<void>;
}

export function AddLineModal({ isOpen, onClose, onSubmit }: AddLineModalProps) {
  const [id, setId] = useState("");
  const [name, setName] = useState("");
  const [dailyTarget, setDailyTarget] = useState<number | string>(60000);
  const [videoUrl, setVideoUrl] = useState("");
  const [lineCoords, setLineCoords] = useState("0,240,640,240");
  const [lineDirection, setLineDirection] = useState("down");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const resetForm = () => {
    setId("");
    setName("");
    setDailyTarget(60000);
    setVideoUrl("");
    setLineCoords("0,240,640,240");
    setLineDirection("down");
    setErrorMsg(null);
  };

  useEffect(() => {
    if (isOpen) {
      resetForm();
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !isSubmitting) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isSubmitting, onClose]);

  if (!isOpen) return null;

  const handleIdChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setId(e.target.value.toLowerCase().replace(/\s+/g, "-"));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    const cleanId = id.trim().toLowerCase().replace(/\s+/g, "-");
    if (!cleanId) {
      setErrorMsg("ID Lini wajib diisi");
      return;
    }
    const slugRegex = /^[a-z0-9_-]{2,50}$/;
    if (!slugRegex.test(cleanId)) {
      setErrorMsg("ID Lini harus berupa 2-50 karakter alfanumerik (huruf kecil, angka, strip '-', atau garis bawah '_')");
      return;
    }
    if (!name.trim()) {
      setErrorMsg("Nama Lini wajib diisi");
      return;
    }

    const targetNum = Number(dailyTarget);
    if (isNaN(targetNum) || targetNum <= 0) {
      setErrorMsg("Target harian harus berupa angka lebih besar dari 0");
      return;
    }

    if (lineCoords.trim()) {
      const parts = lineCoords.split(",").map((p) => p.trim());
      if (parts.length !== 4 || parts.some((p) => p === "" || isNaN(Number(p)))) {
        setErrorMsg("Koordinat garis harus berisi 4 angka dipisahkan koma (contoh: 0,240,640,240)");
        return;
      }
    }

    try {
      setIsSubmitting(true);
      await onSubmit({
        id: cleanId,
        name: name.trim(),
        daily_target: targetNum,
        video_url: videoUrl.trim() || undefined,
        line_coords: lineCoords.trim() || undefined,
        line_direction: lineDirection,
        is_active: true,
      });
      resetForm();
      onClose();
    } catch (err: unknown) {
      let msg = "Gagal membuat lini baru";
      if (err instanceof Error) {
        const raw = err.message.replace(/^API Error \d+:\s*/, "");
        try {
          const parsed = JSON.parse(raw);
          if (Array.isArray(parsed?.detail)) {
            msg = parsed.detail.map((d: { msg?: string }) => d.msg || "Validasi gagal").join(", ");
          } else if (typeof parsed?.detail === "string") {
            msg = parsed.detail;
          } else if (typeof parsed?.message === "string") {
            msg = parsed.message;
          } else {
            msg = raw;
          }
        } catch {
          msg = raw || err.message;
        }
      } else if (err && typeof err === "object") {
        const errorObj = err as Record<string, unknown>;
        const response = errorObj.response as Record<string, unknown> | undefined;
        const resData = response?.data as Record<string, unknown> | undefined;
        if (resData?.detail && typeof resData.detail === "string") {
          msg = resData.detail;
        } else if (resData?.message && typeof resData.message === "string") {
          msg = resData.message;
        } else if (errorObj.detail && typeof errorObj.detail === "string") {
          msg = errorObj.detail;
        } else if (errorObj.message && typeof errorObj.message === "string") {
          msg = errorObj.message;
        }
      }
      setErrorMsg(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="add-line-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSubmitting) onClose();
      }}
    >
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg border border-slate-200 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center">
          <div>
            <h3 id="add-line-modal-title" className="font-semibold text-slate-800 text-base">Tambah Lini Produksi Baru</h3>
            <p className="text-xs text-slate-500">Konfigurasi lini baru, target kuota, dan sumber video kamera</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Tutup"
            className="text-slate-400 hover:text-slate-600 p-1 rounded-md hover:bg-slate-100 transition-colors disabled:opacity-50 cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="p-6 space-y-4 max-h-[75vh] overflow-y-auto text-xs">
            {errorMsg && (
              <div className="p-3 bg-rose-50 border border-rose-200 text-rose-700 rounded-lg text-xs leading-relaxed">
                {errorMsg}
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label htmlFor="modal-line-id" className="font-medium text-slate-700 block mb-1">
                  ID Lini <span className="text-rose-500">*</span>
                </label>
                <Input
                  id="modal-line-id"
                  value={id}
                  onChange={handleIdChange}
                  placeholder="contoh: line-2"
                  required
                />
                <span className="text-[10px] text-slate-400 mt-1 block">Slug unik (huruf, angka, strip)</span>
              </div>
              <div>
                <label htmlFor="modal-line-name" className="font-medium text-slate-700 block mb-1">
                  Nama Lini <span className="text-rose-500">*</span>
                </label>
                <Input
                  id="modal-line-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Lini Konveyor 2"
                  required
                />
              </div>
            </div>

            <div>
              <label htmlFor="modal-daily-target" className="font-medium text-slate-700 block mb-1">
                Target Harian (ekor ayam) <span className="text-rose-500">*</span>
              </label>
              <Input
                id="modal-daily-target"
                type="number"
                value={dailyTarget}
                onChange={(e) => setDailyTarget(e.target.value === "" ? "" : Number(e.target.value))}
                placeholder="60000"
                min={1}
                required
              />
            </div>

            <div>
              <label htmlFor="modal-video-url" className="font-medium text-slate-700 block mb-1">
                URL Stream Kamera / RTSP
              </label>
              <Input
                id="modal-video-url"
                value={videoUrl}
                onChange={(e) => setVideoUrl(e.target.value)}
                placeholder="rtsp://192.168.1.100:554/stream1 atau /samples/video.mp4"
              />
              <span className="text-[10px] text-slate-400 mt-1 block">
                Opsional. Digunakan untuk live streaming kamera di cloud atau edge source.
              </span>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="modal-line-coords" className="font-medium text-slate-700 block">
                Koordinat Garis Virtual (x1, y1, x2, y2)
              </label>
              <Input
                id="modal-line-coords"
                value={lineCoords}
                onChange={(e) => setLineCoords(e.target.value)}
                placeholder="0,240,640,240"
              />
              <div className="flex flex-wrap gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setLineCoords("0,240,640,240")}
                  className="px-2.5 py-1 text-[11px] bg-slate-100 text-slate-600 rounded-md hover:bg-slate-200 border border-slate-200 transition-colors cursor-pointer"
                >
                  Preset Horizontal Tengah (0,240,640,240)
                </button>
                <button
                  type="button"
                  onClick={() => setLineCoords("320,0,320,480")}
                  className="px-2.5 py-1 text-[11px] bg-slate-100 text-slate-600 rounded-md hover:bg-slate-200 border border-slate-200 transition-colors cursor-pointer"
                >
                  Preset Vertikal Tengah (320,0,320,480)
                </button>
              </div>
            </div>

            <div>
              <label htmlFor="modal-line-direction" className="font-medium text-slate-700 block mb-1">
                Arah Hitung Perlintasan
              </label>
              <Select
                id="modal-line-direction"
                value={lineDirection}
                onChange={(e) => setLineDirection(e.target.value)}
                className="w-full"
              >
                <option value="down">Ke Bawah (Down)</option>
                <option value="up">Ke Atas (Up)</option>
                <option value="right">Ke Kanan (Right)</option>
                <option value="left">Ke Kiri (Left)</option>
                <option value="in">Masuk (In)</option>
                <option value="out">Keluar (Out)</option>
              </Select>
            </div>
          </div>

          <div className="px-6 py-3.5 bg-slate-50 border-t border-slate-100 flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Batal
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={isSubmitting}
            >
              {isSubmitting ? "Menyimpan..." : "Simpan Lini"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
