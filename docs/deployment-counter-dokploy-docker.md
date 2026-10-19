# Deployment Guide: Edge Counter Service (Dokploy & Docker)

This guide provides production-ready, step-by-step instructions for deploying and operating the **Edge Poultry Counter Service (`services/counter`)** on edge servers, virtual private servers (VPS), or on-premise industrial gateways using **Dokploy** or standard **Docker / Docker Compose**.

---

## Table of Contents

1. [Architecture & Topology](#1-architecture--topology)
2. [Pre-requisites & Preparation](#2-pre-requisites--preparation)
3. [Configuration Reference](#3-configuration-reference)
4. [Option 1: Dokploy Compose Deployment (Recommended)](#4-option-1-dokploy-compose-deployment-recommended)
5. [Option 2: Dokploy Application Deployment](#5-option-2-dokploy-application-deployment)
6. [Option 3: Standard Docker Compose CLI](#6-option-3-standard-docker-compose-cli)
7. [Option 4: Standalone Docker Run CLI](#7-option-4-standalone-docker-run-cli)
8. [Multi-Line Deployment (Parallel Conveyors)](#8-multi-line-deployment-parallel-conveyors)
9. [Verification, Log Inspection & Troubleshooting](#9-verification-log-inspection--troubleshooting)

---

## 1. Architecture & Topology

The edge counter service operates autonomously at the conveyor line, reading video frames from camera feeds or loop-mounted video files, detecting and tracking chicken carcasses across a virtual tripwire, and persisting all events in a local SQLite database before syncing batches to the central cloud API.

```
+-------------------------------------------------------------------------------+
|  EDGE HOST (Dokploy VPS / On-Premise Gateway / Industrial Mini PC)            |
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
|   |  3. Local Buffer: SQLite WAL (/data/counter_outbox.db)                |   |
|   |  4. Sync Dispatcher: OutboxSyncDispatcher (retries + exp backoff)     |   |
|   +-----------------------------------+-----------------------------------+   |
+---------------------------------------|---------------------------------------+
                                        | Outbound HTTPS POST
                                        | (/api/v1/sync/batch)
                                        v
                    +---------------------------------------+
                    |  Central Cloud Backend (Render / VPS) |
                    |  https://<cdc-api-subdomain>.onrender.com |
                    |  - Ingests batch & verifies line      |
                    |  - Dispatches WebSocket updates       |
                    |  - Stores in cdc-postgres             |
                    +-------------------+-------------------+
                                        |
                                        v
                    +---------------------------------------+
                    |  Web Dashboard (cdc-frontend)         |
                    |  Real-time counter & health charts    |
                    +---------------------------------------+
```

### Key Operational Characteristics

- **Zero Inbound Port Exposure**: The edge container runs headless and does not open any listening HTTP, TCP, or UDP ports. All network operations are outbound requests to `API_SYNC_URL`. Firewalls, NAT gateways, and edge routers require zero port-forwarding or reverse proxy ingress configuration.
- **Offline Outbox Resilience**: Network outages or cloud API spin-up cold starts (such as Render free-tier spin-up delays) do not block or halt carcass counting. Detections, rolling window aggregates, and health telemetry samples are written immediately to the local SQLite database (`/data/counter_outbox.db`) using Write-Ahead Logging (WAL). When connectivity is restored, the decoupled background sync dispatcher automatically drains accumulated batches in order.
- **Decoupled Architecture**: Video ingestion, neural/contour inference, and tracking occur on the main pipeline thread at full target FPS without blocking for network I/O. Outbound synchronization runs in a separate daemon thread (`SyncWorker-<line_id>`).
- **Headless Execution**: The container uses `opencv-python-headless`, eliminating any X11, Wayland, or desktop display server requirements while logging structured performance metrics (FPS, latency, rate/min) to container `stdout`.

---

## 2. Pre-requisites & Preparation

Before deploying the counter container, ensure the following requirements are met:

1. **Docker Engine**: Docker 20.10+ and Docker Compose v2 installed on the target machine (or an active Dokploy installation).
2. **Video Footage**: A video file representing the poultry shackle conveyor line (e.g. `Rekaman_2.MOV`, `Rekaman_1.MOV`, or an MP4 file) placed in a host directory (default: `./samples`).
3. **Central API Endpoint**: An accessible cloud API URL for batch synchronization (e.g. `https://<cdc-api-subdomain>.onrender.com/api/v1/sync/batch` or local `http://<lan-ip>:8000/api/v1/sync/batch`).
4. **Registered Line Identifier**: A valid conveyor line ID matching a record in the central API (the database is pre-seeded with `line-1` and `lineA`).

---

## 3. Configuration Reference

The counter configuration is controlled through environment variables defined in `.env.counter.example`:

| Variable | Type | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `API_SYNC_URL` | String (URL) | `https://cdc-api.onrender.com/api/v1/sync/batch` | Destination API batch sync endpoint for events and telemetry. |
| `LINE_ID` | String | `line-1` | Conveyor line identifier (must match an active line in central database). |
| `VIDEO_PATH` | String (Path) | `/samples/Rekaman_2.MOV` | Absolute path inside the container to the video file to process. |
| `SAMPLES_DIR` | String (Path) | `./samples` | Host directory containing the video files, mounted to `/samples:ro`. |
| `LOOP_VIDEO` | Integer / Bool | `1` | Video playback looping: `1` to loop endlessly, `0` to stop at EOF. |
| `LINE_DIRECTION` | String | `right` | Crossing direction trigger: `right`, `left`, `down`, or `up`. |
| `TARGET_FPS` | Float | `30.0` | Frame rate pacing: `30.0` for real-time simulation; `0.0` for unthrottled maximum throughput. |
| `DB_PATH` | String (Path) | `/data/counter_outbox.db` | Path inside container to the SQLite outbox database file. |
| `SYNC_INTERVAL_SEC` | Float | `5.0` | Interval in seconds between outbox sync dispatcher attempts. |
| `HEALTH_INTERVAL_SEC` | Float | `10.0` | Interval in seconds between system health telemetry records (FPS, latency, CPU/RAM). |
| `CONF_THRESHOLD` | Float | `0.7` | Detector confidence threshold (0.0 to 1.0). |
| `OCCUPANCY_THRESHOLD` | Float | `4.5` | Gradient threshold for `ShackleDetector` to reject empty hanging shackles. |
| `DETECTOR_TYPE` | String | `auto` | Detection engine: `auto`, `shackle`, `mock`, or `onnx`. |
| `LOG_LEVEL` | String | `WARNING` | Console logging verbosity: `DEBUG`, `INFO`, or `WARNING`. |

---

## 4. Option 1: Dokploy Compose Deployment (Recommended)

Dokploy's **Compose** service type is the recommended deployment method because it natively consumes the `docker-compose.counter.yml` specification and handles named volumes and environment configuration through a clean web UI.

### Step-by-Step Dokploy UI Workflow

#### Step 1: Create a New Compose Service
1. Log in to your Dokploy web console (`http://<your-server-ip>:3000`).
2. Select your **Project** (or click **Create Project** and name it e.g. `Poultry-Edge`).
3. Click **+ Create Service** and select **Compose**.
4. Name the service `cdc-counter`.

#### Step 2: Configure Compose Source
You can configure Compose via Git or Raw YAML:

- **Method A: Git Repository (Recommended)**
  - Under **Source Type**, select **Git**.
  - **Repository URL**: `https://github.com/<owner>/cdc-chicken-counting.git` (or your private Git repository).
  - **Branch**: `main` (or your deployment branch).
  - **Compose Path**: `docker-compose.counter.yml`.

- **Method B: Raw Docker Compose**
  - Under **Source Type**, select **Raw**.
  - Paste the contents of `docker-compose.counter.yml`:
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

#### Step 3: Configure Environment Variables
1. Navigate to the **Environment** tab in Dokploy.
2. Click **Add Environment Variable** (or paste bulk content from `.env.counter.example`):
   ```ini
   API_SYNC_URL=https://<cdc-api-subdomain>.onrender.com/api/v1/sync/batch
   LINE_ID=line-1
   VIDEO_PATH=/samples/Rekaman_2.MOV
   SAMPLES_DIR=/var/dokploy/samples
   LOOP_VIDEO=1
   LINE_DIRECTION=right
   TARGET_FPS=30.0
   SYNC_INTERVAL_SEC=5.0
   HEALTH_INTERVAL_SEC=10.0
   CONF_THRESHOLD=0.7
   OCCUPANCY_THRESHOLD=4.5
   ```
3. Click **Save**.

#### Step 4: Host Video Directory Setup
On the host running Dokploy, ensure the sample video is placed in the designated path:
```bash
# Example host setup
mkdir -p /var/dokploy/samples
cp /path/to/Rekaman_2.MOV /var/dokploy/samples/Rekaman_2.MOV
```

#### Step 5: Deploy the Service
1. Click **Deploy** in the top-right corner.
2. Navigate to the **Deployments** / **Logs** tab to view the Docker build output and runtime container startup.

---

## 5. Option 2: Dokploy Application Deployment

If you prefer using Dokploy's single **Application** service type instead of Compose:

### Step-by-Step Dokploy UI Workflow

#### Step 1: Create an Application Service
1. Inside your Dokploy Project, click **+ Create Service** and select **Application**.
2. Name the application `cdc-counter-app`.

#### Step 2: Configure Build Source & Dockerfile
1. Under **Provider**, select **Git** and connect your repository (`cdc-chicken-counting`).
2. Select your branch (`main`).
3. Set **Build Type** to **Dockerfile**.
4. Set **Context Path (Build Context)** to:
   ```
   ./services/counter
   ```
   *(or `.` if deploying directly from inside `services/counter/` or a separate counter repository)*
5. Set **Dockerfile Path** to:
   ```
   Dockerfile
   ```
   *(or `services/counter/Dockerfile` depending on whether your Dokploy version resolves the Dockerfile path relative to repository root or context path)*
   > **STANDALONE BUILD CONTEXT**: The build context is `./services/counter` (or `.` when inside `services/counter/`). The counter service is completely self-contained and does not require repository root files or `shared/` contracts.

#### Step 3: Configure Persistent Volumes
1. Navigate to the **Volumes** tab.
2. Add Volume 1 (**SQLite Outbox Storage**):
   - **Type**: Named Volume
   - **Name**: `counter-data`
   - **Mount Path**: `/data`
3. Add Volume 2 (**Sample Video Bind Mount**):
   - **Type**: Bind Mount (Host path)
   - **Host Path**: `/var/dokploy/samples` (or wherever your video file resides)
   - **Mount Path**: `/samples`
   - **Access Mode**: Read-Only (`ro`)

#### Step 4: Configure Environment Variables
In the **Environment** tab, set:
```ini
API_SYNC_URL=https://<cdc-api-subdomain>.onrender.com/api/v1/sync/batch
LINE_ID=line-1
VIDEO_PATH=/samples/Rekaman_2.MOV
LOOP_VIDEO=1
LINE_DIRECTION=right
TARGET_FPS=30.0
DB_PATH=/data/counter_outbox.db
SYNC_INTERVAL_SEC=5.0
HEALTH_INTERVAL_SEC=10.0
```

#### Step 5: Disable Inbound Routing
Under the **Domains** or **Ports** tab, ensure **no public domains or exposed ports are mapped**. The edge counter does not require ingress routing.

#### Step 6: Deploy
Click **Deploy** and monitor the live build logs.

---

## 6. Option 3: Standard Docker Compose CLI

For bare-metal edge gateways, on-premise industrial PCs, or standard Linux/Windows servers without Dokploy:

### Step 1: Directory Preparation
Clone or copy the repository to the edge machine:
```bash
git clone https://github.com/<owner>/cdc-chicken-counting.git
cd cdc-chicken-counting
```

Ensure the sample video exists in the `./samples` folder:
```bash
mkdir -p ./samples
# Copy your video into ./samples/
cp /path/to/Rekaman_2.MOV ./samples/Rekaman_2.MOV
```

### Step 2: Configure Environment Variables
Copy the configuration template:
```bash
cp .env.counter.example .env
```

Edit `.env` with your preferred editor:
```bash
nano .env
```
Update `API_SYNC_URL` to point to your cloud deployment:
```ini
API_SYNC_URL=https://<cdc-api-subdomain>.onrender.com/api/v1/sync/batch
LINE_ID=line-1
VIDEO_PATH=/samples/Rekaman_2.MOV
SAMPLES_DIR=./samples
LOOP_VIDEO=1
LINE_DIRECTION=right
TARGET_FPS=30.0
```

### Step 3: Launch the Service
Start the counter in detached daemon mode:
```bash
docker compose -f docker-compose.counter.yml up -d --build
```

### Step 4: Follow Live Logs
```bash
docker compose -f docker-compose.counter.yml logs -f counter
```

### Step 5: Lifecycle Management
- **Stop Service**:
  ```bash
  docker compose -f docker-compose.counter.yml down
  ```
- **Restart Service**:
  ```bash
  docker compose -f docker-compose.counter.yml restart counter
  ```
- **Stop and Purge Outbox Database Volume** (⚠️ Deletes buffered counts):
  ```bash
  docker compose -f docker-compose.counter.yml down -v
  ```

---

## 7. Option 4: Standalone Docker Run CLI

For quick deployments without Docker Compose:

### Step 1: Build the Container Image
From the root of the repository:
```bash
docker build -t cdc-counter:latest ./services/counter
```

Alternatively, from inside the `services/counter` directory:
```bash
cd services/counter
docker build -t cdc-counter:latest .
```

### Step 2: Create Named Data Volume
```bash
docker volume create counter_data
```

### Step 3: Run the Container

#### Linux / macOS (Bash)
```bash
docker run -d \
  --name cdc-counter \
  --restart unless-stopped \
  -v counter_data:/data \
  -v "$(pwd)/samples:/samples:ro" \
  -e API_SYNC_URL="https://<cdc-api-subdomain>.onrender.com/api/v1/sync/batch" \
  -e LINE_ID="line-1" \
  -e VIDEO_PATH="/samples/Rekaman_2.MOV" \
  -e LOOP_VIDEO="1" \
  -e LINE_DIRECTION="right" \
  -e TARGET_FPS="30.0" \
  -e DB_PATH="/data/counter_outbox.db" \
  -e SYNC_INTERVAL_SEC="5.0" \
  -e HEALTH_INTERVAL_SEC="10.0" \
  cdc-counter:latest
```

#### Windows (PowerShell)
```powershell
docker run -d `
  --name cdc-counter `
  --restart unless-stopped `
  -v counter_data:/data `
  -v "${PWD}/samples:/samples:ro" `
  -e API_SYNC_URL="https://<cdc-api-subdomain>.onrender.com/api/v1/sync/batch" `
  -e LINE_ID="line-1" `
  -e VIDEO_PATH="/samples/Rekaman_2.MOV" `
  -e LOOP_VIDEO="1" `
  -e LINE_DIRECTION="right" `
  -e TARGET_FPS="30.0" `
  -e DB_PATH="/data/counter_outbox.db" `
  -e SYNC_INTERVAL_SEC="5.0" `
  -e HEALTH_INTERVAL_SEC="10.0" `
  cdc-counter:latest
```

---

## 8. Multi-Line Deployment (Parallel Conveyors)

Industrial slaughterhouses and processing plants often run multiple conveyor lines simultaneously. You can run multiple counter instances on a single host.

### Isolation Rules
1. **Isolated Outbox Volumes**: Each container **must** have its own persistent volume for `/data` (e.g. `counter_data_line1` and `counter_data_lineA`). SQLite databases cannot safely be shared across containers.
2. **Shared Sample Directory**: Multiple containers can safely mount the same `./samples` directory as read-only (`:ro`).
3. **Distinct `LINE_ID`**: Each service must have a unique `LINE_ID` matching the central API configuration.

### Multi-Line Compose Example

Save as `docker-compose.multiline.yml`:

```yaml
version: "3.8"

services:
  # ============================================================================
  # Conveyor Line 1
  # ============================================================================
  counter-line1:
    build:
      context: ./services/counter
      dockerfile: Dockerfile
    container_name: cdc-counter-line1
    restart: unless-stopped
    environment:
      - LINE_ID=line-1
      - VIDEO_PATH=/samples/Rekaman_2.MOV
      - LOOP_VIDEO=1
      - LINE_DIRECTION=right
      - TARGET_FPS=30.0
      - API_SYNC_URL=https://<cdc-api-subdomain>.onrender.com/api/v1/sync/batch
      - DB_PATH=/data/counter_outbox.db
      - SYNC_INTERVAL_SEC=5.0
      - HEALTH_INTERVAL_SEC=10.0
    volumes:
      - counter_data_line1:/data
      - ./samples:/samples:ro

  # ============================================================================
  # Conveyor Line A
  # ============================================================================
  counter-lineA:
    build:
      context: ./services/counter
      dockerfile: Dockerfile
    container_name: cdc-counter-lineA
    restart: unless-stopped
    environment:
      - LINE_ID=lineA
      - VIDEO_PATH=/samples/Rekaman_1.MOV
      - LOOP_VIDEO=1
      - LINE_DIRECTION=right
      - TARGET_FPS=30.0
      - API_SYNC_URL=https://<cdc-api-subdomain>.onrender.com/api/v1/sync/batch
      - DB_PATH=/data/counter_outbox.db
      - SYNC_INTERVAL_SEC=5.0
      - HEALTH_INTERVAL_SEC=10.0
    volumes:
      - counter_data_lineA:/data
      - ./samples:/samples:ro

volumes:
  counter_data_line1:
  counter_data_lineA:
```

Start both lines simultaneously:
```bash
docker compose -f docker-compose.multiline.yml up -d
```

---

## 9. Verification, Log Inspection & Troubleshooting

### 9.1 Viewing Container Logs

Check live container logs using Docker CLI:
```bash
docker logs -f cdc-counter
```

#### Expected Stdout Outputs

1. **Startup Banner**:
   ```text
   ==========================================================================
             POULTRY COUNTING SYSTEM - EDGE COUNTER SERVICE
   ==========================================================================
     Line ID:         line-1
     Video Source:    file (/samples/Rekaman_2.MOV) [1920x1080]
     Detector:        ShackleDetector
     Virtual Line:    (960.0, 216.0) -> (960.0, 972.0) [right]
     API Sync:        ENABLED (https://<cdc-api-subdomain>.onrender.com/api/v1/sync/batch)
     Outbox Database: /data/counter_outbox.db
   ==========================================================================
   Processing video stream... Press Ctrl+C to stop.
   ```

2. **Live Crossing Events & Status Line**:
   ```text
    [COUNT +1] Frame #24    | Track #1   | Conf: 85.0% | Line Total: 1
    [COUNT +1] Frame #58    | Track #2   | Conf: 91.2% | Line Total: 2
   [Frame    95] Chickens:    3 | Rate: 135.0/min | Speed:  30.0 fps | Latency: 12.4ms
   ```

3. **Shutdown Summary** (when stopped via `SIGINT` / `docker stop`):
   ```text
   ==========================================================================
                          COUNTER RUN SUMMARY
   ==========================================================================
     Line ID:                    line-1
     Video Source:               /samples/Rekaman_2.MOV
     Total Frames Processed:     1800
     Total Chickens Counted:     124
     Total Duration:             60.02 seconds
     Average Processing Speed:   30.0 FPS
     Avg / p95 Inference Latency:11.82 ms / 16.40 ms
     Estimated Conveyor Rate:    123.9 chickens/min
     Conveyor Line Status:       NORMAL (>= 130/min)
     Local Database:             /data/counter_outbox.db
   ==========================================================================
   ```

---

### 9.2 Verifying Cloud API Sync

1. **Check Central API Logs**:
   In Render or your cloud VPS logs for `cdc-api`, look for incoming batch sync requests:
   ```text
   INFO:     198.51.100.24:52134 - "POST /api/v1/sync/batch HTTP/1.1" 200 OK
   ```

2. **Verify via Central REST API**:
   Obtain an auth token and query the line summary:
   ```bash
   TOKEN=$(curl -s -X POST https://<cdc-api-subdomain>.onrender.com/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username": "admin", "password": "<your-password>"}' | jq -r .access_token)

   curl -s -H "Authorization: Bearer $TOKEN" \
     https://<cdc-api-subdomain>.onrender.com/api/v1/lines/line-1/summary | jq .
   ```
   Expected response indicates active telemetry and counts:
   ```json
   {
     "line_id": "line-1",
     "period": "today",
     "total_count": 124,
     "current_speed_cpm": 123.9,
     "camera_status": "ONLINE",
     "fps": 30.0
   }
   ```

3. **Verify via Web Frontend**:
   Open `https://<cdc-frontend-subdomain>.onrender.com` in your browser.
   - Navigate to the **Lini Produksi (Conveyor Line)** view.
   - Select **Line 1**.
   - Verify that the live counter increments smoothly, the line indicator shows a green **ONLINE** badge, and the real-time FPS chart displays ~30.0 FPS.

---

### 9.3 Offline Resilience & Outbox Verification

To test that the local SQLite buffer functions properly during network outages:

1. **Simulate a Network Outage**:
   Disconnect the counter container from the Docker bridge network:
   ```bash
   docker network disconnect bridge cdc-counter
   ```

2. **Observe Container Logs**:
   The counting pipeline continues running at 30 FPS without dropping frames. The sync worker logs warnings and engages exponential backoff:
   ```text
   [WARNING] Error in background sync worker: [Errno -3] Temporary failure in name resolution
   ```

3. **Inspect Local SQLite Outbox**:
   Execute a query inside the running container to verify unsynced records:
   ```bash
   docker exec -it cdc-counter python -c "
   import sqlite3
   conn = sqlite3.connect('/data/counter_outbox.db')
   c = conn.cursor()
   for tbl in ['outbox_events', 'outbox_aggregates', 'health_samples']:
       c.execute(f'SELECT count(*) FROM {tbl} WHERE synced_at IS NULL')
       print(f'{tbl} unsynced:', c.fetchone()[0])
   "
   ```
   Output confirms records are safely buffered:
   ```text
   outbox_events unsynced: 42
   outbox_aggregates unsynced: 2
   health_samples unsynced: 12
   ```

4. **Restore Network Connectivity**:
   Reconnect the container to the bridge network:
   ```bash
   docker network connect bridge cdc-counter
   ```

5. **Observe Automatic Drain / Flush**:
   Within one sync interval (`SYNC_INTERVAL_SEC=5.0`), the background sync worker drains all buffered items to the central API. Re-running the SQLite query shows `unsynced: 0`.

---

### 9.4 Common Troubleshooting Scenarios

| Issue | Root Cause | Solution |
| :--- | :--- | :--- |
| **Exits immediately with "Reached end of video stream" (Total Frames: 0)** | The video path specified by `VIDEO_PATH` does not exist inside the container. | Check that `SAMPLES_DIR` on the host contains the file and is mounted to `/samples:ro`. Ensure case sensitivity matches (`Rekaman_2.MOV` vs `rekaman_2.mov`). |
| **`HTTP 404 / 422: Line not found`** | `LINE_ID` does not exist in central API database. | The default database seeds `line-1` and `lineA`. If using a custom line ID, create the line first in the central web dashboard or via `POST /api/v1/lines`. |
| **OpenCV video decoding error** | Incompatible video container or proprietary video codec. | The container runs `opencv-python-headless` with standard FFmpeg decoders. Transcode the video to H.264 MP4: `ffmpeg -i input.mov -c:v libx264 -pix_fmt yuv420p samples/Rekaman_2.MOV`. |
| **Render Cloud 502 / Spin-up Delay** | Free-tier Render instances spin down after inactivity (~50s cold start). | The edge counter's SQLite outbox and exponential backoff retry handle this automatically. No action needed; records flush as soon as the Render service wakes up. |
| **`sqlite3.OperationalError: database is locked`** | Multiple container instances mounting the same host directory or SQLite file. | Ensure each container has its own isolated named volume for `/data` (e.g. `counter_data_line1`, `counter_data_line2`). |
| **High CPU utilization on Edge Gateway** | Processing at unthrottled frame rates. | Set `TARGET_FPS=30.0` (or `25.0`) to pace frame consumption to real-time conveyor speed instead of consuming 100% CPU. |
