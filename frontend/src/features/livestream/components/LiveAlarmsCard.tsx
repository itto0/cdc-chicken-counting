import { useEffect, useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { alarmsApi } from "@/features/alarms";
import type { AlarmDTO } from "@/types";

interface LiveAlarmsCardProps {
  lineId: string;
}

export function LiveAlarmsCard({ lineId }: LiveAlarmsCardProps) {
  const [alarms, setAlarms] = useState<AlarmDTO[]>([]);

  useEffect(() => {
    let isMounted = true;

    const fetchAlarms = () => {
      if (!lineId) return;
      alarmsApi
        .list(lineId)
        .then((res) => {
          if (!isMounted) return;
          // Filter out resolved alarms
          const active = (res || []).filter((a) => a.status !== "RESOLVED");
          // Take top 4 most recent
          setAlarms(active.slice(0, 4));
        })
        .catch(() => {
          // Ignore fetch errors silently
        });
    };

    fetchAlarms();
    const interval = setInterval(fetchAlarms, 10000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [lineId]);

  const formatTimestamp = (isoStr: string) => {
    if (!isoStr) return "-";
    try {
      const dt = new Date(isoStr);
      if (isNaN(dt.getTime())) return isoStr;
      const pad = (n: number) => String(n).padStart(2, "0");
      return `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())} ${pad(dt.getHours())}:${pad(dt.getMinutes())}:${pad(dt.getSeconds())}`;
    } catch {
      return isoStr;
    }
  };

  return (
    <Card className="rounded-2xl border-slate-200/80 shadow-xs bg-white">
      <CardHeader className="p-4 pb-2">
        <CardTitle className="text-sm font-semibold text-slate-800">
          Alarm &amp; Notifikasi
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 pt-2">
        {alarms.length === 0 ? (
          <div className="flex items-center gap-2.5 py-4 px-3 rounded-xl bg-slate-50 text-slate-500 text-xs">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>Tidak ada alarm aktif pada lini ini</span>
          </div>
        ) : (
          <div className="space-y-3">
            {alarms.map((alarm) => {
              const isCritical = (alarm.severity || "").toUpperCase() === "CRITICAL";
              return (
                <div
                  key={alarm.id}
                  className="flex items-start justify-between gap-3 text-xs"
                >
                  <div className="flex items-start gap-2 min-w-0">
                    <span
                      className={`w-2 h-2 rounded-full mt-1 shrink-0 ${
                        isCritical ? "bg-rose-500 ring-2 ring-rose-100" : "bg-amber-500 ring-2 ring-amber-100"
                      }`}
                      aria-hidden="true"
                    />
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span
                          className={`font-bold ${
                            isCritical ? "text-rose-600" : "text-amber-600"
                          }`}
                        >
                          {isCritical ? "Kritis" : "Peringatan"}
                        </span>
                      </div>
                      <p className="text-slate-700 font-medium truncate mt-0.5">
                        {alarm.message}
                      </p>
                      <span className="text-[11px] text-slate-400 font-mono mt-0.5 block">
                        {formatTimestamp(alarm.opened_at)}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
