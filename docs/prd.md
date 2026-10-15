# PRD – Counting Service and Dashboard (Lihat.id Poultry Counter)

*Focused PRD · Derived from the PT Nocola IoT Solution Technical Proposal · Client: CDC c.q. Mr. Kahfi · Status: Draft v0.1*

## 1. Overview

### 1.1 Purpose

This PRD covers only two software products:

1. **Counting Service** – runs on the edge device, reads the RTSP stream from the industrial camera, detects and counts every chicken on the shackle conveyor, and stores results locally.
2. **Dashboard** – a web/mobile app that shows live and historical counts, target attainment, system status, alarms, and exportable reports.

### 1.2 Out of Scope

ERP/database integration connector, full cloud management platform (multi-site, OTA updates, fleet management), ML training pipeline and labeling tooling, hardware, cabling, network and lighting. These are separate work items. Where the dashboard needs data, this PRD defines a **minimal Data API** (section 6) that those items can later extend.

### 1.3 Problem

Manual counting of broilers on a moving shackle line causes double counts and omissions, and results are only known at shift end. The plant needs an automatic, accurate, real-time count without extra physical sensors and without changing the conveyor.

### 1.4 Goals and Success Metrics

| Goal | Metric / Target |
| --- | --- |
| Accurate counting | Count accuracy ≥ 99% vs. manual ground truth (to be confirmed; proposal mockup shows 99.2%) |
| Real-time performance | Inference < 50 ms per frame at 30 fps; dashboard count lag ≤ 5 s |
| Reliability | Counting continues with no network; zero lost counts on outage |
| Usability | Manager reads daily target attainment in < 10 s from opening the dashboard |
| Adoption | Dashboard used by supervisors on phones at the line |

### 1.5 Users

| Persona | Needs |
| --- | --- |
| Plant/Operations Manager | Daily target progress, trends, reports |
| Line Supervisor / Operator | Live count, camera and edge status, alarms (mobile) |
| System Administrator | Camera setup, counting line calibration, users, thresholds |
| Inventory Staff | Historical counts and Excel/PDF export for reconciliation |

### 1.6 Assumptions

- One camera / one monitoring point initially (per BoQ), designed for multiple lines (mockups show Line A and Line B).
- Camera: IP bullet/dome, ≥ 4MP, ≥ 30 fps, WDR, IP67/IP68, RTSP, PoE.
- Edge device: 10-core CPU/GPU, 16-core Neural Engine, 16 GB memory, 256 GB NVMe, Gigabit Ethernet, Wi-Fi 6E.
- A trained YOLO detection model (YOLO26 preferred, YOLO11 fallback; see section 8) is supplied to the Counting Service; model training is a separate workstream that follows the requirements in 8.1.
- Shackle path is predictable; lighting is adequate or supplemented.

## 2. System Context

```
[IP Camera] --RTSP--> [Counting Service (edge)] --local DB--> [Data API] --> [Dashboard (web/mobile)]
                              |
                    (local admin / calibration UI)
```

The Counting Service writes counts to a local database. The Data API (hosted on the edge device for phase 1, or in a cloud later) serves the Dashboard. This keeps the dashboard working on the plant LAN/Wi-Fi even without internet.

## 3. Counting Service – Requirements

Priority: **P0** must for UAT, **P1** should, **P2** later.

### 3.1 Functional

