# Design Specification: Render Cloud Deployment

- **Author**: AI Assistant & User
- **Date**: 2026-10-19
- **Status**: Approved
- **Topic**: Deploying Poultry Counter API, Database, and Frontend to Render Cloud Hosting

---

## 1. Context & Objectives

The Poultry Counter system consists of:
1. An on-premise edge computer vision counter service (`services/counter`) capturing and counting broiler chickens over conveyor lines.
2. A central FastAPI backend (`services/api`) aggregating data, managing configurations, handling authentication, and serving reporting.
3. A React Vite SPA frontend (`frontend/`) providing real-time dashboards and administration.
4. A persistent relational database (`PostgreSQL`).

The goal is to deploy the cloud-accessible tiers (PostgreSQL database, FastAPI backend, and React frontend) to Render cloud hosting using a declarative Blueprint (`render.yaml`) and clear deployment documentation, while edge nodes continue syncing batches to the cloud API.

---

## 2. Architecture & Cloud Services

### Render Component Breakdown
1. **Managed Database (`cdc-postgres`)**:
   - **Type**: Render Managed PostgreSQL (Free or Starter tier).
   - **Database Name**: `chicken_counting`.
   - **User**: `postgres` (or Render default).
   - **Access**: Internal connection string injected into `cdc-api` as `DATABASE_URL`.

2. **Central Backend Service (`cdc-api`)**:
   - **Type**: Web Service (`env: docker`).
   - **Docker Context**: `.` (root directory).
   - **Dockerfile Path**: `./services/api/Dockerfile`.
   - **Port Configuration**: Dynamic port passed via `${PORT:-8070}`.
   - **Environment Variables**:
     - `DATABASE_URL`: Injected from `cdc-postgres` via `fromDatabase`.
     - `JWT_SECRET_KEY`: Automatically generated random secret string.
     - `API_SYNC_BATCH_MAX`: `1000`.
     - `CORS_ORIGINS`: Comma-separated list or `*`.

3. **Web Dashboard (`cdc-frontend`)**:
   - **Type**: Static Site (`env: static`).
   - **Root Directory**: `frontend`.
   - **Build Command**: `npm ci && npm run build`.
   - **Publish Directory**: `dist`.
   - **Routing / Rewrites**: SPA rewrite rule mapping `/*` to `/index.html`.
   - **Environment Variables**:
     - `VITE_API_BASE_URL`: Public URL of `cdc-api` (e.g. `https://cdc-api.onrender.com`).

4. **Edge Counter Integration**:
   - The on-premise counter node (`services/counter`) connects to Render over public HTTPS:
     `API_SYNC_URL=https://<cdc-api-subdomain>.onrender.com/api/v1/sync/batch`.

---

## 3. Codebase Changes

### 3.1 Database Connection Normalization (`services/api/src/db/session.py`)
- Render injects PostgreSQL URLs using the `postgres://` or `postgresql://` URI scheme.
- SQLAlchemy 2.0 requires `postgresql://` or explicit driver notation (`postgresql+psycopg2://` / `postgresql+psycopg://`).
- In `services/api/src/db/session.py`, normalize `postgres://` to `postgresql://` before dialect detection.

### 3.2 Dynamic CORS Origins (`services/api/src/main.py`)
- Support `CORS_ORIGINS` environment variable (comma-delimited) while keeping wildcard fallback `*` enabled for initial bootstrapping.

### 3.3 Render Blueprint Definition (`render.yaml`)
- Declare the database (`cdc-postgres`), backend web service (`cdc-api`), and frontend static site (`cdc-frontend`) in a single blueprint file.
- Configure automatic SPA routing rules for `cdc-frontend`.

### 3.4 Deployment Guide (`docs/deployment-render.md`)
- Step-by-step instructions for:
  - 1-Click deployment using Render Blueprints.
  - Manual deployment via the Render Dashboard.
  - Setting up custom domains and CORS.
  - Edge counter configuration and sample syncing.
  - Handling free tier dormancy / cold starts.

---

## 4. Verification & Testing Strategy
- Unit test database URL normalization with `postgres://` and `postgresql://` formats.
- Validate `render.yaml` schema syntax against Render Blueprint specifications.
- Verify frontend build pipeline (`npm run build`) works cleanly in isolation.
- Confirm FastAPI startup and healthcheck (`/healthz`) succeed.
