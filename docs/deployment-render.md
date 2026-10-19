# Deployment Guide: Render Cloud Hosting

This guide provides complete, step-by-step instructions for deploying the **Poultry Counter (Lihat.id)** platform to [Render](https://render.com) cloud hosting.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Option A: 1-Click Blueprint Deployment (`render.yaml`)](#2-option-a-1-click-blueprint-deployment-renderyaml)
3. [Option B: Manual Dashboard Setup](#3-option-b-manual-dashboard-setup)
4. [Edge Node Configuration (`services/counter`)](#4-edge-node-configuration-servicescounter)
5. [Initial Login & Default Credentials](#5-initial-login--default-credentials)
6. [Production & Free Tier Notes](#6-production--free-tier-notes)
7. [Troubleshooting & Verification](#7-troubleshooting--verification)

---

## 1. Architecture Overview

The Poultry Counter platform is composed of four main components operating across cloud hosting and on-premise industrial edge nodes:

```
+-----------------------------------------------------------------------------------+
|                                   RENDER CLOUD                                    |
|                                                                                   |
|  +---------------------------+                +--------------------------------+  |
|  |       cdc-frontend        |                |            cdc-api             |  |
|  |  (Static Site CDN / Vite) |  API Requests  |     (Docker Web Service)       |  |
|  |  React 18 SPA + Tailwind  | -------------> |     FastAPI Python Backend     |  |
|  |  URL: cdc-frontend...     |  (CORS / HTTPS)|     URL: cdc-api...            |  |
|  +---------------------------+                +--------------------------------+  |
|               ^                                                |                  |
|               | HTTPS Browsing                                 | Internal DB      |
|               |                                                | Connection       |
|               v                                                v                  |
|  +---------------------------+                +--------------------------------+  |
|  |        Web Clients        |                |          cdc-postgres          |  |
|  | (Plant Manager / Operator)|                |       (Managed PostgreSQL)     |  |
|  +---------------------------+                |       Port: 5432 Internal      |  |
|                                               +--------------------------------+  |
+----------------------------------------------------------------|------------------+
                                                                 ^
                                             HTTPS POST Batches  |
                                             /api/v1/sync/batch  |
                                                                 |
                               +---------------------------------+
                               |
+------------------------------|----------------------------------------------------+
| ON-PREMISE EDGE FACILITY     |                                                    |
|                              |                                                    |
|    +-------------------------+----+                                               |
|    |        services/counter      |                                               |
|    |  OutboxSyncDispatcher Worker |                                               |
|    +-------------------------+----+                                               |
|                              ^                                                    |
|                              | Ingests & Drains                                   |
|                              v                                                    |
|    +------------------------------+     Count Events      +------------------+    |
|    |    Local SQLite Outbox DB    | <-------------------- |  Inference Engine|    |
|    |     (counter_outbox.db)      |                       | (YOLO / Shackle) |    |
|    +------------------------------+                       +------------------+    |
|                                                                     ^             |
|                                                                     | Video Frame |
|                                                           +------------------+    |
|                                                           | RTSP Camera Feed |    |
|                                                           | Conveyor Shackle |    |
|                                                           +------------------+    |
+-----------------------------------------------------------------------------------+
```

### Component Breakdown

| Component | Render Service Type | Source Directory / Artifact | Role & Protocol |
| :--- | :--- | :--- | :--- |
| **`cdc-postgres`** | Managed PostgreSQL | Managed Database | Stores system configuration, lines, user authentication, raw count events, aggregations, and alarms. |
| **`cdc-api`** | Web Service (`docker`) | `./services/api/Dockerfile` | Central FastAPI backend serving REST API, WebSockets, JWT authentication, and edge sync batch ingestion. |
| **`cdc-frontend`** | Static Site (`static`) | `frontend/` (`dist/`) | High-performance React 18 / Vite single-page application hosted globally on Render's CDN. |
| **`services/counter`** | On-premise Edge Node | `services/counter/` | Runs on edge hardware at the conveyor line. Detects carcasses via computer vision and syncs batches over HTTPS. |

---

## 2. Option A: 1-Click Blueprint Deployment (`render.yaml`)

The repository includes a declarative Infrastructure-as-Code (IaC) blueprint at `render.yaml`. This is the fastest and recommended way to deploy the entire cloud infrastructure in a single operation.

### Step 1: Fork or Push Repository
Make sure your latest code including `render.yaml` is pushed to your GitHub or GitLab repository.

### Step 2: Open Render Blueprint Manager
1. Log in to your [Render Dashboard](https://dashboard.render.com/).
2. In the top navigation bar, click **New +** and select **Blueprint**.

### Step 3: Connect Git Repository
1. Select your Git provider (GitHub / GitLab) and choose the `cdc-chicken-counting` repository.
2. Select your deployment branch (e.g., `main` or `deploy/render-cloud`).
3. Click **Continue**.

### Step 4: Blueprint Auto-Discovery
Render will automatically parse `render.yaml` and display the resources to be created:
* **Database**: `cdc-postgres` (PostgreSQL)
* **Web Service**: `cdc-api` (Docker runtime, build context `.`)
* **Static Site**: `cdc-frontend` (Static runtime, root `frontend`, build command `npm ci && npm run build`)

### Step 5: Configure `VITE_API_BASE_URL`
During blueprint setup, Render will prompt for the static site's environment variable:
* **`VITE_API_BASE_URL`**:
  * Set this to `https://<cdc-api-subdomain>.onrender.com` (for example: `https://cdc-api.onrender.com` or your designated backend subdomain).
  * *Note*: If you do not know your exact subdomain yet, enter a placeholder (e.g. `https://cdc-api.onrender.com`). Once `cdc-api` finishes deploying and reveals its URL, update `VITE_API_BASE_URL` in `cdc-frontend` > **Environment** and trigger **Manual Deploy > Deploy latest commit** (see [Important Vite Note](#important-vite-build-time-environment-note)).

### Step 6: Apply and Deploy
Click **Apply**. Render will concurrently:
1. Provision the managed PostgreSQL database.
2. Build and launch the Docker container for `cdc-api`, generating a secure `JWT_SECRET_KEY` and linking `DATABASE_URL`.
3. Install dependencies and compile the React frontend, then distribute the static assets to the global CDN.

---

## 3. Option B: Manual Dashboard Setup

If you prefer provisioning each component manually through the Render Dashboard UI, follow these sequential steps.

### Step 3.1: Provision Managed PostgreSQL (`cdc-postgres`)

1. In Render Dashboard, click **New +** > **PostgreSQL**.
2. Configure settings:
   * **Name**: `cdc-postgres`
   * **Database**: `chicken_counting`
   * **User**: *(leave blank for Render to auto-generate a valid user, or specify e.g. `cdc_admin`. Note: `postgres` is a reserved system role and will be rejected by Render)*
   * **Region**: `Oregon (US West)` *(recommended; use same region for all components)*
   * **Plan**: `Free` (or `Starter` for production)
3. Click **Create Database**.
4. Once created, locate the **Connections** section on the database details page and copy the **Internal Database URL** (e.g. `postgres://usr:pwd@dpg-xxxx-a:5432/chicken_counting`).

---

### Step 3.2: Provision Backend API Web Service (`cdc-api`)

1. Click **New +** > **Web Service**.
2. Connect your Git repository.
3. Configure service settings:
   * **Name**: `cdc-api`
   * **Region**: `Oregon (US West)` *(match database region)*
   * **Branch**: `main` (or your deployment branch)
   * **Runtime**: **Docker**
   * **Dockerfile Path**: `./services/api/Dockerfile`
   * **Docker Build Context**: `.` *(the workspace root)*
   * **Plan**: `Free` (or `Starter`)
4. Expand **Advanced** and configure:
   * **Health Check Path**: `/healthz`
5. Add the following **Environment Variables**:

| Key | Value | Notes |
| :--- | :--- | :--- |
| `DATABASE_URL` | `<Internal Database URL>` | Pasted from Step 3.1 (e.g. `postgres://...`). The API automatically normalizes `postgres://` to `postgresql://`. |
| `JWT_SECRET_KEY` | `<Secure Random String>` | Generate via: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `API_SYNC_BATCH_MAX` | `1000` | Maximum items processed per sync payload. |
| `CORS_ORIGINS` | `*` | In production, set to your static site URL(s) comma-separated. |

6. Click **Create Web Service**.
7. Once deployed, copy your backend's public URL:
   `https://<cdc-api-subdomain>.onrender.com`

---

### Step 3.3: Provision React Frontend Static Site (`cdc-frontend`)

1. Click **New +** > **Static Site**.
2. Connect your Git repository.
3. Configure site settings:
   * **Name**: `cdc-frontend`
   * **Branch**: `main` (or your deployment branch)
   * **Root Directory**: `frontend`
   * **Build Command**: `npm ci && npm run build`
   * **Publish Directory**: `dist`
4. Add **Environment Variables**:

| Key | Value | Notes |
| :--- | :--- | :--- |
| `VITE_API_BASE_URL` | `https://<cdc-api-subdomain>.onrender.com` | Public URL of `cdc-api` obtained in Step 3.2. **Must include `https://`**. |

5. Configure **Client-Side SPA Routing (Redirects / Rewrites)**:
   * Navigate to the **Redirects / Rewrites** tab in your static site dashboard.
   * Click **Add Rule**:
     * **Type**: `Rewrite`
     * **Source**: `/*`
     * **Destination**: `/index.html`
   * *Critical*: Without this rewrite rule, reloading pages like `/reports` or `/line-settings` will return HTTP 404 errors.
6. Click **Create Static Site**.

---

### Important: Vite Build-Time Environment Note

> **Note**: Vite embeds `import.meta.env` values at **compile time** when `npm run build` runs. If you change or update `VITE_API_BASE_URL` in Render, the changes will not take effect on the live website until you trigger a new build. Navigate to `cdc-frontend` > **Manual Deploy** > **Deploy latest commit** whenever modifying this variable.

---

## 4. Edge Node Configuration (`services/counter`)

Edge counter nodes run on-premise near the conveyor line and do not require inbound public IP addresses or firewall port forwarding. They only require outbound HTTPS access to your Render API.

### Endpoint Structure

The sync worker targets the `/api/v1/sync/batch` endpoint:
```
https://<cdc-api-subdomain>.onrender.com/api/v1/sync/batch
```

### Method 1: Environment File (`.env`)

On the edge device, create or edit `.env` in the project root:

```ini
# --- Conveyor Line Identity ---
LINE_ID=lineA

# --- Cloud Central API Endpoint ---
API_SYNC_URL=https://<cdc-api-subdomain>.onrender.com/api/v1/sync/batch
SYNC_INTERVAL_SEC=5.0

# --- Video Source Configuration ---
VIDEO_SOURCE_TYPE=rtsp
VIDEO_PATH=rtsp://192.168.1.100:554/stream1

# --- Detection Pipeline ---
DETECTOR_TYPE=shackle
CONF_THRESHOLD=0.7
```

Run the counter service:
```bash
python -m services.counter.main
```

---

### Method 2: CLI Arguments

You can pass the sync target and camera options directly via command-line arguments:

```bash
python -m services.counter.main \
  --line-id lineA \
  --source rtsp \
  --video rtsp://admin:password@192.168.1.100:554/h264Preview_01_main \
  --detector shackle \
  --api-sync-url https://<cdc-api-subdomain>.onrender.com/api/v1/sync/batch \
  --sync-interval 5.0
```

---

### Method 3: Edge Docker Container

If running the counter inside Docker at the facility:

```bash
docker run -d \
  --name cdc-counter-line-a \
  --restart unless-stopped \
  -e LINE_ID=lineA \
  -e API_SYNC_URL=https://<cdc-api-subdomain>.onrender.com/api/v1/sync/batch \
  -e SYNC_INTERVAL_SEC=5.0 \
  -e VIDEO_SOURCE_TYPE=rtsp \
  -e VIDEO_PATH="rtsp://192.168.1.100:554/stream1" \
  -v $(pwd)/data:/app/data \
  cdc-counter:latest
```

---

### Outbox Resilience & Offline Behavior

The edge service is designed for industrial fault tolerance:
1. **Local SQLite Persistence**: Every detection event is written immediately to `counter_outbox.db`.
2. **Background Dispatcher**: `OutboxSyncDispatcher` reads batches of unacknowledged records and posts them to `API_SYNC_URL`.
3. **Automatic Backoff & Reconnection**: If the internet connection is disrupted or Render is waking from sleep, counts are **never lost**. The worker backs off exponentially (up to 30s) and automatically flushes accumulated batches when the connection is restored.
4. **Log Verification**: On successful sync, the edge terminal logs:
   ```text
   Synced 48 items to cloud API (lineA)
   ```

---

## 5. Initial Login & Default Credentials

When `cdc-api` runs for the first time, its database migration and seeding routine automatically initializes tables and creates default user accounts.

### Default User Credentials

| Username | Password | Role | Description & Permissions |
| :--- | :--- | :--- | :--- |
| **`admin`** | `admin123` | `admin` | **System Administrator**: Full access to all dashboards, user management, production line calibrations, and alarm thresholds. |
| **`operator`** | `operator123` | `operator` | **Line Operator**: Access to live conveyor monitors, active alarms acknowledgement, and daily shift reports. |

### Default Production Lines

The initial seed creates two preconfigured conveyor lines:
* **`line-1`**: *Lini Konveyor 1* (Daily target: 62,000 birds)
* **`lineA`**: *Lini Konveyor A* (Daily target: 62,000 birds)

### Interactive API Documentation

You can test endpoints, inspect schemas, and verify authentication tokens directly using the built-in OpenAPI documentation:
* **Swagger UI**: `https://<cdc-api-subdomain>.onrender.com/docs`
* **ReDoc**: `https://<cdc-api-subdomain>.onrender.com/redoc`

> **Security Notice**: Change the default passwords immediately upon production deployment using the User Management interface or the `PUT /api/v1/auth/users/{user_id}/password` endpoint.

---

## 6. Production & Free Tier Notes

### Understanding Render Free Tier Behavior

If you deploy using Render's Free tier, be aware of the following operational characteristics:

1. **Service Sleep (Spindown)**:
   * Free Web Services automatically spin down after **15 minutes of inactivity** (zero incoming HTTP requests).
2. **Cold Start Latency**:
   * The first request that hits a sleeping service triggers a container cold start. It typically takes **~50 seconds** for the backend to become responsive.
   * During this cold start window, the React frontend might display a loading state, and edge nodes will retry sync requests according to their backoff strategy.
3. **PostgreSQL Expiration**:
   * Render Free PostgreSQL databases expire **30 days** after creation.
4. **Static Sites**:
   * Static sites (`cdc-frontend`) are distributed globally via Render CDN and **never spin down**.

---

### Recommendations for Production

For production poultry processing plants operating continuous shifts:

1. **Upgrade Web Service to Starter Plan ($7/month)**:
   * Keeps `cdc-api` always-on (zero cold starts, no sleeping).
   * Ensures instant sync reception from edge nodes and reliable WebSocket broadcast to dashboard users.
2. **Upgrade PostgreSQL to Starter Plan ($7/month)**:
   * Provides persistent data storage without 30-day expiration.
   * Includes automated daily backups and 1 GB+ RAM.
3. **Hardened CORS Configuration**:
   * In development or initial testing, `CORS_ORIGINS=*` is acceptable.
   * In production, restrict CORS to your actual frontend domain(s) in `cdc-api` settings:
     ```ini
     CORS_ORIGINS=https://cdc-frontend.onrender.com,https://poultry.lihat.id
     ```

---

### Free Tier Keep-Alive Workaround (Pilot Testing)

If you wish to keep the backend warm on the Free tier during pilot evaluation:
* Set up a free external uptime monitor (e.g., [UptimeRobot](https://uptimerobot.com), [Cron-job.org](https://cron-job.org), or [BetterStack](https://betterstack.com)).
* Configure an HTTP `GET` check targeting your health endpoint every **10 minutes**:
  ```text
  GET https://<cdc-api-subdomain>.onrender.com/healthz
  ```
* This prevents Render from putting the Web Service to sleep.

---

## 7. Troubleshooting & Verification

### Checklist: Verifying Your Deployment

| Step | Action | Expected Result |
| :--- | :--- | :--- |
| **1. API Healthcheck** | `curl -i https://<cdc-api-subdomain>.onrender.com/healthz` | `HTTP/2 200` with `{"status":"ok"}` |
| **2. API Docs** | Open `https://<cdc-api-subdomain>.onrender.com/docs` in browser | Interactive Swagger UI displays all endpoints |
| **3. Frontend CDN** | Open `https://<cdc-frontend-subdomain>.onrender.com` | Login page loads cleanly with logo |
| **4. Auth Test** | Log in with `admin` / `admin123` | Redirects to Dashboard with real-time stats |
| **5. SPA Refresh** | Navigate to `/reports` and press `Ctrl+R` (Reload) | Page reloads without 404 error |

---

### Common Issues and Solutions

#### Problem 1: Frontend displays "Network Error" or cannot reach API
* **Cause**: `VITE_API_BASE_URL` is unset, missing the `https://` protocol prefix, or pointed to the wrong hostname.
* **Solution**:
  1. Go to `cdc-frontend` > **Environment** in Render.
  2. Verify `VITE_API_BASE_URL` is set to `https://<cdc-api-subdomain>.onrender.com` (do not add trailing slash).
  3. Go to **Manual Deploy** > **Deploy latest commit** to recompile the Vite bundle with the new URL.

#### Problem 2: Reloading subpages returns "404 Not Found"
* **Cause**: Render Static Site does not know how to handle client-side React Router paths on hard refreshes.
* **Solution**:
  1. Open `cdc-frontend` > **Redirects / Rewrites**.
  2. Verify an entry exists with:
     * **Type**: `Rewrite`
     * **Source**: `/*`
     * **Destination**: `/index.html`
  3. Save changes.

#### Problem 3: Backend deployment logs show `DATABASE_URL` error
* **Cause**: SQLAlchemy rejecting `postgres://` or attempting to connect across regions over external IP.
* **Solution**:
  1. Ensure you used the **Internal Database URL** provided by Render PostgreSQL (not the External URL).
  2. The code in `services/api/src/db/session.py` automatically normalizes `postgres://` to `postgresql://` and selects the `psycopg2` / `psycopg` driver. If providing a custom URL manually, ensure it uses `postgresql://` or `postgresql+psycopg2://`.

#### Problem 4: Edge counter logs `httpx.ConnectTimeout`
* **Cause**: The cloud backend on Free tier is cold-starting (~50s).
* **Solution**: No action needed. The edge outbox dispatcher will hold count events in SQLite and automatically retry with exponential backoff until the backend wakes up.

#### Problem 5: Checking Logs in Render
* To view live stdout/stderr streams for troubleshooting:
  1. In the Render Dashboard, open `cdc-api` or `cdc-frontend`.
  2. Click the **Logs** tab on the left navigation menu.
  3. Use the search bar to filter by keywords such as `ERROR`, `POST /api/v1/sync/batch`, or `lifespan`.
