# Full-Stack Authentication & Role-Based Access Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete full-stack authentication and role-based access control system with auto-seeded credentials, protected API routes, session management in React, protected route guards, and industrial dark login UI.

**Architecture:** Backend leverages PBKDF2 password hashing and HS256 JWT tokens with FastAPI dependency injection (`get_current_user` and `require_role`). Edge ingest (`/sync/batch`) and MJPEG preview endpoints remain open/device-accessible. Frontend uses a modular feature structure under `features/auth/` with React Context, Axios/fetch Bearer headers in `lib/http.ts`, route guards in `app/router.tsx`, and dynamic user profile badges with logout in `Header.tsx`.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy, PyJWT, Pytest, React 18, React Router v7, TypeScript, Tailwind CSS, Lucide React.

## Global Constraints

- Backend base prefix: `/api/v1`
- JWT algorithm: `HS256`, 24-hour expiration
- Token storage key: `lihat_auth_token` in `localStorage`
- Seed credentials: `admin / admin123` (role: `admin`), `operator / operator123` (role: `operator`)
- Role authorization logic: case-insensitive matching (`admin` vs `ADMIN`, `operator` vs `OPERATOR`)
- Public endpoints: `/api/v1/auth/login`, `/healthz`, `/api/v1/lines/{id}/preview`, `/api/v1/sync/batch`
- Authenticated endpoints: `/api/v1/auth/me`, `/api/v1/lines`, `/api/v1/summary`, `/api/v1/counts/*`, `/api/v1/alarms/*`, `/api/v1/reports/*`
- Admin-only endpoints: `POST /api/v1/lines`, `PUT /api/v1/lines/{id}`, `DELETE /api/v1/lines/{id}`
- Frontend UI theme: Industrial slate dark theme (`slate-900`, `slate-800`, `emerald-500`, `indigo-500`)

---

### Task 1: Backend Database User Seeding on Startup

**Files:**
- Modify: `services/api/src/main.py:24-52`
- Test: `services/api/tests/test_seed_users.py`

**Interfaces:**
- Consumes: `services.api.src.db.models.User`, `services.api.src.services.auth.hash_password`
- Produces: `init_db(target_engine=None)` seeds default `admin` and `operator` accounts when not present in the database.

- [ ] **Step 1: Write the failing test**

Create `services/api/tests/test_seed_users.py`:

```python
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from services.api.src.db.models import Base, User
from services.api.src.services.auth import verify_password
from services.api.src.main import init_db


def test_init_db_seeds_default_admin_and_operator():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Run database initialization on clean memory engine
    init_db(target_engine=engine)

    with Session(engine) as session:
        admin = session.execute(select(User).where(User.username == "admin")).scalar_one_or_none()
        assert admin is not None
        assert admin.role.lower() == "admin"
        assert admin.is_active is True
        assert verify_password("admin123", admin.password_hash) is True

        operator = session.execute(select(User).where(User.username == "operator")).scalar_one_or_none()
        assert operator is not None
        assert operator.role.lower() == "operator"
        assert operator.is_active is True
        assert verify_password("operator123", operator.password_hash) is True


def test_init_db_idempotent():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(target_engine=engine)
    # Running again should not fail or duplicate users
    init_db(target_engine=engine)

    with Session(engine) as session:
        users = session.execute(select(User)).scalars().all()
        admin_count = sum(1 for u in users if u.username == "admin")
        op_count = sum(1 for u in users if u.username == "operator")
        assert admin_count == 1
        assert op_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest services/api/tests/test_seed_users.py -v`
Expected: FAIL with `AssertionError: assert None is not None`

- [ ] **Step 3: Update `init_db` in `services/api/src/main.py`**

Modify `services/api/src/main.py:24-51` to seed default users:

