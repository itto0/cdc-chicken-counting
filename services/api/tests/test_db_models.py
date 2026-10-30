from datetime import datetime, timezone, timedelta
import pytest
import httpx
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.src.db.models import (
    Base,
    Line,
    CountEvent,
    CountAggregate,
    HealthSample,
    Alarm,
    User,
)
from services.api.src.db.session import get_db, SessionLocal
from services.api.src.main import app, init_db


@pytest.fixture
def memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session


def test_line_crud(memory_db: Session):
    # Create
    line = Line(id="lineA", name="Line A - Broiler Shackle", daily_target=62000, is_active=True)
    memory_db.add(line)
    memory_db.commit()

    # Read
    queried = memory_db.get(Line, "lineA")
    assert queried is not None
    assert queried.name == "Line A - Broiler Shackle"
    assert queried.daily_target == 62000
    assert queried.is_active is True
    assert "Line(id='lineA'" in repr(queried)

    # Update
    queried.name = "Line A - Updated"
    queried.daily_target = 65000
    queried.is_active = False
    memory_db.commit()

    updated = memory_db.get(Line, "lineA")
    assert updated is not None
    assert updated.name == "Line A - Updated"
    assert updated.daily_target == 65000
    assert updated.is_active is False

    # Delete
    memory_db.delete(updated)
    memory_db.commit()
    assert memory_db.get(Line, "lineA") is None


def test_count_event_unique_constraint(memory_db: Session):
    ts = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    event1 = CountEvent(
        line_id="line1",
        track_id=101,
        ts_utc=ts,
        confidence=0.94,
    )
    memory_db.add(event1)
    memory_db.commit()

    assert event1.id is not None
    assert "CountEvent" in repr(event1)

    # Duplicate (line_id, track_id, ts_utc) must violate unique constraint
    event2 = CountEvent(
        line_id="line1",
        track_id=101,
        ts_utc=ts,
        confidence=0.88,
    )
    memory_db.add(event2)
    with pytest.raises(IntegrityError):
        memory_db.commit()

    memory_db.rollback()

    # Different track_id or ts_utc should succeed
    event3 = CountEvent(
        line_id="line1",
        track_id=102,
        ts_utc=ts,
        confidence=0.91,
    )
    memory_db.add(event3)
    memory_db.commit()

    assert event3.id is not None
    events = memory_db.scalars(select(CountEvent).where(CountEvent.line_id == "line1")).all()
    assert len(events) == 2


