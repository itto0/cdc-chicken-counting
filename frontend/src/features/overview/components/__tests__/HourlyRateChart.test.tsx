import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { HourlyRateChart } from "../HourlyRateChart";

// Mock echarts-for-react to avoid canvas rendering requirements in jsdom
vi.mock("echarts-for-react", () => ({
  default: () => <div data-testid="echarts-mock" />,
}));

describe("HourlyRateChart", () => {
  it("renders empty state placeholder when data is empty", () => {
    render(<HourlyRateChart data={[]} />);
    expect(screen.getByText("Belum ada data penghitungan hari ini")).toBeDefined();
    expect(screen.queryByTestId("echarts-mock")).toBeNull();
  });

  it("renders empty state placeholder when data is undefined", () => {
    render(<HourlyRateChart />);
    expect(screen.getByText("Belum ada data penghitungan hari ini")).toBeDefined();
    expect(screen.queryByTestId("echarts-mock")).toBeNull();
  });

  it("renders empty state placeholder when all counts are 0", () => {
    render(
      <HourlyRateChart
        data={[
          { bucket: "2026-10-20T08:00:00Z", count: 0, rate_per_min: 0, status: "normal" },
        ]}
      />
    );
    expect(screen.getByText("Belum ada data penghitungan hari ini")).toBeDefined();
    expect(screen.queryByTestId("echarts-mock")).toBeNull();
  });

  it("renders chart when data is populated", () => {
    render(
      <HourlyRateChart
        data={[
          { bucket: "2026-10-20T08:00:00Z", count: 150, rate_per_min: 25, status: "normal" },
        ]}
      />
    );
    expect(screen.queryByText("Belum ada data penghitungan hari ini")).toBeNull();
    expect(screen.getByTestId("echarts-mock")).toBeDefined();
  });

  it("renders chart when data includes zeroes alongside positive counts", () => {
    render(
      <HourlyRateChart
        data={[
          { bucket: "2026-10-20T08:00:00Z", count: 0, rate_per_min: 0, status: "normal" },
          { bucket: "2026-10-20T09:00:00Z", count: 120, rate_per_min: 20, status: "normal" },
        ]}
      />
    );
    expect(screen.queryByText("Belum ada data penghitungan hari ini")).toBeNull();
    expect(screen.getByTestId("echarts-mock")).toBeDefined();
  });
});
