import { useEffect, useRef, useState, useCallback } from "react";
import { apiClient } from "../services/apiClient";

export type StreamStatus = "CONNECTING" | "CONNECTED" | "DISCONNECTED";

export interface LiveStreamState {
  status: StreamStatus;
  liveSpeed: number; // CPM (Chickens per minute)
  lastCountTime: string | null;
  fps: number;
  latencyMs: number;
  streamState: string;
  totalToday: number;
  reconnect: () => void;
}

export function useLiveStream(lineId: string): LiveStreamState {
  const [status, setStatus] = useState<StreamStatus>("CONNECTING");
  const [liveSpeed, setLiveSpeed] = useState<number>(0);
  const [lastCountTime, setLastCountTime] = useState<string | null>(null);
  const [fps, setFps] = useState<number>(0);
  const [latencyMs, setLatencyMs] = useState<number>(0);
  const [streamState, setStreamState] = useState<string>("OFFLINE");
  const [totalToday, setTotalToday] = useState<number>(0);

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const backoffDelayRef = useRef<number>(1000); // initial delay: 1000ms
  const isMountedRef = useRef<boolean>(true);

  // Exponential backoff configuration
  const INITIAL_DELAY_MS = 1000;
  const MAX_BACKOFF_DELAY_MS = 30000;
  const BACKOFF_MULTIPLIER = 2;

  const cleanup = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    cleanup();

    if (!lineId || typeof window === "undefined" || typeof EventSource === "undefined") {
      if (isMountedRef.current) {
        setStatus("DISCONNECTED");
        setStreamState("OFFLINE");
      }
      return;
    }

    if (isMountedRef.current) {
      setStatus("CONNECTING");
    }

    const streamUrl = apiClient.getLiveStreamUrl(lineId);
    let es: EventSource;

    try {
      es = new EventSource(streamUrl);
      eventSourceRef.current = es;
    } catch {
      if (isMountedRef.current) {
        setStatus("DISCONNECTED");
        setStreamState("OFFLINE");
      }
      return;
    }

    es.onopen = () => {
      if (!isMountedRef.current) return;
      setStatus("CONNECTED");
      setStreamState("ONLINE");
      backoffDelayRef.current = INITIAL_DELAY_MS; // Reset backoff delay on successful connection
    };

    es.onerror = () => {
      if (!isMountedRef.current) return;
      // Close current disconnected stream
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      setStatus("DISCONNECTED");
      setStreamState("OFFLINE");

      // Calculate next backoff delay
      const currentDelay = backoffDelayRef.current;
      backoffDelayRef.current = Math.min(
        currentDelay * BACKOFF_MULTIPLIER,
        MAX_BACKOFF_DELAY_MS
      );

      // Schedule reconnection attempt
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      reconnectTimerRef.current = setTimeout(() => {
        if (isMountedRef.current) {
          connect();
        }
      }, currentDelay);
    };

    const parsePayload = (event: MessageEvent) => {
      try {
        return typeof event.data === "string" ? JSON.parse(event.data) : event.data;
      } catch {
        return null;
      }
    };

    // Event: "status"
    es.addEventListener("status", (event: MessageEvent) => {
      if (!isMountedRef.current) return;
      const data = parsePayload(event);
      if (data) {
        setStatus("CONNECTED");
        if (data.status) {
          setStreamState(String(data.status));
        }
        if (typeof data.total_today === "number") {
          setTotalToday(data.total_today);
        }
      }
    });

    // Event: "count"
    es.addEventListener("count", (event: MessageEvent) => {
      if (!isMountedRef.current) return;
      const data = parsePayload(event);
      if (data) {
        if (typeof data.rate_per_min === "number") {
          setLiveSpeed(data.rate_per_min);
        } else if (typeof data.live_speed === "number") {
          setLiveSpeed(data.live_speed);
        }
        if (typeof data.total_today === "number") {
          setTotalToday(data.total_today);
        }
        const timeVal = data.ts_utc || data.timestamp || new Date().toISOString();
        setLastCountTime(timeVal);
      }
    });

    // Event: "aggregate"
    es.addEventListener("aggregate", (event: MessageEvent) => {
      if (!isMountedRef.current) return;
      const data = parsePayload(event);
      if (data) {
        if (typeof data.rate_per_min === "number") {
          setLiveSpeed(data.rate_per_min);
        }
        if (typeof data.total_today === "number") {
          setTotalToday(data.total_today);
        } else if (typeof data.count === "number") {
          setTotalToday((prev) => prev + data.count);
        }
        if (data.window_end || data.ts_utc) {
          setLastCountTime(data.window_end || data.ts_utc);
        }
      }
    });

    // Event: "health"
    es.addEventListener("health", (event: MessageEvent) => {
      if (!isMountedRef.current) return;
      const data = parsePayload(event);
      if (data) {
        if (typeof data.fps === "number") {
          setFps(data.fps);
        }
        if (typeof data.latency_ms === "number") {
          setLatencyMs(data.latency_ms);
        } else if (typeof data.latency_p95_ms === "number") {
          setLatencyMs(data.latency_p95_ms);
        }
        if (data.status) {
          setStreamState(String(data.status));
        } else if (data.stream_state) {
          setStreamState(String(data.stream_state));
        }
      }
    });

    // Event: "heartbeat"
    es.addEventListener("heartbeat", (event: MessageEvent) => {
      if (!isMountedRef.current) return;
      const data = parsePayload(event);
      if (data) {
        if (typeof data.fps === "number") {
          setFps(data.fps);
        }
        if (data.status) {
          setStreamState(String(data.status));
        }
      }
    });

    // Generic "message" fallback
    es.onmessage = (event: MessageEvent) => {
      if (!isMountedRef.current) return;
      const data = parsePayload(event);
      if (data) {
        if (typeof data.rate_per_min === "number") {
          setLiveSpeed(data.rate_per_min);
        }
        if (typeof data.fps === "number") {
          setFps(data.fps);
        }
        if (typeof data.total_today === "number") {
          setTotalToday(data.total_today);
        }
        if (data.status) {
          setStreamState(String(data.status));
        }
      }
    };
  }, [lineId, cleanup]);

  const reconnect = useCallback(() => {
    backoffDelayRef.current = INITIAL_DELAY_MS;
    connect();
  }, [connect]);

  useEffect(() => {
    isMountedRef.current = true;
    backoffDelayRef.current = INITIAL_DELAY_MS;
    // Reset telemetry state on line switch so previous line's values don't show while connecting
    setLiveSpeed(0);
    setLastCountTime(null);
    setFps(0);
    setLatencyMs(0);
    setTotalToday(0);
    connect();

    return () => {
      isMountedRef.current = false;
      cleanup();
    };
  }, [lineId, connect, cleanup]);

  return {
    status,
    liveSpeed,
    lastCountTime,
    fps,
    latencyMs,
    streamState,
    totalToday,
    reconnect,
  };
}

export default useLiveStream;
