import { Menu } from "lucide-react";
import { useLocation } from "react-router-dom";
import { navigationConfig } from "@/config/navigation";

interface HeaderProps {
  onOpenSidebar: () => void;
}

export function Header({ onOpenSidebar }: HeaderProps) {
  const location = useLocation();
  const currentNav = navigationConfig.find((item) =>
    item.path === "/" ? location.pathname === "/" : location.pathname.startsWith(item.path)
  );

  return (
    <header className="h-14 border-b border-slate-200 bg-white px-4 sm:px-6 flex items-center justify-between sticky top-0 z-30">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onOpenSidebar}
          aria-label="Buka navigasi menu"
          className="p-1.5 rounded-md text-slate-600 hover:bg-slate-100 lg:hidden"
        >
          <Menu className="w-5 h-5" />
        </button>
        <div className="text-sm font-semibold text-slate-800">
          {currentNav?.label || "Poultry Counter"}
        </div>
      </div>
      {/* Intentionally minimal right area: no role selection, no status badge */}
      <div className="flex items-center gap-2" />
    </header>
  );
}
