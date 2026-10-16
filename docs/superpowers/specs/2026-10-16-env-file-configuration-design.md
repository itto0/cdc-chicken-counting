# Design Spec: Minimal Environment File Configuration

- **Date:** 2026-10-16
- **Status:** Approved
- **Scope:** Root `.env` support across backend (API & Counter) and frontend (Vite)

---

## 1. Context & Motivation

Currently, the project contains a root `.env` file containing `PORT=8070`, and Python services (`services/api` and `services/counter`) access environment variables via `os.getenv(...)`. However, neither service loads `.env` files automatically when executed locally (e.g. `uvicorn` or `python services/counter/main.py`). The frontend (`frontend/`) also runs out of a subfolder and does not read `.env` from the project root by default.

This design introduces minimal, automatic `.env` loading and a clean, concise `.env.example` template.

---

## 2. Goals & Non-Goals

### Goals
- Automatically load `.env` from the repository root when running Python services locally.
- Allow Vite frontend to read `VITE_*` environment variables from the root `.env`.
- Provide a clean, minimal `.env.example` containing only the 5 essential configuration keys.
- Preserve backward compatibility with command-line arguments and existing `os.getenv` fallbacks.

### Non-Goals
- Do not introduce complex or heavy settings validation frameworks (e.g. `pydantic-settings`).
- Do not add unnecessary environment variables to `.env.example` for parameters that already have working defaults.

---

## 3. Detailed Design

### 3.1 Dependencies
Add `python-dotenv>=1.0.0` to `dependencies` in `pyproject.toml`.

### 3.2 Python Services Environment Loading
Use `dotenv.load_dotenv(dotenv.find_dotenv(usecwd=True))` to ensure `.env` is discovered and loaded from the project root or parent directories, regardless of the current working directory.

1. **`services/api/src/main.py`**:
   Load `.env` at top of file before application startup.
2. **`services/api/src/db/session.py`**:
   Load `.env` before `DATABASE_URL = os.getenv(...)` to ensure standalone database connections or tests respect `.env`.
3. **`services/counter/main.py`**:
   Load `.env` before argument parsing and default assignments.

### 3.3 Frontend Integration (`frontend/vite.config.ts`)
Set `envDir: "../"` in the Vite configuration so Vite picks up `VITE_*` variables from the root `.env` without requiring file duplication into `frontend/`.

### 3.4 Docker Compose (`docker-compose.yml`)
Ensure both `api` and `counter` services use the root `.env` by declaring `env_file: .env` while preserving container-network overrides.

### 3.5 Minimal `.env.example`
Provide a streamlined template with only essential configuration:

```env
# Server & Frontend
PORT=8070
VITE_API_BASE_URL=http://localhost:8070

# API Security & Database
DATABASE_URL=sqlite:///api_central.db
JWT_SECRET_KEY=cdc-poultry-counter-secret-key-32bytes

# Counter Video Source (optional, defaults to synthetic if empty)
VIDEO_PATH=
```

---

## 4. Verification Plan

1. **Dependency check:** `python-dotenv` installs cleanly in the Python environment.
2. **Backend verification:**
   - Run a test script verifying that setting a test variable in `.env` is loaded by `dotenv.load_dotenv(dotenv.find_dotenv(usecwd=True))`.
   - Verify `DATABASE_URL` and `JWT_SECRET_KEY` load values from `.env` if provided.
   - Run existing pytest suite (`pytest`) to ensure no regressions.
3. **Frontend verification:**
   - Run `npm run build` in `frontend/` to ensure Vite compiles successfully with `envDir: "../"`.
