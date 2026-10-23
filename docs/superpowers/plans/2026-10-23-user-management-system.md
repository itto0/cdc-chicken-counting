# User Management System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete full-stack User Management feature with backend CRUD endpoints under `/api/v1/auth/users`, self-service password changing under `/api/v1/auth/password`, admin sidebar navigation `/pengguna`, and security invariants protecting against self-deletion and last-admin lockouts.

**Architecture:** Extend FastAPI authentication router in `services/api/src/api/auth.py` with Pydantic request/response models and SQLite query logic enforcing safety rules; create a modular frontend feature `frontend/src/features/users/` (types, API client, modal dialogs, KPI cards, filterable table, and management page) and integrate into `Header.tsx`, `navigation.ts`, and `router.tsx`.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, SQLite, pytest, React 19, TypeScript, Tailwind CSS, Lucide React, Vite.

## Global Constraints

- Backend base endpoints: `/api/v1/auth/users` for admin user management, `/api/v1/auth/password` for self-service password updates.
- Invariant 1: Admin cannot delete their own account (`400 Bad Request` with detail `"Cannot delete own account"`).
- Invariant 2: Admin cannot deactivate their own account (`400 Bad Request` with detail `"Cannot deactivate own account"`).
- Invariant 3: Cannot deactivate or demote the last remaining active admin (`400 Bad Request` with detail `"Cannot deactivate or demote the last remaining active admin"`).
- Invariant 4: Cannot delete the last remaining active admin (`400 Bad Request` with detail `"Cannot delete the last remaining active admin"`).
- Invariant 5: Username must be unique across all users (`400 Bad Request` with detail `"Username already exists"`).
- Invariant 6: Minimum password length is 6 characters for user creation, admin reset, and self-service change.
- Invariant 7: Self-service password change requires verifying current password (`400 Bad Request` with detail `"Current password is incorrect"`).
- Invariant 8: Self-service password change forbids reusing current password (`400 Bad Request` with detail `"New password must be different from current password"`).
- Invariant 9: Role values must be normalized to lowercase (`"admin"`, `"operator"`) or uppercase (`"ADMIN"`, `"OPERATOR"`) in a case-insensitive manner.

---

### Task 1: Backend Schemas and User CRUD & Safety Endpoints

**Files:**
- Modify: `services/api/src/api/auth.py`
- Create: `services/api/tests/test_user_management.py`

**Interfaces:**
- Consumes: `services.api.src.db.models.User`, `services.api.src.db.session.get_db`, `services.api.src.services.auth.hash_password`, `require_role(["admin"])`
- Produces:
  - `UserResponse`: `{ id: int, username: str, role: str, is_active: bool }`
  - `UserCreateRequest`: `{ username: str, password: str, role: str = "operator", is_active: bool = True }`
  - `UserUpdateRequest`: `{ role: Optional[str] = None, is_active: Optional[bool] = None }`
  - `AdminResetPasswordRequest`: `{ new_password: str }`
  - Endpoints:
    - `GET /api/v1/auth/users`
    - `POST /api/v1/auth/users`
    - `PUT /api/v1/auth/users/{user_id}`
    - `PUT /api/v1/auth/users/{user_id}/password`
    - `DELETE /api/v1/auth/users/{user_id}`

- [ ] **Step 1: Write the failing tests for User CRUD & Safety Invariants**

Create `services/api/tests/test_user_management.py`:
```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api.src.main import app
from services.api.src.db.session import get_db
from services.api.src.db.models import Base, User
from services.api.src.services.auth import hash_password


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestingSession()
    db.add(User(username="admin", password_hash=hash_password("admin123"), role="admin", is_active=True))
    db.add(User(username="admin2", password_hash=hash_password("admin456"), role="admin", is_active=True))
    db.add(User(username="operator", password_hash=hash_password("op123"), role="operator", is_active=True))
    db.commit()
    db.close()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def get_token(client, username, password):
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_list_users_as_admin(client):
    token = get_token(client, "admin", "admin123")
    res = client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    users = res.json()
    assert len(users) == 3
    usernames = [u["username"] for u in users]
    assert "admin" in usernames
    assert "operator" in usernames


def test_list_users_as_operator_forbidden(client):
    token = get_token(client, "operator", "op123")
    res = client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_create_user_success(client):
    token = get_token(client, "admin", "admin123")
    res = client.post(
        "/api/v1/auth/users",
        json={"username": "newuser", "password": "password123", "role": "operator"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["username"] == "newuser"
    assert data["role"].lower() == "operator"
    assert data["is_active"] is True


def test_create_user_duplicate_username(client):
    token = get_token(client, "admin", "admin123")
    res = client.post(
        "/api/v1/auth/users",
        json={"username": "operator", "password": "password123", "role": "operator"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert "Username already exists" in res.json()["detail"]


def test_update_user_role_and_status(client):
    token = get_token(client, "admin", "admin123")
    # Get operator ID
    users = client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {token}"}).json()
    op = next(u for u in users if u["username"] == "operator")

    res = client.put(
        f"/api/v1/auth/users/{op['id']}",
        json={"role": "admin", "is_active": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["role"].lower() == "admin"
    assert data["is_active"] is False


def test_admin_cannot_deactivate_self(client):
    token = get_token(client, "admin", "admin123")
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    res = client.put(
        f"/api/v1/auth/users/{me['id']}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert "Cannot deactivate own account" in res.json()["detail"]


def test_cannot_deactivate_or_demote_last_admin(client):
    token = get_token(client, "admin", "admin123")
    users = client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {token}"}).json()
    admin2 = next(u for u in users if u["username"] == "admin2")

    # Demote admin2 so admin is the only active admin left
    res = client.put(
        f"/api/v1/auth/users/{admin2['id']}",
        json={"role": "operator"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200

    # Now trying to demote the only remaining admin (admin) should fail
    admin1 = next(u for u in users if u["username"] == "admin")
    res_demote = client.put(
        f"/api/v1/auth/users/{admin1['id']}",
        json={"role": "operator"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_demote.status_code == 400
    assert "Cannot deactivate or demote the last remaining active admin" in res_demote.json()["detail"]


def test_admin_reset_user_password(client):
    token = get_token(client, "admin", "admin123")
    users = client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {token}"}).json()
    op = next(u for u in users if u["username"] == "operator")

    res = client.put(
        f"/api/v1/auth/users/{op['id']}/password",
        json={"new_password": "new_operator_pass"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200

    # Verify operator can login with new password
    login_res = client.post("/api/v1/auth/login", json={"username": "operator", "password": "new_operator_pass"})
    assert login_res.status_code == 200


def test_admin_cannot_delete_self(client):
    token = get_token(client, "admin", "admin123")
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    res = client.delete(
        f"/api/v1/auth/users/{me['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert "Cannot delete own account" in res.json()["detail"]


def test_cannot_delete_last_active_admin(client):
    token = get_token(client, "admin", "admin123")
    users = client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {token}"}).json()
    admin2 = next(u for u in users if u["username"] == "admin2")

    # Delete admin2
    res_del2 = client.delete(
        f"/api/v1/auth/users/{admin2['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_del2.status_code == 200

    # Delete operator
    op = next(u for u in users if u["username"] == "operator")
    res_del_op = client.delete(
        f"/api/v1/auth/users/{op['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_del_op.status_code == 200

    # Now admin is the last admin: delete should fail
    admin1 = next(u for u in users if u["username"] == "admin")
    res_last = client.delete(
        f"/api/v1/auth/users/{admin1['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    # Self delete fails first with 400
    assert res_last.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
& "C:\Users\torino\AppData\Local\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe" run --with fastapi --with httpx --with sqlalchemy --with pytest --with pyjwt --with python-dotenv --with opencv-python-headless --with reportlab --with openpyxl pytest services/api/tests/test_user_management.py -v
```
Expected: FAIL (404/405 Not Found as user endpoints do not exist yet).

