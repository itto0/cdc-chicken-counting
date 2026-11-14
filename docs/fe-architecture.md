# React + Vite Project Structure for Web-Based Management Apps

A recommended, feature-based structure for admin panels, dashboards, and CRUD-heavy systems.

---

## 1. Overview

Management apps (inventory, HR, school, e-commerce admin, etc.) usually consist of many modules, each with lists, detail pages, and forms. Grouping code **by feature** (domain) instead of **by file type** keeps the codebase navigable as it grows.

**Goals**

- Easy to find everything related to one module
- Clear dependency direction
- Reusable building blocks (tables, forms, layout)
- Safe to scale to dozens of modules and multiple developers

---

## 2. Folder Structure

```
my-app/
├── public/
├── src/
│   ├── app/                    # App-level wiring
│   │   ├── App.tsx
│   │   ├── router.tsx          # Route definitions
│   │   ├── providers.tsx       # QueryClient, Theme, Auth providers
│   │   └── store.ts            # Global client state (if needed)
│   │
│   ├── features/               # One folder per business domain
│   │   ├── auth/
│   │   │   ├── api/            # API calls + query hooks
│   │   │   ├── components/     # LoginForm, etc.
│   │   │   ├── hooks/
│   │   │   ├── pages/          # LoginPage.tsx
│   │   │   ├── types.ts
│   │   │   └── index.ts        # Public exports only
│   │   ├── users/
│   │   │   ├── api/
│   │   │   ├── components/     # UserTable, UserForm
│   │   │   ├── pages/          # UserListPage, UserDetailPage
│   │   │   ├── schemas.ts      # Zod validation
│   │   │   ├── types.ts
│   │   │   └── index.ts
│   │   └── orders/ ...
│   │
│   ├── components/             # Shared, reusable UI
│   │   ├── ui/                 # Button, Input, Modal (primitives)
│   │   ├── data-table/         # Generic table: sorting, filters, pagination
│   │   └── layout/             # Sidebar, Header, AppShell, PageHeader
│   │
│   ├── hooks/                  # Shared hooks (useDebounce, usePermissions)
│   ├── lib/                    # Configured libs (axios client, queryClient, utils)
│   ├── config/                 # env.ts, constants, navigation.ts
│   ├── types/                  # Global types
│   ├── styles/
│   ├── main.tsx
│   └── vite-env.d.ts
│
├── .env
├── .env.development
├── .env.production
├── eslint.config.js
├── tsconfig.json
├── vite.config.ts
└── package.json
```

---

## 3. Folder Responsibilities

| Folder | Purpose | Rule of thumb |
|---|---|---|
| `app/` | Bootstraps the app: router, providers, global setup | No business logic |
| `features/` | Domain modules (users, orders, products) | Owns its API, UI, types, and pages |
| `components/` | Shared UI used by 2+ features | Must not import from `features/` |
| `hooks/` | Shared hooks | Generic, not domain-specific |
| `lib/` | Pre-configured third-party libs and utilities | Single place to configure axios, query client, dayjs |
| `config/` | Env validation, constants, navigation menu | Static configuration only |
| `types/` | Global TypeScript types | Keep small; prefer feature-level types |

---

## 4. Key Principles

### 4.1 Features own their code

Everything about "users" lives in `features/users`. Promote code to shared folders (`components/`, `hooks/`) only when **at least two features** need it.

### 4.2 One-way dependencies

```
app  →  features  →  components / hooks / lib / config
```

- Shared code never imports from features.
- Features should not import each other's internals. If they must interact, import from the other feature's `index.ts`.
- Enforce with `eslint-plugin-boundaries` or `import/no-restricted-paths`.

### 4.3 Separate server state from client state

- **Server state** (anything from an API): TanStack Query
- **Client state** (sidebar open, theme, filters in UI): Zustand or React Context
- This removes most of the need for Redux.

### 4.4 Build the reusable pieces early

Management apps are mostly tables, filters, and forms. Invest early in:

- A generic `DataTable` (TanStack Table) with server-side pagination, sorting, and filtering
- A standard form pattern (React Hook Form + Zod)
- An `AppShell` layout (sidebar, header, breadcrumbs)
- A consistent confirm dialog and toast pattern

---

## 5. Recommended Stack

| Concern | Choice |
|---|---|
| Language | TypeScript |
| Build tool | Vite |
| Routing | React Router v7 or TanStack Router |
| Server state | TanStack Query |
| Forms | React Hook Form + Zod |
| Tables | TanStack Table |
| UI | shadcn/ui + Tailwind (or MUI / Ant Design for faster admin UIs) |
| HTTP | Axios or a `fetch` wrapper in `lib/` |
| Client state | Zustand (only if needed) |
| Unit/component tests | Vitest + Testing Library |
| E2E tests | Playwright |
| Lint/format | ESLint + Prettier |

---

## 6. Feature Module Example

```
features/users/
├── api/
│   ├── users.api.ts          # raw HTTP functions
│   └── users.queries.ts      # useUsers, useUser, useCreateUser...
├── components/
│   ├── UserTable.tsx
│   ├── UserForm.tsx
│   └── UserStatusBadge.tsx
├── pages/
│   ├── UserListPage.tsx
│   ├── UserDetailPage.tsx
│   └── UserCreatePage.tsx
├── schemas.ts                # Zod schemas
├── types.ts
└── index.ts                  # exports routes/pages and public hooks only
```

