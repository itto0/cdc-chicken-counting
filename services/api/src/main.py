from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from services.api.src.api.live import router as live_router
from services.api.src.api.reports import router as reports_router
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


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