- [ ] **Step 3: Implement User Schemas and Endpoints in `services/api/src/api/auth.py`**

In `services/api/src/api/auth.py`:
1. Add schemas:
```python
class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    role: Literal["admin", "operator", "ADMIN", "OPERATOR"] = "operator"
    is_active: bool = True

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Username cannot be empty")
        return v

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, v: str) -> str:
        return v.strip().lower() if isinstance(v, str) else v


class UserUpdateRequest(BaseModel):
    role: Optional[Literal["admin", "operator", "ADMIN", "OPERATOR"]] = None
    is_active: Optional[bool] = None

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return v.strip().lower() if isinstance(v, str) else v


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=128)
```

2. Add endpoints:
```python
from sqlalchemy import func

@router.get("/users", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: UserDTO = Depends(require_role(["admin"])),
):
    users = db.scalars(select(User).order_by(User.id)).all()
    return [
        UserResponse(
            id=u.id,
            username=u.username,
            role=u.role.lower(),
            is_active=u.is_active,
        )
        for u in users
    ]


@router.post("/users", response_model=UserResponse, status_code=201)
def create_user(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
    current_user: UserDTO = Depends(require_role(["admin"])),
):
    existing = db.scalars(select(User).where(User.username == payload.username)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    new_user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role.lower(),
        is_active=payload.is_active,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return UserResponse(
        id=new_user.id,
        username=new_user.username,
        role=new_user.role.lower(),
        is_active=new_user.is_active,
    )


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: UserDTO = Depends(require_role(["admin"])),
):
    target_user = db.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Invariant: Admin cannot deactivate their own account
    if target_user.id == current_user.id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="Cannot deactivate own account")

    # Invariant: Cannot deactivate or demote last active admin
    is_target_active_admin = (target_user.role.lower() == "admin") and target_user.is_active
    will_be_demoted = payload.role is not None and payload.role.lower() != "admin"
    will_be_deactivated = payload.is_active is False

    if is_target_active_admin and (will_be_demoted or will_be_deactivated):
        active_admin_count = db.scalar(
            select(func.count(User.id)).where(
                func.lower(User.role) == "admin",
                User.is_active == True,
            )
        )
        if active_admin_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot deactivate or demote the last remaining active admin",
            )

    if payload.role is not None:
        target_user.role = payload.role.lower()
    if payload.is_active is not None:
        target_user.is_active = payload.is_active

    db.commit()
    db.refresh(target_user)
    return UserResponse(
        id=target_user.id,
        username=target_user.username,
        role=target_user.role.lower(),
        is_active=target_user.is_active,
    )


@router.put("/users/{user_id}/password", response_model=dict)
def admin_reset_password(
    user_id: int,
    payload: AdminResetPasswordRequest,
    db: Session = Depends(get_db),
    current_user: UserDTO = Depends(require_role(["admin"])),
):
    target_user = db.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    target_user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"message": "Password reset successfully"}


@router.delete("/users/{user_id}", response_model=dict)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: UserDTO = Depends(require_role(["admin"])),
):
    # Invariant: Admin cannot delete their own account
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete own account")

    target_user = db.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Invariant: Cannot delete the last remaining active admin
    if target_user.role.lower() == "admin" and target_user.is_active:
        active_admin_count = db.scalar(
            select(func.count(User.id)).where(
                func.lower(User.role) == "admin",
                User.is_active == True,
            )
        )
        if active_admin_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the last remaining active admin",
            )

    db.delete(target_user)
    db.commit()
    return {"message": "User deleted successfully"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
& "C:\Users\torino\AppData\Local\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe" run --with fastapi --with httpx --with sqlalchemy --with pytest --with pyjwt --with python-dotenv --with opencv-python-headless --with reportlab --with openpyxl pytest services/api/tests/test_user_management.py -v
```
Expected: PASS (all tests pass).

- [ ] **Step 5: Commit**

```bash
git add services/api/src/api/auth.py services/api/tests/test_user_management.py
git commit -m "feat(auth): add user CRUD and safety invariant endpoints"
```

---

### Task 2: Backend Self-Service Password Change Endpoint

**Files:**
- Modify: `services/api/src/api/auth.py`
- Modify: `services/api/tests/test_user_management.py`

**Interfaces:**
- Consumes: `services.api.src.db.models.User`, `services.api.src.services.auth.verify_password`, `services.api.src.services.auth.hash_password`, `get_current_user`
- Produces:
  - `ChangePasswordRequest`: `{ current_password: str, new_password: str }`
  - Endpoint: `PUT /api/v1/auth/password`

