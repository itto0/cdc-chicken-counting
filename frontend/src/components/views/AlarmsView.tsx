import { useState, useEffect, useMemo, useCallback } from "react";
import {
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Clock,
  ShieldAlert,
  Filter,
  RotateCw,
  X,
  Check,
  CheckCheck,
  Search,
  Lock,
  Info,
  UserCheck,
  MessageSquare,
  Layers,
} from "lucide-react";
import { apiClient } from "../../services/apiClient";
import { useAppContext } from "../../context/AppContext";
import type { AlarmDTO, AlarmPatchPayload } from "../../types";

export interface AlarmsViewProps {
  lineId?: string;
}

export type StatusFilter = "ALL" | "OPEN" | "ACKNOWLEDGED" | "RESOLVED";
export type SeverityFilter = "ALL" | "CRITICAL" | "WARNING" | "INFO";

export const DEFAULT_MOCK_ALARMS: AlarmDTO[] = [
  {
    id: 101,
    line_id: "line-1",
    alarm_type: "SPEED_WARNING",
    severity: "WARNING",
    message: "Kecepatan konveyor di bawah ambang batas minimum (< 30 CPM)",
    status: "OPEN",
    opened_at: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
    ack_at: null,
    resolved_at: null,
  },
  {
    id: 102,
    line_id: "line-1",
    alarm_type: "CAMERA_DROP",
    severity: "CRITICAL",
    message: "Kamera kehilangan frame (latency > 500ms)",
    status: "ACKNOWLEDGED",
    opened_at: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
    ack_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
    resolved_at: null,
  },
  {
    id: 103,
    line_id: "line-1",
    alarm_type: "CONVEYOR_STOP",
    severity: "CRITICAL",
    message: "Konveyor berhenti mendadak selama > 60 detik",
    status: "RESOLVED",
    opened_at: new Date(Date.now() - 2 * 3600 * 1000).toISOString(),
    ack_at: new Date(Date.now() - 1.8 * 3600 * 1000).toISOString(),
    resolved_at: new Date(Date.now() - 1.5 * 3600 * 1000).toISOString(),
  },
  {
    id: 104,
    line_id: "line-2",
    alarm_type: "HIGH_DENSITY",
    severity: "WARNING",
    message: "Kepadatan karkas tinggi berpotensi tumpang tindih shackle",
    status: "OPEN",
    opened_at: new Date(Date.now() - 8 * 60 * 1000).toISOString(),
    ack_at: null,
    resolved_at: null,
  },
  {
    id: 105,
    line_id: "line-1",
    alarm_type: "LOW_CONFIDENCE",
    severity: "INFO",
    message: "Pencahayaan redup menyebabkan penurunan keyakinan deteksi < 90%",
    status: "OPEN",
    opened_at: new Date(Date.now() - 25 * 60 * 1000).toISOString(),
    ack_at: null,
    resolved_at: null,
  },
];

/**
 * Format timestamp into Indonesian WIB (Asia/Jakarta, UTC+7).
 */
