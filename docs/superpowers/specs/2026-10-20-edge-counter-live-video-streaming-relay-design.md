# Edge Counter Live Video Streaming Relay Design Specification

**Date:** 2026-10-20  
**Status:** Approved  
**Author:** AI Agent & System Architect  

---

## 1. Problem Statement & Motivation

Currently, the poultry counter dashboard deployed on the cloud (Render) displays a synthetic animated fallback simulation because the real video file (`Rekaman_2.MOV`, ~1.15 GB) or live camera feed exists exclusively on the edge device/server (`/opt/cdc-counter`).

The edge counter service processes video frames locally and sends count telemetry (`CountEvent`, `CountAggregate`, `HealthSample`), but does not stream video frames to the cloud. The user wants the edge counter service to provide live video streaming so that operators viewing the web dashboard can see the real camera/video feed with detection bounding boxes and the counting line in real time.

Streaming uncompressed raw video 24/7 across the internet is costly and bandwidth-prohibitive for poultry processing plants. Therefore, an **on-demand, bandwidth-optimized frame relay** mechanism is required:
1. Video frames are only streamed when an operator has the dashboard tab open.
2. The edge counter compresses annotated frames (640×480 JPEG, 3–5 FPS) and sends them to the cloud via standard HTTP POST over the existing authenticated connection.
3. The cloud central API caches the latest frame in memory and serves it via the existing MJPEG preview endpoint (`/api/v1/lines/{line_id}/preview`) consumed by the web frontend.

---

## 2. Architecture & Data Flow

```text
Edge Counter (/opt/cdc-counter)                   Central API (Render)                   Browser Web Dashboard
┌─────────────────────────────┐                 ┌───────────────────────┐             ┌─────────────────────┐
│ 1. Processing Video Locally │                 │                       │             │                     │
│    (Rekaman_2.MOV or Camera)│                 │                       │             │                     │
│                             │ 2. Heartbeat    │                       │             │                     │
│    Is viewer watching? ◄────┼─────────────────┤ Viewer Active?        │◄────────────┤ Open Dashboard Tab  │
│    (Yes / No)               │                 │ (Last poll < 10s)     │             │                     │
│                             │                 │                       │             │                     │
│ 3. If Yes: Encodes Frame    │ 4. HTTP POST    │ 5. Memory Buffer      │ 6. MJPEG    │ 7. Displays Live    │
│    with Bounding Boxes      ├────────────────>│    (Latest Frame)     ├────────────>│    Video with       │
│    (3–5 FPS JPEG)           │ /lines/{id}/frame│                       │ /preview    │    Chicken Boxes    │
└─────────────────────────────┘                 └───────────────────────┘             └─────────────────────┘
```

### 2.1 On-Demand Viewer Presence Signaling

1. **Viewer State Tracking:**
   - Central API maintains an in-memory dictionary tracking active viewer timestamps:
     `_active_viewers: dict[str, float] = {}` (maps `line_id` to timestamp `time.time()`).
   - When a browser connects or streams from `GET /api/v1/lines/{line_id}/preview`, the server updates `_active_viewers[line_id] = time.time()`.
   - A line is considered to have active viewers if `time.time() - _active_viewers.get(line_id, 0) < 10.0` seconds.

2. **Signaling via Heartbeat Response:**
   - The edge counter sends periodic health/heartbeat telemetry (`POST /api/v1/sync/batch` or `POST /api/v1/lines/{line_id}/ping`).
   - The central API response includes an on-demand flag:
     `{"stream_requested": bool}`.
   - Alternatively, when `POST /api/v1/sync/batch` succeeds, the response body includes `{"status": "ok", "stream_requested": True/False}`.

### 2.2 Frame Upload from Edge to Cloud

