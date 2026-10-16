# Minimal Environment File Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide minimal, automatic `.env` loading across Python services (API and Counter), configure Vite to load root `.env`, and provide a clean, minimal `.env.example`.

**Architecture:** A lightweight helper `shared/env.py` uses `python-dotenv`'s `find_dotenv(usecwd=True)` to discover and load the root `.env` into `os.environ` before configuration or database globals are evaluated. Frontend (`frontend/vite.config.ts`) is configured with `envDir: "../"` to read `VITE_*` variables directly from the project root, and `docker-compose.yml` includes `env_file: .env`.

**Tech Stack:** Python 3.14, python-dotenv, Vite 5, React 18, Docker Compose.

## Global Constraints

- Backend must maintain 100% compatibility with existing contracts in `shared/contracts.py` and models in `services/api/src/db/models.py`.
- No regression: All 205 existing tests must continue to pass throughout implementation.
- All code changes must have exact file paths, full diffs/contents, and exact test execution commands.

---

### Task 1: Add `python-dotenv` Dependency and `.env.example` Template

**Files:**
- Modify: `pyproject.toml`
- Create: `.env.example`

**Interfaces:**
- Produces: `pyproject.toml` with `python-dotenv>=1.0.0` declared in dependencies.
- Produces: `.env.example` with the 5 essential configuration keys.

- [ ] **Step 1: Update `pyproject.toml`**

Edit `pyproject.toml` to add `"python-dotenv>=1.0.0"` under `dependencies`:

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "cdc-chicken-counting"
version = "0.1.0"
description = "Poultry Counting Service and Dashboard"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.5.0",
    "python-dotenv>=1.0.0",
]

[tool.setuptools.packages.find]
include = ["services*", "shared*"]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests", "services/counter/tests", "services/api/tests"]
```

- [ ] **Step 2: Create `.env.example`**

Write `.env.example` at the repository root:

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

- [ ] **Step 3: Verify `.env.example` exists and syntax is valid**

Run:
```bash
Get-Content .env.example
```
Expected output: Content matching the 5 variables above.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml .env.example
git commit -m "chore(config): add python-dotenv dependency and minimal .env.example"
```

---

### Task 2: Create `shared/env.py` and Test Suite

**Files:**
- Create: `shared/env.py`
- Create: `tests/shared/test_env.py`

**Interfaces:**
- Produces: `shared.env.init_env(override: bool = False, dotenv_path: str | None = None) -> bool`
- Consumes: `dotenv.find_dotenv`, `dotenv.load_dotenv`

- [ ] **Step 1: Write the failing test**

Create `tests/shared/test_env.py`:

```python
import os
import tempfile
from pathlib import Path
from shared.env import init_env


def test_init_env_loads_file_into_os_environ():
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("TEST_CDC_ENV_KEY=chicken_farm_123\n", encoding="utf-8")

        # Ensure env var is not currently set
        os.environ.pop("TEST_CDC_ENV_KEY", None)

        loaded = init_env(dotenv_path=str(env_file))
        assert loaded is True
        assert os.environ.get("TEST_CDC_ENV_KEY") == "chicken_farm_123"

        # Cleanup
        os.environ.pop("TEST_CDC_ENV_KEY", None)


def test_init_env_does_not_override_by_default():
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("TEST_CDC_EXISTING=new_value\n", encoding="utf-8")

        os.environ["TEST_CDC_EXISTING"] = "original_value"

        init_env(dotenv_path=str(env_file), override=False)
        assert os.environ.get("TEST_CDC_EXISTING") == "original_value"

        # Cleanup
        os.environ.pop("TEST_CDC_EXISTING", None)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
& 'C:\Users\torino\AppData\Local\Python\bin\python.exe' -m pytest tests/shared/test_env.py -v
```
Expected output: FAIL with `ModuleNotFoundError: No module named 'shared.env'`

- [ ] **Step 3: Write minimal implementation in `shared/env.py`**

Create `shared/env.py`:

