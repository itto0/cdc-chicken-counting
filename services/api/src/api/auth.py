from datetime import datetime, timezone
from typing import Callable, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from services.api.src.db.models import User, ApiKey
from services.api.src.db.session import get_db
from services.api.src.services.auth import (
    verify_password,
    create_access_token,
    decode_access_token,
    hash_api_key,
    generate_api_key,
    hash_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class UserDTO(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserDTO


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    role: Literal["OPERATOR", "ADMIN"] = "OPERATOR"

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name cannot be blank")
        return v

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, v: str) -> str:
        return v.strip().upper() if isinstance(v, str) else v


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
    last_used_at: Optional[datetime] = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    is_active: bool


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(..., min_length=6, max_length=128)
    role: Literal["admin", "operator", "ADMIN", "OPERATOR"] = "operator"
    is_active: bool = True

    @field_validator("username", mode="before")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if isinstance(v, str):
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


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalars(select(User).where(User.username == payload.username)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is inactive")

    token = create_access_token({"sub": user.username, "role": user.role, "uid": user.id})
    return LoginResponse(
        access_token=token,
        user=UserDTO(id=user.id, username=user.username, role=user.role, is_active=user.is_active),
    )


@router.get("/me", response_model=UserDTO)
def get_current_user(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    raw_key: Optional[str] = None
    if x_api_key is not None:
        if not x_api_key.strip():
            raise HTTPException(status_code=401, detail="Invalid or revoked API key")
        raw_key = x_api_key.strip()
    elif authorization and authorization.startswith("Bearer "):
        parts = authorization.split(" ", 1)
        if len(parts) == 2 and parts[1].strip().startswith("cdc_live_"):
            raw_key = parts[1].strip()

    if raw_key is not None:
        key_hash = hash_api_key(raw_key)
        key = db.scalars(select(ApiKey).where(ApiKey.key_hash == key_hash)).first()
        if not key or not key.is_active:
            raise HTTPException(status_code=401, detail="Invalid or revoked API key")
        user_dto = UserDTO(
            id=key.id,
            username=f"device:{key.name}",
            role=key.role,
            is_active=key.is_active,
        )
        try:
            key.last_used_at = datetime.now(timezone.utc)
            db.commit()
        except Exception:
            db.rollback()
        return user_dto

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    parts = authorization.split(" ", 1)
    if len(parts) < 2 or not parts[1].strip():
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = parts[1].strip()
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.scalars(select(User).where(User.username == payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is inactive")

    return UserDTO(id=user.id, username=user.username, role=user.role, is_active=user.is_active)


@router.put("/password", response_model=dict)
def change_self_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: UserDTO = Depends(get_current_user),
):
    if current_user.username.startswith("device:"):
        raise HTTPException(status_code=404, detail="User not found")

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


def require_role(allowed_roles: list[str]) -> Callable[..., UserDTO]:
    def role_checker(current_user: UserDTO = Depends(get_current_user)) -> UserDTO:
        user_role = (current_user.role or "").strip().lower()
        normalized_allowed = [r.strip().lower() for r in allowed_roles]
        if user_role not in normalized_allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Operation not permitted. Required role: {', '.join(allowed_roles)}",
            )
        return current_user

    return role_checker


@router.post("/api-keys", response_model=ApiKeyCreateResponse, status_code=201)
def create_api_key_endpoint(
    payload: ApiKeyCreateRequest,
    db: Session = Depends(get_db),
    current_user: UserDTO = Depends(require_role(["admin"])),
):
    raw_key, key_hash, prefix = generate_api_key()
    api_key_obj = ApiKey(
        name=payload.name,
        key_hash=key_hash,
        prefix=prefix,
        role=payload.role,
    )
    db.add(api_key_obj)
    db.commit()
    db.refresh(api_key_obj)
    return ApiKeyCreateResponse(
        id=api_key_obj.id,
        name=api_key_obj.name,
        api_key=raw_key,
        prefix=api_key_obj.prefix,
        role=api_key_obj.role,
        created_at=api_key_obj.created_at,
    )


@router.get("/api-keys", response_model=list[ApiKeyResponse])
def list_api_keys(
    db: Session = Depends(get_db),
    current_user: UserDTO = Depends(require_role(["admin"])),
):
    keys = db.scalars(select(ApiKey).order_by(ApiKey.id)).all()
    return [
        ApiKeyResponse(
            id=k.id,
            name=k.name,
            prefix=k.prefix,
            role=k.role,
            is_active=k.is_active,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
        )
        for k in keys
    ]


@router.delete("/api-keys/{key_id}", response_model=ApiKeyResponse)
def revoke_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: UserDTO = Depends(require_role(["admin"])),
):
    key = db.get(ApiKey, key_id)
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    key.is_active = False
    db.commit()
    db.refresh(key)
    return ApiKeyResponse(
        id=key.id,
        name=key.name,
        prefix=key.prefix,
        role=key.role,
        is_active=key.is_active,
        created_at=key.created_at,
        last_used_at=key.last_used_at,
    )


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
    existing = db.scalars(
        select(User).where(func.lower(User.username) == payload.username.lower())
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    new_user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role.lower(),
        is_active=payload.is_active,
    )
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Username already exists")
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
    if (
        target_user.id == current_user.id
        and not current_user.username.startswith("device:")
        and payload.is_active is False
    ):
        raise HTTPException(status_code=400, detail="Cannot deactivate own account")

    # Invariant: Cannot deactivate or demote last active admin
    is_target_active_admin = (target_user.role.lower() == "admin") and target_user.is_active
    will_be_demoted = payload.role is not None and payload.role.lower() != "admin"
    will_be_deactivated = payload.is_active is False

    if is_target_active_admin and (will_be_demoted or will_be_deactivated):
        active_admin_count = db.scalar(
            select(func.count(User.id)).where(
                func.lower(User.role) == "admin",
                User.is_active.is_(True),
            )
        )
        if active_admin_count is not None and active_admin_count <= 1:
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
    if user_id == current_user.id and not current_user.username.startswith("device:"):
        raise HTTPException(status_code=400, detail="Cannot delete own account")

    target_user = db.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Invariant: Cannot delete the last remaining active admin
    if target_user.role.lower() == "admin" and target_user.is_active:
        active_admin_count = db.scalar(
            select(func.count(User.id)).where(
                func.lower(User.role) == "admin",
                User.is_active.is_(True),
            )
        )
        if active_admin_count is not None and active_admin_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the last remaining active admin",
            )

    db.delete(target_user)
    db.commit()
    return {"message": "User deleted successfully"}

