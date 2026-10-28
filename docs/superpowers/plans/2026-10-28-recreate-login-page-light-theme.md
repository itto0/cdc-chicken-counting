# Recreate Login Page (Light Theme) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recreate the authentication login page and login form with an accessible, modern light theme matching the Lihat.id poultry counter dashboard, complete with English localization and automated tests.

**Architecture:** Refactor `LoginForm.tsx` into an elevated white card with emerald accents, localized English labels, and the brand chicken logo, and update `LoginPage.tsx` with light viewport background styling and subtle ambient glow effects. Add comprehensive Vitest and React Testing Library tests for both components.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, Lucide React, Vitest, React Testing Library.

## Global Constraints

- Design layout: Centered card elevated on `bg-slate-50` with subtle glow accents (`bg-emerald-500/5`, `bg-indigo-500/5`).
- Color palette: White card (`bg-white`), borders (`border-slate-200/80` or `border-slate-300`), text (`text-slate-900`, `text-slate-700`, `text-slate-500`, `text-slate-400`), emerald actions (`bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 focus:ring-emerald-500/20`), rose errors (`bg-rose-50 border-rose-200 text-rose-700`).
- Brand asset: Chicken logo at `@/assets/logo/chicken_logo.png` inside `bg-emerald-50 ring-1 ring-emerald-500/20 p-2.5 rounded-2xl mb-4`.
- Typography and copy: English text across all labels, placeholders, errors, and buttons.
- Developer helper: Demo accounts quick-fill buttons rendered only in development mode (`import.meta.env.DEV`).
- TDD workflow: Write tests first, verify failure, implement code, verify passing, and commit.

---

### Task 1: Recreate LoginForm with Light Theme and Automated Tests

**Files:**
- Modify: `frontend/src/features/auth/components/LoginForm.tsx`
- Create: `frontend/src/features/auth/components/__tests__/LoginForm.test.tsx`

**Interfaces:**
- Consumes:
  - `useAuth()` from `../context/useAuth` (`login({ username, password })`)
  - Chicken logo from `@/assets/logo/chicken_logo.png`
- Produces:
  - `export function LoginForm({ onSuccess }: { onSuccess?: () => void }): JSX.Element`

- [ ] **Step 1: Write the failing tests in `LoginForm.test.tsx`**

Create `frontend/src/features/auth/components/__tests__/LoginForm.test.tsx`:

```tsx
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
npx vitest run src/features/auth/components/__tests__/LoginForm.test.tsx
```
Expected: FAIL (because current `LoginForm.tsx` has Indonesian text like "Masuk", "Nama Pengguna", lacks logo, and has old dark styling).

- [ ] **Step 3: Implement minimal recreated light theme `LoginForm.tsx`**

Update `frontend/src/features/auth/components/LoginForm.tsx`:

```tsx
import { useState, type FormEvent } from "react";
import { Lock, User, AlertCircle, Loader2, Eye, EyeOff } from "lucide-react";
import { useAuth } from "../context/useAuth";
import chickenLogo from "@/assets/logo/chicken_logo.png";

interface LoginFormProps {
  onSuccess?: () => void;
}

export function LoginForm({ onSuccess }: LoginFormProps) {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError("Please enter your username and password.");
      return;
    }

    setError(null);
    setIsSubmitting(true);
    try {
      await login({ username: username.trim(), password });
      onSuccess?.();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to sign in to the system.";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleQuickFill = (u: string, p: string) => {
    setUsername(u);
    setPassword(p);
    setError(null);
  };

  return (
    <div className="w-full max-w-md bg-white border border-slate-200/80 rounded-2xl p-6 sm:p-8 shadow-xl shadow-slate-200/60">
      <div className="mb-6 flex flex-col items-center text-center">
        <div className="bg-emerald-50 ring-1 ring-emerald-500/20 p-2.5 rounded-2xl mb-4">
          <img
            src={chickenLogo}
            alt="Poultry Counter Logo"
            className="w-12 h-12 object-contain"
          />
        </div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Sign In</h1>
        <p className="text-sm text-slate-500 mt-1">Poultry Counter Central Dashboard</p>
      </div>

      {error && (
        <div
          role="alert"
          className="mb-5 p-3.5 bg-rose-50 border border-rose-200 rounded-xl flex items-start gap-3 text-rose-700 text-sm"
        >
          <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label
            htmlFor="username"
            className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5"
          >
            Username
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
              <User className="w-4 h-4" />
            </div>
            <input
              id="username"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="admin / operator"
              required
              autoFocus
              className="w-full pl-10 pr-4 py-2.5 bg-white border border-slate-300 rounded-xl text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all"
            />
          </div>
        </div>

        <div>
          <label
            htmlFor="password"
            className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5"
          >
            Password
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
              <Lock className="w-4 h-4" />
            </div>
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              className="w-full pl-10 pr-10 py-2.5 bg-white border border-slate-300 rounded-xl text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-600 transition-colors cursor-pointer"
              tabIndex={-1}
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full mt-2 py-2.5 px-4 bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 disabled:opacity-50 text-white rounded-xl text-sm font-semibold shadow-sm shadow-emerald-600/20 flex items-center justify-center gap-2 transition-all cursor-pointer"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Signing in...</span>
            </>
          ) : (
            <span>Sign In</span>
          )}
        </button>
      </form>

      {/* Demo Credentials Quick-Fill helper */}
      {import.meta.env.DEV && (
        <div className="mt-6 pt-5 border-t border-slate-100">
          <p className="text-xs text-slate-400 text-center mb-2.5">Demo accounts:</p>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => handleQuickFill("admin", "admin123")}
              className="py-1.5 px-3 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 transition-colors cursor-pointer text-center"
            >
              Admin (admin123)
            </button>
            <button
              type="button"
              onClick={() => handleQuickFill("operator", "operator123")}
              className="py-1.5 px-3 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 transition-colors cursor-pointer text-center"
            >
              Operator (operator123)
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
npx vitest run src/features/auth/components/__tests__/LoginForm.test.tsx
```
Expected: PASS (all 7 tests pass).

