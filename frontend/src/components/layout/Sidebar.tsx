import { useEffect } from "react";
import { NavLink } from "react-router-dom";
import { navigationConfig } from "@/config/navigation";
import { cn } from "@/lib/utils";
import { useAuth } from "@/features/auth";
import ChickenLogo from "@/assets/logo/chicken_logo.png";

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const { user } = useAuth();

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

  const navItems = navigationConfig.filter((item) => {
    if (!item.requiredRole) return true;
    return (user?.role || "").toLowerCase() === item.requiredRole.toLowerCase();
  });

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
          "fixed top-0 bottom-0 left-0 z-50 flex flex-col w-60 bg-white border-r border-slate-200 transition-transform duration-200 ease-in-out lg:translate-x-0 lg:sticky lg:top-0 lg:h-screen lg:shrink-0",
          isOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Brand identity with chicken logo */}
        <div className="flex items-center h-20 px-6 border-b border-slate-100">
          <div className="flex items-center gap-3 text-slate-800">
            <img src={ChickenLogo} alt="" className="h-10 w-10" />
            <span className="sr-only">Lihat.id Poultry Counter</span>
          </div>
        </div>

        {/* Navigation list */}
        <nav aria-label="Menu Halaman" className="flex-1 px-3 py-6 space-y-1.5 overflow-y-auto">
          {navItems.map((item) => {
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
