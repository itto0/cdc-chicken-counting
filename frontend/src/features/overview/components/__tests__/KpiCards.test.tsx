import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { KpiCards } from "../KpiCards";
import type { LineSummaryResponse } from "@/types";

const baseSummary: LineSummaryResponse = {
  line_id: "line-1",
  period: "today",
  total_count: 0,
  target_count: 62000,
  target_attainment_pct: 0.0,
  current_speed_cpm: 0.0,
  target_speed_cpm: 120.0,
  active_alarms_count: 0,
  camera_status: "offline",
  last_event_time: null,
  fps: 0.0,
  latency_p95_ms: 0.0,
  detection_accuracy_pct: 0.0,
};

describe("KpiCards", () => {
  it("renders 0 ekor/menit and '-' accuracy when speed and count/accuracy are 0", () => {
    render(<KpiCards summary={baseSummary} />);

    const speedCard = screen.getByText("Laju Rata-rata").closest("div");
    expect(speedCard?.textContent).toContain("0");
    expect(speedCard?.textContent).toContain("ekor/menit");
    expect(screen.queryByText("120")).toBeNull();

    const accuracyCard = screen.getByText("Akurasi Deteksi").closest("div");
    expect(accuracyCard?.textContent).toContain("-");
    expect(screen.queryByText(/99[,.]2/)).toBeNull();
  });

  it("renders speed and formatted accuracy when count > 0 and accuracy > 0", () => {
    const summary: LineSummaryResponse = {
      ...baseSummary,
      total_count: 500,
      current_speed_cpm: 85,
      detection_accuracy_pct: 98.5,
      camera_status: "online",
    };

    render(<KpiCards summary={summary} />);

    const speedCard = screen.getByText("Laju Rata-rata").closest("div");
    expect(speedCard?.textContent).toContain("85");

    const accuracyCard = screen.getByText("Akurasi Deteksi").closest("div");
    expect(accuracyCard?.textContent).toContain("98,5%");
  });

  it("renders '-' for accuracy if total_count is 0 even if accuracy is provided", () => {
    const summary: LineSummaryResponse = {
      ...baseSummary,
      total_count: 0,
      detection_accuracy_pct: 98.5,
    };

    render(<KpiCards summary={summary} />);

    const accuracyCard = screen.getByText("Akurasi Deteksi").closest("div");
    expect(accuracyCard?.textContent).toContain("-");
    expect(screen.queryByText("98,5%")).toBeNull();
  });

  it("renders '0' for speed when current_speed_cpm is undefined or null", () => {
    const summary = {
      ...baseSummary,
      current_speed_cpm: undefined as unknown as number,
    };

    render(<KpiCards summary={summary} />);

    const speedCard = screen.getByText("Laju Rata-rata").closest("div");
    expect(speedCard?.textContent).toContain("0");
    expect(screen.queryByText("120")).toBeNull();
  });
});
