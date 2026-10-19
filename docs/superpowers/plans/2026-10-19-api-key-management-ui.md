# Edge API Key Management UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dedicated administrative web UI page at route `/api-keys` (accessible via URL and restricted to administrators) to view, generate, and revoke edge device API keys with a one-time secret copy dialog.

**Architecture:** A new feature slice under `frontend/src/features/api-keys/` following the existing codebase conventions (`types.ts`, `api/apiKeys.api.ts`, `components/`, `pages/`), wired to `http<T>` in `frontend/src/lib/http.ts`, and mounted in `frontend/src/app/router.tsx` under `<ProtectedRoute allowedRoles={["admin"]}>`.

**Tech Stack:** React 18, TypeScript 5.2, Vite 5, Tailwind CSS, Lucide React, React Router 7.

## Global Constraints

- Route path is `/api-keys` directly inside authenticated `<AppShell />`.
- Access is URL-only: do NOT add a link to `frontend/src/config/navigation.ts`.
- Protected by `<ProtectedRoute allowedRoles={["admin"]}>` (operators and unauthenticated users must be redirected).
- Secret key (`cdc_live_...`) is displayed strictly once upon creation inside a dedicated modal with a copy-to-clipboard button and security warning.
- Raw keys are never stored in client state after the creation modal is closed.
- Production build (`npm run build` in `frontend/`) must pass with 0 TypeScript and bundling errors.

---

### Task 1: API Key Contracts & API Client Service

**Files:**
- Create: `frontend/src/features/api-keys/types.ts`
- Create: `frontend/src/features/api-keys/api/apiKeys.api.ts`
- Create: `frontend/src/features/api-keys/index.ts`

**Interfaces:**
- Consumes: `http<T>` from `frontend/src/lib/http.ts`
- Produces: `ApiKeyItem`, `CreateApiKeyPayload`, `CreateApiKeyResponse`, `apiKeysApi` (`getApiKeys`, `createApiKey`, `revokeApiKey`)

- [ ] **Step 1: Create TypeScript type definitions**

Write `frontend/src/features/api-keys/types.ts`:
```typescript
export interface ApiKeyItem {
  id: string;
  name: string;
  prefix: string;
  role: "OPERATOR" | "ADMIN";
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
}

export interface CreateApiKeyPayload {
  name: string;
  role: "OPERATOR" | "ADMIN";
}

export interface CreateApiKeyResponse {
  id: string;
  name: string;
  api_key: string;
  prefix: string;
  role: "OPERATOR" | "ADMIN";
  created_at: string;
}
```

- [ ] **Step 2: Create API client service**

Write `frontend/src/features/api-keys/api/apiKeys.api.ts`:
```typescript
import { http } from "@/lib/http";
import type { ApiKeyItem, CreateApiKeyPayload, CreateApiKeyResponse } from "../types";

export const apiKeysApi = {
  getApiKeys: (): Promise<ApiKeyItem[]> =>
    http<ApiKeyItem[]>("/api/v1/auth/api-keys", {
      method: "GET",
    }),

  createApiKey: (payload: CreateApiKeyPayload): Promise<CreateApiKeyResponse> =>
    http<CreateApiKeyResponse>("/api/v1/auth/api-keys", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  revokeApiKey: (keyId: string): Promise<ApiKeyItem> =>
    http<ApiKeyItem>(`/api/v1/auth/api-keys/${keyId}`, {
      method: "DELETE",
    }),
};
```

- [ ] **Step 3: Create module index**

Write `frontend/src/features/api-keys/index.ts`:
```typescript
export * from "./types";
export * from "./api/apiKeys.api";
```

- [ ] **Step 4: Verify TypeScript compilation**

