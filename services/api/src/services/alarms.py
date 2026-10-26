from datetime import datetime, timezone
from sqlalchemy.orm import Session
from services.api.src.db.models import Alarm
from shared.contracts import HealthSampleDTO

DEFAULT_RATE_WARNING = 130.0
DEFAULT_RATE_CRITICAL = 110.0


class AlarmEvaluator:
    """Evaluates metrics and health samples against operational thresholds

    and manages alarm lifecycle and deduplication.
    """

    def __init__(self, db: Session):
        self.db = db

    def _record_or_update_alarm(
        self,
        line_id: str,
        alarm_type: str,
        severity: str,
        message: str,
    ) -> Alarm:
        """Finds an existing open alarm for (line_id, alarm_type) or creates a new one.

        If an open alarm exists and its severity or message has changed, it is updated.
        """
        existing = (
            self.db.query(Alarm)
            .filter(
                Alarm.line_id == line_id,
                Alarm.alarm_type == alarm_type,
                Alarm.status == "OPEN",
            )
            .first()
        )

        if existing is not None:
            updated = False
            if existing.severity != severity:
                existing.severity = severity
                updated = True
            if existing.message != message:
                existing.message = message
                updated = True
            if updated:
                self.db.commit()
                self.db.refresh(existing)
            return existing

        alarm = Alarm(
            line_id=line_id,
            alarm_type=alarm_type,
            severity=severity,
            message=message,
            status="OPEN",
            opened_at=datetime.now(timezone.utc),
        )
        self.db.add(alarm)
        self.db.commit()
        self.db.refresh(alarm)
        return alarm

    def evaluate_rate(
        self,
        line_id: str,
        rate_per_min: float,
        warning_threshold: float | None = None,
        critical_threshold: float | None = None,
    ) -> Alarm | None:
        """Evaluate line production rate against warning/critical thresholds.

        Uses line-specific overrides when provided, falling back to system defaults
        (DEFAULT_RATE_WARNING = 130.0, DEFAULT_RATE_CRITICAL = 110.0).

        When rate returns to normal (>= warning threshold), any OPEN LOW_RATE alarm
        for this line is auto-resolved.
        """
        warning = warning_threshold if warning_threshold is not None else DEFAULT_RATE_WARNING
        critical = critical_threshold if critical_threshold is not None else DEFAULT_RATE_CRITICAL

        if rate_per_min < critical:
            severity = "CRITICAL"
        elif rate_per_min < warning:
            severity = "WARNING"
        else:
            # Auto-resolve existing open LOW_RATE alarm for this line if present
            open_alarm = (
                self.db.query(Alarm)
                .filter_by(line_id=line_id, alarm_type="LOW_RATE", status="OPEN")
                .first()
            )
            if open_alarm is not None:
                open_alarm.status = "RESOLVED"
                open_alarm.resolved_at = datetime.now(timezone.utc)
                self.db.commit()
            return None

        message = f"Production rate fell to {rate_per_min:.1f} birds/min"
        return self._record_or_update_alarm(
            line_id=line_id,
            alarm_type="LOW_RATE",
            severity=severity,
            message=message,
        )

    def evaluate_health(self, line_id: str, health: HealthSampleDTO) -> Alarm | None:
        """Evaluate stream health sample against operational thresholds.

        - stream_state == "OFFLINE": CRITICAL (STREAM_OFFLINE)
        - stream_state == "DEGRADED" or fps < 10.0: WARNING (LOW_FPS)
        - latency_p95_ms > 150.0: WARNING (HIGH_LATENCY)
        - Otherwise: None
        """
        if health.stream_state == "OFFLINE":
            alarm_type = "STREAM_OFFLINE"
            severity = "CRITICAL"
            message = "Camera stream is offline"
        elif health.stream_state == "DEGRADED" or health.fps < 10.0:
            alarm_type = "LOW_FPS"
            severity = "WARNING"
            message = f"Camera stream degraded or low FPS ({health.fps:.1f} FPS)"
        elif health.latency_p95_ms > 150.0:
            alarm_type = "HIGH_LATENCY"
            severity = "WARNING"
            message = f"High pipeline latency ({health.latency_p95_ms:.1f} ms)"
        else:
            return None

        return self._record_or_update_alarm(
            line_id=line_id,
            alarm_type=alarm_type,
            severity=severity,
            message=message,
        )
