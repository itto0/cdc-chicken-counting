# Full-Stack Authentication & RBAC System Design

## 1. Overview
This design specifies the end-to-end authentication and Role-Based Access Control (RBAC) system for the **Lihat.id Poultry Counter** platform. The system bridges the existing FastAPI backend JWT infrastructure with the React 18 / Vite frontend dashboard, while ensuring backwards-compatible operation for edge camera counters and browser media streams.

### Key Objectives
1. **User Authentication:** Enable operators and administrators to log in using credentials, obtain JWT access tokens, and securely persist session state.
2. **Access Control (RBAC):** Differentiate between `admin` (full configuration and management access) and `operator` (viewing dashboards, monitoring production lines, acknowledging alarms) across backend APIs and frontend navigation.
3. **Protected Navigation:** Shield dashboard routes (`/`, `/lini-produksi`, `/alarm`, `/laporan`, `/pengaturan`) behind authentication guards, automatically redirecting unauthenticated users to `/login`.
4. **Resilient Edge Device Operations:** Ensure edge counter batch sync (`/api/v1/sync/batch`) and image feeds (`/api/v1/lines/{id}/preview`) remain operable without breaking automated counter services or browser `<img>` rendering.

---

## 2. Backend Architecture & Security

### 2.1 Database Seeding & User Model
* **Model:** Leverages the existing `User` model in `services/api/src/db/models.py`:
  - `id`: Integer primary key.
  - `username`: String (unique, indexed).
  - `password_hash`: String (PBKDF2 with SHA-256 and unique salt).
  - `role`: String (`admin` or `operator`).
  - `is_active`: Boolean (default `True`).
  - `created_at` / `updated_at`: Timestamps.
* **Automatic Startup Seeding:**
  - In `init_db()` (`services/api/src/db/session.py` or startup event in `services/api/src/main.py`), verify if any records exist in the `users` table.
  - If empty, automatically seed two default accounts:
    - **Administrator:** Username `admin`, Password `admin123`, Role `admin`.
    - **Field Operator:** Username `operator`, Password `operator123`, Role `operator`.
  - Passwords are encrypted using `services.auth.hash_password`.

### 2.2 FastAPI Dependencies & RBAC
* **`get_current_user` Dependency:**
  - Extracts JWT token from the `Authorization: Bearer <token>` header via `fastapi.security.HTTPBearer(auto_error=True)`.
  - Decodes token using existing `services.auth.decode_token(token)`.
  - Queries active user from database session; raises `HTTPException(status_code=401, detail="Invalid credentials or token expired", headers={"WWW-Authenticate": "Bearer"})` on invalid tokens or deactivated users.
* **`require_role(allowed_roles: list[str])` Guard:**
  - A dependency factory that validates `current_user.role in allowed_roles`.
  - Raises `HTTPException(status_code=403, detail="Forbidden: Insufficient privileges")` if the user's role is not authorized.

### 2.3 Route Protection Matrix
* **Public Endpoints:**
  - `POST /api/v1/auth/login` - User login and token generation.
  - `GET /healthz` - Health probe.
  - `GET /api/v1/lines/{id}/preview` - MJPEG live stream (permits browser `<img>` tags without manual bearer headers; supports optional query parameter token if configured).
* **Edge Device Sync Endpoint:**
  - `POST /api/v1/sync/batch` - Accepts batch detections. Protected with an optional device secret header `X-Device-Token` (or bypassed in dev mode) so running edge counter services do not fail.
* **Protected Dashboard Endpoints (`Depends(get_current_user)`):**
  - `GET /api/v1/auth/me` - Active session profile.
  - `GET /api/v1/lines`, `GET /api/v1/lines/{id}` - Read line configurations.
  - `GET /api/v1/counts/*` - Real-time and historical count data.
  - `GET /api/v1/alarms/*` - Active and historical alarms.
  - `POST /api/v1/alarms/{id}/ack` - Operator alarm acknowledgment.
  - `GET /api/v1/reports/*` - Report generation and summary exports.
  - `GET /api/v1/summary` - Overview dashboard metrics.
* **Admin-Restricted Endpoints (`Depends(require_role(["admin"]))`):**
  - `POST /api/v1/lines` - Create production line.
  - `PUT /api/v1/lines/{id}` - Update production line configuration.
  - `DELETE /api/v1/lines/{id}` - Remove production line.

---

## 3. Frontend Architecture & State Management

### 3.1 Directory & Feature Structure
Adhering to `docs/fe-architecture.md`, auth functionality is organized as a dedicated feature module:
```text
frontend/src/features/auth/
├── api/
│   └── auth.api.ts              # API calls (login, getMe) using http client
├── context/
│   ├── AuthContext.tsx          # React Context, Provider, and session bootstrapping
│   └── useAuth.ts               # Custom hook for consuming auth state
├── components/
│   ├── LoginForm.tsx            # Form UI, validation, and error alert
│   └── ProtectedRoute.tsx       # Route guard for authentication and roles
├── pages/
│   └── LoginPage.tsx            # Full-page login container with branding
└── types.ts                     # TypeScript interfaces (User, AuthState, LoginCredentials)
```

