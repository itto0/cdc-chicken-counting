# Edge Poultry Counter Service

A standalone, lightweight edge computer vision service designed for industrial poultry processing lines. It processes high-speed conveyor video feeds, detects and tracks shackles/chickens across virtual counting lines, records real-time counting and health metrics into an offline-first SQLite outbox, and syncs batches to the central API in the background.

---

## Key Features

- **Decoupled Architecture**: Fully self-contained service that can be built and deployed without the monorepo root or central API code.
- **Offline-First Store & Forward**: Uses a local SQLite database (`counter_outbox.db`) to queue count aggregates and health telemetry. If network connectivity drops, edge processing continues uninterrupted and backlogs flush automatically upon reconnection.
- **Zero Inbound Attack Surface**: Operates purely as an outbound HTTP client — exposes no listening network ports, making it secure for deployment in factory OT networks.
- **Flexible Detection Engines**:
  - `auto`: Automatic detector selection.
  - `shackle`: Industrial poultry conveyor detector with carcass occupancy gradient analysis to reject empty shackles.
  - `onnx`: Hardware-accelerated YOLO inference via ONNX Runtime.
  - `mock`: Light intensity contour segmentation for benchmarking and CPU-only testing.
- **Remote Configuration**: Automatically fetches line calibration parameters (virtual line coordinates, direction, RTSP stream) from the central API on startup using Bearer API Key authentication (`API_TOKEN`), with offline fallback to local defaults.
- **Real-Time Visual Preview & Headless Modes**: Optional OpenCV display window for on-site line tuning, or headless execution for production Docker containers.

---

## Directory Structure

```text
services/counter/
├── Dockerfile             # Standalone Docker build definition
├── README.md              # Documentation (this file)
├── requirements.txt       # Edge Python runtime dependencies
├── main.py                # Service entry point and CLI runner
├── benchmark.py           # Performance and latency benchmark suite
├── src/
│   ├── capture/           # Video capture (synthetic, file, RTSP)
│   ├── detection/         # Shackle, ONNX, and mock detectors
│   ├── tracking/          # Centroid tracker & virtual line zone
│   ├── storage/           # Local SQLite outbox database manager
│   ├── sync/              # Background HTTP batch dispatcher
│   ├── contracts.py       # Data transfer schemas (Pydantic models)
│   └── env.py             # Environment configuration loader
└── tests/                 # Unit and integration test suite
```

---

## Requirements

- Python 3.11+
- System libraries for OpenCV (when running on host Linux: `libgl1`, `libglib2.0-0`)

---

## Local Installation

```bash
cd services/counter
pip install -r requirements.txt
```

Dependencies defined in `requirements.txt`:
```text
opencv-python-headless>=4.8.0
numpy>=1.24.0
pydantic>=2.5.0
httpx>=0.27.0
python-dotenv>=1.0.0
```

---

## CLI Usage

The service entrypoint is `main.py`. You can configure execution using command-line arguments or environment variables.

### Quick Start Examples

1. **Synthetic Video Test (Zero configuration):**
   ```bash
   python main.py --source synthetic --show-window
   ```

2. **Run on Video File with Central API Sync & Authentication:**
   ```bash
   python main.py \
     --video /path/to/conveyor_sample.mp4 \
     --line-id line-1 \
     --direction right \
     --api-sync-url http://localhost:8000/api/v1/sync/batch \
     --api-token cdc_live_xxxxxxxxxxxxxxxxxxxxxxxx \
     --loop
   ```

3. **Standalone Mode (No network sync, local storage only):**
   ```bash
   python main.py \
     --video /path/to/conveyor_sample.mp4 \
     --line-id line-1 \
     --no-sync \
     --show-window
   ```

### Command Line Options

