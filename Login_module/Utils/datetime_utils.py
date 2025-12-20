"""
DateTime utility functions - All operations use IST (Indian Standard Time).
Database storage, internal operations, and API responses all use IST.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))


def to_ist(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Ensure datetime is in IST timezone.
    If datetime is naive or in different timezone, convert to IST.
    
    Args:
        dt: Datetime object (timezone-aware or naive)
    
    Returns:
        IST datetime object, or None if input is None
    """
    if dt is None:
        return None
    
    # If naive datetime, assume it's IST (since everything is IST now)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=IST)
    
    # If already in IST, return as-is
    if dt.tzinfo == IST:
        return dt
    
    # Convert to IST
    return dt.astimezone(IST)


def to_ist_isoformat(dt: Optional[datetime]) -> Optional[str]:
    """
    Convert datetime to IST and return as ISO format string.
    Used for API responses - ensures IST timezone.
    
    Args:
        dt: Datetime object (timezone-aware or naive)
    
    Returns:
        ISO format string in IST timezone (e.g., "2024-12-17T14:30:00+05:30"),
        or None if input is None
    """
    ist_dt = to_ist(dt)
    if ist_dt is None:
        return None
    return ist_dt.isoformat()


def to_ist_str(dt: Optional[datetime], format_str: str = "%Y-%m-%d %H:%M:%S") -> Optional[str]:
    """
    Convert datetime to IST and return as formatted string.
    
    Args:
        dt: Datetime object (timezone-aware or naive)
        format_str: Python strftime format string (default: "%Y-%m-%d %H:%M:%S")
    
    Returns:
        Formatted string in IST timezone, or None if input is None
    """
    ist_dt = to_ist(dt)
    if ist_dt is None:
        return None
    return ist_dt.strftime(format_str)


def now_ist() -> datetime:
    """
    Get current IST datetime (timezone-aware).
    Use this for ALL datetime operations - database storage, internal operations, API responses.
    
    Returns:
        Current datetime in IST timezone
    """
    return datetime.now(IST)


def now_utc() -> datetime:
    """
    DEPRECATED: Use now_ist() instead.
    Kept for backward compatibility but returns IST time.
    
    Returns:
        Current datetime in IST timezone (not UTC)
    """
    return datetime.now(IST)

