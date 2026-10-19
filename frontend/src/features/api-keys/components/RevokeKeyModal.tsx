import { useState, useEffect } from "react";
import { AlertCircle, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ApiKeyItem } from "../types";

export interface RevokeKeyModalProps {
  apiKey: ApiKeyItem | null;
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (keyId: string | number) => Promise<void>;
}

export function RevokeKeyModal({ apiKey, isOpen, onClose, onConfirm }: RevokeKeyModalProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setIsSubmitting(false);
      setErrorMsg(null);
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

  if (!isOpen || !apiKey) return null;

  const handleConfirm = async () => {
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      await onConfirm(apiKey.id);
      onClose();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Gagal mencabut kunci API");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="revoke-modal-title"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSubmitting) {
          onClose();
        }
      }}
    >
      <div className="relative w-full max-w-md bg-white rounded-xl shadow-xl border border-slate-200 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="p-2 bg-rose-50 text-rose-600 rounded-lg">
              <AlertCircle className="w-5 h-5" />
            </div>
            <h3 id="revoke-modal-title" className="text-base font-semibold text-slate-900">
              Cabut Kunci API
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Tutup"
            className="text-slate-400 hover:text-slate-600 p-1 rounded-md transition-colors disabled:opacity-50 cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {errorMsg && (
          <div className="mx-6 mt-4 p-3 bg-rose-50 border border-rose-200 text-rose-700 rounded-md text-xs leading-relaxed">
            {errorMsg}
          </div>
        )}

        <div className="p-6 space-y-3">
          <p className="text-sm text-slate-600 leading-relaxed">
            Apakah Anda yakin ingin mencabut akses untuk kunci{" "}
            <span className="font-semibold text-slate-900">{apiKey.name}</span> (awalan:{" "}
            <code className="font-mono text-xs bg-slate-100 px-1 py-0.5 rounded font-semibold text-slate-700">{apiKey.prefix}...</code>)?
          </p>
          <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-800 leading-relaxed">
            Perangkat yang menggunakan kunci ini akan langsung ditolak (HTTP 401) dan tidak dapat mengambil konfigurasi
            lini atau menyinkronkan data penghitungan.
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 px-6 py-4 bg-slate-50 border-t border-slate-100">
          <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting}>
            Batal
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={handleConfirm}
            disabled={isSubmitting}
            className="bg-rose-600 hover:bg-rose-700 text-white"
          >
            {isSubmitting ? "Mencabut..." : "Ya, Cabut Kunci"}
          </Button>
        </div>
      </div>
    </div>
  );
}