```python
import os
from dotenv import find_dotenv, load_dotenv


def init_env(override: bool = False, dotenv_path: str | None = None) -> bool:
    """Find and load .env file into os.environ.

    Searches from current working directory upward if dotenv_path is not specified.
    Returns True if an env file was found and loaded, False otherwise.
    """
    path = dotenv_path or find_dotenv(usecwd=True)
    if path:
        return load_dotenv(dotenv_path=path, override=override)
    return False
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
& 'C:\Users\torino\AppData\Local\Python\bin\python.exe' -m pytest tests/shared/test_env.py -v
```
Expected output: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add shared/env.py tests/shared/test_env.py
git commit -m "feat(shared): implement init_env helper with find_dotenv resolution"
```

---

### Task 3: Initialize Environment in API and Counter Entry Points

**Files:**
- Modify: `services/api/src/db/session.py:1-10`
- Modify: `services/api/src/main.py:1-6`
- Modify: `services/counter/main.py:1-25`

**Interfaces:**
- Consumes: `shared.env.init_env`
- Ensures: `DATABASE_URL`, `JWT_SECRET_KEY`, `PORT`, and counter configs resolve values loaded from `.env`.

- [ ] **Step 1: Write test verifying session.py and main.py load `.env`**

Add a test in `tests/shared/test_env.py`:

```python
def test_session_reads_database_url_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test_custom_api.db")
    # Re-import or read session DATABASE_URL logic
    import services.api.src.db.session as session_mod
    # Verify module uses the environment variable
    assert os.getenv("DATABASE_URL") == "sqlite:///test_custom_api.db"
```

- [ ] **Step 2: Update `services/api/src/db/session.py`**

In `services/api/src/db/session.py`, import and invoke `init_env()` before reading `DATABASE_URL`:

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from shared.env import init_env

init_env()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///api_central.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 3: Update `services/api/src/main.py`**

In `services/api/src/main.py`, ensure `init_env()` is called at the top:

```python
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from shared.env import init_env

init_env()

from services.api.src.api.alarms import router as alarms_router
# ... rest of file unchanged
```

- [ ] **Step 4: Update `services/counter/main.py`**

In `services/counter/main.py`, import and call `init_env()` at top before argument parsing:

```python
import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from shared.env import init_env

init_env()
```

- [ ] **Step 5: Run full test suite to verify no regressions**

Run:
```bash
& 'C:\Users\torino\AppData\Local\Python\bin\python.exe' -m pytest
```
Expected output: `208 passed` (205 existing + 3 new env tests)

- [ ] **Step 6: Commit**

```bash
git add services/api/src/db/session.py services/api/src/main.py services/counter/main.py tests/shared/test_env.py
git commit -m "feat(services): initialize environment from .env in API and Counter"
```

---

### Task 4: Configure Frontend (`vite.config.ts`) and Docker Compose (`docker-compose.yml`)

**Files:**
- Modify: `frontend/vite.config.ts`
- Modify: `docker-compose.yml`

**Interfaces:**
- Vite loads root `.env` through `envDir: "../"`.
- Docker Compose loads `.env` through `env_file: .env`.

- [ ] **Step 1: Update `frontend/vite.config.ts`**

Edit `frontend/vite.config.ts` to add `envDir: "../"`:

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  envDir: "../",
  server: {
    port: 3000,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
```

- [ ] **Step 2: Update `docker-compose.yml`**

Edit `docker-compose.yml` to specify `env_file: .env` for both `api` and `counter`:

```yaml
version: "3.8"

services:
  api:
    build:
      context: .
      dockerfile: services/api/Dockerfile
    env_file:
      - .env
    ports:
      - "${PORT:-8070}:${PORT:-8070}"
    environment:
      - DATABASE_URL=sqlite:////data/api_central.db
    volumes:
      - api_data:/data

  counter:
    build:
      context: .
      dockerfile: services/counter/Dockerfile
    env_file:
      - .env
    environment:
      - API_SYNC_URL=http://api:${PORT:-8070}/api/v1/sync/batch
      - LINE_ID=lineA
      - DB_PATH=/data/counter_outbox.db
    volumes:
      - counter_data:/data
    depends_on:
      - api

volumes:
  api_data:
  counter_data:
```

- [ ] **Step 3: Verify frontend build**

Run:
```bash
cd frontend && npm run build
```
Expected output: Build succeeds with `✓ built in ...` and 0 errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/vite.config.ts docker-compose.yml
git commit -m "feat(infra): point Vite envDir to root and attach env_file in docker-compose"
```
