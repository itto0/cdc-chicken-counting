import type {
  AlarmDTO,
  AlarmPatchPayload,
  AlarmQueryParams,
  CountQueryParams,
  LineCountsResponse,
  LineDetailDTO,
  LineItem,
  LineSummaryResponse,
  LineUpdatePayload,
  LoginResponse,
  UserDTO,
} from "../types";

const TOKEN_KEY = "lihat_auth_token";
let inMemoryToken: string | null = null;

/**
 * Resolve base API URL from environment or default to local dev backend.
 */
export function getBaseUrl(): string {
  if (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL !== undefined) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  if (typeof process !== "undefined" && process.env?.VITE_API_BASE_URL) {
    return process.env.VITE_API_BASE_URL;
  }
  return "http://localhost:8000";
}

/**
 * Retrieve current Bearer token from memory or localStorage.
 */
export function getAuthToken(): string | null {
  if (inMemoryToken) {
    return inMemoryToken;
  }
  if (typeof window !== "undefined" && window.localStorage) {
    try {
      const stored = window.localStorage.getItem(TOKEN_KEY);
      if (stored) {
        inMemoryToken = stored;
        return stored;
      }
    } catch {
      // ignore storage access issues
    }
  }
  return null;
}

/**
 * Store Bearer token in memory and localStorage.
 */
export function setAuthToken(token: string | null): void {
  inMemoryToken = token;
  if (typeof window !== "undefined" && window.localStorage) {
    try {
      if (token) {
        window.localStorage.setItem(TOKEN_KEY, token);
      } else {
        window.localStorage.removeItem(TOKEN_KEY);
      }
    } catch {
      // ignore storage access issues
    }
  }
}

/**
 * Clear stored auth token.
 */
export function logout(): void {
  setAuthToken(null);
}

/**
 * Generic JSON fetch client with Bearer auth headers and error handling.
 */
export async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const base = getBaseUrl().replace(/\/$/, "");
  const normalizedEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const url = endpoint.startsWith("http://") || endpoint.startsWith("https://")
    ? endpoint
    : `${base}${normalizedEndpoint}`;

  const headers = new Headers(options.headers || {});
  if (options.body && !headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  const token = getAuthToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = response.statusText;
    try {
      const errorJson = await response.json();
      if (errorJson && typeof errorJson === "object") {
        if ("detail" in errorJson && typeof errorJson.detail === "string") {
          errorDetail = errorJson.detail;
        } else if ("message" in errorJson && typeof errorJson.message === "string") {
          errorDetail = errorJson.message;
        } else {
          errorDetail = JSON.stringify(errorJson);
        }
      }
    } catch {
      // fallback to statusText
    }
    const error = new Error(`API Error ${response.status}: ${errorDetail}`);
    (error as Error & { status?: number }).status = response.status;
    throw error;
  }

  return response.json() as Promise<T>;
}

/**
 * Fetch all configured production lines with live status summary.
 */
export async function getLines(): Promise<LineItem[]> {
  return request<LineItem[]>("/api/v1/lines");
}

/**
 * Fetch operational summary metrics for a specific line.
 */
export async function getLineSummary(
  lineId: string,
  period?: "today" | "shift" | "week" | string
): Promise<LineSummaryResponse> {
  const params = period ? `?period=${encodeURIComponent(period)}` : "";
  return request<LineSummaryResponse>(`/api/v1/lines/${encodeURIComponent(lineId)}/summary${params}`);
}

/**
 * Fetch counts history and aggregate buckets for a line.
 */
export async function getLineCounts(
  lineId: string,
  params?: CountQueryParams
): Promise<LineCountsResponse> {
  const query = new URLSearchParams();
  if (params?.from) query.append("from", params.from);
  if (params?.to) query.append("to", params.to);
  if (params?.granularity) query.append("granularity", params.granularity);
  if (params?.page !== undefined) query.append("page", String(params.page));
  if (params?.limit !== undefined) query.append("limit", String(params.limit));

  const qs = query.toString();
  return request<LineCountsResponse>(
    `/api/v1/lines/${encodeURIComponent(lineId)}/counts${qs ? `?${qs}` : ""}`
  );
}

/**
 * Fetch alarm incidents with optional filtering.
 */
export async function getAlarms(params?: AlarmQueryParams): Promise<AlarmDTO[]> {
  const query = new URLSearchParams();
  if (params?.line_id) query.append("line_id", params.line_id);
  if (params?.status) query.append("status", params.status);
  if (params?.severity) query.append("severity", params.severity);

  const qs = query.toString();
  return request<AlarmDTO[]>(`/api/v1/alarms${qs ? `?${qs}` : ""}`);
}

/**
 * Acknowledge or resolve an alarm incident.
 */
export async function patchAlarm(
  alarmId: number,
  payload: AlarmPatchPayload
): Promise<AlarmDTO> {
  return request<AlarmDTO>(`/api/v1/alarms/${alarmId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

/**
 * Update line parameters (name, target, active state).
 */
export async function updateLine(
  lineId: string,
  payload: LineUpdatePayload
): Promise<LineDetailDTO> {
  return request<LineDetailDTO>(`/api/v1/lines/${encodeURIComponent(lineId)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

/**
 * Authenticate user and persist access token.
 */
export async function login(username: string, password: string): Promise<LoginResponse> {
  const data = await request<LoginResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  if (data?.access_token) {
    setAuthToken(data.access_token);
  }
  return data;
}

/**
 * Fetch current authenticated user profile.
 */
export async function getMe(): Promise<UserDTO> {
  return request<UserDTO>("/api/v1/auth/me");
}

/**
 * Generate full download URL for Excel or PDF reports.
 */
export function getExportUrl(
  lineId: string,
  format: "xlsx" | "pdf" = "xlsx",
  fromTime?: string,
  toTime?: string
): string {
  const base = getBaseUrl().replace(/\/$/, "");
  const params = new URLSearchParams();
  params.append("line_id", lineId);
  params.append("format", format);
  if (fromTime) {
    params.append("start_time", fromTime);
  }
  if (toTime) {
    params.append("end_time", toTime);
  }
  return `${base}/api/v1/reports/export?${params.toString()}`;
}

/**
 * Generate live MJPEG preview stream URL for video player element.
 */
export function getPreviewUrl(lineId: string): string {
  const base = getBaseUrl().replace(/\/$/, "");
  return `${base}/api/v1/lines/${encodeURIComponent(lineId)}/preview`;
}

/**
 * Generate SSE live telemetry stream URL.
 */
export function getLiveStreamUrl(lineId: string): string {
  const base = getBaseUrl().replace(/\/$/, "");
  return `${base}/api/v1/lines/${encodeURIComponent(lineId)}/live`;
}

export const apiClient = {
  getBaseUrl,
  getAuthToken,
  setAuthToken,
  logout,
  request,
  getLines,
  getLineSummary,
  getLineCounts,
  getAlarms,
  patchAlarm,
  updateLine,
  login,
  getMe,
  getExportUrl,
  getPreviewUrl,
  getLiveStreamUrl,
};

export default apiClient;
