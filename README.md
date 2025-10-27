# Contest Calendar MCP Server - Refactored Structure

<img width="1606" height="658" alt="image" src="https://github.com/user-attachments/assets/c9feb644-468b-44a8-881d-742388fd9642" />

## Project Structure

```
contest-calendar-mcp/
├── config.py              # Configuration settings and constants
├── utils.py               # Utility functions for time conversion
├── database.py            # Database management and queries
├── fetchers.py            # API fetchers for contest platforms
├── calendar_manager.py    # Google Calendar integration
├── tools.py               # MCP tool implementations
├── server.py              # Main MCP server entry point
├── requirements.txt       # Python dependencies
└── README.md              # Documentation

~/.contest_calendar/       # Data directory (auto-created)
├── contests.db            # SQLite database
├── token.pickle           # Google OAuth token
└── credentials.json       # Google OAuth credentials (user provided)
```

## Setup Instructions

### 1. Install Dependencies

```bash
pip install fastmcp aiohttp google-auth-oauthlib google-api-python-client
```

Or run:
```bash
pip install -r requirements.txt
```

### 2. Google Calendar Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable Google Calendar API
4. Create OAuth 2.0 credentials (Desktop app)
5. Download credentials and save as `~/.contest_calendar/credentials.json`

### 3. Run the Server

```bash
python server.py
```

On first run, it will open a browser for Google authentication.

## Debugging Guide

### Testing Individual Components

**Test Database:**
```python
from database import ContestDatabase

db = ContestDatabase()
contests = db.get_upcoming_contests()
print(contests)
```

**Test Fetchers:**
```python
import asyncio
from fetchers import ContestFetcher

async def test():
    contests = await ContestFetcher.fetch_codeforces()
    print(contests)

asyncio.run(test())
```

**Test Calendar:**
```python
from calendar_manager import GoogleCalendarManager

cal = GoogleCalendarManager()
cal.authenticate()
events = cal.list_events()
print(events)
```

**Test Utils:**
```python
from datetime import datetime, timezone
from utils import to_ist, format_ist_time

now = datetime.now(timezone.utc)
print(format_ist_time(now))
```

## Adding a New Platform

To add a new contest platform (e.g., AtCoder):

1. **In `config.py`**: Add API URL constant
2. **In `fetchers.py`**: Add `fetch_atcoder()` method
3. **In `fetchers.py`**: Update `fetch_all()` to include new fetcher

Example:
```python
# In config.py
ATCODER_API_URL = "https://atcoder.jp/contests/..."

# In fetchers.py
@staticmethod
async def fetch_atcoder():
    # Implementation here
    pass

@staticmethod
async def fetch_all():
    results = await asyncio.gather(
        ContestFetcher.fetch_codeforces(),
        ContestFetcher.fetch_leetcode(),
        ContestFetcher.fetch_codechef(),
        ContestFetcher.fetch_atcoder(),  # Add here
        return_exceptions=True
    )
    # Rest of the code...
```

## Running in Production

For production deployment:

```bash
# Run with process manager
pm2 start server.py --interpreter python3 --name contest-calendar
```
