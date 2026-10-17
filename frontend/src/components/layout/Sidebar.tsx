import { useEffect } from "react";
import { NavLink } from "react-router-dom";
import { navigationConfig } from "@/config/navigation";
import { cn } from "@/lib/utils";

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

// Chicken outline SVG logo as shown in client mockup
function ChickenLogo({ className = "w-9 h-9" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 100 100"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {/* Sleek chicken outline path */}
      <path d="M 35 25 C 38 18 45 15 50 18 C 55 21 52 28 50 32 C 65 32 80 42 82 58 C 84 72 72 85 55 85 C 38 85 24 72 25 55 C 26 42 32 35 38 28 Z" />
      <path d="M 48 24 L 58 24" />
      <circle cx="43" cy="24" r="2.5" fill="currentColor" stroke="none" />
      <path d="M 28 56 C 35 52 45 54 52 62" />
      <path d="M 38 85 L 34 94" />
      <path d="M 50 85 L 50 94" />
    </svg>
  );
}

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  return (
    <>
      {isOpen && (
        <div
          aria-hidden="true"
          className="fixed inset-0 z-40 bg-slate-900/30 backdrop-blur-sm lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        aria-label="Navigasi Utama"
        className={cn(
          "fixed top-0 bottom-0 left-0 z-50 flex flex-col w-60 bg-white border-r border-slate-200 transition-transform duration-200 ease-in-out lg:translate-x-0 lg:static lg:z-auto",
          isOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Brand identity with chicken logo */}
        <div className="flex items-center h-20 px-6 border-b border-slate-100">
          <div className="flex items-center gap-3 text-slate-800">
            <ChickenLogo className="w-10 h-10 text-slate-700" />
            <span className="sr-only">Lihat.id Poultry Counter</span>
          </div>
        </div>

        {/* Navigation list */}
        <nav aria-label="Menu Halaman" className="flex-1 px-3 py-6 space-y-1.5 overflow-y-auto">
          {navigationConfig.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.id}
                to={item.path}
                end={item.path === "/"}
                onClick={onClose}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3.5 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors",
                    isActive
                      ? "bg-slate-100 text-slate-900 font-semibold"
                      : "text-slate-500 hover:bg-slate-50 hover:text-slate-900"
                  )
                }
              >
                <Icon className="w-4 h-4" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>
      </aside>
    </>
  );
}
