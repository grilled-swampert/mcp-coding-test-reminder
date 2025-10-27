"""
Database management for contest storage
"""

import sqlite3
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from config import DB_PATH


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

    def get_contest_by_id(self, contest_id: str):
        """Get a specific contest by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM contests WHERE id = ?', (contest_id,))

        columns = [desc[0] for desc in cursor.description]
        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(zip(columns, row))
        return None

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