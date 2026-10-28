# User Management English Localization Design

**Date:** 2026-10-28  
**Topic:** User Management English Localization  
**Status:** Approved  

---

## 1. Context & Motivation
The user management feature in the frontend (`frontend/src/features/users/`) previously used Indonesian copy (e.g. "Manajemen Pengguna", "Tambah Pengguna", "Pengguna Aktif"), while the sidebar was recently updated to "User Management" (`path: "/pengguna"`), and the backend auth API (`services/api/src/api/auth.py`) already returns all user status/error messages in English.

This spec standardizes all user-facing text in the User Management feature, all related modals, routing, and component test suites into idiomatic English.

---

## 2. Scope & Components

### 2.1 Navigation & Routing
- `frontend/src/config/navigation.ts`: Keep title as `"User Management"` pointing to `/pengguna` (or `/users`).
- `frontend/src/router.tsx`: Add route alias `/users` alongside `/pengguna` mapping to `PenggunaPage` to preserve backwards compatibility while providing an English URL path.
- `frontend/src/components/layout/__tests__/Sidebar.test.tsx`: Update sidebar test assertions to look for `"User Management"` instead of `"Pengguna"`.

### 2.2 User Management Main Page (`frontend/src/features/users/PenggunaPage.tsx`)
- **Header:**
  - Title: `"User Management"` (was `"Manajemen Pengguna"`)
  - Subtitle: `"Manage user accounts, roles, and access permissions"` (was `"Kelola akun pengguna, peran, dan hak akses sistem"`)
  - Action buttons: `"Add User"` (was `"Tambah Pengguna"`), `"Export CSV"`
- **KPI Metric Cards:**
  - `"Total Users"` (was `"Total Pengguna"`)
  - `"Active Users"` (was `"Pengguna Aktif"`)
  - `"Admin"` / `"Viewer"`
- **Search & Filters:**
  - Search placeholder: `"Search username or full name..."` (was `"Cari username atau nama..."`)
  - Role filter label & default: `"All Roles"` (was `"Semua Peran"`), options: `"Admin"`, `"Viewer"`
  - Status filter label & default: `"All Status"` (was `"Semua Status"`), options: `"Active"` (was `"Aktif"`), `"Inactive"` (was `"Nonaktif"`)
- **Users Table:**
  - Column headers: `"User"`, `"Full Name"`, `"Role"`, `"Status"`, `"Created At"`, `"Actions"`
  - Badges: `"Active"` / `"Inactive"`
  - Self-indicator tag: `"(You)"` (was `"(Anda)"`)
  - Action button tooltips: `"Edit user"`, `"Reset password"`, `"Delete user"`
- **Empty & Error States:**
  - Empty search / filter results: `"No users found"` with subtitle `"Try adjusting search keywords or filters."`
  - Error state: `"Failed to load user list."` with `"Retry"` button

### 2.3 User Modals (`frontend/src/features/users/`)

#### A. CreateUserModal (`CreateUserModal.tsx`)
- Title: `"Add New User"` (was `"Tambah Pengguna Baru"`)
- Subtitle: `"Fill in the details to create a new user account"`
- Labels & placeholders:
  - `"Username"` (placeholder: `"e.g. johndoe"`, helper: `"Letters, numbers, and underscores only, min 3 characters"`)
  - `"Full Name"` (placeholder: `"e.g. John Doe"`)
  - `"Role"` (options: `"Admin"`, `"Viewer"`)
  - `"Password"` (placeholder: `"Minimum 8 characters"`)
  - `"Confirm Password"` (placeholder: `"Re-enter password"`)
- Actions: `"Cancel"`, `"Create User"` (loading state: `"Creating..."`)

#### B. EditUserModal (`EditUserModal.tsx`)
- Title: `"Edit User"` (was `"Ubah Data Pengguna"`)
- Subtitle: `"Update user details and status"`
- Labels:
  - `"Username"` (disabled / read-only)
  - `"Full Name"`
  - `"Role"`
  - `"Account Status"` (`"Active"` / `"Inactive"`)
- Warnings & Guards:
  - Self edit notice: `"You cannot change your own role or deactivate your own account"`
  - Demotion guard: `"Cannot demote the last active admin"`
- Actions: `"Cancel"`, `"Save Changes"` (loading state: `"Saving..."`)

#### C. ResetPasswordModal (`ResetPasswordModal.tsx`)
- Title: `"Reset Password"` (was `"Reset Password Pengguna"`)
- Subtitle: `"Set a new password for user {username}"`
- Labels & placeholders:
  - `"New Password"` (placeholder: `"Minimum 8 characters"`)
  - `"Confirm New Password"` (placeholder: `"Re-enter new password"`)
- Actions: `"Cancel"`, `"Reset Password"` (loading state: `"Resetting..."`)

#### D. DeleteUserModal (`DeleteUserModal.tsx`)
- Title: `"Delete User"` (was `"Hapus Pengguna"`)
- Confirmation prompt: `"Are you sure you want to delete user \"{username}\"? This action cannot be undone."`
- Self-delete guard: `"You cannot delete your own account."`
- Actions: `"Cancel"`, `"Delete User"` (loading state: `"Deleting..."`)

#### E. ChangePasswordModal (`ChangePasswordModal.tsx`)
- Title: `"Change My Password"` (was `"Ganti Password Saya"`)
- Subtitle: `"Update your login password"`
- Labels: `"Current Password"`, `"New Password"`, `"Confirm New Password"`
- Validation & notifications:
  - `"All fields are required"`
  - `"New password must be at least 8 characters"`
  - `"New passwords do not match"`
  - Success message: `"Password updated successfully!"`
- Actions: `"Cancel"`, `"Update Password"` (loading state: `"Updating..."`)

---

## 3. Testing & Verification

1. **`Sidebar.test.tsx`**: Update assertion for User Management link to expect `"User Management"`.
2. **`PenggunaPage.test.tsx`**: Update assertions to test for English headings, buttons, KPI cards, table headers, and status/role filter options.
3. **`modals.test.tsx`**: Update test matchers for `CreateUserModal`, `EditUserModal`, `ResetPasswordModal`, and `DeleteUserModal` to check English headings, field labels, button states, and confirmation alerts.
4. **`ChangePasswordModal.test.tsx`**: Update test matchers for headings, field labels, validation messages, and success alerts.
5. **Full Test Execution**:
   - Run Vitest for `frontend/src/features/users/` and `frontend/src/components/layout/`.
   - Run TypeScript typecheck to verify zero compilation errors.
