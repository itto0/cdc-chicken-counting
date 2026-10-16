import { useState, useEffect, useCallback } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { LineSelector } from "@/components/layout/LineSelector";
import { StatusBadge } from "@/components/common/StatusBadge";
import { useAppContext } from "@/context/AppContext";
import { alarmsApi } from "../api/alarms.api";
import { AlarmsTable } from "../components/AlarmsTable";
import type { AlarmDTO } from "@/types";

export default function AlarmPage() {
  const { currentLineId, isConnected } = useAppContext();
  const [alarms, setAlarms] = useState<AlarmDTO[]>([]);

  const fetchAlarms = useCallback(() => {
    let isCurrent = true;
    alarmsApi
      .list(currentLineId)
      .then((data) => {
        if (isCurrent) setAlarms(data || []);
      })
      .catch(() => {
        if (isCurrent) {
          // fallback sample
          setAlarms([
            {
              id: 1,
              line_id: currentLineId,
              alarm_type: "LOW_SPEED",
              severity: "MEDIUM",
              message: "Kecepatan di bawah target (84 cpm < 120 cpm)",
              status: "ACTIVE",
              opened_at: new Date().toISOString(),
              ack_at: null,
              resolved_at: null,
            },
          ]);
        }
      });

    return () => {
      isCurrent = false;
    };
  }, [currentLineId]);

  useEffect(() => {
    const cleanup = fetchAlarms();
    return cleanup;
  }, [fetchAlarms]);

  const handleAcknowledge = async (id: number) => {
    try {
      await alarmsApi.patch(id, { status: "ACKNOWLEDGED" });
      fetchAlarms();
    } catch {
      setAlarms((prev) =>
        prev.map((a) => (a.id === id ? { ...a, status: "ACKNOWLEDGED" } : a))
      );
    }
  };

  const handleResolve = async (id: number) => {
    try {
      await alarmsApi.patch(id, { status: "RESOLVED" });
      fetchAlarms();
    } catch {
      setAlarms((prev) =>
        prev.map((a) => (a.id === id ? { ...a, status: "RESOLVED" } : a))
      );
    }
  };

  return (
    <div>
      <PageHeader
        title="Daftar Alarm & Anomali"
        description="Peringatan kecepatan rendah, pemutusan kamera, dan anomali deteksi"
      >
        <StatusBadge isConnected={isConnected} />
        <LineSelector />
      </PageHeader>

      <AlarmsTable
        alarms={alarms}
        onAcknowledge={handleAcknowledge}
        onResolve={handleResolve}
      />
    </div>
  );
}
