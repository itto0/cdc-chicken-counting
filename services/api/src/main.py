from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from services.api.src.api.alarms import router as alarms_router
from services.api.src.api.auth import router as auth_router
from services.api.src.api.counts import router as counts_router
from services.api.src.api.lines import router as lines_router
from services.api.src.api.live import router as live_router
from services.api.src.api.reports import router as reports_router
from services.api.src.api.summary import router as summary_router
from services.api.src.api.sync import router as sync_router
from services.api.src.db.models import Base
from services.api.src.db.session import engine


def init_db(target_engine=None) -> None:
    Base.metadata.create_all(bind=target_engine or engine)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    init_db()
    yield


app = FastAPI(
    title="Lihat.id Poultry Counter Data API",
    version="0.1.0",
    lifespan=lifespan,
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
