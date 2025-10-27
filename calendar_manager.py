"""
Google Calendar integration
"""

import pickle
from datetime import datetime, timedelta, timezone
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from config import SCOPES, TOKEN_PATH, CREDENTIALS_PATH, DEFAULT_REMINDER_MINUTES


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
            reminder_minutes = DEFAULT_REMINDER_MINUTES

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