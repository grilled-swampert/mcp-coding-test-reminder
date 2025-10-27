"""
Configuration settings for the Contest Calendar MCP Server
"""

from pathlib import Path
from zoneinfo import ZoneInfo

# Google Calendar API scopes
SCOPES = ['https://www.googleapis.com/auth/calendar']

# IST timezone
IST = ZoneInfo('Asia/Kolkata')

# Base directory for application data
BASE_DIR = Path.home() / '.contest_calendar'

# File paths
DB_PATH = BASE_DIR / 'contests.db'
TOKEN_PATH = BASE_DIR / 'token.pickle'
CREDENTIALS_PATH = BASE_DIR / 'credentials.json'

# API URLs
CODEFORCES_API_URL = "https://codeforces.com/api/contest.list"
LEETCODE_API_URL = "https://leetcode.com/graphql"
CODECHEF_API_URL = "https://www.codechef.com/api/list/contests/all?sort_by=START&sorting_order=asc&offset=0&mode=premium"

# Default settings
DEFAULT_REMINDER_MINUTES = [30, 10]
DEFAULT_DAYS_AHEAD = 30

# Ensure directory exists
BASE_DIR.mkdir(parents=True, exist_ok=True)