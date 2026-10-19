from typing import Callable, Optional
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from services.api.src.db.models import User
from services.api.src.db.session import get_db
from services.api.src.services.auth import (
    verify_password,
    create_access_token,
    decode_access_token,
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
def get_current_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
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