| Option | Flag | Default | Description |
|---|---|---|---|
| `--video` | `-v` | `""` | Path to video file (`.mp4`, `.mov`, `.avi`, `.mkv`). Sets source type to `file`. |
| `--source` | | `synthetic` | Video source type: `synthetic`, `file`, or `rtsp`. |
| `--line-id` | | `lineA` | Conveyor line identifier (e.g. `line-1`, `lineA`). |
| `--model` | `-m` | `""` | Path to ONNX YOLO model file (optional). |
| `--detector` | | `auto` | Detector engine: `auto`, `shackle`, `mock`, or `onnx`. |
| `--conf` | | `0.7` | Detection confidence threshold (0.0 to 1.0). |
| `--occupancy-threshold` | | `4.5` | Carcass occupancy gradient threshold for `ShackleDetector` empty shackle rejection. |
| `--no-occupancy-check` | | `False` | Disable carcass occupancy verification (counts all shackles). |
| `--line` | | `""` | Virtual crossing line as `x1,y1,x2,y2` (e.g. `0,240,640,240`). |
| `--direction` | | `down` | Line crossing direction: `down`, `up`, `left`, `right`, `in`, `out`. |
| `--no-sync` | | `False` | Disable HTTP sync to central API (runs completely offline). |
| `--api-sync-url` | | `http://localhost:8000/api/v1/sync/batch` | Central API endpoint for batch outbox sync. |
| `--api-token` | `--api-key` | `""` | Bearer API key/token for authenticating with central cloud API. Eliminates HTTP 401 warnings and enables remote line calibration sync. |
| `--db-path` | | `counter_outbox.db` | Local SQLite database file path. |
| `--loop` | | `False` | Loop video continuously instead of exiting at EOF. |
| `--max-frames` | | `None` | Stop processing after reaching frame count limit. |
| `--target-fps` | | `0.0` | Target playback FPS pacing (e.g. `30.0`). Set `0.0` for maximum speed. |
| `--show-window` | `--gui` | `False` | Display OpenCV GUI window with tracking overlays and line counters. |
| `--sync-interval` | | `5.0` | Seconds between background batch sync attempts. |
| `--aggregate-window` | | `60.0` | Rolling aggregate time window in seconds. |
| `--health-interval` | | `10.0` | Telemetry health recording interval in seconds. |
| `--verbose` | | `False` | Enable verbose DEBUG logging. |

---

## Environment Variables

All command-line arguments can also be set via environment variables or a `.env` file:

| Variable | Default | Description |
|---|---|---|
| `LINE_ID` | `line-1` | Line identifier matching registered lines in central API |
| `VIDEO_PATH` | `/samples/Rekaman_2.MOV` | Video file path inside container or host |
| `VIDEO_SOURCE_TYPE` | `synthetic` | `synthetic`, `file`, or `rtsp` |
| `SAMPLES_DIR` | `./samples` | Host directory containing video files for volume mount |
| `LOOP_VIDEO` | `1` | `1` to loop video endlessly, `0` to stop at EOF |
| `LINE_DIRECTION` | `right` | Crossing trigger direction (`right`, `left`, `down`, `up`) |
| `LINE_COORDS` | `""` | Manual line coordinates `x1,y1,x2,y2` |
| `TARGET_FPS` | `30.0` | Frame rate throttle (`0.0` for unthrottled maximum speed) |
| `API_SYNC_URL` | `http://localhost:8000/api/v1/sync/batch` | Destination URL for outbox batch sync |
| `API_TOKEN` | `""` | Bearer API key/token for central cloud API authentication (alias: `API_KEY`). Resolves HTTP 401 warnings and enables remote line sync |
| `DB_PATH` | `/data/counter_outbox.db` | Path to persistent SQLite outbox file |
| `SYNC_INTERVAL_SEC` | `5.0` | Interval between background sync pushes |
| `HEALTH_INTERVAL_SEC` | `10.0` | Interval between system health telemetry samples |
| `CONF_THRESHOLD` | `0.7` | Shackle/chicken detection confidence threshold |
| `OCCUPANCY_THRESHOLD` | `4.5` | Carcass occupancy threshold for empty shackle rejection |
| `NO_SYNC` | `0` | Set `1` to disable central sync completely |
| `SHOW_WINDOW` | `0` | Set `1` to show visual preview window |
| `VERBOSE` | `0` | Set `1` to enable debug log output |

---

## Authentication & API Keys

The edge counter interacts with the central API for two distinct operations:
1. **Startup Remote Line Sync (`GET /api/v1/lines/{line_id}`)**: Pulls authoritative line settings (video RTSP stream URL, line crossing coordinates, line direction) configured in the central cloud dashboard.
2. **Background Batch Sync (`POST /api/v1/sync/batch`)**: Transmits buffered counting events, aggregates, and system health telemetry.