- [ ] **Step 1: Write the failing tests for Self-Service Password Change**

Append to `services/api/tests/test_user_management.py`:
```python
def test_change_password_success(client):
    token = get_token(client, "operator", "op123")
    res = client.put(
        "/api/v1/auth/password",
        json={"current_password": "op123", "new_password": "new_op_password_456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["message"] == "Password changed successfully"

    # Verify old password fails
    res_old = client.post("/api/v1/auth/login", json={"username": "operator", "password": "op123"})
    assert res_old.status_code == 401

    # Verify new password works
    res_new = client.post("/api/v1/auth/login", json={"username": "operator", "password": "new_op_password_456"})
    assert res_new.status_code == 200


def test_change_password_wrong_current_password(client):
    token = get_token(client, "operator", "op123")
    res = client.put(
        "/api/v1/auth/password",
        json={"current_password": "wrong_password", "new_password": "new_op_password_456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert "Current password is incorrect" in res.json()["detail"]


def test_change_password_same_password_rejected(client):
    token = get_token(client, "operator", "op123")
    res = client.put(
        "/api/v1/auth/password",
        json={"current_password": "op123", "new_password": "op123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert "New password must be different from current password" in res.json()["detail"]


def test_change_password_too_short(client):
    token = get_token(client, "operator", "op123")
    res = client.put(
        "/api/v1/auth/password",
        json={"current_password": "op123", "new_password": "123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
& "C:\Users\torino\AppData\Local\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe" run --with fastapi --with httpx --with sqlalchemy --with pytest --with pyjwt --with python-dotenv --with opencv-python-headless --with reportlab --with openpyxl pytest services/api/tests/test_user_management.py -k "test_change_password" -v
```
Expected: FAIL (404/405 Not Found).

- [ ] **Step 3: Implement `ChangePasswordRequest` and `PUT /api/v1/auth/password`**

In `services/api/src/api/auth.py`:
1. Add Schema:
```python
class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6, max_length=128)
```
2. Add Endpoint:
```python
@router.put("/password", response_model=dict)
def change_self_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: UserDTO = Depends(get_current_user),
):
    user = db.get(User, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=400,
            detail="New password must be different from current password",
        )

    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"message": "Password changed successfully"}
```

- [ ] **Step 4: Run all auth and user management tests to verify they pass**

Run:
```bash
& "C:\Users\torino\AppData\Local\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe" run --with fastapi --with httpx --with sqlalchemy --with pytest --with pyjwt --with python-dotenv --with opencv-python-headless --with reportlab --with openpyxl pytest services/api/tests/test_user_management.py services/api/tests/test_auth_api.py -v
```
Expected: PASS (all tests in both files pass).

- [ ] **Step 5: Commit**

```bash
git add services/api/src/api/auth.py services/api/tests/test_user_management.py
git commit -m "feat(auth): add self-service change password endpoint"
```

---

### Task 3: Frontend Feature Types and API Client

**Files:**
- Create: `frontend/src/features/users/types/index.ts`
- Create: `frontend/src/features/users/api/users.api.ts`
- Create: `frontend/src/features/users/index.ts`

**Interfaces:**
- Consumes: `frontend/src/lib/http.ts` (`apiClient`)
- Produces:
  - `UserItem`, `CreateUserPayload`, `UpdateUserPayload`, `AdminResetPasswordPayload`, `ChangePasswordPayload`
  - `usersApi.getUsers(): Promise<UserItem[]>`
  - `usersApi.createUser(payload: CreateUserPayload): Promise<UserItem>`
  - `usersApi.updateUser(userId: number, payload: UpdateUserPayload): Promise<UserItem>`
  - `usersApi.resetPassword(userId: number, payload: AdminResetPasswordPayload): Promise<{ message: string }>`
  - `usersApi.deleteUser(userId: number): Promise<{ message: string }>`
  - `usersApi.changePassword(payload: ChangePasswordPayload): Promise<{ message: string }>`

- [ ] **Step 1: Create `frontend/src/features/users/types/index.ts`**

```typescript
export interface UserItem {
  id: number;
  username: str;
  role: "admin" | "operator";
  is_active: boolean;
}

export interface CreateUserPayload {
  username: string;
  password: str;
  role: "admin" | "operator";
  is_active?: boolean;
}

export interface UpdateUserPayload {
  role?: "admin" | "operator";
  is_active?: boolean;
}

export interface AdminResetPasswordPayload {
  new_password: string;
}

export interface ChangePasswordPayload {
  current_password: string;
  new_password: string;
}
```

- [ ] **Step 2: Create `frontend/src/features/users/api/users.api.ts`**

```typescript
import { apiClient } from "@/lib/http";
import type {
  UserItem,
  CreateUserPayload,
  UpdateUserPayload,
  AdminResetPasswordPayload,
  ChangePasswordPayload,
} from "../types";

export const usersApi = {
  getUsers: async (): Promise<UserItem[]> => {
    return apiClient.get<UserItem[]>("/api/v1/auth/users");
  },

  createUser: async (payload: CreateUserPayload): Promise<UserItem> => {
    return apiClient.post<UserItem>("/api/v1/auth/users", payload);
  },

  updateUser: async (userId: number, payload: UpdateUserPayload): Promise<UserItem> => {
    return apiClient.put<UserItem>(`/api/v1/auth/users/${userId}`, payload);
  },

  resetPassword: async (userId: number, payload: AdminResetPasswordPayload): Promise<{ message: string }> => {
    return apiClient.put<{ message: string }>(`/api/v1/auth/users/${userId}/password`, payload);
  },

  deleteUser: async (userId: number): Promise<{ message: string }> => {
    return apiClient.delete<{ message: string }>(`/api/v1/auth/users/${userId}`);
  },

  changePassword: async (payload: ChangePasswordPayload): Promise<{ message: string }> => {
    return apiClient.put<{ message: string }>("/api/v1/auth/password", payload);
  },
};
```

- [ ] **Step 3: Create `frontend/src/features/users/index.ts`**

```typescript
export * from "./types";
export * from "./api/users.api";
```

- [ ] **Step 4: Run frontend build to verify TypeScript compilation**

