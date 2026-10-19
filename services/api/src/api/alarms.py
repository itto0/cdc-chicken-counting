from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from services.api.src.db.models import Alarm
from services.api.src.db.session import get_db
from services.api.src.api.auth import get_current_user, UserDTO

router = APIRouter(prefix="/api/v1/alarms", tags=["alarms"])


class AlarmDTO(BaseModel):
    id: int
    line_id: str
    alarm_type: str
    severity: str
    message: str
    status: str
    opened_at: str
    ack_at: Optional[str] = None
    resolved_at: Optional[str] = None


class AlarmPatchPayload(BaseModel):
    status: str  # "ACKNOWLEDGED" or "RESOLVED"
    notes: Optional[str] = None
    acknowledged_by: Optional[str] = None


def _format_iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


@router.get("", response_model=list[AlarmDTO])
def list_alarms(
    line_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: UserDTO = Depends(get_current_user),
):
    query = select(Alarm)
    if line_id:
        query = query.where(Alarm.line_id == line_id)
    if status:
        stat = status.upper()
        if stat == "ACTIVE":
            query = query.where(Alarm.status.in_(["OPEN", "ACKNOWLEDGED"]))
        else:
            query = query.where(Alarm.status == stat)
    if severity:
        query = query.where(Alarm.severity == severity.upper())

    query = query.order_by(Alarm.opened_at.desc())
    alarms = db.scalars(query).all()

    return [
        AlarmDTO(
            id=a.id,
            line_id=a.line_id,
            alarm_type=a.alarm_type,
            severity=a.severity,
            message=a.message,
            status=a.status,
            opened_at=_format_iso(a.opened_at) or "",
            ack_at=_format_iso(a.ack_at),
            resolved_at=_format_iso(a.resolved_at),
        )
        for a in alarms
    ]


@router.patch("/{alarm_id}", response_model=AlarmDTO)
def patch_alarm(
    alarm_id: int,
    payload: AlarmPatchPayload,
    db: Session = Depends(get_db),
    current_user: UserDTO = Depends(get_current_user),
):
    alarm = db.get(Alarm, alarm_id)
    if not alarm:
        raise HTTPException(status_code=404, detail="Alarm not found")

    target_status = payload.status.upper()
    now = datetime.now(timezone.utc)

    if target_status == "ACKNOWLEDGED":
        alarm.status = "ACKNOWLEDGED"
        alarm.ack_at = now
        note_parts = []
        if payload.notes:
            note_parts.append(payload.notes)
        if payload.acknowledged_by:
            note_parts.append(f"by {payload.acknowledged_by}")
        if note_parts:
            base_msg = alarm.message or ""
            alarm.message = f"{base_msg} [Ack Note: {' '.join(note_parts)}]"[:255]
    elif target_status == "RESOLVED":
        alarm.status = "RESOLVED"
        alarm.resolved_at = now
        note_parts = []
        if payload.notes:
            note_parts.append(payload.notes)
        if payload.acknowledged_by:
            note_parts.append(f"by {payload.acknowledged_by}")
        if note_parts:
            base_msg = alarm.message or ""
            alarm.message = f"{base_msg} [Resolution: {' '.join(note_parts)}]"[:255]
    else:
        raise HTTPException(status_code=400, detail=f"Invalid target status: {target_status}")

    db.commit()
    db.refresh(alarm)

    return AlarmDTO(
        id=alarm.id,
        line_id=alarm.line_id,
        alarm_type=alarm.alarm_type,
        severity=alarm.severity,
        message=alarm.message,
        status=alarm.status,
        opened_at=_format_iso(alarm.opened_at) or "",
        ack_at=_format_iso(alarm.ack_at),
        resolved_at=_format_iso(alarm.resolved_at),
    )
