# Edge API Key Authentication System Design

**Date:** 2026-10-19  
**Status:** Approved  
**Topic:** Edge Counter API Key Authentication for Central API Line Configuration and Ingestion

---

## 1. Overview & Problem Statement

### 1.1 Problem Statement
When running the edge counter service (`services/counter/main.py`), the service attempts to pull remote line configuration from the central API at startup via `fetch_remote_line_config()`, querying `GET /api/v1/lines/{line_id}`.

Because the central API protects `GET /api/v1/lines/{line_id}` with user JWT authentication (`current_user = Depends(get_current_user)`), unauthenticated requests from the counter service are rejected with `HTTP 401 Unauthorized`:
```text
[WARNING] counter.service: Remote line config returned HTTP 401 for line line-1
```
While the counter service gracefully falls back to local CLI/environment parameters, it prevents edge devices from dynamically adopting remote conveyor coordinates (`line_coords`), camera stream URLs (`video_url`), and counting directions (`line_direction`) configured in the central web dashboard. Furthermore, edge devices lack a dedicated long-lived authentication mechanism suited for industrial 24/7 OT environments where user JWT tokens expire after 24 hours.

### 1.2 Proposed Solution
Implement a persistent **API Key Authentication** subsystem:
1. **Database-backed API Key Storage (`api_keys` table)**: Securely stores SHA-256 hashed API keys with descriptive metadata, display prefix, active status, role, and usage timestamps.
2. **Dual-Authentication in Central API**: Enhance `get_current_user` to accept both standard user JWT Bearer tokens and API Keys (via `Authorization: Bearer cdc_live_...` or `X-API-Key: cdc_live_...`).
3. **Admin Management & CLI Generator**:
   - REST endpoints (`POST /api/v1/auth/api-keys`, `GET /api/v1/auth/api-keys`, `DELETE /api/v1/auth/api-keys/{id}`) restricted to admins.
   - Command-line interface (`python -m services.api.src.cli create-api-key --name "Line 1 Edge"`) for initial server setup and headless deployments.
4. **Edge Counter Integration**: Add `API_TOKEN` / `--api-token` support to `services/counter` for both startup remote configuration retrieval and batch sync dispatching.

---

## 2. Architecture & Data Flow

```text
+-------------------------------------------------------------+
|                     Edge Counter Device                     |
|                                                             |
|  .env / CLI: API_TOKEN=cdc_live_9f83...                     |
|                                                             |
|  1. Startup: fetch_remote_line_config()                     |
|     GET /api/v1/lines/{line_id}                             |
|     Headers: { Authorization: "Bearer cdc_live_9f83..." }   |
|                                                             |
|  2. Dispatch: OutboxSyncDispatcher                          |
|     POST /api/v1/sync/batch                                 |
|     Headers: { Authorization: "Bearer cdc_live_9f83..." }   |
+------------------------------+------------------------------+
                               |
                               | HTTPS
                               v
+-------------------------------------------------------------+
|                      Central FastAPI API                    |
|                                                             |
|  Dependency: get_current_user()                             |
|  Check token:                                               |
|    - If JWT: verify & decode claims                         |
|    - If "cdc_live_...":                                     |
|        sha256(key) -> query api_keys table                  |
|        verify is_active == True                             |
|        update last_used_at                                  |
|        return UserDTO(id=key.id, username=f"device:{name}") |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                     PostgreSQL Database                     |
|                                                             |
|  Table: api_keys                                            |
|    - id, name, key_hash, prefix, role, is_active, ...       |
+-------------------------------------------------------------+
```

---

## 3. Detailed Specifications

### 3.1 Database Schema (`services/api/src/db/models.py`)

New SQLAlchemy model `ApiKey`:
- **Table Name:** `api_keys`
- **Fields:**
  - `id`: `Mapped[int]` - Primary Key, Autoincrement.
  - `name`: `Mapped[str]` - `String(100)`, non-nullable. Human-readable description (e.g. `"Line 1 Edge Counter"`).
  - `key_hash`: `Mapped[str]` - `String(64)`, indexed, unique, non-nullable. Hex-encoded SHA-256 hash of the full plaintext key.
  - `prefix`: `Mapped[str]` - `String(16)`, non-nullable. First 12 characters of the key for display/auditing (e.g. `"cdc_live_a1b2"`).
  - `role`: `Mapped[str]` - `String(20)`, default `"OPERATOR"`. Allows permission evaluation across standard endpoints.
  - `is_active`: `Mapped[bool]` - `Boolean`, default `True`. Soft-revocation flag.
  - `created_at`: `Mapped[datetime]` - `DateTime`, default `utcnow`.
  - `last_used_at`: `Mapped[datetime | None]` - `DateTime`, nullable. Updated on successful authentication.

### 3.2 Key Generation & Format (`services/api/src/services/auth.py`)
- **Key Prefix:** `cdc_live_`
- **Entropy:** 32 random bytes (64 hex characters) generated via Python standard library `secrets.token_hex(32)`.
- **Full Key Length:** `9 + 64 = 73` characters (e.g., `cdc_live_3f9b2d8e41a...`).
- **Helper Functions:**
  - `generate_api_key() -> tuple[str, str, str]`: Returns `(raw_key, key_hash, prefix)`.
  - `hash_api_key(raw_key: str) -> str`: Returns `hashlib.sha256(raw_key.encode("utf-8")).hexdigest()`.