```python
def init_db(target_engine=None) -> None:
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)
    with Session(eng) as session:
        if not session.get(Line, "line-1"):
            session.add(
                Line(
                    id="line-1",
                    name="Lini Konveyor 1",
                    daily_target=62000,
                    line_direction="right",
                    line_coords="0,240,640,240",
                    is_active=True,
                )
            )
        if not session.get(Line, "lineA"):
            session.add(
                Line(
                    id="lineA",
                    name="Lini Konveyor A",
                    daily_target=62000,
                    line_direction="down",
                    line_coords="0,240,640,240",
                    is_active=True,
                )
            )

        from services.api.src.db.models import User
        from services.api.src.services.auth import hash_password

        admin_user = session.execute(select(User).where(User.username == "admin")).scalar_one_or_none()
        if not admin_user:
            session.add(
                User(
                    username="admin",
                    password_hash=hash_password("admin123"),
                    role="admin",
                    is_active=True,
                )
            )
        operator_user = session.execute(select(User).where(User.username == "operator")).scalar_one_or_none()
        if not operator_user:
            session.add(
                User(
                    username="operator",
                    password_hash=hash_password("operator123"),
                    role="operator",
                    is_active=True,
                )
            )

        session.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest services/api/tests/test_seed_users.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add services/api/src/main.py services/api/tests/test_seed_users.py
git commit -m "feat(api): seed default admin and operator users on startup"
```

---

### Task 2: Role-Based Access Control (RBAC) Dependency

**Files:**
- Modify: `services/api/src/api/auth.py`
- Test: `services/api/tests/test_rbac_unit.py`

**Interfaces:**
- Consumes: `UserDTO`, `get_current_user`
- Produces: `require_role(allowed_roles: list[str]) -> Callable[[UserDTO], UserDTO]`

- [ ] **Step 1: Write the failing test**

Create `services/api/tests/test_rbac_unit.py`:

```python
import pytest
from fastapi import HTTPException
from services.api.src.api.auth import UserDTO, require_role


def test_require_role_matching_role():
    checker = require_role(["admin", "manager"])
    user = UserDTO(id=1, username="alice", role="admin", is_active=True)
    res = checker(user)
    assert res == user


def test_require_role_case_insensitive():
    checker = require_role(["ADMIN"])
    user = UserDTO(id=1, username="alice", role="admin", is_active=True)
    res = checker(user)
    assert res == user

    checker_lower = require_role(["admin"])
    user_upper = UserDTO(id=1, username="alice", role="ADMIN", is_active=True)
    res2 = checker_lower(user_upper)
    assert res2 == user_upper


def test_require_role_forbidden():
    checker = require_role(["admin"])
    user = UserDTO(id=2, username="bob", role="operator", is_active=True)
    with pytest.raises(HTTPException) as exc_info:
        checker(user)
    assert exc_info.value.status_code == 403
    assert "Required role: admin" in exc_info.value.detail
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest services/api/tests/test_rbac_unit.py -v`
Expected: FAIL with `ImportError: cannot import name 'require_role' from 'services.api.src.api.auth'`

- [ ] **Step 3: Implement `require_role` in `services/api/src/api/auth.py`**

Add `require_role` to `services/api/src/api/auth.py`:

```python
def require_role(allowed_roles: list[str]):
    def role_checker(current_user: UserDTO = Depends(get_current_user)) -> UserDTO:
        user_role = (current_user.role or "").strip().lower()
        normalized_allowed = [r.strip().lower() for r in allowed_roles]
        if user_role not in normalized_allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Operation not permitted. Required role: {', '.join(allowed_roles)}",
            )
        return current_user

    return role_checker
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest services/api/tests/test_rbac_unit.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add services/api/src/api/auth.py services/api/tests/test_rbac_unit.py
git commit -m "feat(api): implement require_role dependency for RBAC"
```

---

### Task 3: REST Endpoint Route Protection & Test Suite Isolation

**Files:**
- Create: `services/api/tests/conftest.py`
- Modify: `services/api/src/api/lines.py`
- Modify: `services/api/src/api/summary.py`
- Modify: `services/api/src/api/counts.py`
- Modify: `services/api/src/api/alarms.py`
- Modify: `services/api/src/api/reports.py`
- Test: `services/api/tests/test_rbac_api.py`

**Interfaces:**
- Consumes: `get_current_user`, `require_role` from `services.api.src.api.auth`
- Produces: Protected REST endpoints rejecting unauthenticated (401) or unauthorized (403) requests.

- [ ] **Step 1: Create `services/api/tests/conftest.py` for test isolation**

Create `services/api/tests/conftest.py`:

```python
import pytest
from services.api.src.api.auth import get_current_user, UserDTO
from services.api.src.main import app


@pytest.fixture(autouse=True)
def default_auth_override(request):
    """
    Automatically bypass auth for existing functional tests (lines, counts, alarms, etc.)
    while preserving real auth evaluation for dedicated auth and RBAC test suites.
    """
    node_id = request.node.nodeid
    if any(auth_file in node_id for auth_file in ("test_auth_api", "test_rbac", "test_seed_users")):
        yield
        return

    app.dependency_overrides[get_current_user] = lambda: UserDTO(
        id=1, username="admin", role="admin", is_active=True
    )
    yield
    app.dependency_overrides.pop(get_current_user, None)
```

