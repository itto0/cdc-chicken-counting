# Render Cloud Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Configure and document the complete deployment of the Poultry Counter system (Managed PostgreSQL database, FastAPI Docker backend, and React Vite static frontend) to Render cloud hosting using a Blueprint and comprehensive guide.

**Architecture:** Render Managed PostgreSQL provides relational persistence; Render Web Service runs the FastAPI backend inside a Docker container with automatic database linking and dynamic PORT support; Render Static Site hosts the Vite React SPA globally on CDN with client-side SPA rewrite rules. On-premise edge computer vision nodes continue syncing over HTTPS to the deployed API.

**Tech Stack:** Render (Web Service, Static Site, Managed PostgreSQL, Blueprint YAML), Python 3.11/3.14 (FastAPI, SQLAlchemy, Uvicorn, Pytest), React 18 / Vite / TypeScript.

## Global Constraints

- Backend must handle Render's `postgres://` database URI scheme without crashing SQLAlchemy 2.0.
- Frontend must build cleanly with zero missing asset errors (`npm run build`).
- Frontend routing must support browser refreshes on arbitrary subpaths (`/*` -> `/index.html`).
- Edge nodes must be able to push to the cloud API over HTTPS.

---

### Task 1: Frontend Build Readiness & Environment URL Formatting

**Files:**
- Modify: `frontend/src/components/layout/Sidebar.tsx:6`
- Modify: `frontend/src/config/env.ts:1-7`
- Test: Build verification with `npm run build` in `frontend/`

**Interfaces:**
- `env.API_BASE_URL`: string, guaranteed to have `https://` scheme if a bare domain is passed (e.g. `cdc-api.onrender.com` -> `https://cdc-api.onrender.com`).

- [ ] **Step 1: Fix broken asset import in Sidebar.tsx**

In `frontend/src/components/layout/Sidebar.tsx`, update line 6:
```typescript
import ChickenLogo from "@/assets/logo/chicken_logo.png";
```

- [ ] **Step 2: Add protocol normalization in env.ts**

In `frontend/src/config/env.ts`, update to normalize domain strings missing `https://`:
```typescript
function formatApiBaseUrl(url: string | undefined): string {
  if (!url) return "";
  const trimmed = url.trim();
  if (trimmed === "" || trimmed.startsWith("/")) return trimmed;
  if (!trimmed.startsWith("http://") && !trimmed.startsWith("https://")) {
    return `https://${trimmed}`;
  }
  return trimmed;
}

export const env = {
  API_BASE_URL: formatApiBaseUrl(import.meta.env.VITE_API_BASE_URL),
  APP_NAME: "Lihat.id · Poultry Counter",
};

export const API_BASE_URL = env.API_BASE_URL;
```

- [ ] **Step 3: Run frontend build to verify success**

Run: `npm run build` in directory `frontend`
Expected: `✓ built in ...` with no asset or typescript errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/layout/Sidebar.tsx frontend/src/config/env.ts
git commit -m "fix(frontend): resolve logo asset import path and format api base url"
```

---

### Task 2: Database Connection URL Normalization for Render

**Files:**
- Modify: `services/api/src/db/session.py:10-22`
- Create: `services/api/tests/test_database_url.py`

**Interfaces:**
- Produces: `resolve_database_url(url: str | None = None) -> str`
- Handles: `postgres://` -> `postgresql://` and driver detection (`postgresql+psycopg2://` / `postgresql+psycopg://`).

- [ ] **Step 1: Write the failing test**

Create `services/api/tests/test_database_url.py`:
```python
from services.api.src.db.session import resolve_database_url


def test_resolve_sqlite_url():
    url = "sqlite:///custom_path.db"
    assert resolve_database_url(url) == url


def test_resolve_render_postgres_prefix():
    raw_render_url = "postgres://usr:pwd@dpg-xxx-a.oregon-postgres.render.com/chicken_counting"
    resolved = resolve_database_url(raw_render_url)
    assert resolved.startswith("postgresql://") or resolved.startswith("postgresql+psycopg2://")
    assert "dpg-xxx-a.oregon-postgres.render.com" in resolved
    assert not resolved.startswith("postgres://")


def test_resolve_postgresql_prefix():
    url = "postgresql://usr:pwd@localhost:5432/chicken_counting"
    resolved = resolve_database_url(url)
    assert resolved.startswith("postgresql://") or resolved.startswith("postgresql+psycopg2://")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest services/api/tests/test_database_url.py -v`
Expected: FAIL with `ImportError: cannot import name 'resolve_database_url'`

- [ ] **Step 3: Implement resolve_database_url in session.py**

In `services/api/src/db/session.py`, implement `resolve_database_url`:
```python
def resolve_database_url(url: str | None = None) -> str:
    raw_url = url or os.getenv("DATABASE_URL", "sqlite:///api_central.db")
    # Render and legacy providers provide postgres:// which SQLAlchemy 2.0 rejects
    if raw_url.startswith("postgres://"):
        raw_url = "postgresql://" + raw_url[len("postgres://"):]

    if raw_url.startswith("postgresql://") and "+psycopg" not in raw_url:
        try:
            import psycopg  # noqa: F401
        except ImportError:
            try:
                import psycopg2  # noqa: F401
                raw_url = "postgresql+psycopg2://" + raw_url[len("postgresql://"):]
            except ImportError:
                pass
    return raw_url


DATABASE_URL = resolve_database_url()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest services/api/tests/test_database_url.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add services/api/src/db/session.py services/api/tests/test_database_url.py
git commit -m "fix(api): normalize render postgres database urls for sqlalchemy compatibility"
```

