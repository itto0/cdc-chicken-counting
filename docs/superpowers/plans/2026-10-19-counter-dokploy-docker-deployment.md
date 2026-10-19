# Edge Counter Service Dokploy & Docker Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide an isolated, production-ready deployment configuration and comprehensive operational guide for running the edge poultry counter service independently on Dokploy or standard Docker/Docker Compose hosts.

**Architecture:** A standalone Docker container (`services/counter/Dockerfile`) processing looped or streaming video from a host-mounted directory (`/samples`), writing detections and telemetry to an offline-resilient SQLite outbox volume (`/data`), and continuously syncing count batches upstream to Render Cloud API (`https://<cdc-api-subdomain>.onrender.com/api/v1/sync/batch`).

**Tech Stack:** Docker, Docker Compose, Dokploy, Python 3.11, OpenCV Headless, SQLite, Pytest, YAML.

## Global Constraints

- Standalone manifest must be located at `docker-compose.counter.yml` at repository root.
- Environment variables must use safe defaults with parameter expansions `${VAR:-default}`.
- SQLite outbox database must be stored in named volume `counter_data` mounted at `/data`.
- Sample video directory must be mounted as read-only at `/samples`.
- Zero inbound ports exposed; all sync operations must be outbound HTTPS requests to `API_SYNC_URL`.
- Container restart policy must be `unless-stopped`.

---

### Task 1: Standalone Docker Compose Manifest and Environment Template

**Files:**
- Create: `docker-compose.counter.yml`
- Create: `.env.counter.example`
- Test: `services/counter/tests/test_compose_counter.py`

**Interfaces:**
- Consumes: `services/counter/Dockerfile` (Docker build context: `.`)
- Produces: `docker-compose.counter.yml` manifest consumable by Dokploy Compose and Docker CLI.

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path
import yaml