- [ ] **Step 2: Write failing RBAC integration test**

Create `services/api/tests/test_rbac_api.py`:

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api.src.main import app
from services.api.src.db.session import get_db
from services.api.src.db.models import Base, User, Line
from services.api.src.services.auth import hash_password, create_access_token


@pytest.fixture
def rbac_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with TestingSession() as db:
        db.add(Line(id="line-1", name="Test Line", daily_target=50000, is_active=True))
        db.add(User(username="admin", password_hash=hash_password("admin123"), role="admin", is_active=True))
        db.add(User(username="operator", password_hash=hash_password("op123"), role="operator", is_active=True))
        db.commit()

    def override_get_db():
        with TestingSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_lines_unauthenticated_returns_401(rbac_client):
    res = rbac_client.get("/api/v1/lines")
    assert res.status_code == 401


def test_lines_authenticated_operator_can_read(rbac_client):
    token = create_access_token({"sub": "operator", "role": "operator"})
    res = rbac_client.get("/api/v1/lines", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert len(res.json()) >= 1


def test_lines_create_forbidden_for_operator(rbac_client):
    token = create_access_token({"sub": "operator", "role": "operator"})
    res = rbac_client.post(
        "/api/v1/lines",
        json={"id": "line-2", "name": "Line 2", "daily_target": 10000},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
    assert "Required role: admin" in res.json()["detail"]


def test_lines_create_allowed_for_admin(rbac_client):
    token = create_access_token({"sub": "admin", "role": "admin"})
    res = rbac_client.post(
        "/api/v1/lines",
        json={"id": "line-2", "name": "Line 2", "daily_target": 10000},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    assert res.json()["id"] == "line-2"


def test_sync_batch_remains_open_without_auth(rbac_client):
    # Edge syncing must not require user login
    res = rbac_client.post(
        "/api/v1/sync/batch",
        json={"line_id": "line-1", "events": [], "aggregates": [], "health": None},
    )
    assert res.status_code == 200
```

- [ ] **Step 3: Run test to verify it fails**

Run: `py -m pytest services/api/tests/test_rbac_api.py -v`
Expected: FAIL on `test_lines_unauthenticated_returns_401` (currently returns 200 because endpoints are open).

- [ ] **Step 4: Protect endpoints in routers**

1. In `services/api/src/api/lines.py`:
   - Import `from services.api.src.api.auth import get_current_user, require_role, UserDTO`
   - Add `current_user: UserDTO = Depends(require_role(["admin"]))` to:
     - `@router.post("", ...)` (`create_line`)
     - `@router.put("/{line_id}", ...)` (`update_line`)
     - `@router.delete("/{line_id}", ...)` (`delete_line`)
   - Add `current_user: UserDTO = Depends(get_current_user)` to:
     - `@router.get("", ...)` (`list_lines`)
     - `@router.get("/{line_id}", ...)` (`get_line`)

2. In `services/api/src/api/summary.py`:
   - Import `from services.api.src.api.auth import get_current_user, UserDTO`
   - Add `current_user: UserDTO = Depends(get_current_user)` to `@router.get("")` (`get_summary`).

3. In `services/api/src/api/counts.py`:
   - Import `from services.api.src.api.auth import get_current_user, UserDTO`
   - Add `current_user: UserDTO = Depends(get_current_user)` to `@router.get("/{line_id}")` (`get_line_counts`).

4. In `services/api/src/api/alarms.py`:
   - Import `from services.api.src.api.auth import get_current_user, UserDTO`
   - Add `current_user: UserDTO = Depends(get_current_user)` to:
     - `@router.get("")` (`list_alarms`)
     - `@router.patch("/{alarm_id}")` (`patch_alarm`)

5. In `services/api/src/api/reports.py`:
   - Import `from services.api.src.api.auth import get_current_user, UserDTO`
   - Add `current_user: UserDTO = Depends(get_current_user)` to `@router.get("/export")` (`export_report`).

- [ ] **Step 5: Run all backend tests to verify RBAC and regression passes**

Run: `py -m pytest services/api/tests/ -v`
Expected: PASS on all tests (154+ passed, 0 failed)

- [ ] **Step 6: Commit**

```bash
git add services/api/tests/conftest.py services/api/tests/test_rbac_api.py services/api/src/api/
git commit -m "feat(api): protect dashboard REST endpoints with JWT and RBAC"
```

---

### Task 4: Frontend Auth Feature Types & API Client

**Files:**
- Create: `frontend/src/features/auth/types.ts`
- Create: `frontend/src/features/auth/api/auth.api.ts`
- Modify: `frontend/src/lib/http.ts`

**Interfaces:**
- Consumes: `http` from `@/lib/http`
- Produces: `authApi.login`, `authApi.getMe`, updated `http.ts` token lifecycle handling.

- [ ] **Step 1: Create `frontend/src/features/auth/types.ts`**

```ts
export type UserRole = "admin" | "operator" | string;

export interface User {
  id: number;
  username: string;
  role: UserRole;
  is_active: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
}
```

- [ ] **Step 2: Create `frontend/src/features/auth/api/auth.api.ts`**

```ts
import { http } from "@/lib/http";
import type { LoginCredentials, LoginResponse, User } from "../types";

export const authApi = {
  login: (credentials: LoginCredentials): Promise<LoginResponse> =>
    http<LoginResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(credentials),
    }),

  getMe: (): Promise<User> =>
    http<User>("/api/v1/auth/me", {
      method: "GET",
    }),
};
```

- [ ] **Step 3: Update `frontend/src/lib/http.ts` for clean 401 handling**

Modify `frontend/src/lib/http.ts`:

```ts
import { env } from "@/config/env";

const TOKEN_KEY = "lihat_auth_token";

export function getAuthToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setAuthToken(token: string | null): void {
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    // ignore storage access errors
  }
}

