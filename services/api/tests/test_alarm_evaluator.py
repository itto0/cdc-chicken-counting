import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from services.api.src.db.models import Base, Alarm
from services.api.src.services.alarms import AlarmEvaluator
from shared.contracts import HealthSampleDTO


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session


def test_alarm_evaluator_triggers_critical_for_low_rate(db_session: Session):
    evaluator = AlarmEvaluator(db=db_session)
    alarm = evaluator.evaluate_rate(line_id="lineA", rate_per_min=105.0)

    assert alarm is not None
    assert alarm.severity == "CRITICAL"
    assert alarm.alarm_type == "LOW_RATE"
    assert alarm.status == "OPEN"
    assert "105.0" in alarm.message

    saved = db_session.query(Alarm).filter_by(line_id="lineA").first()
    assert saved is not None
    assert saved.severity == "CRITICAL"
    assert saved.alarm_type == "LOW_RATE"


def test_alarm_evaluator_triggers_warning_for_moderate_rate(db_session: Session):
    evaluator = AlarmEvaluator(db=db_session)
    alarm = evaluator.evaluate_rate(line_id="lineA", rate_per_min=120.0)

    assert alarm is not None
    assert alarm.severity == "WARNING"
    assert alarm.alarm_type == "LOW_RATE"
    assert alarm.status == "OPEN"


def test_alarm_evaluator_boundary_rates(db_session: Session):
    evaluator = AlarmEvaluator(db=db_session)

    # 110.0 should be WARNING (110.0 <= rate < 130.0)
    alarm_110 = evaluator.evaluate_rate(line_id="line110", rate_per_min=110.0)
    assert alarm_110 is not None
    assert alarm_110.severity == "WARNING"

    # 109.9 should be CRITICAL (< 110.0)
    alarm_109 = evaluator.evaluate_rate(line_id="line109", rate_per_min=109.9)
    assert alarm_109 is not None
    assert alarm_109.severity == "CRITICAL"

    # 130.0 should be None (>= 130.0)
    alarm_130 = evaluator.evaluate_rate(line_id="line130", rate_per_min=130.0)
    assert alarm_130 is None

    # 129.9 should be WARNING (< 130.0)
    alarm_129 = evaluator.evaluate_rate(line_id="line129", rate_per_min=129.9)
    assert alarm_129 is not None
    assert alarm_129.severity == "WARNING"


def test_alarm_evaluator_no_alarm_for_normal_rate(db_session: Session):
    evaluator = AlarmEvaluator(db=db_session)
    alarm = evaluator.evaluate_rate(line_id="lineA", rate_per_min=140.0)

    assert alarm is None
    alarms = db_session.query(Alarm).all()
    assert len(alarms) == 0


def test_alarm_evaluator_prevents_duplicate_open_rate_alarm(db_session: Session):
    evaluator = AlarmEvaluator(db=db_session)

    first_alarm = evaluator.evaluate_rate(line_id="lineA", rate_per_min=120.0)
    assert first_alarm is not None
    first_id = first_alarm.id

    # Second call with same line_id and severity
    second_alarm = evaluator.evaluate_rate(line_id="lineA", rate_per_min=122.0)
    assert second_alarm is not None
    assert second_alarm.id == first_id

    # Only one record in database
    all_alarms = db_session.query(Alarm).filter_by(line_id="lineA").all()
    assert len(all_alarms) == 1


def test_alarm_evaluator_updates_severity_on_existing_open_alarm(db_session: Session):
    evaluator = AlarmEvaluator(db=db_session)

    # First call: WARNING
    alarm1 = evaluator.evaluate_rate(line_id="lineA", rate_per_min=120.0)
    assert alarm1 is not None
    assert alarm1.severity == "WARNING"
    alarm_id = alarm1.id

    # Second call: Drops below 110.0 -> Escalate to CRITICAL
    alarm2 = evaluator.evaluate_rate(line_id="lineA", rate_per_min=95.0)
    assert alarm2 is not None
    assert alarm2.id == alarm_id
    assert alarm2.severity == "CRITICAL"
    assert "95.0" in alarm2.message

    # Verify single DB row updated
    all_alarms = db_session.query(Alarm).filter_by(line_id="lineA").all()
    assert len(all_alarms) == 1
    assert all_alarms[0].severity == "CRITICAL"


