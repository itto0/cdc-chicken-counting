# Edge Counter Service Deployment Design (Dokploy & Docker)

## 1. Executive Summary

This specification defines the deployment architecture and operational configuration for running the **Edge Poultry Counter Service (`services/counter`)** independently on edge hardware or virtual private servers (VPS) managed via **Dokploy** or standard **Docker / Docker Compose**.

The counter operates decoupled from the central API, reading local or looped video files from a host-mounted directory, tracking chicken carcasses across a designated virtual line, maintaining an offline-resilient SQLite outbox buffer, and syncing count batches upstream to the central cloud API (such as our Render deployment) over secure outbound HTTPS.

---

## 2. Architecture & Data Flow

```text
+-------------------------------------------------------------------------------+
|  Edge Host Machine (Dokploy VPS / On-Premise Mini PC / Edge Server)           |
|                                                                               |
|   +-----------------------+           +-----------------------------------+   |
|   | Host ./samples Folder |           | Named Docker Volume               |   |
|   | (e.g. Rekaman_2.MOV)  |           | (counter_data: /data)             |   |
|   +-----------+-----------+           +-----------------+-----------------+   |
|               |                                         |                     |
|               | (read-only mount)                       | (read-write mount)  |
|               v                                         v                     |
|   +-----------------------------------------------------------------------+   |
|   |  Container: cdc-counter (built via services/counter/Dockerfile)       |   |
|   |                                                                       |   |
|   |  1. Capture: FileVideoSource (continuous loop mode)                   |   |
|   |  2. Detect & Track: ShackleDetector + VirtualLineZone (crossings)    |   |
|   |  3. Local Buffer: SQLite (/data/counter_outbox.db)                    |   |
|   |  4. Sync Dispatcher: OutboxSyncDispatcher (retries + exp backoff)     |   |
|   +-----------------------------------+-----------------------------------+   |
+---------------------------------------|---------------------------------------+
                                        | Outbound HTTPS POST
                                        | (/api/v1/sync/batch)
                                        v
                    +---------------------------------------+
                    |  Render Cloud Backend (cdc-api)       |
                    |  https://<cdc-api-subdomain>.onrender.com |
                    +---------------------------------------+
```

### Key Architectural Characteristics
1. **Zero Inbound Port Exposure**: The edge container runs headless and does not open any inbound HTTP/TCP ports. All network operations are outbound requests to the cloud API (`API_SYNC_URL`). Firewalls and NAT routers require zero configuration.
2. **Offline Outbox Resilience**: Network partitions or cloud API cold starts (such as Render free tier spin-up delays) do not stop chicken counting. Detections and telemetry samples are written immediately to `/data/counter_outbox.db`. When connection restores, the background sync thread flushes accumulated records automatically.
3. **Headless Execution**: OpenCV runs without X11/GUI display requirements (`opencv-python-headless`), logging real-time FPS, frame counters, and chicken counts directly to container `stdout`.

---

## 3. Configuration & Deliverables

### 3.1 Standalone Compose Specification (`docker-compose.counter.yml`)

A self-contained Compose file dedicated to the counter:

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

### 3.2 Environment Template (`.env.counter.example`)

A clean template file providing operators with all available configuration keys and explanations:
- `API_SYNC_URL`: Destination API batch sync endpoint (e.g., `https://cdc-api-xxxx.onrender.com/api/v1/sync/batch`)
- `LINE_ID`: Pre-seeded conveyor line identifier (`line-1` or `lineA`)
- `VIDEO_PATH`: Path inside container to the video file (`/samples/Rekaman_2.MOV`)
- `LOOP_VIDEO`: `1` for endless loop, `0` for single-pass
- `LINE_DIRECTION`: Crossing direction (`right`, `down`, `left`, `up`)
- `TARGET_FPS`: FPS pacing (`30.0` for real-time simulation, `0.0` for maximum speed)
- `SAMPLES_DIR`: Host path to local video directory (default: `./samples`)

### 3.3 Dokploy & Docker Operational Guide (`docs/deployment-counter-dokploy-docker.md`)

A comprehensive guide explaining:
1. **Architecture & Pre-requisites**: Video file placement, cloud API endpoint preparation.
2. **Dokploy Deployment (Option 1: Compose - Recommended)**:
   - Creating a new Project / Service in Dokploy.
   - Selecting "Compose" build type.
   - Supplying the repository or compose file.
   - Defining environment variables in Dokploy UI.
3. **Dokploy Deployment (Option 2: Application)**:
   - Selecting "Application" build type with Git provider.
   - Specifying Dockerfile path `services/counter/Dockerfile` and Context `.`.
   - Adding Volumes (`/data` to named volume, `/samples` to host path).
4. **Standard Docker CLI Deployment**:
   - `docker compose -f docker-compose.counter.yml up -d`
   - Standalone `docker run` command with `-v` and `-e` flags.
5. **Multi-Line Deployment**:
   - How to run concurrent counters for multiple conveyor lines (`line-1`, `lineA`) on a single Dokploy/Docker host.
6. **Verification, Log Inspection & Troubleshooting**:
   - Checking logs with `docker compose -f docker-compose.counter.yml logs -f counter`.
   - Verifying count progression in the cloud web dashboard (`cdc-frontend`).

---

## 4. Verification & Testing Strategy

1. **Docker Compose Syntax & Configuration Test**:
   - Automated pytest in `services/counter/tests/test_compose_counter.py` validating that `docker-compose.counter.yml` parses cleanly, references valid Dockerfile context, correct volume mounts, and all required environment variables.
2. **Headless Execution Test**:
   - Verify `services/counter/main.py` execution against a sample video in test mode with zero errors.
3. **Documentation Review**:
   - Ensure all sample commands, paths, and environment keys align with the existing codebase contracts.
