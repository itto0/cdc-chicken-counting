# Design Specification: Dashboard & Data API Integration

**Date:** 2026-10-16  
**Status:** Approved  
**Related Documents:** `docs/prd.md`, `docs/superpowers/plans/2026-10-15-chicken-counting-system.md`

---

## 1. Executive Summary

This specification outlines the architecture, API contracts, and user interface implementation for the complete poultry shackle counting dashboard and its underlying Data API services. The core edge counting service and foundational SQLite batch sync engine are already verified with 130 passing tests. This phase connects the end-to-end user experience across all five PRD dashboard views (Overview, Live Stream, Alarms, Reports & Analytics, Settings) driven by real-time Server-Sent Events (SSE) and comprehensive REST endpoints.

---

## 2. System Architecture & Component Interactions

```
+-----------------------------------------------------------------------------------+
|                                  Edge Counter                                     |
|  [RTSP / Video Source] -> [Detector & Tracker] -> [LocalStorage SQLite Outbox]   |
|                                                  |                                |
|                                           HTTP Sync Dispatcher                    |
+--------------------------------------------------|--------------------------------+
                                                   | POST /api/v1/sync/batch
                                                   v
+-----------------------------------------------------------------------------------+
|                                    Data API                                       |
|                                                                                   |
|  [Sync Batch Ingest] -> [Threshold Alarm Evaluator] -> [SQLite WAL Database]     |
|                                                              |                    |
|  [SSE Live Stream Hub] <--- Real-time events & metrics ------+                    |
|  [MJPEG Preview Engine]                                                           |
|  [REST API: Lines, Summary, Counts, Alarms Lifecycle, Auth]                      |
|  [Reporting: Excel (.xlsx) & PDF (.pdf) Exporters]                                |
+--------------------------------------------------^--------------------------------+
                                                   | HTTP REST & SSE
                                                   |
+--------------------------------------------------v--------------------------------+
|                             React 18 Dashboard (PWA)                              |
|                                                                                   |
|  [API Client & SSE Hooks] <-> [AppContext: Active Line & Role Switcher]           |
|                                                                                   |
|  [Overview]        [Live Stream]     [Alarms]       [Reports]       [Settings]    |
|  - Real-time KPIs  - MJPEG player    - Active/Hist  - Date filter   - Line config |
|  - Hourly Pace     - Telemetry HUD   - Acknowledge  - Volume charts - Thresholds  |
|  - Health status   - Threshold tags  - Resolve modal- Excel/PDF DL  - Roles matrix|
+-----------------------------------------------------------------------------------+
```

---

## 3. Data API Specifications

### 3.1 Authentication & Role-Based Access Control (RBAC)
- **Token Mechanism:** Lightweight signed JWT (HMAC-SHA256) with 24-hour expiration.
- **Roles:**
  - `admin`: Full system access, threshold modifications, line configuration, user management.
  - `manager`: Line settings, threshold updates, reports download, alarm acknowledge/resolve.
  - `operator`: Live view, report inspection, alarm acknowledge and resolve with notes.
  - `viewer`: Read-only view for all screens.
- **Endpoints:**
  - `POST /api/v1/auth/login`
    - Body: `{"username": "admin", "password": "password"}`
    - Response: `{"access_token": "...", "token_type": "bearer", "user": {"id": 1, "username": "admin", "role": "admin"}}`
  - `GET /api/v1/auth/me`
    - Returns current authenticated user record.
- **Direct Access Mode:** In development/demo mode, a persistent UI role switcher injects a simulated authenticated header, allowing seamless testing without requiring repeated manual logins.

### 3.2 Lines CRUD & Status
- **Endpoints:**
  - `GET /api/v1/lines`
    - Returns list of lines with current telemetry status (`online`, `offline`, `degraded`), last ping timestamp, daily target, and current total count.
  - `GET /api/v1/lines/{id}`
    - Returns detailed line configuration.
  - `PUT /api/v1/lines/{id}`
    - Updates line name, RTSP stream URL, daily target, target speed (chickens/min), and status.

