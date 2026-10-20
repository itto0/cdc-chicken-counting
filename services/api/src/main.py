import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.env import init_env

init_env()

from services.api.src.api.alarms import router as alarms_router
from services.api.src.api.auth import router as auth_router
from services.api.src.api.counts import router as counts_router
from services.api.src.api.lines import router as lines_router
from services.api.src.api.live import router as live_router
from services.api.src.api.reports import router as reports_router
from services.api.src.api.summary import router as summary_router
from services.api.src.api.sync import router as sync_router
from services.api.src.db.models import Base, Line, User
from services.api.src.db.session import engine
from services.api.src.services.auth import hash_password
from sqlalchemy import select
from sqlalchemy.orm import Session


def init_db(target_engine=None) -> None:
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)
    with Session(eng) as session:
        if not session.get(Line, "line-1"):
            session.add(
                Line(
                    id="line-1",
                    name="Lini Konveyor 1",
                    daily_target=62000,
                    line_direction="right",
                    line_coords="960,200,960,950",
                    is_active=True,
                )
            )
        if not session.get(Line, "lineA"):
            session.add(
                Line(
                    id="lineA",
                    name="Lini Konveyor A",
                    daily_target=62000,
                    line_direction="down",
                    line_coords="0,240,640,240",
                    is_active=True,
                )
            )

        admin_user = session.execute(select(User).where(User.username == "admin")).scalar_one_or_none()
        if not admin_user:
            session.add(
                User(
                    username="admin",
                    password_hash=hash_password("admin123"),
                    role="admin",
                    is_active=True,
                )
            )
        operator_user = session.execute(select(User).where(User.username == "operator")).scalar_one_or_none()
        if not operator_user:
            session.add(
                User(
                    username="operator",
                    password_hash=hash_password("operator123"),
                    role="operator",
                    is_active=True,
                )
            )

        session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    init_db()
    yield


def get_cors_origins(env_origins: str | None = None) -> list[str]:
    raw = env_origins if env_origins is not None else os.getenv("CORS_ORIGINS", "*")
    if not raw or raw.strip() == "*":
        return ["*"]
    origins = [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]
    return origins if origins else ["*"]


app = FastAPI(
    title="Lihat.id Poultry Counter Data API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sync_router)
app.include_router(live_router)
app.include_router(reports_router)
app.include_router(summary_router)
app.include_router(counts_router)
app.include_router(lines_router)
app.include_router(alarms_router)
app.include_router(auth_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