| ID | Requirement | Pri |
| --- | --- | --- |
| CS-01 | Connect to camera via RTSP URL; support ≥ 4MP at ≥ 30 fps; auto-reconnect with exponential backoff on stream loss | P0 |
| CS-02 | Detect each chicken (multi-object detection) using the supplied model on the edge accelerator | P0 |
| CS-03 | Track each object across frames with a stable ID | P0 |
| CS-04 | Count each object exactly once when it crosses a configurable virtual counting line/zone; no double counting from jitter, swinging or re-entry | P0 |
| CS-05 | Inference latency < 50 ms per frame; sustain 30 fps without dropping frames under normal load | P0 |
| CS-06 | Persist every count event locally (timestamp UTC, line\_id, track\_id, confidence) and per-minute aggregates; survive restart/power loss | P0 |
| CS-07 | Work fully offline; no internet dependency | P0 |
| CS-08 | Configurable parameters: RTSP URL, counting line geometry and direction, ROI mask, confidence threshold, aggregation interval (default 1 min), line name | P0 |
| CS-09 | Calibration/test mode: live video with detection boxes, counting line and running count overlay, accessible from a local admin page | P0 |
| CS-10 | Compute and expose health metrics: stream state, FPS, latency (avg/p95), CPU/GPU/memory, disk usage, temperature, uptime | P0 |
| CS-11 | Auto-start on boot, watchdog restart on crash or hung stream; 24/7 operation | P0 |
| CS-12 | Shift and daily counters with configurable shift times and daily reset (WIB default) | P0 |
| CS-13 | Ignore empty shackles and reverse movement (configurable) | P1 |
| CS-14 | Image-quality monitor (brightness, blur, lens obstruction) raising a warning event | P1 |
| CS-15 | Save snapshot/short clip on alarm or on demand, with retention limit | P1 |
| CS-16 | Manual count correction by admin with audit trail (reason, who, when) | P1 |
| CS-17 | Support multiple camera/line instances in one service via configuration | P2 |
| CS-18 | Run YOLO26 (YOLO11 as configurable fallback) through a detector interface with selectable inference backend (Core ML, TensorRT/CUDA, OpenVINO, CPU); backend and model set by config | P0 |
| CS-19 | Include a benchmark tool reporting FPS and p95 latency on the target device, plus an accuracy harness that replays ground-truth video and reports count accuracy and double-count rate | P0 |
| CS-20 | Record model name, version and license reference in every health sample and report, so the deployed model is traceable | P1 |

### 3.2 Non-Functional

| Area | Requirement |
| --- | --- |
| Accuracy | ≥ 99% on agreed UAT video set at maximum line speed; double-count rate < 0.5% |
| Performance | Latency < 50 ms; CPU/GPU headroom ≥ 20% at steady state |
| Reliability | Recover stream within 30 s; no count lost on restart; local buffer retains ≥ 7 days |
| Security | Admin page behind authentication; camera credentials encrypted at rest; services bound to LAN only |
| Privacy | No face or worker identification; video not retained by default |
| Observability | Structured logs with rotation; health endpoint |

### 3.3 Counting Logic (Spec)

1. Decode frame, apply ROI mask.
2. Run detector, keep detections above confidence threshold.
3. Update tracker (associate detections to tracks, handle occlusion with a short track-lost buffer).
4. For each track, check if its anchor point crosses the counting line in the configured direction; if so and not already counted, increment counter and emit a count event.
5. Every interval, roll up the events into an aggregate with count, rate (birds/min), and average confidence.
6. Update line status from the threshold rules (see 5.4).

## 4. Dashboard – Requirements

### 4.1 Navigation

Left menu: **Dashboard**, **Production Lines**, **Alarms**, **Reports**, **Settings**. Top bar: notification bell and user menu. Responsive for phones and desktop. Default language Indonesian with English option; times in WIB.

### 4.2 Screen 1 – Dashboard Overview ("Ringkasan Hari Ini")

| ID | Requirement | Pri |
| --- | --- | --- |
| DB-01 | KPI cards: Total counted today, Average rate (birds/min), Camera status (Online/Offline), Detection accuracy | P0 |
| DB-02 | Hourly count trend line chart for today | P0 |
| DB-03 | Daily target gauge showing % attainment and absolute target | P0 |
| DB-04 | Live camera preview with detection boxes | P1 |
| DB-05 | Auto-refresh every ≤ 5 s with a visible "last updated" time | P0 |

### 4.3 Screen 2 – Live Monitoring and Alarms (per line)

| ID | Requirement | Pri |
| --- | --- | --- |
| DB-06 | Live camera preview with boxes and a "Counted: N" overlay | P0 |
| DB-07 | System status panel: FPS, latency, edge status (Online/Offline) | P0 |
| DB-08 | Alarms and notifications list with severity (Warning/Critical), message and timestamp | P0 |
| DB-09 | Threshold matrix table (metric, Warning amber, Critical red) for production rate, latency, detection accuracy, downtime; editable by admin | P1 |
| DB-10 | Switch between lines via selector | P0 |

### 4.4 Screen 3 – Alarms

| ID | Requirement | Pri |
| --- | --- | --- |
| DB-11 | Alarm list with filters (severity, line, status, date) | P0 |
| DB-12 | Alarm lifecycle: open, acknowledge, resolve, with optional note | P0 |
| DB-13 | Alarm types: camera offline, stream lost, rate below threshold, latency above threshold, accuracy/confidence low, edge resource high, image-quality problem | P0 |
| DB-14 | In-app notification and email for Critical alarms | P1 |