Run in `frontend/`:
```bash
npm run build
```
Expected: PASS with exit code 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/api-keys/
git commit -m "feat(frontend): add api-keys types and api client service"
```

---

### Task 2: Modals (CreateApiKeyModal & RevokeKeyModal)

**Files:**
- Create: `frontend/src/features/api-keys/components/CreateApiKeyModal.tsx`
- Create: `frontend/src/features/api-keys/components/RevokeKeyModal.tsx`

**Interfaces:**
- Consumes: `CreateApiKeyPayload`, `CreateApiKeyResponse`, `ApiKeyItem` from `@/features/api-keys/types`
- Produces: `CreateApiKeyModal`, `RevokeKeyModal`

- [ ] **Step 1: Create `CreateApiKeyModal.tsx` with two-stage form & one-time copy**

Write `frontend/src/features/api-keys/components/CreateApiKeyModal.tsx`:
```tsx
import React, { useState, useEffect } from "react";
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

  const handleSubmit = async (e: React.FormEvent) => {
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
      aria-labelledby="modal-title"
    >
      <div className="relative w-full max-w-lg bg-white rounded-xl shadow-xl border border-slate-200 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="p-2 bg-emerald-50 text-emerald-600 rounded-lg">
              <KeyRound className="w-5 h-5" />
            </div>
            <div>
              <h3 id="modal-title" className="text-base font-semibold text-slate-900">
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
              className="text-slate-400 hover:text-slate-600 p-1 rounded-md transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        {errorMsg && (
          <div className="mx-6 mt-4 p-3 bg-rose-50 border border-rose-200 text-rose-700 rounded-md text-xs">
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
                >
                  <option value="OPERATOR">OPERATOR (Default - Baca Config & Sinkronisasi Data)</option>
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
                <p className="mt-0.5 text-amber-700">
                  Kunci rahasia hanya ditampilkan satu kali demi keamanan. Masukkan kunci ini ke file{" "}
                  <code className="bg-amber-100/80 px-1 py-0.5 rounded font-mono">.env</code> pada perangkat counter sebagai{" "}
                  <code className="bg-amber-100/80 px-1 py-0.5 rounded font-mono">API_TOKEN</code>.
                </p>
              </div>
            </div>

            <div className="space-y-1.5">
              <span className="text-xs font-medium text-slate-700">Kunci Rahasia API:</span>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  readOnly
                  value={createdResult.api_key}
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
                      <span>Salin</span>
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
                Selesai & Tutup
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `RevokeKeyModal.tsx` for confirmation dialog**

Write `frontend/src/features/api-keys/components/RevokeKeyModal.tsx`:
```tsx
import React, { useState } from "react";
import { AlertCircle, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ApiKeyItem } from "../types";

export interface RevokeKeyModalProps {
  apiKey: ApiKeyItem | null;
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (keyId: string) => Promise<void>;
}

export function RevokeKeyModal({ apiKey, isOpen, onClose, onConfirm }: RevokeKeyModalProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

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
            className="text-slate-400 hover:text-slate-600 p-1 rounded-md transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {errorMsg && (
          <div className="mx-6 mt-4 p-3 bg-rose-50 border border-rose-200 text-rose-700 rounded-md text-xs">
            {errorMsg}
          </div>
        )}

        <div className="p-6 space-y-3">
          <p className="text-sm text-slate-600">
            Apakah Anda yakin ingin mencabut akses untuk kunci{" "}
            <span className="font-semibold text-slate-900">{apiKey.name}</span> (awalan:{" "}
            <code className="font-mono text-xs bg-slate-100 px-1 py-0.5 rounded">{apiKey.prefix}...</code>)?
          </p>
          <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-800">
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
```

- [ ] **Step 3: Update `frontend/src/features/api-keys/index.ts` to export modals**

Edit `frontend/src/features/api-keys/index.ts`:
```typescript
export * from "./types";
export * from "./api/apiKeys.api";
export * from "./components/CreateApiKeyModal";
export * from "./components/RevokeKeyModal";
```

- [ ] **Step 4: Verify TypeScript compilation**

Run in `frontend/`:
```bash
npm run build
```
Expected: PASS with exit code 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/api-keys/
git commit -m "feat(frontend): add create and revoke api key modal components"
```

---

### Task 3: ApiKeyTable & ApiKeysPage View

**Files:**
- Create: `frontend/src/features/api-keys/components/ApiKeyTable.tsx`
- Create: `frontend/src/features/api-keys/pages/ApiKeysPage.tsx`
- Modify: `frontend/src/features/api-keys/index.ts`

**Interfaces:**
- Consumes: `ApiKeyItem`, `apiKeysApi`, `CreateApiKeyModal`, `RevokeKeyModal`
- Produces: `ApiKeyTable`, `ApiKeysPage`

- [ ] **Step 1: Create `ApiKeyTable.tsx`**

Write `frontend/src/features/api-keys/components/ApiKeyTable.tsx`:
```tsx
import React from "react";
import { KeyRound, ShieldAlert, CheckCircle2, XCircle } from "lucide-react";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ApiKeyItem } from "../types";

export interface ApiKeyTableProps {
  keys: ApiKeyItem[];
  isLoading: boolean;
  onRevokeClick: (keyItem: ApiKeyItem) => void;
}

