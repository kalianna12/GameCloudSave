"""Display timestamps in the computer's timezone without changing stored values."""
from datetime import datetime


def local_time(value: str) -> str:
    if not value:
        return ''
    # A calendar date is not an instant (for example a game's release date).
    if len(value) == 10:
        return value
    try:
        timestamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return value
    # Legacy timestamps without an offset already represent local wall time.
    if timestamp.tzinfo is not None:
        timestamp = timestamp.astimezone()
    return timestamp.strftime('%Y-%m-%d %H:%M:%S')
