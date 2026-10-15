# Design Specification: Poultry Counting Service & Dashboard (Lihat.id)

- **Date**: 2026-10-15
- **Status**: Approved (Brainstorming Phase Complete)
- **Derived from**: `docs/prd.md` (Lihat.id Poultry Counter PRD v0.1)
- **Primary Architecture**: Decoupled Microservices with REST Push + Local Outbox Sync

---

## 1. Overview & Scope

The system automates broiler counting on high-speed shackle conveyors in poultry processing plants. It eliminates manual counting errors and delay by delivering real-time throughput metrics, visual verification, automated threshold alerting, and audit-ready historical reporting.

The project is structured as a decoupled multi-service monorepo:
1. **Counting Service (`services/counter`)**: Autonomous Python edge service ingesting camera video, running hardware-agnostic YOLO detection and ByteTrack tracking, counting birds crossing a virtual line zone, logging into a local SQLite outbox, and streaming a local MJPEG feed for calibration.
2. **Data API Service (`services/api`)**: FastAPI backend ingesting sync batches from the edge counter, evaluating operational thresholds, dispatching real-time SSE updates, managing users/RBAC, and serving report exports.
3. **Frontend Dashboard (`frontend`)**: React 18 + TypeScript PWA delivering 5 responsive screens optimized for both mobile operators on the plant floor and plant managers on desktop.

---

## 2. System Architecture & Repository Layout

### 2.1 Topology

```
[ Camera / RTSP / MP4 / Synthetic ]
                │
                ▼
┌────────────────────────────────────────────────────────┐
│ services/counter/ (Autonomous Edge Python Service)     │
│  - Video Ingest (RTSP / MP4 File / Synthetic)          │
│  - Detector Interface (YOLO26 / YOLO11 / Mock)        │
│  - ByteTrack Tracker + Virtual LineZone Counter       │
│  - Local SQLite Store (Events, Aggregates, Health)    │
│  - REST Outbox Syncer (Background Push with Backoff)   │
│  - Local MJPEG Calibration Streamer                   │
└────────────────────────┬───────────────────────────────┘
                         │ HTTP POST /api/v1/sync/batch
                         ▼
┌────────────────────────────────────────────────────────┐
│ services/api/ (FastAPI Data Service)                   │
│  - Sync Ingest Endpoints (Batch Deduplication)        │
│  - Central Database (SQLite WAL / PostgreSQL-ready)    │
│  - Threshold & Alarm Evaluator Engine                  │
│  - Server-Sent Events (SSE) Live Feed Broadcaster      │
│  - REST Data API (/api/v1/lines, summary, reports)     │
│  - Report Exporter (openpyxl Excel, WeasyPrint PDF)    │
│  - Auth (JWT + Argon2) & RBAC Enforcement              │
└────────────────────────┬───────────────────────────────┘
                         │ REST + SSE
                         ▼
┌────────────────────────────────────────────────────────┐
│ frontend/ (React 18 + Vite + TypeScript PWA)           │
│  - Overview Dashboard (KPIs, Trends, Attainment Gauge) │
│  - Live Line Monitoring & Calibration Preview          │
│  - Alarm Management & Acknowledgment                   │
│  - Historical Reports & File Downloads                 │
│  - Settings & Line Threshold Configuration             │
└────────────────────────────────────────────────────────┘
```

### 2.2 Directory Layout