**`users.api.ts`**

```ts
import { http } from '@/lib/http';
import type { User, UserListParams, Paginated } from '../types';

export const usersApi = {
  list: (params: UserListParams) =>
    http.get<Paginated<User>>('/users', { params }).then((r) => r.data),
  get: (id: string) => http.get<User>(`/users/${id}`).then((r) => r.data),
  create: (payload: Partial<User>) =>
    http.post<User>('/users', payload).then((r) => r.data),
  update: (id: string, payload: Partial<User>) =>
    http.put<User>(`/users/${id}`, payload).then((r) => r.data),
  remove: (id: string) => http.delete(`/users/${id}`),
};
```

**`users.queries.ts`**

```ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { usersApi } from './users.api';

export const userKeys = {
  all: ['users'] as const,
  list: (params: unknown) => [...userKeys.all, 'list', params] as const,
  detail: (id: string) => [...userKeys.all, 'detail', id] as const,
};

export const useUsers = (params: UserListParams) =>
  useQuery({ queryKey: userKeys.list(params), queryFn: () => usersApi.list(params) });

export const useCreateUser = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: usersApi.create,
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.all }),
  });
};
```

---

## 7. Management-App Specifics

### Authentication and permissions

- `ProtectedRoute` wrapper for authenticated routes
- `usePermissions()` hook and `<Can permission="users.delete">` component for role-based UI
- Keep tokens in memory or HttpOnly cookies where possible
- Real authorization must be enforced on the backend; UI checks are for UX only

### Navigation as config

Define the sidebar in `config/navigation.ts` so menus and routes stay in sync:

```ts
export const navigation = [
  { label: 'Dashboard', path: '/', icon: 'home' },
  { label: 'Users', path: '/users', icon: 'users', roles: ['admin'] },
  { label: 'Orders', path: '/orders', icon: 'cart', roles: ['admin', 'staff'] },
];
```

### Route-level code splitting

```tsx
const UserListPage = lazy(() => import('@/features/users/pages/UserListPage'));
```

Keeps the initial bundle small as modules grow.

### Path aliases

`vite.config.ts`

```ts
import path from 'node:path';
export default defineConfig({
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
});
```

`tsconfig.json`

```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": { "@/*": ["src/*"] }
  }
}
```

### Environment validation

`config/env.ts`

```ts
import { z } from 'zod';

const schema = z.object({
  VITE_API_URL: z.string().url(),
  VITE_APP_NAME: z.string().default('Admin'),
});

export const env = schema.parse(import.meta.env);
```

A misconfigured deployment then fails at startup instead of at runtime.

### Other practical items

- **Error boundaries** at route level, plus a global 401 handler in the HTTP client
- **Consistent API error format** mapped to toasts and form field errors
- **Loading and empty states** built into `DataTable` and page templates
- **Audit-friendly actions:** confirm dialogs for destructive operations
- **i18n** (`react-i18next`) from the start if multiple languages are possible
- **Date/number formatting** centralized in `lib/format.ts`

---

## 8. Naming Conventions

| Item | Convention | Example |
|---|---|---|
| Components | PascalCase | `UserTable.tsx` |
| Hooks | camelCase with `use` prefix | `useUsers.ts` |
| Pages | `*Page.tsx` | `UserListPage.tsx` |
| API modules | `*.api.ts` | `users.api.ts` |
| Schemas | `schemas.ts` or `*.schema.ts` | `user.schema.ts` |
| Folders | kebab-case | `data-table/` |
| Tests | beside the file | `UserTable.test.tsx` |

---

## 9. Testing Strategy

- **Unit:** utilities, schemas, permission logic (Vitest)
- **Component:** forms, tables, conditional UI (Testing Library)
- **API mocking:** MSW, shared between tests and local development
- **E2E:** critical flows such as login, create/edit/delete record, permission denial (Playwright)

---

## 10. When to Simplify

For a small app (under about 5 screens), skip `features/` and use a flat layout:

```
src/
├── pages/
├── components/
├── hooks/
├── api/
└── lib/
```

Migrate to feature folders when the flat structure starts to feel crowded. Moving files is cheap if you already use path aliases.

---

## 11. Starter Checklist

- [ ] `npm create vite@latest my-app -- --template react-ts`
- [ ] Configure `@/` alias, ESLint, Prettier
- [ ] Install TanStack Query, React Router, React Hook Form, Zod, TanStack Table
- [ ] Set up Tailwind + shadcn/ui (or chosen UI library)
- [ ] Create `lib/http.ts` and `lib/queryClient.ts`
- [ ] Create `config/env.ts` with validation
- [ ] Build `AppShell` (sidebar, header, breadcrumbs)
- [ ] Build `ProtectedRoute` and `usePermissions`
- [ ] Build generic `DataTable` and form patterns
- [ ] Implement the first feature (`auth`), then `users` as the CRUD template
- [ ] Add boundary lint rules and Vitest setup