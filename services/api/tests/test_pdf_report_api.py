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


def test_export_pdf_report_all_lines(pdf_client):
    for param in ("all", "semua", "", None):
        url = "/api/v1/reports/export?format=pdf" if param is None else f"/api/v1/reports/export?line_id={param}&format=pdf"
        res = pdf_client.get(url)
        assert res.status_code == 200
        assert res.headers["content-type"] == "application/pdf"
        assert res.headers["content-disposition"] == 'attachment; filename="report_semua_lini.pdf"'
        assert res.content.startswith(b"%PDF")


def test_export_excel_report_all_lines(pdf_client):
    for param in ("all", "semua", "", None):
        url = "/api/v1/reports/export?format=xlsx" if param is None else f"/api/v1/reports/export?line_id={param}&format=xlsx"
        res = pdf_client.get(url)
        assert res.status_code == 200
        assert "application/vnd.openxmlformats-officedocument" in res.headers["content-type"]
        assert res.headers["content-disposition"] == 'attachment; filename="report_semua_lini.xlsx"'
        assert len(res.content) > 0


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
    from reportlab.platypus import Table
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
    elements = generator._build_elements("line-large", records)
    tables = [e for e in elements if isinstance(e, Table)]
    assert len(tables) >= 2
    records_table = tables[1]
    assert records_table.repeatRows == 1

    # Check footnote when records > 50
    has_footnote = any("first 50 intervals" in getattr(e, "text", "") for e in elements)
    assert has_footnote is True

    # Check no footnote when records <= 50
    elements_small = generator._build_elements("line-small", records[:50])
    has_footnote_small = any("first 50 intervals" in getattr(e, "text", "") for e in elements_small)
    assert has_footnote_small is False

    pdf_bytes = generator.generate_line_report("line-large", records)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")


def test_export_pdf_report_special_characters(pdf_client):
    res = pdf_client.get("/api/v1/reports/export?line_id=line%26test%3C1%3E&format=pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.headers["content-disposition"] == 'attachment; filename="report_line_test_1_.pdf"'
    assert res.content.startswith(b"%PDF")


def test_pdf_report_generator_special_characters():
    from services.api.src.services.pdf_exporter import PDFReportGenerator

    generator = PDFReportGenerator()
    pdf_bytes = generator.generate_line_report("line&test<1>", [])
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")

    # Also test tags that would trigger XML parse errors if unescaped
    pdf_bytes_unescaped = generator.generate_line_report("line<unclosed>&'\"test<foo>", [])
    assert isinstance(pdf_bytes_unescaped, bytes)
    assert pdf_bytes_unescaped.startswith(b"%PDF")


def test_pdf_report_generator_multiline_column_layout():
    from reportlab.platypus import Table
    from services.api.src.services.pdf_exporter import PDFReportGenerator

    generator = PDFReportGenerator()

    # 1. Multi-line via line_id="Semua Lini"
    elements_multi_1 = generator._build_elements("Semua Lini", [])
    tables_1 = [e for e in elements_multi_1 if isinstance(e, Table)]
    assert len(tables_1) == 2
    records_table_1 = tables_1[1]
    assert records_table_1._cellvalues[0] == ["Interval Start (WIB)", "Line", "Count", "Speed (cpm)", "Status"]
    assert records_table_1._argW == [120, 90, 80, 90, 80]

    # 2. Multi-line via line_id="all"
    elements_multi_2 = generator._build_elements("all", [])
    tables_2 = [e for e in elements_multi_2 if isinstance(e, Table)]
    assert tables_2[1]._cellvalues[0] == ["Interval Start (WIB)", "Line", "Count", "Speed (cpm)", "Status"]
    assert tables_2[1]._argW == [120, 90, 80, 90, 80]

    # 3. Multi-line via records having line_id
    records_with_line = [
        {"window_start": "2026-10-17 10:00", "line_id": "line-2", "count": 50, "rate_per_min": 50.0, "status": "NORMAL"}
    ]
    elements_multi_3 = generator._build_elements("line-custom", records_with_line)
    tables_3 = [e for e in elements_multi_3 if isinstance(e, Table)]
    assert tables_3[1]._cellvalues[0] == ["Interval Start (WIB)", "Line", "Count", "Speed (cpm)", "Status"]
    assert tables_3[1]._cellvalues[1] == ["2026-10-17 10:00", "line-2", "50", "50.0", "NORMAL"]
    assert tables_3[1]._argW == [120, 90, 80, 90, 80]

    # 4. Single-line without line_id in records and line_id not "all"/"semua lini"
    records_single = [
        {"window_start": "2026-10-17 10:00", "count": 50, "rate_per_min": 50.0, "status": "NORMAL"}
    ]
    elements_single = generator._build_elements("line-1", records_single)
    tables_single = [e for e in elements_single if isinstance(e, Table)]
    assert tables_single[1]._cellvalues[0] == ["Interval Start (WIB)", "Count", "Speed (cpm)", "Status"]
    assert tables_single[1]._cellvalues[1] == ["2026-10-17 10:00", "50", "50.0", "NORMAL"]
    assert tables_single[1]._argW == [180, 100, 120, 100]


def test_export_report_tie_breaking_order():
    import openpyxl
    from reportlab.platypus import Table
    from services.api.src.db.models import CountAggregate
    from services.api.src.api.reports import get_db
    from services.api.src.main import app

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestingSession()
    same_time = datetime(2026, 10, 17, 10, 0, 0, tzinfo=timezone.utc)
    # Add line-B first, then line-A
    db.add(CountAggregate(
        line_id="line-B",
        window_start=same_time,
        window_end=same_time + timedelta(minutes=1),
        count=200,
        rate_per_min=100.0,
        confidence_avg=0.95,
        status="NORMAL",
    ))
    db.add(CountAggregate(
        line_id="line-A",
        window_start=same_time,
        window_end=same_time + timedelta(minutes=1),
        count=150,
        rate_per_min=90.0,
        confidence_avg=0.95,
        status="NORMAL",
    ))
    db.commit()
    db.close()

    def override_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        res = client.get("/api/v1/reports/export?line_id=all&format=xlsx")
        assert res.status_code == 200
        wb = openpyxl.load_workbook(io.BytesIO(res.content))
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        # Header is row 0: ("Timestamp (WIB)", "Line", "Count", "Rate (birds/min)", "Status")
        # Row 1 must be line-A (tie breaker order asc), Row 2 must be line-B
        assert rows[1][1] == "line-A"
        assert rows[2][1] == "line-B"
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