```
cdc-chicken-counting/
├── docs/
│   ├── prd.md
│   └── superpowers/specs/
│       └── 2026-10-15-chicken-counting-system-design.md
├── services/
│   ├── counter/                    # Autonomous Edge AI Service
│   │   ├── src/
│   │   │   ├── capture/            # VideoSource: RTSP, File, Synthetic
│   │   │   ├── detection/          # Detector interface, ONNX/YOLO26/11, Mock
│   │   │   ├── tracking/           # ByteTrack & Virtual Line Crossing
│   │   │   ├── storage/            # Local SQLite outbox & schema
│   │   │   ├── sync/               # Background REST outbox dispatcher
│   │   │   ├── streamer/           # Lightweight MJPEG server
│   │   │   ├── monitoring/         # Image quality & system health
│   │   │   └── config.py           # Pydantic settings & line configs
│   │   ├── tests/
│   │   ├── benchmark.py            # FPS & p95 latency benchmark tool
│   │   └── pyproject.toml
│   │
│   ├── api/                        # Central Data API Service
│   │   ├── src/
│   │   │   ├── api/                # FastAPI routers (auth, lines, alarms, sync, reports)
│   │   │   ├── core/               # Security, JWT, config
│   │   │   ├── db/                 # SQLAlchemy models, SQLite WAL engine
│   │   │   ├── services/           # Alarm evaluator, SSE broadcaster, exporters
│   │   │   └── main.py
│   │   ├── tests/
│   │   └── pyproject.toml
│   │
│   └── shared/                     # Shared DTO schemas & contracts
│
├── frontend/                       # Web & Mobile Dashboard
│   ├── src/
│   │   ├── components/             # Reusable UI (KPI cards, charts, stream player)
│   │   ├── pages/                  # Overview, Live, Alarms, Reports, Settings
│   │   ├── services/               # API client, SSE subscriber, Auth context
│   │   ├── locales/                # Indonesian (id) & English (en)
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
│
└── docker-compose.yml              # Local multi-service orchestration
```

---

## 3. Counting Service Deep-Dive (`services/counter`)

### 3.1 Video Ingest & Source Abstraction
The service ingests frames at ≥ 30 fps via an extensible `VideoSource` interface:
- **`RTSPVideoSource`**: PyAV / OpenCV RTSP client. Auto-reconnects on stream drops with exponential backoff (1s base, doubling to 30s cap). Maintains frame buffer to prevent lag.
- **`FileVideoSource`**: Reads `.mp4` / `.avi` test footage in a real-time paced loop (30 fps) for offline testing, ground-truth verification, and continuous development without physical cameras.
- **`SyntheticVideoSource`**: Procedurally generates moving target shapes across a canvas to enable deterministic, fast-running unit and integration tests in CI.
- **Image Quality Guard**: Measures average frame brightness and Laplacian variance (blur detection) every 10 seconds. Raises warning telemetry if the lens is covered or steam/condensation reduces contrast.

### 3.2 Detector Interface & Acceleration
- **Contract**:
  ```python
  class Detector(ABC):
      @abstractmethod
      def predict(self, frame: np.ndarray) -> list[Detection]: ...
  ```
- **Implementations**:
  - `ONNXDetector`: Loads YOLO26 nano (primary, end-to-end NMS-free) or YOLO11 (fallback). Configurable execution providers:
    - Apple Silicon: `CoreMLExecutionProvider`
    - NVIDIA Jetson/GPU: `TensorrtExecutionProvider` / `CUDAExecutionProvider`
    - Intel/AMD Mini-PC: `OpenVINOExecutionProvider` / `CPUExecutionProvider`
  - `MockDetector`: Emits synthetic chicken detections with realistic bounding boxes and confidences for testing the complete downstream pipeline without heavyweight model files.

### 3.3 Tracking & Counting Logic
- **ByteTrack Association**: Correlates bounding boxes across frames using Kalman filtering and IoU association. Maintains a lost-track buffer of 30 frames to handle brief wing flapping or hook swinging.
- **Virtual Line Crossing (LineZone)**:
  - Configurable line segment defined by `[(x1, y1), (x2, y2)]` and valid vector direction.
  - Anchor point is the bottom-center of the chicken bounding box `(x_mid, y_max)`.
  - Crossing detection: Triggers when the vector between consecutive track positions intersects the counting line in the allowed direction.
  - **Double-Count Prevention**: Track IDs that cross the line are immediately registered in an in-memory LRU cache (`max_size=10,000`). Reverse movement or swinging back across the line is explicitly ignored.
  - Emits `CountEvent(line_id, track_id, timestamp_utc, confidence)`.