def test_alarm_evaluator_creates_new_alarm_if_previous_resolved(db_session: Session):
    evaluator = AlarmEvaluator(db=db_session)

    alarm1 = evaluator.evaluate_rate(line_id="lineA", rate_per_min=100.0)
    assert alarm1 is not None

    # Resolve the first alarm
    alarm1.status = "RESOLVED"
    db_session.commit()

    # Next evaluation triggers a new open alarm
    alarm2 = evaluator.evaluate_rate(line_id="lineA", rate_per_min=105.0)
    assert alarm2 is not None
    assert alarm2.id != alarm1.id
    assert alarm2.status == "OPEN"

    all_alarms = db_session.query(Alarm).filter_by(line_id="lineA").all()
    assert len(all_alarms) == 2


def test_alarm_evaluator_independent_lines(db_session: Session):
    evaluator = AlarmEvaluator(db=db_session)

    alarm_a = evaluator.evaluate_rate(line_id="lineA", rate_per_min=100.0)
    alarm_b = evaluator.evaluate_rate(line_id="lineB", rate_per_min=105.0)

    assert alarm_a is not None
    assert alarm_b is not None
    assert alarm_a.id != alarm_b.id
    assert alarm_a.line_id == "lineA"
    assert alarm_b.line_id == "lineB"

    assert db_session.query(Alarm).count() == 2


def test_evaluate_health_offline_triggers_critical(db_session: Session):
    evaluator = AlarmEvaluator(db=db_session)
    health = HealthSampleDTO(
        fps=0.0,
        latency_p95_ms=0.0,
        cpu_pct=15.0,
        mem_pct=25.0,
        stream_state="OFFLINE",
    )

    alarm = evaluator.evaluate_health(line_id="lineA", health=health)
    assert alarm is not None
    assert alarm.severity == "CRITICAL"
    assert alarm.alarm_type == "STREAM_OFFLINE"
    assert alarm.status == "OPEN"
    assert "offline" in alarm.message.lower()

    saved = db_session.query(Alarm).filter_by(line_id="lineA", alarm_type="STREAM_OFFLINE").first()
    assert saved is not None
    assert saved.severity == "CRITICAL"


def test_evaluate_health_degraded_stream_triggers_warning(db_session: Session):
    evaluator = AlarmEvaluator(db=db_session)
    health = HealthSampleDTO(
        fps=25.0,
        latency_p95_ms=40.0,
        cpu_pct=20.0,
        mem_pct=30.0,
        stream_state="DEGRADED",
    )

    alarm = evaluator.evaluate_health(line_id="lineA", health=health)
    assert alarm is not None
    assert alarm.severity == "WARNING"
    assert alarm.alarm_type == "LOW_FPS"


def test_evaluate_health_low_fps_triggers_warning(db_session: Session):
    evaluator = AlarmEvaluator(db=db_session)
    health = HealthSampleDTO(
        fps=8.5,
        latency_p95_ms=50.0,
        cpu_pct=35.0,
        mem_pct=40.0,
        stream_state="ONLINE",
    )

    alarm = evaluator.evaluate_health(line_id="lineA", health=health)
    assert alarm is not None
    assert alarm.severity == "WARNING"
    assert alarm.alarm_type == "LOW_FPS"
    assert "8.5" in alarm.message


def test_evaluate_health_high_latency_triggers_warning(db_session: Session):
    evaluator = AlarmEvaluator(db=db_session)
    health = HealthSampleDTO(
        fps=30.0,
        latency_p95_ms=185.0,
        cpu_pct=40.0,
        mem_pct=45.0,
        stream_state="ONLINE",
    )

    alarm = evaluator.evaluate_health(line_id="lineA", health=health)
    assert alarm is not None
    assert alarm.severity == "WARNING"
    assert alarm.alarm_type == "HIGH_LATENCY"
    assert "185.0" in alarm.message


def test_evaluate_health_normal_returns_none(db_session: Session):
    evaluator = AlarmEvaluator(db=db_session)
    health = HealthSampleDTO(
        fps=30.0,
        latency_p95_ms=45.0,
        cpu_pct=20.0,
        mem_pct=30.0,
        stream_state="ONLINE",
    )

    alarm = evaluator.evaluate_health(line_id="lineA", health=health)
    assert alarm is None
    assert db_session.query(Alarm).count() == 0


