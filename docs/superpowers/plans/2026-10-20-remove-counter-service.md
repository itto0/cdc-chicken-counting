# Remove Counter Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Completely decouple and remove the edge computer vision service (`services/counter`) and its associated edge artifacts from the repository while preserving cloud API ingestion contracts, database models, frontend, and tests.

**Architecture:** Define DTO schemas directly as authoritative models in `shared/contracts.py` eliminating dynamic fallback imports; purge `services/counter/` and edge runtime/deployment artifacts; clean `docker-compose.yml`, `pyproject.toml`, and deployment documentation; and verify all remaining test suites.

**Tech Stack:** Python 3.11+, Pydantic v2, Docker Compose, Pytest.

## Global Constraints

- Cloud API (`services/api`), Frontend (`frontend`), and PostgreSQL database configurations must remain intact and functional.
- Zero imports from `services.counter` anywhere in remaining code.
- `shared/contracts.py` must retain identical field names, types, constraints, and defaults for all 6 DTOs (`CountEventDTO`, `CountAggregateDTO`, `HealthSampleDTO`, `SyncBatchPayload`, `LineConfigDTO`, `AlarmDTO`).
- Test suites in `tests/` and `services/api/tests/` must execute cleanly.

---

### Task 1: Make `shared/contracts.py` Authoritative

**Files:**
- Modify: `shared/contracts.py:1-76`
- Test: `tests/shared/test_contracts.py`

**Interfaces:**
- Consumes: None (independent Pydantic DTOs)
- Produces: `CountEventDTO`, `CountAggregateDTO`, `HealthSampleDTO`, `SyncBatchPayload`, `LineConfigDTO`, `AlarmDTO` exported from `shared.contracts`

- [ ] **Step 1: Write a contract independence test**

Add a test in `tests/shared/test_contracts.py` verifying that `shared.contracts` can be imported without any reference to `services.counter` in `sys.modules`:

```python
def test_contracts_independent_of_counter_service():
    import sys
    import shared.contracts
    counter_modules = [m for m in sys.modules if m.startswith("services.counter")]
    assert counter_modules == [], f"shared.contracts leaked counter dependencies: {counter_modules}"
```

- [ ] **Step 2: Run test to verify it fails or exposes coupling**

Run:
```powershell
& "C:\Users\torino\AppData\Local\Python\bin\python.exe" -m pytest tests/shared/test_contracts.py::test_contracts_independent_of_counter_service -v
```
Expected: FAIL if `services.counter` is loaded by the `try: from services.counter...` import in `shared/contracts.py`.

- [ ] **Step 3: Refactor `shared/contracts.py` to define DTOs directly**

Replace lines 6-50 of `shared/contracts.py` so all models are defined directly without any `try / except ImportError`:

```python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class CountEventDTO(BaseModel):
    track_id: int
    ts_utc: datetime
    confidence: float = Field(ge=0.0, le=1.0)


class CountAggregateDTO(BaseModel):
    window_start: datetime
    window_end: datetime
    count: int = Field(ge=0)
    rate_per_min: float = Field(ge=0.0)
    confidence_avg: float = Field(ge=0.0, le=1.0)
    status: Literal["NORMAL", "WARNING", "CRITICAL"] = "NORMAL"


class HealthSampleDTO(BaseModel):
    fps: float = Field(ge=0.0)
    latency_p95_ms: float = Field(ge=0.0)
    cpu_pct: float = Field(ge=0.0, le=100.0)
    mem_pct: float = Field(ge=0.0, le=100.0)
    stream_state: Literal["ONLINE", "OFFLINE", "DEGRADED"] = "ONLINE"
    model_name: str = "yolo26n"
    model_version: str = "v1.0"


class SyncBatchPayload(BaseModel):
    line_id: str
    events: list[CountEventDTO] = Field(default_factory=list)
    aggregates: list[CountAggregateDTO] = Field(default_factory=list)
    health: HealthSampleDTO | None = None


class LineConfigDTO(BaseModel):
    line_id: str
    line_name: str = ""
    direction: str = "IN"
    coordinates: list[list[int]] = Field(default_factory=list)
    status: str = "ACTIVE"


class AlarmDTO(BaseModel):
    id: str
    line_id: str
    alarm_type: str
    severity: Literal["INFO", "WARNING", "CRITICAL"] = "WARNING"
    message: str
    ts_utc: datetime
    acknowledged: bool = False


__all__ = [
    "CountEventDTO",
    "CountAggregateDTO",
    "HealthSampleDTO",
    "SyncBatchPayload",
    "LineConfigDTO",
    "AlarmDTO",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
& "C:\Users\torino\AppData\Local\Python\bin\python.exe" -m pytest tests/shared/test_contracts.py -v
```
Expected: PASS (all 6 tests pass)