- [ ] **Step 5: Commit changes**

```bash
git add frontend/src/features/auth/components/LoginForm.tsx frontend/src/features/auth/components/__tests__/LoginForm.test.tsx
git commit -m "feat(auth): recreate LoginForm with light theme, brand logo, and tests"
```

---

### Task 2: Recreate LoginPage Shell with Light Theme and Automated Tests

**Files:**
- Modify: `frontend/src/features/auth/pages/LoginPage.tsx`
- Create: `frontend/src/features/auth/pages/__tests__/LoginPage.test.tsx`

**Interfaces:**
- Consumes:
  - `useAuth()` from `../context/useAuth`
  - `LoginForm` from `../components/LoginForm`
  - React Router `useNavigate`, `useLocation`
- Produces:
  - `export default function LoginPage(): JSX.Element`

- [ ] **Step 1: Write the failing tests in `LoginPage.test.tsx`**

Create `frontend/src/features/auth/pages/__tests__/LoginPage.test.tsx`:

```tsx
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
npx vitest run src/features/auth/pages/__tests__/LoginPage.test.tsx
```
Expected: FAIL (because current `LoginPage.tsx` lacks `bg-slate-50`, test IDs, and has `text-slate-500` footer).

- [ ] **Step 3: Implement minimal recreated light theme `LoginPage.tsx`**

Update `frontend/src/features/auth/pages/LoginPage.tsx`:

```tsx
import { useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { LoginForm } from "../components/LoginForm";
import { useAuth } from "../context/useAuth";

export default function LoginPage() {
  const { isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as { from?: { pathname?: string; search?: string } })?.from;
  const destination = from ? `${from.pathname || "/"}${from.search || ""}` : "/";

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      navigate(destination, { replace: true });
    }
  }, [isAuthenticated, isLoading, navigate, destination]);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4 relative overflow-hidden">
      {/* Decorative ambient background accents */}
      <div
        data-testid="ambient-glow-emerald"
        className="absolute top-1/4 -left-32 w-96 h-96 bg-emerald-500/5 rounded-full blur-3xl pointer-events-none"
      />
      <div
        data-testid="ambient-glow-indigo"
        className="absolute bottom-1/4 -right-32 w-96 h-96 bg-indigo-500/5 rounded-full blur-3xl pointer-events-none"
      />

      <LoginForm onSuccess={() => navigate(destination, { replace: true })} />

      <footer className="mt-8 text-center text-xs text-slate-400">
        &copy; {new Date().getFullYear()} Lihat.id Computer Vision Poultry Counter System
      </footer>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
npx vitest run src/features/auth/pages/__tests__/LoginPage.test.tsx
```
Expected: PASS (all 4 tests pass).

- [ ] **Step 5: Commit changes**

```bash
git add frontend/src/features/auth/pages/LoginPage.tsx frontend/src/features/auth/pages/__tests__/LoginPage.test.tsx
git commit -m "feat(auth): recreate LoginPage with light theme background, ambient glow, and tests"
```

---

### Task 3: Full Feature Verification and Build Check

**Files:**
- Verify: `frontend/src/features/auth/components/LoginForm.tsx`
- Verify: `frontend/src/features/auth/components/__tests__/LoginForm.test.tsx`
- Verify: `frontend/src/features/auth/pages/LoginPage.tsx`
- Verify: `frontend/src/features/auth/pages/__tests__/LoginPage.test.tsx`

**Interfaces:**
- Consumes: All auth feature modules and build configurations
- Produces: Passing test suites and successful build output

- [ ] **Step 1: Run all auth unit and component tests**

Run:
```bash
npx vitest run src/features/auth
```
Expected: PASS (all tests in `LoginForm.test.tsx` and `LoginPage.test.tsx` pass without errors).

- [ ] **Step 2: Run frontend production build check**

Run:
```bash
npm run build
```
Expected: PASS with zero TypeScript or Vite bundle errors.

- [ ] **Step 3: Check git status to ensure working directory is clean**

Run:
```bash
git status
```
Expected: Clean working tree on master branch (spec and plan committed, changes committed).