1. **Endpoint Specification:**
   - **Route:** `POST /api/v1/lines/{line_id}/frame`
   - **Headers:**
     - `Authorization: Bearer <API_TOKEN>` (Must be valid `OPERATOR` or `ADMIN` token)
     - `Content-Type: image/jpeg`
   - **Body:** Raw JPEG binary bytes.
   - **Response:** HTTP 204 No Content (or 200 `{"status": "ok"}`).
   - **Rate Limiting:** Maximum 6 FPS accepted per line to protect cloud memory and CPU. Older frames in memory are replaced immediately with the newest frame.

2. **In-Memory Frame Buffer in Central API:**
   - Central API stores the latest frame per line in an in-memory buffer:
     `_latest_frames: dict[str, tuple[bytes, float]] = {}` (stores `(jpeg_bytes, timestamp)`).
   - If the latest frame is newer than 8.0 seconds, `services/api/src/services/preview.py` delivers that frame to the MJPEG stream.
   - If no frame has been received for >8.0 seconds (e.g., edge counter stopped or viewer left), `preview.py` seamlessly falls back to the synthetic generator or a waiting card.

### 2.3 Edge Counter Streaming Worker

1. **Frame Capture & Drawing:**
   - In `services/counter/main.py`:
     - If `stream_requested` is true, on every Nth frame (matching ~3–5 FPS):
       - Uses OpenCV to draw detection bounding boxes, IDs, and counting line on the frame.
       - Resizes to standard web preview resolution (640×480).
       - Compresses to JPEG with quality 70–75 (`cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])`).
       - Asynchronously posts the JPEG to `API_BASE_URL + f"/api/v1/lines/{line_id}/frame"`.
     - If `stream_requested` is false, frame encoding and uploading are completely skipped (0% CPU/bandwidth overhead).

2. **Background Async Dispatcher:**
   - Frame uploads are performed in a non-blocking background thread or task so that edge chicken counting and detection FPS are never stalled by network latency.

---

## 3. Configuration & Environment Variables

| Variable | Service | Default | Description |
| :--- | :--- | :--- | :--- |
| `ENABLE_STREAM_RELAY` | Counter | `1` | Enable or disable on-demand cloud video streaming |
| `STREAM_FPS` | Counter | `4.0` | Target FPS for frame uploads when viewer is active (3.0 - 5.0) |
| `STREAM_JPEG_QUALITY` | Counter | `75` | JPEG compression quality (1-100) |
| `STREAM_MAX_WIDTH` | Counter | `640` | Output frame width |
| `STREAM_MAX_HEIGHT` | Counter | `480` | Output frame height |

---

## 4. Security & Role Permissions

1. **Authentication:**
   - `POST /api/v1/lines/{line_id}/frame` is protected by `require_role(["operator", "admin"])`.
   - Edge devices authenticate using their standard API key (`cdc_live_...`).
   - If `line_id` in token claims (e.g. `device:line-1`) does not match the route path (and token is not `admin`), access is rejected with HTTP 403.
2. **Denial of Service Protection:**
   - Frame payload size capped at 1 MB. Payloads exceeding 1 MB are rejected with HTTP 413.
   - Central API only keeps the single newest frame in RAM (no unbounded memory buffer).

---

## 5. Verification & Testing Strategy

1. **Unit & API Tests:**
   - Test `POST /api/v1/lines/{line_id}/frame` with valid bearer token stores frame in buffer.
   - Test `POST /api/v1/lines/{line_id}/frame` with invalid/expired token returns 401.
   - Test `POST /api/v1/lines/{line_id}/frame` with mismatched line ID returns 403.
   - Test viewer presence tracking updates when `GET /api/v1/lines/{line_id}/preview` is called.
   - Test `GET /api/v1/lines/{line_id}/preview` serves uploaded frame when fresh, and falls back to synthetic when stale (>8s).
2. **Counter Service Integration Tests:**
   - Test edge counter respects `stream_requested=False` by not sending frames.
   - Test edge counter activates frame posting when `stream_requested=True`.
3. **End-to-End Build Verification:**
   - All backend tests pass (`py -m pytest services/api/tests/`).
   - All counter tests pass (`py -m pytest services/counter/tests/`).
   - Frontend build completes cleanly (`npm --prefix frontend run build`).
