import { http } from "@/lib/http";
import type { AlarmDTO, AlarmPatchPayload } from "@/types";

export const alarmsApi = {
  list: (lineId?: string) => {
    const query = lineId ? `?line_id=${encodeURIComponent(lineId)}` : "";
    return http<AlarmDTO[]>(`/api/v1/alarms${query}`);
  },
  patch: (id: number, payload: AlarmPatchPayload) =>
    http<AlarmDTO>(`/api/v1/alarms/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
};
