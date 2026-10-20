from datetime import datetime, timezone, timedelta
from shared.time_utils import (
    JAKARTA_TZ,
    WIB_OFFSET,
    WIB_LABEL,
    now_jakarta,
    to_jakarta,
    get_jakarta_today_bounds_utc,
    format_jakarta_display,
)

def test_jakarta_timezone_constants():
    assert WIB_OFFSET == timedelta(hours=7)
    assert WIB_LABEL == "WIB"
    now_jkt = now_jakarta()
    assert now_jkt.utcoffset() == timedelta(hours=7)

def test_to_jakarta():
    # Naive datetime assumed UTC
    dt_naive = datetime(2026, 4, 14, 3, 0, 0)
    jkt = to_jakarta(dt_naive)
    assert jkt.utcoffset() == timedelta(hours=7)
    assert jkt.hour == 10

    # Aware UTC datetime
    dt_utc = datetime(2026, 4, 14, 3, 0, 0, tzinfo=timezone.utc)
    jkt2 = to_jakarta(dt_utc)
    assert jkt2.hour == 10
    assert jkt2.day == 14

    # Aware non-UTC timezone (e.g., UTC+1)
    tz_plus_1 = timezone(timedelta(hours=1))
    dt_other = datetime(2026, 4, 14, 4, 0, 0, tzinfo=tz_plus_1)
    jkt3 = to_jakarta(dt_other)
    assert jkt3.hour == 10
    assert jkt3.day == 14

def test_get_jakarta_today_bounds_utc():
    # Reference: 2026-04-14 01:00:00 WIB (which is 2026-04-13 18:00:00 UTC)
    ref_dt = datetime(2026, 4, 13, 18, 0, 0, tzinfo=timezone.utc)
    start_utc, end_utc = get_jakarta_today_bounds_utc(reference_dt=ref_dt)

    # In Jakarta, that day is 2026-04-14 00:00:00 to 23:59:59.999999
    # In UTC, 00:00:00 WIB corresponds to 2026-04-13 17:00:00 UTC
    assert start_utc == datetime(2026, 4, 13, 17, 0, 0, tzinfo=timezone.utc)
    assert end_utc == datetime(2026, 4, 14, 16, 59, 59, 999999, tzinfo=timezone.utc)

    # Calling without reference_dt uses current time
    now_start_utc, now_end_utc = get_jakarta_today_bounds_utc()
    assert (now_end_utc - now_start_utc) == timedelta(days=1) - timedelta(microseconds=1)
    assert now_start_utc.tzinfo == timezone.utc
    assert now_end_utc.tzinfo == timezone.utc

def test_format_jakarta_display():
    dt_utc = datetime(2026, 4, 14, 3, 30, 15, tzinfo=timezone.utc)
    formatted = format_jakarta_display(dt_utc)
    assert formatted == "2026-04-14 10:30:15"

    # Custom format and naive input
    dt_naive = datetime(2026, 4, 14, 3, 30, 15)
    custom_formatted = format_jakarta_display(dt_naive, fmt="%H:%M")
    assert custom_formatted == "10:30"