---

### Task 3: Dynamic CORS Configuration for Cloud Frontend

**Files:**
- Modify: `services/api/src/main.py:88-94`
- Create: `services/api/tests/test_cors_config.py`

**Interfaces:**
- Produces: `get_cors_origins(env_origins: str | None = None) -> list[str]`
- Used by: `CORSMiddleware` in `services/api/src/main.py`.

- [ ] **Step 1: Write the failing test**

Create `services/api/tests/test_cors_config.py`:
```python
from services.api.src.main import get_cors_origins


def test_cors_origins_wildcard():
    assert get_cors_origins("*") == ["*"]
    assert get_cors_origins("") == ["*"]
    assert get_cors_origins(None) == ["*"]


def test_cors_origins_multiple_domains():
    env_str = "https://cdc-frontend.onrender.com, http://localhost:3000, https://custom.com/"
    expected = ["https://cdc-frontend.onrender.com", "http://localhost:3000", "https://custom.com/"]
    assert get_cors_origins(env_str) == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest services/api/tests/test_cors_config.py -v`
Expected: FAIL with `ImportError: cannot import name 'get_cors_origins'`

- [ ] **Step 3: Implement get_cors_origins and update main.py**

In `services/api/src/main.py`:
```python
def get_cors_origins(env_origins: str | None = None) -> list[str]:
    raw = env_origins if env_origins is not None else os.getenv("CORS_ORIGINS", "*")
    if not raw or raw.strip() == "*":
        return ["*"]
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    return origins if origins else ["*"]
```
And update `app.add_middleware(CORSMiddleware)`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest services/api/tests/test_cors_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run all existing API tests to verify no regressions**

Run: `py -m pytest services/api/tests/ -v`
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add services/api/src/main.py services/api/tests/test_cors_config.py
git commit -m "feat(api): support configurable cors origins via environment variable"
```

---

### Task 4: Render Blueprint Specification (`render.yaml`)

**Files:**
- Create: `render.yaml`

**Interfaces:**
- Produces: Declarative infrastructure manifest defining `cdc-postgres`, `cdc-api` (Docker web service), and `cdc-frontend` (static site with client-side SPA routing).

- [ ] **Step 1: Write render.yaml**

Create `render.yaml` in the workspace root:
```yaml
databases:
  - name: cdc-postgres
    databaseName: chicken_counting
    user: postgres
    plan: free
    region: oregon

services:
  - type: web
    name: cdc-api
    runtime: docker
    dockerfilePath: ./services/api/Dockerfile
    dockerContext: .
    plan: free
    region: oregon
    healthCheckPath: /healthz
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: cdc-postgres
          property: connectionString
      - key: JWT_SECRET_KEY
        generateValue: true
      - key: API_SYNC_BATCH_MAX
        value: "1000"
      - key: CORS_ORIGINS
        value: "*"

  - type: web
    name: cdc-frontend
    runtime: static
    rootDir: frontend
    buildCommand: npm ci && npm run build
    staticPublishPath: ./dist
    plan: free
    region: oregon
    routes:
      - type: rewrite
        source: /*
        destination: /index.html
    envVars:
      - key: VITE_API_BASE_URL
        sync: false
```

- [ ] **Step 2: Validate render.yaml format**

Verify the YAML is valid and contains the required properties:
- `databases` list with `cdc-postgres`
- `services` list with `cdc-api` (`runtime: docker`) and `cdc-frontend` (`runtime: static`)
- Correct `routes` rewrite rule for React Router navigation

- [ ] **Step 3: Commit**

```bash
git add render.yaml
git commit -m "ci: add render blueprint specification for 1-click cloud deployment"
```

---

### Task 5: Comprehensive Render Deployment Guide

**Files:**
- Create: `docs/deployment-render.md`

**Interfaces:**
- Produces: Complete, accessible documentation explaining how to deploy, configure, connect edge nodes, and troubleshoot the Poultry Counter on Render.

- [ ] **Step 1: Write docs/deployment-render.md**

Create `docs/deployment-render.md` covering:
1. Overview of Cloud Architecture on Render (Postgres + FastAPI + Static Vite).
2. Option A: 1-Click Blueprint Deployment (connecting GitHub repo, setting `render.yaml`, entering `VITE_API_BASE_URL`).
3. Option B: Manual Dashboard Setup (creating PostgreSQL, Web Service, and Static Site independently in the Render UI).
4. Edge Node Configuration: how to configure `services/counter` on farm/factory cameras with `API_SYNC_URL=https://<cdc-api>.onrender.com/api/v1/sync/batch`.
5. Default Credentials & Initial Login (`admin` / `admin123`, `operator` / `operator123`).
6. Free Tier Notes & Best Practices (Render free tier 15-minute sleep, cold start latency, upgrading to Starter if 24/7 instant response is needed).

- [ ] **Step 2: Commit**

```bash
git add docs/deployment-render.md
git commit -m "docs: add comprehensive render cloud hosting deployment guide"
```

---

### Task 6: Final Verification & Smoke Test

**Files:**
- Verification only

- [ ] **Step 1: Run all Python tests**

Run: `py -m pytest services/api/tests/ -v`
Expected: All tests pass.

- [ ] **Step 2: Run frontend build**

Run: `npm run build` in directory `frontend`
Expected: Build passes with exit code 0.

- [ ] **Step 3: Verify git status is clean**

Run: `git status`
Expected: Clean working tree.
