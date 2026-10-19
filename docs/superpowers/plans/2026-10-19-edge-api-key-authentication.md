# Edge API Key Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement persistent database-backed API Key authentication for the central API and integrate token authentication into the edge counter service to resolve HTTP 401 warnings when retrieving remote line configuration.

**Architecture:** A new `ApiKey` model in PostgreSQL/SQLite stores SHA-256 hashed keys generated with a `cdc_live_` prefix. The central FastAPI `get_current_user` dependency is upgraded to dual-auth (supporting both user JWT and API Keys). Admin endpoints and a CLI script allow provisioning keys. The edge counter service receives `API_TOKEN` / `--api-token` to authenticate both startup line configuration requests and outbox telemetry dispatches.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0, Pydantic v2, HTTPX, SQLite / PostgreSQL, Pytest.

## Global Constraints

- Full API Key format: `cdc_live_<64-hex-chars>` (total length: 73 characters).
- Storage: SHA-256 hash (`key_hash`) stored in DB; plaintext key returned once only upon creation.
- Dual-auth: Support both `Authorization: Bearer <token_or_key>` and `X-API-Key: <key>`.
- Edge Counter: Zero breaking changes when `API_TOKEN` is unset (preserves offline/local fallback).
- Backward Compatibility: Existing user JWT authentication and all existing tests must pass with 100% pass rate.

---

### Task 1: Database Model & API Key Generation Utilities

**Files:**
- Create: `services/api/tests/test_api_key_service.py`
- Modify: `services/api/src/db/models.py:100-115`
- Modify: `services/api/src/services/auth.py:40-60`

**Interfaces:**
- Produces: `ApiKey` model in `services.api.src.db.models`
- Produces: `generate_api_key() -> tuple[str, str, str]` (raw_key, key_hash, prefix) in `services.api.src.services.auth`
- Produces: `hash_api_key(raw_key: str) -> str` in `services.api.src.services.auth`

- [ ] **Step 1: Write failing unit test for ApiKey model and generator**

`services/api/tests/test_api_key_service.py`:
```python
from services.api.src.services.auth import generate_api_key, hash_api_key
from services.api.src.db.models import ApiKey


def test_generate_api_key_format():
    raw_key, key_hash, prefix = generate_api_key()
    assert raw_key.startswith("cdc_live_")
    assert len(raw_key) == 73
    assert len(key_hash) == 64
    assert prefix == raw_key[:16]
    assert hash_api_key(raw_key) == key_hash


def test_api_key_model_attributes():
    raw_key, key_hash, prefix = generate_api_key()
    key_obj = ApiKey(
        name="Line 1 Counter",
        key_hash=key_hash,
        prefix=prefix,
        role="OPERATOR",
    )
    assert key_obj.name == "Line 1 Counter"
    assert key_obj.key_hash == key_hash
    assert key_obj.prefix == prefix
    assert key_obj.role == "OPERATOR"
    assert key_obj.is_active is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest services/api/tests/test_api_key_service.py -v`  
Expected: FAIL with `ImportError: cannot import name 'generate_api_key' from 'services.api.src.services.auth'`

- [ ] **Step 3: Implement ApiKey model and generation functions**

In `services/api/src/db/models.py`:
```python
class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="OPERATOR")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

    def __repr__(self) -> str:
        return f"<ApiKey(id={self.id}, name='{self.name}', prefix='{self.prefix}', role='{self.role}', active={self.is_active})>"
```

In `services/api/src/services/auth.py`:
```python
def hash_api_key(raw_key: str) -> str:
    """Return SHA-256 hex digest of a raw API key."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Generate a high-entropy API key.
    Returns: (raw_key, key_hash, prefix)
    """
    token_hex = secrets.token_hex(32)
    raw_key = f"cdc_live_{token_hex}"
    key_hash = hash_api_key(raw_key)
    prefix = raw_key[:16]
    return raw_key, key_hash, prefix
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest services/api/tests/test_api_key_service.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/api/src/db/models.py services/api/src/services/auth.py services/api/tests/test_api_key_service.py
git commit -m "feat(api): add ApiKey database model and key generation utilities"
```

---

### Task 2: Dual-Auth Integration & API Key Management Endpoints

