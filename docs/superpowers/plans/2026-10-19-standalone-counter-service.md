# Standalone Counter Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decouple `services/counter` from the monorepo root so it can be built, packaged, deployed, or extracted into a separate Git repository completely self-contained, without any dependency on external monorepo files (`shared/` or root `context: .`).

**Architecture:** Move edge contracts (`CountEventDTO`, `CountAggregateDTO`, `HealthSampleDTO`, `SyncBatchPayload`) and environment loading directly inside `services/counter/src/`. Have `shared/contracts.py` re-export them for the central API. Adapt `services/counter/main.py` and internal modules to support both standalone folder execution and monorepo execution. Scope `services/counter/Dockerfile` and `docker-compose.counter.yml` to `./services/counter` context.

**Tech Stack:** Python 3.11+, Pydantic v2, OpenCV headless, NumPy, HTTPX, Docker, Docker Compose, Pytest.

## Global Constraints

- Python compatibility: Python 3.11+.
- Pydantic compatibility: Pydantic 2.x.
- Zero breaking changes to `services/api` or existing monorepo tests.
- `services/counter/Dockerfile` must build using only files inside `services/counter` (`context: ./services/counter`).
- All 88+ counter tests and 179+ API tests must pass without regression.

---

### Task 1: Self-Contained Contracts & Environment Loader

**Files:**
- Create: `services/counter/src/contracts.py`
- Create: `services/counter/src/env.py`
- Modify: `services/counter/src/storage/db.py:1-15`
- Modify: `services/counter/src/tracking/tracker.py:1-12`
- Modify: `services/counter/src/sync/dispatcher.py:1-15`
- Modify: `shared/contracts.py:1-25`
- Test: `services/counter/tests/test_contracts.py`

**Interfaces:**
- Produces: `CountEventDTO`, `CountAggregateDTO`, `HealthSampleDTO`, `SyncBatchPayload` in `services/counter/src/contracts.py`.
- Produces: `init_env` in `services/counter/src/env.py`.
- Consumes: Standard library + Pydantic v2 + python-dotenv.

- [ ] **Step 1: Write the failing test for local contracts**

```python
# services/counter/tests/test_contracts.py
from datetime import datetime, timezone
import pytest


def test_standalone_contracts_import():
    from services.counter.src.contracts import (
        CountAggregateDTO,
        CountEventDTO,
        HealthSampleDTO,
        SyncBatchPayload,
    )

    now = datetime.now(timezone.utc)
    event = CountEventDTO(track_id=1, ts_utc=now, confidence=0.95)
    assert event.track_id == 1
    assert event.confidence == 0.95

    agg = CountAggregateDTO(
        window_start=now,
        window_end=now,
        count=10,
        rate_per_min=120.0,
        confidence_avg=0.92,
        status="NORMAL",
    )
    assert agg.count == 10

    health = HealthSampleDTO(
        fps=30.0,
        latency_p95_ms=5.0,
        cpu_pct=15.0,
        mem_pct=25.0,
        stream_state="ONLINE",
    )
    assert health.stream_state == "ONLINE"

    batch = SyncBatchPayload(line_id="line-1", events=[event], aggregates=[agg], health=health)
    assert batch.line_id == "line-1"
    assert len(batch.events) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest services/counter/tests/test_contracts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.counter.src.contracts'`

- [ ] **Step 3: Implement local contracts and env loader**

Create `services/counter/src/contracts.py`:
```python
"""Self-contained data contracts for the edge counter service."""

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


__all__ = [
    "CountEventDTO",
    "CountAggregateDTO",
    "HealthSampleDTO",
    "SyncBatchPayload",
]
```

Create `services/counter/src/env.py`:
```python
"""Self-contained environment initialization for the edge counter service."""

from dotenv import find_dotenv, load_dotenv


def init_env(override: bool = False, dotenv_path: str | None = None) -> bool:
    """Find and load .env file into os.environ."""
    path = dotenv_path or find_dotenv(usecwd=True)
    if path:
        return load_dotenv(dotenv_path=path, override=override)
    return False
```

Update imports in `services/counter/src/storage/db.py`:
```python
try:
    from src.contracts import (
        CountAggregateDTO,
        CountEventDTO,
        HealthSampleDTO,
        SyncBatchPayload,
    )
except ImportError:
    try:
        from services.counter.src.contracts import (
            CountAggregateDTO,
            CountEventDTO,
            HealthSampleDTO,
            SyncBatchPayload,
        )
    except ImportError:
        from shared.contracts import (
            CountAggregateDTO,
            CountEventDTO,
            HealthSampleDTO,
            SyncBatchPayload,
        )
```

Update imports in `services/counter/src/tracking/tracker.py`:
```python
try:
    from src.contracts import CountEventDTO
except ImportError:
    try:
        from services.counter.src.contracts import CountEventDTO
    except ImportError:
        from shared.contracts import CountEventDTO
```

