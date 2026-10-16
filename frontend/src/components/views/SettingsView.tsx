import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import {
  Sliders,
  Shield,
  ShieldCheck,
  Check,
  X,
  AlertCircle,
  CheckCircle2,
  Lock,
  RotateCw,
  Save,
  Layers,
  Clock,
  Eye,
  Info,
  UserCheck,
} from "lucide-react";
import { useAppContext } from "../../context/AppContext";
import { apiClient } from "../../services/apiClient";
import type { LineDetailDTO } from "../../types";

export interface SettingsViewProps {
  lineId?: string;
}

export interface LineFormState {
  name: string;
  daily_target: number;
  target_speed: number;
  is_active: boolean;
}

export interface ThresholdSettings {
  under_critical: number; // CPM, default 15
  under_warning: number; // CPM, default 30
  over_warning: number; // CPM, default 75
  over_critical: number; // CPM, default 90
  heartbeat_timeout: number; // seconds, default 60
}

export const DEFAULT_THRESHOLDS: ThresholdSettings = {
  under_critical: 15,
  under_warning: 30,
  over_warning: 75,
  over_critical: 90,
  heartbeat_timeout: 60,
};

export interface ThresholdPreset {
  id: string;
  name: string;
  badge: string;
  description: string;
  settings: ThresholdSettings;
}

export const THRESHOLD_PRESETS: ThresholdPreset[] = [
  {
    id: "factory_default",
    name: "Standar Pabrik (Rekomendasi)",
    badge: "Standar Industri",
    description: "Optimal untuk shackle konveyor standar broiler (30-75 CPM)",
    settings: {
      under_critical: 15,
      under_warning: 30,
      over_warning: 75,
      over_critical: 90,
      heartbeat_timeout: 60,
    },
  },
  {
    id: "high_throughput",
    name: "Throughput Tinggi",
    badge: "Shift Sibuk",
    description: "Disesuaikan untuk shift pemotongan berkecepatan tinggi",
    settings: {
      under_critical: 20,
      under_warning: 45,
      over_warning: 95,
      over_critical: 115,
      heartbeat_timeout: 45,
    },
  },
  {
    id: "conservative",
    name: "Konservatif / Pemeliharaan",
    badge: "Uji Coba",
    description: "Toleransi lebih longgar saat pemeliharaan rantai konveyor",
    settings: {
      under_critical: 10,
      under_warning: 25,
      over_warning: 65,
      over_critical: 80,
      heartbeat_timeout: 90,
    },
  },
];

export type PermissionLevel = "none" | "view" | "operate" | "manage" | "full";

export interface MatrixRow {
  id: string;
  feature: string;
  category: string;
  description: string;
  viewer: { level: PermissionLevel; label: string };
  operator: { level: PermissionLevel; label: string };
  manager: { level: PermissionLevel; label: string };
  admin: { level: PermissionLevel; label: string };
}

export const PERMISSIONS_MATRIX: MatrixRow[] = [
  {
    id: "overview",
    feature: "Dashboard Ringkasan & KPI",
    category: "Pemantauan",
    description: "Melihat total hitungan karkas hari ini, target capaian %, dan status sensor",
    viewer: { level: "view", label: "Lihat Ringkasan" },
    operator: { level: "view", label: "Lihat Ringkasan" },
    manager: { level: "view", label: "Analisis & Pantau" },
    admin: { level: "full", label: "Akses Penuh" },
  },
  {
    id: "live_stream",
    feature: "Video MJPEG & Telemetri Langsung",
    category: "Pemantauan",
    description: "Streaming video feed konveyor, grafik CPM real-time, dan metrik latensi/FPS",
    viewer: { level: "view", label: "Tonton Umpan" },
    operator: { level: "view", label: "Pantau Telemetri" },
    manager: { level: "view", label: "Audit Kualitas" },
    admin: { level: "full", label: "Debug Sensor & RTSP" },
  },
  {
    id: "alarms",
    feature: "Manajemen Alarm & Insiden",
    category: "Operasional",
    description: "Mengakui insiden alarm (ACK), mencatat resolusi perbaikan, dan eskalasi",
    viewer: { level: "view", label: "Lihat Daftar Alarm" },
    operator: { level: "operate", label: "Akui & Selesaikan" },
    manager: { level: "manage", label: "Investigasi & Eskalasi" },
    admin: { level: "full", label: "Kontrol Penuh & Hapus" },
  },
  {
    id: "reports",
    feature: "Laporan Produksi & Ekspor Data",
    category: "Pelaporan",
    description: "Melihat event log optical sensor dan ekspor dokumen resmi Excel (.xlsx) / PDF",
    viewer: { level: "none", label: "Terkunci" },
    operator: { level: "operate", label: "Unduh Laporan Shift" },
    manager: { level: "manage", label: "Ekspor Resmi Excel/PDF" },
    admin: { level: "full", label: "Ekspor Historis Penuh" },
  },
  {
    id: "line_config",
    feature: "Konfigurasi Jalur & Target Harian",
    category: "Pengaturan",
    description: "Mengubah nama jalur konveyor, target jumlah pemotongan, dan status aktif",
    viewer: { level: "none", label: "Terkunci" },
    operator: { level: "none", label: "Terkunci" },
    manager: { level: "manage", label: "Ubah Parameter Jalur" },
    admin: { level: "full", label: "Kelola Semua Jalur" },
  },
  {
    id: "thresholds",
    feature: "Ambang Batas Kecepatan & Sensor",
    category: "Pengaturan",
    description: "Menyesuaikan rentang warning/critical CPM dan batas waktu camera heartbeat",
    viewer: { level: "none", label: "Terkunci" },
    operator: { level: "none", label: "Terkunci" },
    manager: { level: "manage", label: "Ubah Ambang Batas" },
    admin: { level: "full", label: "Kalibrasi & Override" },
  },
  {
    id: "user_mgmt",
    feature: "Manajemen Akun & Otoritas Peran",
    category: "Keamanan",
    description: "Mendaftarkan operator baru, rotasi kata sandi, dan perubahan peran sistem",
    viewer: { level: "none", label: "Terkunci" },
    operator: { level: "none", label: "Terkunci" },
    manager: { level: "view", label: "Lihat Operator Shift" },
    admin: { level: "full", label: "Manajemen Akun Penuh" },
  },
];