### 3.3 Central API Authentication Integration (`services/api/src/api/auth.py`)
Enhance `get_current_user` to inspect incoming credentials:
1. Accept credentials from:
   - Header `Authorization: Bearer <token_or_key>`
   - Header `X-API-Key: <key>`
2. Detection & Branching:
   - If token starts with `cdc_live_`:
     - Compute `key_hash = hash_api_key(token)`.
     - Query `db.scalars(select(ApiKey).where(ApiKey.key_hash == key_hash)).first()`.
     - If not found or `not key.is_active`: raise `HTTPException(401, detail="Invalid or revoked API key")`.
     - Update `key.last_used_at = datetime.now(timezone.utc)` and commit.
     - Return `UserDTO(id=key.id, username=f"device:{key.name}", role=key.role, is_active=key.is_active)`.
   - Otherwise, proceed with existing JWT validation (`decode_access_token`).

### 3.4 REST Endpoints (`services/api/src/api/auth.py`)
Endpoints protected by `Depends(require_role(["admin"]))`:
1. `POST /api/v1/auth/api-keys`:
   - Request Body: `{"name": "Edge Counter Line 1", "role": "OPERATOR"}`
   - Response: `{"id": 1, "name": "...", "api_key": "cdc_live_...", "prefix": "cdc_live_...", "created_at": "..."}`
   - *Note:* The full `api_key` is returned **only once** upon creation.
2. `GET /api/v1/auth/api-keys`:
   - Response: `list[ApiKeyListItem]` (`id`, `name`, `prefix`, `role`, `is_active`, `created_at`, `last_used_at`).
3. `DELETE /api/v1/auth/api-keys/{key_id}`:
   - Deactivates or removes the API key by ID.
   - Response: `{"detail": "API key revoked successfully"}`.

### 3.5 Central CLI Tool (`services/api/src/cli.py`)
Provide an administrative CLI entrypoint:
```bash
python -m services.api.src.cli create-api-key --name "Line 1 Counter" --role OPERATOR
```
Outputs the newly generated key directly to stdout for immediate copying into the edge device's `.env`.

### 3.6 Edge Counter Integration (`services/counter`)
1. **CLI & Environment Options (`services/counter/main.py`)**:
   - Argument: `--api-token` / `--api-key`
   - Environment variable: `API_TOKEN` (or `API_KEY`)
2. **Remote Config Fetching (`fetch_remote_line_config`)**:
   - Signature: `fetch_remote_line_config(api_sync_url: str, line_id: str, timeout: float = 3.0, api_token: str | None = None) -> dict | None`
   - If `api_token` is provided, set header `headers = {"Authorization": f"Bearer {api_token}"}`.
   - If HTTP 401 is received, output helpful guidance in logger:
     ```text
     [WARNING] counter.service: Remote line config returned HTTP 401 for line line-1. Check API_TOKEN configuration.
     ```
3. **Outbox Batch Sync (`services/counter/src/sync/dispatcher.py`)**:
   - Accept optional `api_token: str | None = None`.
   - Include `Authorization: Bearer <api_token>` on `POST /api/v1/sync/batch` requests when provided.
4. **Manifests & Config Files**:
   - `.env.counter.example`: Add `API_TOKEN=` documentation.
   - `docker-compose.counter.yml`: Add `API_TOKEN: ${API_TOKEN:-}`.

---

## 4. Error Handling & Edge Cases

1. **Missing or Empty Token**:
   - If `API_TOKEN` is unset, `fetch_remote_line_config` still attempts unauthenticated GET. If the endpoint requires auth, it logs the 401 and falls back to local configuration without crashing.
2. **Invalid or Revoked API Key**:
   - Central API returns `401 Unauthorized` (`{"detail": "Invalid or revoked API key"}`).
   - Edge counter catches the 401, logs a warning with troubleshooting context, and falls back to local parameters.
3. **Timing Attacks**:
   - Storing and querying by fixed-length SHA-256 hash avoids plaintext leaks and limits timing discrepancy vectors.
4. **Database Migration / Table Auto-creation**:
   - `init_db()` in `services/api/src/db/session.py` calls `Base.metadata.create_all(bind=engine)`, ensuring `api_keys` table is automatically provisioned on startup.

---

## 5. Testing & Verification Plan

1. **API Key Generation & Hash Unit Tests (`test_auth_service.py`)**:
   - Verify `generate_api_key()` format (`cdc_live_` prefix and 73 chars length).
   - Verify SHA-256 hashing consistency.
2. **API Key Management Endpoints (`test_api_keys.py`)**:
   - Admin can create, list, and delete API keys.
   - Non-admin (operator) receives 403 Forbidden.
   - Unauthenticated user receives 401 Unauthorized.
3. **Dual-Auth Authentication Verification (`test_api_keys.py`)**:
   - Request `GET /api/v1/lines/line-1` with `Authorization: Bearer <api_key>` -> returns 200 OK.
   - Request with `X-API-Key: <api_key>` -> returns 200 OK.
   - Request with revoked key -> returns 401 Unauthorized.
   - Request with invalid key -> returns 401 Unauthorized.
   - Successful call updates `last_used_at`.
4. **CLI Creation Command (`test_api_cli.py`)**:
   - Test `create-api-key` creates active record in DB and outputs valid key to stdout.
5. **Counter Remote Config with Token (`test_remote_config.py`)**:
   - Verify `fetch_remote_line_config` sends `Authorization: Bearer <api_token>` header.
   - Verify successful retrieval applies remote config without HTTP 401 warning.
6. **Full Test Suite Regression**:
   - Run all 287 existing Python tests to ensure zero regressions.