- [ ] **Step 5: Commit**

```bash
git add shared/contracts.py tests/shared/test_contracts.py
git commit -m "refactor(shared): define DTO contracts directly without counter dependency"
```

---

### Task 2: Remove `services/counter` Directory and Edge Counter Artifacts

**Files:**
- Delete: `services/counter/` (entire directory)
- Delete: `docker-compose.counter.yml`
- Delete: `cdc-counter.tar`
- Delete: `counter_outbox.db`
- Delete: `.env.counter.example`
- Delete: `docs/deployment-counter-dokploy-docker.md`

**Interfaces:**
- Consumes: `shared/contracts.py` (verified independent in Task 1)
- Produces: None

- [ ] **Step 1: Delete directory and artifact files**

Run:
```powershell
Remove-Item -Recurse -Force services/counter
Remove-Item -Force docker-compose.counter.yml -ErrorAction SilentlyContinue
Remove-Item -Force cdc-counter.tar -ErrorAction SilentlyContinue
Remove-Item -Force counter_outbox.db -ErrorAction SilentlyContinue
Remove-Item -Force .env.counter.example -ErrorAction SilentlyContinue
Remove-Item -Force docs/deployment-counter-dokploy-docker.md -ErrorAction SilentlyContinue
```

- [ ] **Step 2: Verify deleted files are gone**

Run:
```powershell
Test-Path services/counter, docker-compose.counter.yml, cdc-counter.tar, counter_outbox.db, .env.counter.example, docs/deployment-counter-dokploy-docker.md
```
Expected: `False, False, False, False, False, False`

- [ ] **Step 3: Run contracts test to ensure no regression**

Run:
```powershell
& "C:\Users\torino\AppData\Local\Python\bin\python.exe" -m pytest tests/shared/test_contracts.py -v
```
Expected: PASS

- [ ] **Step 4: Commit deletions**

```bash
git add -A
git commit -m "chore: remove counter service and edge deployment artifacts"
```

---

### Task 3: Remove `counter` Service from `docker-compose.yml`

**Files:**
- Modify: `docker-compose.yml:40-60,73`

**Interfaces:**
- Consumes: None
- Produces: Streamlined `docker-compose.yml` defining only `postgres`, `api`, and `frontend` services and `postgres_data` volume.

- [ ] **Step 1: Remove `counter` service block and `counter_data` volume from `docker-compose.yml`**

Edit `docker-compose.yml` so that `counter:` service (lines 40-60) and `counter_data:` volume under `volumes:` (line 73) are removed. The resulting file content must be:

```yaml
version: "3.8"

services:
  postgres:
    image: postgres:15-alpine
    container_name: cdc_postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgrespassword}
      POSTGRES_DB: chicken_counting
    ports:
      - "127.0.0.1:${POSTGRES_HOST_PORT:-5433}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d chicken_counting"]
      interval: 5s
      timeout: 5s
      retries: 5

  api:
    build:
      context: .
      dockerfile: services/api/Dockerfile
    env_file:
      - .env
    ports:
      - "${PORT:-8070}:${PORT:-8070}"
    environment:
      - DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD:-postgrespassword}@postgres:5432/chicken_counting
      - VIDEO_PATH=/samples/Rekaman_2.MOV
    volumes:
      - ./samples:/samples:ro
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "${FRONTEND_PORT:-8071}:80"
    depends_on:
      - api
    restart: unless-stopped

volumes:
  postgres_data:
```

