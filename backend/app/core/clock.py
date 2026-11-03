"""Time helpers. Timestamps are stored in UTC and shown in Indian Standard Time."""

from datetime import UTC, datetime, timedelta, timezone

# India has no daylight saving, so a fixed offset is exact and needs no timezone database.
IST = timezone(timedelta(hours=5, minutes=30), "IST")


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """Treat a naive datetime (as returned by SQLite) as UTC; leave aware ones alone."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def clock_time_ist(value: datetime) -> str:
    """Wall-clock time in IST, for example '20:59'."""
    return as_utc(value).astimezone(IST).strftime("%H:%M")
