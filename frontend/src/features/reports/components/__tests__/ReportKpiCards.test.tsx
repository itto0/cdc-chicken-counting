import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { ReportKpiCards, type ReportSummaryMetrics } from "../ReportKpiCards";

describe("ReportKpiCards", () => {
  const getCardContent = (title: string): HTMLElement => {
    const titleEl = screen.getByText(title);
    const cardContent = titleEl.closest(".p-5") as HTMLElement;
    return cardContent || titleEl.parentElement?.parentElement;
  };

  it("renders zero metrics correctly and does not display 'Sangat Baik' on zero state", () => {
    const zeroMetrics: ReportSummaryMetrics = {
      totalCount: 0,
      avgRateCpm: 0,
      avgAccuracyPct: 0,
      totalOperationMinutes: 0,
    };

    render(<ReportKpiCards metrics={zeroMetrics} />);

    // Total Ayam Terhitung
    const totalCountCard = getCardContent("Total Ayam Terhitung");
    expect(within(totalCountCard).getByText("0")).toBeDefined();
    expect(within(totalCountCard).getByText("ekor")).toBeDefined();

    // Rata-rata Laju
    const rateCard = getCardContent("Rata-rata Laju");
    expect(within(rateCard).getByText("0")).toBeDefined();
    expect(within(rateCard).getByText("ekor/menit")).toBeDefined();

    // Akurasi Rata-rata: should display '-' and not 'Sangat Baik' or '99.1%'
    const accuracyCard = getCardContent("Akurasi Rata-rata");
    expect(within(accuracyCard).getByText("-")).toBeDefined();
    expect(screen.queryByText("Sangat Baik")).toBeNull();
    expect(screen.queryByText(/99[,.]1/)).toBeNull();

    // Total Waktu Operasi
    const timeCard = getCardContent("Total Waktu Operasi");
    expect(within(timeCard).getByText("0 jam 0 mnt")).toBeDefined();
  });

  it("renders active metrics, formatted accuracy with % and 'Sangat Baik' when accuracy is valid", () => {
    const activeMetrics: ReportSummaryMetrics = {
      totalCount: 1250,
      avgRateCpm: 85.4,
      avgAccuracyPct: 98.7,
      totalOperationMinutes: 150,
    };

    render(<ReportKpiCards metrics={activeMetrics} />);

    // Total Ayam Terhitung formatted id-ID
    const totalCountCard = getCardContent("Total Ayam Terhitung");
    expect(within(totalCountCard).getByText("1.250")).toBeDefined();

    // Rata-rata Laju rounded
    const rateCard = getCardContent("Rata-rata Laju");
    expect(within(rateCard).getByText("85")).toBeDefined();

    // Akurasi Rata-rata formatted id-ID + '%'
    const accuracyCard = getCardContent("Akurasi Rata-rata");
    expect(within(accuracyCard).getByText("98,7%")).toBeDefined();
    expect(within(accuracyCard).getByText("Sangat Baik")).toBeDefined();

    // Total Waktu Operasi: 150 mins = 2 jam 30 mnt
    const timeCard = getCardContent("Total Waktu Operasi");
    expect(within(timeCard).getByText("2 jam 30 mnt")).toBeDefined();
  });

  it("renders '-' for accuracy and suppresses 'Sangat Baik' when totalCount is 0 even if avgAccuracyPct > 0", () => {
    const metricsWithZeroCount: ReportSummaryMetrics = {
      totalCount: 0,
      avgRateCpm: 0,
      avgAccuracyPct: 99.1,
      totalOperationMinutes: 60,
    };

    render(<ReportKpiCards metrics={metricsWithZeroCount} />);

    const accuracyCard = getCardContent("Akurasi Rata-rata");
    expect(within(accuracyCard).getByText("-")).toBeDefined();
    expect(screen.queryByText("Sangat Baik")).toBeNull();
  });

  it("renders '-' for accuracy and suppresses 'Sangat Baik' when avgAccuracyPct is 0 even if totalCount > 0", () => {
    const metricsWithZeroAccuracy: ReportSummaryMetrics = {
      totalCount: 500,
      avgRateCpm: 45,
      avgAccuracyPct: 0,
      totalOperationMinutes: 60,
    };

    render(<ReportKpiCards metrics={metricsWithZeroAccuracy} />);

    const accuracyCard = getCardContent("Akurasi Rata-rata");
    expect(within(accuracyCard).getByText("-")).toBeDefined();
    expect(screen.queryByText("Sangat Baik")).toBeNull();
  });

  it("handles undefined/partial metrics safely without errors", () => {
    render(<ReportKpiCards metrics={undefined as any} />);

    const zeroes = screen.getAllByText("0");
    expect(zeroes.length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("0 jam 0 mnt")).toBeDefined();
    expect(screen.getByText("-")).toBeDefined();
    expect(screen.queryByText("Sangat Baik")).toBeNull();
  });
});
