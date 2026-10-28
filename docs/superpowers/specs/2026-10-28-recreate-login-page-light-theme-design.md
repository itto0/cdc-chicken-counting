# Recreate Login Page in Light Theme Design Specification

## 1. Overview
Recreate the login page (`LoginPage.tsx`) and authentication form (`LoginForm.tsx`) using a clean, accessible, modern light theme that matches the rest of the Lihat.id Poultry Counter dashboard. The recreated interface replaces dark-mode classes with elevated white card components, slate borders, emerald accent states, the brand chicken logo, and localized English copy.

---

## 2. Architecture & Visual Layout

### 2.1 Page Shell (`LoginPage.tsx`)
- **Container**: Full-height viewport container (`min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4 relative overflow-hidden`).
- **Ambient Lighting**: Subtle background glow accents (`bg-emerald-500/5` top-left, `bg-indigo-500/5` bottom-right) to provide atmospheric depth without reducing readability.
- **Brand Header**:
  - Centered chicken logo (`@/assets/logo/chicken_logo.png`, 48×48px) inside a soft rounded container (`bg-emerald-50 ring-1 ring-emerald-500/20 p-2.5 rounded-2xl mb-4`).
  - Title: `Sign In` (`text-2xl font-bold text-slate-900 tracking-tight`).
  - Subtitle: `Poultry Counter Central Dashboard` (`text-sm text-slate-500 mt-1`).
- **Card Container**:
  - Elevated white card (`w-full max-w-md bg-white border border-slate-200/80 rounded-2xl p-6 sm:p-8 shadow-xl shadow-slate-200/60`).
- **Footer**:
  - Copyright text: `© {currentYear} Lihat.id Computer Vision Poultry Counter System` (`mt-8 text-center text-xs text-slate-400`).

---

## 3. Form Controls & Interactions (`LoginForm.tsx`)

### 3.1 Input Fields
- **Username Input**:
  - Label: `Username` (`block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5`).
  - Leading Icon: `User` (`w-4 h-4 text-slate-400`).
  - Input: `w-full pl-10 pr-4 py-2.5 bg-white border border-slate-300 rounded-xl text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all`.
  - Placeholder: `admin / operator`.
  - Autocomplete: `username`.
- **Password Input**:
  - Label: `Password` (`block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5`).
  - Leading Icon: `Lock` (`w-4 h-4 text-slate-400`).
  - Reveal Toggle: Button with `Eye` / `EyeOff` icons (`text-slate-400 hover:text-slate-600`), switching input type between `password` and `text`.
  - Input: Matching styling with `pr-10` padding for the reveal icon.
  - Placeholder: `••••••••`.
  - Autocomplete: `current-password`.

### 3.2 Action Buttons & Validation
- **Submit Button**:
  - Label: `Sign In` (`w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white rounded-xl text-sm font-semibold shadow-sm shadow-emerald-600/20 flex items-center justify-center gap-2 cursor-pointer transition-all disabled:opacity-50`).
  - Loading State: Disabled button displaying a spinning `Loader2` icon and `Signing in...`.
- **Validation & Error Banner**:
  - Empty field check: `"Please enter your username and password."`
  - Network/API failure: Displays received error message or fallback `"Failed to sign in to the system."`
  - Style: `bg-rose-50 border border-rose-200 text-rose-700 text-sm rounded-xl p-3.5 mb-5 flex items-start gap-3` with `AlertCircle` icon.

### 3.3 Development Demo Quick-Fill
- Conditionally rendered when `import.meta.env.DEV` is true.
- Separator: `border-t border-slate-100 mt-6 pt-5`.
- Header: `Demo accounts:` (`text-xs text-slate-400 text-center mb-2.5`).
- Quick-fill Buttons:
  - Admin: `Admin (admin123)` (`py-1.5 px-3 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 transition-colors`).
  - Operator: `Operator (operator123)` (`py-1.5 px-3 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 transition-colors`).

---

## 4. State & Authentication Integration

- **Hook**: Consumes `useAuth()` (`login`, `isAuthenticated`, `isLoading`).
- **Navigation**:
  - On mount / auth state change: if `isAuthenticated && !isLoading`, auto-redirect to `location.state.from` (fallback `/`).
  - On successful login: invokes `onSuccess` callback which calls `navigate(destination, { replace: true })`.

---

## 5. Testing & Verification

Comprehensive Vitest + React Testing Library test suites:
1. `frontend/src/features/auth/components/__tests__/LoginForm.test.tsx`:
   - Renders all form labels, inputs, icons, and buttons in light theme style.
   - Shows validation error when submitted empty.
   - Toggles password visibility between password and plain text.
   - Clicking quick-fill buttons fills username and password.
   - Calls `login` on form submit and triggers `onSuccess`.
   - Displays error banner on rejected login.
   - Disables submit button while submitting.
2. `frontend/src/features/auth/pages/__tests__/LoginPage.test.tsx`:
   - Renders logo, page title, subtitle, and footer.
   - Auto-navigates when already authenticated.
