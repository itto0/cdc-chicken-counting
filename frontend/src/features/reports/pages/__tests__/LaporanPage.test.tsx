import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import LaporanPage from "../LaporanPage";
import { reportsApi } from "../../api/reports.api";

vi.mock("@/context/AppContext", () => ({
  useAppContext: () => ({
    currentLineId: "line-1",
    lines: [{ id: "line-1", name: "Conveyor Line 1", status: "online" }],
    isConnected: true,
  }),
}));

vi.mock("@/components/layout/PageHeader", () => ({
  PageHeader: ({ title, children }: any) => (
    <div data-testid="page-header">
      <h1>{title}</h1>
      {children}
    </div>
  ),
}));

vi.mock("@/components/common/StatusBadge", () => ({
  StatusBadge: () => <div data-testid="status-badge" />,
}));

vi.mock("@/components/layout/LineSelector", () => ({
  LineSelector: () => <div data-testid="line-selector" />,
}));

describe("LaporanPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("does not inject sample-1..sample-4 when report api calls fail", async () => {
    const getCountsSpy = vi.spyOn(reportsApi, "getCounts").mockRejectedValue(new Error("Network Error"));

    render(<LaporanPage />);

    await waitFor(() => {
      expect(getCountsSpy).toHaveBeenCalled();
    });

    // In current code before fix, sample-1 / Lini 2 / 7.120 are injected once the rejected promise finishes
    await waitFor(() => {
      expect(screen.queryByText("sample-1")).toBeNull();
      expect(screen.queryByText("Lini 2 - Pemotongan")).toBeNull();
      expect(screen.queryByText("7.120")).toBeNull();
    });

    expect(screen.getByText("Belum ada riwayat data penghitungan untuk filter yang dipilih")).toBeDefined();
  });

  it("renders genuine zero KPI metrics when API returns empty data", async () => {
    vi.spyOn(reportsApi, "getCounts").mockResolvedValue({
      line_id: "line-1",
      aggregates: [],
      events: [],
      pagination: { total: 0, page: 1, limit: 10 },
    });

    render(<LaporanPage />);

    await waitFor(() => {
      const zeroes = screen.getAllByText("0");
      expect(zeroes.length).toBeGreaterThanOrEqual(2); // totalCount and avgRateCpm
      expect(screen.getByText("0 jam 0 mnt")).toBeDefined();
      expect(screen.getByText("-")).toBeDefined();
      expect(screen.queryByText("Sangat Baik")).toBeNull();
    });

    expect(screen.getByText("Belum ada riwayat data penghitungan untuk filter yang dipilih")).toBeDefined();
  });
});
