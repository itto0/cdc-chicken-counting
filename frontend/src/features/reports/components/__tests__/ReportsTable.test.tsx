import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ReportsTable, type ReportRowItem } from "../ReportsTable";

describe("ReportsTable", () => {
  it("renders empty state message when data is empty", () => {
    render(<ReportsTable data={[]} />);
    expect(
      screen.getByText("Belum ada riwayat data penghitungan untuk filter yang dipilih")
    ).toBeDefined();
  });

  it("handles null/undefined items in data safely", () => {
    // Should not crash if undefined/null is in data
    render(<ReportsTable data={undefined} />);
    expect(
      screen.getByText("Belum ada riwayat data penghitungan untuk filter yang dipilih")
    ).toBeDefined();
  });

  it("displays '-' for accuracy when count is 0 or accuracyPct <= 0", () => {
    const rows: ReportRowItem[] = [
      {
        id: "1",
        timestamp: "01 Jan 2026, 10:00",
        lineName: "Line 1",
        count: 0,
        ratePerMin: 0,
        accuracyPct: 99.2,
        status: "Normal",
      },
      {
        id: "2",
        timestamp: "01 Jan 2026, 11:00",
        lineName: "Line 2",
        count: 100,
        ratePerMin: 50,
        accuracyPct: 0,
        status: "Normal",
      },
    ];

    render(<ReportsTable data={rows} />);

    const hyphens = screen.getAllByText("-");
    expect(hyphens.length).toBe(2);
  });

  it("displays formatted accuracy when count > 0 and accuracyPct > 0", () => {
    const rows: ReportRowItem[] = [
      {
        id: "1",
        timestamp: "01 Jan 2026, 10:00",
        lineName: "Line 1",
        count: 250,
        ratePerMin: 45,
        accuracyPct: 98.5,
        status: "Normal",
      },
    ];

    render(<ReportsTable data={rows} />);

    expect(screen.getByText("98,5%")).toBeDefined();
    expect(screen.getByText("250 ekor")).toBeDefined();
    expect(screen.getByText("45 cpm")).toBeDefined();
  });
});
