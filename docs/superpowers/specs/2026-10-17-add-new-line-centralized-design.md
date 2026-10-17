# Design Specification: Centralized Production Line Management with PostgreSQL

**Date:** 2026-10-17  
**Status:** Approved  
**Topic:** Add New Production Line via Frontend with Centralized Cloud/VM API, PostgreSQL Storage, and Edge Configuration Pull

---

## 1. Overview & Objectives

Currently, production lines are pre-seeded in the database on API startup, and virtual counting lines are statically configured via command-line arguments or environment variables on edge workers. The user requires the ability to create and configure new production lines directly from the frontend dashboard, with centralized storage in PostgreSQL on the cloud/VM, and automatic configuration pickup by edge counting services.

### Objectives
1. **Frontend Line Creation:** Provide an intuitive UI in the Settings (*Pengaturan*) page to create, view, edit, and deactivate production lines.
2. **Central Cloud Storage (PostgreSQL):** Persist line metadata (Line ID, Name, Daily Target, Video Stream URL, Virtual Line Coordinates, Crossing Direction) in PostgreSQL (`lines` table) while preserving SQLite for local development.
3. **Edge Startup Sync:** Allow edge counter instances to pull configuration on startup using their assigned `LINE_ID`, seamlessly falling back to local environment variables if offline.
4. **Live Stream Integration:** Wire the configured video stream URL to the live preview endpoint for real-time monitoring.

---

## 2. Architecture & Data Storage

```
  +-------------------------------------+      +-------------------------------------+
  |       Edge Counter 1 (Factory)      |      |       Edge Counter 2 (Factory)      |
  |  - Local SQLite WAL (Outbox)        |      |  - Local SQLite WAL (Outbox)        |
  |  - Pulls config on boot via LINE_ID |      |  - Pulls config on boot via LINE_ID |
  |  - Fallback to local .env/CLI args  |      |  - Fallback to local .env/CLI args  |
  +------------------+------------------+      +------------------+------------------+
                     |                                            |
                     | (Push counts & health / Pull config)       |
                     v                                            v
+------------------------------------------------------------------------------------+
| Central VM / Cloud Deployment                                                      |
|                                                                                    |
|  +-------------------------+             +--------------------------------------+  |
|  |   Central API (FastAPI) | <---------> |   PostgreSQL Database                |  |
|  |   Port: 8070 / 8000     |             |   - lines (configs & stream URLs)    |  |
|  +------------^------------+             |   - count_events, count_aggregates   |  |
|               |                          |   - health_samples, alarms           |  |
|               | REST / SSE               +--------------------------------------+  |
|  +------------v------------+                                                       |
|  |   Frontend Dashboard    |                                                       |
|  |   (Vite + React)        |                                                       |
|  |   - Settings: Add Line  |                                                       |
|  |   - Live Stream Tab     |                                                       |
|  +-------------------------+                                                       |
+------------------------------------------------------------------------------------+
```

### Storage Distinction
1. **Line Configurations:** Saved centrally in PostgreSQL on the cloud/VM in the `lines` table. Single source of truth across the factory.
2. **Count & Telemetry Data:**
   - **At Edge:** Stored locally in `counter_outbox.db` (SQLite WAL) to ensure zero data loss during cloud or network outages.
   - **In Cloud:** Dispatched and synchronized into PostgreSQL (`count_events`, `count_aggregates`, `health_samples`, `alarms`).

---

## 3. Database Schema (`services/api/src/db/models.py`)

### Updated `Line` Model
```python
class Line(Base):
    __tablename__ = "lines"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    daily_target: Mapped[int] = mapped_column(Integer, default=60000)
    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    line_coords: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Format: "x1,y1,x2,y2"
    line_direction: Mapped[str] = mapped_column(String(20), default="down")      # "down", "up", "left", "right", "in", "out"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

### PostgreSQL Driver & Docker Environment
- Add `psycopg2-binary>=2.9.9` to `services/api/Dockerfile` dependencies.
- Update `docker-compose.yml` to include a `postgres` service:
  - Image: `postgres:15-alpine`
  - Environment: `POSTGRES_USER=postgres`, `POSTGRES_PASSWORD=postgres`, `POSTGRES_DB=chicken_counting`
  - Volumes: `postgres_data:/var/lib/postgresql/data`
- Central API service receives `DATABASE_URL=postgresql://postgres:postgres@postgres:5432/chicken_counting`.
- In `services/api/src/db/session.py`, support both `postgresql://` and `sqlite://` seamlessly.

---

## 4. Central API Endpoints (`services/api/src/api/lines.py`)

### 1. `POST /api/v1/lines` (Create Line)
- **Request Body (`LineCreatePayload`)**:
  ```json
  {
    "id": "line-2",
    "name": "Lini Konveyor 2",
    "daily_target": 60000,
    "video_url": "rtsp://192.168.1.102/stream1",
    "line_coords": "0,240,640,240",
    "line_direction": "down",
    "is_active": true
  }
  ```
- **Validation**:
  - `id`: Regex `^[a-zA-Z0-9_-]+$`, 2 to 50 chars. Checks uniqueness; returns `409 Conflict` if existing.
  - `daily_target`: Integer > 0.
  - `line_coords`: Optional string. Validates 4 comma-separated numbers (floats/integers).
  - `line_direction`: Enum in `["down", "up", "left", "right", "in", "out"]`.
