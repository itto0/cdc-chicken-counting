import { useState, useEffect, useCallback } from "react";
import { RefreshCw, Plus, KeyRound, CheckCircle2, XCircle, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { apiKeysApi } from "../api/apiKeys.api";
import { CreateApiKeyModal } from "../components/CreateApiKeyModal";
import { RevokeKeyModal } from "../components/RevokeKeyModal";
import { ApiKeyTable } from "../components/ApiKeyTable";
import type { ApiKeyItem, CreateApiKeyPayload, CreateApiKeyResponse } from "../types";

export function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKeyItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [revokingKey, setRevokingKey] = useState<ApiKeyItem | null>(null);

  const fetchKeys = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) {
      setIsRefreshing(true);
    } else {
      setIsLoading(true);
    }
    setError(null);
    try {
      const data = await apiKeysApi.getApiKeys();
      setKeys(Array.isArray(data) ? data : []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Gagal memuat daftar kunci API";
      setError(msg);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchKeys();
  }, [fetchKeys]);

  const handleCreateSubmit = async (payload: CreateApiKeyPayload): Promise<CreateApiKeyResponse> => {
    const res = await apiKeysApi.createApiKey(payload);
    await fetchKeys();
    return res;
  };

  const handleRevokeConfirm = async (keyId: string | number) => {
    await apiKeysApi.revokeApiKey(keyId);
    await fetchKeys();
  };

  const totalCount = keys.length;
  const activeCount = keys.filter((k) => k.is_active).length;
  const revokedCount = keys.filter((k) => !k.is_active).length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Manajemen Kunci API"
        description="Kelola token autentikasi perangkat edge counter untuk sinkronisasi data cloud"
      >
        <Button
          variant="outline"
          size="sm"
          onClick={() => fetchKeys(true)}
          disabled={isLoading || isRefreshing}
          className="flex items-center gap-1.5 cursor-pointer"
        >
          <RefreshCw className={cn("w-4 h-4", (isLoading || isRefreshing) && "animate-spin")} />
          <span>Segarkan</span>
        </Button>
        <Button
          size="sm"
          onClick={() => setIsCreateOpen(true)}
          className="flex items-center gap-1.5 cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>+ Buat Kunci Baru</span>
        </Button>
      </PageHeader>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 text-rose-800 rounded-lg flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-rose-600 shrink-0" />
            <div className="text-xs">
              <p className="font-semibold text-rose-900">Gagal Memuat Kunci API</p>
              <p className="text-rose-700">{error}</p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchKeys(true)}
            className="bg-white border-rose-300 text-rose-700 hover:bg-rose-100 hover:text-rose-800 shrink-0 cursor-pointer"
          >
            Coba Lagi
          </Button>
        </div>
      )}

      {/* Summary Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* Total Kunci */}
        <Card className="rounded-2xl border-slate-200/80 shadow-sm bg-white">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-500">Total Kunci Terdaftar</span>
              <div
                className="p-2 rounded-full bg-slate-100 text-slate-700 flex items-center justify-center"
                aria-hidden="true"
              >
                <KeyRound className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-3 flex items-baseline gap-1.5">
              <span className="text-2xl font-bold tracking-tight text-slate-900">{totalCount}</span>
              <span className="text-xs font-medium text-slate-500">kunci</span>
            </div>
            <p className="mt-1 text-[11px] text-slate-400">Total token perangkat terdaftar</p>
          </CardContent>
        </Card>

        {/* Kunci Aktif */}
        <Card className="rounded-2xl border-slate-200/80 shadow-sm bg-white">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-500">Kunci Aktif</span>
              <div
                className="p-2 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center"
                aria-hidden="true"
              >
                <CheckCircle2 className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-3 flex items-baseline gap-1.5">
              <span className="text-2xl font-bold tracking-tight text-slate-900">{activeCount}</span>
              <span className="text-xs font-medium text-slate-500">kunci</span>
            </div>
            <p className="mt-1 text-[11px] text-slate-400">Dapat melakukan sinkronisasi data</p>
          </CardContent>
        </Card>

        {/* Kunci Dicabut / Nonaktif */}
        <Card className="rounded-2xl border-slate-200/80 shadow-sm bg-white">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-500">Kunci Dicabut / Nonaktif</span>
              <div
                className="p-2 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center"
                aria-hidden="true"
              >
                <XCircle className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-3 flex items-baseline gap-1.5">
              <span className="text-2xl font-bold tracking-tight text-slate-900">{revokedCount}</span>
              <span className="text-xs font-medium text-slate-500">kunci</span>
            </div>
            <p className="mt-1 text-[11px] text-slate-400">Akses ditolak (HTTP 401)</p>
          </CardContent>
        </Card>
      </div>

      {/* Main Card with Table */}
      <Card>
        <CardHeader>
          <CardTitle>Daftar Kunci API</CardTitle>
          <CardDescription>
            Daftar token autentikasi perangkat edge counter dan status aksesnya
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ApiKeyTable
            keys={keys}
            isLoading={isLoading}
            onRevokeClick={(keyItem) => setRevokingKey(keyItem)}
          />
        </CardContent>
      </Card>

      {/* Modal Orchestration */}
      {isCreateOpen && (
        <CreateApiKeyModal
          isOpen={isCreateOpen}
          onClose={() => setIsCreateOpen(false)}
          onSubmit={handleCreateSubmit}
        />
      )}
      {Boolean(revokingKey) && (
        <RevokeKeyModal
          apiKey={revokingKey}
          isOpen={Boolean(revokingKey)}
          onClose={() => setRevokingKey(null)}
          onConfirm={handleRevokeConfirm}
        />
      )}
    </div>
  );
}

export default ApiKeysPage;
