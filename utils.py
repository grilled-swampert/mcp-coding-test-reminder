"""
Utility functions for time conversion and formatting
"""

from datetime import datetime, timezone
from config import IST


def to_ist(dt: datetime) -> datetime:
    """Convert datetime to IST"""
    if dt.tzinfo is None:
        # Assume UTC if no timezone
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)


def format_ist_time(dt: datetime) -> str:
    """Format datetime in IST for display"""
    ist_dt = to_ist(dt)
    return ist_dt.strftime('%Y-%m-%d %H:%M IST')