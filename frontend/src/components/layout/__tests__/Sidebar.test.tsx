import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Sidebar } from "../Sidebar";

let mockCurrentUser: { id: number; username: string; role: string; is_active: boolean } | null = null;

vi.mock("@/features/auth", () => ({
  useAuth: () => ({
    user: mockCurrentUser,
    token: "fake-token",
    isAuthenticated: !!mockCurrentUser,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
  }),
}));

describe("Sidebar Navigation", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders 'User Management' navigation item linking to /pengguna when user has role 'admin'", () => {
    mockCurrentUser = { id: 1, username: "admin_user", role: "admin", is_active: true };

    render(
      <MemoryRouter>
        <Sidebar isOpen={true} onClose={vi.fn()} />
      </MemoryRouter>
    );

    const userManagementLink = screen.getByRole("link", { name: "User Management" });
    expect(userManagementLink).toBeDefined();
    expect(userManagementLink.getAttribute("href")).toBe("/pengguna");

    const pengaturanLink = screen.getByRole("link", { name: "Pengaturan" });
    expect(pengaturanLink).toBeDefined();
    expect(pengaturanLink.getAttribute("href")).toBe("/pengaturan");
  });

  it("does not render 'User Management' or 'Pengaturan' navigation item when user has role 'operator'", () => {
    mockCurrentUser = { id: 2, username: "operator_jane", role: "operator", is_active: true };

    render(
      <MemoryRouter>
        <Sidebar isOpen={true} onClose={vi.fn()} />
      </MemoryRouter>
    );

    expect(screen.queryByRole("link", { name: "User Management" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Pengaturan" })).toBeNull();

    // Standard operator items are visible
    expect(screen.getByRole("link", { name: "Dashboard" })).toBeDefined();
    expect(screen.getByRole("link", { name: "Lini Produksi" })).toBeDefined();
    expect(screen.getByRole("link", { name: "Alarm" })).toBeDefined();
    expect(screen.getByRole("link", { name: "Laporan" })).toBeDefined();
  });

  it("calls onClose when a navigation item is clicked", () => {
    mockCurrentUser = { id: 1, username: "admin_user", role: "admin", is_active: true };
    const onClose = vi.fn();

    render(
      <MemoryRouter>
        <Sidebar isOpen={true} onClose={onClose} />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole("link", { name: "User Management" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when Escape key is pressed while sidebar is open", () => {
    mockCurrentUser = { id: 1, username: "admin_user", role: "admin", is_active: true };
    const onClose = vi.fn();

    render(
      <MemoryRouter>
        <Sidebar isOpen={true} onClose={onClose} />
      </MemoryRouter>
    );

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
