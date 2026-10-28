# User Management English Localization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Localize all Indonesian user-facing copy in the frontend User Management feature, modals, navigation, and associated test suites to clean, idiomatic English.

**Architecture:** Direct English text replacement across React functional components, preserving all existing component interfaces, props, styling, accessibility attributes, and behavior. Add route aliasing (`/users` -> `/pengguna`) in React Router, and update Vitest component tests in lockstep with English matchers.

**Tech Stack:** React 19, TypeScript, Tailwind CSS, Lucide React, Vitest, React Testing Library.

## Global Constraints

- No runtime i18n abstraction or third-party localization packages added; use direct clean English strings matching the codebase pattern.
- Preserve backward-compatible routing: support both `/pengguna` and `/users`.
- Maintain all existing test coverage, aria-labels, form validation semantics, and admin guard conditions.
- Zero TypeScript compiler errors (`tsc --noEmit`).

---

### Task 1: Navigation Test Fix & Route Aliasing

**Files:**
- Modify: `frontend/src/components/layout/__tests__/Sidebar.test.tsx:28-40`
- Modify: `frontend/src/app/router.tsx:85-92`

**Interfaces:**
- Consumes: `frontend/src/config/navigation.ts` (`title: "User Management"`, `path: "/pengguna"`)
- Produces: Route `/users` pointing to `PenggunaPage` as an alias alongside `/pengguna`

- [ ] **Step 1: Update Sidebar test to expect "User Management"**

In `frontend/src/components/layout/__tests__/Sidebar.test.tsx`, update the role assertions that check for the user management link:

```tsx
// Replace "Pengguna" with "User Management"
expect(screen.getByRole("link", { name: "User Management" })).toHaveAttribute(
  "href",
  "/pengguna"
);
```

- [ ] **Step 2: Run Sidebar test to verify it passes**

Run: `pnpm --filter frontend test -- src/components/layout/__tests__/Sidebar.test.tsx --run`
Expected: PASS (resolving the current test failure since `navigation.ts` has `title: "User Management"`)

- [ ] **Step 3: Add `/users` route alias in `router.tsx`**

In `frontend/src/app/router.tsx`, add `{ path: "users", element: <Suspense fallback={<PageFallback />}><PenggunaPage /></Suspense> }` right before or after the existing `"pengguna"` route.

- [ ] **Step 4: Verify router builds without TypeScript errors**

