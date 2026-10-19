import { useState, useEffect } from "react";
import { Menu, Bell, User, LogOut } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { alarmsApi } from "@/features/alarms";
import { useAuth } from "@/features/auth";

interface HeaderProps {
  onOpenSidebar: () => void;
}

export function Header({ onOpenSidebar }: HeaderProps) {
  const [activeCount, setActiveCount] = useState(0);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    let isMounted = true;

    const fetchAlarms = () => {
      alarmsApi
        .list()
        .then((alarms) => {
          if (isMounted && Array.isArray(alarms)) {
            const count = alarms.filter((a) => a.status !== "RESOLVED").length;
            setActiveCount(count);
          }
        })
        .catch(() => {
          // Keep current state on error
        });
    };

    fetchAlarms();
    const interval = setInterval(fetchAlarms, 10000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  const isAdmin = (user?.role || "").toLowerCase() === "admin";

  return (
    <header className="h-16 bg-white px-4 sm:px-8 flex items-center justify-between sticky top-0 z-30 border-b border-slate-100">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onOpenSidebar}
          aria-label="Buka navigasi menu"
          className="p-1.5 rounded-lg text-slate-600 hover:bg-slate-100 lg:hidden"
        >
          <Menu className="w-5 h-5" />
        </button>
      </div>

      <div className="flex items-center gap-3 sm:gap-4">
        {/* Notification bell button */}
        <Link
          to="/alarm"
          aria-label="Lihat alarm"
          className="relative p-2 rounded-xl text-slate-600 hover:bg-slate-100 transition-colors border border-slate-200"
        >
          <Bell className="w-5 h-5" />
          {activeCount > 0 && (
            <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 bg-rose-500 text-white rounded-full text-[10px] font-bold flex items-center justify-center">
              {activeCount > 99 ? "99+" : activeCount}
            </span>
          )}
        </Link>

        {/* Dynamic User Profile Badge */}
        <div className="flex items-center gap-2 bg-slate-300 pl-3.5 pr-1.5 py-1.5 rounded-full text-xs font-medium shadow-sm">
          <div className="flex flex-col items-start leading-none pr-1">
            <span className="font-semibold">{user?.username || "Pengguna"}</span>
            <span className={`text-[10px] font-bold uppercase mt-0.5 ${isAdmin ? "text-indigo-400" : "text-emerald-400"}`}>
              {user?.role || "Operator"}
            </span>
          </div>
          <div className={`w-7 h-7 rounded-full flex items-center justify-center text-white ${isAdmin ? "bg-indigo-600" : "bg-emerald-600"}`}>
            <User className="w-3.5 h-3.5" />
          </div>
        </div>

        {/* Logout Button */}
        <button
          type="button"
          onClick={handleLogout}
          title="Keluar dari sistem"
          aria-label="Keluar dari sistem"
          className="p-2 rounded-xl text-slate-500 hover:text-rose-600 hover:bg-rose-50 border border-slate-200 transition-colors cursor-pointer"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}