def test_evaluate_health_boundary_values(db_session: Session):
    evaluator = AlarmEvaluator(db=db_session)

    # fps = 10.0 and latency = 150.0 should be normal (no alarm)
    normal_health = HealthSampleDTO(
        fps=10.0,
        latency_p95_ms=150.0,
        cpu_pct=20.0,
        mem_pct=30.0,
        stream_state="ONLINE",
    )
    assert evaluator.evaluate_health(line_id="line1", health=normal_health) is None

    # fps = 9.9 triggers LOW_FPS
    low_fps_health = HealthSampleDTO(
        fps=9.9,
        latency_p95_ms=150.0,
        cpu_pct=20.0,
        mem_pct=30.0,
        stream_state="ONLINE",
    )
    low_fps_alarm = evaluator.evaluate_health(line_id="line2", health=low_fps_health)
    assert low_fps_alarm is not None
    assert low_fps_alarm.alarm_type == "LOW_FPS"

    # latency = 150.1 triggers HIGH_LATENCY
    high_lat_health = HealthSampleDTO(
        fps=10.0,
        latency_p95_ms=150.1,
        cpu_pct=20.0,
        mem_pct=30.0,
        stream_state="ONLINE",
    )
    high_lat_alarm = evaluator.evaluate_health(line_id="line3", health=high_lat_health)
    assert high_lat_alarm is not None
    assert high_lat_alarm.alarm_type == "HIGH_LATENCY"


def test_evaluate_health_prevents_duplicate_open_alarm(db_session: Session):
    evaluator = AlarmEvaluator(db=db_session)
    health = HealthSampleDTO(
        fps=0.0,
        latency_p95_ms=0.0,
        cpu_pct=20.0,
        mem_pct=30.0,
        stream_state="OFFLINE",
    )

    alarm1 = evaluator.evaluate_health(line_id="lineA", health=health)
    alarm2 = evaluator.evaluate_health(line_id="lineA", health=health)

    assert alarm1 is not None
    assert alarm2 is not None
    assert alarm1.id == alarm2.id

    assert db_session.query(Alarm).filter_by(line_id="lineA").count() == 1


def test_alarm_evaluator_uses_custom_line_thresholds(db_session: Session):
    evaluator = AlarmEvaluator(db=db_session)
    # Line custom threshold: warning 140, critical 120
    # A rate of 125 is below warning 140 -> should trigger WARNING
    alarm = evaluator.evaluate_rate(
        line_id="customLine",
        rate_per_min=125.0,
        warning_threshold=140.0,
        critical_threshold=120.0,
    )
    assert alarm is not None
    assert alarm.severity == "WARNING"

    # A rate of 115 is below critical 120 -> should trigger CRITICAL
    alarm_crit = evaluator.evaluate_rate(
        line_id="customLine2",
        rate_per_min=115.0,
        warning_threshold=140.0,
        critical_threshold=120.0,
    )
    assert alarm_crit is not None
    assert alarm_crit.severity == "CRITICAL"


def test_alarm_evaluator_auto_resolves_low_rate_on_recovery(db_session: Session):
    evaluator = AlarmEvaluator(db=db_session)

    # 1. Trigger WARNING alarm at 120.0 (default warning 130)
    alarm = evaluator.evaluate_rate(line_id="lineRecover", rate_per_min=120.0)
    assert alarm is not None
    assert alarm.status == "OPEN"

    # 2. Rate recovers to 135.0 (>= 130.0)
    recovered_alarm = evaluator.evaluate_rate(line_id="lineRecover", rate_per_min=135.0)
    assert recovered_alarm is None

    # Verify existing DB alarm is now RESOLVED
    saved = db_session.query(Alarm).filter_by(line_id="lineRecover", alarm_type="LOW_RATE").first()
    assert saved is not None
    assert saved.status == "RESOLVED"
    assert saved.resolved_at is not None


def test_alarm_evaluator_auto_resolves_low_rate_with_custom_threshold(db_session: Session):
    evaluator = AlarmEvaluator(db=db_session)
    # Custom: warning 140, critical 120
    # 1. Rate 115 is CRITICAL
    alarm = evaluator.evaluate_rate(
        line_id="customRec",
        rate_per_min=115.0,
        warning_threshold=140.0,
        critical_threshold=120.0,
    )
    assert alarm is not None
    assert alarm.severity == "CRITICAL"
    assert alarm.status == "OPEN"

    # 2. Rate recovers to 130.0 (still < 140.0 warning) -> updates to WARNING, still OPEN
    alarm_mid = evaluator.evaluate_rate(
        line_id="customRec",
        rate_per_min=130.0,
        warning_threshold=140.0,
        critical_threshold=120.0,
    )
    assert alarm_mid is not None
    assert alarm_mid.severity == "WARNING"
    assert alarm_mid.status == "OPEN"

    # 3. Rate recovers to 142.0 (>= 140.0) -> RESOLVED
    recovered = evaluator.evaluate_rate(
        line_id="customRec",
        rate_per_min=142.0,
        warning_threshold=140.0,
        critical_threshold=120.0,
    )
    assert recovered is None

    saved = db_session.query(Alarm).filter_by(line_id="customRec", alarm_type="LOW_RATE").first()
    assert saved is not None
    assert saved.status == "RESOLVED"
    assert saved.resolved_at is not None