export async function http<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const base = env.API_BASE_URL.replace(/\/$/, "");
  const normalizedEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const url = endpoint.startsWith("http://") || endpoint.startsWith("https://")
    ? endpoint
    : `${base}${normalizedEndpoint}`;

  const headers = new Headers(options.headers || {});
  if (options.body && !headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  const token = getAuthToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url, { ...options, headers });

  if (response.status === 401) {
    // If request to /me or protected resource failed with 401, clear stale token
    if (!endpoint.includes("/auth/login")) {
      setAuthToken(null);
    }
  }

  if (!response.ok) {
    const errorText = await response.text();
    let parsedMessage = `HTTP error! status: ${response.status}`;
    try {
      const parsed = JSON.parse(errorText);
      if (typeof parsed.detail === "string") {
        parsedMessage = parsed.detail;
      } else if (parsed.detail) {
        parsedMessage = JSON.stringify(parsed.detail);
      }
    } catch {
      if (errorText) parsedMessage = errorText;
    }
    throw new Error(parsedMessage);
  }

  if (response.status === 204) return null as T;
  const text = await response.text();
  return text ? (JSON.parse(text) as T) : (null as T);
}
```

- [ ] **Step 4: Verify build with TypeScript compiler**

Run: `npm --prefix frontend run build`
Expected: Build succeeds with 0 errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/auth/types.ts frontend/src/features/auth/api/auth.api.ts frontend/src/lib/http.ts
git commit -m "feat(frontend): add auth API client, types, and http interceptor"
```

---

### Task 5: Frontend Auth Context & State Management

**Files:**
- Create: `frontend/src/features/auth/context/AuthContext.tsx`
- Create: `frontend/src/features/auth/context/useAuth.ts`
- Modify: `frontend/src/app/providers.tsx`

**Interfaces:**
- Consumes: `authApi`, `getAuthToken`, `setAuthToken`
- Produces: `AuthProvider`, `useAuth()` hook delivering `{ user, token, isAuthenticated, isLoading, login, logout }`.

- [ ] **Step 1: Create `frontend/src/features/auth/context/AuthContext.tsx`**

```tsx
import { createContext, useCallback, useEffect, useState, type ReactNode } from "react";
import { getAuthToken, setAuthToken } from "@/lib/http";
import { authApi } from "../api/auth.api";
import type { AuthContextType, LoginCredentials, User } from "../types";

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setTokenState] = useState<string | null>(() => getAuthToken());
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const logout = useCallback(() => {
    setAuthToken(null);
    setTokenState(null);
    setUser(null);
  }, []);

  const login = useCallback(async (credentials: LoginCredentials) => {
    const res = await authApi.login(credentials);
    setAuthToken(res.access_token);
    setTokenState(res.access_token);
    setUser(res.user);
  }, []);

  useEffect(() => {
    let isMounted = true;
    const initialToken = getAuthToken();

    if (!initialToken) {
      setIsLoading(false);
      return;
    }

    authApi
      .getMe()
      .then((userData) => {
        if (isMounted) {
          setUser(userData);
          setIsLoading(false);
        }
      })
      .catch(() => {
        if (isMounted) {
          logout();
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [logout]);

  const value: AuthContextType = {
    user,
    token,
    isAuthenticated: !!user && !!token,
    isLoading,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
```