const THRESHOLD_STORAGE_PREFIX = "lihat_thresholds_";
const TARGET_SPEED_STORAGE_PREFIX = "lihat_target_speed_";

function getStoredThresholds(lineId: string): ThresholdSettings {
  if (typeof window === "undefined" || !window.localStorage) {
    return DEFAULT_THRESHOLDS;
  }
  try {
    const raw = window.localStorage.getItem(`${THRESHOLD_STORAGE_PREFIX}${lineId}`);
    if (raw) {
      const parsed = JSON.parse(raw);
      return {
        under_critical: Number(parsed.under_critical) || DEFAULT_THRESHOLDS.under_critical,
        under_warning: Number(parsed.under_warning) || DEFAULT_THRESHOLDS.under_warning,
        over_warning: Number(parsed.over_warning) || DEFAULT_THRESHOLDS.over_warning,
        over_critical: Number(parsed.over_critical) || DEFAULT_THRESHOLDS.over_critical,
        heartbeat_timeout: Number(parsed.heartbeat_timeout) || DEFAULT_THRESHOLDS.heartbeat_timeout,
      };
    }
  } catch {
    // ignore json error
  }
  return DEFAULT_THRESHOLDS;
}

function setStoredThresholds(lineId: string, thresholds: ThresholdSettings): void {
  if (typeof window === "undefined" || !window.localStorage) return;
  try {
    window.localStorage.setItem(`${THRESHOLD_STORAGE_PREFIX}${lineId}`, JSON.stringify(thresholds));
  } catch {
    // ignore storage error
  }
}

function getStoredTargetSpeed(lineId: string): number {
  if (typeof window === "undefined" || !window.localStorage) return 120;
  try {
    const raw = window.localStorage.getItem(`${TARGET_SPEED_STORAGE_PREFIX}${lineId}`);
    if (raw) {
      const val = parseInt(raw, 10);
      if (!isNaN(val) && val > 0) return val;
    }
  } catch {
    // ignore storage error
  }
  return 120;
}

function setStoredTargetSpeed(lineId: string, speed: number): void {
  if (typeof window === "undefined" || !window.localStorage) return;
  try {
    window.localStorage.setItem(`${TARGET_SPEED_STORAGE_PREFIX}${lineId}`, String(speed));
  } catch {
    // ignore storage error
  }
}

