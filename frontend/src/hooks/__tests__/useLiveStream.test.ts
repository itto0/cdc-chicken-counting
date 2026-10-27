import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useLiveStream } from "../useLiveStream";

class MockEventSource {
  static instances: MockEventSource[] = [];
  listeners: Record<string, ((event: any) => void)[]> = {};
  url: string;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
    setTimeout(() => {
      if (this.onopen) {
        act(() => {
          this.onopen!();
        });
      }
    }, 0);
  }

  addEventListener(type: string, listener: (event: any) => void) {
    if (!this.listeners[type]) this.listeners[type] = [];
    this.listeners[type].push(listener);
  }

  emit(type: string, data: any) {
    const listeners = this.listeners[type] || [];
    listeners.forEach((fn) => fn({ data: JSON.stringify(data) }));
  }

  close() {
    this.listeners = {};
  }
}

describe("useLiveStream hook", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("updates totalToday when count event arrives with total_today", async () => {
    const { result } = renderHook(() => useLiveStream("line-1"));

    // Wait for connection
    await vi.waitFor(() => expect(result.current.status).toBe("CONNECTED"));

    const instance = MockEventSource.instances[0];

    act(() => {
      instance.emit("count", {
        total_today: 42,
        rate_per_min: 125.5,
        ts_utc: "2026-10-27T10:00:00Z",
      });
    });

    expect(result.current.totalToday).toBe(42);
    expect(result.current.liveSpeed).toBe(125.5);
    expect(result.current.countTick).toBe(1);
    expect(result.current.lastCountTime).toBe("2026-10-27T10:00:00Z");
  });

  it("increments totalToday if count event omits total_today", async () => {
    const { result } = renderHook(() => useLiveStream("line-1"));

    await vi.waitFor(() => expect(result.current.status).toBe("CONNECTED"));
    const instance = MockEventSource.instances[0];

    // Initial status event sets baseline (verifying >= 0 allows 0 or positive values)
    act(() => {
      instance.emit("status", { total_today: 10, status: "ONLINE" });
    });
    expect(result.current.totalToday).toBe(10);

    // Count tick without absolute total
    act(() => {
      instance.emit("count", { rate_per_min: 130 });
    });

    expect(result.current.totalToday).toBe(11);
    expect(result.current.countTick).toBe(1);
  });

  it("initializes totalToday when status event has total_today = 0", async () => {
    const { result } = renderHook(() => useLiveStream("line-1"));

    await vi.waitFor(() => expect(result.current.status).toBe("CONNECTED"));
    const instance = MockEventSource.instances[0];

    // Set non-zero count first to verify status event can reset or set total_today to 0
    act(() => {
      instance.emit("count", { total_today: 15 });
    });
    expect(result.current.totalToday).toBe(15);

    act(() => {
      instance.emit("status", { total_today: 0, status: "ONLINE" });
    });
    expect(result.current.totalToday).toBe(0);
  });

  it("increments countTick on every count event sequentially", async () => {
    const { result } = renderHook(() => useLiveStream("line-1"));

    await vi.waitFor(() => expect(result.current.status).toBe("CONNECTED"));
    const instance = MockEventSource.instances[0];

    act(() => {
      instance.emit("count", { total_today: 5 });
    });
    expect(result.current.countTick).toBe(1);
    expect(result.current.totalToday).toBe(5);

    act(() => {
      instance.emit("count", {});
    });
    expect(result.current.countTick).toBe(2);
    expect(result.current.totalToday).toBe(6);
  });
});
