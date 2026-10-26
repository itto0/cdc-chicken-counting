import sqlite3
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from services.api.src.db.models import Base, Line
from services.api.src.main import init_db


def test_line_model_has_threshold_columns():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        line = Line(
            id="line-test",
            name="Test Line",
            daily_target=50000,
            rate_warning_threshold=125.0,
            rate_critical_threshold=105.0,
        )
        session.add(line)
        session.commit()

        queried = session.get(Line, "line-test")
        assert queried is not None
        assert queried.rate_warning_threshold == 125.0
        assert queried.rate_critical_threshold == 105.0


def test_init_db_migrates_existing_lines_table(tmp_path):
    db_file = tmp_path / "test_migration.db"
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    # Create legacy lines table without threshold columns
    cursor.execute("""
        CREATE TABLE lines (
            id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            daily_target INTEGER NOT NULL DEFAULT 60000,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            video_url VARCHAR(255),
            line_coords VARCHAR(100),
            line_direction VARCHAR(20) DEFAULT 'down',
            created_at DATETIME
        )
    """)
    cursor.execute(
        "INSERT INTO lines (id, name, daily_target, is_active) VALUES ('line-legacy', 'Legacy Line', 60000, 1)"
    )
    conn.commit()
    conn.close()

    # Run init_db with engine pointing to this db
    engine = create_engine(f"sqlite:///{db_file}")
    init_db(target_engine=engine)

    # Verify columns were added and legacy row is readable
    with Session(engine) as session:
        line = session.get(Line, "line-legacy")
        assert line is not None
        assert line.rate_warning_threshold is None
        assert line.rate_critical_threshold is None

    # Calling init_db again on the migrated db must be fully idempotent
    init_db(target_engine=engine)


def test_init_db_idempotency_multiple_calls(tmp_path):
    db_file = tmp_path / "test_idempotent.db"
    engine = create_engine(f"sqlite:///{db_file}")

    # Call init_db first time (creates tables, columns, seed rows)
    init_db(target_engine=engine)

    # Call init_db second and third time (must be idempotent without throwing errors)
    init_db(target_engine=engine)
    init_db(target_engine=engine)

    with Session(engine) as session:
        lines = session.query(Line).all()
        assert len(lines) >= 2
        line1 = session.get(Line, "line-1")
        assert line1 is not None
        assert line1.rate_warning_threshold is None
        assert line1.rate_critical_threshold is None

