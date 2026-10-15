from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.src.db.models import CountAggregate
from services.api.src.db.session import get_db
from services.api.src.services.exporter import ExcelReportGenerator

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def _parse_filter_datetime(dt_str: str) -> datetime:
    try:
        clean_str = dt_str.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid datetime format: '{dt_str}'. Error: {exc}",
        ) from exc


@router.get("/export")
def export_report(
    line_id: str = Query(default="lineA"),
    format: str = Query(default="xlsx"),
    start_time: str | None = Query(default=None),
    end_time: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> Response:
    if format.lower() != "xlsx":
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{format}'. Only 'xlsx' is supported.",
        )

    query = select(CountAggregate).where(CountAggregate.line_id == line_id)

    if start_time is not None:
        start_dt = _parse_filter_datetime(start_time)
        query = query.where(CountAggregate.window_start >= start_dt)

    if end_time is not None:
        end_dt = _parse_filter_datetime(end_time)
        query = query.where(CountAggregate.window_start <= end_dt)

    query = query.order_by(CountAggregate.window_start.asc())
    aggregates = db.scalars(query).all()

    records = [
        {
            "window_start": agg.window_start,
            "count": agg.count,
            "rate_per_min": agg.rate_per_min,
            "status": agg.status,
        }
        for agg in aggregates
    ]

    generator = ExcelReportGenerator()
    xlsx_bytes = generator.generate_line_report(line_id=line_id, records=records)

    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="report_{line_id}.xlsx"'},
    )
