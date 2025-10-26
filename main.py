"""
Coding Contest Calendar MCP Server
Integrates LeetCode, CodeChef, and Codeforces contests with Google Calendar
Times displayed in IST (Indian Standard Time)
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any
import asyncio
import aiohttp
from pathlib import Path
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle

# Google Calendar API scopes
SCOPES = ['https://www.googleapis.com/auth/calendar']

# IST timezone
IST = ZoneInfo('Asia/Kolkata')

# Database path
DB_PATH = Path.home() / '.contest_calendar' / 'contests.db'
TOKEN_PATH = Path.home() / '.contest_calendar' / 'token.pickle'
CREDENTIALS_PATH = Path.home() / '.contest_calendar' / 'credentials.json'

# Ensure directory exists
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


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


class ContestDatabase:
    """Manages contest data storage"""

    def __init__(self, db_path: str = str(DB_PATH)):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contests (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                title TEXT NOT NULL,
                start_time TEXT NOT NULL,
                duration_seconds INTEGER NOT NULL,
                url TEXT,
                fetched_at TEXT NOT NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS calendar_events (
                event_id TEXT PRIMARY KEY,
                contest_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (contest_id) REFERENCES contests(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')

        conn.commit()
        conn.close()

    def save_contests(self, contests: list):
        """Save contests to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for contest in contests:
            cursor.execute('''
                INSERT OR REPLACE INTO contests 
                (id, platform, title, start_time, duration_seconds, url, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                contest['id'],
                contest['platform'],
                contest['title'],
                contest['start_time'],
                contest['duration_seconds'],
                contest.get('url', ''),
                datetime.now(timezone.utc).isoformat()
            ))

        conn.commit()
        conn.close()

    def get_upcoming_contests(self, platform: str = None, days_ahead: int = 30):
        """Get upcoming contests"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff_time = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).isoformat()
        current_time = datetime.now(timezone.utc).isoformat()

        if platform:
            cursor.execute('''
                SELECT * FROM contests
                WHERE platform = ? AND start_time > ? AND start_time < ?
                ORDER BY start_time
            ''', (platform, current_time, cutoff_time))
        else:
            cursor.execute('''
                SELECT * FROM contests
                WHERE start_time > ? AND start_time < ?
                ORDER BY start_time
            ''', (current_time, cutoff_time))

        columns = [desc[0] for desc in cursor.description]
        contests = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return contests

    def save_calendar_event(self, event_id: str, contest_id: str):
        """Save calendar event mapping"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO calendar_events 
            (event_id, contest_id, created_at)
            VALUES (?, ?, ?)
        ''', (event_id, contest_id, datetime.now(timezone.utc).isoformat()))

        conn.commit()
        conn.close()

    def is_contest_in_calendar(self, contest_id: str) -> tuple[bool, str]:
        """Check if contest already has a calendar event"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT event_id FROM calendar_events 
            WHERE contest_id = ?
        ''', (contest_id,))

        result = cursor.fetchone()
        conn.close()

        if result:
            return True, result[0]
        return False, None

    def get_preference(self, key: str, default: Any = None):
        """Get user preference"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT value FROM preferences WHERE key = ?', (key,))
        result = cursor.fetchone()

        conn.close()

        if result:
            try:
                return json.loads(result[0])
            except:
                return result[0]
        return default

    def set_preference(self, key: str, value: Any):
        """Set user preference"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        value_str = json.dumps(value) if not isinstance(value, str) else value

        cursor.execute('''
            INSERT OR REPLACE INTO preferences (key, value)
            VALUES (?, ?)
        ''', (key, value_str))

        conn.commit()
        conn.close()


class ContestFetcher:
    """Fetches contests from various platforms"""

    @staticmethod
    async def fetch_codeforces():
        """Fetch contests from Codeforces"""
        url = "https://codeforces.com/api/contest.list"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    data = await response.json()

                    if data['status'] != 'OK':
                        return []

                    contests = []
                    for contest in data['result']:
                        if contest['phase'] == 'BEFORE':
                            # UTC timestamp from Codeforces
                            start_time = datetime.fromtimestamp(contest['startTimeSeconds'], tz=timezone.utc)

                            contests.append({
                                'id': f"codeforces_{contest['id']}",
                                'platform': 'Codeforces',
                                'title': contest['name'],
                                'start_time': start_time.isoformat(),
                                'duration_seconds': contest['durationSeconds'],
                                'url': f"https://codeforces.com/contest/{contest['id']}"
                            })

                    return contests
        except Exception as e:
            print(f"Error fetching Codeforces contests: {e}")
            return []

    @staticmethod
    async def fetch_leetcode():
        """Fetch contests from LeetCode (GraphQL API)"""
        url = "https://leetcode.com/graphql"

        query = """
        query {
            allContests {
                title
                titleSlug
                startTime
                duration
            }
        }
        """

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={'query': query}) as response:
                    data = await response.json()

                    contests = []
                    current_time = datetime.now(timezone.utc)

                    for contest in data.get('data', {}).get('allContests', []):
                        # UTC timestamp from LeetCode
                        start_time = datetime.fromtimestamp(contest['startTime'], tz=timezone.utc)

                        if start_time > current_time:
                            contests.append({
                                'id': f"leetcode_{contest['titleSlug']}",
                                'platform': 'LeetCode',
                                'title': contest['title'],
                                'start_time': start_time.isoformat(),
                                'duration_seconds': contest['duration'],
                                'url': f"https://leetcode.com/contest/{contest['titleSlug']}"
                            })

                    return contests
        except Exception as e:
            print(f"Error fetching LeetCode contests: {e}")
            return []

    @staticmethod
    async def fetch_codechef():
        """Fetch contests from CodeChef (API v3)"""
        url = "https://www.codechef.com/api/list/contests/all?sort_by=START&sorting_order=asc&offset=0&mode=premium"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    data = await response.json()

                    # Debug: Print the response status
                    print(f"CodeChef API Status: {data.get('status')}")
                    print(f"Future contests count: {len(data.get('future_contests', []))}")

                    if data.get('status') != 'success':
                        print(f"CodeChef API returned non-success status: {data.get('status')}")
                        return []

                    contests = []
                    current_time = datetime.now(timezone.utc)

                    # Process future contests
                    for contest in data.get('future_contests', []):
                        try:
                            # Parse ISO format datetime (includes IST timezone +05:30)
                            start_time = datetime.fromisoformat(contest['contest_start_date_iso'])

                            # Convert to UTC
                            start_time_utc = start_time.astimezone(timezone.utc)

                            # Debug: Print each contest
                            print(f"Processing: {contest['contest_name']} - Start: {start_time_utc}")

                            # Duration is in minutes, convert to seconds
                            duration_seconds = int(contest['contest_duration']) * 60

                            contests.append({
                                'id': f"codechef_{contest['contest_code']}",
                                'platform': 'CodeChef',
                                'title': contest['contest_name'],
                                'start_time': start_time_utc.isoformat(),
                                'duration_seconds': duration_seconds,
                                'url': f"https://www.codechef.com/{contest['contest_code']}"
                            })
                        except Exception as e:
                            print(f"Error processing CodeChef contest {contest.get('contest_code')}: {e}")
                            continue

                    print(f"Total CodeChef contests added: {len(contests)}")
                    return contests

        except Exception as e:
            print(f"Error fetching CodeChef contests: {e}")
            import traceback
            traceback.print_exc()
            return []

    @staticmethod
    async def fetch_all():
        """Fetch from all platforms"""
        results = await asyncio.gather(
            ContestFetcher.fetch_codeforces(),
            ContestFetcher.fetch_leetcode(),
            ContestFetcher.fetch_codechef(),
            return_exceptions=True
        )

        all_contests = []
        for result in results:
            if isinstance(result, list):
                all_contests.extend(result)

        return all_contests


class GoogleCalendarManager:
    """Manages Google Calendar integration"""

    def __init__(self):
        self.creds = None
        self.service = None

    def authenticate(self):
        """Authenticate with Google Calendar"""
        # Load credentials from pickle file
        if TOKEN_PATH.exists():
            with open(TOKEN_PATH, 'rb') as token:
                self.creds = pickle.load(token)

        # If no valid credentials, let user log in
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                if not CREDENTIALS_PATH.exists():
                    raise FileNotFoundError(
                        f"Please place your Google OAuth credentials.json at {CREDENTIALS_PATH}"
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    str(CREDENTIALS_PATH), SCOPES
                )
                self.creds = flow.run_local_server(port=0)

            # Save credentials
            with open(TOKEN_PATH, 'wb') as token:
                pickle.dump(self.creds, token)

        self.service = build('calendar', 'v3', credentials=self.creds)
        return True

    def create_contest_event(self, contest: dict, reminder_minutes: list = None):
        """Create a calendar event for a contest"""
        if not self.service:
            self.authenticate()

        if reminder_minutes is None:
            reminder_minutes = [30, 10]  # Default reminders

        start_time = datetime.fromisoformat(contest['start_time'])
        end_time = start_time + timedelta(seconds=contest['duration_seconds'])

        event = {
            'summary': f"{contest['platform']}: {contest['title']}",
            'description': f"Contest URL: {contest.get('url', 'N/A')}",
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'Asia/Kolkata',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'Asia/Kolkata',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': minutes}
                    for minutes in reminder_minutes
                ],
            },
        }

        try:
            event_result = self.service.events().insert(
                calendarId='primary',
                body=event
            ).execute()

            return event_result
        except Exception as e:
            raise Exception(f"Failed to create calendar event: {e}")

    def list_events(self, days_ahead: int = 30):
        """List upcoming calendar events"""
        if not self.service:
            self.authenticate()

        now = datetime.now(timezone.utc)
        time_max = now + timedelta(days=days_ahead)

        events_result = self.service.events().list(
            calendarId='primary',
            timeMin=now.isoformat(),
            timeMax=time_max.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        return events_result.get('items', [])

    def delete_event(self, event_id: str):
        """Delete a calendar event"""
        if not self.service:
            self.authenticate()

        try:
            self.service.events().delete(
                calendarId='primary',
                eventId=event_id
            ).execute()
            return True
        except Exception as e:
            raise Exception(f"Failed to delete event: {e}")


# Initialize components
db = ContestDatabase()
calendar_manager = GoogleCalendarManager()

# Create FastMCP server
mcp = FastMCP("contest-calendar")


@mcp.resource("contest://{contest_id}")
async def get_contest(contest_id: str) -> str:
    """Get detailed information about a specific contest"""
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM contests WHERE id = ?', (contest_id,))

    columns = [desc[0] for desc in cursor.description]
    row = cursor.fetchone()
    conn.close()

    if row:
        contest = dict(zip(columns, row))
        # Add IST time for display
        start_time = datetime.fromisoformat(contest['start_time'])
        contest['start_time_ist'] = format_ist_time(start_time)
        return json.dumps(contest, indent=2)

    return json.dumps({"error": "Contest not found"})


@mcp.tool()
async def fetch_contests(platform: str = "", days_ahead: int = 30) -> str:
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


@mcp.tool()
async def add_contest_to_calendar(contest_id: str, reminder_minutes: list[int] = None, force: bool = False) -> str:
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
        return f"Contest already added to calendar!\n\nEvent ID: `{event_id}`\n\nUse `force=True` to add anyway, or delete the existing event first."

    # Get contest from database
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM contests WHERE id = ?', (contest_id,))
    columns = [desc[0] for desc in cursor.description]
    row = cursor.fetchone()
    conn.close()

    if not row:
        return f"Contest with ID '{contest_id}' not found. Please fetch contests first."

    contest = dict(zip(columns, row))

    try:
        event = calendar_manager.create_contest_event(contest, reminder_minutes)
        db.save_calendar_event(event['id'], contest_id)

        start_time = datetime.fromisoformat(contest['start_time'])
        start_time_ist = to_ist(start_time)

        result = f" Successfully added to Google Calendar!\n\n"
        result += f"**{contest['title']}**\n"
        result += f"Platform: {contest['platform']}\n"
        result += f"Start Time (IST): {start_time_ist.strftime('%Y-%m-%d %H:%M IST')}\n"
        result += f"Event ID: `{event['id']}`\n"
        result += f"Reminders: {', '.join([f'{m} minutes before' for m in reminder_minutes])}\n"
        result += f"Calendar Link: {event.get('htmlLink', 'N/A')}\n"

        return result

    except Exception as e:
        return f"Error adding to calendar: {str(e)}"


@mcp.tool()
async def list_calendar_contests(days_ahead: int = 30) -> str:
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


@mcp.tool()
async def delete_calendar_event(event_id: str) -> str:
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


@mcp.tool()
async def set_reminder_preferences(reminder_minutes: list[int]) -> str:
    """
    Set default reminder times for future contests

    Args:
        reminder_minutes: Default reminder times in minutes (e.g., [60, 30, 10])
    """
    db.set_preference("default_reminders", reminder_minutes)

    result = f"Default reminders updated!\n\n"
    result += f"Future contests will have reminders: {', '.join([f'{m} minutes before' for m in reminder_minutes])}"

    return result


if __name__ == "__main__":
    mcp.run()