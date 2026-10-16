import { http } from "@/lib/http";
import type { LineCountsResponse, CountQueryParams } from "@/types";

export const reportsApi = {
  getCounts: (lineId: string, params: CountQueryParams = {}) => {
    const searchParams = new URLSearchParams();
    if (params.from) searchParams.set("from", params.from);
    if (params.to) searchParams.set("to", params.to);
    if (params.granularity) searchParams.set("granularity", params.granularity);
    const query = searchParams.toString();
    return http<LineCountsResponse>(
      `/api/v1/lines/${encodeURIComponent(lineId)}/counts${query ? `?${query}` : ""}`
    );
  },
};