- [ ] **Step 2: Create `frontend/src/features/auth/context/useAuth.ts`**

```tsx
import { useContext } from "react";
import { AuthContext } from "./AuthContext";
import type { AuthContextType } from "../types";

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
```

- [ ] **Step 3: Register `AuthProvider` in `frontend/src/app/providers.tsx`**

Modify `frontend/src/app/providers.tsx`:

```tsx
import type { ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/lib/queryClient";
import { AppProvider } from "@/context/AppContext";
import { AuthProvider } from "@/features/auth/context/AuthContext";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AppProvider>{children}</AppProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
```

- [ ] **Step 4: Verify build with TypeScript compiler**

Run: `npm --prefix frontend run build`
Expected: Build succeeds with 0 errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/auth/context/AuthContext.tsx frontend/src/features/auth/context/useAuth.ts frontend/src/app/providers.tsx
git commit -m "feat(frontend): create AuthContext and register AuthProvider"
```

---

### Task 6: Frontend Route Guard (`ProtectedRoute`), Login UI, and Router Configuration

**Files:**
- Create: `frontend/src/features/auth/components/LoginForm.tsx`
- Create: `frontend/src/features/auth/pages/LoginPage.tsx`
- Create: `frontend/src/features/auth/components/ProtectedRoute.tsx`
- Create: `frontend/src/features/auth/index.ts`
- Modify: `frontend/src/app/router.tsx`

**Interfaces:**
- Consumes: `useAuth()`, `LoginForm`, `ProtectedRoute`
- Produces: Login screen, redirection flow, and protected dashboard routing.

- [ ] **Step 1: Create `frontend/src/features/auth/components/LoginForm.tsx`**

```tsx
import { useState, type FormEvent } from "react";
import { Lock, User, AlertCircle, Loader2, Eye, EyeOff } from "lucide-react";
import { useAuth } from "../context/useAuth";

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
      setError("Silakan isi nama pengguna dan kata sandi.");
      return;
    }

    setError(null);
    setIsSubmitting(true);
    try {
      await login({ username: username.trim(), password });
      onSuccess?.();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Gagal masuk ke sistem";
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
    <div className="w-full max-w-md bg-slate-800/90 border border-slate-700/80 rounded-2xl p-6 sm:p-8 shadow-2xl backdrop-blur-sm">
      <div className="mb-6 text-center">
        <h1 className="text-2xl font-bold text-white tracking-tight">Masuk ke Sistem</h1>
        <p className="text-sm text-slate-400 mt-1">Lihat.id Poultry Counter Central Dashboard</p>
      </div>

      {error && (
        <div
          role="alert"
          className="mb-5 p-3.5 bg-rose-500/10 border border-rose-500/30 rounded-xl flex items-start gap-3 text-rose-400 text-sm"
        >
          <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
            Nama Pengguna
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
              <User className="w-4 h-4" />
            </div>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="admin / operator"
              required
              autoFocus
              className="w-full pl-10 pr-4 py-2.5 bg-slate-900/80 border border-slate-700 rounded-xl text-white placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
            Kata Sandi
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
              <Lock className="w-4 h-4" />
            </div>
            <input
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              className="w-full pl-10 pr-10 py-2.5 bg-slate-900/80 border border-slate-700 rounded-xl text-white placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-200"
              tabIndex={-1}
            >
              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full mt-2 py-2.5 px-4 bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 disabled:opacity-50 text-white rounded-xl text-sm font-semibold shadow-lg shadow-emerald-900/30 flex items-center justify-center gap-2 transition-all cursor-pointer"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Memverifikasi...</span>
            </>
          ) : (
            <span>Masuk</span>
          )}
        </button>
      </form>

      {/* Demo Credentials Quick-Fill helper */}
      <div className="mt-6 pt-5 border-t border-slate-700/60">
        <p className="text-xs text-slate-400 text-center mb-2.5">Pilih akun demonstrasi:</p>
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => handleQuickFill("admin", "admin123")}
            className="py-1.5 px-3 bg-slate-700/60 hover:bg-slate-700 border border-slate-600/50 rounded-lg text-xs font-medium text-slate-200 transition-colors"
          >
            Admin (admin123)
          </button>
          <button
            type="button"
            onClick={() => handleQuickFill("operator", "operator123")}
            className="py-1.5 px-3 bg-slate-700/60 hover:bg-slate-700 border border-slate-600/50 rounded-lg text-xs font-medium text-slate-200 transition-colors"
          >
            Operator (operator123)
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/src/features/auth/pages/LoginPage.tsx`**

```tsx
import { useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { LoginForm } from "../components/LoginForm";
import { useAuth } from "../context/useAuth";

export default function LoginPage() {
  const { isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const destination = (location.state as { from?: { pathname?: string } })?.from?.pathname || "/";

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      navigate(destination, { replace: true });
    }
  }, [isAuthenticated, isLoading, navigate, destination]);

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-4 relative overflow-hidden">
      {/* Decorative ambient background */}
      <div className="absolute top-1/4 -left-32 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 -right-32 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

      <LoginForm onSuccess={() => navigate(destination, { replace: true })} />

      <footer className="mt-8 text-center text-xs text-slate-500">
        &copy; {new Date().getFullYear()} Lihat.id Computer Vision Poultry Counter System
      </footer>
    </div>
  );
}
```

- [ ] **Step 3: Create `frontend/src/features/auth/components/ProtectedRoute.tsx`**

```tsx
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { ShieldAlert } from "lucide-react";
import { useAuth } from "../context/useAuth";

