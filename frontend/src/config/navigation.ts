import type { ComponentType } from "react";
import {
  LayoutDashboard,
  Network,
  Bell,
  FileText,
  Settings as SettingsIcon,
} from "lucide-react";

export interface NavigationItem {
  id: string;
  label: string;
  path: string;
  icon: ComponentType<{ className?: string }>;
}

export const navigationConfig: NavigationItem[] = [
  { id: "dashboard", label: "Dashboard", path: "/", icon: LayoutDashboard },
  { id: "lini-produksi", label: "Lini Produksi", path: "/lini-produksi", icon: Network },
  { id: "alarm", label: "Alarm", path: "/alarm", icon: Bell },
  { id: "laporan", label: "Laporan", path: "/laporan", icon: FileText },
  { id: "pengaturan", label: "Pengaturan", path: "/pengaturan", icon: SettingsIcon },
];