Run: `pnpm --filter frontend exec tsc --noEmit`
Expected: PASS with 0 errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/layout/__tests__/Sidebar.test.tsx frontend/src/app/router.tsx
git commit -m "fix(nav): update sidebar test for User Management and add /users route alias"
```

---

### Task 2: English Localization for `PenggunaPage` & Tests

**Files:**
- Modify: `frontend/src/features/users/pages/__tests__/PenggunaPage.test.tsx`
- Modify: `frontend/src/features/users/pages/PenggunaPage.tsx`

**Interfaces:**
- Consumes: `useUsers` hook (`data`, `isLoading`, `isError`, `refetch`), `useAuthStore` (`currentUser`)
- Produces: Localized `PenggunaPage` rendered at `/pengguna` and `/users`

- [ ] **Step 1: Update `PenggunaPage.test.tsx` with English assertions**

Update test matchers in `frontend/src/features/users/pages/__tests__/PenggunaPage.test.tsx`:
- Heading: `"User Management"` (was `"Manajemen Pengguna"`)
- Buttons: `"Refresh"` (was `"Segarkan"`), `"Add User"` (was `"Tambah Pengguna"`)
- KPI card titles & subtitles:
  - `"Total Users"` / `"Registered in system"` (was `"Total Pengguna"` / `"Terdaftar di sistem"`)
  - `"Active Users"` / `"Can sign in"` (was `"Pengguna Aktif"` / `"Dapat melakukan login"`)
  - `"Administrator"` / `"Full configuration access"`
  - `"Operator"` / `"Line and video operations"` (was `"Operasional lini dan video"`)
- Section heading & filters:
  - `"User List"` (was `"Daftar Pengguna"`)
  - Search placeholder: `"Search username..."` (was `"Cari username..."`)
  - Select options: `"All Roles"` (was `"Semua Peran"`), `"All Status"` (was `"Semua Status"`)
- Table headers & content:
  - Headers: `"Username"` (was `"Nama Pengguna"`), `"Role"` (was `"Peran"`), `"Status"`, `"Actions"` (was `"Aksi"`)
  - Self-badge: `"Your Account"` (was `"Akun Anda"`)
  - Status badges: `"Active"` (was `"Aktif"`), `"Inactive"` (was `"Nonaktif"`)
  - Tooltips/labels: `"Edit role and status"` (was `"Ubah peran dan status"`), `"Reset password"`, `"Delete user account"` (was `"Hapus akun pengguna"`), `"You cannot delete your own account"` (was `"Anda tidak dapat menghapus akun sendiri"`), `"Cannot delete the only active admin"` (was `"Tidak dapat menghapus satu-satunya admin aktif"`)
- Empty/Error states:
  - Error: `"Failed to load users"` (was `"Gagal memuat pengguna"`), button: `"Retry"` (was `"Coba Lagi"`)
  - Empty: `"No matching users found"` (was `"Tidak ada data pengguna yang cocok"`), `"Try adjusting search keywords or filters"` (was `"Coba sesuaikan kata kunci atau filter pencarian"`)

- [ ] **Step 2: Run test to observe failure**

Run: `pnpm --filter frontend test -- src/features/users/pages/__tests__/PenggunaPage.test.tsx --run`
Expected: FAIL due to Indonesian strings in `PenggunaPage.tsx`

- [ ] **Step 3: Update `PenggunaPage.tsx` with English strings**

Translate all UI strings in `frontend/src/features/users/pages/PenggunaPage.tsx`:
1. Header:
   - Title: `"User Management"`
   - Subtitle: `"Manage user accounts, roles, and access permissions in the system."`
   - Refresh button: `"Refresh"` (loading: `"Refreshing..."`)
   - Add button: `"Add User"`
2. Metric cards:
   - `"Total Users"` / `"Registered in system"`
   - `"Active Users"` / `"Can sign in"`
   - `"Administrator"` / `"Full configuration access"`
   - `"Operator"` / `"Line and video operations"`
3. Table controls & filters:
   - Heading: `User List ({filteredUsers.length})`
   - Search placeholder: `"Search username..."`
   - Role dropdown: `"All Roles"`, `"Operator"`, `"Admin"`
   - Status dropdown: `"All Status"`, `"Active"`, `"Inactive"`
4. Table columns & rows:
   - Headers: `"ID"`, `"Username"`, `"Role"`, `"Status"`, `"Actions"`
   - Badges: `"Your Account"`, `"Active"`, `"Inactive"`
   - Action buttons:
     - Edit title: `"Edit role and status"`
     - Reset password title: `"Reset password"`
     - Delete title: `"Delete user account"`, or disabled warnings: `"You cannot delete your own account"`, `"Cannot delete the only active admin"`
5. Feedback states:
   - Error card: `"Failed to load users"`, Retry button: `"Retry"`
   - Loading: `"Loading user list..."`
   - Empty state: `"No matching users found"`, `"Try adjusting search keywords or filters"`

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm --filter frontend test -- src/features/users/pages/__tests__/PenggunaPage.test.tsx --run`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/users/pages/PenggunaPage.tsx frontend/src/features/users/pages/__tests__/PenggunaPage.test.tsx
git commit -m "feat(users): localize PenggunaPage and its tests to English"
```

---

### Task 3: English Localization for Admin Modals (`CreateUserModal`, `EditUserModal`, `ResetPasswordModal`, `DeleteUserModal`) & Tests

**Files:**
- Modify: `frontend/src/features/users/components/__tests__/modals.test.tsx`
- Modify: `frontend/src/features/users/components/CreateUserModal.tsx`
- Modify: `frontend/src/features/users/components/EditUserModal.tsx`
- Modify: `frontend/src/features/users/components/ResetPasswordModal.tsx`
- Modify: `frontend/src/features/users/components/DeleteUserModal.tsx`

**Interfaces:**
- Consumes: Modal props (`isOpen`, `onClose`, `onSuccess`, user entities)
- Produces: Localized dialogs for user CRUD operations

- [ ] **Step 1: Update `modals.test.tsx` with English assertions**

In `frontend/src/features/users/components/__tests__/modals.test.tsx`:
- `CreateUserModal`:
  - Title: `"Add New User"`
  - Labels: `"Username"`, `"Password"`, `"Role"`
  - Role options: `"Operator (Monitoring & Operations)"`, `"Admin (Full System Access)"`
  - Validations: `"Username cannot be empty"`, `"Username must be at least 3 characters"`, `"Password must be at least 6 characters"`
  - Buttons: `"Cancel"`, `"Save User"`
- `EditUserModal`:
  - Title: `"Edit User"`
  - Labels: `"Username"`, `"Role"`, `"Account Status"`, `"Active Account"`
  - Guards: `"Role cannot be demoted because this is the only active admin."`, `"You cannot deactivate the account currently in use."`, `"This account cannot be deactivated because it is the only active admin."`
  - Buttons: `"Cancel"`, `"Save Changes"`
- `ResetPasswordModal`:
  - Title: `"Reset User Password"`
  - Labels: `"New Password"`, `"Confirm New Password"`
  - Validations: `"Password must be at least 6 characters"`, `"New passwords do not match"`
  - Buttons: `"Cancel"`, `"Reset Password"`
- `DeleteUserModal`:
  - Title: `"Delete User"`
  - Message: `Are you sure you want to delete user account "testuser"? This action cannot be undone.`
  - Buttons: `"Cancel"`, `"Delete User"`

- [ ] **Step 2: Run test to observe failure**

Run: `pnpm --filter frontend test -- src/features/users/components/__tests__/modals.test.tsx --run`
Expected: FAIL due to Indonesian strings in modal components

- [ ] **Step 3: Update `CreateUserModal.tsx`**

Translate in `frontend/src/features/users/components/CreateUserModal.tsx`:
- Title: `"Add New User"`, Close aria-label: `"Close"`
- Labels & placeholders:
  - `"Username"`, placeholder: `"e.g. op_johndoe"`
  - `"Password"`, placeholder: `"Minimum 6 characters"`
  - `"Role"`, options: `"Operator (Monitoring & Operations)"`, `"Admin (Full System Access)"`
- Validation messages:
  - `"Username cannot be empty"`
  - `"Username must be at least 3 characters"`
  - `"Password must be at least 6 characters"`
  - Error fallback: `"Failed to add user"`
- Buttons: `"Cancel"`, `"Save User"` (submitting: `"Saving..."`)

- [ ] **Step 4: Update `EditUserModal.tsx`**

Translate in `frontend/src/features/users/components/EditUserModal.tsx`:
- Title: `"Edit User"`, Close aria-label: `"Close"`
- Labels:
  - `"Username"`, helper: `"(cannot be changed)"`
  - `"Role"`, options: `"Operator (Monitoring & Operations)"`, `"Admin (Full System Access)"`
  - `"Account Status"`, checkbox label: `"Active Account"`
- Guards and alerts:
  - Self-deactivation warning: `"You cannot deactivate your own account"`
  - Only-admin warning: `"Cannot change role or deactivate the only active admin"`
  - Demotion guard banner: `"Role cannot be demoted because this is the only active admin."`
  - Self-deactivation banner: `"You cannot deactivate the account currently in use."`
  - Last admin deactivation banner: `"This account cannot be deactivated because it is the only active admin."`
- Buttons: `"Cancel"`, `"Save Changes"` (submitting: `"Saving..."`), error fallback: `"Failed to update user"`

- [ ] **Step 5: Update `ResetPasswordModal.tsx`**

Translate in `frontend/src/features/users/components/ResetPasswordModal.tsx`:
- Title: `"Reset User Password"`, Close aria-label: `"Close"`
- Info text: `"Reset password for: "`
- Labels & placeholders:
  - `"New Password"`, placeholder: `"Minimum 6 characters"`
  - `"Confirm New Password"`, placeholder: `"Re-enter new password"`
- Validation messages:
  - `"Password must be at least 6 characters"`
  - `"New passwords do not match"`
  - Error fallback: `"Failed to reset password"`
- Buttons: `"Cancel"`, `"Reset Password"` (submitting: `"Resetting..."`)

- [ ] **Step 6: Update `DeleteUserModal.tsx`**

Translate in `frontend/src/features/users/components/DeleteUserModal.tsx`:
- Title: `"Delete User"`, Close aria-label: `"Close"`
- Confirmation text: `"Are you sure you want to delete user account \"{username}\"? This action cannot be undone."`
- Buttons: `"Cancel"`, `"Delete User"` (submitting: `"Deleting..."`), error fallback: `"Failed to delete user"`

- [ ] **Step 7: Run test to verify it passes**

Run: `pnpm --filter frontend test -- src/features/users/components/__tests__/modals.test.tsx --run`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add frontend/src/features/users/components/CreateUserModal.tsx frontend/src/features/users/components/EditUserModal.tsx frontend/src/features/users/components/ResetPasswordModal.tsx frontend/src/features/users/components/DeleteUserModal.tsx frontend/src/features/users/components/__tests__/modals.test.tsx
git commit -m "feat(users): localize user management admin modals and tests to English"
```