**Files:**
- Create: `services/api/tests/test_api_keys.py`
- Modify: `services/api/src/api/auth.py:40-100`

**Interfaces:**
- Consumes: `ApiKey`, `generate_api_key`, `hash_api_key` from Task 1
- Produces: Dual-auth support in `get_current_user`
- Produces: REST endpoints `POST /api/v1/auth/api-keys`, `GET /api/v1/auth/api-keys`, `DELETE /api/v1/auth/api-keys/{id}`

- [ ] **Step 1: Write failing tests for API key management and dual-auth**

`services/api/tests/test_api_keys.py`:
```python
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from services.api.src.main import app
from services.api.src.db.session import get_db
from services.api.src.services.auth import create_access_token


@pytest.fixture
def api_client(test_db):
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_api_key_crud_lifecycle(api_client):
    admin_token = create_access_token({"sub": "admin", "role": "admin"})
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Create API Key
    create_resp = api_client.post(
        "/api/v1/auth/api-keys",
        json={"name": "Line 1 Edge", "role": "OPERATOR"},
        headers=admin_headers,
    )
    assert create_resp.status_code == 201
    data = create_resp.json()
    assert data["name"] == "Line 1 Edge"
    assert data["api_key"].startswith("cdc_live_")
    key_id = data["id"]
    api_key = data["api_key"]

    # 2. List API Keys
    list_resp = api_client.get("/api/v1/auth/api-keys", headers=admin_headers)
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert any(k["id"] == key_id for k in items)
    # Ensure raw api_key is not exposed in list
    assert "api_key" not in items[0]

    # 3. Authenticate with Bearer API Key
    auth_resp = api_client.get(
        "/api/v1/lines/line-1",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    assert auth_resp.status_code == 200
    assert auth_resp.json()["id"] == "line-1"

    # 4. Authenticate with X-API-Key Header
    header_resp = api_client.get(
        "/api/v1/lines/line-1",
        headers={"X-API-Key": api_key},
    )
    assert header_resp.status_code == 200

    # 5. Revoke API Key
    del_resp = api_client.delete(f"/api/v1/auth/api-keys/{key_id}", headers=admin_headers)
    assert del_resp.status_code == 200

    # 6. Verify revoked key returns 401
    revoked_resp = api_client.get(
        "/api/v1/lines/line-1",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    assert revoked_resp.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest services/api/tests/test_api_keys.py -v`  
Expected: FAIL with 404 Not Found on `/api/v1/auth/api-keys`

- [ ] **Step 3: Implement dual-auth and API key management routes**

In `services/api/src/api/auth.py`:
- Add request and response DTO schemas:
```python
class ApiKeyCreateRequest(BaseModel):
    name: str
    role: str = "OPERATOR"


class ApiKeyCreateResponse(BaseModel):
    id: int
    name: str
    api_key: str
    prefix: str
    role: str
    created_at: datetime


class ApiKeyResponse(BaseModel):
    id: int
    name: str
    prefix: str
    role: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None
```
- Update `get_current_user` to inspect `authorization: Optional[str] = Header(None)` and `x_api_key: Optional[str] = Header(None, alias="X-API-Key")`:
  - If `x_api_key` or `authorization.startswith("Bearer cdc_live_")`:
    - Extract `raw_key`, compute `key_hash = hash_api_key(raw_key)`.
    - Query `ApiKey` from DB.
    - If missing or `not key.is_active`: raise `HTTPException(401, detail="Invalid or revoked API key")`.
    - Update `key.last_used_at = datetime.now(timezone.utc)`, commit to DB.
    - Return `UserDTO(id=key.id, username=f"device:{key.name}", role=key.role, is_active=key.is_active)`.
