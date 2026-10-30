import math
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func
from sqlalchemy.orm import Session

from services.api.src.db.models import CountEvent, CountingBatch
from services.api.src.db.session import get_db

router = APIRouter(prefix="/api/v1/lines/{line_id}/batches", tags=["batches"])


class BatchItemResponse(BaseModel):
    batch_id: str
    line_id: str
    start_time: datetime
    finish_time: datetime | None = None
    total_count: int
    status: str

    model_config = ConfigDict(from_attributes=True)


class BatchListResponse(BaseModel):
    items: list[BatchItemResponse]
    total: int
    page: int
    page_size: int
    pages: int


class BatchDetailResponse(BaseModel):
    batch_id: str
    line_id: str
    start_time: datetime
    finish_time: datetime | None = None
    total_count: int
    status: str
    duration_seconds: float
    rate_per_minute: float
    events_count: int

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=BatchListResponse)
@router.get("/", response_model=BatchListResponse, include_in_schema=False)
def list_batches(
    line_id: str,
    status: Literal["ALL", "COMPLETED", "ACTIVE"] = "COMPLETED",
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> BatchListResponse:
    query = db.query(CountingBatch).filter(CountingBatch.line_id == line_id)

    if status != "ALL":
        query = query.filter(CountingBatch.status == status)

    if start_date is not None:
        query = query.filter(CountingBatch.start_time >= start_date)

    if end_date is not None:
        query = query.filter(CountingBatch.start_time <= end_date)

    total = query.count()
    offset = (page - 1) * page_size
    items = (
        query.order_by(CountingBatch.start_time.desc(), CountingBatch.id.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    pages = math.ceil(total / page_size) if total > 0 else 0

    return BatchListResponse(
        items=[BatchItemResponse.model_validate(b) for b in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/latest", response_model=BatchItemResponse | None)
def get_latest_batch(
    line_id: str,
    db: Session = Depends(get_db),
) -> BatchItemResponse | None:
    batch = (
        db.query(CountingBatch)
        .filter(CountingBatch.line_id == line_id)
        .order_by(CountingBatch.start_time.desc(), CountingBatch.id.desc())
        .first()
    )
    if not batch:
        return None

    return BatchItemResponse.model_validate(batch)


@router.get("/{batch_id}", response_model=BatchDetailResponse)
def get_batch_detail(
    line_id: str,
    batch_id: str,
    db: Session = Depends(get_db),
) -> BatchDetailResponse:
    batch = (
        db.query(CountingBatch)
        .filter(CountingBatch.line_id == line_id, CountingBatch.batch_id == batch_id)
        .first()
    )
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    events_count = (
        db.query(func.count(CountEvent.id))
        .filter(CountEvent.line_id == line_id, CountEvent.batch_id == batch.batch_id)
        .scalar()
        or 0
    )

    st = batch.start_time
    if st.tzinfo is None:
        st = st.replace(tzinfo=timezone.utc)

    if batch.finish_time:
        ft = batch.finish_time
        if ft.tzinfo is None:
            ft = ft.replace(tzinfo=timezone.utc)
    else:
        ft = datetime.now(timezone.utc)

    duration_seconds = max((ft - st).total_seconds(), 0.0)
    rate_per_minute = (
        round(batch.total_count / (duration_seconds / 60.0), 2)
        if duration_seconds > 0
        else 0.0
    )

    return BatchDetailResponse(
        batch_id=batch.batch_id,
        line_id=batch.line_id,
        start_time=batch.start_time,
        finish_time=batch.finish_time,
        total_count=batch.total_count,
        status=batch.status,
        duration_seconds=duration_seconds,
        rate_per_minute=rate_per_minute,
        events_count=events_count,
    )


batches_router = router