interface ProtectedRouteProps {
  children?: ReactNode;
  allowedRoles?: string[];
}

export function ProtectedRoute({ children, allowedRoles }: ProtectedRouteProps) {
  const { user, isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[350px]">
        <div className="w-8 h-8 border-3 border-emerald-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (allowedRoles && user) {
    const userRole = (user.role || "").toLowerCase();
    const hasRole = allowedRoles.some((r) => r.toLowerCase() === userRole);
    if (!hasRole) {
      return (
        <div className="flex flex-col items-center justify-center min-h-[400px] p-6 text-center">
          <div className="w-14 h-14 rounded-2xl bg-amber-500/10 text-amber-500 flex items-center justify-center mb-4">
            <ShieldAlert className="w-7 h-7" />
          </div>
          <h2 className="text-xl font-bold text-slate-900 mb-2">Akses Ditolak</h2>
          <p className="text-sm text-slate-500 max-w-md mb-6">
            Akun Anda ({user.username} - {user.role}) tidak memiliki izin untuk mengakses halaman ini. Halaman ini memerlukan peran: {allowedRoles.join(", ")}.
          </p>
        </div>
      );
    }
  }

  return <>{children}</>;
}
```

- [ ] **Step 4: Create barrel export in `frontend/src/features/auth/index.ts`**

```ts
export * from "./types";
export * from "./api/auth.api";
export * from "./context/AuthContext";
export * from "./context/useAuth";
export * from "./components/ProtectedRoute";
export * from "./components/LoginForm";
```

- [ ] **Step 5: Wire routes in `frontend/src/app/router.tsx`**

Update `frontend/src/app/router.tsx` to include `/login` and wrap dashboard children in `ProtectedRoute`:

```tsx
import { lazy, Suspense } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { ProtectedRoute } from "@/features/auth";

const LoginPage = lazy(() => import("@/features/auth/pages/LoginPage"));
const DashboardPage = lazy(() => import("@/features/overview/pages/DashboardPage"));
const LiniProduksiPage = lazy(() => import("@/features/livestream/pages/LiniProduksiPage"));
const AlarmPage = lazy(() => import("@/features/alarms/pages/AlarmPage"));
const LaporanPage = lazy(() => import("@/features/reports/pages/LaporanPage"));
const PengaturanPage = lazy(() => import("@/features/settings/pages/PengaturanPage"));

const PageLoader = () => (
  <div
    role="status"
    aria-label="Memuat halaman..."
    className="flex items-center justify-center min-h-[300px]"
  >
    <div className="w-6 h-6 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin" />
  </div>
);

