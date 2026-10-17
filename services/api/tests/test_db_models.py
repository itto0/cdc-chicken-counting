from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from services.api.src.db.models import Base, Line


def test_line_model_extended_fields():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        line = Line(
            id="line-test",
            name="Test Conveyor",
            daily_target=50000,
            video_url="rtsp://192.168.1.10:554/live",
            line_coords="0,240,640,240",
            line_direction="right",
            is_active=True,
        )
        session.add(line)
        session.commit()

        retrieved = session.get(Line, "line-test")
        assert retrieved is not None
        assert retrieved.name == "Test Conveyor"
        assert retrieved.video_url == "rtsp://192.168.1.10:554/live"
        assert retrieved.line_coords == "0,240,640,240"
        assert retrieved.line_direction == "right"
        assert retrieved.is_active is True
        assert isinstance(retrieved.created_at, datetime)