function formatDate(isoStr: string | null): string {
  if (!isoStr) return "-";
  try {
    const d = new Date(isoStr);
    return new Intl.DateTimeFormat("id-ID", {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(d);
  } catch {
    return isoStr;
  }
}

export function ApiKeyTable({ keys, isLoading, onRevokeClick }: ApiKeyTableProps) {
  if (isLoading) {
    return (
      <div className="p-8 text-center text-slate-500 text-sm flex items-center justify-center gap-2">
        <div className="w-5 h-5 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin" />
        <span>Memuat daftar kunci API...</span>
      </div>
    );
  }

  if (keys.length === 0) {
    return (
      <div className="p-12 text-center">
        <div className="w-12 h-12 bg-slate-100 text-slate-400 rounded-full flex items-center justify-center mx-auto mb-3">
          <KeyRound className="w-6 h-6" />
        </div>
        <h4 className="text-sm font-semibold text-slate-900 mb-1">Belum Ada Kunci API</h4>
        <p className="text-xs text-slate-500 max-w-sm mx-auto mb-4">
          Buat kunci API pertama Anda agar edge counter dapat menyinkronkan data batch ke central cloud API.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Nama Kunci / Perangkat</TableHead>
            <TableHead>Awalan (Prefix)</TableHead>
            <TableHead>Peran (Role)</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Dibuat Pada</TableHead>
            <TableHead>Terakhir Digunakan</TableHead>
            <TableHead className="text-right">Aksi</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {keys.map((key) => (
            <TableRow key={key.id}>
              <TableCell className="font-medium text-slate-900">
                <div className="flex items-center gap-2">
                  <KeyRound className="w-4 h-4 text-slate-400 shrink-0" />
                  <span>{key.name}</span>
                </div>
              </TableCell>
              <TableCell>
                <code className="font-mono text-xs bg-slate-100 text-slate-700 px-2 py-0.5 rounded border border-slate-200">
                  {key.prefix}...
                </code>
              </TableCell>
              <TableCell>
                <Badge variant={key.role === "ADMIN" ? "default" : "outline"} className="text-[10px]">
                  {key.role}
                </Badge>
              </TableCell>
              <TableCell>
                {key.is_active ? (
                  <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                    <CheckCircle2 className="w-3 h-3" />
                    Aktif
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">
                    <XCircle className="w-3 h-3" />
                    Dicabut
                  </span>
                )}
              </TableCell>
              <TableCell className="text-xs text-slate-500">{formatDate(key.created_at)}</TableCell>
              <TableCell className="text-xs text-slate-500">{formatDate(key.last_used_at)}</TableCell>
              <TableCell className="text-right">
                {key.is_active ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => onRevokeClick(key)}
                    className="text-rose-600 hover:text-rose-700 hover:bg-rose-50 text-xs h-8 px-2.5"
                  >
                    <ShieldAlert className="w-3.5 h-3.5 mr-1" />
                    Cabut Akses
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
```

- [ ] **Step 2: Create `ApiKeysPage.tsx`**

Write `frontend/src/features/api-keys/pages/ApiKeysPage.tsx`:
```tsx
import React, { useState, useEffect, useCallback } from "react";
import { Plus, KeyRound, CheckCircle2, ShieldOff, RefreshCw } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { apiKeysApi } from "../api/apiKeys.api";
import { ApiKeyTable } from "../components/ApiKeyTable";
import { CreateApiKeyModal } from "../components/CreateApiKeyModal";
import { RevokeKeyModal } from "../components/RevokeKeyModal";
import type { ApiKeyItem, CreateApiKeyPayload, CreateApiKeyResponse } from "../types";

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKeyItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [revokingKey, setRevokingKey] = useState<ApiKeyItem | null>(null);

  const fetchKeys = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const data = await apiKeysApi.getApiKeys();
      setKeys(data);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Gagal memuat daftar kunci API");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchKeys();
  }, [fetchKeys]);

  const handleCreateSubmit = async (payload: CreateApiKeyPayload): Promise<CreateApiKeyResponse> => {
    const res = await apiKeysApi.createApiKey(payload);
    // Refresh list in background
    fetchKeys();
    return res;
  };

  const handleRevokeConfirm = async (keyId: string) => {
    await apiKeysApi.revokeApiKey(keyId);
    await fetchKeys();
  };

  const totalCount = keys.length;
  const activeCount = keys.filter((k) => k.is_active).length;
  const revokedCount = totalCount - activeCount;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Manajemen Kunci API"
        description="Kelola token autentikasi perangkat edge counter untuk sinkronisasi data cloud"
      >
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={fetchKeys} disabled={isLoading} className="h-9">
            <RefreshCw className={`w-4 h-4 mr-1.5 ${isLoading ? "animate-spin" : ""}`} />
            Segarkan
          </Button>
          <Button size="sm" onClick={() => setIsCreateOpen(true)} className="h-9">
            <Plus className="w-4 h-4 mr-1.5" />
            Buat Kunci Baru
          </Button>
        </div>
      </PageHeader>

      {errorMsg && (
        <div className="p-3 bg-rose-50 border border-rose-200 text-rose-700 rounded-lg text-xs flex justify-between items-center">
          <span>{errorMsg}</span>
          <Button variant="outline" size="sm" onClick={fetchKeys} className="text-xs h-7">
            Coba Lagi
          </Button>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="p-4 bg-white">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-slate-500">Total Kunci Terdaftar</p>
              <h3 className="text-2xl font-bold text-slate-900 mt-1">{totalCount}</h3>
            </div>
            <div className="p-3 bg-slate-100 text-slate-600 rounded-xl">
              <KeyRound className="w-5 h-5" />
            </div>
          </div>
        </Card>

        <Card className="p-4 bg-white">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-emerald-600">Kunci Aktif</p>
              <h3 className="text-2xl font-bold text-emerald-700 mt-1">{activeCount}</h3>
            </div>
            <div className="p-3 bg-emerald-50 text-emerald-600 rounded-xl">
              <CheckCircle2 className="w-5 h-5" />
            </div>
          </div>
        </Card>

        <Card className="p-4 bg-white">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-rose-600">Kunci Dicabut / Nonaktif</p>
              <h3 className="text-2xl font-bold text-rose-700 mt-1">{revokedCount}</h3>
            </div>
            <div className="p-3 bg-rose-50 text-rose-600 rounded-xl">
              <ShieldOff className="w-5 h-5" />
            </div>
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Daftar Token Perangkat Edge</CardTitle>
          <CardDescription>
            Semua kunci API yang dapat digunakan oleh layanan edge counter untuk autentikasi otomatis
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <ApiKeyTable keys={keys} isLoading={isLoading} onRevokeClick={(k) => setRevokingKey(k)} />
        </CardContent>
      </Card>

      <CreateApiKeyModal
        isOpen={isCreateOpen}
        onClose={() => {
          setIsCreateOpen(false);
          fetchKeys();
        }}
        onSubmit={handleCreateSubmit}
      />

      <RevokeKeyModal
        apiKey={revokingKey}
        isOpen={Boolean(revokingKey)}
        onClose={() => setRevokingKey(null)}
        onConfirm={handleRevokeConfirm}
      />
    </div>
  );
}
```

- [ ] **Step 3: Update `frontend/src/features/api-keys/index.ts`**

Edit `frontend/src/features/api-keys/index.ts`:
```typescript
export * from "./types";
export * from "./api/apiKeys.api";
export * from "./components/ApiKeyTable";
export * from "./components/CreateApiKeyModal";
export * from "./components/RevokeKeyModal";
export { default as ApiKeysPage } from "./pages/ApiKeysPage";
```

- [ ] **Step 4: Verify TypeScript compilation**

Run in `frontend/`:
```bash
npm run build
```
Expected: PASS with exit code 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/api-keys/
git commit -m "feat(frontend): add api-keys table and main management page"
```

---

### Task 4: Router Registration & Role Guard Integration

**Files:**
- Modify: `frontend/src/app/router.tsx`

**Interfaces:**
- Consumes: `ApiKeysPage` from `@/features/api-keys`
- Produces: Route `/api-keys` guarded by `<ProtectedRoute allowedRoles={["admin"]}>`

- [ ] **Step 1: Update router to register `/api-keys`**

In `frontend/src/app/router.tsx`, import `ApiKeysPage` lazy:
```typescript
const ApiKeysPage = lazy(() => import("@/features/api-keys/pages/ApiKeysPage"));
```

And add the route definition under the `children` array of `/`:
```typescript
      {
        path: "api-keys",
        element: (
          <ProtectedRoute allowedRoles={["admin"]}>
            <Suspense fallback={<PageLoader />}>
              <ApiKeysPage />
            </Suspense>
          </ProtectedRoute>
        ),
      },
```

- [ ] **Step 2: Run frontend production build**

Run in `frontend/`:
```bash
npm run build
```
Expected: PASS with exit code 0 (all modules transformed, dist generated).

- [ ] **Step 3: Run backend test suite to verify zero regressions**

Run:
```bash
py -m pytest services/api/tests/ -q
```
Expected: PASS (200 passed).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/router.tsx
git commit -m "feat(frontend): register /api-keys route with admin role protection"
```
