# Standalone Counter Service Design Specification

- **Date:** 2026-10-19
- **Status:** Approved
- **Target:** `services/counter`
- **Goal:** Decouple `services/counter` from the monorepo root so it can be built, packaged, deployed, or extracted into a separate Git repository completely self-contained, without any dependency on external monorepo files (`shared/` or root `context: .`).

---

## 1. Context & Motivation

Currently, the edge counter service lives in `services/counter/` within the `cdc-chicken-counting` monorepo. It relies on:
1. `shared/contracts.py` for Pydantic DTOs (`CountEventDTO`, `CountAggregateDTO`, `HealthSampleDTO`, `SyncBatchPayload`).
2. `shared/env.py` for `.env` initialization.
3. `services/counter/Dockerfile` requiring `COPY shared /app/shared` and `COPY services/counter /app/services/counter`, which mandates that Docker builds must run from the repository root (`context: .`).
4. Monorepo import paths such as `from services.counter.src...` and `from shared.contracts...`.

When deploying on Dokploy, edge gateways, or standalone Docker servers, operators frequently attempt to point Docker directly to `services/counter` as the build context, or clone only the counter folder. Under the current setup, builds fail because Docker cannot access files outside its context.

By making `services/counter` a **self-contained standalone service**, edge operators can:
- Clone or copy just the `services/counter` directory to an edge machine.
- Build the Docker image with context `services/counter` (`docker build -t cdc-counter .`).
- Run the service directly with `python main.py` or inside Docker with zero monorepo dependencies.
- Continue running all monorepo backend API tests and Compose workflows seamlessly.

---

## 2. Architecture & File Structure

The `services/counter/` directory becomes fully autonomous:

```text
services/counter/
├── Dockerfile                  # Self-contained build (context: .)
├── requirements.txt            # Explicit runtime Python dependencies
├── main.py                     # Entrypoint (supports standalone & monorepo)
├── benchmark.py                # Benchmark runner
├── generate_sample_video.py    # Synthetic video generator
├── README.md                   # Standalone service documentation
├── src/
│   ├── contracts.py            # Local Pydantic DTO definitions
│   ├── env.py                  # Local .env loader
│   ├── capture/
│   │   ├── __init__.py
│   │   └── source.py           # Video capture implementations
│   ├── detection/
│   │   ├── __init__.py
│   │   └── detector.py         # Shackle & mock detectors
│   ├── tracking/
│   │   ├── __init__.py
│   │   └── tracker.py          # Line crossing & counting engine
│   ├── storage/
│   │   ├── __init__.py
│   │   └── db.py               # SQLite WAL outbox persistence
│   └── sync/
│       ├── __init__.py
│       └── dispatcher.py       # Decoupled HTTP batch syncer
└── tests/                      # Dedicated counter unit tests (pytest)
```

---

## 3. Decoupling & Import Strategy

### 3.1 Self-Contained Contracts (`services/counter/src/contracts.py`)
`services/counter/src/contracts.py` defines the canonical Pydantic contracts required by the edge runner:
- `CountEventDTO`: Single crossing event (`track_id`, `ts_utc`, `confidence`).
- `CountAggregateDTO`: Aggregated window metrics (`window_start`, `window_end`, `count`, `rate_per_min`, `confidence_avg`, `status`).
- `HealthSampleDTO`: Runtime telemetry (`fps`, `latency_p95_ms`, `cpu_pct`, `mem_pct`, `stream_state`, `model_name`, `model_version`).
- `SyncBatchPayload`: Outbound sync batch payload (`line_id`, `events`, `aggregates`, `health`).

### 3.2 Monorepo Re-Export (`shared/contracts.py`)
To preserve single-source-of-truth across the monorepo, `shared/contracts.py` re-exports the DTOs from `services.counter.src.contracts` with a fallback definition, ensuring `services/api` continues to consume identical types:
```python
try:
    from services.counter.src.contracts import (
        CountAggregateDTO,
        CountEventDTO,
        HealthSampleDTO,
        SyncBatchPayload,
    )
except ImportError:
    # Local fallback definitions if counter package is not in python path
    ...
```

### 3.3 Dual-Compatible Import Resolution
To allow executing `main.py` directly as a script (`python main.py`), as a package (`python -m services.counter.main`), or within Docker (`CMD ["python", "main.py"]`):
1. In `services/counter/main.py`:
   ```python
   import sys
   from pathlib import Path

   # Ensure both local counter directory and monorepo root are accessible in sys.path
   counter_dir = Path(__file__).resolve().parent
   monorepo_dir = counter_dir.parent.parent
   for directory in (counter_dir, monorepo_dir):
       dir_str = str(directory)
       if dir_str not in sys.path:
           sys.path.insert(0, dir_str)
   ```
2. In internal counter modules (`src/storage/db.py`, `src/tracking/tracker.py`, `src/sync/dispatcher.py`):
   Use dual-import fallbacks for internal references:
   ```python
   try:
       from src.contracts import CountAggregateDTO, CountEventDTO, HealthSampleDTO
   except ImportError:
       from services.counter.src.contracts import (
           CountAggregateDTO,
           CountEventDTO,
           HealthSampleDTO,
       )
   ```

---

## 4. Standalone Docker Configuration

### 4.1 Standalone `requirements.txt` (`services/counter/requirements.txt`)
Contains pinned minimal dependencies required for edge execution:
```text
opencv-python-headless>=4.8.0
numpy>=1.24.0
pydantic>=2.5.0
httpx>=0.27.0
python-dotenv>=1.0.0
```

### 4.2 Standalone `Dockerfile` (`services/counter/Dockerfile`)
The Dockerfile is refactored so its build context is strictly `./services/counter`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only counter service files
COPY . /app

RUN mkdir -p /data /app/data

ENV PYTHONPATH=/app
ENV LINE_ID=line-1
ENV VIDEO_SOURCE_TYPE=synthetic
ENV API_SYNC_URL=http://localhost:8000/api/v1/sync/batch
ENV DB_PATH=/data/counter_outbox.db
ENV SYNC_INTERVAL_SEC=5.0

CMD ["python", "main.py"]
```

### 4.3 Root Compose Manifest (`docker-compose.counter.yml`)
Updated to point its build context to `./services/counter`:
```yaml
version: "3.8"

services:
  counter:
    build:
      context: ./services/counter
      dockerfile: Dockerfile
    container_name: cdc-counter
    restart: unless-stopped
    ...
```

---

## 5. Verification & Testing

1. **Unit Tests**:
   - Run `py -m pytest services/counter/tests/ -v` (assert 88+ passing).
   - Run `py -m pytest services/api/tests/ -v` (assert 179+ passing with re-exported contracts).
2. **Standalone Execution Smoke Test**:
   - Execute `python main.py --help` directly from within `services/counter/` without setting `PYTHONPATH`.
3. **Standalone Docker Build Verification**:
   - Execute `docker build -t cdc-counter-test ./services/counter` (confirm build succeeds with isolated context).
4. **Dokploy & Docker Compose Verification**:
   - Validate `docker-compose.counter.yml` config using `services/counter/tests/test_compose_counter.py`.

---

## 6. Migration & Rollback Strategy

- All changes are additive and backward-compatible.
- `shared/contracts.py` continues to provide the identical models to `services/api`.
- Existing monorepo test scripts and CI pipelines remain fully supported.
