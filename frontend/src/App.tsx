import { useState } from "react";
import type { ComponentType } from "react";
import {
  LayoutDashboard,
  Radio,
  AlertTriangle,
  FileText,
  Settings as SettingsIcon,
  Layers,
  UserCheck,
} from "lucide-react";
import type { TabKey, UserRole, LineSummary } from "./types";
import { AppProvider, useAppContext } from "./context/AppContext";
import { OverviewView } from "./components/OverviewView";
import { LiveStreamView } from "./components/views/LiveStreamView";
import { AlarmsView } from "./components/views/AlarmsView";

interface NavTab {
  key: TabKey;
  label: string;
  icon: ComponentType<{ className?: string }>;
}

const TABS: NavTab[] = [
  { key: "overview", label: "Overview", icon: LayoutDashboard },
  { key: "live", label: "Live Stream", icon: Radio },
  { key: "alarms", label: "Alarms", icon: AlertTriangle },
  { key: "reports", label: "Reports", icon: FileText },
  { key: "settings", label: "Settings", icon: SettingsIcon },
];

const ROLES: UserRole[] = ["ADMIN", "MANAGER", "OPERATOR", "VIEWER"];

function DashboardContent() {
  const { currentLineId, setLineId, currentRole, setRole, lines, isConnected } = useAppContext();
  const [activeTab, setActiveTab] = useState<TabKey>("overview");

  const currentLine = lines.find((l) => l.id === currentLineId) || lines[0];

  const summary: LineSummary = {
    line_id: currentLineId,
    total_today: currentLine?.total_today ?? 48320,
    avg_rate_per_min: 118,
    target: currentLine?.daily_target ?? 62000,
    attainment_pct:
      currentLine && currentLine.daily_target > 0
        ? Math.round(((currentLine.total_today || 0) / currentLine.daily_target) * 1000) / 10
        : 0.0,
    camera_status: currentLine?.status ?? "online",
    detection_confidence_pct: 98.4,
  };

  return (
    <div className="min-h-screen bg-slate-900 text-white flex flex-col font-sans">
      <header className="bg-slate-800 border-b border-slate-700 px-4 sm:px-6 py-3.5 flex flex-wrap justify-between items-center gap-4">
        {/* Left: Brand title & Live connection indicator */}
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold tracking-tight text-emerald-400">
            Lihat.id <span className="text-slate-400 font-normal">· Poultry Counter</span>
          </h1>

          {/* Live Connection Pulse Badge */}
          <div
            className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold tracking-wide border transition ${
              isConnected
                ? "bg-emerald-950/80 border-emerald-500/40 text-emerald-400"
                : "bg-amber-950/80 border-amber-500/40 text-amber-400"
            }`}
            role="status"
            aria-label={isConnected ? "Connection status: Online" : "Connection status: Offline"}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                isConnected ? "bg-emerald-400 animate-pulse" : "bg-amber-400"
              }`}
            />
            <span>{isConnected ? "LIVE" : "OFFLINE"}</span>
          </div>
        </div>

        {/* Right / Center Controls: Line Selector, Role Switcher & Nav Tabs */}
        <div className="flex flex-wrap items-center gap-3 md:gap-4">
          {/* Line Selector Dropdown */}
          <div className="flex items-center gap-1.5">
            <label
              htmlFor="line-select"
              className="text-xs font-medium text-slate-400 flex items-center gap-1"
            >
              <Layers className="w-3.5 h-3.5 text-slate-400" />
              <span className="hidden sm:inline">Line:</span>
            </label>
            <select
              id="line-select"
              aria-label="Select Production Line"
              value={currentLineId}
              onChange={(e) => setLineId(e.target.value)}
              className="bg-slate-700 hover:bg-slate-600 border border-slate-600 text-slate-100 text-xs sm:text-sm rounded-md px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-emerald-500 cursor-pointer transition font-medium"
            >
              {lines.map((line) => (
                <option key={line.id} value={line.id} className="bg-slate-800 text-slate-100">
                  {line.name} ({line.status})
                </option>
              ))}
            </select>
          </div>

          {/* Role Switcher Pills */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-medium text-slate-400 hidden sm:flex items-center gap-1">
              <UserCheck className="w-3.5 h-3.5 text-slate-400" />
              <span>Role:</span>
            </span>
            <div
              className="flex items-center gap-0.5 sm:gap-1 bg-slate-900/80 p-0.5 sm:p-1 rounded-md border border-slate-700/80"
              role="radiogroup"
              aria-label="User Role Switcher"
            >
              {ROLES.map((role) => {
                const isSelected = currentRole === role;
                return (
                  <button
                    key={role}
                    type="button"
                    role="radio"
                    aria-checked={isSelected}
                    onClick={() => setRole(role)}
                    className={`px-2 py-1 text-[11px] sm:text-xs font-semibold rounded transition ${
                      isSelected
                        ? "bg-emerald-600 text-white shadow-sm"
                        : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
                    }`}
                  >
                    {role}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="flex items-center gap-1 sm:gap-1.5 border-l border-slate-700 pl-3">
            {TABS.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.key;
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs sm:text-sm font-medium transition ${
                    isActive
                      ? "bg-emerald-600 text-white shadow-sm"
                      : "bg-slate-700 text-slate-300 hover:bg-slate-600 hover:text-white"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span className="hidden md:inline">{tab.label}</span>
                </button>
              );
            })}
          </nav>
        </div>
      </header>

      <main className="flex-1 p-6 max-w-7xl w-full mx-auto">
        {activeTab === "overview" ? (
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-2xl font-bold tracking-tight text-slate-100">
                Ringkasan Hari Ini
              </h2>
              <span className="text-xs text-slate-400">
                Dashboard Operasional & Pemantauan Kuota
              </span>
            </div>
            <OverviewView summary={summary} onNavigateTab={setActiveTab} />
          </div>
        ) : activeTab === "live" ? (
          <div>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-2xl font-bold tracking-tight text-slate-100">
                  Umpan Video & Telemetri Langsung
                </h2>
                <span className="text-xs text-slate-400">
                  Streaming MJPEG Kamera Real-time & Evaluator Kecepatan Konveyor
                </span>
              </div>
            </div>
            <LiveStreamView />
          </div>
        ) : activeTab === "alarms" ? (
          <div>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-2xl font-bold tracking-tight text-slate-100">
                  Manajemen Alarm & Insiden
                </h2>
                <span className="text-xs text-slate-400">
                  Pemantauan status bahaya, pengakuan insiden, dan catatan penyelesaian operasional
                </span>
              </div>
            </div>
            <AlarmsView />
          </div>
        ) : (
          <div>
            <h2 className="text-2xl font-semibold mb-4 capitalize">{activeTab} View</h2>
            <div className="p-6 bg-slate-800 rounded-lg border border-slate-700 text-slate-300 shadow">
              Ready for {activeTab} view components.
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export function App() {
  return (
    <AppProvider>
      <DashboardContent />
    </AppProvider>
  );
}

export default App;
