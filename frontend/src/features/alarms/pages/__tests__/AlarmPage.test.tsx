import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import AlarmPage from "../AlarmPage";
import { alarmsApi } from "../../api/alarms.api";

vi.mock("@/context/AppContext", () => ({
  useAppContext: () => ({
    currentLineId: "line-1",
    lines: [{ id: "line-1", name: "Conveyor Line 1", status: "online" }],
    isConnected: true,
  }),
}));

vi.mock("@/components/layout/PageHeader", () => ({
  PageHeader: ({ title, description, children }: any) => (
    <div data-testid="page-header">
      <h1>{title}</h1>
      <p>{description}</p>
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

describe("AlarmPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("does not inject fallback LOW_SPEED mock alarm on error and displays empty state text", async () => {
    const listSpy = vi.spyOn(alarmsApi, "list").mockRejectedValue(new Error("Network Error"));

    render(<AlarmPage />);

    await waitFor(() => {
      expect(listSpy).toHaveBeenCalledWith("line-1");
    });

    await waitFor(() => {
      expect(screen.queryByText(/Kecepatan di bawah target/i)).toBeNull();
      expect(screen.queryByText("LOW_SPEED")).toBeNull();
    });

    expect(screen.getByText("Tidak ada data alarm yang tercatat")).toBeDefined();
  });

  it("renders clean empty state when alarmsApi returns empty array", async () => {
    vi.spyOn(alarmsApi, "list").mockResolvedValue([]);

    render(<AlarmPage />);

    await waitFor(() => {
      expect(screen.getByText("Tidak ada data alarm yang tercatat")).toBeDefined();
    });
  });
});
