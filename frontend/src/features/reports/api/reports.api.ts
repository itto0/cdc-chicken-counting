import { http, getAuthToken } from "@/lib/http";
import { env } from "@/config/env";
import type { LineCountsResponse, CountQueryParams } from "@/types";

export interface DownloadReportParams {
  lineId?: string;
  format: "xlsx" | "pdf";
  startTime?: string;
  endTime?: string;
}

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

  downloadReport: async ({ lineId, format, startTime, endTime }: DownloadReportParams): Promise<void> => {
    const searchParams = new URLSearchParams();
    if (lineId && lineId !== "all") searchParams.set("line_id", lineId);
    else searchParams.set("line_id", "all");
    searchParams.set("format", format);
    if (startTime) searchParams.set("start_time", startTime);
    if (endTime) searchParams.set("end_time", endTime);

    const base = env.API_BASE_URL.replace(/\/$/, "");
    const targetUrl = `${base}/api/v1/reports/export?${searchParams.toString()}`;

    const headers = new Headers();
    const token = getAuthToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    const res = await fetch(targetUrl, { headers });
    if (!res.ok) {
      throw new Error(`Gagal mengunduh laporan (${res.status} ${res.statusText})`);
    }

    const blob = await res.blob();
    const disposition = res.headers.get("content-disposition");
    let filename = `report_${lineId || "semua_lini"}.${format}`;
    if (disposition && disposition.includes("filename=")) {
      const match = disposition.match(/filename=["']?([^"';]+)["']?/);
      if (match && match[1]) {
        filename = match[1].trim();
      }
    }

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  },
};
