import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Header } from "../Header";
import { alarmsApi } from "@/features/alarms";

const mockLogout = vi.fn();
const mockNavigate = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock("@/features/auth", () => ({
  useAuth: () => ({
    user: { id: 1, username: "operator_john", role: "operator", is_active: true },
    token: "fake-token",
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    logout: mockLogout,
  }),
}));

describe("Header", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(alarmsApi, "list").mockResolvedValue([]);
  });

  it("renders user badge and navigation elements", () => {
    render(
      <MemoryRouter>
        <Header onOpenSidebar={vi.fn()} />
      </MemoryRouter>
    );

    expect(screen.getByText("operator_john")).toBeDefined();
    expect(screen.getByText("operator")).toBeDefined();
    expect(screen.getByRole("button", { name: "Ganti Password" })).toBeDefined();
    expect(screen.getByRole("button", { name: "Keluar dari sistem" })).toBeDefined();
  });

  it("opens ChangePasswordModal when Ganti Password button is clicked and closes on cancel", () => {
    render(
      <MemoryRouter>
        <Header onOpenSidebar={vi.fn()} />
      </MemoryRouter>
    );

    expect(screen.queryByRole("dialog")).toBeNull();

    const changePasswordBtn = screen.getByRole("button", { name: "Ganti Password" });
    fireEvent.click(changePasswordBtn);

    expect(screen.getByRole("dialog")).toBeDefined();
    expect(screen.getByText("Ganti Password Saya")).toBeDefined();

    // Click Batal to close
    fireEvent.click(screen.getByRole("button", { name: "Batal" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("calls logout and navigates to /login when logout button is clicked", () => {
    render(
      <MemoryRouter>
        <Header onOpenSidebar={vi.fn()} />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole("button", { name: "Keluar dari sistem" }));
    expect(mockLogout).toHaveBeenCalledTimes(1);
    expect(mockNavigate).toHaveBeenCalledWith("/login", { replace: true });
  });
});
