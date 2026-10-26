import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import PengaturanPage from "../PengaturanPage";

const mockUpdateLine = vi.fn();
const mockCreateLine = vi.fn();

const defaultLine = {
  id: "line-1",
  name: "Lini Konveyor 1",
  daily_target: 60000,
  is_active: true,
  video_url: "",
  line_coords: "0,240,640,240",
  line_direction: "down",
  rate_warning_threshold: 135.0,
  rate_critical_threshold: 115.0,
  effective_rate_warning: 135.0,
  effective_rate_critical: 115.0,
};

vi.mock("@/context/AppContext", () => ({
  useAppContext: () => ({
    currentLineId: "line-1",
    lines: [defaultLine],
    isConnected: true,
    updateLine: mockUpdateLine,
    createLine: mockCreateLine,
  }),
}));

vi.mock("@/components/layout/PageHeader", () => ({
  PageHeader: ({ title, description }: any) => (
    <div>
      <h1>{title}</h1>
      <p>{description}</p>
    </div>
  ),
}));

vi.mock("@/components/layout/LineSelector", () => ({
  LineSelector: () => <div data-testid="line-selector" />,
}));

describe("PengaturanPage Thresholds", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders threshold inputs with active line custom values", () => {
    render(<PengaturanPage />);
    const warningInput = screen.getByLabelText(/Peringatan.*Warning/i) as HTMLInputElement;
    const criticalInput = screen.getByLabelText(/Kritis.*Critical/i) as HTMLInputElement;

    expect(warningInput).toBeDefined();
    expect(criticalInput).toBeDefined();
    expect(warningInput.value).toBe("135");
    expect(criticalInput.value).toBe("115");
  });

  it("clears inputs when 'Gunakan Standar Sistem' button is clicked", () => {
    render(<PengaturanPage />);
    const warningInput = screen.getByLabelText(/Peringatan.*Warning/i) as HTMLInputElement;
    const criticalInput = screen.getByLabelText(/Kritis.*Critical/i) as HTMLInputElement;
    const resetBtn = screen.getByRole("button", { name: /Gunakan Standar Sistem/i });

    fireEvent.click(resetBtn);
    expect(warningInput.value).toBe("");
    expect(criticalInput.value).toBe("");
  });

  it("shows error if critical threshold is greater than or equal to warning", async () => {
    render(<PengaturanPage />);
    const warningInput = screen.getByLabelText(/Peringatan.*Warning/i) as HTMLInputElement;
    const criticalInput = screen.getByLabelText(/Kritis.*Critical/i) as HTMLInputElement;
    const submitBtn = screen.getByRole("button", { name: /Simpan Konfigurasi/i });

    fireEvent.change(warningInput, { target: { value: "110" } });
    fireEvent.change(criticalInput, { target: { value: "120" } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/Ambang batas kritis harus lebih kecil dari ambang batas peringatan/i)).toBeDefined();
    });
    expect(mockUpdateLine).not.toHaveBeenCalled();
  });

  it("shows error if single-sided warning threshold is less than or equal to default critical (110)", async () => {
    render(<PengaturanPage />);
    const warningInput = screen.getByLabelText(/Peringatan.*Warning/i) as HTMLInputElement;
    const criticalInput = screen.getByLabelText(/Kritis.*Critical/i) as HTMLInputElement;
    const submitBtn = screen.getByRole("button", { name: /Simpan Konfigurasi/i });

    // Warning 100 with empty critical (effective critical = 110 >= warning 100)
    fireEvent.change(warningInput, { target: { value: "100" } });
    fireEvent.change(criticalInput, { target: { value: "" } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/Ambang batas kritis harus lebih kecil dari ambang batas peringatan/i)).toBeDefined();
    });
    expect(mockUpdateLine).not.toHaveBeenCalled();
  });

  it("shows error if single-sided critical threshold is greater than or equal to default warning (130)", async () => {
    render(<PengaturanPage />);
    const warningInput = screen.getByLabelText(/Peringatan.*Warning/i) as HTMLInputElement;
    const criticalInput = screen.getByLabelText(/Kritis.*Critical/i) as HTMLInputElement;
    const submitBtn = screen.getByRole("button", { name: /Simpan Konfigurasi/i });

    // Critical 135 with empty warning (critical 135 >= effective warning 130)
    fireEvent.change(warningInput, { target: { value: "" } });
    fireEvent.change(criticalInput, { target: { value: "135" } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/Ambang batas kritis harus lebih kecil dari ambang batas peringatan/i)).toBeDefined();
    });
    expect(mockUpdateLine).not.toHaveBeenCalled();
  });
});