### 3.3 Summary & Historical Metrics
- **Endpoints:**
  - `GET /api/v1/lines/{id}/summary?period=today|shift|week`
    - Query Parameters: `period` (default: `today`)
    - Returns calculated KPIs:
      - `line_id`: string
      - `period`: string
      - `total_count`: integer (sum of counts in period)
      - `target_count`: integer
      - `target_attainment_pct`: float (0.0 to 100.0+)
      - `current_speed_cpm`: float (chickens per minute over last 5 minutes)
      - `target_speed_cpm`: float
      - `active_alarms_count`: integer
      - `camera_status`: `online` | `offline` | `degraded`
      - `last_event_time`: ISO8601 string or null
      - `fps`: float
      - `latency_p95_ms`: float
  - `GET /api/v1/lines/{id}/counts?from=&to=&granularity=minute|hourly|daily&page=1&limit=50`
    - Returns:
      - `aggregates`: array of `{bucket: ISO8601, count: integer, speed_cpm: float}` for charting.
      - `events`: paginated raw count events `{id, timestamp, count_increment, track_id, direction}`.
      - `pagination`: `{total: integer, page: integer, limit: integer}`.

### 3.4 Alarms Management Lifecycle
- **Endpoints:**
  - `GET /api/v1/alarms?line_id=&status=active|acknowledged|resolved&severity=warning|critical`
    - Returns list of alarm instances matching query filters, sorted newest first.
  - `PATCH /api/v1/alarms/{id}`
    - Request Body:
      ```json
      {
        "status": "acknowledged" | "resolved",
        "acknowledged_by": "operator_name",
        "notes": "Belt speed adjusted to normal."
      }
      ```
    - Updates alarm record and records audit metadata (`acknowledged_at`, `resolved_at`, notes).

### 3.5 Real-Time Telemetry & Live Video Preview
- **Server-Sent Events (SSE):**
  - `GET /api/v1/live/{line_id}/stream` (existing endpoint verified in test suite).
  - Emits events:
    - `count`: `{line_id, timestamp, count, speed_cpm}`
    - `health`: `{line_id, fps, latency_p95, camera_status}`
    - `alarm`: `{alarm_id, line_id, type, severity, message}`
- **MJPEG Live Stream Fallback:**
  - `GET /api/v1/live/{line_id}/preview`
  - Streams `multipart/x-mixed-replace; boundary=frame` delivering annotated JPEG frames with counting lines and track bounding boxes.
  - If no live camera feed is connected, delivers a synthesized or captured frame overlay loop with real-time HUD stats.

### 3.6 Report Generation
- **Excel Export:** `GET /api/v1/reports/export?line_id=&from=&to=&format=xlsx` (existing verified implementation via `openpyxl`).
- **PDF Export:** `GET /api/v1/reports/export?line_id=&from=&to=&format=pdf`
  - Generates downloadable PDF document using `reportlab`.
  - Content: Title, metadata header, shift metrics summary card table, hourly throughput breakdown, and recent alarm incident log.

---

## 4. Frontend Architecture & Screen Implementation

### 4.1 Structure & State Management
- **Directory Structure:**
  ```
  frontend/src/
  ├── components/
  │   ├── common/             # MetricCard, StatusBadge, DataTable, Modal, FilterBar
  │   ├── layout/             # Header, NavigationTabs, ConnectionBanner
  │   └── views/              # OverviewView, LiveStreamView, AlarmsView, ReportsView, SettingsView
  ├── context/
  │   └── AppContext.tsx      # Active line, Active user role, Notifications
  ├── hooks/
  │   └── useLiveStream.ts    # SSE subscriber with auto-reconnection & fallback
  ├── services/
  │   └── apiClient.ts        # Typed fetch client with baseUrl & auth interceptor
  ├── types/
  │   └── index.ts            # Line, CountSummary, Alarm, LogEvent, UserRole
  ├── App.tsx
  └── main.tsx
  ```
- **Context Capabilities:**
  - `currentLineId`: selected production line (e.g. `line-1`).
  - `currentRole`: active role (`admin`, `manager`, `operator`, `viewer`) toggleable in top navbar.
  - `isConnected`: boolean connection status to API & SSE.
  - `unreadAlarms`: count of active unresolved alarms.

### 4.2 Screen Specifications

#### 1. Overview Screen (`OverviewView.tsx`)
- Connected to `GET /api/v1/lines/{id}/summary` and real-time SSE stream.
- **KPI Cards:**
  - Total Daily Count (with animated increment flash on live events).
  - Production Speed (Chickens/Minute) vs. Target Speed indicator.
  - Attainment % with color-coded progress meter (green >= 95%, amber >= 85%, red < 85%).
  - Active Alarms badge with direct jump to Alarms tab.