### 4.5 Screen 4 – Reports and Historical Data

| ID | Requirement | Pri |
| --- | --- | --- |
| DB-15 | Filters: period (hourly, shift, daily, custom range), line, search | P0 |
| DB-16 | Summary cards: Total counted, Average per hour, Attainment vs. target, Data integrity | P0 |
| DB-17 | Log table: timestamp (WIB), line, count, rate, status chip (Normal / Warning / Critical), pagination | P0 |
| DB-18 | Export current view to PDF and Excel | P0 |
| DB-19 | Scheduled daily report by email | P2 |

### 4.6 Screen 5 – Settings

| ID | Requirement | Pri |
| --- | --- | --- |
| DB-20 | Users and roles: Admin, Manager, Operator, Viewer | P0 |
| DB-21 | Line and camera configuration: names, daily target, shift times | P0 |
| DB-22 | Counting Service configuration: RTSP URL, counting line editor over a snapshot, confidence threshold, test mode | P1 |
| DB-23 | Threshold matrix configuration | P1 |
| DB-24 | Language and timezone | P1 |

### 4.7 Roles and Permissions

| Capability | Admin | Manager | Operator | Viewer |
| --- | :-: | :-: | :-: | :-: |
| View dashboards, live, reports | ✓ | ✓ | ✓ | ✓ |
| Acknowledge alarms | ✓ | ✓ | ✓ |  |
| Export reports | ✓ | ✓ |  |  |
| Edit targets and thresholds | ✓ | ✓ |  |  |
| Manage users, lines, service config | ✓ |  |  |  |

### 4.7a Dashboard Non-Functional

| Area | Requirement |
| --- | --- |
| Performance | First load < 3 s on plant Wi-Fi; charts render < 1 s after data |
| Compatibility | Latest Chrome, Edge, Safari; Android and iOS browsers (PWA-capable) |
| Accessibility | Readable contrast, touch targets ≥ 44 px, works in bright plant conditions |
| Security | Login with hashed passwords, session timeout, RBAC enforced on the server, HTTPS |
| Availability | Dashboard remains usable on the local network without internet |

## 5. Business Rules

### 5.1 Definitions

- **Count:** one chicken crossing the counting line once.
- **Rate:** counts per minute over the aggregation window.
- **Attainment:** counted total divided by the daily target, as a percent.
- **Data integrity:** share of expected aggregation windows that have a valid record.
- **Downtime:** minutes with stream offline or the service not producing frames.

### 5.2 Day and Shift

Day boundary and shifts are configurable per line; default timezone WIB (UTC+7); data stored in UTC.

### 5.3 Status Logic

Each window gets Normal, Warning, or Critical based on the threshold matrix. Initial thresholds must be set by the client during UAT, because the proposal's mockup values are inconsistent (see section 10).

### 5.4 Alarm Rules (Defaults, to be confirmed)

| Metric | Warning | Critical |
| --- | --- | --- |
| Camera/stream offline | > 30 s | > 2 min |
| Rate below expected | < 130 birds/min (mockup) | < 110 birds/min (mockup) |
| Inference latency | > 50 ms | > 100 ms |
| Detection confidence (avg) | < 90% | < 80% |
| Downtime per hour | > 5 min | > 10 min |

## 6. Minimal Data API (Dashboard ↔ Counting Service)

The API is served from the edge device (or later a cloud). All endpoints require authentication and HTTPS.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | /api/v1/auth/login | Obtain session/token |
| GET | /api/v1/lines | List lines with status and daily target |
| GET | /api/v1/lines/{id}/summary?period=today | KPI cards and target attainment |
| GET | /api/v1/lines/{id}/counts?from=&to=&granularity=minute\|hour\|day | Time series and log table |
| GET | /api/v1/lines/{id}/status | FPS, latency, stream state, resource usage |
| GET | /api/v1/lines/{id}/live | MJPEG/HLS/WebRTC preview with overlay |
| GET | /api/v1/alarms | List/filter alarms |
| POST | /api/v1/alarms/{id}/ack | Acknowledge |
| POST | /api/v1/alarms/{id}/resolve | Resolve |
| GET/PUT | /api/v1/config/lines/{id} | Counting line, ROI, targets, thresholds |
| GET | /api/v1/reports/export?format=pdf\|xlsx&from=&to=&line= | Report file |
| POST | /api/v1/counts/{id}/correction | Manual correction (admin) |

Example summary response:

```json
{
  "line_id": "lineA",
  "date": "2026-10-15",
  "total": 48250,
  "avg_rate_per_min": 120,
  "target": 62000,
  "attainment_pct": 77.8,
  "camera_status": "online",
  "detection_confidence_pct": 99.2,
  "updated_at": "2026-10-15T08:35:12Z"
}
```

## 7. Data Model

| Entity | Key fields |
| --- | --- |
| Line | id, name, daily\_target, shift\_config, timezone |
| Camera | id, line\_id, rtsp\_url (encrypted), resolution, fps |
| CountingConfig | line\_id, line\_geometry, direction, roi\_mask, confidence\_threshold, interval\_sec |
| CountEvent | id, line\_id, track\_id, ts\_utc, confidence |
| CountAggregate | id, line\_id, window\_start, window\_end, count, rate\_per\_min, confidence\_avg, status |
| HealthSample | ts\_utc, line\_id, fps, latency\_avg, latency\_p95, cpu, gpu, mem, disk, temp, stream\_state |
| ThresholdRule | line\_id, metric, warning, critical |
| Alarm | id, line\_id, type, severity, value, opened\_at, ack\_by, ack\_at, resolved\_at, note |
| User | id, name, email, role, status |
| AuditLog | id, user\_id, action, entity, before, after, ts\_utc |

Retention: events 90 days, aggregates 12 months, health samples 30 days (configurable).

## 8. Technology Stack and Licensing

The stack is hardware-agnostic: the edge device is not yet chosen, so only the inference backend changes per device. The detector is YOLO26, with YOLO11 as fallback.

| Layer | Choice |
| --- | --- |
| Counting Service language | Python 3.11 |
| Detector | YOLO26 nano (upgrade to small if UAT needs it); YOLO11 as fallback |
| Inference runtime | ONNX Runtime with a per-device backend (see 8.2); CPU fallback during development |
| Tracking and line counting | ByteTrack with the `supervision` line-zone counter |
| Video ingest | FFmpeg / PyAV with OpenCV; hardware decode optional |
| Local storage | SQLite (WAL mode) |
| Data API | FastAPI, SQLAlchemy, Alembic; Server-Sent Events for live updates |
| Auth | JWT sessions, argon2 password hashing, server-side RBAC |
| Reports | openpyxl (Excel), WeasyPrint (PDF) |
| Live video | MJPEG sub-stream with overlay in phase 1; WebRTC (MediaMTX or go2rtc) if latency requires |
| Dashboard | React, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Query, Apache ECharts, i18next, PWA |
| Reverse proxy / TLS | Caddy with internal CA for LAN HTTPS |
| Packaging | Docker Compose on Linux/Windows devices; native `launchd` service on macOS (Docker on macOS cannot reach the Neural Engine) |
| Later (cloud) | PostgreSQL, optionally TimescaleDB; SQLAlchemy models stay portable |
| Quality | pytest, Playwright, GitHub Actions CI, structured JSON logs, `/healthz` endpoint |

### 8.1 Detection Model: YOLO26 with YOLO11 Fallback

- **Primary: YOLO26** (released January 2026). It is end-to-end and NMS-free, which removes a post-processing step and suits edge latency targets.
- **Fallback: YOLO11.** Use it if the chosen device or runtime cannot compile or run YOLO26 correctly. The Ultralytics API is nearly identical, so the switch is one line of config.
- **Size:** start with nano; move to small only if UAT footage shows misses on overlapping or partly hidden birds. Medium and larger are not planned.
- **Classes:** `chicken`, plus optional `empty_shackle` so hooks without birds can be ignored.
- **Training:** input 640 px (test 960 px only if birds look small in the 4MP frame); footage from all shifts and lighting, with steam, water spray and different bird sizes.
- **Success is measured by count accuracy on held-out video**, not only mAP.
- **Export:** ONNX as the common format; Core ML, TensorRT or OpenVINO builds per device when they beat ONNX Runtime on the benchmark.

### 8.2 Hardware-Agnostic Inference

| If the device is | Inference backend (config change only) |
| --- | --- |
| Apple Silicon (what the proposal specification resembles) | ONNX Runtime with Core ML provider |
| NVIDIA Jetson or PC with NVIDIA GPU | ONNX Runtime with TensorRT/CUDA provider |
| Intel or AMD mini PC without GPU | ONNX Runtime with OpenVINO provider, or CPU |

Design rules:

1. Hide inference behind a single interface, `Detector.predict(frame)`, so a backend or model swap touches one module.
2. Keep device settings (backend, input size, thread count) in a config file, not code.
3. Provide a benchmark script that prints FPS and p95 latency on any device.
4. **Hardware gate:** before the device is purchased for rollout, the benchmark on the candidate device must show ≥ 30 fps and p95 latency < 50 ms with the real model.

### 8.3 Licensing

YOLO26 and YOLO11 are both released by Ultralytics under AGPL-3.0, with a separate Enterprise License for closed commercial use. The project decision is to use YOLO, so the following conditions apply:

1. **Nocola obtains the Ultralytics Enterprise License before delivering the Counting Service as closed-source, sold or bundled software.** Without it, the AGPL requires offering the full source of the combined work to recipients and network users.
2. AGPL-3.0 use is acceptable only for internal research, evaluation and prototypes that are not delivered to the client.
3. Exporting to ONNX, Core ML or TensorRT does not remove the obligation; it follows the model and the code that produced it.
4. Weights fine-tuned from Ultralytics pretrained weights are treated as derivative.
5. Open questions for legal review: who is the licensee (Nocola or client), whether terms are per developer, per deployment or per device, coverage for additional lines and future clients, and how the client contract describes code ownership.
6. Because of the detector interface in 8.2, a permissively licensed model can replace YOLO if the license cannot be agreed.

## 9. Delivery Plan and Acceptance

### 9.1 Milestones (fits proposal weeks 2–8)

| Weeks | Counting Service | Dashboard |
| --- | --- | --- |
| 2–3 | RTSP ingest, config, storage schema, health metrics | UI shell, auth, mock data, navigation |
| 4 | On-site stream test, calibration page, sample recording | Data API v1 |
| 5–6 | Detector + tracker + counting line, latency tuning, watchdog | Overview, Live Monitoring, Reports with real data |
| 7–8 | Alarms, corrections, UAT fixes | Alarms, Settings, export, training and docs |

### 9.2 UAT Acceptance Criteria

1. Count accuracy ≥ 99% on the agreed ground-truth set across shifts and lighting at max line speed.
2. 24-hour run at 30 fps with p95 latency < 50 ms, no crash.
3. Network and internet cut for 1 hour: counting continues, dashboard on LAN still works, no data lost.
4. Power-cycle: service auto-recovers in < 2 min with counts preserved.
5. All P0 dashboard screens work on desktop and a phone over plant Wi-Fi.
6. Alarms fire within 60 s for camera offline and rate below threshold.
7. PDF and Excel exports match the on-screen data.
8. RBAC verified for all four roles.

## 10. Risks, Gaps and Open Questions

| Item | Detail / Action |
| --- | --- |
| Mockup numbers conflict | Overview shows 120 birds/min vs. Reports 1,190 birds/hour; 48,250 vs. 12,480 totals; targets 62,000 vs. 300,000. Define units and scope (line vs. plant). |
| Threshold values unclear | Accuracy "0.096 / 0.075" and latency amber 130 ms / red 110 ms contradict the <50 ms claim. Client to define real thresholds. |
| Accuracy target | Needs a contractual number and a test protocol. |
| Occlusion and overlap | Birds may overlap or swing; tune tracker and camera angle at survey. |
| Lighting, steam, water on lens | Use WDR, supplemental light, quality alarm. |
| Line speed unknown | Confirm shackle speed (checklist item 2); benchmark early. |
| Edge hardware specified by silicon only | Confirm exact device and OS to choose inference runtime. |
| Dashboard hosting | Phase 1 on edge or cloud? Affects remote access and security. |
| Number of lines | BoQ says one point; mockups show two lines. |
| Live video in browser | Choose MJPEG, HLS or WebRTC based on latency and bandwidth. |
| Text placeholder | Proposal closing still says \[NAMA KLIEN\]. |
| YOLO license (AGPL-3.0) | Closed-source delivery needs the Ultralytics Enterprise License; obtain it before shipping and confirm licensee and per-device terms (see 8.3). Fallback: swap to a permissively licensed detector via the detector interface. |
| Device undecided | Hardware-agnostic inference plus a benchmark gate (≥ 30 fps, p95 < 50 ms) before purchase (see 8.2). |

## 11. Glossary

- **Shackle:** overhead hook carrying each bird.
- **Edge device:** local compute unit running the AI model.
- **RTSP:** Real Time Streaming Protocol.
- **ROI:** Region of interest in the camera frame.
- **WDR:** Wide Dynamic Range.
- **UAT:** User Acceptance Test.