Update `shared/contracts.py` to re-export from `services.counter.src.contracts`:
```python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

try:
    from services.counter.src.contracts import (
        CountAggregateDTO,
        CountEventDTO,
        HealthSampleDTO,
        SyncBatchPayload,
    )
except ImportError:
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest services/counter/tests/test_contracts.py -v`
Expected: PASS

- [ ] **Step 5: Verify existing counter tests still pass**

Run: `py -m pytest services/counter/tests/test_storage.py services/counter/tests/test_tracking.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add services/counter/src/contracts.py services/counter/src/env.py services/counter/src/storage/db.py services/counter/src/tracking/tracker.py shared/contracts.py services/counter/tests/test_contracts.py
git commit -m "refactor(counter): add self-contained contracts and env loader"
```

---

### Task 2: Dual-Compatible Entrypoint & Standalone Execution Tests

**Files:**
- Modify: `services/counter/main.py:1-40`
- Modify: `services/counter/benchmark.py:1-25`
- Test: `services/counter/tests/test_standalone_import.py`

**Interfaces:**
- Consumes: `services/counter/src/contracts.py`, `services/counter/src/env.py`.
- Produces: Resilient entrypoint executable both as `python main.py` directly from `services/counter` and as `python -m services.counter.main` from monorepo root.

- [ ] **Step 1: Write the failing test for isolated standalone import**

```python
# services/counter/tests/test_standalone_import.py
import subprocess
import sys
from pathlib import Path


def test_main_cli_help_as_standalone():
    """Verify that main.py can run --help directly without relying on monorepo PYTHONPATH."""
    counter_dir = Path(__file__).resolve().parent.parent
    
    # Run python main.py --help with cwd=services/counter and clean env (no PYTHONPATH)
    env = {}
    import os
    for k, v in os.environ.items():
        if k != "PYTHONPATH":
            env[k] = v

    result = subprocess.run(
        [sys.executable, "main.py", "--help"],
        cwd=str(counter_dir),
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )
    assert result.returncode == 0, f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    assert "Poultry Counting System - Edge Counter Service" in result.stdout or "usage:" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest services/counter/tests/test_standalone_import.py -v`
Expected: FAIL (because `main.py` currently imports `from shared.env import init_env` and `from services.counter.src...`)

- [ ] **Step 3: Update `services/counter/main.py` and `benchmark.py`**

In `services/counter/main.py`:
Update sys.path and imports at top of file:
```python
import sys
from pathlib import Path

# Add both counter root and monorepo root to sys.path
counter_root = Path(__file__).resolve().parent
monorepo_root = counter_root.parent.parent
for p in (counter_root, monorepo_root):
    p_str = str(p)
    if p_str not in sys.path:
        sys.path.insert(0, p_str)

# Self-contained env loader
try:
    from src.env import init_env
except ImportError:
    try:
        from services.counter.src.env import init_env
    except ImportError:
        from shared.env import init_env

init_env()

# Self-contained modules
try:
    from src.capture.source import (
        FileVideoSource,
        SyntheticVideoSource,
        VideoSource,
    )
    from src.contracts import CountAggregateDTO, HealthSampleDTO
    from src.detection.detector import Detector, MockDetector, ShackleDetector
    from src.storage.db import LocalStorage
    from src.sync.dispatcher import OutboxSyncDispatcher
    from src.tracking.tracker import ChickenCounter, VirtualLineZone
except ImportError:
    from services.counter.src.capture.source import (
        FileVideoSource,
        SyntheticVideoSource,
        VideoSource,
    )
    from services.counter.src.contracts import CountAggregateDTO, HealthSampleDTO
    from services.counter.src.detection.detector import Detector, MockDetector, ShackleDetector
    from services.counter.src.storage.db import LocalStorage
    from services.counter.src.sync.dispatcher import OutboxSyncDispatcher
    from services.counter.src.tracking.tracker import ChickenCounter, VirtualLineZone
```

