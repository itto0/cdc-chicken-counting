export type UserRole = "ADMIN" | "MANAGER" | "OPERATOR" | "VIEWER";

export interface Line {
  id: string;
  name: string;
  daily_target: number;
  video_url?: string | null;
  line_coords?: string | null;
  line_direction?: string;
  is_active?: boolean;
  status?: string;
  last_ping?: string | null;
  total_today?: number;
}

export interface CreateLinePayload {
  id: string;
  name: string;
  daily_target: number;
  video_url?: string;
  line_coords?: string;
  line_direction?: string;
  is_active?: boolean;
}

export interface UpdateLinePayload {
  name?: string;
  daily_target?: number;
  video_url?: string | null;
  line_coords?: string | null;
  line_direction?: string;
  is_active?: boolean;
}

export type LineItem = Line;
export type LineDetailDTO = Line;
export type LineUpdatePayload = UpdateLinePayload;

export interface LineSummaryResponse {
  line_id: string;
  period: string;
  total_count: number;
  target_count: number;
  target_attainment_pct: number;
  current_speed_cpm: number;
  target_speed_cpm: number;
  active_alarms_count: number;
  camera_status: "online" | "offline" | "degraded" | string;
  last_event_time: string | null;
  fps: number;
  latency_p95_ms: number;
  detection_accuracy_pct?: number;
}

export interface AggregateItemDTO {
  bucket: string;
  count: number;
  rate_per_min: number;
  status: string;
}

export interface CountEventDTO {
  id: number;
  track_id: number;
  ts_utc: string;
  confidence: number;
}

export interface PaginationMeta {
  total: number;
  page: number;
  limit: number;
}

export interface LineCountsResponse {
  line_id: string;
  aggregates: AggregateItemDTO[];
  events: CountEventDTO[];
  pagination: PaginationMeta;
}

export type CountsHistoryResponse = LineCountsResponse;

export interface CountQueryParams {
  from?: string;
  to?: string;
  from_time?: string;
  to_time?: string;
  granularity?: "minute" | "hourly" | "daily" | string;
  page?: number;
  limit?: number;
}

export interface UserDTO {
  id: number;
  username: string;
  role: string | UserRole;
  is_active: boolean;
}

export type UserProfile = UserDTO;

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserDTO;
}

export interface AlarmDTO {
  id: number;
  line_id: string;
  alarm_type: string;
  severity: string;
  message: string;
  status: string;
  opened_at: string;
  ack_at: string | null;
  resolved_at: string | null;
}

export interface AlarmPatchPayload {
  status: "ACKNOWLEDGED" | "RESOLVED" | string;
  notes?: string;
  acknowledged_by?: string;
}

export interface AlarmQueryParams {
  line_id?: string;
  status?: string;
  severity?: string;
}

export interface LineSummary {
  line_id: string;
  total_today: number;
  avg_rate_per_min: number;
  target: number;
  attainment_pct: number;
  camera_status: "online" | "offline" | "degraded";
  detection_confidence_pct: number;
}

export interface AlarmItem {
  id: number;
  line_id: string;
  type: string;
  severity: "WARNING" | "CRITICAL" | "INFO";
  message: string;
  opened_at: string;
  status?: "OPEN" | "ACKNOWLEDGED" | "RESOLVED";
  ack_at?: string | null;
  resolved_at?: string | null;
}

export interface CountEventItem {
  id?: number;
  track_id: number;
  ts_utc: string;
  confidence: number;
  line_id?: string;
}

export interface CountAggregateItem {
  id?: number;
  line_id: string;
  window_start: string;
  window_end: string;
  count: number;
  rate_per_min: number;
  confidence_avg: number;
  status: "NORMAL" | "WARNING" | "CRITICAL";
}

export interface HealthStatus {
  line_id?: string;
  fps: number;
  latency_p95_ms: number;
  cpu_pct: number;
  mem_pct: number;
  stream_state: "ONLINE" | "OFFLINE" | "DEGRADED";
  model_name?: string;
  model_version?: string;
  timestamp?: string;
}

export type TabKey = "overview" | "live" | "alarms" | "reports" | "settings";
