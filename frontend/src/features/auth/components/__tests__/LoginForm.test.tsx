import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { LoginForm } from "../LoginForm";

const mockLogin = vi.fn();

vi.mock("../../context/useAuth", () => ({
  useAuth: () => ({
    login: mockLogin,
    user: null,
    token: null,
    isAuthenticated: false,
    isLoading: false,
    logout: vi.fn(),
  }),
}));

describe("LoginForm (Light Theme)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders light-themed login card, logo, title, labels, and placeholders", () => {
    render(<LoginForm />);

    // Brand header
    const logoImg = screen.getByRole("img", { name: "Poultry Counter Logo" });
    expect(logoImg).toBeDefined();
    expect(screen.getByRole("heading", { name: "Sign In", level: 1 })).toBeDefined();
    expect(screen.getByText("Poultry Counter Central Dashboard")).toBeDefined();

    // Labels & Inputs
    expect(screen.getByLabelText("Username")).toBeDefined();
    expect(screen.getByPlaceholderText("admin / operator")).toBeDefined();
    expect(screen.getByLabelText("Password")).toBeDefined();
    expect(screen.getByPlaceholderText("••••••••")).toBeDefined();

    // Submit button
    expect(screen.getByRole("button", { name: "Sign In" })).toBeDefined();
  });

  it("shows validation error message when submitted with empty fields", async () => {
    render(<LoginForm />);

    const submitBtn = screen.getByRole("button", { name: "Sign In" });
    fireEvent.click(submitBtn);

    const alert = await screen.findByRole("alert");
    expect(alert).toBeDefined();
    expect(alert.textContent).toContain("Please enter your username and password.");
    expect(mockLogin).not.toHaveBeenCalled();
  });

  it("toggles password visibility between password and text when eye toggle button is clicked", () => {
    render(<LoginForm />);

    const passwordInput = screen.getByPlaceholderText("••••••••") as HTMLInputElement;
    expect(passwordInput.type).toBe("password");

    const toggleBtn = screen.getByRole("button", { name: "Show password" });
    fireEvent.click(toggleBtn);
    expect(passwordInput.type).toBe("text");
    expect(screen.getByRole("button", { name: "Hide password" })).toBeDefined();

    fireEvent.click(screen.getByRole("button", { name: "Hide password" }));
    expect(passwordInput.type).toBe("password");
  });

  it("populates fields when demo quick-fill buttons are clicked in DEV mode", () => {
    render(<LoginForm />);

    const adminBtn = screen.getByRole("button", { name: "Admin (admin123)" });
    const operatorBtn = screen.getByRole("button", { name: "Operator (operator123)" });

    fireEvent.click(adminBtn);
    expect((screen.getByLabelText("Username") as HTMLInputElement).value).toBe("admin");
    expect((screen.getByLabelText("Password") as HTMLInputElement).value).toBe("admin123");

    fireEvent.click(operatorBtn);
    expect((screen.getByLabelText("Username") as HTMLInputElement).value).toBe("operator");
    expect((screen.getByLabelText("Password") as HTMLInputElement).value).toBe("operator123");
  });

  it("calls login with credentials and invokes onSuccess upon successful submission", async () => {
    const onSuccess = vi.fn();
    mockLogin.mockResolvedValueOnce({
      access_token: "test-token",
      user: { id: 1, username: "admin", role: "admin", is_active: true },
    });

    render(<LoginForm onSuccess={onSuccess} />);

    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "admin" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "admin123" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign In" }));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith({
        username: "admin",
        password: "admin123",
      });
      expect(onSuccess).toHaveBeenCalledTimes(1);
    });
  });

  it("displays error banner when login API call fails", async () => {
    mockLogin.mockRejectedValueOnce(new Error("Invalid credentials"));

    render(<LoginForm />);

    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "wronguser" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "wrongpass" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign In" }));

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Invalid credentials");
  });

  it("disables submit button and shows loading spinner while submitting", async () => {
    let resolveLogin: (value: unknown) => void;
    mockLogin.mockReturnValue(new Promise((resolve) => {
      resolveLogin = resolve;
    }));

    render(<LoginForm />);

    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "admin" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "admin123" } });

    const submitBtn = screen.getByRole("button", { name: "Sign In" });
    fireEvent.click(submitBtn);

    expect(screen.getByRole("button", { name: "Signing in..." })).toBeDefined();
    expect(submitBtn.hasAttribute("disabled")).toBe(true);

    // Resolve login to clean up
    resolveLogin!({ access_token: "token" });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Sign In" })).toBeDefined();
    });
  });
});