- Implement router endpoints:
  - `@router.post("/api-keys", response_model=ApiKeyCreateResponse, status_code=201)` (guarded by `require_role(["admin"])`).
  - `@router.get("/api-keys", response_model=list[ApiKeyResponse])` (guarded by `require_role(["admin"])`).
  - `@router.delete("/api-keys/{key_id}")` (guarded by `require_role(["admin"])`).

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest services/api/tests/test_api_keys.py -v`  
Expected: PASS

- [ ] **Step 5: Run existing auth test suite to ensure no regressions**

Run: `py -m pytest services/api/tests/test_auth_api.py services/api/tests/test_rbac_api.py -v`  
Expected: PASS (all tests pass)

- [ ] **Step 6: Commit**

```bash
git add services/api/src/api/auth.py services/api/tests/test_api_keys.py
git commit -m "feat(api): implement dual-auth and api key management endpoints"
```

---

### Task 3: Backend Administrative CLI for API Key Generation

**Files:**
- Create: `services/api/src/cli.py`
- Create: `services/api/tests/test_api_cli.py`

**Interfaces:**
- Consumes: `ApiKey`, `generate_api_key`, `get_db` / `SessionLocal`
- Produces: CLI script runnable via `python -m services.api.src.cli create-api-key --name <name> --role <role>`

- [ ] **Step 1: Write failing test for administrative CLI**

`services/api/tests/test_api_cli.py`:
```python
import subprocess
import sys