### 3.2 State & Storage Contract
* **Storage Key:** `localStorage.getItem("lihat_auth_token")`
* **Session Lifecycle:**
  1. **Bootstrapping:** On initial app mount, `AuthProvider` reads `lihat_auth_token`.
  2. **Hydration:** If a token exists, `AuthProvider` sets `isLoading = true` and invokes `GET /api/v1/auth/me`.
     - *Success:* Populates `user` and sets `isAuthenticated = true`.
     - *Failure (401 / Network error):* Removes token, sets `user = null`, `isAuthenticated = false`.
  3. **Login:** `login(username, password)` submits to `POST /api/v1/auth/login`, stores `access_token`, hydrates `user`, and navigates to the intended route or `/`.
  4. **Logout:** `logout()` clears `localStorage`, clears auth context, and navigates to `/login`.

### 3.3 HTTP Client & Interceptors (`frontend/src/services/http.ts`)
* **Request Interceptor:**
  - Automatically attaches `Authorization: Bearer <token>` to all outgoing API requests when `getAuthToken()` returns a valid token.
* **Response Interceptor:**
  - Detects `401 Unauthorized` responses from protected endpoints.
  - Clears `lihat_auth_token` and triggers a global auth expiration event or redirects the browser to `/login?session_expired=true`.
  - Skips redirect logic when the 401 is triggered by `/api/v1/auth/login` itself (to display standard invalid password feedback).

### 3.4 Route Guards (`frontend/src/router.tsx`)
* **`ProtectedRoute`**:
  - Checks `isLoading`: Renders a centered loading spinner to avoid route flicker during initial hydration.
  - Checks `!isAuthenticated`: Redirects to `/login`, storing current path in `location.state.from`.
  - Checks `requiredRole`: If the user role does not match (e.g. non-admin accessing `/pengaturan`), renders an access denied view or redirects to `/`.
* **Login Route (`/login`)**:
  - If an already authenticated user navigates to `/login`, redirects them immediately to `/`.

---

## 4. UI Components & User Experience

### 4.1 Login Page & Form (`LoginPage.tsx`, `LoginForm.tsx`)
* **Visual Presentation:**
  - Modern, high-contrast industrial dashboard theme (Dark slate/zinc `#0f172a`, `#1e293b`).
  - Brand header featuring poultry counter icon, title "Lihat.id Counter", and subtitle "Sistem Monitoring & Penghitung Ayam Otomatis".
* **Form Inputs & Feedback:**
  - Username / ID Operator input field with auto-focus.
  - Password input field with toggleable show/hide password visibility.
  - Submit button with dynamic spinner ("Memproses...").
  - Clean error banner displaying server or network errors ("Username atau kata sandi salah").
  - Quick-start helper card displaying default credentials (`admin / admin123` & `operator / operator123`) for seamless field trials.

### 4.2 Header User Status & Logout (`Header.tsx`)
* **Dynamic User Indicator:**
  - Replaces static "Operator Lapangan" label with dynamic user details from `useAuth()`.
  - Displays user's username alongside a color-coded role badge:
    - **Admin:** `bg-indigo-500/20 text-indigo-400 border border-indigo-500/30`
    - **Operator:** `bg-emerald-500/20 text-emerald-400 border border-emerald-500/30`
* **Logout Button:**
  - Logout action button with Lucide `LogOut` icon.
  - Prompts immediate sign-out and cleanly returns the user to the login screen.

---

## 5. Error Handling & Edge Cases
1. **Expired or Tampered Tokens:** If the backend rejects a JWT token with 401, the frontend catches the error, purges local storage, and prompts the user to log in again without unhandled promise crashes.
2. **Offline / Backend Down:** If the backend is unreachable during login, `LoginForm` renders a friendly "Server backend tidak dapat dihubungi. Periksa koneksi Anda." alert.
3. **Browser Refresh:** Preserves session seamlessly across refreshes via `localStorage` and `getMe` verification.
4. **Direct URL Navigation:** Deep links to `/lini-produksi` or `/laporan` preserve the target route in state and redirect back after successful login.
5. **Edge Device Resilience:** If edge counter services push batches without user tokens, the endpoint permits the sync or checks optional device tokens without blocking operational counting.

---

## 6. Testing & Verification Plan

### 6.1 Backend Tests (`py -m pytest services/api/tests/`)
* **Auth Core & Seeding:**
  - Verify default users (`admin` & `operator`) are initialized upon fresh database setup.
  - Verify `POST /api/v1/auth/login` succeeds with valid passwords and fails with invalid passwords or non-existent users.
  - Verify `GET /api/v1/auth/me` returns the authenticated user's profile and rejects missing or malformed tokens.
* **RBAC & Endpoint Protection:**
  - Verify unauthenticated requests to `/api/v1/lines`, `/api/v1/summary`, `/api/v1/counts` return 401.
  - Verify operator token can access `/api/v1/lines` (GET), but receives 403 on `POST /api/v1/lines`.
  - Verify admin token can perform `POST /api/v1/lines`.
  - Verify `/api/v1/sync/batch` continues to function for counter device sync.

### 6.2 Frontend Tests & Build (`npm run build`, `npm run test`)
* **Type Safety & Build:** Run `npm --prefix frontend run build` to verify zero TypeScript errors.
* **Component & Context Unit Tests:**
  - Test `LoginForm`: renders inputs, validates required fields, triggers login on submit, and displays error messages on rejection.
  - Test `ProtectedRoute`: redirects unauthenticated visitors to `/login`, renders child routes when authenticated.
  - Test `AuthContext`: verifies session loading, token storage, and logout state reset.
