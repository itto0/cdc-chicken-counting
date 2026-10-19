# Edge API Key Management UI Design Specification

**Date:** 2026-10-19  
**Status:** Approved  
**Feature:** API Key Management UI Page (`/api-keys`)  

---

## 1. Overview & Goal

Provide a dedicated, administrative web UI page at route `/api-keys` allowing authorized administrators to create, inspect, and revoke API keys used by edge counter devices. This interface complements the administrative CLI (`services.api.src.cli`) and enables zero-friction onboarding for edge devices connecting to the central cloud platform.

Access to `/api-keys` is restricted to administrators and is directly accessible via URL (intentionally omitted from the standard sidebar menu).

---

## 2. Architecture & Routing

### 2.1 Route & Layout Configuration
- **Path:** `/api-keys`
- **Component:** `frontend/src/features/api-keys/pages/ApiKeysPage.tsx`
- **Layout:** Rendered within the authenticated `<AppShell />` layout.
- **Route Guard:** Wrapped with `<ProtectedRoute allowedRoles={["admin"]}>` in `frontend/src/app/router.tsx`. Unauthenticated users are redirected to `/login`, and non-admin users (`operator`) are redirected to `/`.
- **Navigation Menu:** Omitted from `navigationConfig` in `frontend/src/config/navigation.ts`, keeping the URL accessible without cluttering the operator sidebar.

### 2.2 Feature Directory Layout
```text
frontend/src/features/api-keys/
├── api/
│   └── apiKeys.api.ts          # HTTP client methods for API key management
├── components/
│   ├── ApiKeyTable.tsx         # Table listing existing API keys
│   ├── CreateApiKeyModal.tsx   # Two-stage creation modal with one-time secret display
│   └── RevokeKeyModal.tsx      # Confirmation dialog for revoking keys
├── pages/
│   └── ApiKeysPage.tsx         # Main page view with header, stats, and action triggers
├── types.ts                    # TypeScript interface definitions
└── index.ts                    # Public module re-exports
```

---

## 3. Data Contracts & API Integration

### 3.1 TypeScript Types (`types.ts`)
```typescript
export interface ApiKeyItem {
  id: string;
  name: string;
  prefix: string;          // e.g. "cdc_live_abc12345"
  role: "OPERATOR" | "ADMIN";
  is_active: boolean;
  created_at: string;      // ISO 8601 string
  last_used_at: string | null;
}

export interface CreateApiKeyPayload {
  name: string;
  role: "OPERATOR" | "ADMIN";
}

export interface CreateApiKeyResponse {
  id: string;
  name: string;
  api_key: string;         // Plaintext full key (cdc_live_...), returned ONLY upon creation
  prefix: string;
  role: "OPERATOR" | "ADMIN";
  created_at: string;
}
```

### 3.2 API Service (`api/apiKeys.api.ts`)
Consumes the backend endpoints introduced in `feat/edge-api-key-auth`:
- **List API Keys:** `getApiKeys(): Promise<ApiKeyItem[]>` $\rightarrow$ `GET /api/v1/auth/api-keys`
- **Create API Key:** `createApiKey(payload: CreateApiKeyPayload): Promise<CreateApiKeyResponse>` $\rightarrow$ `POST /api/v1/auth/api-keys`
- **Revoke API Key:** `revokeApiKey(keyId: string): Promise<ApiKeyItem>` $\rightarrow$ `DELETE /api/v1/auth/api-keys/${keyId}`

---

## 4. User Interaction & UI Specifications

### 4.1 Page View (`ApiKeysPage.tsx`)
- **Header:** Title *"Manajemen Kunci API"*, description *"Kelola token autentikasi perangkat edge counter untuk sinkronisasi data cloud"*, and a primary action button *"+ Buat Kunci Baru"* (icon `Plus`).
- **Summary Cards:**
  - Total Kunci (Total Keys)
  - Kunci Aktif (Active Keys)
  - Kunci Dicabut / Nonaktif (Revoked Keys)
- **Table Container:** Renders `ApiKeyTable` with loading skeleton during data fetch, and an empty state if no keys exist.

