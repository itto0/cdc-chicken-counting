import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ThresholdMatrixCard } from "../ThresholdMatrixCard";
import type { Line } from "@/types";

vi.mock("@/context/AppContext", () => ({
  useAppContext: () => ({
    currentLineId: "line-1",
    lines: [
      {
        id: "line-1",
        name: "Lini Konveyor 1",
        is_active: true,
        effective_rate_warning: 130,
        effective_rate_critical: 110,
        rate_warning_threshold: null,
        rate_critical_threshold: null,
      },
    ],
  }),
}));

describe("ThresholdMatrixCard", () => {
  it("renders standard thresholds when active line has no overrides", () => {
    render(<ThresholdMatrixCard />);
    expect(screen.getByText("Matriks Ambang Batas")).toBeDefined();
    expect(screen.getByText("< 130 /mnt")).toBeDefined();
    expect(screen.getByText("< 110 /mnt")).toBeDefined();
    expect(screen.queryByText("Kustom")).toBeNull();
  });

  it("renders custom thresholds and Kustom badge when line has overrides", () => {
    const customLine: Line = {
      id: "line-custom",
      name: "Lini Khusus",
      is_active: true,
      rate_warning_threshold: 145,
      rate_critical_threshold: 120,
      effective_rate_warning: 145,
      effective_rate_critical: 120,
    };

    render(<ThresholdMatrixCard line={customLine} />);
    expect(screen.getByText("< 145 /mnt")).toBeDefined();
    expect(screen.getByText("< 120 /mnt")).toBeDefined();
    expect(screen.getByText("Kustom")).toBeDefined();
  });
});
