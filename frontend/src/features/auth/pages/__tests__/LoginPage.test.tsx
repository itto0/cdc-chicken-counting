import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import LoginPage from "../LoginPage";

const mockNavigate = vi.fn();
let mockIsAuthenticated = false;
let mockIsLoading = false;
let mockLocationState: { from?: { pathname?: string; search?: string } } | null = null;

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useLocation: () => ({ state: mockLocationState }),
  };
});

vi.mock("../../context/useAuth", () => ({
  useAuth: () => ({
    isAuthenticated: mockIsAuthenticated,
    isLoading: mockIsLoading,
    login: vi.fn(),
    logout: vi.fn(),
  }),
}));

vi.mock("../../components/LoginForm", () => ({
  LoginForm: ({ onSuccess }: { onSuccess?: () => void }) => (
    <div data-testid="mock-login-form">
      <button data-testid="mock-login-success-btn" onClick={onSuccess}>
        Mock Success
      </button>
    </div>
  ),
}));

describe("LoginPage (Light Theme)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsAuthenticated = false;
    mockIsLoading = false;
    mockLocationState = null;
  });

  it("renders light page background, ambient glow accents, and footer", () => {
    const { container } = render(<LoginPage />);

    // Shell background container has bg-slate-50
    const pageWrapper = container.firstElementChild as HTMLElement;
    expect(pageWrapper.className).toContain("bg-slate-50");

    // Ambient glow accents
    expect(screen.getByTestId("ambient-glow-emerald")).toBeDefined();
    expect(screen.getByTestId("ambient-glow-indigo")).toBeDefined();

    // LoginForm rendered
    expect(screen.getByTestId("mock-login-form")).toBeDefined();

    // Copyright footer with current year
    const currentYear = new Date().getFullYear().toString();
    const footer = screen.getByRole("contentinfo");
    expect(footer.textContent).toContain(currentYear);
    expect(footer.textContent).toContain("Lihat.id Computer Vision Poultry Counter System");
    expect(footer.className).toContain("text-slate-400");
  });

  it("auto-navigates to destination if already authenticated", () => {
    mockIsAuthenticated = true;
    mockIsLoading = false;

    render(<LoginPage />);

    expect(mockNavigate).toHaveBeenCalledWith("/", { replace: true });
  });

  it("auto-navigates to original route if location.state.from is provided", () => {
    mockIsAuthenticated = true;
    mockIsLoading = false;
    mockLocationState = {
      from: {
        pathname: "/reports",
        search: "?filter=active",
      },
    };

    render(<LoginPage />);

    expect(mockNavigate).toHaveBeenCalledWith("/reports?filter=active", { replace: true });
  });

  it("navigates to destination when LoginForm triggers onSuccess", () => {
    render(<LoginPage />);

    const successBtn = screen.getByTestId("mock-login-success-btn");
    successBtn.click();

    expect(mockNavigate).toHaveBeenCalledWith("/", { replace: true });
  });
});