Similarly update `services/counter/benchmark.py` to use dual-compatible imports.

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest services/counter/tests/test_standalone_import.py -v`
Expected: PASS

- [ ] **Step 5: Verify full counter test suite passes**

Run: `py -m pytest services/counter/tests/ -v`
Expected: PASS (all 89+ tests pass)

- [ ] **Step 6: Commit**

```bash
git add services/counter/main.py services/counter/benchmark.py services/counter/tests/test_standalone_import.py
git commit -m "feat(counter): make entrypoints dual-compatible for standalone execution"
```

---

### Task 3: Standalone Dockerfile, Requirements & Compose Update

**Files:**
- Create: `services/counter/requirements.txt`
- Create: `services/counter/README.md`
- Modify: `services/counter/Dockerfile`
- Modify: `docker-compose.counter.yml`
- Modify: `services/counter/tests/test_compose_counter.py`

**Interfaces:**
- Produces: Standalone Docker build configuration scoped strictly to `services/counter`.
- Produces: `requirements.txt` containing pinned edge dependencies.

- [ ] **Step 1: Write failing test for compose context update**

Update `services/counter/tests/test_compose_counter.py`:
```python
def test_counter_compose_structure():
    # ...
    # Verify build context is scoped to ./services/counter
    build = counter.get("build", {})
    assert build.get("context") in ("./services/counter", "services/counter"), (
        "Build context must point to ./services/counter for standalone builds"
    )
    assert build.get("dockerfile") == "Dockerfile"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest services/counter/tests/test_compose_counter.py -v`
Expected: FAIL with `AssertionError: Build context must point to ./services/counter for standalone builds`

- [ ] **Step 3: Implement `requirements.txt`, update `Dockerfile`, `docker-compose.counter.yml`, and `README.md`**

Create `services/counter/requirements.txt`:
```text
opencv-python-headless>=4.8.0
numpy>=1.24.0
pydantic>=2.5.0
httpx>=0.27.0
python-dotenv>=1.0.0
```

Update `services/counter/Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies from local requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only counter service files (completely self-contained)
COPY . /app

# Create data directory for local outbox SQLite database
RUN mkdir -p /data /app/data

ENV PYTHONPATH=/app
ENV LINE_ID=line-1
ENV VIDEO_SOURCE_TYPE=synthetic
ENV API_SYNC_URL=http://localhost:8000/api/v1/sync/batch
ENV DB_PATH=/data/counter_outbox.db
ENV SYNC_INTERVAL_SEC=5.0

CMD ["python", "main.py"]
```

Update `docker-compose.counter.yml`:
```yaml
version: "3.8"

services:
  counter:
    build:
      context: ./services/counter
      dockerfile: Dockerfile
    container_name: cdc-counter
    restart: unless-stopped
    environment:
      - LINE_ID=${LINE_ID:-line-1}
      - VIDEO_PATH=${VIDEO_PATH:-/samples/Rekaman_2.MOV}
      - LOOP_VIDEO=${LOOP_VIDEO:-1}
      - LINE_DIRECTION=${LINE_DIRECTION:-right}
      - TARGET_FPS=${TARGET_FPS:-30.0}
      - API_SYNC_URL=${API_SYNC_URL:-http://localhost:8000/api/v1/sync/batch}
      - DB_PATH=${DB_PATH:-/data/counter_outbox.db}
      - SYNC_INTERVAL_SEC=${SYNC_INTERVAL_SEC:-5.0}
      - HEALTH_INTERVAL_SEC=${HEALTH_INTERVAL_SEC:-10.0}
      - CONF_THRESHOLD=${CONF_THRESHOLD:-0.60}
      - OCCUPANCY_THRESHOLD=${OCCUPANCY_THRESHOLD:-0.15}
    volumes:
      - counter_data:/data
      - ${SAMPLES_DIR:-./samples}:/samples:ro

volumes:
  counter_data:
```

Create `services/counter/README.md`:
Document standalone usage, local execution (`python main.py`), standalone Docker builds (`docker build -t cdc-counter .`), and volume configurations.

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest services/counter/tests/test_compose_counter.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/counter/requirements.txt services/counter/Dockerfile docker-compose.counter.yml services/counter/tests/test_compose_counter.py services/counter/README.md
git commit -m "feat(counter): enable standalone docker build with scoped context and requirements"
```

---

### Task 4: Full Suite Verification & Monorepo Integration Test

**Files:**
- Modify: `docs/deployment-counter-dokploy-docker.md` (Update build context notes to reflect standalone `./services/counter`)
- Test: All test suites (`services/counter/tests/`, `services/api/tests/`)

- [ ] **Step 1: Run the full counter test suite**

Run: `py -m pytest services/counter/tests/ -v`
Expected: All 90+ tests pass.

- [ ] **Step 2: Run the full backend API test suite**

Run: `py -m pytest services/api/tests/ -v`
Expected: All 179+ tests pass (confirming `shared/contracts.py` re-exports work seamlessly).

- [ ] **Step 3: Update deployment guide with standalone context notes**

In `docs/deployment-counter-dokploy-docker.md`, update sections mentioning build context to clarify that `services/counter` can now be built directly from its own directory with `context: ./services/counter` or `context: .` when inside `services/counter/`.

- [ ] **Step 4: Commit**

```bash
git add docs/deployment-counter-dokploy-docker.md
git commit -m "docs(counter): update deployment guide to reflect standalone build context"
```

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-10-19-standalone-counter-service.md`.