Run:
```bash
npm --prefix frontend run build
```
Expected: Build succeeds with 0 errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/users/
git commit -m "feat(users): add user management types and api client"
```

---

### Task 4: Frontend Modals (`CreateUserModal`, `EditUserModal`, `ResetPasswordModal`, `DeleteUserModal`)

**Files:**
- Create: `frontend/src/features/users/components/CreateUserModal.tsx`
- Create: `frontend/src/features/users/components/EditUserModal.tsx`
- Create: `frontend/src/features/users/components/ResetPasswordModal.tsx`
- Create: `frontend/src/features/users/components/DeleteUserModal.tsx`
- Modify: `frontend/src/features/users/index.ts`

**Interfaces:**
- Consumes: `@/components/ui/button`, `@/components/ui/input`, `@/components/ui/select`, `lucide-react`, `frontend/src/features/users/types`
- Produces:
  - `<CreateUserModal isOpen onClose onSubmit />`
  - `<EditUserModal isOpen onClose user currentUserId activeAdminCount onSubmit />`
  - `<ResetPasswordModal isOpen onClose user onSubmit />`
  - `<DeleteUserModal isOpen onClose user onConfirm />`

- [ ] **Step 1: Create `CreateUserModal.tsx`**

Create `frontend/src/features/users/components/CreateUserModal.tsx`:
```tsx
import { useState, useEffect, type FormEvent } from "react";
import { X, UserPlus, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import type { CreateUserPayload } from "../types";

export interface CreateUserModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (payload: CreateUserPayload) => Promise<void>;
}

