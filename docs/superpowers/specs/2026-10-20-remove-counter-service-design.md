# Remove Edge Counter Service Design Specification

- **Date:** 2026-10-20
- **Status:** Approved
- **Target:** Full clean removal of `services/counter` and edge counter artifacts
- **Goal:** Decouple the `cdc-chicken-counting` repository completely from the edge counter service, establishing this repository as dedicated exclusively to the Central Data API, PostgreSQL, and Frontend Dashboard.

---

## 1. Context & Motivation

Historically, `cdc-chicken-counting` hosted the edge counter service under `services/counter/` alongside the Central API (`services/api/`) and Frontend (`frontend/`). The counter service was previously refactored to be self-contained so that edge gateways could run it independently.

The edge counter is now maintained in its own dedicated repository. Maintaining `services/counter/`, outdated deployment guides, and counter-specific Docker compose definitions within this repository creates technical debt, confusion during cloud/Render deployments, and risk of accidental regressions.

Removing the edge counter service from this repository leaves a clean, focused monorepo for the Central Cloud API and Dashboard.

---

## 2. Scope of Changes

### 2.1 File & Directory Deletions
1. **Source & Tests:**
   - Delete `services/counter/` directory entirely (including `main.py`, `benchmark.py`, `generate_sample_video.py`, `Dockerfile`, `README.md`, `src/`, and `tests/`).
2. **Docker & Runtime Artifacts:**
   - Delete `docker-compose.counter.yml`
   - Delete `cdc-counter.tar`
   - Delete `counter_outbox.db`
   - Delete `.env.counter.example`
3. **Documentation:**
   - Delete `docs/deployment-counter-dokploy-docker.md`

### 2.2 File Modifications
1. **`shared/contracts.py`:**
   - Remove the `try: from services.counter.src.contracts import ...` import block.
   - Declare canonical Pydantic models directly:
     - `CountEventDTO`
     - `CountAggregateDTO`
     - `HealthSampleDTO`
     - `SyncBatchPayload`
     - `LineConfigDTO`
     - `AlarmDTO`
   - Maintain full backwards compatibility for all Central API endpoints and tests importing from `shared.contracts`.
2. **`docker-compose.yml`:**
   - Remove the `counter` service definition.
   - Remove the `counter_data` volume definition.
   - Retain `postgres`, `api`, `frontend`, and `postgres_data`.
3. **`pyproject.toml`:**
   - Update `[tool.pytest.ini_options]` `testpaths` from `["tests", "services/counter/tests", "services/api/tests"]` to `["tests", "services/api/tests"]`.
4. **`docs/deployment-render.md`:**
   - Remove Section 4 (`Edge Node Configuration (services/counter)`).
   - Update the architecture table and overview to state that edge counter nodes are deployed separately from their dedicated standalone repository.

---

## 3. Data Contracts Compatibility

The Data API consumes JSON payloads synced from edge devices according to `SyncBatchPayload`. Making `shared/contracts.py` self-contained ensures:
- Central API endpoints (`/api/v1/sync/batch`, `/api/v1/counts/*`, `/api/v1/summary/*`, etc.) continue to validate and parse payloads without any code changes.
- Existing unit and integration tests under `tests/` and `services/api/tests/` that import `shared.contracts` continue to pass without changes.

---

## 4. Verification & Testing Strategy

1. **Automated Unit Tests:**
   - Run `pytest tests/` to verify shared contracts and utilities pass.
   - Run `pytest services/api/tests/` to verify all Central API routes, models, serializers, and sync handlers work correctly.
2. **Docker Compose Validation:**
   - Run `docker compose config` to verify syntax validity of `docker-compose.yml` without the removed counter service.
3. **Grep Reference Audit:**
   - Scan the codebase to ensure no remaining active code in `services/api/`, `frontend/`, or `shared/` imports or references deleted counter paths.