### 3.4 Local Persistence & Outbox Synchronization
- **Local SQLite Store (`events.db` in WAL mode)**:
  - `outbox_events`: Stores raw events with `synced_at TIMESTAMP NULL`.
  - `outbox_aggregates`: Rolls up events into 1-minute windows (count, rate/min, avg confidence).
  - `health_samples`: Records FPS, p95 inference latency, CPU%, Memory%, and stream status.
- **Background Sync Worker**:
  - Runs in an asynchronous loop every 2 seconds.
  - Fetches unsynced records (`synced_at IS NULL`) in batches of up to 500 rows.
  - Posts payload to `POST /api/v1/sync/batch` on the Data API.
  - Sets `synced_at = CURRENT_TIMESTAMP` upon HTTP 200 response.
  - On network drop or API unavailability, enters backoff mode; zero data is lost, guaranteeing 100% offline edge autonomy (retention: 90 days local storage).

### 3.5 Calibration & Streamer
- Exposes a lightweight local HTTP MJPEG server at `/stream`.
- Draws bounding boxes, track IDs, the virtual counting line, and the running tally onto frames for on-site technician alignment.

---

## 4. Data API Deep-Dive (`services/api`)

### 4.1 Ingest Contract & Idempotency
- **Endpoint**: `POST /api/v1/sync/batch`
- **Payload Schema**:
  ```json
  {
    "line_id": "lineA",
    "events": [
      { "track_id": 1042, "ts_utc": "2026-10-15T08:30:01.120Z", "confidence": 0.96 }
    ],
    "aggregates": [
      {
        "window_start": "2026-10-15T08:30:00Z",
        "window_end": "2026-10-15T08:31:00Z",
        "count": 125,
        "rate_per_min": 125.0,
        "confidence_avg": 0.955
      }
    ],
    "health": {
      "fps": 29.8,
      "latency_p95_ms": 38.5,
      "cpu_pct": 24.2,
      "mem_pct": 31.0,
      "stream_state": "ONLINE"
    }
  }
  ```
- **Deduplication**: Ingest runs an `INSERT OR IGNORE` on unique constraint `(line_id, track_id, ts_utc)` so retries from the outbox syncer never produce duplicate records.

### 4.2 Central Database Schema (SQLAlchemy)
- **`lines`**: `id`, `name`, `daily_target` (default 62000), `shift_config_json`, `timezone` (`Asia/Jakarta`), `is_active`.
- **`count_events`**: `id`, `line_id`, `track_id`, `ts_utc`, `confidence`.
- **`count_aggregates`**: `id`, `line_id`, `window_start`, `window_end`, `count`, `rate_per_min`, `confidence_avg`, `status` (`NORMAL`, `WARNING`, `CRITICAL`).
- **`health_samples`**: `id`, `line_id`, `ts_utc`, `fps`, `latency_avg_ms`, `latency_p95_ms`, `cpu_pct`, `mem_pct`, `disk_pct`, `stream_state`.
- **`alarms`**: `id`, `line_id`, `type`, `severity`, `value`, `message`, `opened_at`, `ack_by`, `ack_at`, `resolved_at`, `note`.
- **`users`**: `id`, `username`, `email`, `password_hash`, `role` (`ADMIN`, `MANAGER`, `OPERATOR`, `VIEWER`), `is_active`.
- **`audit_logs`**: `id`, `user_id`, `action`, `entity`, `before_val`, `after_val`, `ts_utc`.

### 4.3 Alarm & Threshold Engine
Evaluates every incoming aggregate and health sample against configurable rules:
- **Stream Offline**: Warning > 30s, Critical > 2 min.
- **Low Production Rate**: Warning < 130 birds/min, Critical < 110 birds/min.
- **High Latency**: Warning > 50 ms, Critical > 100 ms.
- **Low Confidence**: Warning < 90%, Critical < 80%.
When violated, an alarm record is created or updated in `OPEN` state, and an alarm alert is broadcast via SSE.

### 4.4 Real-Time SSE Broadcaster
- Endpoint: `GET /api/v1/lines/{id}/events/live`
- Delivers Server-Sent Events to connected browsers:
  - `event: count` -> `{ "total_today": 48250, "rate_per_min": 120, "attainment_pct": 77.8 }`
  - `event: health` -> `{ "fps": 30.0, "latency_ms": 38.2, "status": "ONLINE" }`
  - `event: alarm` -> `{ "type": "LOW_RATE", "severity": "WARNING", "msg": "Rate dropped to 118" }`