export function CreateUserModal({ isOpen, onClose, onSubmit }: CreateUserModalProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"admin" | "operator">("operator");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setUsername("");
      setPassword("");
      setRole("operator");
      setErrorMsg(null);
      setIsSubmitting(false);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const cleanUsername = username.trim();
    if (!cleanUsername) {
      setErrorMsg("Nama pengguna tidak boleh kosong");
      return;
    }
    if (password.length < 6) {
      setErrorMsg("Password minimal 6 karakter");
      return;
    }

    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      await onSubmit({ username: cleanUsername, password, role, is_active: true });
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Gagal menambahkan pengguna";
      setErrorMsg(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden border border-slate-100 animate-in fade-in zoom-in duration-150">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="p-2 bg-emerald-50 rounded-lg text-emerald-600">
              <UserPlus className="w-5 h-5" />
            </div>
            <h2 className="text-lg font-semibold text-slate-900">Tambah Pengguna Baru</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {errorMsg && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-start gap-2.5 text-rose-700 text-sm">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Nama Pengguna (Username)
            </label>
            <Input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Contoh: op_johndoe"
              required
              disabled={isSubmitting}
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Password
            </label>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Minimal 6 karakter"
              required
              disabled={isSubmitting}
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Peran (Role)
            </label>
            <Select
              value={role}
              onChange={(e) => setRole(e.target.value as "admin" | "operator")}
              disabled={isSubmitting}
            >
              <option value="operator">Operator (Pemantauan & Operasional)</option>
              <option value="admin">Admin (Akses Penuh Sistem)</option>
            </Select>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
            <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting}>
              Batal
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Menyimpan..." : "Simpan Pengguna"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `EditUserModal.tsx`**

Create `frontend/src/features/users/components/EditUserModal.tsx`:
```tsx
import { useState, useEffect, type FormEvent } from "react";
import { X, UserCog, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import type { UserItem, UpdateUserPayload } from "../types";

export interface EditUserModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: UserItem | null;
  currentUserId: number | undefined;
  activeAdminCount: number;
  onSubmit: (userId: number, payload: UpdateUserPayload) => Promise<void>;
}

export function EditUserModal({
  isOpen,
  onClose,
  user,
  currentUserId,
  activeAdminCount,
  onSubmit,
}: EditUserModalProps) {
  const [role, setRole] = useState<"admin" | "operator">("operator");
  const [isActive, setIsActive] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (user && isOpen) {
      setRole(user.role);
      setIsActive(user.is_active);
      setErrorMsg(null);
      setIsSubmitting(false);
    }
  }, [user, isOpen]);

  if (!isOpen || !user) return null;

  const isSelf = user.id === currentUserId;
  const isLastActiveAdmin = user.role === "admin" && user.is_active && activeAdminCount <= 1;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (isSelf && !isActive) {
      setErrorMsg("Anda tidak dapat menonaktifkan akun sendiri");
      return;
    }
    if (isLastActiveAdmin && (role !== "admin" || !isActive)) {
      setErrorMsg("Tidak dapat mengubah peran atau menonaktifkan satu-satunya admin aktif");
      return;
    }

    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      await onSubmit(user.id, { role, is_active: isActive });
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Gagal memperbarui pengguna";
      setErrorMsg(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden border border-slate-100 animate-in fade-in zoom-in duration-150">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="p-2 bg-indigo-50 rounded-lg text-indigo-600">
              <UserCog className="w-5 h-5" />
            </div>
            <h2 className="text-lg font-semibold text-slate-900">Ubah Data Pengguna</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {errorMsg && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-start gap-2.5 text-rose-700 text-sm">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-sm">
            <span className="text-slate-500 font-medium">Username: </span>
            <span className="font-semibold text-slate-900">{user.username}</span>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Peran (Role)
            </label>
            <Select
              value={role}
              onChange={(e) => setRole(e.target.value as "admin" | "operator")}
              disabled={isSubmitting || (isLastActiveAdmin && role === "admin")}
            >
              <option value="operator">Operator</option>
              <option value="admin">Admin</option>
            </Select>
            {isLastActiveAdmin && (
              <p className="text-xs text-amber-600 mt-1">
                Peran tidak dapat diturunkan karena merupakan satu-satunya admin aktif.
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Status Akun
            </label>
            <div className="flex items-center gap-3 pt-1">
              <label className="inline-flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={isActive}
                  onChange={(e) => setIsActive(e.target.checked)}
                  disabled={isSubmitting || isSelf || isLastActiveAdmin}
                  className="w-4 h-4 text-emerald-600 rounded border-slate-300 focus:ring-emerald-500 disabled:opacity-50"
                />
                <span className="text-sm font-medium text-slate-700">Akun Aktif</span>
              </label>
            </div>
            {isSelf && (
              <p className="text-xs text-amber-600 mt-1">
                Anda tidak dapat menonaktifkan akun yang sedang digunakan saat ini.
              </p>
            )}
            {!isSelf && isLastActiveAdmin && (
              <p className="text-xs text-amber-600 mt-1">
                Akun ini tidak dapat dinonaktifkan karena merupakan satu-satunya admin aktif.
              </p>
            )}
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
            <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting}>
              Batal
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Menyimpan..." : "Simpan Perubahan"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create `ResetPasswordModal.tsx`**

Create `frontend/src/features/users/components/ResetPasswordModal.tsx`:
```tsx
import { useState, useEffect, type FormEvent } from "react";
import { X, KeyRound, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { UserItem, AdminResetPasswordPayload } from "../types";

export interface ResetPasswordModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: UserItem | null;
  onSubmit: (userId: number, payload: AdminResetPasswordPayload) => Promise<void>;
}

export function ResetPasswordModal({ isOpen, onClose, user, onSubmit }: ResetPasswordModalProps) {
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setNewPassword("");
      setConfirmPassword("");
      setErrorMsg(null);
      setIsSubmitting(false);
    }
  }, [isOpen]);

  if (!isOpen || !user) return null;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (newPassword.length < 6) {
      setErrorMsg("Password minimal 6 karakter");
      return;
    }
    if (newPassword !== confirmPassword) {
      setErrorMsg("Konfirmasi password baru tidak cocok");
      return;
    }

    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      await onSubmit(user.id, { new_password: newPassword });
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Gagal mengatur ulang password";
      setErrorMsg(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden border border-slate-100 animate-in fade-in zoom-in duration-150">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="p-2 bg-amber-50 rounded-lg text-amber-600">
              <KeyRound className="w-5 h-5" />
            </div>
            <h2 className="text-lg font-semibold text-slate-900">Reset Password Pengguna</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {errorMsg && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-start gap-2.5 text-rose-700 text-sm">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-sm">
            <span className="text-slate-500 font-medium">Reset password untuk: </span>
            <span className="font-semibold text-slate-900">{user.username}</span>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Password Baru
            </label>
            <Input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Minimal 6 karakter"
              required
              disabled={isSubmitting}
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Konfirmasi Password Baru
            </label>
            <Input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Ulangi password baru"
              required
              disabled={isSubmitting}
            />
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
            <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting}>
              Batal
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Menyimpan..." : "Simpan Password Baru"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create `DeleteUserModal.tsx`**

Create `frontend/src/features/users/components/DeleteUserModal.tsx`:
```tsx
import { useState } from "react";
import { AlertTriangle, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { UserItem } from "../types";

export interface DeleteUserModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: UserItem | null;
  onConfirm: (userId: number) => Promise<void>;
}

export function DeleteUserModal({ isOpen, onClose, user, onConfirm }: DeleteUserModalProps) {
  const [isDeleting, setIsDeleting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isOpen || !user) return null;

  const handleDelete = async () => {
    setIsDeleting(true);
    setErrorMsg(null);
    try {
      await onConfirm(user.id);
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Gagal menghapus pengguna";
      setErrorMsg(msg);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden border border-slate-100 animate-in fade-in zoom-in duration-150">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="p-2 bg-rose-50 rounded-lg text-rose-600">
              <Trash2 className="w-5 h-5" />
            </div>
            <h2 className="text-lg font-semibold text-slate-900">Hapus Pengguna</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          {errorMsg && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-start gap-2.5 text-rose-700 text-sm">
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          <p className="text-sm text-slate-600 leading-relaxed">
            Apakah Anda yakin ingin menghapus akun pengguna{" "}
            <span className="font-semibold text-slate-900">"{user.username}"</span>? Tindakan ini tidak dapat
            dibatalkan.
          </p>

          <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
            <Button type="button" variant="outline" onClick={onClose} disabled={isDeleting}>
              Batal
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={handleDelete}
              disabled={isDeleting}
            >
              {isDeleting ? "Menghapus..." : "Hapus Pengguna"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Export Modals in `frontend/src/features/users/index.ts`**

Update `frontend/src/features/users/index.ts`:
```typescript
export * from "./types";
export * from "./api/users.api";
export * from "./components/CreateUserModal";
export * from "./components/EditUserModal";
export * from "./components/ResetPasswordModal";
export * from "./components/DeleteUserModal";
```

- [ ] **Step 6: Run frontend build to verify compilation**

Run:
```bash
npm --prefix frontend run build
```
Expected: Build succeeds with 0 errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/users/
git commit -m "feat(users): add user management modal components"
```

---

### Task 5: Frontend Users Management Page (`PenggunaPage.tsx`)

**Files:**
- Create: `frontend/src/features/users/pages/PenggunaPage.tsx`
- Modify: `frontend/src/features/users/index.ts`

**Interfaces:**
- Consumes:
  - `PageHeader` from `@/components/layout/PageHeader`
  - `Card`, `Button`, `Input`, `Select` from `@/components/ui/`
  - `useAuth` from `@/features/auth`
  - `usersApi`, Modals, Types from `frontend/src/features/users`
- Produces:
  - `PenggunaPage` component

- [ ] **Step 1: Create `PenggunaPage.tsx`**

Create `frontend/src/features/users/pages/PenggunaPage.tsx`:
```tsx
import { useState, useEffect, useCallback, useMemo } from "react";
import {
  Users,
  UserCheck,
  ShieldAlert,
  UserPlus,
  RefreshCw,
  Search,
  Filter,
  KeyRound,
  Edit2,
  Trash2,
  Shield,
  User,
  AlertCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useAuth } from "@/features/auth";
import {
  usersApi,
  CreateUserModal,
  EditUserModal,
  ResetPasswordModal,
  DeleteUserModal,
  type UserItem,
  type CreateUserPayload,
  type UpdateUserPayload,
  type AdminResetPasswordPayload,
} from "../index";

export function PenggunaPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<UserItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Modal states
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<UserItem | null>(null);
  const [resettingUser, setResettingUser] = useState<UserItem | null>(null);
  const [deletingUser, setDeletingUser] = useState<UserItem | null>(null);

  const fetchUsers = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) {
      setIsRefreshing(true);
    } else {
      setIsLoading(true);
    }
    setError(null);
    try {
      const data = await usersApi.getUsers();
      setUsers(Array.isArray(data) ? data : []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Gagal memuat data pengguna";
      setError(msg);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  // KPI Calculations
  const totalCount = users.length;
  const activeCount = useMemo(() => users.filter((u) => u.is_active).length, [users]);
  const adminCount = useMemo(() => users.filter((u) => u.role === "admin").length, [users]);
  const activeAdminCount = useMemo(
    () => users.filter((u) => u.role === "admin" && u.is_active).length,
    [users]
  );
  const operatorCount = useMemo(() => users.filter((u) => u.role === "operator").length, [users]);

  // Filtered users
  const filteredUsers = useMemo(() => {
    return users.filter((u) => {
      const matchSearch = u.username.toLowerCase().includes(searchQuery.toLowerCase().trim());
      const matchRole = roleFilter === "all" || u.role.toLowerCase() === roleFilter.toLowerCase();
      const matchStatus =
        statusFilter === "all" ||
        (statusFilter === "active" && u.is_active) ||
        (statusFilter === "inactive" && !u.is_active);
      return matchSearch && matchRole && matchStatus;
    });
  }, [users, searchQuery, roleFilter, statusFilter]);

  // Modal actions
  const handleCreateSubmit = async (payload: CreateUserPayload) => {
    await usersApi.createUser(payload);
    await fetchUsers();
  };

  const handleEditSubmit = async (userId: number, payload: UpdateUserPayload) => {
    await usersApi.updateUser(userId, payload);
    await fetchUsers();
  };

  const handleResetSubmit = async (userId: number, payload: AdminResetPasswordPayload) => {
    await usersApi.resetPassword(userId, payload);
  };

  const handleDeleteConfirm = async (userId: number) => {
    await usersApi.deleteUser(userId);
    await fetchUsers();
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Manajemen Pengguna"
        description="Kelola akun pengguna, peran otorisasi, status aktivasi, dan reset kredensial sistem"
      >
        <Button
          variant="outline"
          size="sm"
          onClick={() => fetchUsers(true)}
          disabled={isLoading || isRefreshing}
          className="flex items-center gap-1.5 cursor-pointer"
        >
          <RefreshCw className={cn("w-4 h-4", (isLoading || isRefreshing) && "animate-spin")} />
          <span>Segarkan</span>
        </Button>
        <Button
          size="sm"
          onClick={() => setIsCreateOpen(true)}
          className="flex items-center gap-1.5 cursor-pointer"
        >
          <UserPlus className="w-4 h-4" />
          <span>Tambah Pengguna</span>
        </Button>
      </PageHeader>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Total Pengguna
            </CardTitle>
            <div className="p-2 bg-slate-100 rounded-lg text-slate-600">
              <Users className="w-4 h-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-slate-900">{totalCount}</div>
            <p className="text-xs text-slate-500 mt-1">Terdaftar di sistem</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Pengguna Aktif
            </CardTitle>
            <div className="p-2 bg-emerald-50 rounded-lg text-emerald-600">
              <UserCheck className="w-4 h-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-emerald-600">{activeCount}</div>
            <p className="text-xs text-slate-500 mt-1">Dapat melakukan login</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Administrator
            </CardTitle>
            <div className="p-2 bg-indigo-50 rounded-lg text-indigo-600">
              <Shield className="w-4 h-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-indigo-600">{adminCount}</div>
            <p className="text-xs text-slate-500 mt-1">Akses konfigurasi penuh</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Operator
            </CardTitle>
            <div className="p-2 bg-amber-50 rounded-lg text-amber-600">
              <User className="w-4 h-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-600">{operatorCount}</div>
            <p className="text-xs text-slate-500 mt-1">Operasional lini dan video</p>
          </CardContent>
        </Card>
      </div>

      {/* Main Table Card */}
      <Card>
        <CardHeader className="border-b border-slate-100">
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-slate-500" />
              <CardTitle className="text-base font-semibold text-slate-900">
                Daftar Pengguna ({filteredUsers.length})
              </CardTitle>
            </div>

            {/* Filter controls */}
            <div className="flex flex-wrap items-center gap-2.5">
              <div className="relative min-w-[200px]">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input
                  type="text"
                  placeholder="Cari username..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9 h-9 text-xs"
                />
              </div>

              <Select
                value={roleFilter}
                onChange={(e) => setRoleFilter(e.target.value)}
                className="h-9 text-xs min-w-[120px]"
              >
                <option value="all">Semua Peran</option>
                <option value="admin">Admin</option>
                <option value="operator">Operator</option>
              </Select>

              <Select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="h-9 text-xs min-w-[120px]"
              >
                <option value="all">Semua Status</option>
                <option value="active">Aktif</option>
                <option value="inactive">Nonaktif</option>
              </Select>
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-0">
          {error && (
            <div className="p-4 bg-rose-50 border-b border-rose-100 flex items-center gap-3 text-rose-700 text-sm">
              <AlertCircle className="w-5 h-5 shrink-0" />
              <div className="flex-1">
                <p className="font-semibold">Gagal memuat pengguna</p>
                <p className="text-xs text-rose-600 mt-0.5">{error}</p>
              </div>
              <Button size="sm" variant="outline" onClick={() => fetchUsers(true)}>
                Coba Lagi
              </Button>
            </div>
          )}

          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-16 text-slate-400">
              <RefreshCw className="w-6 h-6 animate-spin text-emerald-600 mb-2" />
              <p className="text-xs">Memuat daftar pengguna...</p>
            </div>
          ) : filteredUsers.length === 0 ? (
            <div className="text-center py-16 text-slate-500">
              <Users className="w-10 h-10 mx-auto text-slate-300 mb-2" />
              <p className="text-sm font-medium">Tidak ada data pengguna yang cocok</p>
              <p className="text-xs text-slate-400 mt-1">Coba sesuaikan kata kunci atau filter pencarian</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50/75 border-b border-slate-100 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  <tr>
                    <th className="py-3 px-6">ID</th>
                    <th className="py-3 px-6">Nama Pengguna</th>
                    <th className="py-3 px-6">Peran</th>
                    <th className="py-3 px-6">Status</th>
                    <th className="py-3 px-6 text-right">Aksi</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredUsers.map((u) => {
                    const isSelf = u.id === currentUser?.id;
                    const isLastAdmin = u.role === "admin" && u.is_active && activeAdminCount <= 1;

                    return (
                      <tr key={u.id} className="hover:bg-slate-50/60 transition-colors">
                        <td className="py-4 px-6 font-mono text-xs text-slate-500">#{u.id}</td>
                        <td className="py-4 px-6">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-slate-900">{u.username}</span>
                            {isSelf && (
                              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                                Akun Anda
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="py-4 px-6">
                          {u.role === "admin" ? (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                              <Shield className="w-3 h-3" />
                              Admin
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                              <User className="w-3 h-3" />
                              Operator
                            </span>
                          )}
                        </td>
                        <td className="py-4 px-6">
                          {u.is_active ? (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                              Aktif
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-600 border border-slate-200">
                              <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                              Nonaktif
                            </span>
                          )}
                        </td>
                        <td className="py-4 px-6 text-right">
                          <div className="inline-flex items-center gap-1">
                            <button
                              type="button"
                              onClick={() => setEditingUser(u)}
                              title="Ubah peran dan status"
                              className="p-1.5 text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors cursor-pointer"
                            >
                              <Edit2 className="w-4 h-4" />
                            </button>
                            <button
                              type="button"
                              onClick={() => setResettingUser(u)}
                              title="Reset password"
                              className="p-1.5 text-slate-500 hover:text-amber-600 hover:bg-amber-50 rounded-lg transition-colors cursor-pointer"
                            >
                              <KeyRound className="w-4 h-4" />
                            </button>
                            <button
                              type="button"
                              onClick={() => setDeletingUser(u)}
                              disabled={isSelf || isLastAdmin}
                              title={
                                isSelf
                                  ? "Anda tidak dapat menghapus akun sendiri"
                                  : isLastAdmin
                                  ? "Tidak dapat menghapus satu-satunya admin aktif"
                                  : "Hapus akun pengguna"
                              }
                              className={cn(
                                "p-1.5 rounded-lg transition-colors",
                                isSelf || isLastAdmin
                                  ? "text-slate-300 cursor-not-allowed opacity-50"
                                  : "text-slate-500 hover:text-rose-600 hover:bg-rose-50 cursor-pointer"
                              )}
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Modals */}
      <CreateUserModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onSubmit={handleCreateSubmit}
      />
      <EditUserModal
        isOpen={!!editingUser}
        onClose={() => setEditingUser(null)}
        user={editingUser}
        currentUserId={currentUser?.id}
        activeAdminCount={activeAdminCount}
        onSubmit={handleEditSubmit}
      />
      <ResetPasswordModal
        isOpen={!!resettingUser}
        onClose={() => setResettingUser(null)}
        user={resettingUser}
        onSubmit={handleResetSubmit}
      />
      <DeleteUserModal
        isOpen={!!deletingUser}
        onClose={() => setDeletingUser(null)}
        user={deletingUser}
        onConfirm={handleDeleteConfirm}
      />
    </div>
  );
}

export default PenggunaPage;
```

- [ ] **Step 2: Re-export `PenggunaPage` in `frontend/src/features/users/index.ts`**

Update `frontend/src/features/users/index.ts`:
```typescript
export * from "./types";
export * from "./api/users.api";
export * from "./components/CreateUserModal";
export * from "./components/EditUserModal";
export * from "./components/ResetPasswordModal";
export * from "./components/DeleteUserModal";
export { PenggunaPage, default } from "./pages/PenggunaPage";
```

- [ ] **Step 3: Run frontend build to verify compilation**

Run:
```bash
npm --prefix frontend run build
```
Expected: Build succeeds with 0 errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/users/
git commit -m "feat(users): add PenggunaPage user management view"
```

---

### Task 6: Self-Service Password Modal & Header Integration

**Files:**
- Create: `frontend/src/features/users/components/ChangePasswordModal.tsx`
- Modify: `frontend/src/features/users/index.ts`
- Modify: `frontend/src/components/layout/Header.tsx`

**Interfaces:**
- Consumes: `usersApi.changePassword`, `@/components/ui/button`, `@/components/ui/input`, `lucide-react`
- Produces:
  - `<ChangePasswordModal isOpen onClose />`
  - Integrated header trigger button in `Header.tsx`

- [ ] **Step 1: Create `ChangePasswordModal.tsx`**

Create `frontend/src/features/users/components/ChangePasswordModal.tsx`:
```tsx
import { useState, useEffect, type FormEvent } from "react";
import { X, KeyRound, AlertCircle, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { usersApi } from "../api/users.api";

export interface ChangePasswordModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function ChangePasswordModal({ isOpen, onClose }: ChangePasswordModalProps) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setErrorMsg(null);
      setSuccessMsg(null);
      setIsSubmitting(false);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!currentPassword) {
      setErrorMsg("Password saat ini wajib diisi");
      return;
    }
    if (newPassword.length < 6) {
      setErrorMsg("Password baru minimal 6 karakter");
      return;
    }
    if (newPassword === currentPassword) {
      setErrorMsg("Password baru harus berbeda dari password saat ini");
      return;
    }
    if (newPassword !== confirmPassword) {
      setErrorMsg("Konfirmasi password baru tidak cocok");
      return;
    }

    setIsSubmitting(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      await usersApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setSuccessMsg("Password berhasil diperbarui!");
      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Gagal mengganti password";
      setErrorMsg(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden border border-slate-100 animate-in fade-in zoom-in duration-150">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="p-2 bg-indigo-50 rounded-lg text-indigo-600">
              <KeyRound className="w-5 h-5" />
            </div>
            <h2 className="text-lg font-semibold text-slate-900">Ganti Password Saya</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {errorMsg && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-start gap-2.5 text-rose-700 text-sm">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          {successMsg && (
            <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl flex items-start gap-2.5 text-emerald-700 text-sm">
              <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{successMsg}</span>
            </div>
          )}

          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Password Saat Ini
            </label>
            <Input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              placeholder="Masukkan password lama"
              required
              disabled={isSubmitting || !!successMsg}
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Password Baru
            </label>
            <Input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Minimal 6 karakter"
              required
              disabled={isSubmitting || !!successMsg}
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Konfirmasi Password Baru
            </label>
            <Input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Ulangi password baru"
              required
              disabled={isSubmitting || !!successMsg}
            />
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Batal
            </Button>
            <Button type="submit" disabled={isSubmitting || !!successMsg}>
              {isSubmitting ? "Menyimpan..." : "Perbarui Password"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Export `ChangePasswordModal` in `frontend/src/features/users/index.ts`**

Update `frontend/src/features/users/index.ts`:
```typescript
export * from "./types";
export * from "./api/users.api";
export * from "./components/CreateUserModal";
export * from "./components/EditUserModal";
export * from "./components/ResetPasswordModal";
export * from "./components/DeleteUserModal";
export * from "./components/ChangePasswordModal";
export { PenggunaPage, default } from "./pages/PenggunaPage";
```

- [ ] **Step 3: Integrate `ChangePasswordModal` into `frontend/src/components/layout/Header.tsx`**

In `frontend/src/components/layout/Header.tsx`:
1. Import `KeyRound` from `"lucide-react"`.
2. Import `ChangePasswordModal` from `@/features/users`.
3. Add state: `const [isChangePasswordOpen, setIsChangePasswordOpen] = useState(false);`.
4. Add a button next to the user badge and render `<ChangePasswordModal isOpen={isChangePasswordOpen} onClose={() => setIsChangePasswordOpen(false)} />`.

```tsx
// Inside Header component return:
<div className="flex items-center gap-3 sm:gap-4">
  {/* Notification bell button */}
  <Link ... />

  {/* Dynamic User Profile Badge */}
  <div className="flex items-center gap-2 bg-slate-300 pl-3.5 pr-1.5 py-1.5 rounded-full text-xs font-medium shadow-sm">
    <div className="flex flex-col items-start leading-none pr-1">
      <span className="font-semibold">{user?.username || "Pengguna"}</span>
      <span className={`text-[10px] font-bold uppercase mt-0.5 ${isAdmin ? "text-indigo-400" : "text-emerald-400"}`}>
        {user?.role || "Operator"}
      </span>
    </div>
    <div className={`w-7 h-7 rounded-full flex items-center justify-center text-white ${isAdmin ? "bg-indigo-600" : "bg-emerald-600"}`}>
      <User className="w-3.5 h-3.5" />
    </div>
  </div>

  {/* Change Password Button */}
  <button
    type="button"
    onClick={() => setIsChangePasswordOpen(true)}
    title="Ganti Password"
    aria-label="Ganti Password"
    className="p-2 rounded-xl text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 border border-slate-200 transition-colors cursor-pointer"
  >
    <KeyRound className="w-4 h-4" />
  </button>

  {/* Logout Button */}
  <button ... />
</div>

<ChangePasswordModal
  isOpen={isChangePasswordOpen}
  onClose={() => setIsChangePasswordOpen(false)}
/>
```

- [ ] **Step 4: Run frontend build to verify compilation**

Run:
```bash
npm --prefix frontend run build
```
Expected: Build succeeds with 0 errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/users/components/ChangePasswordModal.tsx frontend/src/features/users/index.ts frontend/src/components/layout/Header.tsx
git commit -m "feat(users): add self-service change password modal and header button"
```

---

### Task 7: Navigation Config & App Router Integration

**Files:**
- Modify: `frontend/src/config/navigation.ts`
- Modify: `frontend/src/app/router.tsx`

**Interfaces:**
- Consumes: `PenggunaPage` from `@/features/users`, `Users` icon from `lucide-react`
- Produces:
  - Sidebar entry for `/pengguna` (Admin only)
  - Protected route for `/pengguna` (Admin only)

- [ ] **Step 1: Update `frontend/src/config/navigation.ts`**

Add `Users` from `lucide-react` and add the navigation item with `requiredRole: "admin"`:
```typescript
import type { ComponentType } from "react";
import {
  LayoutDashboard,
  Network,
  Bell,
  FileText,
  Settings as SettingsIcon,
  Users,
} from "lucide-react";

export interface NavigationItem {
  id: string;
  label: string;
  path: string;
  icon: ComponentType<{ className?: string }>;
  requiredRole?: string;
}

export const navigationConfig: NavigationItem[] = [
  { id: "dashboard", label: "Dashboard", path: "/", icon: LayoutDashboard },
  { id: "lini-produksi", label: "Lini Produksi", path: "/lini-produksi", icon: Network },
  { id: "alarm", label: "Alarm", path: "/alarm", icon: Bell },
  { id: "laporan", label: "Laporan", path: "/laporan", icon: FileText },
  { id: "pengaturan", label: "Pengaturan", path: "/pengaturan", icon: SettingsIcon, requiredRole: "admin" },
  { id: "pengguna", label: "Pengguna", path: "/pengguna", icon: Users, requiredRole: "admin" },
];
```

- [ ] **Step 2: Update `frontend/src/app/router.tsx`**

In `frontend/src/app/router.tsx`:
1. Add lazy import:
```typescript
const PenggunaPage = lazy(() => import("@/features/users/pages/PenggunaPage"));
```
2. Add route inside `AppShell` children under `pengaturan`:
```typescript
      {
        path: "pengaturan",
        element: (
          <ProtectedRoute allowedRoles={["admin"]}>
            <Suspense fallback={<PageLoader />}>
              <PengaturanPage />
            </Suspense>
          </ProtectedRoute>
        ),
      },
      {
        path: "pengguna",
        element: (
          <ProtectedRoute allowedRoles={["admin"]}>
            <Suspense fallback={<PageLoader />}>
              <PenggunaPage />
            </Suspense>
          </ProtectedRoute>
        ),
      },
```

- [ ] **Step 3: Run full verification suite (Backend + Frontend)**

Run:
```bash
# 1. Backend tests
& "C:\Users\torino\AppData\Local\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe" run --with fastapi --with httpx --with sqlalchemy --with pytest --with pyjwt --with python-dotenv --with opencv-python-headless --with reportlab --with openpyxl pytest services/api/tests/ -v

# 2. Frontend build
npm --prefix frontend run build
```
Expected: All backend pytest suites pass, frontend Vite build succeeds cleanly with 0 TypeScript/ESLint errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/config/navigation.ts frontend/src/app/router.tsx
git commit -m "feat(navigation): integrate Pengguna page route and sidebar navigation"
```
