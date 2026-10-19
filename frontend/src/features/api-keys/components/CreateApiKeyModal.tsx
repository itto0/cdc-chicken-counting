import { useState, useEffect, type FormEvent } from "react";
import { X, Copy, Check, AlertTriangle, KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import type { CreateApiKeyPayload, CreateApiKeyResponse } from "../types";

export interface CreateApiKeyModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (payload: CreateApiKeyPayload) => Promise<CreateApiKeyResponse>;
}

export function CreateApiKeyModal({ isOpen, onClose, onSubmit }: CreateApiKeyModalProps) {
  const [name, setName] = useState("");
  const [role, setRole] = useState<"OPERATOR" | "ADMIN">("OPERATOR");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Stage 2: One-time reveal
  const [createdResult, setCreatedResult] = useState<CreateApiKeyResponse | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setName("");
      setRole("OPERATOR");
      setIsSubmitting(false);
      setErrorMsg(null);
      setCreatedResult(null);
      setCopied(false);
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      // Allow escape only on stage 1 to prevent losing uncopied key on stage 2
      if (e.key === "Escape" && !isSubmitting && !createdResult) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isSubmitting, createdResult, onClose]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) {
      setErrorMsg("Nama kunci wajib diisi");
      return;
    }

    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      const res = await onSubmit({ name: trimmedName, role });
      setCreatedResult(res);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Gagal membuat kunci API");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCopy = async () => {
    if (!createdResult?.api_key) return;
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(createdResult.api_key);
      } else {
        const textarea = document.createElement("textarea");
        textarea.value = createdResult.api_key;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      setErrorMsg("Gagal menyalin ke clipboard");
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-api-key-modal-title"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSubmitting && !createdResult) {
          onClose();
        }
      }}
    >
      <div className="relative w-full max-w-lg bg-white rounded-xl shadow-xl border border-slate-200 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="p-2 bg-emerald-50 text-emerald-600 rounded-lg">
              <KeyRound className="w-5 h-5" />
            </div>
            <div>
              <h3 id="create-api-key-modal-title" className="text-base font-semibold text-slate-900">
                {createdResult ? "Kunci API Berhasil Dibuat" : "Buat Kunci API Perangkat"}
              </h3>
              <p className="text-xs text-slate-500">
                {createdResult
                  ? "Salin kunci rahasia sekarang sebelum menutup dialog"
                  : "Buat token autentikasi baru untuk edge counter"}
              </p>
            </div>
          </div>
          {!createdResult && (
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              aria-label="Tutup"
              className="text-slate-400 hover:text-slate-600 p-1 rounded-md transition-colors disabled:opacity-50 cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        {errorMsg && (
          <div className="mx-6 mt-4 p-3 bg-rose-50 border border-rose-200 text-rose-700 rounded-md text-xs leading-relaxed">
            {errorMsg}
          </div>
        )}

        {!createdResult ? (
          <form onSubmit={handleSubmit}>
            <div className="p-6 space-y-4">
              <div>
                <label htmlFor="key-name-input" className="text-xs font-medium text-slate-700 block mb-1">
                  Nama Kunci / Perangkat <span className="text-rose-500">*</span>
                </label>
                <Input
                  id="key-name-input"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Contoh: Edge Counter Conveyor 1"
                  required
                  disabled={isSubmitting}
                  autoFocus
                />
                <span className="text-[10px] text-slate-400 mt-1 block">
                  Identifikasi deskriptif untuk perangkat edge atau lokasi conveyor.
                </span>
              </div>

              <div>
                <label htmlFor="key-role-select" className="text-xs font-medium text-slate-700 block mb-1">
                  Peran Akses (Role)
                </label>
                <Select
                  id="key-role-select"
                  value={role}
                  onChange={(e) => setRole(e.target.value as "OPERATOR" | "ADMIN")}
                  disabled={isSubmitting}
                  className="w-full"
                >
                  <option value="OPERATOR">OPERATOR (Default - Baca Config &amp; Sinkronisasi Data)</option>
                  <option value="ADMIN">ADMIN (Akses Penuh Manajemen)</option>
                </Select>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 px-6 py-4 bg-slate-50 border-t border-slate-100">
              <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting}>
                Batal
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? "Membuat..." : "Buat Kunci"}
              </Button>
            </div>
          </form>
        ) : (
          <div className="p-6 space-y-4">
            <div className="p-3.5 bg-amber-50 border border-amber-200 text-amber-900 rounded-lg text-xs flex gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-amber-800">Simpan kunci ini sekarang!</p>
                <p className="mt-0.5 text-amber-700 leading-relaxed">
                  Kunci rahasia hanya ditampilkan satu kali demi keamanan. Masukkan kunci ini ke file{" "}
                  <code className="bg-amber-100/80 px-1 py-0.5 rounded font-mono font-semibold">.env</code> pada perangkat counter sebagai{" "}
                  <code className="bg-amber-100/80 px-1 py-0.5 rounded font-mono font-semibold">API_TOKEN</code>.
                </p>
              </div>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="revealed-api-key" className="text-xs font-medium text-slate-700 block">
                Kunci Rahasia API:
              </label>
              <div className="flex items-center gap-2">
                <input
                  id="revealed-api-key"
                  type="text"
                  readOnly
                  value={createdResult.api_key}
                  onFocus={(e) => e.target.select()}
                  onClick={(e) => (e.target as HTMLInputElement).select()}
                  className="flex-1 font-mono text-xs p-2.5 bg-slate-900 text-emerald-400 rounded-lg border border-slate-800 focus:outline-none select-all"
                />
                <Button
                  type="button"
                  variant={copied ? "default" : "outline"}
                  onClick={handleCopy}
                  className="shrink-0 flex items-center gap-1.5"
                >
                  {copied ? (
                    <>
                      <Check className="w-4 h-4 text-emerald-300" />
                      <span>Tersalin</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-4 h-4" />
                      <span>Salin Kunci</span>
                    </>
                  )}
                </Button>
              </div>
            </div>

            <div className="text-xs text-slate-500 space-y-1 pt-2 border-t border-slate-100">
              <div className="flex justify-between">
                <span>Perangkat:</span>
                <span className="font-medium text-slate-700">{createdResult.name}</span>
              </div>
              <div className="flex justify-between">
                <span>Awalan (Prefix):</span>
                <span className="font-mono text-slate-700">{createdResult.prefix}...</span>
              </div>
              <div className="flex justify-between">
                <span>Peran:</span>
                <span className="font-medium text-slate-700">{createdResult.role}</span>
              </div>
            </div>

            <div className="pt-2">
              <Button type="button" onClick={onClose} className="w-full">
                Selesai &amp; Tutup
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