- **Response**: HTTP 201 with `LineDetailDTO`.

### 2. `GET /api/v1/lines` & `GET /api/v1/lines/{line_id}`
- Returns full details including `video_url`, `line_coords`, and `line_direction` in `LineStatusDTO` and `LineDetailDTO`.

### 3. `PUT /api/v1/lines/{line_id}`
- Updates fields (`name`, `daily_target`, `video_url`, `line_coords`, `line_direction`, `is_active`).

### 4. `DELETE /api/v1/lines/{line_id}`
- Soft deletes by setting `is_active = False` to prevent foreign key or historical data breakage.

### 5. `GET /api/v1/lines/{line_id}/preview`
- Inspects `line.video_url`. If set and accessible, frames are captured from the RTSP/video source. If absent or unreachable, falls back to the synthetic frame generator with an offline camera status.

---

## 5. Edge Counter Startup Pull (`services/counter/main.py`)

1. During `services/counter` initialization:
   - If `--no-sync` is not set and `API_SYNC_URL` is available:
     - Extracts the API host and requests `GET {api_host}/api/v1/lines/{line_id}` with a 5.0-second timeout.
     - If HTTP 200 is returned:
       - If `video_url` is provided and `--video` was not explicitly passed, applies `video_url`.
       - If `line_coords` is provided and `--line` was not explicitly passed, applies `line_coords`.
       - If `line_direction` is provided and `--direction` was not explicitly passed, applies `line_direction`.
       - Logs: `[Startup] Loaded remote configuration for line '%s' from central API.`
   - If the request times out or connection fails (factory offline mode):
     - Logs: `[Startup] Could not reach central API for remote line config. Using local fallback.`
     - Continues cleanly using local CLI/env values.

---

## 6. Frontend UI & State Management

### 1. `PengaturanPage.tsx` Enhancements
- **Daftar Lini Produksi (Table)**:
  - Lists all lines with:
    - ID Lini (monospace badge)
    - Nama Lini
    - Target Harian (formatted with thousand separator)
    - Status (Online / Offline badge with last ping)
    - Arah & Garis (e.g. `down`, `0,240,640,240`)
    - Aksi (Edit modal, Nonaktifkan toggle)
- **Modal Dialog: "Tambah Lini Baru"**:
  - Modal with form inputs:
    - `ID Lini` (required, slug validation)
    - `Nama Lini` (required)
    - `Target Harian` (numeric input, default 60000)
    - `URL Stream / Video` (text input, placeholder `rtsp://...` or `/samples/video.mp4`)
    - `Koordinat Garis Virtual` with quick preset buttons:
      - *Horizontal Tengah:* `0, 240, 640, 240`
      - *Vertikal Tengah:* `320, 0, 320, 480`
    - `Arah Lintasan`: Select dropdown (`down`, `up`, `left`, `right`, `in`, `out`)
  - Validates and submits via `POST /api/v1/lines`.
  - On success:
    - Refreshes global line state in `AppContext`.
    - Shows success toast / message.
    - Closes modal.

### 2. `AppContext.tsx` & Navigation
- Exposes `createLine`, `updateLine`, and `deleteLine` actions.
- Automatically selects the newly created line if desired, instantly updating `LineSelector` and live stream views.

---

## 7. Error Handling & Edge Cases

| Scenario | Handling |
|---|---|
| Duplicate Line ID on Creation | API returns `409 Conflict` with `"Line ID already exists"`. Frontend highlights the ID input with an error. |
| Invalid Line Coordinates format | API rejects with `422 Unprocessable Entity` (`"line_coords must be 4 comma-separated numbers"`). |
| Edge boots while Cloud API is down | Edge logs warning, proceeds with local env arguments (`LINE_COORDS`, `LINE_DIRECTION`). |
| Cloud API connects to PostgreSQL with no tables | `Base.metadata.create_all(bind=engine)` runs on API startup to ensure tables exist. Default lines (`line-1`) seeded if table is empty. |
| Stream URL cannot be reached by preview generator | Preview generator returns synthetic test card with "Camera Disconnected" overlay without crashing the API. |

---

## 8. Verification & Testing Plan

1. **Unit & API Tests (`services/api/tests/test_lines_api.py`)**:
   - `test_create_line_success`: verify `POST /api/v1/lines` returns 201 and stores all fields.
   - `test_create_line_duplicate_id`: verify 409 conflict returned on duplicate.
   - `test_create_line_invalid_coords`: verify 422 on malformed coordinate string.
   - `test_update_and_soft_delete_line`: verify updates and `is_active` toggling.
2. **Edge Remote Config Tests (`services/counter/tests/test_remote_config.py`)**:
   - Mock API endpoint returning line configuration. Verify edge initializes tracker with remote coordinates.
   - Mock API offline; verify edge falls back to CLI flags.
3. **Frontend Integration Tests / Component Verification**:
   - Verify modal opens, validates required fields, submits payload, and updates line list.
   - Verify `LineSelector` reflects newly added line.
