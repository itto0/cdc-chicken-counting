from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional
import zoneinfo

try:
    JAKARTA_TZ = zoneinfo.ZoneInfo("Asia/Jakarta")
except Exception:
    JAKARTA_TZ = timezone(timedelta(hours=7), name="WIB")

WIB_OFFSET = timedelta(hours=7)
WIB_LABEL = "WIB"

def now_jakarta() -> datetime:
    """Return current timezone-aware datetime in Jakarta (WIB, UTC+7)."""
    return datetime.now(JAKARTA_TZ)

def to_jakarta(dt: datetime) -> datetime:
    """Convert any datetime (aware or naive UTC) to Jakarta timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(JAKARTA_TZ)

def get_jakarta_today_bounds_utc(reference_dt: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    """
    Calculate the start and end of the Jakarta calendar day in UTC.
    If reference_dt is provided, bounds are computed for the Jakarta day containing reference_dt.
    Otherwise, current Jakarta time is used.
    Returns:
        (start_utc, end_utc): timezone-aware UTC datetimes.
    """
    if reference_dt is None:
        ref_jkt = now_jakarta()
    else:
        ref_jkt = to_jakarta(reference_dt)

    jkt_start = datetime(ref_jkt.year, ref_jkt.month, ref_jkt.day, 0, 0, 0, 0, tzinfo=JAKARTA_TZ)
    jkt_end = datetime(ref_jkt.year, ref_jkt.month, ref_jkt.day, 23, 59, 59, 999999, tzinfo=JAKARTA_TZ)
    return jkt_start.astimezone(timezone.utc), jkt_end.astimezone(timezone.utc)

def format_jakarta_display(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format a datetime into a Jakarta-local display string."""
    return to_jakarta(dt).strftime(fmt)