---

### Task 4: English Localization for `ChangePasswordModal` & Tests

**Files:**
- Modify: `frontend/src/features/users/components/__tests__/ChangePasswordModal.test.tsx`
- Modify: `frontend/src/features/users/components/ChangePasswordModal.tsx`

**Interfaces:**
- Consumes: `ChangePasswordModalProps` (`isOpen`, `onClose`)
- Produces: Localized self-service password update dialog

- [ ] **Step 1: Update `ChangePasswordModal.test.tsx` with English assertions**

In `frontend/src/features/users/components/__tests__/ChangePasswordModal.test.tsx`:
- Title: `"Change My Password"`
- Labels: `"Current Password"`, `"New Password"`, `"Confirm New Password"`
- Validation messages:
  - `"Current password is required"`
  - `"New password must be at least 6 characters"`
  - `"New password must be different from current password"`
  - `"New passwords do not match"`
- Success message: `"Password updated successfully!"`
- Buttons: `"Cancel"`, `"Update Password"`

- [ ] **Step 2: Run test to observe failure**

Run: `pnpm --filter frontend test -- src/features/users/components/__tests__/ChangePasswordModal.test.tsx --run`
Expected: FAIL due to Indonesian strings in `ChangePasswordModal.tsx`

- [ ] **Step 3: Update `ChangePasswordModal.tsx` with English strings**