export function SettingsView({ lineId: propLineId }: SettingsViewProps) {
  const { currentLineId, setLineId, currentRole, lines, refreshLines } = useAppContext();

  // Selected line id sync
  const activeLineId = propLineId || currentLineId || (lines[0]?.id ?? "line-1");

  // Edit capability
  const canEdit = currentRole === "ADMIN" || currentRole === "MANAGER";
  const isRestricted = currentRole === "VIEWER" || currentRole === "OPERATOR";

  // Line Form States
  const [lineForm, setLineForm] = useState<LineFormState>({
    name: "",
    daily_target: 60000,
    target_speed: 120,
    is_active: true,
  });
  const [initialLineForm, setInitialLineForm] = useState<LineFormState>({
    name: "",
    daily_target: 60000,
    target_speed: 120,
    is_active: true,
  });

  // Thresholds States
  const [thresholds, setThresholds] = useState<ThresholdSettings>(DEFAULT_THRESHOLDS);
  const [initialThresholds, setInitialThresholds] = useState<ThresholdSettings>(DEFAULT_THRESHOLDS);

  // Status & Feedback States
  const [isLoadingLine, setIsLoadingLine] = useState<boolean>(false);
  const [isSavingLine, setIsSavingLine] = useState<boolean>(false);
  const [isSavingThresholds, setIsSavingThresholds] = useState<boolean>(false);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<string | null>(null);
  const [saveErrorMsg, setSaveErrorMsg] = useState<string | null>(null);

  // Success auto-dismiss timer ref
  const successDismissTimeoutRef = useRef<number | null>(null);

  const clearSuccessMsg = useCallback(() => {
    if (successDismissTimeoutRef.current !== null) {
      window.clearTimeout(successDismissTimeoutRef.current);
      successDismissTimeoutRef.current = null;
    }
    setSaveSuccessMsg(null);
  }, []);

  const triggerSuccessMsg = useCallback((msg: string) => {
    if (successDismissTimeoutRef.current !== null) {
      window.clearTimeout(successDismissTimeoutRef.current);
    }
    setSaveSuccessMsg(msg);
    setSaveErrorMsg(null);
    successDismissTimeoutRef.current = window.setTimeout(() => {
      setSaveSuccessMsg(null);
      successDismissTimeoutRef.current = null;
    }, 4500);
  }, []);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (successDismissTimeoutRef.current !== null) {
        window.clearTimeout(successDismissTimeoutRef.current);
      }
    };
  }, []);

  // Load line details and local settings whenever activeLineId changes
  const loadLineDetails = useCallback(
    async (targetId: string) => {
      setIsLoadingLine(true);
      setSaveErrorMsg(null);
      clearSuccessMsg();

      // Load stored thresholds & target speed
      const storedThresholds = getStoredThresholds(targetId);
      setThresholds(storedThresholds);
      setInitialThresholds(storedThresholds);

      const storedSpeed = getStoredTargetSpeed(targetId);

      // Fallback data from context
      const fallbackLine = lines.find((l) => l.id === targetId) || lines[0];

      try {
        let lineDetail: LineDetailDTO | null = null;
        if ("getLine" in apiClient && typeof (apiClient as Record<string, unknown>).getLine === "function") {
          lineDetail = await (apiClient as unknown as { getLine: (id: string) => Promise<LineDetailDTO> }).getLine(targetId);
        } else {
          lineDetail = await apiClient.request<LineDetailDTO>(`/api/v1/lines/${encodeURIComponent(targetId)}`);
        }

        if (lineDetail) {
          const loadedForm: LineFormState = {
            name: lineDetail.name,
            daily_target: lineDetail.daily_target,
            target_speed: storedSpeed,
            is_active: lineDetail.is_active,
          };
          setLineForm(loadedForm);
          setInitialLineForm(loadedForm);
        }
      } catch (err) {
        // Fallback gracefully to line item in context
        const loadedForm: LineFormState = {
          name: fallbackLine?.name ?? "Conveyor Line 1",
          daily_target: fallbackLine?.daily_target ?? 60000,
          target_speed: storedSpeed,
          is_active: fallbackLine?.is_active ?? true,
        };
        setLineForm(loadedForm);
        setInitialLineForm(loadedForm);
      } finally {
        setIsLoadingLine(false);
      }
    },
    [lines, clearSuccessMsg]
  );

  useEffect(() => {
    loadLineDetails(activeLineId);
  }, [activeLineId, loadLineDetails]);

  // Is Line form modified
  const isLineFormDirty = useMemo(() => {
    return (
      lineForm.name !== initialLineForm.name ||
      lineForm.daily_target !== initialLineForm.daily_target ||
      lineForm.target_speed !== initialLineForm.target_speed ||
      lineForm.is_active !== initialLineForm.is_active
    );
  }, [lineForm, initialLineForm]);

  // Is Thresholds form modified
  const isThresholdsDirty = useMemo(() => {
    return (
      thresholds.under_critical !== initialThresholds.under_critical ||
      thresholds.under_warning !== initialThresholds.under_warning ||
      thresholds.over_warning !== initialThresholds.over_warning ||
      thresholds.over_critical !== initialThresholds.over_critical ||
      thresholds.heartbeat_timeout !== initialThresholds.heartbeat_timeout
    );
  }, [thresholds, initialThresholds]);

  // Handle production line change from dropdown
  const handleLineSelect = (newId: string) => {
    setLineId(newId);
    clearSuccessMsg();
    setSaveErrorMsg(null);
  };

  // Save Line configuration to backend
  const handleSaveLineConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canEdit) {
      setSaveErrorMsg(
        "Akses Ditolak: Hanya pengguna dengan peran Manager atau Admin yang memiliki hak mengubah konfigurasi."
      );
      return;
    }

    if (!lineForm.name.trim()) {
      setSaveErrorMsg("Nama jalur tidak boleh kosong.");
      return;
    }

    if (lineForm.daily_target <= 0) {
      setSaveErrorMsg("Target harian harus berupa angka positif lebih dari 0 ekor.");
      return;
    }

    if (lineForm.target_speed <= 0) {
      setSaveErrorMsg("Target kecepatan konveyor harus lebih dari 0 CPM.");
      return;
    }

    setIsSavingLine(true);
    setSaveErrorMsg(null);

    try {
      await apiClient.updateLine(activeLineId, {
        name: lineForm.name.trim(),
        daily_target: Number(lineForm.daily_target),
        is_active: lineForm.is_active,
      });

      // Save target speed in local storage
      setStoredTargetSpeed(activeLineId, Number(lineForm.target_speed));

      // Refresh global lines context
      await refreshLines();

      setInitialLineForm({ ...lineForm });
      triggerSuccessMsg(
        `Konfigurasi jalur "${lineForm.name.trim()}" berhasil disimpan ke server.`
      );
    } catch (err) {
      // Backend error fallback
      const errorDetail = err instanceof Error ? err.message : String(err);
      setSaveErrorMsg(
        `Gagal memperbarui konfigurasi jalur di server: ${errorDetail}`
      );
    } finally {
      setIsSavingLine(false);
    }
  };

  // Reset Line configuration to initial loaded values
  const handleResetLineConfig = () => {
    setLineForm({ ...initialLineForm });
    clearSuccessMsg();
    setSaveErrorMsg(null);
  };

  // Apply a threshold preset
  const handleApplyPreset = (preset: ThresholdPreset) => {
    if (!canEdit) return;
    setThresholds({ ...preset.settings });
  };

  // Save Threshold matrix
  const handleSaveThresholds = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canEdit) {
      setSaveErrorMsg(
        "Akses Ditolak: Hanya pengguna dengan peran Manager atau Admin yang dapat mengubah ambang batas."
      );
      return;
    }

    // Validation
    if (thresholds.under_critical >= thresholds.under_warning) {
      setSaveErrorMsg(
        "Batas kritis lambat harus bernilai lebih kecil dari batas peringatan lambat."
      );
      return;
    }

    if (thresholds.under_warning >= thresholds.over_warning) {
      setSaveErrorMsg(
        "Batas peringatan lambat harus bernilai lebih kecil dari batas peringatan cepat."
      );
      return;
    }

    if (thresholds.over_warning >= thresholds.over_critical) {
      setSaveErrorMsg(
        "Batas peringatan cepat harus bernilai lebih kecil dari batas kritis cepat."
      );
      return;
    }

    if (thresholds.heartbeat_timeout < 5) {
      setSaveErrorMsg("Batas waktu camera heartbeat minimal 5 detik.");
      return;
    }

    setIsSavingThresholds(true);
    setSaveErrorMsg(null);

    try {
      setStoredThresholds(activeLineId, thresholds);
      setInitialThresholds({ ...thresholds });
      triggerSuccessMsg(
        `Ambang batas alarm untuk jalur ${activeLineId} berhasil disimpan.`
      );
    } catch (err) {
      setSaveErrorMsg("Gagal menyimpan ambang batas ke penyimpanan lokal.");
    } finally {
      setIsSavingThresholds(false);
    }
  };

  // Reset Thresholds to initial loaded values
  const handleResetThresholds = () => {
    setThresholds({ ...initialThresholds });
    clearSuccessMsg();
    setSaveErrorMsg(null);
  };

  const currentLineItem = lines.find((l) => l.id === activeLineId) || lines[0];

  return (
    <div className="space-y-6">
      {/* Role-Based Edit Restriction Banner */}
      {isRestricted && (
        <div
          role="alert"
          className="flex items-start sm:items-center gap-3 p-4 bg-amber-950/70 border border-amber-500/50 rounded-lg text-amber-200 shadow-sm"
        >
          <Lock className="w-5 h-5 text-amber-400 shrink-0 mt-0.5 sm:mt-0" />
          <div className="text-xs sm:text-sm leading-relaxed flex-1">
            <span className="font-bold">Akses Terbatas:</span> Hanya Manager dan Admin yang dapat
            mengubah konfigurasi jalur dan ambang batas. (Peran Anda saat ini:{" "}
            <span className="font-semibold uppercase tracking-wider text-amber-300">
              {currentRole}
            </span>
            )
          </div>
        </div>
      )}

      {/* Success Notification Banner */}
      {saveSuccessMsg && (
        <div
          role="status"
          className="flex items-center justify-between px-4 py-3 bg-emerald-950/80 border border-emerald-500/50 rounded-lg text-emerald-200 text-xs sm:text-sm shadow-sm"
        >
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
            <span className="font-medium">{saveSuccessMsg}</span>
          </div>
          <button
            type="button"
            onClick={clearSuccessMsg}
            className="text-emerald-400 hover:text-emerald-200 p-1 rounded transition"
            aria-label="Tutup pesan sukses"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Error Notification Banner */}
      {saveErrorMsg && (
        <div
          role="alert"
          className="flex items-center justify-between px-4 py-3 bg-rose-950/80 border border-rose-500/50 rounded-lg text-rose-200 text-xs sm:text-sm shadow-sm"
        >
          <div className="flex items-center gap-2.5">
            <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
            <span className="font-medium">{saveErrorMsg}</span>
          </div>
          <button
            type="button"
            onClick={() => setSaveErrorMsg(null)}
            className="text-rose-400 hover:text-rose-200 p-1 rounded transition"
            aria-label="Tutup pesan error"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Section 1: Line Selection & Configuration */}
      <section
        aria-labelledby="section-line-config"
        className="bg-slate-800 border border-slate-700 rounded-lg p-5 sm:p-6 shadow-sm"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-700 gap-3">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-emerald-950/70 border border-emerald-500/30 rounded-md text-emerald-400">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <h3 id="section-line-config" className="text-lg font-bold text-slate-100">
                Konfigurasi Jalur Produksi
              </h3>
              <p className="text-xs text-slate-400">
                Pilih jalur konveyor dan sesuaikan parameter operasional mesin
              </p>
            </div>
          </div>

          {/* Active Line Selector Dropdown */}
          <div className="flex items-center gap-2">
            <label
              htmlFor="settings-line-selector"
              className="text-xs font-medium text-slate-300"
            >
              Jalur Aktif:
            </label>
            <select
              id="settings-line-selector"
              aria-label="Pilih Jalur Produksi Untuk Konfigurasi"
              value={activeLineId}
              onChange={(e) => handleLineSelect(e.target.value)}
              className="bg-slate-900 border border-slate-600 text-slate-100 text-xs sm:text-sm rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-emerald-500 cursor-pointer font-medium"
            >
              {lines.map((line) => (
                <option key={line.id} value={line.id} className="bg-slate-900 text-slate-100">
                  {line.name} ({line.status})
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Form Controls */}
        <form onSubmit={handleSaveLineConfig} className="mt-5 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Line Name */}
            <div>
              <label
                htmlFor="line-name-input"
                className="block text-xs font-semibold text-slate-300 mb-1.5"
              >
                Nama Jalur Produksi
              </label>
              <input
                id="line-name-input"
                type="text"
                disabled={!canEdit || isLoadingLine}
                value={lineForm.name}
                onChange={(e) => setLineForm((prev) => ({ ...prev, name: e.target.value }))}
                placeholder="cth. Conveyor Line 1"
                className={`w-full bg-slate-900 border rounded-md px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 transition ${
                  !canEdit
                    ? "border-slate-700 bg-slate-900/50 text-slate-400 cursor-not-allowed"
                    : "border-slate-600"
                }`}
                required
              />
              <p className="text-[11px] text-slate-400 mt-1">
                Identitas unik untuk laporan produksi dan tampilan live sensor.
              </p>
            </div>

            {/* Daily Target */}
            <div>
              <label
                htmlFor="line-target-input"
                className="block text-xs font-semibold text-slate-300 mb-1.5"
              >
                Target Harian (Ekor / Burung)
              </label>
              <div className="relative">
                <input
                  id="line-target-input"
                  type="number"
                  min="1"
                  step="500"
                  disabled={!canEdit || isLoadingLine}
                  value={lineForm.daily_target}
                  onChange={(e) =>
                    setLineForm((prev) => ({
                      ...prev,
                      daily_target: parseInt(e.target.value, 10) || 0,
                    }))
                  }
                  placeholder="60000"
                  className={`w-full bg-slate-900 border rounded-md px-3 py-2 pr-16 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 transition ${
                    !canEdit
                      ? "border-slate-700 bg-slate-900/50 text-slate-400 cursor-not-allowed"
                      : "border-slate-600"
                  }`}
                  required
                />
                <span className="absolute right-3 top-2 text-xs text-slate-400 font-medium pointer-events-none">
                  ekor
                </span>
              </div>
              <p className="text-[11px] text-slate-400 mt-1">
                Kapasitas kuota penyelesaian karkas yang diharapkan per siklus 24 jam.
              </p>
            </div>

            {/* Target Speed (CPM) */}
            <div>
              <label
                htmlFor="line-speed-input"
                className="block text-xs font-semibold text-slate-300 mb-1.5"
              >
                Kecepatan Target Konveyor (CPM)
              </label>
              <div className="relative">
                <input
                  id="line-speed-input"
                  type="number"
                  min="10"
                  max="250"
                  step="5"
                  disabled={!canEdit || isLoadingLine}
                  value={lineForm.target_speed}
                  onChange={(e) =>
                    setLineForm((prev) => ({
                      ...prev,
                      target_speed: parseInt(e.target.value, 10) || 0,
                    }))
                  }
                  placeholder="120"
                  className={`w-full bg-slate-900 border rounded-md px-3 py-2 pr-16 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 transition ${
                    !canEdit
                      ? "border-slate-700 bg-slate-900/50 text-slate-400 cursor-not-allowed"
                      : "border-slate-600"
                  }`}
                  required
                />
                <span className="absolute right-3 top-2 text-xs text-slate-400 font-medium pointer-events-none">
                  cpm
                </span>
              </div>
              <p className="text-[11px] text-slate-400 mt-1">
                Laju ideal pergerakan shackle konveyor (ayam per menit).
              </p>
            </div>

            {/* Active Line Status Toggle */}
            <div className="flex flex-col justify-center">
              <span className="block text-xs font-semibold text-slate-300 mb-2">
                Status Operasional Jalur
              </span>
              <label
                htmlFor="line-active-toggle"
                className={`flex items-center gap-3 p-2.5 rounded-md border transition ${
                  lineForm.is_active
                    ? "bg-emerald-950/30 border-emerald-500/40"
                    : "bg-slate-900/50 border-slate-700"
                } ${!canEdit ? "cursor-not-allowed opacity-75" : "cursor-pointer"}`}
              >
                <input
                  id="line-active-toggle"
                  type="checkbox"
                  disabled={!canEdit || isLoadingLine}
                  checked={lineForm.is_active}
                  onChange={(e) =>
                    setLineForm((prev) => ({ ...prev, is_active: e.target.checked }))
                  }
                  className="w-4 h-4 rounded border-slate-600 text-emerald-600 focus:ring-emerald-500 cursor-pointer"
                />
                <div className="flex flex-col">
                  <span className="text-xs font-semibold text-slate-200">
                    {lineForm.is_active ? "Jalur Produksi Aktif" : "Jalur Dinonaktifkan"}
                  </span>
                  <span className="text-[11px] text-slate-400">
                    {lineForm.is_active
                      ? "Kamera aktif memproses event deteksi dan mencatat alarm."
                      : "Jalur dalam mode shutdown atau perbaikan terjadwal."}
                  </span>
                </div>
              </label>
            </div>
          </div>

          {/* Form Actions Footer */}
          <div className="flex flex-wrap items-center justify-between pt-4 border-t border-slate-700 gap-3">
            <div className="text-xs text-slate-400 flex items-center gap-1.5">
              <Info className="w-3.5 h-3.5 text-slate-400" />
              <span>
                ID Sistem: <code className="text-slate-300">{activeLineId}</code> · Status Sensor:{" "}
                <span className="text-emerald-400 font-medium uppercase">
                  {currentLineItem?.status ?? "online"}
                </span>
              </span>
            </div>

            <div className="flex items-center gap-2.5">
              <button
                type="button"
                onClick={handleResetLineConfig}
                disabled={!canEdit || !isLineFormDirty || isSavingLine}
                className="px-3.5 py-1.5 rounded-md text-xs font-medium text-slate-300 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed transition"
              >
                Reset
              </button>

              <button
                type="submit"
                disabled={!canEdit || !isLineFormDirty || isSavingLine}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-md text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50 disabled:cursor-not-allowed shadow transition focus:ring-2 focus:ring-emerald-400"
              >
                {isSavingLine ? (
                  <>
                    <RotateCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Menyimpan...</span>
                  </>
                ) : (
                  <>
                    <Save className="w-3.5 h-3.5" />
                    <span>Simpan Konfigurasi Jalur</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </form>
      </section>

      {/* Section 2: Threshold Limits Matrix (Speed & Heartbeat Alerts) */}
      <section
        aria-labelledby="section-thresholds"
        className="bg-slate-800 border border-slate-700 rounded-lg p-5 sm:p-6 shadow-sm"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-700 gap-3">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-amber-950/70 border border-amber-500/30 rounded-md text-amber-400">
              <Sliders className="w-5 h-5" />
            </div>
            <div>
              <h3 id="section-thresholds" className="text-lg font-bold text-slate-100">
                Matriks Ambang Batas & Alarm Kecepatan (CPM)
              </h3>
              <p className="text-xs text-slate-400">
                Kriteria batas kecepatan konveyor dan batas waktu respons sensor optik kamera
              </p>
            </div>
          </div>

          {/* Preset Buttons */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
            <span className="text-xs font-medium text-slate-400 mr-1 hidden sm:inline">
              Preset:
            </span>
            {THRESHOLD_PRESETS.map((preset) => (
              <button
                key={preset.id}
                type="button"
                disabled={!canEdit}
                onClick={() => handleApplyPreset(preset)}
                className="px-2.5 py-1 rounded text-xs font-medium bg-slate-700 hover:bg-slate-600 text-slate-200 border border-slate-600 hover:border-slate-500 disabled:opacity-50 disabled:cursor-not-allowed transition shrink-0"
                title={preset.description}
              >
                {preset.name}
              </button>
            ))}
          </div>
        </div>

        {/* Visual Industrial Zones Gauge */}
        <div className="mt-5 p-4 bg-slate-900 rounded-lg border border-slate-700/80">
          <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-3 flex items-center justify-between">
            <span>Visualisasi Rentang Kecepatan Industri (CPM)</span>
            <span className="text-[11px] font-normal text-slate-400">
              Optimal: {thresholds.under_warning + 1} - {thresholds.over_warning - 1} CPM
            </span>
          </h4>

          {/* Color bar indicator */}
          <div className="grid grid-cols-1 sm:grid-cols-5 gap-2 text-xs">
            {/* Critical Low */}
            <div className="p-2.5 rounded-md bg-rose-950/60 border border-rose-500/40 text-rose-200 flex flex-col justify-between">
              <div className="flex items-center justify-between">
                <span className="font-bold text-rose-400">Kritis Rendah</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-900/80 text-rose-300 font-mono">
                  &lt; {thresholds.under_critical} CPM
                </span>
              </div>
              <p className="text-[11px] text-rose-300/80 mt-1">
                Konveyor berhenti atau macet parah.
              </p>
            </div>

            {/* Warning Low */}
            <div className="p-2.5 rounded-md bg-amber-950/60 border border-amber-500/40 text-amber-200 flex flex-col justify-between">
              <div className="flex items-center justify-between">
                <span className="font-bold text-amber-400">Peringatan Lambat</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-900/80 text-amber-300 font-mono">
                  {thresholds.under_critical} - {thresholds.under_warning} CPM
                </span>
              </div>
              <p className="text-[11px] text-amber-300/80 mt-1">
                Throughput di bawah kuota operasional.
              </p>
            </div>

            {/* Normal Range */}
            <div className="p-2.5 rounded-md bg-emerald-950/60 border border-emerald-500/40 text-emerald-200 flex flex-col justify-between">
              <div className="flex items-center justify-between">
                <span className="font-bold text-emerald-400">Rentang Optimal</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-900/80 text-emerald-300 font-mono">
                  {thresholds.under_warning + 1} - {thresholds.over_warning - 1} CPM
                </span>
              </div>
              <p className="text-[11px] text-emerald-300/80 mt-1">
                Kondisi stabil, akurasi deteksi tinggi (98%+).
              </p>
            </div>

            {/* Warning High */}
            <div className="p-2.5 rounded-md bg-amber-950/60 border border-amber-500/40 text-amber-200 flex flex-col justify-between">
              <div className="flex items-center justify-between">
                <span className="font-bold text-amber-400">Peringatan Cepat</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-900/80 text-amber-300 font-mono">
                  {thresholds.over_warning} - {thresholds.over_critical - 1} CPM
                </span>
              </div>
              <p className="text-[11px] text-amber-300/80 mt-1">
                Laju konveyor melampaui ritme normal.
              </p>
            </div>

            {/* Critical High */}
            <div className="p-2.5 rounded-md bg-rose-950/60 border border-rose-500/40 text-rose-200 flex flex-col justify-between">
              <div className="flex items-center justify-between">
                <span className="font-bold text-rose-400">Kritis Cepat</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-900/80 text-rose-300 font-mono">
                  &ge; {thresholds.over_critical} CPM
                </span>
              </div>
              <p className="text-[11px] text-rose-300/80 mt-1">
                Bahaya mekanik & frame drop kamera.
              </p>
            </div>
          </div>
        </div>

        {/* Threshold Input Controls Form */}
        <form onSubmit={handleSaveThresholds} className="mt-5 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
            {/* Under-Speed Critical */}
            <div className="bg-slate-900/70 p-3 rounded-md border border-slate-700">
              <label
                htmlFor="threshold-under-critical"
                className="block text-xs font-medium text-rose-300 mb-1"
              >
                Batas Kritis Lambat
              </label>
              <div className="relative">
                <input
                  id="threshold-under-critical"
                  type="number"
                  min="1"
                  max="50"
                  disabled={!canEdit}
                  value={thresholds.under_critical}
                  onChange={(e) =>
                    setThresholds((prev) => ({
                      ...prev,
                      under_critical: parseInt(e.target.value, 10) || 0,
                    }))
                  }
                  className="w-full bg-slate-950 border border-rose-500/40 rounded px-2.5 py-1.5 pr-12 text-sm text-slate-100 focus:outline-none focus:ring-1 focus:ring-rose-400 disabled:opacity-60"
                  required
                />
                <span className="absolute right-2 top-1.5 text-xs text-slate-400 pointer-events-none">
                  cpm
                </span>
              </div>
              <span className="text-[10px] text-slate-400 mt-1 block">Default: 15 CPM</span>
            </div>

            {/* Under-Speed Warning */}
            <div className="bg-slate-900/70 p-3 rounded-md border border-slate-700">
              <label
                htmlFor="threshold-under-warning"
                className="block text-xs font-medium text-amber-300 mb-1"
              >
                Batas Peringatan Lambat
              </label>
              <div className="relative">
                <input
                  id="threshold-under-warning"
                  type="number"
                  min="5"
                  max="80"
                  disabled={!canEdit}
                  value={thresholds.under_warning}
                  onChange={(e) =>
                    setThresholds((prev) => ({
                      ...prev,
                      under_warning: parseInt(e.target.value, 10) || 0,
                    }))
                  }
                  className="w-full bg-slate-950 border border-amber-500/40 rounded px-2.5 py-1.5 pr-12 text-sm text-slate-100 focus:outline-none focus:ring-1 focus:ring-amber-400 disabled:opacity-60"
                  required
                />
                <span className="absolute right-2 top-1.5 text-xs text-slate-400 pointer-events-none">
                  cpm
                </span>
              </div>
              <span className="text-[10px] text-slate-400 mt-1 block">Default: 30 CPM</span>
            </div>

            {/* Over-Speed Warning */}
            <div className="bg-slate-900/70 p-3 rounded-md border border-slate-700">
              <label
                htmlFor="threshold-over-warning"
                className="block text-xs font-medium text-amber-300 mb-1"
              >
                Batas Peringatan Cepat
              </label>
              <div className="relative">
                <input
                  id="threshold-over-warning"
                  type="number"
                  min="40"
                  max="150"
                  disabled={!canEdit}
                  value={thresholds.over_warning}
                  onChange={(e) =>
                    setThresholds((prev) => ({
                      ...prev,
                      over_warning: parseInt(e.target.value, 10) || 0,
                    }))
                  }
                  className="w-full bg-slate-950 border border-amber-500/40 rounded px-2.5 py-1.5 pr-12 text-sm text-slate-100 focus:outline-none focus:ring-1 focus:ring-amber-400 disabled:opacity-60"
                  required
                />
                <span className="absolute right-2 top-1.5 text-xs text-slate-400 pointer-events-none">
                  cpm
                </span>
              </div>
              <span className="text-[10px] text-slate-400 mt-1 block">Default: 75 CPM</span>
            </div>

            {/* Over-Speed Critical */}
            <div className="bg-slate-900/70 p-3 rounded-md border border-slate-700">
              <label
                htmlFor="threshold-over-critical"
                className="block text-xs font-medium text-rose-300 mb-1"
              >
                Batas Kritis Cepat
              </label>
              <div className="relative">
                <input
                  id="threshold-over-critical"
                  type="number"
                  min="60"
                  max="200"
                  disabled={!canEdit}
                  value={thresholds.over_critical}
                  onChange={(e) =>
                    setThresholds((prev) => ({
                      ...prev,
                      over_critical: parseInt(e.target.value, 10) || 0,
                    }))
                  }
                  className="w-full bg-slate-950 border border-rose-500/40 rounded px-2.5 py-1.5 pr-12 text-sm text-slate-100 focus:outline-none focus:ring-1 focus:ring-rose-400 disabled:opacity-60"
                  required
                />
                <span className="absolute right-2 top-1.5 text-xs text-slate-400 pointer-events-none">
                  cpm
                </span>
              </div>
              <span className="text-[10px] text-slate-400 mt-1 block">Default: 90 CPM</span>
            </div>

            {/* Camera Heartbeat Timeout */}
            <div className="bg-slate-900/70 p-3 rounded-md border border-slate-700">
              <label
                htmlFor="threshold-heartbeat-timeout"
                className="block text-xs font-medium text-cyan-300 mb-1"
              >
                Camera Timeout
              </label>
              <div className="relative">
                <input
                  id="threshold-heartbeat-timeout"
                  type="number"
                  min="5"
                  max="300"
                  disabled={!canEdit}
                  value={thresholds.heartbeat_timeout}
                  onChange={(e) =>
                    setThresholds((prev) => ({
                      ...prev,
                      heartbeat_timeout: parseInt(e.target.value, 10) || 0,
                    }))
                  }
                  className="w-full bg-slate-950 border border-cyan-500/40 rounded px-2.5 py-1.5 pr-12 text-sm text-slate-100 focus:outline-none focus:ring-1 focus:ring-cyan-400 disabled:opacity-60"
                  required
                />
                <span className="absolute right-2 top-1.5 text-xs text-slate-400 pointer-events-none">
                  dtk
                </span>
              </div>
              <span className="text-[10px] text-slate-400 mt-1 block">Default: 60 Detik</span>
            </div>
          </div>

          {/* Form Actions Footer */}
          <div className="flex flex-wrap items-center justify-between pt-4 border-t border-slate-700 gap-3">
            <div className="text-xs text-slate-400 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-slate-400" />
              <span>
                Jika kamera tidak merespons dalam {thresholds.heartbeat_timeout} detik, status jalur
                otomatis berubah menjadi <span className="text-rose-400 font-semibold">OFFLINE</span>.
              </span>
            </div>

            <div className="flex items-center gap-2.5">
              <button
                type="button"
                onClick={handleResetThresholds}
                disabled={!canEdit || !isThresholdsDirty || isSavingThresholds}
                className="px-3.5 py-1.5 rounded-md text-xs font-medium text-slate-300 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed transition"
              >
                Reset Ambang Batas
              </button>

              <button
                type="submit"
                disabled={!canEdit || !isThresholdsDirty || isSavingThresholds}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-md text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50 disabled:cursor-not-allowed shadow transition focus:ring-2 focus:ring-emerald-400"
              >
                {isSavingThresholds ? (
                  <>
                    <RotateCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Menyimpan...</span>
                  </>
                ) : (
                  <>
                    <Save className="w-3.5 h-3.5" />
                    <span>Simpan Ambang Batas</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </form>
      </section>

      {/* Section 3: Role Permissions Matrix Reference Table */}
      <section
        aria-labelledby="section-role-matrix"
        className="bg-slate-800 border border-slate-700 rounded-lg p-5 sm:p-6 shadow-sm"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-700 gap-3">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-indigo-950/70 border border-indigo-500/30 rounded-md text-indigo-400">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <h3 id="section-role-matrix" className="text-lg font-bold text-slate-100">
                Matriks Wewenang & Hak Akses Pengguna (Role Permissions Matrix)
              </h3>
              <p className="text-xs text-slate-400">
                Tabel referensi kemampuan dan batasan tindakan tiap peran operasional sistem
              </p>
            </div>
          </div>

          {/* Current Role Tag */}
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-900 border border-slate-700 text-xs">
            <UserCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-slate-400">Peran Anda Saat Ini:</span>
            <span className="font-bold text-emerald-400 uppercase tracking-wide">{currentRole}</span>
          </div>
        </div>

        {/* Matrix Table */}
        <div className="mt-5 overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-700 bg-slate-900/60">
                <th
                  scope="col"
                  className="py-3 px-4 text-slate-300 font-semibold uppercase tracking-wider text-[11px]"
                >
                  Fitur / Modul Sistem
                </th>
                {/* Viewer Column */}
                <th
                  scope="col"
                  className={`py-3 px-3 text-center uppercase tracking-wider text-[11px] font-semibold transition ${
                    currentRole === "VIEWER"
                      ? "bg-slate-800 text-emerald-400 border-x-2 border-t-2 border-emerald-500/80 rounded-t"
                      : "text-slate-400"
                  }`}
                >
                  <div className="flex flex-col items-center">
                    <span>Viewer</span>
                    {currentRole === "VIEWER" && (
                      <span className="text-[9px] lowercase bg-emerald-500 text-slate-950 font-bold px-1.5 py-0.2 rounded-full mt-0.5">
                        aktif
                      </span>
                    )}
                  </div>
                </th>
                {/* Operator Column */}
                <th
                  scope="col"
                  className={`py-3 px-3 text-center uppercase tracking-wider text-[11px] font-semibold transition ${
                    currentRole === "OPERATOR"
                      ? "bg-slate-800 text-emerald-400 border-x-2 border-t-2 border-emerald-500/80 rounded-t"
                      : "text-slate-400"
                  }`}
                >
                  <div className="flex flex-col items-center">
                    <span>Operator</span>
                    {currentRole === "OPERATOR" && (
                      <span className="text-[9px] lowercase bg-emerald-500 text-slate-950 font-bold px-1.5 py-0.2 rounded-full mt-0.5">
                        aktif
                      </span>
                    )}
                  </div>
                </th>
                {/* Manager Column */}
                <th
                  scope="col"
                  className={`py-3 px-3 text-center uppercase tracking-wider text-[11px] font-semibold transition ${
                    currentRole === "MANAGER"
                      ? "bg-slate-800 text-emerald-400 border-x-2 border-t-2 border-emerald-500/80 rounded-t"
                      : "text-slate-400"
                  }`}
                >
                  <div className="flex flex-col items-center">
                    <span>Manager</span>
                    {currentRole === "MANAGER" && (
                      <span className="text-[9px] lowercase bg-emerald-500 text-slate-950 font-bold px-1.5 py-0.2 rounded-full mt-0.5">
                        aktif
                      </span>
                    )}
                  </div>
                </th>
                {/* Admin Column */}
                <th
                  scope="col"
                  className={`py-3 px-3 text-center uppercase tracking-wider text-[11px] font-semibold transition ${
                    currentRole === "ADMIN"
                      ? "bg-slate-800 text-emerald-400 border-x-2 border-t-2 border-emerald-500/80 rounded-t"
                      : "text-slate-400"
                  }`}
                >
                  <div className="flex flex-col items-center">
                    <span>Admin</span>
                    {currentRole === "ADMIN" && (
                      <span className="text-[9px] lowercase bg-emerald-500 text-slate-950 font-bold px-1.5 py-0.2 rounded-full mt-0.5">
                        aktif
                      </span>
                    )}
                  </div>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/60">
              {PERMISSIONS_MATRIX.map((row, idx) => (
                <tr
                  key={row.id}
                  className={`hover:bg-slate-750 transition ${
                    idx % 2 === 0 ? "bg-slate-800/40" : "bg-slate-850/20"
                  }`}
                >
                  {/* Module & Description */}
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-slate-200">{row.feature}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700 text-slate-400 font-medium">
                        {row.category}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">{row.description}</p>
                  </td>

                  {/* Viewer */}
                  <td
                    className={`py-3 px-3 text-center ${
                      currentRole === "VIEWER" ? "bg-slate-800/80 border-x-2 border-emerald-500/50" : ""
                    }`}
                  >
                    <PermissionBadge level={row.viewer.level} label={row.viewer.label} />
                  </td>

                  {/* Operator */}
                  <td
                    className={`py-3 px-3 text-center ${
                      currentRole === "OPERATOR" ? "bg-slate-800/80 border-x-2 border-emerald-500/50" : ""
                    }`}
                  >
                    <PermissionBadge level={row.operator.level} label={row.operator.label} />
                  </td>

                  {/* Manager */}
                  <td
                    className={`py-3 px-3 text-center ${
                      currentRole === "MANAGER" ? "bg-slate-800/80 border-x-2 border-emerald-500/50" : ""
                    }`}
                  >
                    <PermissionBadge level={row.manager.level} label={row.manager.label} />
                  </td>

                  {/* Admin */}
                  <td
                    className={`py-3 px-3 text-center ${
                      currentRole === "ADMIN" ? "bg-slate-800/80 border-x-2 border-emerald-500/50" : ""
                    }`}
                  >
                    <PermissionBadge level={row.admin.level} label={row.admin.label} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Legend */}
        <div className="mt-4 pt-3 border-t border-slate-700/80 flex flex-wrap items-center gap-4 text-[11px] text-slate-400">
          <span className="font-medium text-slate-300">Keterangan:</span>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-slate-600 inline-block" />
            <span>Terkunci / Tanpa Akses</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 inline-block" />
            <span>Lihat / Monitoring</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-blue-400 inline-block" />
            <span>Aksi Operasional</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-400 inline-block" />
            <span>Konfigurasi & Manajemen</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 inline-block" />
            <span>Akses Penuh / Superuser</span>
          </div>
        </div>
      </section>
    </div>
  );
}

interface PermissionBadgeProps {
  level: PermissionLevel;
  label: string;
}

function PermissionBadge({ level, label }: PermissionBadgeProps) {
  switch (level) {
    case "none":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-slate-900 text-slate-500 border border-slate-700/60">
          <X className="w-3 h-3 text-slate-500" />
          <span>{label}</span>
        </span>
      );
    case "view":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-cyan-950/60 text-cyan-300 border border-cyan-500/30">
          <Eye className="w-3 h-3 text-cyan-400" />
          <span>{label}</span>
        </span>
      );
    case "operate":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-blue-950/60 text-blue-300 border border-blue-500/30">
          <Check className="w-3 h-3 text-blue-400" />
          <span>{label}</span>
        </span>
      );
    case "manage":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-amber-950/60 text-amber-300 border border-amber-500/30">
          <Sliders className="w-3 h-3 text-amber-400" />
          <span>{label}</span>
        </span>
      );
    case "full":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-950/60 text-emerald-300 border border-emerald-500/30">
          <ShieldCheck className="w-3 h-3 text-emerald-400" />
          <span>{label}</span>
        </span>
      );
    default:
      return <span>-</span>;
  }
}

export default SettingsView;