function RouteErrorBoundary() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] p-6 text-center">
      <h2 className="text-xl font-semibold text-slate-900 mb-2">Terjadi Kesalahan</h2>
      <p className="text-sm text-slate-500 mb-4">Gagal memuat halaman atau terjadi masalah koneksi.</p>
      <button
        type="button"
        onClick={() => window.location.reload()}
        className="px-4 py-2 bg-emerald-600 text-white rounded-md text-sm font-medium hover:bg-emerald-700 transition-colors"
      >
        Muat Ulang
      </button>
    </div>
  );
}

export const router = createBrowserRouter([
  {
    path: "/login",
    element: (
      <Suspense fallback={<PageLoader />}>
        <LoginPage />
      </Suspense>
    ),
    errorElement: <RouteErrorBoundary />,
  },
  {
    path: "/",
    element: (
      <ProtectedRoute>
        <AppShell />
      </ProtectedRoute>
    ),
    errorElement: <RouteErrorBoundary />,
    children: [
      {
        index: true,
        element: (
          <Suspense fallback={<PageLoader />}>
            <DashboardPage />
          </Suspense>
        ),
      },
      {
        path: "lini-produksi",
        element: (
          <Suspense fallback={<PageLoader />}>
            <LiniProduksiPage />
          </Suspense>
        ),
      },
      {
        path: "alarm",
        element: (
          <Suspense fallback={<PageLoader />}>
            <AlarmPage />
          </Suspense>
        ),
      },
      {
        path: "laporan",
        element: (
          <Suspense fallback={<PageLoader />}>
            <LaporanPage />
          </Suspense>
        ),
      },
      {
        path: "pengaturan",
        element: (
          <Suspense fallback={<PageLoader />}>
            <PengaturanPage />
          </Suspense>
        ),
      },
      {
        path: "*",
        element: <Navigate to="/" replace />,
      },
    ],
  },
]);
```

- [ ] **Step 6: Verify build with TypeScript compiler**

Run: `npm --prefix frontend run build`
Expected: Build succeeds with 0 errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/auth/ frontend/src/app/router.tsx
git commit -m "feat(frontend): add ProtectedRoute, LoginPage, and configure router guards"
```

---

### Task 7: Dynamic User Profile & Logout in Header

**Files:**
- Modify: `frontend/src/components/layout/Header.tsx`

**Interfaces:**
- Consumes: `useAuth` from `@/features/auth`
- Produces: Dynamic username display, role badge (`Admin` / `Operator`), and Logout trigger.

- [ ] **Step 1: Update `frontend/src/components/layout/Header.tsx`**

Modify `frontend/src/components/layout/Header.tsx`:

```tsx
import { useState, useEffect } from "react";
import { Menu, Bell, User, LogOut } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { alarmsApi } from "@/features/alarms";
import { useAuth } from "@/features/auth";

interface HeaderProps {
  onOpenSidebar: () => void;
}

export function Header({ onOpenSidebar }: HeaderProps) {
  const [activeCount, setActiveCount] = useState(0);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    let isMounted = true;

    const fetchAlarms = () => {
      alarmsApi
        .list()
        .then((alarms) => {
          if (isMounted && Array.isArray(alarms)) {
            const count = alarms.filter((a) => a.status !== "RESOLVED").length;
            setActiveCount(count);
          }
        })
        .catch(() => {
          // Keep current state on error
        });
    };

    fetchAlarms();
    const interval = setInterval(fetchAlarms, 10000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  const isAdmin = (user?.role || "").toLowerCase() === "admin";

  return (
    <header className="h-16 bg-white px-4 sm:px-8 flex items-center justify-between sticky top-0 z-30 border-b border-slate-100">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onOpenSidebar}
          aria-label="Buka navigasi menu"
          className="p-1.5 rounded-lg text-slate-600 hover:bg-slate-100 lg:hidden"
        >
          <Menu className="w-5 h-5" />
        </button>
      </div>

      <div className="flex items-center gap-3 sm:gap-4">
        {/* Notification bell button */}
        <Link
          to="/alarm"
          aria-label="Lihat alarm"
          className="relative p-2 rounded-xl text-slate-600 hover:bg-slate-100 transition-colors border border-slate-200"
        >
          <Bell className="w-5 h-5" />
          {activeCount > 0 && (
            <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 bg-rose-500 text-white rounded-full text-[10px] font-bold flex items-center justify-center">
              {activeCount > 99 ? "99+" : activeCount}
            </span>
          )}
        </Link>

        {/* Dynamic User Profile Badge */}
        <div className="flex items-center gap-2 bg-slate-900 text-white pl-3.5 pr-1.5 py-1.5 rounded-full text-xs font-medium shadow-sm">
          <div className="flex flex-col items-start leading-none pr-1">
            <span className="font-semibold text-slate-100">{user?.username || "Pengguna"}</span>
            <span className={`text-[10px] font-bold uppercase mt-0.5 ${isAdmin ? "text-indigo-400" : "text-emerald-400"}`}>
              {user?.role || "Operator"}
            </span>
          </div>
          <div className={`w-7 h-7 rounded-full flex items-center justify-center text-white ${isAdmin ? "bg-indigo-600" : "bg-emerald-600"}`}>
            <User className="w-3.5 h-3.5" />
          </div>
        </div>

        {/* Logout Button */}
        <button
          type="button"
          onClick={handleLogout}
          title="Keluar dari sistem"
          aria-label="Keluar dari sistem"
          className="p-2 rounded-xl text-slate-500 hover:text-rose-600 hover:bg-rose-50 border border-slate-200 transition-colors cursor-pointer"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}
```