### 4.5 Reporting & Export
- Endpoint: `GET /api/v1/reports/export?format=xlsx|pdf&line_id=&from=&to=`
- **Excel (.xlsx)**: Generated using `openpyxl` with styled headers, totals, and per-minute or hourly sheets.
- **PDF (.pdf)**: Generated using `WeasyPrint` with branded layout, KPI summary, and tabulated shift logs.

---

## 5. Frontend Dashboard Deep-Dive (`frontend`)

### 5.1 Technology & UX Foundations
- **Stack**: React 18, Vite, TypeScript, Tailwind CSS, TanStack Query, Apache ECharts.
- **Mobile First / Plant-Floor Friendly**: High-contrast typography, large touch targets (≥ 44px), readable under bright plant lighting.
- **Localization**: Default Indonesian (`id`) with English (`en`) switch via `i18next`.
- **Timezone**: Explicit WIB (UTC+7) formatting for all timestamps.

### 5.2 Screen Details
1. **Screen 1 – Ringkasan Hari Ini (Overview)**:
   - 4 KPI cards: Total Count, Average Rate (birds/min), Camera Status (Online/Offline + FPS), Detection Confidence.
   - Daily Target Attainment Gauge (radial progress % and absolute numbers).
   - Hourly count trend chart (ECharts smoothed area chart).
   - Mini live preview window.
2. **Screen 2 – Pemantauan Langsung (Live Monitoring)**:
   - Live stream display with bounding box overlays and line crossing indicators.
   - Live telemetry sidebar: FPS gauge, p95 latency, edge CPU/RAM usage.
   - Active alarm ticker.
   - Multi-line switcher (Line A / Line B).
3. **Screen 3 – Daftar Alarm (Alarms)**:
   - Tabular alarm log with severity badges (amber Warning, red Critical) and status filters (Open, Acknowledged, Resolved).
   - Action modal: Operators can acknowledge alarms; Managers can resolve with notes.
4. **Screen 4 – Laporan & Riwayat (Reports)**:
   - Filter by Shift (Shift 1, 2, 3), Daily, or custom dates.
   - Aggregated log table with pagination.
   - Download buttons for Excel (.xlsx) and PDF formats.
5. **Screen 5 – Pengaturan (Settings)**:
   - RBAC User Management (Admin, Manager, Operator, Viewer).
   - Line configuration: names, target quota, shift schedule.
   - Threshold matrix editor (Warning/Critical values).
   - Virtual line calibration interface with live frame snapshot.

---

## 6. Non-Functional & Reliability Guarantees

| Metric | Target | Verification Method |
|---|---|---|
| Count Accuracy | ≥ 99.0% vs ground truth | Ground-truth video benchmark replay harness (CS-19) |
| Double-Count Rate | < 0.5% | Replay harness with deliberate shackle swinging |
| Inference Latency | p95 < 50 ms @ 30 fps | Real-time health sampler & benchmark script |
| Network Outage Resilience | 0 lost counts for 7+ days | Local SQLite outbox queue with exponential backoff sync |
| Dashboard First Load | < 3 s on plant Wi-Fi | Vite bundle optimization & lightweight PWA caching |
| Dashboard Lag | ≤ 5 s from camera event | Real-time SSE push channel |

---

## 7. Spec Self-Review Checklist

- [x] **Placeholder Scan**: No `TODO`, `TBD`, or unresolved placeholders.
- [x] **Internal Consistency**: Decoupled microservices architecture matches REST Push + Local Outbox pattern across all sections.
- [x] **Scope Bounded**: Explicitly covers Counting Service, Data API, and Frontend Dashboard; excludes external ERP and cloud fleet platforms per PRD Section 1.2.
- [x] **Ambiguity Check**: Resolved mockup conflicts by establishing configurable threshold rules, explicit WIB timezone, and standardized idempotency keys.
