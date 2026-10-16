import { http } from "@/lib/http";
import type { LineSummaryResponse, LineCountsResponse, CountQueryParams } from "@/types";

export const overviewApi = {
  getSummary: (lineId: string, period: string = "today") =>
    http<LineSummaryResponse>(`/api/v1/lines/${lineId}/summary?period=${period}`),
  getCounts: (lineId: string, params: CountQueryParams = {}) => {
    const searchParams = new URLSearchParams();
    if (params.from) searchParams.set("from", params.from);
    if (params.to) searchParams.set("to", params.to);
    if (params.granularity) searchParams.set("granularity", params.granularity);
    const query = searchParams.toString();
    return http<LineCountsResponse>(`/api/v1/lines/${lineId}/counts${query ? `?${query}` : ""}`);
  },
};