- [ ] **Step 2: Verify build with TypeScript compiler**

Run: `npm --prefix frontend run build`
Expected: Build succeeds with 0 errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/layout/Header.tsx
git commit -m "feat(frontend): display dynamic user badge and logout action in Header"
```

---

### Task 8: End-to-End Verification & Health Check

**Files:**
- Create: `services/api/tests/test_e2e_auth_flow.py`

**Interfaces:**
- Validates the entire full-stack auth lifecycle: default seeding -> login -> me -> protected endpoints -> RBAC differentiation -> logout.

- [ ] **Step 1: Write comprehensive end-to-end integration test**

Create `services/api/tests/test_e2e_auth_flow.py`:

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api.src.main import app, init_db
from services.api.src.db.session import get_db


@pytest.fixture
def e2e_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Seed default lines and accounts
    init_db(target_engine=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        with TestingSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_complete_auth_lifecycle(e2e_client):
    # 1. Unauthenticated request to /me is rejected
    res_me_unauth = e2e_client.get("/api/v1/auth/me")
    assert res_me_unauth.status_code == 401

    # 2. Login as seeded operator
    res_login_op = e2e_client.post(
        "/api/v1/auth/login",
        json={"username": "operator", "password": "operator123"},
    )
    assert res_login_op.status_code == 200
    op_token = res_login_op.json()["access_token"]
    assert res_login_op.json()["user"]["username"] == "operator"
    assert res_login_op.json()["user"]["role"] == "operator"

    # 3. Authenticated request to /me
    res_me_op = e2e_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {op_token}"},
    )
    assert res_me_op.status_code == 200
    assert res_me_op.json()["username"] == "operator"

    # 4. Operator reads lines
    res_lines_op = e2e_client.get(
        "/api/v1/lines",
        headers={"Authorization": f"Bearer {op_token}"},
    )
    assert res_lines_op.status_code == 200
    assert len(res_lines_op.json()) >= 2  # seeded line-1 and lineA

    # 5. Operator attempts to create line (forbidden)
    res_create_op = e2e_client.post(
        "/api/v1/lines",
        json={"id": "line-forbidden", "name": "Illegal Line", "daily_target": 1000},
        headers={"Authorization": f"Bearer {op_token}"},
    )
    assert res_create_op.status_code == 403

    # 6. Login as seeded admin
    res_login_admin = e2e_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert res_login_admin.status_code == 200
    admin_token = res_login_admin.json()["access_token"]

    # 7. Admin creates line (authorized)
    res_create_admin = e2e_client.post(
        "/api/v1/lines",
        json={"id": "line-allowed", "name": "Admin Created Line", "daily_target": 1000},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_create_admin.status_code == 201

    # 8. Unauthenticated edge sync works seamlessly
    res_sync = e2e_client.post(
        "/api/v1/sync/batch",
        json={"line_id": "line-1", "events": [], "aggregates": [], "health": None},
    )
    assert res_sync.status_code == 200
```

- [ ] **Step 2: Run all backend tests**

Run: `py -m pytest services/api/tests/ -v`
Expected: ALL tests pass (155+ passed, 0 failed).

- [ ] **Step 3: Run full frontend build**

Run: `npm --prefix frontend run build`
Expected: Build succeeds with 0 errors.

- [ ] **Step 4: Commit**

```bash
git add services/api/tests/test_e2e_auth_flow.py
git commit -m "test: add comprehensive end-to-end auth lifecycle integration test"
```
