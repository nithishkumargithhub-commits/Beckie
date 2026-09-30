import os
import re
import datetime
import logging
from typing import Optional, Tuple
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import config
import actions.database as database

logger = logging.getLogger("VoiceAssistant.Reminders")

from actions.google_services import SERVICE_SCOPES
SCOPES = SERVICE_SCOPES['calendar']

# File paths in project root
CREDENTIALS_PATH = os.path.join(config.BASE_DIR, "credentials.json")
TOKEN_PATH = os.path.join(config.BASE_DIR, "token.json")

def get_calendar_service():
    """
    Performs OAuth authentication and returns the Google Calendar API service instance.
    Returns (service, None) or (None, error_message).
    """
    if not os.path.exists(CREDENTIALS_PATH):
        msg = (
            "Google Calendar credentials file 'credentials.json' is missing in the project root. "
            "Please place your OAuth client 'credentials.json' in the project root directory to enable Google Calendar integration."
        )
        logger.warning(msg)
        return None, msg

    creds = None
    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
            logger.info("Credentials loaded successfully from token.json")
        except Exception as e:
            logger.error(f"Error reading token.json: {e}")

    try:
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Credentials expired. Refreshing token...")
                creds.refresh(Request())
            else:
                logger.info("Initializing new OAuth flow...")
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(TOKEN_PATH, 'w') as token:
                token.write(creds.to_json())
                logger.info(f"Refreshed credentials saved to {TOKEN_PATH}")

        service = build('calendar', 'v3', credentials=creds)
        return service, None

    except Exception as e:
        msg = f"Google Calendar API OAuth authentication failed: {e}"
        logger.error(msg)
        return None, msg

def parse_datetime_expression(datetime_str: Optional[str]) -> datetime.datetime:
    """
    Parses datetime expressions into a datetime object with timezone offset.
    Supports ISO format strings, relative offsets ("in 30 minutes", "in 2 hours"),
    and natural time phrases ("tomorrow at 10 am", "at 5 pm").
    Defaults to 1 hour from now if unparseable or omitted.
    """
    now = datetime.datetime.now().astimezone()

    if not datetime_str:
        return now + datetime.timedelta(hours=1)

    cleaned = str(datetime_str).strip()

    # 1. Try ISO Format Parsing
    try:
        iso_str = cleaned.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.astimezone()
        return dt
    except Exception:
        pass

    # 2. Try dateutil.parser if installed
    try:
        from dateutil import parser as du_parser
        dt = du_parser.parse(cleaned, fuzzy=True, default=now)
        if dt.tzinfo is None:
            dt = dt.astimezone()
        return dt
    except Exception:
        pass

    # 3. Relative Offset Matching (e.g. "in 30 minutes", "in 2 hours", "in 1 day")
    lower_str = cleaned.lower()
    rel_match = re.search(r"in\s+(\d+)\s+(minute|min|hour|hr|day)s?", lower_str)
    if rel_match:
        val = int(rel_match.group(1))
        unit = rel_match.group(2)
        if "min" in unit:
            return now + datetime.timedelta(minutes=val)
        elif "hour" in unit or "hr" in unit:
            return now + datetime.timedelta(hours=val)
        elif "day" in unit:
            return now + datetime.timedelta(days=val)

    # 4. Fallback Default: 1 hour from now
    logger.warning(f"Could not parse datetime string '{datetime_str}'. Defaulting to 1 hour from now.")
    return now + datetime.timedelta(hours=1)


def create_calendar_reminder(text: str, datetime_str: Optional[str] = None) -> Tuple[bool, str]:
    """
    Creates a reminder event locally in SQLite database and syncs to Google Calendar if available.
    """
    logger.info(f"Request to create reminder: '{text}' at: '{datetime_str}'")
    
    start_time = parse_datetime_expression(datetime_str)
    end_time = start_time + datetime.timedelta(minutes=30)
    formatted_time = start_time.strftime('%I:%M %p on %B %d, %Y')
    iso_time_str = start_time.isoformat()

    # Save to local database first
    database.add_local_reminder(text, iso_time_str)

    # Try Google Calendar Authentication
    service, auth_error = get_calendar_service()
    if not service:
        msg = f"Reminder set for {formatted_time}! Saved locally in database."
        logger.info(f"{msg} (Google Calendar offline: {auth_error})")
        return True, msg

    # Create Event Body in Google Calendar
    event = {
        'summary': text,
        'description': 'Reminder scheduled by Windows Voice Assistant (Jarvis)',
        'start': {
            'dateTime': iso_time_str,
        },
        'end': {
            'dateTime': end_time.isoformat(),
        },
        'reminders': {
            'useDefault': True,
        }
    }

    try:
        created_event = service.events().insert(calendarId='primary', body=event).execute()
        html_link = created_event.get("htmlLink", "")
        msg = f"Reminder set successfully on Google Calendar and local database! Scheduled for {formatted_time}."
        logger.info(f"Calendar event created successfully. Link: {html_link}")
        return True, msg
    except Exception as e:
        msg = f"Reminder saved locally for {formatted_time}. (Google Calendar sync error: {e})"
        logger.warning(msg)
        return True, msg


def list_calendar_reminders(max_results: int = 5) -> Tuple[bool, str]:
    """
    Fetches upcoming reminders/events from Google Calendar, or falls back to local database.
    """
    service, auth_error = get_calendar_service()
    
    # Fallback to local DB if service not available
    if not service:
        local_reminders = database.get_local_reminders(limit=max_results)
        if not local_reminders:
            return True, "You have no upcoming reminders saved locally."
        
        items_str = []
        for idx, item in enumerate(local_reminders, 1):
            title = item.get("title", "Untitled")
            s_time = item.get("scheduled_time", "N/A")
            try:
                dt = datetime.datetime.fromisoformat(s_time)
                time_fmt = dt.strftime('%I:%M %p on %B %d')
            except Exception:
                time_fmt = s_time
            items_str.append(f"{idx}. {title} at {time_fmt}")
        
        result_msg = "Here are your local reminders:\n" + "\n".join(items_str)
        return True, result_msg

    # Query Google Calendar API
    try:
        now_iso = datetime.datetime.now().astimezone().isoformat()
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now_iso,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        if not events:
            return True, "You have no upcoming events or reminders scheduled on Google Calendar."

        items_str = []
        for idx, event in enumerate(events, 1):
            summary = event.get('summary', 'No Title')
            start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date'))
            try:
                dt = datetime.datetime.fromisoformat(start)
                time_fmt = dt.strftime('%I:%M %p on %B %d')
            except Exception:
                time_fmt = start
            items_str.append(f"{idx}. {summary} at {time_fmt}")

        msg = f"Here are your upcoming Google Calendar events:\n" + "\n".join(items_str)
        return True, msg

    except Exception as e:
        logger.error(f"Error fetching Google Calendar events: {e}")
        return False, f"Could not retrieve Google Calendar events: {e}"