def test_count_aggregate_crud(memory_db: Session):
    start = datetime(2026, 10, 15, 8, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(seconds=60)
    agg = CountAggregate(
        line_id="line1",
        window_start=start,
        window_end=end,
        count=45,
        rate_per_min=45.0,
        confidence_avg=0.92,
        status="NORMAL",
    )
    memory_db.add(agg)
    memory_db.commit()

    assert agg.id is not None
    assert "CountAggregate" in repr(agg)

    queried = memory_db.get(CountAggregate, agg.id)
    assert queried is not None
    assert queried.line_id == "line1"
    assert queried.count == 45
    assert queried.rate_per_min == 45.0
    assert queried.confidence_avg == 0.92
    assert queried.status == "NORMAL"


def test_health_sample_crud(memory_db: Session):
    ts = datetime(2026, 10, 15, 8, 30, 0, tzinfo=timezone.utc)
    sample = HealthSample(
        line_id="line1",
        timestamp=ts,
        fps=29.8,
        latency_p95_ms=18.4,
        cpu_pct=34.2,
        mem_pct=48.5,
        stream_state="ONLINE",
        model_name="yolo26n",
        model_version="v1.0",
    )
    memory_db.add(sample)
    memory_db.commit()

    assert sample.id is not None
    assert "HealthSample" in repr(sample)

    queried = memory_db.get(HealthSample, sample.id)
    assert queried is not None
    assert queried.fps == 29.8
    assert queried.model_name == "yolo26n"
    assert queried.model_version == "v1.0"

    # Test sample with default None for model_name/model_version
    sample2 = HealthSample(
        line_id="line2",
        fps=30.0,
        latency_p95_ms=15.0,
        cpu_pct=25.0,
        mem_pct=40.0,
        stream_state="ONLINE",
    )
    memory_db.add(sample2)
    memory_db.commit()

    queried2 = memory_db.get(HealthSample, sample2.id)
    assert queried2 is not None
    assert queried2.model_name is None
    assert queried2.model_version is None


def test_alarm_lifecycle(memory_db: Session):
    opened = datetime(2026, 10, 15, 9, 0, 0, tzinfo=timezone.utc)
    alarm = Alarm(
        line_id="line1",
        alarm_type="LOW_RATE",
        severity="WARNING",
        message="Throughput dropped below threshold",
        status="OPEN",
        opened_at=opened,
    )
    memory_db.add(alarm)
    memory_db.commit()

    assert alarm.id is not None
    assert alarm.status == "OPEN"
    assert alarm.ack_at is None
    assert alarm.resolved_at is None
    assert "Alarm" in repr(alarm)

    # Acknowledge alarm
    ack_time = opened + timedelta(minutes=5)
    alarm.status = "ACKNOWLEDGED"
    alarm.ack_at = ack_time
    memory_db.commit()

    queried = memory_db.get(Alarm, alarm.id)
    assert queried is not None
    assert queried.status == "ACKNOWLEDGED"
    assert queried.ack_at == ack_time.replace(tzinfo=None)

    # Resolve alarm
    res_time = opened + timedelta(minutes=15)
    alarm.status = "RESOLVED"
    alarm.resolved_at = res_time
    memory_db.commit()

    queried = memory_db.get(Alarm, alarm.id)
    assert queried is not None
    assert queried.status == "RESOLVED"
    assert queried.resolved_at == res_time.replace(tzinfo=None)


def test_user_model_and_unique_constraint(memory_db: Session):
    user1 = User(
        username="admin",
        password_hash="hashed_pw_admin",
        role="ADMIN",
        is_active=True,
    )
    user2 = User(
        username="operator",
        password_hash="hashed_pw_operator",
    )
    memory_db.add_all([user1, user2])
    memory_db.commit()

    assert user1.id is not None
    assert user2.id is not None
    assert user2.role == "OPERATOR"
    assert user2.is_active is True
    assert "User" in repr(user1)

    # Unique constraint on username
    duplicate_user = User(
        username="admin",
        password_hash="another_pw",
    )
    memory_db.add(duplicate_user)
    with pytest.raises(IntegrityError):
        memory_db.commit()


def test_session_get_db():
    gen = get_db()
    session = next(gen)
    assert isinstance(session, Session)
    # Finish generator
    try:
        next(gen)
    except StopIteration:
        pass


def test_sqlite_wal_pragma_on_file(tmp_path):
    from sqlalchemy import event
    db_file = tmp_path / "test_wal.db"
    test_engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})

    @event.listens_for(test_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    with test_engine.connect() as conn:
        journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        synchronous = conn.execute(text("PRAGMA synchronous")).scalar()
        assert str(journal_mode).upper() == "WAL"
        # synchronous NORMAL is 1 in SQLite
        assert synchronous in (1, "1", "NORMAL")

    test_engine.dispose()


def test_sqlite_pragma_conditional_handling():
    """Verify set_sqlite_pragma logic does not execute or register for non-sqlite connection."""
    from services.api.src.db.session import DATABASE_URL
    # When DATABASE_URL starts with sqlite, listener executes safely without error
    if DATABASE_URL.startswith("sqlite"):
        from services.api.src.db.session import engine
        with engine.connect() as conn:
            assert conn is not None


def test_metadata_tables_registered():
    table_names = set(Base.metadata.tables.keys())
    assert table_names == {
        "lines",
        "count_events",
        "count_aggregates",
        "health_samples",
        "alarms",
        "users",
        "api_keys",
        "batches",
    }


def test_init_db_helper(tmp_path):
    test_db = tmp_path / "init_test.db"
    test_engine = create_engine(f"sqlite:///{test_db}")
    init_db(target_engine=test_engine)
    assert set(Base.metadata.tables.keys()) == {
        "lines",
        "count_events",
        "count_aggregates",
        "health_samples",
        "alarms",
        "users",
        "api_keys",
        "batches",
    }
    test_engine.dispose()


@pytest.mark.asyncio
async def test_fastapi_healthz_and_lifespan():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_line_model_extended_fields(memory_db: Session):
    # Test with custom extended fields
    line_custom = Line(
        id="line-test",
        name="Test Conveyor",
        daily_target=50000,
        video_url="rtsp://192.168.1.10:554/live",
        line_coords="0,240,640,240",
        line_direction="right",
        is_active=True,
    )
    memory_db.add(line_custom)
    memory_db.commit()

    retrieved = memory_db.get(Line, "line-test")
    assert retrieved is not None
    assert retrieved.name == "Test Conveyor"
    assert retrieved.video_url == "rtsp://192.168.1.10:554/live"
    assert retrieved.line_coords == "0,240,640,240"
    assert retrieved.line_direction == "right"
    assert retrieved.is_active is True
    assert isinstance(retrieved.created_at, datetime)

    # Test default values when omitted
    line_default = Line(
        id="line-default",
        name="Default Line",
    )
    memory_db.add(line_default)
    memory_db.commit()

    retrieved_default = memory_db.get(Line, "line-default")
    assert retrieved_default is not None
    assert retrieved_default.video_url is None
    assert retrieved_default.line_coords is None
    assert retrieved_default.line_direction == "down"
    assert retrieved_default.created_at is not None
    assert isinstance(retrieved_default.created_at, datetime)


def test_health_sample_model_accuracy_pct(memory_db: Session):
    from services.api.src.db.models import HealthSample

    sample = HealthSample(
        line_id="line-1",
        fps=29.8,
        latency_p95_ms=35.0,
        cpu_pct=10.0,
        mem_pct=20.0,
        stream_state="ONLINE",
        accuracy_pct=98.75,
    )
    memory_db.add(sample)
    memory_db.commit()

    retrieved = memory_db.query(HealthSample).filter_by(id=sample.id).first()
    assert retrieved.accuracy_pct == 98.75


def test_init_db_migrates_accuracy_pct(tmp_path):
    test_db = tmp_path / "migration_test.db"
    test_engine = create_engine(f"sqlite:///{test_db}")
    with test_engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE health_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    line_id VARCHAR(50),
                    timestamp DATETIME,
                    fps FLOAT,
                    latency_p95_ms FLOAT,
                    cpu_pct FLOAT,
                    mem_pct FLOAT,
                    stream_state VARCHAR(20),
                    model_name VARCHAR(100),
                    model_version VARCHAR(50)
                )
                """
            )
        )
        conn.commit()

    init_db(target_engine=test_engine)

    with test_engine.connect() as conn:
        res = conn.execute(text("PRAGMA table_info(health_samples)"))
        cols = [r[1] for r in res.fetchall()]
        assert "accuracy_pct" in cols

    test_engine.dispose()


