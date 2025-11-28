from __future__ import annotations

from datetime import datetime, timezone


def as_utc_iso(dt: datetime) -> str:
    """Return a strict ISO8601 string with trailing Z."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")



