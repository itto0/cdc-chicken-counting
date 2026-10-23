# User Management & Self-Service Password System Design

## 1. Overview
This design specifies the end-to-end user management and self-service credential system for the **Lihat.id Poultry Counter** platform. It expands the existing authentication infrastructure (`services/api/src/api/auth.py` and `frontend/src/features/auth/`) to provide administrators with full lifecycle control over operator and administrator accounts, while enabling all authenticated users to manage their own passwords.

### Key Objectives
1. **User Lifecycle Management (Admin Only):** Provide administrators with a centralized UI and REST API to create users, view user lists, update roles (`admin` or `operator`), toggle active status, reset user passwords, and delete accounts.
2. **Administrative Safety Guards:** Protect against accidental system lockouts by preventing administrators from deleting their own accounts, deactivating their own accounts, or demoting/deactivating the last active administrator.
3. **Self-Service Password Management:** Allow any authenticated user (both `admin` and `operator`) to change their account password from the application header after verifying their current password.
4. **Cohesive Frontend Integration:** Introduce a dedicated sidebar navigation item (*"Manajemen Pengguna"* at `/pengguna`) restricted to `admin` roles, and extend the user profile badge in the navigation header with a *"Ganti Password"* dialog.

---

## 2. Backend Architecture & API Specification

### 2.1 Database & Encryption
* **Database Model:** Reuses `User` in `services/api/src/db/models.py`:
  - `id`: Integer primary key
  - `username`: String(50), unique, indexed
  - `password_hash`: String(255)
  - `role`: String(20), values: `"admin"` or `"operator"`
  - `is_active`: Boolean, default `True`
  - `created_at` / `updated_at`: Timestamps
* **Password Hashing:** Uses `services.services.auth.hash_password` (PBKDF2 HMAC SHA-256 with 100,000 iterations and salt) and `verify_password`.

### 2.2 Pydantic Schemas (`services/api/src/api/auth.py`)
* **`UserResponse`:**
  - `id`: `int`
  - `username`: `str`
  - `role`: `str`
  - `is_active`: `bool`
  - `created_at`: `datetime | None`
  - *(Note: `password_hash` is strictly excluded)*
* **`UserCreateRequest`:**
  - `username`: `str` (min length: 3, max length: 50, pattern: `^[a-zA-Z0-9_-]+$`)
  - `password`: `str` (min length: 6)
  - `role`: `str` (Literal: `"admin"` | `"operator"`, default: `"operator"`)
* **`UserUpdateRequest`:**
  - `role`: `str` (Literal: `"admin"` | `"operator"`)
  - `is_active`: `bool`
* **`AdminResetPasswordRequest`:**
  - `new_password`: `str` (min length: 6)
* **`ChangePasswordRequest`:**
  - `current_password`: `str`
  - `new_password`: `str` (min length: 6)

### 2.3 REST Endpoints

All endpoints are registered under the `/api/v1/auth` router:

#### A. `GET /api/v1/auth/users`
- **Access:** Admin only (`Depends(require_role(["admin"]))`).
- **Response:** `200 OK`, `list[UserResponse]`.
- **Behavior:** Returns all registered users ordered by `id` ascending.

#### B. `POST /api/v1/auth/users`
- **Access:** Admin only (`Depends(require_role(["admin"]))`).
- **Request Body:** `UserCreateRequest`.
- **Response:** `201 Created`, `UserResponse`.
- **Validation:**
  - If `username` already exists (case-insensitive check), raises `HTTPException(409, "Username already exists")`.
  - Hashes password using `hash_password(payload.password)`.

#### C. `PUT /api/v1/auth/users/{user_id}`
- **Access:** Admin only (`Depends(require_role(["admin"]))`).
- **Path Parameter:** `user_id: int`.
- **Request Body:** `UserUpdateRequest`.
- **Response:** `200 OK`, `UserResponse`.
- **Safety Checks:**
  1. Fetch target user: if not found, raise `HTTPException(404, "User not found")`.
  2. **Self-deactivation guard:** If `target_user.id == current_user.id` and `payload.is_active is False`, raise `HTTPException(400, "Cannot deactivate your own account")`.
  3. **Last active admin guard:** If target user is an active admin (`target_user.role == "admin"` and `target_user.is_active is True`), and the update either changes role to `"operator"` or sets `is_active = False`:
     - Query count of active admins: `SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = True`.
     - If count <= 1, raise `HTTPException(400, "Cannot demote or deactivate the last active administrator")`.

