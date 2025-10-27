"""
MCP tool functions for the contest calendar server
"""

import json
from datetime import datetime
from database import ContestDatabase
from calendar_manager import GoogleCalendarManager
from fetchers import ContestFetcher
from utils import to_ist, format_ist_time
from config import DEFAULT_DAYS_AHEAD


# Initialize components
db = ContestDatabase()
calendar_manager = GoogleCalendarManager()


async def get_contest_resource(contest_id: str) -> str:
    """Get detailed information about a specific contest"""
    contest = db.get_contest_by_id(contest_id)

    if contest:
        # Add IST time for display
        start_time = datetime.fromisoformat(contest['start_time'])
        contest['start_time_ist'] = format_ist_time(start_time)
        return json.dumps(contest, indent=2)

    return json.dumps({"error": "Contest not found"})


async def fetch_contests_tool(platform: str = "", days_ahead: int = DEFAULT_DAYS_AHEAD) -> str:
    """
    Fetch upcoming coding contests from LeetCode, CodeChef, and Codeforces
    Times are displayed in IST (Indian Standard Time)

    Args:
        platform: Filter by platform (Codeforces, LeetCode, CodeChef). Leave empty for all.
        days_ahead: Number of days to look ahead (default: 30)
    """
    platform = platform.strip()

    # Fetch latest contests
    all_contests = await ContestFetcher.fetch_all()
    db.save_contests(all_contests)

    # Get from database with filters
    contests = db.get_upcoming_contests(
        platform=platform if platform else None,
        days_ahead=days_ahead
    )

    if not contests:
        return "No upcoming contests found in the specified timeframe."

    result = f"Found {len(contests)} upcoming contest(s):\n\n"
    for contest in contests:
        start_time = datetime.fromisoformat(contest['start_time'])
        start_time_ist = to_ist(start_time)
        duration_hours = contest['duration_seconds'] / 3600

        result += f"**{contest['title']}**\n"
        result += f"Platform: {contest['platform']}\n"
        result += f"Start: {start_time_ist.strftime('%Y-%m-%d %H:%M IST')}\n"
        result += f"Duration: {duration_hours:.1f} hours\n"
        result += f"Contest ID: `{contest['id']}`\n"
        if contest.get('url'):
            result += f"URL: {contest['url']}\n"
        result += "\n"

    return result


async def add_contest_to_calendar_tool(
    contest_id: str,
    reminder_minutes: list[int] = None,
    force: bool = False
) -> str:
    """
    Add a coding contest to Google Calendar with custom reminders
    Calendar event will be created with IST timezone

    Args:
        contest_id: The contest ID (e.g., codeforces_1234)
        reminder_minutes: Minutes before contest to send reminders (e.g., [30, 10])
        force: If True, add even if already exists (default: False)
    """
    if reminder_minutes is None:
        reminder_minutes = [30, 10]

    # Check if already added
    already_exists, event_id = db.is_contest_in_calendar(contest_id)
    if already_exists and not force:
        return (
            f"Contest already added to calendar!\n\n"
            f"Event ID: `{event_id}`\n\n"
            f"Use `force=True` to add anyway, or delete the existing event first."
        )

    # Get contest from database
    contest = db.get_contest_by_id(contest_id)

    if not contest:
        return f"Contest with ID '{contest_id}' not found. Please fetch contests first."

    try:
        event = calendar_manager.create_contest_event(contest, reminder_minutes)
        db.save_calendar_event(event['id'], contest_id)

        start_time = datetime.fromisoformat(contest['start_time'])
        start_time_ist = to_ist(start_time)

        result = "Successfully added to Google Calendar!\n\n"
        result += f"**{contest['title']}**\n"
        result += f"Platform: {contest['platform']}\n"
        result += f"Start Time (IST): {start_time_ist.strftime('%Y-%m-%d %H:%M IST')}\n"
        result += f"Event ID: `{event['id']}`\n"
        result += f"Reminders: {', '.join([f'{m} minutes before' for m in reminder_minutes])}\n"
        result += f"Calendar Link: {event.get('htmlLink', 'N/A')}\n"

        return result

    except Exception as e:
        return f"Error adding to calendar: {str(e)}"


async def list_calendar_contests_tool(days_ahead: int = DEFAULT_DAYS_AHEAD) -> str:
    """
    List contest events in Google Calendar
    Times are displayed in IST

    Args:
        days_ahead: Number of days to look ahead (default: 30)
    """
    try:
        events = calendar_manager.list_events(days_ahead)

        if not events:
            return "No upcoming events found in your Google Calendar."

        result = f"Found {len(events)} upcoming event(s) in your calendar:\n\n"
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            # Convert to IST for display
            if 'T' in start:
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                start_ist = format_ist_time(start_dt)
            else:
                start_ist = start

            result += f"**{event['summary']}**\n"
            result += f"Start: {start_ist}\n"
            result += f"Event ID: `{event['id']}`\n\n"

        return result

    except Exception as e:
        return f"Error listing events: {str(e)}"


async def delete_calendar_event_tool(event_id: str) -> str:
    """
    Delete a contest event from Google Calendar

    Args:
        event_id: The Google Calendar event ID
    """
    try:
        calendar_manager.delete_event(event_id)
        return f"Successfully deleted event `{event_id}` from Google Calendar."

    except Exception as e:
        return f"Error deleting event: {str(e)}"


async def set_reminder_preferences_tool(reminder_minutes: list[int]) -> str:
    """
    Set default reminder times for future contests

    Args:
        reminder_minutes: Default reminder times in minutes (e.g., [60, 30, 10])
    """
    db.set_preference("default_reminders", reminder_minutes)

    result = "Default reminders updated!\n\n"
    result += f"Future contests will have reminders: {', '.join([f'{m} minutes before' for m in reminder_minutes])}"

    return result