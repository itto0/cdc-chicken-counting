import re
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.src.db.models import CountAggregate
from services.api.src.db.session import get_db
from services.api.src.services.exporter import ExcelReportGenerator
from services.api.src.services.pdf_exporter import PDFReportGenerator

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
    line_id: str = Query(default="all"),
    format: str = Query(default="xlsx"),
    start_time: str | None = Query(default=None),
    end_time: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> Response:
    fmt = format.lower()
    if fmt not in ("xlsx", "pdf"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{format}'. Only 'xlsx' and 'pdf' are supported.",
        )

    is_all_lines = (line_id.lower().strip() in ("all", "semua", "")) if line_id else True
    query = select(CountAggregate)
    if not is_all_lines:
        query = query.where(CountAggregate.line_id == line_id)

    if start_time is not None:
        start_dt = _parse_filter_datetime(start_time)
        query = query.where(CountAggregate.window_start >= start_dt)

    if end_time is not None:
        end_dt = _parse_filter_datetime(end_time)
        query = query.where(CountAggregate.window_start <= end_dt)

    query = query.order_by(CountAggregate.window_start.asc(), CountAggregate.line_id.asc())
    aggregates = db.scalars(query).all()

    records = [
        {
            "window_start": agg.window_start,
            "line_id": agg.line_id,
            "count": agg.count,
            "rate_per_min": agg.rate_per_min,
            "status": agg.status,
        }
        for agg in aggregates
    ]

    display_line_name = "Semua Lini" if is_all_lines else line_id
    clean_line_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", line_id)
    safe_filename = "report_semua_lini" if is_all_lines else f"report_{clean_line_id}"

    if fmt == "pdf":
        pdf_generator = PDFReportGenerator()
        pdf_bytes = pdf_generator.generate_line_report(line_id=display_line_name, records=records)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{safe_filename}.pdf"'},
        )

    generator = ExcelReportGenerator()
    xlsx_bytes = generator.generate_line_report(line_id=display_line_name, records=records)

    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}.xlsx"'},
    )