### 4.2 API Key Table (`ApiKeyTable.tsx`)
Displays columns:
1. **Nama & Perangkat (Name):** Display name (e.g., "Edge Counter Lini 1").
2. **Awalan Kunci (Key Prefix):** Monospaced code badge (e.g., `cdc_live_a1b2c3d4...`).
3. **Peran (Role):** Badge indicating `OPERATOR` or `ADMIN`.
4. **Status:**
   - Active: Emerald green badge with check icon (*Aktif*).
   - Inactive: Slate/Rose badge with ban icon (*Dicabut*).
5. **Dibuat (Created):** Formatted date & time (e.g., `19 Okt 2026, 14:30`).
6. **Terakhir Digunakan (Last Used):** Relative or formatted time (e.g., `5 menit yang lalu` or `-` if never used).
7. **Aksi (Action):** Button *Cabut Akses* (Revoke) with trash/ban icon for active keys; disabled or hidden for already-revoked keys.

### 4.3 Creation Dialog (`CreateApiKeyModal.tsx`)
Two-stage modal:
- **Stage 1 (Form):**
  - Input field for `Nama Kunci` (required, trimmed, max 100 characters).
  - Select dropdown for `Peran / Role` (options: `OPERATOR` [default], `ADMIN`).
  - Validation error display for blank/invalid submissions.
  - Buttons: *Batal* (Cancel) and *Buat Kunci* (Submit, with loading spinner).
- **Stage 2 (Secret Reveal):**
  - Prominent code box displaying the raw `cdc_live_<64-hex>` key.
  - *Salin Kunci* (Copy to Clipboard) button using `navigator.clipboard.writeText` with visual confirmation ("Tersalin!").
  - Warning banner (Amber/Yellow): *"Kunci rahasia ini hanya ditampilkan sekali. Simpan ke file `.env` pada edge counter sekarang. Anda tidak akan dapat melihat kunci ini lagi setelah menutup dialog ini."*
  - Single button: *Selesai* (Close), which triggers a table data refresh.

### 4.4 Revocation Dialog (`RevokeKeyModal.tsx`)
- Confirmation modal stating: *"Apakah Anda yakin ingin mencabut akses untuk kunci **<Nama Kunci>** (`<prefix>...`)? Perangkat yang menggunakan kunci ini tidak akan dapat menyinkronkan data atau mengambil konfigurasi lini lagi."*
- Buttons: *Batal* and *Ya, Cabut Kunci* (destructive red button).
- Calls `revokeApiKey(keyId)`, updates state optimistically or re-fetches, and closes modal.

---

## 5. Error Handling & Edge Cases

- **Network / API Failure:** Friendly error alerts if loading keys fails, with a "Coba Lagi" (Retry) button.
- **Copy to Clipboard Fallback:** If `navigator.clipboard` is restricted (e.g. non-HTTPS iframe), falls back to temporary textarea selection.
- **Escape Key & Backdrop Click:** Stage 1 closes cleanly on Escape / backdrop click. Stage 2 requires an explicit button confirmation to prevent accidental loss of the uncopied key.
- **Role Permission Guard:** If a non-admin directly navigates to `/api-keys`, React Router redirects them immediately away from the view.

---

## 6. Verification & Testing Plan

1. **Routing & Access Tests:**
   - Verify unauthenticated users navigating to `/api-keys` are redirected to `/login`.
   - Verify non-admin users (`operator`) are redirected away from `/api-keys`.
   - Verify admin users can access `/api-keys` cleanly.
2. **API Mock & Component Tests:**
   - Verify `ApiKeyTable` renders keys correctly, displays appropriate badges for active/revoked states, and formats timestamps.
   - Verify `CreateApiKeyModal` handles stage 1 submission, error states, and transitions to stage 2 with the full secret key and clipboard copy.
   - Verify `RevokeKeyModal` confirms and triggers revocation API call.
3. **Build & Bundle Verification:**
   - Execute `npm run build` in `frontend/` to confirm complete TypeScript type safety, valid JSX, and clean asset bundling without errors.
