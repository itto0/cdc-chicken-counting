import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import ReactECharts from "echarts-for-react";
import { HourlyRateChart } from "../HourlyRateChart";

// Mock echarts-for-react to avoid canvas rendering requirements in jsdom
vi.mock("echarts-for-react", () => ({
  default: vi.fn(() => <div data-testid="echarts-mock" />),
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

  it("maps counts onto the 24-hour timeline with zeroes for missing hours", () => {
    let capturedOption: any = null;
    (vi.mocked(ReactECharts) as any).mockImplementationOnce(({ option }: any) => {
      capturedOption = option;
      return <div data-testid="echarts-mock" />;
    });

    render(
      <HourlyRateChart
        data={[
          { bucket: "2026-10-21T08:00:00+07:00", count: 250, rate_per_min: 4.2, status: "NORMAL" },
          { bucket: "2026-10-21T09:00:00+07:00", count: 300, rate_per_min: 5.0, status: "NORMAL" },
        ]}
      />
    );

    expect(screen.getByTestId("echarts-mock")).toBeDefined();
    expect(capturedOption).not.toBeNull();
    expect(capturedOption.xAxis.data).toHaveLength(24);
    expect(capturedOption.xAxis.data[0]).toBe("00:00");
    expect(capturedOption.xAxis.data[8]).toBe("08:00");
    expect(capturedOption.xAxis.data[23]).toBe("23:00");

    expect(capturedOption.series[0].data).toHaveLength(24);
    expect(capturedOption.series[0].data[8]).toBe(250);
    expect(capturedOption.series[0].data[9]).toBe(300);
    expect(capturedOption.series[0].data[0]).toBe(0);
    expect(capturedOption.tooltip.formatter).toBe("{b}<br /><span style='font-weight:600;'>{c} ekor</span>");
  });

  it("accumulates counts when multiple items fall into the same hour bucket", () => {
    let capturedOption: any = null;
    (vi.mocked(ReactECharts) as any).mockImplementationOnce(({ option }: any) => {
      capturedOption = option;
      return <div data-testid="echarts-mock" />;
    });

    render(
      <HourlyRateChart
        data={[
          { bucket: "2026-10-21T08:15:00+07:00", count: 100, rate_per_min: 6.6, status: "NORMAL" },
          { bucket: "2026-10-21T08:45:00+07:00", count: 150, rate_per_min: 10.0, status: "NORMAL" },
        ]}
      />
    );

    expect(capturedOption.series[0].data[8]).toBe(250);
  });
});
