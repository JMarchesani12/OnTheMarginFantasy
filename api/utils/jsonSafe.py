# utils/json_safe.py
from datetime import date, datetime
from typing import Any

def jsonSafe(value: Any) -> Any:
    """
    Recursively convert datetimes/dates into ISO strings so payload is JSON serializable.
    """
    if isinstance(value, datetime):
        # keep timezone info if present
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: jsonSafe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonSafe(v) for v in value]
    return value
