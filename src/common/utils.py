import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union


def utc_now() -> datetime:
    """Returns the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def datetime_to_isoformat(dt: Optional[datetime] = None) -> str:
    """Converts a datetime to an ISO 8601 string with UTC indicator."""
    if dt is None:
        dt = utc_now()
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def isoformat_to_datetime(dt_str: str) -> datetime:
    """Parses an ISO 8601 string into a timezone-aware UTC datetime."""
    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def hash_payload(data: Union[Dict[str, Any], str, bytes]) -> str:
    """Generates SHA-256 hash for a given object."""
    if isinstance(data, dict):
        encoded = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
    elif isinstance(data, str):
        encoded = data.encode("utf-8")
    else:
        encoded = data
    return hashlib.sha256(encoded).hexdigest()