### Resolving HTTP 401 Unauthorized Warning
The line details endpoint requires authenticated access. If `API_TOKEN` (or `API_KEY`) is missing or invalid, the service logs:
```text
[WARNING] counter.service: Remote line config returned HTTP 401 for line line-1. Check that API_TOKEN or API_KEY is set in your environment. Falling back to local configuration.
```
When this occurs, the counter falls back to local command-line or `.env` defaults, and will not adopt settings managed from the cloud dashboard. Setting `API_TOKEN` eliminates this warning and allows the edge counter to automatically adopt line settings (RTSP stream, coordinates, direction) from the central cloud dashboard.

### How to Generate an API Key

#### Option 1: Via Central API CLI
From the backend server:
```bash
python -m services.api.src.cli create-api-key --name "Line 1 Edge"
```
Or specify an explicit role (`OPERATOR` or `ADMIN`, defaults to `OPERATOR`):
```bash
python -m services.api.src.cli create-api-key --name "Line 1 Edge" --role OPERATOR
```
Output:
```text
API Key created successfully for 'Line 1 Edge' [OPERATOR]:
  cdc_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Store this key securely in the edge device's .env file as API_TOKEN.
```

#### Option 2: Via REST API (`POST /api/v1/auth/api-keys`)
Admin users can generate keys programmatically:
```bash
curl -X POST https://<cdc-api-subdomain>.onrender.com/api/v1/auth/api-keys \
  -H "Authorization: Bearer <ADMIN_JWT_OR_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Line 1 Edge", "role": "OPERATOR"}'
```
Response:
```json
{
  "id": 1,
  "name": "Line 1 Edge",
  "api_key": "cdc_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "prefix": "cdc_live_xxxx",
  "role": "OPERATOR",
  "created_at": "2026-10-19T10:00:00Z"
}
```

Assign the returned `api_key` to `API_TOKEN` in `.env.counter` or your container's environment variables.

---

## Standalone Docker Build

The counter service is completely self-contained. You can build it directly with Docker using only the `services/counter` directory as the build context.

### 1. Build Docker Image

From inside `services/counter`:
```bash
cd services/counter
docker build -t cdc-counter .
```

Or from repository root:
```bash
docker build -t cdc-counter ./services/counter
```

### 2. Run Container Standalone

```bash
docker run --rm \
  -v $(pwd)/data:/data \
  -v /path/to/samples:/samples:ro \
  -e LINE_ID=line-1 \
  -e VIDEO_PATH=/samples/Rekaman_2.MOV \
  -e LOOP_VIDEO=1 \
  -e LINE_DIRECTION=right \
  -e API_SYNC_URL=http://your-central-api:8000/api/v1/sync/batch \
  -e API_TOKEN=cdc_live_xxxxxxxxxxxxxxxxxxxxxxxx \
  cdc-counter
```

---

## Docker Compose Execution

For edge server deployments, a dedicated Docker Compose configuration `docker-compose.counter.yml` is provided at the repository root.

### 1. Setup Environment File

Copy the template configuration:
```bash
cp .env.counter.example .env.counter
```

Edit `.env.counter` with your central API endpoint, authentication key, and conveyor parameters:
```dotenv
API_SYNC_URL=https://cdc-api.onrender.com/api/v1/sync/batch
API_TOKEN=cdc_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
LINE_ID=line-1
VIDEO_PATH=/samples/Rekaman_2.MOV
SAMPLES_DIR=./samples
LOOP_VIDEO=1
LINE_DIRECTION=right
TARGET_FPS=30.0
SYNC_INTERVAL_SEC=5.0
HEALTH_INTERVAL_SEC=10.0
CONF_THRESHOLD=0.7
OCCUPANCY_THRESHOLD=4.5
```

### 2. Start Service

```bash
docker compose -f docker-compose.counter.yml --env-file .env.counter up -d --build
```

### 3. Check Logs & Status

```bash
docker compose -f docker-compose.counter.yml logs -f counter
```

### 4. Stop Service

```bash
docker compose -f docker-compose.counter.yml down
```

---

## Testing

Run unit and integration tests for the counter service:

```bash
# Run compose verification test
py -m pytest services/counter/tests/test_compose_counter.py -v

# Run all counter service tests
py -m pytest services/counter/tests/ -v
```
