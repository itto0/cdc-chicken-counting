import { useState, useEffect } from "react";
import { Menu, Bell, User } from "lucide-react";
import { Link } from "react-router-dom";
import { alarmsApi } from "@/features/alarms";

interface HeaderProps {
  onOpenSidebar: () => void;
}

export function Header({ onOpenSidebar }: HeaderProps) {
  const [activeCount, setActiveCount] = useState(0);

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

  return (
    <header className="h-16 bg-white px-4 sm:px-8 flex items-center justify-between sticky top-0 z-30">
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

      <div className="flex items-center gap-4">
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

        {/* Operator Profile Badge */}
        <div className="flex items-center gap-2.5 bg-slate-900 text-white pl-4 pr-1.5 py-1.5 rounded-full text-xs font-medium shadow-sm">
          <span>Operator Lapangan</span>
          <div className="w-7 h-7 rounded-full bg-slate-700 flex items-center justify-center text-slate-200">
            <User className="w-4 h-4" />
          </div>
        </div>
      </div>
    </header>
  );
}
