import { useState } from "react";
import type { ComponentType } from "react";
import {
  LayoutDashboard,
  Radio,
  AlertTriangle,
  FileText,
  Settings as SettingsIcon,
} from "lucide-react";
import { TabKey, LineSummary } from "./types";
import { OverviewView } from "./components/OverviewView";

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

export function App() {
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [summary] = useState<LineSummary>({
    line_id: "line-1",
    total_today: 48320,
    avg_rate_per_min: 118,
    target: 62000,
    attainment_pct: 77.9,
    camera_status: "online",
    detection_confidence_pct: 98.4,
  });

  return (
    <div className="min-h-screen bg-slate-900 text-white flex flex-col font-sans">
      <header className="bg-slate-800 border-b border-slate-700 px-6 py-4 flex flex-wrap justify-between items-center gap-4">
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 rounded-full bg-emerald-500 animate-pulse" />
          <h1 className="text-xl font-bold tracking-tight text-emerald-400">
            Lihat.id <span className="text-slate-400 font-normal">· Poultry Counter</span>
          </h1>
        </div>
        <nav className="flex items-center gap-2">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition ${
                  isActive
                    ? "bg-emerald-600 text-white shadow-sm"
                    : "bg-slate-700 text-slate-300 hover:bg-slate-600 hover:text-white"
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
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
            <OverviewView summary={summary} />
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

export default App;