export function formatToWIB(dateStr: string | null | undefined): string {
  if (!dateStr) return "-";
  try {
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return dateStr;
    const datePart = date.toLocaleDateString("id-ID", {
      timeZone: "Asia/Jakarta",
      year: "numeric",
      month: "short",
      day: "numeric",
    });
    const timePart = date.toLocaleTimeString("id-ID", {
      timeZone: "Asia/Jakarta",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
    return `${datePart}, ${timePart} WIB`;
  } catch {
    return dateStr;
  }
}

export function AlarmsView({ lineId: propLineId }: AlarmsViewProps) {
  const { currentRole, lines, currentLineId } = useAppContext();
  const isViewer = currentRole === "VIEWER";

  // Filter States
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("ALL");
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>("ALL");
  const [selectedLineId, setSelectedLineId] = useState<string>(
    propLineId || currentLineId || "ALL"
  );
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Sync selected line when propLineId or global currentLineId changes
  useEffect(() => {
    setSelectedLineId(propLineId || currentLineId || "ALL");
  }, [propLineId, currentLineId]);

  // Data States
  const [allAlarms, setAllAlarms] = useState<AlarmDTO[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isOfflineFallback, setIsOfflineFallback] = useState<boolean>(false);
  const [errorNotice, setErrorNotice] = useState<string | null>(null);

  // Toast notification
  const [toast, setToast] = useState<{ type: "success" | "error" | "info"; message: string } | null>(
    null
  );

  // Action Modal States
  const [modalOpen, setModalOpen] = useState<boolean>(false);
  const [actionType, setActionType] = useState<"ACKNOWLEDGE" | "RESOLVE">("ACKNOWLEDGE");
  const [targetAlarm, setTargetAlarm] = useState<AlarmDTO | null>(null);
  const [notes, setNotes] = useState<string>("");
  const [operatorName, setOperatorName] = useState<string>(
    `${currentRole.toLowerCase()}_user`
  );
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Auto-dismiss toast after 4 seconds
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => {
      setToast(null);
    }, 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  // Keep operatorName in sync with role if not manually customized
  useEffect(() => {
    setOperatorName(`${currentRole.toLowerCase()}_user`);
  }, [currentRole]);

  // Fetch all alarms for the selected line from API (decoupled from status/severity filters)
  const fetchAlarms = useCallback(async () => {
    setIsLoading(true);
    setErrorNotice(null);

    const lineParam =
      selectedLineId && selectedLineId.toLowerCase() !== "all"
        ? selectedLineId
        : undefined;

    try {
      const data = await apiClient.getAlarms({
        line_id: lineParam,
      });
      if (Array.isArray(data)) {
        setAllAlarms(data);
        setIsOfflineFallback(false);
      } else {
        throw new Error("Invalid alarms response structure");
      }
    } catch (err) {
      console.warn("Failed to load alarms from backend, falling back to mock data:", err);
      setIsOfflineFallback(true);
      setErrorNotice(
        "Mode Offline: Gagal terhubung ke server API Alarms (/api/v1/alarms). Menampilkan data simulasi lokal."
      );
      // Filter mock data locally by line if specified
      let filtered = [...DEFAULT_MOCK_ALARMS];
      if (lineParam) {
        filtered = filtered.filter((a) => a.line_id === lineParam);
      }
      setAllAlarms(filtered);
    } finally {
      setIsLoading(false);
    }
  }, [selectedLineId]);

  useEffect(() => {
    fetchAlarms();
  }, [fetchAlarms]);

  // Statistics counts computed from all alarms for selected line (remains intact when status filter changes)
  const stats = useMemo(() => {
    const total = allAlarms.length;
    const open = allAlarms.filter((a) => a.status.toUpperCase() === "OPEN").length;
    const ack = allAlarms.filter((a) => a.status.toUpperCase() === "ACKNOWLEDGED").length;
    const resolved = allAlarms.filter((a) => a.status.toUpperCase() === "RESOLVED").length;
    const critical = allAlarms.filter((a) => a.severity.toUpperCase() === "CRITICAL").length;
    return { total, open, ack, resolved, critical };
  }, [allAlarms]);

  // In-memory filtered alarms for table display (by status, severity, and search keyword)
  const filteredAlarms = useMemo(() => {
    return allAlarms.filter((alarm) => {
      // Status filter
      if (statusFilter !== "ALL" && alarm.status.toUpperCase() !== statusFilter) {
        return false;
      }
      // Severity filter
      if (severityFilter !== "ALL" && alarm.severity.toUpperCase() !== severityFilter) {
        return false;
      }
      // Keyword search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const match =
          alarm.id.toString().includes(q) ||
          alarm.alarm_type.toLowerCase().includes(q) ||
          alarm.message.toLowerCase().includes(q) ||
          alarm.line_id.toLowerCase().includes(q) ||
          alarm.severity.toLowerCase().includes(q);
        if (!match) return false;
      }
      return true;
    });
  }, [allAlarms, statusFilter, severityFilter, searchQuery]);

  // Open action modal
  const openActionModal = (alarm: AlarmDTO, type: "ACKNOWLEDGE" | "RESOLVE") => {
    if (isViewer) return;
    setTargetAlarm(alarm);
    setActionType(type);
    setNotes("");
    setModalError(null);
    setModalOpen(true);
  };

  // Close action modal
  const closeActionModal = useCallback(() => {
    if (isSubmitting) return;
    setModalOpen(false);
    setTargetAlarm(null);
    setModalError(null);
  }, [isSubmitting]);

  // Close modal on Escape key press
  useEffect(() => {
    if (!modalOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        closeActionModal();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [modalOpen, closeActionModal]);

  // Handle action confirmation (Acknowledge / Resolve)
  const handleConfirmAction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetAlarm) return;
    if (isViewer) {
      setModalError("Operasi ditolak: Hanya pengguna dengan peran Operator, Manager, atau Admin yang diizinkan.");
      return;
    }

    setIsSubmitting(true);
    setModalError(null);

    const targetStatus = actionType === "ACKNOWLEDGE" ? "ACKNOWLEDGED" : "RESOLVED";
    const payload: AlarmPatchPayload = {
      status: targetStatus,
      notes: notes.trim() || undefined,
      acknowledged_by: operatorName.trim() || undefined,
    };

    try {
      if (isOfflineFallback) {
        // Optimistic local update in offline fallback
        const nowIso = new Date().toISOString();
        setAllAlarms((prev) =>
          prev.map((item) => {
            if (item.id === targetAlarm.id) {
              const notePart = notes.trim() ? ` [${actionType === "ACKNOWLEDGE" ? "Ack Note" : "Resolution"}: ${notes.trim()} by ${operatorName.trim()}]` : "";
              return {
                ...item,
                status: targetStatus,
                ack_at: actionType === "ACKNOWLEDGE" ? nowIso : item.ack_at,
                resolved_at: actionType === "RESOLVE" ? nowIso : item.resolved_at,
                message: `${item.message}${notePart}`.slice(0, 255),
              };
            }
            return item;
          })
        );
        setToast({
          type: "success",
          message: `Mode Offline: Alarm #${targetAlarm.id} berhasil di-${actionType === "ACKNOWLEDGE" ? "akui" : "selesaikan"} secara lokal.`,
        });
        setModalOpen(false);
      } else {
        await apiClient.patchAlarm(targetAlarm.id, payload);
        setToast({
          type: "success",
          message: `Alarm #${targetAlarm.id} berhasil ${actionType === "ACKNOWLEDGE" ? "diakui" : "diselesaikan"}.`,
        });
        setModalOpen(false);
        await fetchAlarms();
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Gagal memperbarui status alarm";
      setModalError(msg);
      setToast({
        type: "error",
        message: `Gagal memperbarui status alarm: ${msg}`,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Toast Notification Banner */}
      {toast && (
        <div
          role="status"
          aria-live="polite"
          className={`flex items-center justify-between px-4 py-3 rounded-lg border text-sm font-medium shadow-md transition-all duration-200 ${
            toast.type === "success"
              ? "bg-emerald-950/90 border-emerald-500/60 text-emerald-200"
              : toast.type === "error"
              ? "bg-rose-950/90 border-rose-500/60 text-rose-200"
              : "bg-cyan-950/90 border-cyan-500/60 text-cyan-200"
          }`}
        >
          <div className="flex items-center gap-2.5">
            {toast.type === "success" ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
            ) : toast.type === "error" ? (
              <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
            ) : (
              <Info className="w-5 h-5 text-cyan-400 shrink-0" />
            )}
            <span>{toast.message}</span>
          </div>
          <button
            type="button"
            onClick={() => setToast(null)}
            className="text-slate-400 hover:text-white p-1 rounded"
            aria-label="Tutup notifikasi"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Offline Notice Banner */}
      {errorNotice && (
        <div
          role="alert"
          className="flex items-center justify-between px-4 py-3 bg-amber-950/70 border border-amber-500/50 rounded-lg text-amber-200 text-xs sm:text-sm"
        >
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            <span>{errorNotice}</span>
          </div>
          <button
            type="button"
            onClick={() => setErrorNotice(null)}
            className="text-amber-400 hover:text-amber-200 p-0.5"
            aria-label="Tutup pesan offline"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Top Header & Quick Metrics Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
        {/* Total Incidents */}
        <div className="bg-slate-800 border border-slate-700 p-4 rounded-lg shadow-sm">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium mb-1">
            <span>Total Insiden</span>
            <ShieldAlert className="w-4 h-4 text-slate-400" />
          </div>
          <div className="text-2xl font-bold text-slate-100">{stats.total}</div>
          <div className="text-[11px] text-slate-400 mt-1">Semua status alarm</div>
        </div>

        {/* Terbuka (Open) */}
        <div className="bg-slate-800 border border-slate-700 p-4 rounded-lg shadow-sm">
          <div className="flex items-center justify-between text-rose-400 text-xs font-medium mb-1">
            <span>Insiden Terbuka</span>
            <AlertCircle className="w-4 h-4 text-rose-400" />
          </div>
          <div className="text-2xl font-bold text-rose-400 flex items-center gap-2">
            <span>{stats.open}</span>
            {stats.open > 0 && (
              <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
            )}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Perlu tindakan penanganan</div>
        </div>

        {/* Sedang Diakui (Acknowledged) */}
        <div className="bg-slate-800 border border-slate-700 p-4 rounded-lg shadow-sm">
          <div className="flex items-center justify-between text-amber-400 text-xs font-medium mb-1">
            <span>Sedang Diakui</span>
            <Clock className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-amber-400">{stats.ack}</div>
          <div className="text-[11px] text-slate-400 mt-1">Dalam proses inspeksi</div>
        </div>

        {/* Terselesaikan (Resolved) */}
        <div className="bg-slate-800 border border-slate-700 p-4 rounded-lg shadow-sm">
          <div className="flex items-center justify-between text-emerald-400 text-xs font-medium mb-1">
            <span>Terselesaikan</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400">{stats.resolved}</div>
          <div className="text-[11px] text-slate-400 mt-1">Insiden telah tuntas</div>
        </div>
      </div>

      {/* Viewer Permission Notice Banner */}
      {isViewer && (
        <div className="bg-slate-800/80 border border-cyan-500/40 px-4 py-2.5 rounded-lg flex items-center gap-2.5 text-xs text-cyan-300">
          <Lock className="w-4 h-4 text-cyan-400 shrink-0" />
          <span>
            <strong>Mode Hanya Baca:</strong> Peran Anda saat ini adalah <strong>VIEWER</strong>. Tombol &quot;Akui&quot; dan &quot;Selesaikan&quot; dinonaktifkan. Beralih ke peran <strong>OPERATOR</strong>, <strong>MANAGER</strong>, atau <strong>ADMIN</strong> pada bilah atas untuk melakukan tindakan operasional.
          </span>
        </div>
      )}

      {/* Filters and Search Bar Card */}
      <div className="bg-slate-800 border border-slate-700 p-4 rounded-lg shadow-sm space-y-4">
        {/* Row 1: Status Filter Tabs & Action Refresh */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-700/80 pb-3">
          {/* Status Tabs */}
          <div className="flex items-center gap-1 sm:gap-1.5 flex-wrap">
            <span className="text-xs font-medium text-slate-400 mr-1 flex items-center gap-1">
              <Filter className="w-3.5 h-3.5 text-slate-400" />
              <span>Status:</span>
            </span>

            {[
              { key: "ALL" as StatusFilter, label: "Semua", count: stats.total },
              { key: "OPEN" as StatusFilter, label: "Terbuka", count: stats.open },
              { key: "ACKNOWLEDGED" as StatusFilter, label: "Diakui", count: stats.ack },
              { key: "RESOLVED" as StatusFilter, label: "Terselesaikan", count: stats.resolved },
            ].map((tab) => {
              const isActive = statusFilter === tab.key;
              return (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setStatusFilter(tab.key)}
                  className={`px-3 py-1.5 rounded-md text-xs font-semibold transition flex items-center gap-1.5 ${
                    isActive
                      ? "bg-emerald-600 text-white shadow"
                      : "bg-slate-700 text-slate-300 hover:bg-slate-600 hover:text-white"
                  }`}
                >
                  <span>{tab.label}</span>
                  <span
                    className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold ${
                      isActive ? "bg-emerald-800 text-emerald-100" : "bg-slate-800 text-slate-400"
                    }`}
                  >
                    {tab.count}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Refresh Button */}
          <button
            type="button"
            onClick={fetchAlarms}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs font-medium rounded-md border border-slate-600 shadow-sm transition disabled:opacity-50"
            title="Segarkan daftar alarm"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin text-emerald-400" : "text-slate-300"}`} />
            <span>Segarkan</span>
          </button>
        </div>

        {/* Row 2: Severity Tabs, Line Filter, Search Input */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
          {/* Severity Tabs */}
          <div className="flex items-center gap-1 sm:gap-1.5 flex-wrap">
            <span className="text-xs font-medium text-slate-400 mr-1 flex items-center gap-1">
              <span>Tingkat:</span>
            </span>

            {[
              { key: "ALL" as SeverityFilter, label: "Semua", badgeClass: "" },
              { key: "CRITICAL" as SeverityFilter, label: "Kritis", badgeClass: "text-rose-400" },
              { key: "WARNING" as SeverityFilter, label: "Peringatan", badgeClass: "text-amber-400" },
              { key: "INFO" as SeverityFilter, label: "Info", badgeClass: "text-cyan-400" },
            ].map((sev) => {
              const isActive = severityFilter === sev.key;
              return (
                <button
                  key={sev.key}
                  type="button"
                  onClick={() => setSeverityFilter(sev.key)}
                  className={`px-2.5 py-1 rounded text-xs font-medium transition ${
                    isActive
                      ? "bg-slate-950 text-white border border-emerald-500/70"
                      : "bg-slate-900/60 text-slate-400 hover:text-slate-200 border border-slate-700/60"
                  }`}
                >
                  <span className={sev.badgeClass}>{sev.label}</span>
                </button>
              );
            })}
          </div>

          {/* Line Filter & Search */}
          <div className="flex items-center gap-2 flex-wrap">
            {/* Line Filter Selector */}
            <div className="flex items-center gap-1.5">
              <label htmlFor="alarm-line-filter" className="text-xs text-slate-400 flex items-center gap-1">
                <Layers className="w-3.5 h-3.5 text-slate-400" />
                <span className="hidden sm:inline">Jalur:</span>
              </label>
              <select
                id="alarm-line-filter"
                value={selectedLineId}
                onChange={(e) => setSelectedLineId(e.target.value)}
                className="bg-slate-700 hover:bg-slate-600 border border-slate-600 text-slate-100 text-xs rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
              >
                <option value="ALL">Semua Line</option>
                {lines.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Keyword Search Input */}
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                placeholder="Cari ID, pesan, tipe..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="bg-slate-900/80 border border-slate-700 text-slate-100 text-xs rounded pl-8 pr-3 py-1 focus:outline-none focus:ring-1 focus:ring-emerald-500 w-44 sm:w-56 placeholder-slate-500"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery("")}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Incidents Table Card */}
      <div className="bg-slate-800 border border-slate-700 rounded-lg shadow-sm overflow-hidden">
        <div className="px-5 py-3.5 border-b border-slate-700 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-slate-100">
              Daftar Insiden Alarm
            </h3>
            <span className="text-xs text-slate-400 font-normal">
              ({filteredAlarms.length} insiden ditampilkan)
            </span>
          </div>

          <div className="text-xs text-slate-400 flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-slate-400" />
            <span>Zona Waktu: WIB (UTC+7)</span>
          </div>
        </div>

        {/* Table Container */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-slate-900/90 text-slate-300 uppercase tracking-wider text-[11px] font-semibold border-b border-slate-700">
                <th scope="col" className="px-4 py-3">ID</th>
                <th scope="col" className="px-4 py-3">Tingkat</th>
                <th scope="col" className="px-4 py-3">Jalur</th>
                <th scope="col" className="px-4 py-3">Tipe Alarm</th>
                <th scope="col" className="px-4 py-3 min-w-[200px]">Pesan &amp; Catatan</th>
                <th scope="col" className="px-4 py-3 whitespace-nowrap">Waktu Muncul</th>
                <th scope="col" className="px-4 py-3">Status</th>
                <th scope="col" className="px-4 py-3 min-w-[160px]">Jejak Audit</th>
                <th scope="col" className="px-4 py-3 text-right">Aksi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/70">
              {isLoading ? (
                <tr>
                  <td colSpan={9} className="px-4 py-12 text-center text-slate-400">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <RotateCw className="w-6 h-6 animate-spin text-emerald-400" />
                      <span>Memuat data alarm...</span>
                    </div>
                  </td>
                </tr>
              ) : filteredAlarms.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-12 text-center text-slate-400">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <CheckCircle2 className="w-8 h-8 text-emerald-500/80 mb-1" />
                      <span className="font-semibold text-slate-200">Tidak ada insiden alarm</span>
                      <span className="text-xs text-slate-400 max-w-sm">
                        {statusFilter !== "ALL" || severityFilter !== "ALL" || (selectedLineId && selectedLineId.toLowerCase() !== "all") || searchQuery
                          ? "Tidak ditemukan alarm yang sesuai dengan filter yang dipilih."
                          : "Sistem beroperasi optimal tanpa gangguan atau pelanggaran ambang batas."}
                      </span>
                    </div>
                  </td>
                </tr>
              ) : (
                filteredAlarms.map((alarm) => {
                  const upperSev = alarm.severity.toUpperCase();
                  const upperStat = alarm.status.toUpperCase();

                  // Severity badge styles
                  const sevConfig =
                    upperSev === "CRITICAL"
                      ? {
                          badge: "bg-rose-500/20 text-rose-300 border-rose-500/40",
                          icon: AlertCircle,
                          label: "KRITIS",
                        }
                      : upperSev === "WARNING"
                      ? {
                          badge: "bg-amber-500/20 text-amber-300 border-amber-500/40",
                          icon: AlertTriangle,
                          label: "PERINGATAN",
                        }
                      : {
                          badge: "bg-cyan-500/20 text-cyan-300 border-cyan-500/40",
                          icon: Info,
                          label: "INFO",
                        };
                  const SevIcon = sevConfig.icon;

                  // Status badge styles
                  const statConfig =
                    upperStat === "OPEN"
                      ? {
                          badge: "bg-rose-500/20 text-rose-300 border-rose-500/40",
                          dot: "bg-rose-500 animate-pulse",
                          label: "TERBUKA",
                        }
                      : upperStat === "ACKNOWLEDGED"
                      ? {
                          badge: "bg-amber-500/20 text-amber-300 border-amber-500/40",
                          dot: "bg-amber-400",
                          label: "DIAKUI",
                        }
                      : {
                          badge: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
                          dot: "bg-emerald-400",
                          label: "TERSELESAIKAN",
                        };

                  return (
                    <tr
                      key={alarm.id}
                      className="hover:bg-slate-750/50 transition-colors"
                    >
                      {/* ID */}
                      <td className="px-4 py-3 font-mono text-slate-300 font-semibold">
                        #{alarm.id}
                      </td>

                      {/* Severity */}
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold border ${sevConfig.badge}`}
                        >
                          <SevIcon className="w-3 h-3" />
                          <span>{sevConfig.label}</span>
                        </span>
                      </td>

                      {/* Line */}
                      <td className="px-4 py-3 font-mono text-slate-300">
                        {alarm.line_id}
                      </td>

                      {/* Alarm Type */}
                      <td className="px-4 py-3 font-mono font-medium text-slate-200">
                        {alarm.alarm_type}
                      </td>

                      {/* Message */}
                      <td className="px-4 py-3 text-slate-200 leading-snug">
                        <span>{alarm.message}</span>
                      </td>

                      {/* Opened At (WIB) */}
                      <td className="px-4 py-3 font-mono text-slate-300 whitespace-nowrap">
                        {formatToWIB(alarm.opened_at)}
                      </td>

                      {/* Status */}
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${statConfig.badge}`}
                        >
                          <span className={`w-1.5 h-1.5 rounded-full ${statConfig.dot}`} />
                          <span>{statConfig.label}</span>
                        </span>
                      </td>

                      {/* Audit Trail (Ack & Resolved At) */}
                      <td className="px-4 py-3 text-[11px] text-slate-400 font-mono">
                        {alarm.ack_at && (
                          <div className="text-amber-300/90 truncate" title={`Diakui: ${formatToWIB(alarm.ack_at)}`}>
                            Ack: {formatToWIB(alarm.ack_at)}
                          </div>
                        )}
                        {alarm.resolved_at && (
                          <div className="text-emerald-300/90 truncate" title={`Selesai: ${formatToWIB(alarm.resolved_at)}`}>
                            Res: {formatToWIB(alarm.resolved_at)}
                          </div>
                        )}
                        {!alarm.ack_at && !alarm.resolved_at && (
                          <span className="text-slate-600">-</span>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="px-4 py-3 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-1.5">
                          {upperStat === "OPEN" && (
                            <>
                              <button
                                type="button"
                                disabled={isViewer || isSubmitting}
                                onClick={() => openActionModal(alarm, "ACKNOWLEDGE")}
                                title={
                                  isViewer
                                    ? "Hanya baca untuk Viewer (memerlukan peran Operator atau Manager)"
                                    : "Akui alarm ini"
                                }
                                className={`px-2.5 py-1 text-xs font-semibold rounded transition flex items-center gap-1 ${
                                  isViewer
                                    ? "bg-slate-700/50 text-slate-500 cursor-not-allowed border border-slate-700"
                                    : "bg-amber-600 hover:bg-amber-500 text-white shadow-sm"
                                }`}
                              >
                                {isViewer ? <Lock className="w-3 h-3" /> : <Check className="w-3 h-3" />}
                                <span>Akui</span>
                              </button>

                              <button
                                type="button"
                                disabled={isViewer || isSubmitting}
                                onClick={() => openActionModal(alarm, "RESOLVE")}
                                title={
                                  isViewer
                                    ? "Hanya baca untuk Viewer (memerlukan peran Operator atau Manager)"
                                    : "Selesaikan insiden alarm ini"
                                }
                                className={`px-2.5 py-1 text-xs font-semibold rounded transition flex items-center gap-1 ${
                                  isViewer
                                    ? "bg-slate-700/50 text-slate-500 cursor-not-allowed border border-slate-700"
                                    : "bg-emerald-600 hover:bg-emerald-500 text-white shadow-sm"
                                }`}
                              >
                                {isViewer ? <Lock className="w-3 h-3" /> : <CheckCheck className="w-3 h-3" />}
                                <span>Selesaikan</span>
                              </button>
                            </>
                          )}

                          {upperStat === "ACKNOWLEDGED" && (
                            <button
                              type="button"
                              disabled={isViewer || isSubmitting}
                              onClick={() => openActionModal(alarm, "RESOLVE")}
                              title={
                                isViewer
                                  ? "Hanya baca untuk Viewer (memerlukan peran Operator atau Manager)"
                                  : "Selesaikan insiden alarm yang telah diakui ini"
                              }
                              className={`px-2.5 py-1 text-xs font-semibold rounded transition flex items-center gap-1 ${
                                isViewer
                                  ? "bg-slate-700/50 text-slate-500 cursor-not-allowed border border-slate-700"
                                  : "bg-emerald-600 hover:bg-emerald-500 text-white shadow-sm"
                              }`}
                            >
                              {isViewer ? <Lock className="w-3 h-3" /> : <CheckCheck className="w-3 h-3" />}
                              <span>Selesaikan</span>
                            </button>
                          )}

                          {upperStat === "RESOLVED" && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium text-slate-400 bg-slate-900 border border-slate-700">
                              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                              <span>Tuntas</span>
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Action Modal (Acknowledge / Resolve) */}
      {modalOpen && targetAlarm && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="alarm-action-modal-title"
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              closeActionModal();
            }
          }}
        >
          <div
            className="bg-slate-900 border border-slate-700 rounded-lg shadow-xl max-w-lg w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="px-5 py-4 border-b border-slate-700 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div
                  className={`p-2 rounded-md ${
                    actionType === "ACKNOWLEDGE"
                      ? "bg-amber-500/20 text-amber-300"
                      : "bg-emerald-500/20 text-emerald-300"
                  }`}
                >
                  {actionType === "ACKNOWLEDGE" ? (
                    <Clock className="w-5 h-5" />
                  ) : (
                    <CheckCircle2 className="w-5 h-5" />
                  )}
                </div>
                <div>
                  <h3 id="alarm-action-modal-title" className="text-base font-semibold text-slate-100">
                    {actionType === "ACKNOWLEDGE"
                      ? "Konfirmasi Pengakuan Alarm (Acknowledge)"
                      : "Penyelesaian Insiden Alarm (Resolve)"}
                  </h3>
                  <p className="text-xs text-slate-400">
                    Alarm #{targetAlarm.id} · {targetAlarm.alarm_type} · Jalur {targetAlarm.line_id}
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={closeActionModal}
                disabled={isSubmitting}
                className="text-slate-400 hover:text-white p-1 rounded transition"
                aria-label="Tutup dialog modal"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body Form */}
            <form onSubmit={handleConfirmAction} className="p-5 space-y-4">
              {/* Error Notice in Modal */}
              {modalError && (
                <div className="p-3 bg-rose-950/80 border border-rose-500/50 rounded-md text-xs text-rose-200 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
                  <span>{modalError}</span>
                </div>
              )}

              {/* Alarm Summary Card */}
              <div className="bg-slate-950/70 border border-slate-800 p-3.5 rounded-md space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400 font-medium">Tingkat Keparahan:</span>
                  <span
                    className={`font-bold px-2 py-0.5 rounded text-[10px] ${
                      targetAlarm.severity === "CRITICAL"
                        ? "bg-rose-500/20 text-rose-300"
                        : targetAlarm.severity === "WARNING"
                        ? "bg-amber-500/20 text-amber-300"
                        : "bg-cyan-500/20 text-cyan-300"
                    }`}
                  >
                    {targetAlarm.severity}
                  </span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-slate-400 font-medium">Waktu Muncul:</span>
                  <span className="font-mono text-slate-300">{formatToWIB(targetAlarm.opened_at)}</span>
                </div>

                <div>
                  <span className="text-slate-400 font-medium">Pesan Alarm:</span>
                  <p className="text-slate-200 mt-0.5 leading-relaxed bg-slate-900 p-2 rounded border border-slate-800">
                    {targetAlarm.message}
                  </p>
                </div>
              </div>

              {/* Operator Name Field */}
              <div>
                <label
                  htmlFor="operator-name-input"
                  className="block text-xs font-medium text-slate-300 mb-1"
                >
                  Nama Operator / Petugas Penanggung Jawab
                </label>
                <div className="relative">
                  <UserCheck className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                  <input
                    id="operator-name-input"
                    type="text"
                    required
                    value={operatorName}
                    onChange={(e) => setOperatorName(e.target.value)}
                    placeholder="misal: operator_1, jono_maintenance"
                    className="w-full bg-slate-950 border border-slate-700 rounded-md pl-9 pr-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
              </div>

              {/* Action Note / Resolution Field */}
              <div>
                <label
                  htmlFor="action-notes-input"
                  className="block text-xs font-medium text-slate-300 mb-1"
                >
                  <span className="flex items-center gap-1.5">
                    <MessageSquare className="w-3.5 h-3.5 text-slate-400" />
                    <span>
                      {actionType === "ACKNOWLEDGE"
                        ? "Catatan Pengakuan (Opsional):"
                        : "Catatan Penyelesaian & Tindakan Korektif (Wajib/Direkomendasikan):"}
                    </span>
                  </span>
                </label>
                <textarea
                  id="action-notes-input"
                  rows={3}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder={
                    actionType === "ACKNOWLEDGE"
                      ? "Contoh: Petugas sedang menuju lokasi shackle conveyor untuk memeriksa bearing..."
                      : "Contoh: Penumpukan ayam dibersihkan, rantai konveyor distel ulang, kecepatan stabil di 60 CPM..."
                  }
                  className="w-full bg-slate-950 border border-slate-700 rounded-md px-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 leading-relaxed"
                />
                <span className="text-[10px] text-slate-500">
                  Catatan akan dicatat dalam jejak audit kepatuhan ISO/HACCP dan dapat diunduh pada laporan insiden.
                </span>
              </div>

              {/* Modal Footer Buttons */}
              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={closeActionModal}
                  disabled={isSubmitting}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-md transition focus:outline-none border border-slate-700 disabled:opacity-50"
                >
                  Batal
                </button>

                <button
                  type="submit"
                  disabled={isSubmitting || isViewer}
                  className={`px-4 py-2 text-xs font-semibold rounded-md text-white transition flex items-center gap-2 shadow-md disabled:opacity-50 ${
                    actionType === "ACKNOWLEDGE"
                      ? "bg-amber-600 hover:bg-amber-500 focus:ring-2 focus:ring-amber-400"
                      : "bg-emerald-600 hover:bg-emerald-500 focus:ring-2 focus:ring-emerald-400"
                  }`}
                >
                  {isSubmitting ? (
                    <>
                      <RotateCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Menyimpan...</span>
                    </>
                  ) : actionType === "ACKNOWLEDGE" ? (
                    <>
                      <Check className="w-3.5 h-3.5" />
                      <span>Konfirmasi Pengakuan (Ack)</span>
                    </>
                  ) : (
                    <>
                      <CheckCheck className="w-3.5 h-3.5" />
                      <span>Konfirmasi Selesaikan</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default AlarmsView;