Translate in `frontend/src/features/users/components/ChangePasswordModal.tsx`:
- Title: `"Change My Password"`, Close aria-label: `"Close"`
- Labels & placeholders:
  - `"Current Password"`, placeholder: `"Enter current password"`
  - `"New Password"`, placeholder: `"Minimum 6 characters"`
  - `"Confirm New Password"`, placeholder: `"Re-enter new password"`
- Validation messages:
  - `"Current password is required"`
  - `"New password must be at least 6 characters"`
  - `"New password must be different from current password"`
  - `"New passwords do not match"`
- Feedback messages:
  - Error fallback: `"Failed to change password"`
  - Success banner: `"Password updated successfully!"`
- Buttons: `"Cancel"`, `"Update Password"` (submitting: `"Updating..."`)

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm --filter frontend test -- src/features/users/components/__tests__/ChangePasswordModal.test.tsx --run`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/users/components/ChangePasswordModal.tsx frontend/src/features/users/components/__tests__/ChangePasswordModal.test.tsx
git commit -m "feat(users): localize ChangePasswordModal and its tests to English"
```

---

### Task 5: Full Test Suite & TypeScript Verification

**Files:**
- All touched files

- [ ] **Step 1: Run all affected Vitest suites**

Run: `pnpm --filter frontend test -- src/components/layout/__tests__/Sidebar.test.tsx src/features/users/pages/__tests__/PenggunaPage.test.tsx src/features/users/components/__tests__/modals.test.tsx src/features/users/components/__tests__/ChangePasswordModal.test.tsx --run`
Expected: All suites PASS with 0 failures

- [ ] **Step 2: Run full TypeScript check**

Run: `pnpm --filter frontend exec tsc --noEmit`
Expected: 0 errors

- [ ] **Step 3: Check git status to ensure working tree is clean**

Run: `git status`
Expected: Clean working tree on master branch