- [ ] **Step 2: Validate YAML syntax of `docker-compose.yml`**

Run:
```powershell
& "C:\Users\torino\AppData\Local\Python\bin\python.exe" -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"
```
Expected: Exit code 0 (or if PyYAML not installed, check file structure without errors).

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "chore(docker): remove counter service and volume from docker-compose"
```

---

### Task 4: Update `pyproject.toml` Test Paths

**Files:**
- Modify: `pyproject.toml:20`

**Interfaces:**
- Consumes: None
- Produces: Updated `testpaths` configuration for `pytest`.

- [ ] **Step 1: Update `testpaths` in `pyproject.toml`**

Change line 20 from:
```toml
testpaths = ["tests", "services/counter/tests", "services/api/tests"]
```
to:
```toml
testpaths = ["tests", "services/api/tests"]
```

- [ ] **Step 2: Run pytest discovery check**

Run:
```powershell
& "C:\Users\torino\AppData\Local\Python\bin\python.exe" -m pytest --collect-only
```
Expected: Successfully collects tests from `tests` and `services/api/tests` without errors or warnings regarding missing `services/counter/tests`.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore(config): update pytest testpaths to remove counter tests"
```

---

### Task 5: Update `docs/deployment-render.md`

**Files:**
- Modify: `docs/deployment-render.md:196-281`

**Interfaces:**
- Consumes: None
- Produces: Clean deployment documentation reflecting cloud-only API and static frontend services.

- [ ] **Step 1: Remove Section 4 and renumber remaining sections**

In `docs/deployment-render.md`:
1. Delete lines 196-281 (Section 4: "Edge Node Configuration (`services/counter`)").
2. Renumber Section 5 ("5. Initial Login & Default Credentials") to Section 4 ("4. Initial Login & Default Credentials").
3. Renumber Section 6 ("6. Production & Free Tier Notes") to Section 5 ("5. Production & Free Tier Notes").

- [ ] **Step 2: Verify no lingering `services/counter` references in docs**

Run:
```powershell
Select-String -Path docs/deployment-render.md -Pattern "services/counter"
```
Expected: No matches returned.

- [ ] **Step 3: Commit**

```bash
git add docs/deployment-render.md
git commit -m "docs: remove counter edge service configuration from render deployment guide"
```

---

### Task 6: Comprehensive Verification

**Files:**
- Test: `tests/shared/test_contracts.py`
- Test: `services/api/tests/test_sync_endpoint.py`
- Test: `services/api/tests/test_counts_api.py`
- Test: `services/api/tests/test_auth_api.py`

**Interfaces:**
- Consumes: All updated files
- Produces: Test verification pass evidence

- [ ] **Step 1: Run contracts unit tests**

Run:
```powershell
& "C:\Users\torino\AppData\Local\Python\bin\python.exe" -m pytest tests/shared/test_contracts.py -v
```
Expected: PASS (6/6 passed)

- [ ] **Step 2: Run sync endpoint integration tests**

Run:
```powershell
& "C:\Users\torino\AppData\Local\Python\bin\python.exe" -m pytest services/api/tests/test_sync_endpoint.py -v
```
Expected: PASS (8/8 passed)

- [ ] **Step 3: Run core API suites**

Run:
```powershell
& "C:\Users\torino\AppData\Local\Python\bin\python.exe" -m pytest services/api/tests/test_counts_api.py services/api/tests/test_auth_api.py -v
```
Expected: PASS (all passed)

- [ ] **Step 4: Run repo-wide grep check for unwanted counter references**

Run:
```powershell
git grep "services.counter"
```
Expected: No matches in any source code file (only historical docs/specs if any).