#### D. `PUT /api/v1/auth/users/{user_id}/password`
- **Access:** Admin only (`Depends(require_role(["admin"]))`).
- **Path Parameter:** `user_id: int`.
- **Request Body:** `AdminResetPasswordRequest`.
- **Response:** `200 OK`, `{"message": "Password reset successfully"}`.
- **Behavior:**
  - If user not found, raise `HTTPException(404, "User not found")`.
  - Sets `target_user.password_hash = hash_password(payload.new_password)`.

#### E. `DELETE /api/v1/auth/users/{user_id}`
- **Access:** Admin only (`Depends(require_role(["admin"]))`).
- **Path Parameter:** `user_id: int`.
- **Response:** `200 OK`, `{"message": "User deleted successfully"}`.
- **Safety Checks:**
  1. If user not found, raise `HTTPException(404, "User not found")`.
  2. **Self-deletion guard:** If `target_user.id == current_user.id`, raise `HTTPException(400, "Cannot delete your own account")`.
  3. **Last active admin guard:** If `target_user.role == "admin"` and `target_user.is_active is True`:
     - Count active admins: `SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = True`.
     - If count <= 1, raise `HTTPException(400, "Cannot delete the last active administrator")`.

#### F. `PUT /api/v1/auth/password`
- **Access:** Any authenticated user (`Depends(get_current_user)`).
- **Request Body:** `ChangePasswordRequest`.
- **Response:** `200 OK`, `{"message": "Password changed successfully"}`.
- **Behavior:**
  - Verifies `current_password` with `verify_password(payload.current_password, current_user.password_hash)`.
  - If verification fails, raise `HTTPException(400, "Current password is incorrect")`.
  - If `payload.new_password == payload.current_password`, raise `HTTPException(400, "New password cannot be the same as current password")`.
  - Sets `current_user.password_hash = hash_password(payload.new_password)`.

---

## 3. Frontend Architecture & UI Specification

### 3.1 Feature Module Structure (`frontend/src/features/users/`)
```text
frontend/src/features/users/
├── api/
│   └── users.api.ts            # API client calls for CRUD and password operations
├── types/
│   └── index.ts                # TypeScript interfaces (User, CreateUserDTO, UpdateUserDTO, etc.)
├── components/
│   ├── CreateUserModal.tsx     # Modal to add user
│   ├── EditUserModal.tsx       # Modal to edit user role and active status
│   ├── ResetPasswordModal.tsx  # Admin modal to reset user password
│   ├── DeleteUserModal.tsx     # Confirmation dialog for deleting user
│   └── ChangePasswordModal.tsx # Dialog for self-service password update
└── pages/
    └── PenggunaPage.tsx        # Main management page
```

### 3.2 Types & Interfaces (`frontend/src/features/users/types/index.ts`)
```typescript
export type UserRole = 'admin' | 'operator';

export interface User {
  id: number;
  username: string;
  role: UserRole;
  is_active: boolean;
  created_at?: string;
}

export interface CreateUserPayload {
  username: string;
  password: string;
  role: UserRole;
}

export interface UpdateUserPayload {
  role: UserRole;
  is_active: boolean;
}

export interface AdminResetPasswordPayload {
  new_password: string;
}

export interface ChangePasswordPayload {
  current_password: string;
  new_password: string;
}
```

### 3.3 API Client (`frontend/src/features/users/api/users.api.ts`)
Exports helper functions wrapping `http` from `src/services/http`:
- `getUsers(): Promise<User[]>` -> `GET /api/v1/auth/users`
- `createUser(payload: CreateUserPayload): Promise<User>` -> `POST /api/v1/auth/users`
- `updateUser(id: number, payload: UpdateUserPayload): Promise<User>` -> `PUT /api/v1/auth/users/${id}`
- `adminResetPassword(id: number, payload: AdminResetPasswordPayload): Promise<{ message: string }>` -> `PUT /api/v1/auth/users/${id}/password`
- `deleteUser(id: number): Promise<{ message: string }>` -> `DELETE /api/v1/auth/users/${id}`
- `changePassword(payload: ChangePasswordPayload): Promise<{ message: string }>` -> `PUT /api/v1/auth/password`

### 3.4 Page & Component Details

#### 1. `PenggunaPage.tsx`
- **Access Guard:** Wrapped in `ProtectedRoute` with `requiredRole="admin"`.
- **Top Bar:** Page header with title *"Manajemen Pengguna"*, description *"Kelola akun pengguna, hak akses, dan keamanan sistem"*, and button `Tambah Pengguna`.
- **Search & Filters:**
  - Text input to filter table rows by username.
  - Dropdown/pill selector to filter by role: `Semua`, `Admin`, `Operator`.
