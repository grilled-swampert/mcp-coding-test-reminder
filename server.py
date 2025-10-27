"""
Coding Contest Calendar MCP Server
Integrates LeetCode, CodeChef, and Codeforces contests with Google Calendar
Times displayed in IST (Indian Standard Time)
"""

from mcp.server.fastmcp import FastMCP
from tools import (
    get_contest_resource,
    fetch_contests_tool,
    add_contest_to_calendar_tool,
    list_calendar_contests_tool,
    delete_calendar_event_tool,
    set_reminder_preferences_tool
)
from config import DEFAULT_DAYS_AHEAD

# Create FastMCP server
mcp = FastMCP("contest-calendar")


@mcp.resource("contest://{contest_id}")
async def get_contest(contest_id: str) -> str:
    """Get detailed information about a specific contest"""
    return await get_contest_resource(contest_id)


@mcp.tool()
async def fetch_contests(platform: str = "", days_ahead: int = DEFAULT_DAYS_AHEAD) -> str:
    """
    Fetch upcoming coding contests from LeetCode, CodeChef, and Codeforces
    Times are displayed in IST (Indian Standard Time)

    Args:
        platform: Filter by platform (Codeforces, LeetCode, CodeChef). Leave empty for all.
        days_ahead: Number of days to look ahead (default: 30)
    """
    return await fetch_contests_tool(platform, days_ahead)


@mcp.tool()
async def add_contest_to_calendar(
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
    return await add_contest_to_calendar_tool(contest_id, reminder_minutes, force)


@mcp.tool()
async def list_calendar_contests(days_ahead: int = DEFAULT_DAYS_AHEAD) -> str:
    """
    List contest events in Google Calendar
    Times are displayed in IST

    Args:
        days_ahead: Number of days to look ahead (default: 30)
    """
    return await list_calendar_contests_tool(days_ahead)


@mcp.tool()
async def delete_calendar_event(event_id: str) -> str:
    """
    Delete a contest event from Google Calendar

    Args:
        event_id: The Google Calendar event ID
    """
    return await delete_calendar_event_tool(event_id)


@mcp.tool()
async def set_reminder_preferences(reminder_minutes: list[int]) -> str:
    """
    Set default reminder times for future contests

    Args:
        reminder_minutes: Default reminder times in minutes (e.g., [60, 30, 10])
    """
    return await set_reminder_preferences_tool(reminder_minutes)


if __name__ == "__main__":
    mcp.run()