- **Hourly Pace Chart:**
  - Recharts composite chart: Bars = Actual counts per hour, Line = Target pace per hour.
- **System Health Card:**
  - Edge FPS gauge, Latency p95, Camera connection status.

#### 2. Live Stream Screen (`LiveStreamView.tsx`)
- **Video Canvas / Frame Viewer:**
  - `<img>` tag streaming from `/api/v1/live/{line_id}/preview`.
  - Reconnect banner and placeholder when stream is offline.
  - Toggle controls: Toggle Virtual Line overlay, Toggle Bounding Boxes.
- **Real-Time Telemetry HUD:**
  - Speed gauge (Chickens / min) updated via SSE in sub-second intervals.
  - Last chicken detected timestamp (relative "X seconds ago").
  - Edge FPS & inference time.
- **Threshold Matrix Banner:**
  - Visual status pill: Normal (green), Under-speed warning (amber), Zero-count critical (red).

#### 3. Alarms Screen (`AlarmsView.tsx`)
- **Filter Controls:**
  - Status toggle buttons: All, Active (unresolved), Acknowledged, Resolved.
  - Severity dropdown: All, Critical, Warning, Info.
- **Alarm Incidents Table:**
  - Columns: Timestamp, Alarm Type, Severity, Trigger Value, Threshold, Status, Acknowledged By, Actions.
- **Action Modal:**
  - For Active alarms: "Acknowledge" button.
  - For Acknowledged alarms: "Resolve" button with mandatory or optional Operator Notes text area.
  - Permissions enforcement: Viewer role sees disabled action buttons with tooltip "Requires Operator or Manager role".

#### 4. Reports & Analytics Screen (`ReportsView.tsx`)
- **Filter Bar:**
  - Date presets: Today, Yesterday, This Week, Custom Date Range.
  - Shift filter: All Shifts, Shift 1 (07:00 - 15:00), Shift 2 (15:00 - 23:00).
- **Aggregated Statistics:**
  - Summary metric tiles for selected range: Total birds, Avg speed, Peak hour, Total downtime / alarms.
- **Throughput Visualization:**
  - Hourly or Daily bar chart of counts over the selected range.
- **Raw Count Log Table:**
  - Paginated count records with timestamps and track IDs.
- **Export Actions:**
  - "Export Excel (.xlsx)" button triggers download from `/api/v1/reports/export?format=xlsx`.
  - "Export PDF (.pdf)" button triggers download from `/api/v1/reports/export?format=pdf`.

#### 5. Settings Screen (`SettingsView.tsx`)
- **Line & Camera Configuration:**
  - Edit Line Name, Target Speed (chickens/min), Shift Target, RTSP Camera Stream URL.
  - Save changes via `PUT /api/v1/lines/{id}`.
- **Threshold Matrix Configuration:**
  - Under-speed warning threshold (e.g. < 40 cpm).
  - Under-speed critical threshold (e.g. < 20 cpm).
  - Over-speed warning threshold (e.g. > 150 cpm).
  - Camera disconnect timeout (e.g. 10 seconds).
  - Save changes with permission check (Admin and Manager only).
- **Role Permissions Reference:**
  - Explanatory matrix table detailing what Admin, Manager, Operator, and Viewer can perform.

---

## 5. Testing & Verification Plan

1. **Backend Integration Tests (`services/api/tests/`):**
   - `test_lines_api.py`: Verify lines listing, detail, and update endpoints.
   - `test_summary_api.py`: Verify summary calculation accuracy, attainment %, and period filtering.
   - `test_counts_api.py`: Verify count aggregation by hour/day and raw events pagination.
   - `test_alarms_lifecycle_api.py`: Verify alarm listing, status filtering, and PATCH acknowledge/resolve lifecycle.
   - `test_auth_api.py`: Verify login JWT token generation, invalid password rejection, and `/auth/me` validation.
   - `test_pdf_report_api.py`: Verify PDF binary response with correct `application/pdf` Content-Type and non-empty payload.
   - `test_mjpeg_preview_api.py`: Verify multipart MJPEG response stream.
2. **Frontend Build & Typecheck:**
   - Execute TypeScript compiler check (`npm run build` / `tsc --noEmit`).
   - Validate that all screens render without runtime errors and mock fallback handles API unavailability gracefully.
3. **Full Suite Regression:**
   - Run the entire Python test suite to ensure all 130 existing tests remain passing.