- **Data Table:**
  - Columns:
    1. **Pengguna:** Username with avatar icon; badge `(Anda)` if `user.id === currentUser.id`.
    2. **Peran:** Badge (Purple for `admin`, Slate for `operator`).
    3. **Status:** Badge (Green for `Aktif`, Red for `Nonaktif`).
    4. **Aksi:** Action buttons:
       - *Edit* (`Edit2` / `Pencil` icon): opens `EditUserModal`.
       - *Reset Password* (`Key` icon): opens `ResetPasswordModal`.
       - *Hapus* (`Trash2` icon): opens `DeleteUserModal`.
  - **Self-Protection UI:** If `user.id === currentUser.id`, the delete button is disabled with title *"Anda tidak dapat menghapus akun Anda sendiri"*.

#### 2. Modals
- **`CreateUserModal`:**
  - Fields: `username`, `password` (masked with show/hide toggle), `role` (select: `admin` | `operator`).
  - Validation: username required (min 3 chars), password min 6 chars.
- **`EditUserModal`:**
  - Fields: `role` (select), `is_active` (toggle or checkbox).
  - Safety check: If editing self, the `is_active` toggle is disabled with a note *"Anda tidak dapat menonaktifkan akun sendiri"*.
- **`ResetPasswordModal`:**
  - Fields: `new_password`, `confirm_password`.
  - Validation: passwords must match, min 6 chars.
- **`DeleteUserModal`:**
  - Confirmation alert with the username highlighted and warning that the action is irreversible.
- **`ChangePasswordModal`:**
  - Triggered from Header user profile badge.
  - Fields: `current_password`, `new_password`, `confirm_password`.
  - Client-side validation: matching passwords, min 6 characters.

### 3.5 Header & Navigation Integration
- **`frontend/src/components/layout/Header.tsx`:**
  - Update user badge dropdown or add an action button next to the username/role pill for *"Ganti Password"*.
  - Clicking opens `ChangePasswordModal`.
- **`frontend/src/config/navigation.ts`:**
  - Add navigation entry:
    ```typescript
    {
      name: 'Pengguna',
      href: '/pengguna',
      icon: Users,
      requiredRole: 'admin',
    }
    ```
- **`frontend/src/app/router.tsx`:**
  - Register route:
    ```tsx
    <Route
      path="/pengguna"
      element={
        <ProtectedRoute requiredRole="admin">
          <PenggunaPage />
        </ProtectedRoute>
      }
    />
    ```

---

## 4. Error Handling & Validation Rules

| Scenario | HTTP Status | Error Message | Frontend Handling |
| :--- | :--- | :--- | :--- |
| Unauthenticated request | `401 Unauthorized` | "Invalid credentials or token expired" | Redirects to `/login` |
| Non-admin accessing user management | `403 Forbidden` | "Forbidden: Insufficient privileges" | UI hidden; direct access redirects to `/unauthorized` |
| Duplicate username on creation | `409 Conflict` | "Username already exists" | Inline error on username input |
| Admin attempts to deactivate own account | `400 Bad Request` | "Cannot deactivate your own account" | Toast/modal alert + toggle disabled in UI |
| Admin attempts to delete own account | `400 Bad Request` | "Cannot delete your own account" | Button disabled in UI + backend 400 rejection |
| Admin attempts to demote/deactivate last active admin | `400 Bad Request` | "Cannot demote or deactivate the last active administrator" | Toast/modal alert |
| Admin attempts to delete last active admin | `400 Bad Request` | "Cannot delete the last active administrator" | Toast/modal alert |
| User enters wrong current password on self-service change | `400 Bad Request` | "Current password is incorrect" | Inline error on `current_password` input |
| New password matches current password | `400 Bad Request` | "New password cannot be the same as current password" | Inline form error |

---

## 5. Testing & Verification Plan

### 5.1 Backend Automated Tests (`services/api/tests/test_user_management.py`)
- Test user listing by admin vs operator (403).
- Test user creation (happy path and 409 duplicate check).
- Test updating user role and active state.
- Test admin resetting another user's password and verifying login with new password.
- Test self-deactivation prevention (400).
- Test last admin demotion/deactivation prevention (400).
- Test self-deletion prevention (400).
- Test last admin deletion prevention (400).
- Test self-service password update with correct current password and verify login.
- Test self-service password update with wrong current password (400).

### 5.2 Frontend Automated & Build Verification
- Unit/component test or TypeScript compilation: `npm run build` in `frontend/`.
- Ensure ESLint / build checks pass without warnings or errors.
