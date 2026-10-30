from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from services.api.src.db.models import Base, Line, CountEvent, CountingBatch
from services.api.src.main import init_db


def test_counting_batch_model_creation():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    line = Line(id="line-1", name="Line 1")
    session.add(line)
    session.commit()

    now = datetime.now(timezone.utc)
    batch = CountingBatch(
        batch_id="batch_001",
        line_id="line-1",
        start_time=now,
        finish_time=now,
        total_count=42,
        status="COMPLETED",
    )
    session.add(batch)

    event = CountEvent(
        track_id=10,
        ts_utc=now,
        confidence=0.98,
        line_id="line-1",
        class_name="chicken",
        batch_id="batch_001",
    )
    session.add(event)
    session.commit()

    saved_batch = session.query(CountingBatch).filter_by(batch_id="batch_001").first()
    assert saved_batch is not None
    assert saved_batch.total_count == 42
    assert saved_batch.status == "COMPLETED"

    saved_event = session.query(CountEvent).filter_by(track_id=10).first()
    assert saved_event is not None
    assert saved_event.batch_id == "batch_001"


def test_init_db_migrates_events_batch_id():
    engine = create_engine("sqlite:///:memory:")
    # Simulate old schema without batch_id in events
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE lines (id VARCHAR(64) PRIMARY KEY, name VARCHAR(128) NOT NULL, status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE', target_speed FLOAT NOT NULL DEFAULT 60.0, created_at TIMESTAMP NOT NULL, updated_at TIMESTAMP NOT NULL)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, track_id INTEGER NOT NULL, ts_utc TIMESTAMP NOT NULL, confidence FLOAT NOT NULL, line_id VARCHAR(64) NOT NULL, class_name VARCHAR(64) NOT NULL, created_at TIMESTAMP NOT NULL)"
            )
        )

    # Run init_db on the simulated engine
    init_db(target_engine=engine)

    inspector = inspect(engine)
    event_cols = [c["name"] for c in inspector.get_columns("events")]
    assert "batch_id" in event_cols
    assert "batches" in inspector.get_table_names()


def test_line_batches_relationship_and_cascade():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    line = Line(id="line-2", name="Line 2")
    session.add(line)
    session.commit()

    now = datetime.now(timezone.utc)
    batch1 = CountingBatch(
        batch_id="b_01",
        line_id="line-2",
        start_time=now,
        total_count=10,
        status="ACTIVE",
    )
    batch2 = CountingBatch(
        batch_id="b_02",
        line_id="line-2",
        start_time=now,
        total_count=20,
        status="COMPLETED",
    )
    session.add_all([batch1, batch2])
    session.commit()

    # Verify back-reference and relationship
    reloaded_line = session.get(Line, "line-2")
    assert reloaded_line is not None
    assert len(reloaded_line.batches) == 2
    assert {b.batch_id for b in reloaded_line.batches} == {"b_01", "b_02"}
    assert batch1.line.id == "line-2"

    # Verify cascade delete
    session.delete(reloaded_line)
    session.commit()
    assert session.query(CountingBatch).filter_by(line_id="line-2").count() == 0


def test_init_db_migrates_count_events_batch_id_and_is_idempotent():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE count_events (id INTEGER PRIMARY KEY AUTOINCREMENT, line_id VARCHAR(50) NOT NULL, track_id INTEGER NOT NULL, ts_utc DATETIME NOT NULL, confidence FLOAT NOT NULL)"
            )
        )

    # First migration run
    init_db(target_engine=engine)
    inspector = inspect(engine)
    cols = [c["name"] for c in inspector.get_columns("count_events")]
    assert "batch_id" in cols
    assert "batches" in inspector.get_table_names()

    # Second migration run should be idempotent and not raise error
    init_db(target_engine=engine)
    inspector = inspect(engine)
    cols = [c["name"] for c in inspector.get_columns("count_events")]
    assert "batch_id" in cols