def test_counter_compose_structure():
    root_dir = Path(__file__).resolve().parents[3]
    compose_path = root_dir / "docker-compose.counter.yml"
    assert compose_path.exists(), "docker-compose.counter.yml must exist at repository root"

    with open(compose_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    assert "services" in config, "services key is required"
    assert "counter" in config["services"], "counter service must be defined"

    counter = config["services"]["counter"]
    assert counter["build"]["context"] == "."
    assert counter["build"]["dockerfile"] == "services/counter/Dockerfile"
    assert counter["restart"] == "unless-stopped"

    # Environment checks
    env = counter.get("environment", [])
    env_keys = [e.split("=")[0] if isinstance(e, str) else list(e.keys())[0] for e in env]
    assert any("LINE_ID" in k for k in env_keys)
    assert any("API_SYNC_URL" in k for k in env_keys)
    assert any("VIDEO_PATH" in k for k in env_keys)
    assert any("DB_PATH" in k for k in env_keys)

    # Volume checks
    volumes = counter.get("volumes", [])
    assert any("counter_data:/data" in v for v in volumes)
    assert any(":/samples:ro" in v for v in volumes)

    # Named volume definition
    assert "volumes" in config and "counter_data" in config["volumes"]


def test_env_counter_example_exists():
    root_dir = Path(__file__).resolve().parents[3]
    env_example_path = root_dir / ".env.counter.example"
    assert env_example_path.exists(), ".env.counter.example must exist at repository root"

    content = env_example_path.read_text(encoding="utf-8")
    assert "API_SYNC_URL=" in content
    assert "LINE_ID=" in content
    assert "VIDEO_PATH=" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest services/counter/tests/test_compose_counter.py -v`
Expected: FAIL with `AssertionError: docker-compose.counter.yml must exist at repository root`

- [ ] **Step 3: Create `docker-compose.counter.yml` and `.env.counter.example`**

`docker-compose.counter.yml`:
```yaml
version: "3.8"

services:
  counter:
    build:
      context: .
      dockerfile: services/counter/Dockerfile
    container_name: cdc-counter
    restart: unless-stopped
    environment:
      - LINE_ID=${LINE_ID:-line-1}
      - VIDEO_PATH=${VIDEO_PATH:-/samples/Rekaman_2.MOV}
      - LOOP_VIDEO=${LOOP_VIDEO:-1}
      - LINE_DIRECTION=${LINE_DIRECTION:-right}
      - TARGET_FPS=${TARGET_FPS:-30.0}
      - API_SYNC_URL=${API_SYNC_URL:-https://cdc-api.onrender.com/api/v1/sync/batch}
      - DB_PATH=/data/counter_outbox.db
      - SYNC_INTERVAL_SEC=${SYNC_INTERVAL_SEC:-5.0}
      - HEALTH_INTERVAL_SEC=${HEALTH_INTERVAL_SEC:-10.0}
      - CONF_THRESHOLD=${CONF_THRESHOLD:-0.7}
      - OCCUPANCY_THRESHOLD=${OCCUPANCY_THRESHOLD:-4.5}
    volumes:
      - counter_data:/data
      - ${SAMPLES_DIR:-./samples}:/samples:ro

volumes:
  counter_data:
```

`.env.counter.example`:
```ini
# ==============================================================================
# Edge Poultry Counter Service - Environment Configuration Template
# ==============================================================================

# Central Cloud API endpoint for syncing counting batches and health telemetry
# Replace <cdc-api-subdomain> with your Render cloud service URL
API_SYNC_URL=https://<cdc-api-subdomain>.onrender.com/api/v1/sync/batch

# Conveyor Line Identifier (must match a registered line in central API: line-1 or lineA)
LINE_ID=line-1

# Path to the video file inside the container (mounted from SAMPLES_DIR)
VIDEO_PATH=/samples/Rekaman_2.MOV

# Local directory on host containing the video files
SAMPLES_DIR=./samples

# Video playback looping (1 = loop endlessly, 0 = stop at EOF)
LOOP_VIDEO=1

# Virtual line crossing direction (right, left, down, up)
LINE_DIRECTION=right

# Frame rate pacing (30.0 for real-time camera simulation, 0.0 for maximum unthrottled throughput)
TARGET_FPS=30.0

# Sync interval in seconds for background batch dispatcher
SYNC_INTERVAL_SEC=5.0

# Telemetry health recording interval in seconds
HEALTH_INTERVAL_SEC=10.0

# Detector confidence threshold
CONF_THRESHOLD=0.7

# Carcass occupancy threshold for ShackleDetector (empty shackle rejection)
OCCUPANCY_THRESHOLD=4.5
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest services/counter/tests/test_compose_counter.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add docker-compose.counter.yml .env.counter.example services/counter/tests/test_compose_counter.py
git commit -m "feat(counter): add standalone compose manifest and env template for dokploy and docker"
```

---

### Task 2: Dokploy & Docker Operational Deployment Guide

**Files:**
- Create: `docs/deployment-counter-dokploy-docker.md`

**Interfaces:**
- Consumes: `docker-compose.counter.yml`, `.env.counter.example`, `services/counter/Dockerfile`
- Produces: Production deployment documentation for operators using Dokploy or Docker CLI.

- [ ] **Step 1: Write `docs/deployment-counter-dokploy-docker.md`**

Create comprehensive guide covering:
1. Overview & Architecture (Edge to Cloud topology).
2. Option 1: Dokploy Compose Deployment (recommended: Projects > New Service > Compose).
3. Option 2: Dokploy Application Deployment (Projects > New Service > Application > Dockerfile build).
4. Option 3: Standard Docker Compose CLI (`docker compose -f docker-compose.counter.yml up -d`).
5. Option 4: Standalone Docker Run CLI (`docker build` + `docker run`).
6. Running Multiple Conveyor Lines (e.g. `line-1` and `lineA` concurrently).
7. Inspection, Verification & Troubleshooting (viewing stdout logs, verifying SQLite outbox, checking Render API sync).

- [ ] **Step 2: Verify links and commands**

Check that all paths, file references, and CLI flags in the documentation match the codebase.

- [ ] **Step 3: Commit**

```bash
git add docs/deployment-counter-dokploy-docker.md
git commit -m "docs: add dokploy and docker deployment guide for edge counter service"
```

---

### Task 3: Full Test Suite Verification & Smoke Test

**Files:**
- Test: All tests in `services/counter/tests/` and `services/api/tests/`

- [ ] **Step 1: Run counter test suite**

Run: `py -m pytest services/counter/tests/ -v`
Expected: PASS (all tests pass)

- [ ] **Step 2: Run backend test suite**

Run: `py -m pytest services/api/tests/ -v`
Expected: PASS (179 passed)

- [ ] **Step 3: Verify git working tree**

Run: `git status`
Expected: Clean working tree on branch.