def test_cli_create_api_key():
    cmd = [
        sys.executable,
        "-m",
        "services.api.src.cli",
        "create-api-key",
        "--name",
        "CLI Test Key",
        "--role",
        "OPERATOR",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    output = res.stdout
    assert "cdc_live_" in output
    assert "API Key created successfully" in output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest services/api/tests/test_api_cli.py -v`  
Expected: FAIL with `No module named services.api.src.cli`

- [ ] **Step 3: Implement CLI module**

`services/api/src/cli.py`:
```python
import argparse
import sys
from services.api.src.db.session import SessionLocal, init_db
from services.api.src.db.models import ApiKey
from services.api.src.services.auth import generate_api_key


def create_api_key_cmd(name: str, role: str) -> str:
    init_db()
    raw_key, key_hash, prefix = generate_api_key()
    with SessionLocal() as db:
        key_record = ApiKey(
            name=name,
            key_hash=key_hash,
            prefix=prefix,
            role=role.upper(),
            is_active=True,
        )
        db.add(key_record)
        db.commit()
        db.refresh(key_record)
        return raw_key


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Lihat.id Poultry Counter Central API Admin CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create-api-key", help="Create a persistent API key for edge devices")
    create_parser.add_argument("--name", required=True, help="Descriptive name of the device/key (e.g. 'Line 1 Edge')")
    create_parser.add_argument("--role", default="OPERATOR", choices=["OPERATOR", "ADMIN"], help="Role assigned to this key")

    args = parser.parse_args(argv)
    if args.command == "create-api-key":
        key = create_api_key_cmd(args.name, args.role)
        print(f"API Key created successfully for '{args.name}' [{args.role}]:")
        print(f"  {key}")
        print("Store this key securely in the edge device's .env file as API_TOKEN.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest services/api/tests/test_api_cli.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/api/src/cli.py services/api/tests/test_api_cli.py
git commit -m "feat(api): add admin cli for edge device api key creation"
```

---

### Task 4: Edge Counter Integration with API Token Authentication

**Files:**
- Modify: `services/counter/main.py:830-845, 905-970`
- Modify: `services/counter/src/sync/dispatcher.py:20-75`
- Modify: `.env.counter.example`
- Modify: `docker-compose.counter.yml`
- Modify: `services/counter/tests/test_remote_config.py`

**Interfaces:**
- Consumes: Central API dual-auth supporting `Authorization: Bearer <token_or_key>`
- Produces: `fetch_remote_line_config(..., api_token: str | None = None)`
- Produces: CLI `--api-token` and env `API_TOKEN` / `API_KEY` in `services.counter.main`

- [ ] **Step 1: Write failing test in counter test suite**

In `services/counter/tests/test_remote_config.py`:
```python
def test_fetch_remote_config_with_api_token():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "line-1",
        "video_url": "rtsp://camera1/stream",
        "line_coords": "0,240,640,240",
        "line_direction": "right",
    }

    with patch("httpx.get", return_value=mock_resp) as mock_get:
        config = fetch_remote_line_config(
            api_sync_url="http://central-api:8000/api/v1/sync/batch",
            line_id="line-1",
            api_token="cdc_live_test_token_123",
        )
        assert config is not None
        assert config["video_url"] == "rtsp://camera1/stream"
        mock_get.assert_called_once_with(
            "http://central-api:8000/api/v1/lines/line-1",
            timeout=3.0,
            headers={"Authorization": "Bearer cdc_live_test_token_123"},
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest services/counter/tests/test_remote_config.py -k test_fetch_remote_config_with_api_token -v`  
Expected: FAIL with `TypeError: fetch_remote_line_config() got an unexpected keyword argument 'api_token'`

- [ ] **Step 3: Update `fetch_remote_line_config` and CLI in `services/counter/main.py`**

1. In `fetch_remote_line_config`:
```python
def fetch_remote_line_config(
    api_sync_url: str,
    line_id: str,
    timeout: float = 3.0,
    api_token: str | None = None,
) -> dict | None:
    try:
        import httpx
        if "/api/v1/" in api_sync_url:
            base_api = api_sync_url.split("/api/v1/")[0] + "/api/v1"
        elif api_sync_url.rstrip("/").endswith("/api/v1"):
            base_api = api_sync_url.rstrip("/")
        else:
            base_api = f"{api_sync_url.rstrip('/')}/api/v1"

        target_url = f"{base_api}/lines/{line_id}"
        headers = {}
        if api_token:
            headers["Authorization"] = f"Bearer {api_token.strip()}"

        resp = httpx.get(target_url, timeout=timeout, headers=headers)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 401:
            logger.warning(
                "Remote line config returned HTTP 401 (Unauthorized) for line %s. "
                "Check that API_TOKEN or API_KEY is set in your environment. "
                "Falling back to local configuration.",
                line_id,
            )
        else:
            logger.warning("Remote line config returned HTTP %s for line %s", resp.status_code, line_id)
        return None
    except Exception as exc:
        logger.info("Could not fetch remote line config (%s). Using local parameters.", exc)
        return None
```
2. In `parse_args()` add:
```python
    parser.add_argument(
        "--api-token",
        "--api-key",
        default=os.getenv("API_TOKEN") or os.getenv("API_KEY") or "",
        help="API token or key for authenticating with central cloud API",
    )
```
3. In `main()` pass `api_token=args.api_token`:
```python
    if enable_sync and args.api_sync_url:
        logger.info("Attempting to fetch remote line configuration for %s from %s...", args.line_id, args.api_sync_url)
        remote_config = fetch_remote_line_config(args.api_sync_url, args.line_id, api_token=args.api_token)
```
4. Update `OutboxSyncDispatcher` in `services/counter/src/sync/dispatcher.py` to accept optional `api_token: str | None = None` and include `Authorization` header when posting to `api_url`.
5. Update `.env.counter.example` and `docker-compose.counter.yml` to include `API_TOKEN`.

- [ ] **Step 4: Run counter unit tests**

Run: `py -m pytest services/counter/tests/test_remote_config.py services/counter/tests/test_compose_counter.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/counter/main.py services/counter/src/sync/dispatcher.py .env.counter.example docker-compose.counter.yml services/counter/tests/test_remote_config.py
git commit -m "feat(counter): authenticate remote line config requests with api token"
```

---

### Task 5: Full Regression Testing & Documentation

**Files:**
- Modify: `docs/deployment-counter-dokploy-docker.md`
- Modify: `services/counter/README.md`

- [ ] **Step 1: Run full backend test suite**

Run: `py -m pytest services/api/tests/ -v`  
Expected: 181+ passed, 0 failed.

- [ ] **Step 2: Run full counter test suite**

Run: `py -m pytest services/counter/tests/ -v`  
Expected: 99+ passed, 0 failed.

- [ ] **Step 3: Run shared test suite**

Run: `py -m pytest tests/shared/ -v`  
Expected: 10+ passed, 0 failed.

- [ ] **Step 4: Update deployment guides and README**

In `docs/deployment-counter-dokploy-docker.md` and `services/counter/README.md`:
- Document `API_TOKEN` parameter in Configuration Reference tables.
- Add instructions on generating a key via `python -m services.api.src.cli create-api-key` or `POST /api/v1/auth/api-keys`.
- Document how adding `API_TOKEN` eliminates the HTTP 401 warning and enables remote line sync from cloud dashboard.

- [ ] **Step 5: Commit**

```bash
git add docs/deployment-counter-dokploy-docker.md services/counter/README.md
git commit -m "docs: document api key creation and edge counter authentication"
```
