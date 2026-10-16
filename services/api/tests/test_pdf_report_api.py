import io
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api.src.db.models import Base, CountAggregate
from services.api.src.db.session import get_db
from services.api.src.main import app


@pytest.fixture
def pdf_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestingSession()
    t1 = datetime(2026, 10, 16, 7, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 10, 16, 8, 0, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 10, 16, 9, 0, 0, tzinfo=timezone.utc)

    db.add(
        CountAggregate(
            line_id="line-1",
            window_start=t1,
            window_end=t1 + timedelta(minutes=1),
            count=100,
            rate_per_min=100.0,
            confidence_avg=0.95,
            status="NORMAL",
        )
    )
    db.add(
        CountAggregate(
            line_id="line-1",
            window_start=t2,
            window_end=t2 + timedelta(minutes=1),
            count=120,
            rate_per_min=120.0,
            confidence_avg=0.98,
            status="NORMAL",
        )
    )
    db.add(
        CountAggregate(
            line_id="line-1",
            window_start=t3,
            window_end=t3 + timedelta(minutes=1),
            count=140,
            rate_per_min=140.0,
            confidence_avg=0.99,
            status="NORMAL",
        )
    )
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
    engine.dispose()


def test_export_pdf_report_with_records(pdf_client):
    res = pdf_client.get("/api/v1/reports/export?line_id=line-1&format=pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.headers["content-disposition"] == 'attachment; filename="report_line-1.pdf"'
    assert res.content.startswith(b"%PDF")


def test_export_pdf_report_empty_records(pdf_client):
    res = pdf_client.get("/api/v1/reports/export?line_id=line-empty&format=pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.headers["content-disposition"] == 'attachment; filename="report_line-empty.pdf"'
    assert res.content.startswith(b"%PDF")


def test_export_pdf_report_time_filtering(pdf_client):
    start_time = "2026-10-16T07:30:00Z"
    end_time = "2026-10-16T08:30:00Z"
    res = pdf_client.get(
        f"/api/v1/reports/export?line_id=line-1&format=pdf&start_time={start_time}&end_time={end_time}"
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.headers["content-disposition"] == 'attachment; filename="report_line-1.pdf"'
    assert res.content.startswith(b"%PDF")


def test_export_unsupported_format(pdf_client):
    res = pdf_client.get("/api/v1/reports/export?line_id=line-1&format=docx")
    assert res.status_code == 400
    assert res.json()["detail"] == "Unsupported format 'docx'. Only 'xlsx' and 'pdf' are supported."


def test_pdf_report_generator_unit_empty_and_nulls():
    from services.api.src.services.pdf_exporter import PDFReportGenerator

    generator = PDFReportGenerator()
    pdf_bytes = generator.generate_line_report("line-empty", [])
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")

    records_with_nulls = [
        {"window_start": None, "count": None, "rate_per_min": None, "status": None},
        {
            "window_start": datetime(2026, 10, 16, 8, 0, 0),
            "count": 10,
            "rate_per_min": 10.5,
            "status": "NORMAL",
        },
    ]
    pdf_bytes_nulls = generator.generate_line_report("line-nulls", records_with_nulls)
    assert isinstance(pdf_bytes_nulls, bytes)
    assert pdf_bytes_nulls.startswith(b"%PDF")


def test_pdf_report_generator_large_record_set():
    from services.api.src.services.pdf_exporter import PDFReportGenerator

    generator = PDFReportGenerator()
    records = [
        {
            "window_start": f"2026-10-16 08:{i:02d}",
            "count": i,
            "rate_per_min": float(i),
            "status": "NORMAL",
        }
        for i in range(65)
    ]
    pdf_bytes = generator.generate_line_report("line-large", records)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")

