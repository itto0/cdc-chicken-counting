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
