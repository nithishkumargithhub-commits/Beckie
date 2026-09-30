import os
import logging
import base64
from email.mime.text import MIMEText
from typing import Optional, Tuple, List, Dict

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

import config

logger = logging.getLogger("VoiceAssistant.GoogleServices")

# Scopes definition
CALENDAR_TASKS_SCOPES = [
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/tasks',
]

SERVICE_SCOPES = {
    'calendar': ['https://www.googleapis.com/auth/calendar.events'],
    'tasks': ['https://www.googleapis.com/auth/tasks'],
    'gmail': ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.send']
}

# Unified OAuth Scopes for Calendar, Tasks, and Gmail
ALL_SCOPES = CALENDAR_TASKS_SCOPES + SERVICE_SCOPES['gmail']

CREDENTIALS_PATH = os.path.join(config.BASE_DIR, "credentials.json")
TOKEN_PATH = os.path.join(config.BASE_DIR, "token.json")

def get_google_service(service_name: str, version: str) -> Tuple[Optional[object], Optional[str]]:
    """
    Unified OAuth authentication helper that builds and returns a Google API service client.
    """
    if not os.path.exists(CREDENTIALS_PATH):
        msg = (
            f"Google credentials file 'credentials.json' is missing in project root. "
            f"Please place your OAuth client 'credentials.json' in the project root folder to use Google {service_name.capitalize()} API."
        )
        logger.warning(msg)
        return None, msg

    req_scopes = SERVICE_SCOPES.get(service_name.lower(), CALENDAR_TASKS_SCOPES)
    creds = None
    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, req_scopes)
            logger.info(f"Loaded credentials from token.json for {service_name}")
        except Exception as e:
            logger.warning(f"Error reading token.json for {service_name}: {e}")

    try:
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info(f"Credentials expired for {service_name}. Refreshing OAuth token...")
                creds.refresh(Request())
            else:
                logger.info(f"Initializing OAuth login flow for Google {service_name}...")
                # Request Calendar & Tasks by default to avoid failing if Gmail API isn't enabled
                flow_scopes = SERVICE_SCOPES['gmail'] if service_name.lower() == 'gmail' else CALENDAR_TASKS_SCOPES
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, flow_scopes)
                creds = flow.run_local_server(port=0)

            with open(TOKEN_PATH, 'w') as token_file:
                token_file.write(creds.to_json())
                logger.info(f"Updated credentials written to {TOKEN_PATH}")

        service = build(service_name, version, credentials=creds)
        return service, None

    except Exception as e:
        msg = f"Google {service_name.capitalize()} API OAuth authentication failed: {e}"
        logger.error(msg)
        return None, msg


# ==========================================
# GOOGLE TASKS INTEGRATION
# ==========================================

def add_google_task(title: str, notes: Optional[str] = None) -> Tuple[bool, str]:
    """Adds a task to the default Google Tasks list."""
    service, err = get_google_service('tasks', 'v1')
    if not service:
        return False, f"Could not connect to Google Tasks: {err}"

    try:
        task_body = {
            'title': title,
            'notes': notes or 'Added by Jarvis Assistant'
        }
        result = service.tasks().insert(tasklist='@default', body=task_body).execute()
        task_id = result.get('id', '')
        msg = f"Task '{title}' added successfully to Google Tasks!"
        logger.info(f"{msg} (ID: {task_id})")
        return True, msg
    except Exception as e:
        msg = f"Failed to add Google Task: {e}"
        logger.error(msg)
        return False, msg


def list_google_tasks(max_results: int = 5) -> Tuple[bool, str]:
    """Lists upcoming/active tasks from Google Tasks."""
    service, err = get_google_service('tasks', 'v1')
    if not service:
        return False, f"Could not connect to Google Tasks: {err}"

    try:
        results = service.tasks().list(tasklist='@default', maxResults=max_results, showCompleted=False).execute()
        items = results.get('items', [])
        if not items:
            return True, "You have no pending tasks in Google Tasks."

        task_strings = []
        for idx, item in enumerate(items, 1):
            title = item.get('title', 'Untitled Task')
            notes = item.get('notes', '')
            note_str = f" ({notes})" if notes else ""
            task_strings.append(f"{idx}. {title}{note_str}")

        msg = "Here are your active Google Tasks:\n" + "\n".join(task_strings)
        return True, msg
    except Exception as e:
        msg = f"Failed to fetch Google Tasks: {e}"
        logger.error(msg)
        return False, msg


def complete_google_task(task_title_or_query: str) -> Tuple[bool, str]:
    """Marks a task as completed in Google Tasks by matching title."""
    service, err = get_google_service('tasks', 'v1')
    if not service:
        return False, f"Could not connect to Google Tasks: {err}"

    try:
        results = service.tasks().list(tasklist='@default', showCompleted=False).execute()
        items = results.get('items', [])
        
        target_task = None
        for item in items:
            title = item.get('title', '').lower()
            if task_title_or_query.lower() in title or title in task_title_or_query.lower():
                target_task = item
                break

        if not target_task:
            return False, f"Could not find an active task matching '{task_title_or_query}'."

        task_id = target_task['id']
        target_task['status'] = 'completed'
        service.tasks().update(tasklist='@default', task=task_id, body=target_task).execute()
        
        msg = f"Task '{target_task.get('title')}' marked as completed in Google Tasks!"
        logger.info(msg)
        return True, msg

    except Exception as e:
        msg = f"Failed to complete Google Task: {e}"
        logger.error(msg)
        return False, msg


# ==========================================
# GMAIL INTEGRATION
# ==========================================

def check_unread_emails(max_results: int = 5) -> Tuple[bool, str]:
    """Checks for unread emails in Gmail inbox."""
    service, err = get_google_service('gmail', 'v1')
    if not service:
        return False, f"Could not connect to Gmail: {err}"

    try:
        response = service.users().messages().list(userId='me', q='is:unread', maxResults=max_results).execute()
        messages = response.get('messages', [])

        if not messages:
            return True, "You have no unread emails in your Gmail inbox."

        email_summaries = []
        for idx, msg in enumerate(messages, 1):
            msg_data = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
            headers = msg_data.get('payload', {}).get('headers', [])
            
            subject = "No Subject"
            sender = "Unknown Sender"
            for h in headers:
                if h['name'].lower() == 'subject':
                    subject = h['value']
                elif h['name'].lower() == 'from':
                    sender = h['value']
            
            email_summaries.append(f"{idx}. From {sender}: '{subject}'")

        result_msg = f"You have unread emails in Gmail:\n" + "\n".join(email_summaries)
        return True, result_msg

    except Exception as e:
        msg = f"Failed to check Gmail emails: {e}"
        logger.error(msg)
        return False, msg


def send_email(to_address: str, subject: str, body: str) -> Tuple[bool, str]:
    """Sends an email using Gmail API."""
    service, err = get_google_service('gmail', 'v1')
    if not service:
        return False, f"Could not connect to Gmail: {err}"

    try:
        message = MIMEText(body)
        message['to'] = to_address
        message['subject'] = subject
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        send_body = {'raw': raw_message}
        
        service.users().messages().send(userId='me', body=send_body).execute()
        msg = f"Email sent successfully to {to_address} with subject '{subject}'."
        logger.info(msg)
        return True, msg

    except Exception as e:
        msg = f"Failed to send email via Gmail API: {e}"
        logger.error(msg)
        return False, msg


# ==========================================
# GOOGLE CALENDAR WRAPPERS
# ==========================================

def add_calendar_event(title: str, datetime_str: Optional[str] = None) -> Tuple[bool, str]:
    """Schedules an event on Google Calendar and local DB."""
    from actions.reminders import create_calendar_reminder
    return create_calendar_reminder(title, datetime_str)


def list_calendar_events(max_results: int = 5) -> Tuple[bool, str]:
    """Lists upcoming events from Google Calendar."""
    from actions.reminders import list_calendar_reminders
    return list_calendar_reminders(max_results)


def get_structured_calendar_events(max_results: int = 10) -> List[Dict]:
    """Returns structured calendar events for HUD visualization."""
    service, err = get_google_service('calendar', 'v3')
    if not service:
        logger.warning(f"Calendar service unavailable: {err}")
        return []

    try:
        import datetime
        now_iso = datetime.datetime.now().astimezone().isoformat()
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now_iso,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        raw_events = events_result.get('items', [])
        structured = []
        for ev in raw_events:
            start_val = ev.get('start', {}).get('dateTime', ev.get('start', {}).get('date', ''))
            end_val = ev.get('end', {}).get('dateTime', ev.get('end', {}).get('date', ''))
            structured.append({
                "id": ev.get("id"),
                "summary": ev.get("summary", "Untitled Event"),
                "start": start_val,
                "end": end_val,
                "location": ev.get("location", ""),
                "htmlLink": ev.get("htmlLink", "")
            })
        return structured
    except Exception as e:
        logger.error(f"Error fetching structured calendar events: {e}")
        return []


def get_week_agenda(days: int = 7) -> List[Dict]:
    """
    Returns structured 7-day agenda from Google Calendar for the 3D Week Dashboard.
    Guarantees 7 consecutive day buckets starting from today, with associated events.
    """
    import datetime
    now = datetime.datetime.now().astimezone()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Pre-populate 7 days
    agenda = []
    day_map = {}
    for i in range(days):
        day_date = today_start + datetime.timedelta(days=i)
        d_key = day_date.strftime("%Y-%m-%d")
        day_obj = {
            "date": d_key,
            "day_name": day_date.strftime("%A"),
            "day_short": day_date.strftime("%a").upper(),
            "day_num": day_date.strftime("%d"),
            "month_short": day_date.strftime("%b").upper(),
            "display_date": day_date.strftime("%b %d").upper(),
            "is_today": (i == 0),
            "events": []
        }
        agenda.append(day_obj)
        day_map[d_key] = day_obj
        
    service, err = get_google_service('calendar', 'v3')
    if not service:
        logger.warning(f"Calendar service unavailable for week agenda: {err}")
        return agenda

    try:
        end_window = today_start + datetime.timedelta(days=days)
        events_result = service.events().list(
            calendarId='primary',
            timeMin=today_start.isoformat(),
            timeMax=end_window.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        raw_events = events_result.get('items', [])
        for ev in raw_events:
            start_raw = ev.get('start', {})
            start_val = start_raw.get('dateTime', start_raw.get('date', ''))
            end_raw = ev.get('end', {})
            end_val = end_raw.get('dateTime', end_raw.get('date', ''))

            # Parse start time and date
            time_str = "All Day"
            event_date_key = ""
            if 'T' in start_val:
                try:
                    dt = datetime.datetime.fromisoformat(start_val.replace('Z', '+00:00'))
                    local_dt = dt.astimezone()
                    event_date_key = local_dt.strftime("%Y-%m-%d")
                    time_str = local_dt.strftime("%I:%M %p")
                except Exception:
                    event_date_key = start_val.split('T')[0]
            else:
                event_date_key = start_val

            event_entry = {
                "id": ev.get("id"),
                "summary": ev.get("summary", "Untitled Event"),
                "start": start_val,
                "end": end_val,
                "time_str": time_str,
                "location": ev.get("location", ""),
                "htmlLink": ev.get("htmlLink", "")
            }

            if event_date_key in day_map:
                day_map[event_date_key]["events"].append(event_entry)

    except Exception as e:
        logger.error(f"Error fetching week agenda events: {e}")

    return agenda



def get_structured_tasks(max_results: int = 20) -> List[Dict]:
    """Returns structured Google Tasks for HUD checklist."""
    service, err = get_google_service('tasks', 'v1')
    if not service:
        logger.warning(f"Tasks service unavailable: {err}")
        return []

    try:
        results = service.tasks().list(tasklist='@default', maxResults=max_results, showCompleted=True).execute()
        items = results.get('items', [])
        return [
            {
                "id": t.get("id"),
                "title": t.get("title", "Untitled Task"),
                "notes": t.get("notes", ""),
                "status": t.get("status", "needsAction"),
                "completed": t.get("status") == "completed",
                "due": t.get("due", "")
            }
            for t in items
        ]
    except Exception as e:
        logger.error(f"Error fetching structured tasks: {e}")
        return []


def set_task_completed(task_id: str, completed: bool = True) -> Tuple[bool, str]:
    """Toggles task status by task ID."""
    service, err = get_google_service('tasks', 'v1')
    if not service:
        return False, f"Could not connect to Google Tasks: {err}"

    try:
        new_status = 'completed' if completed else 'needsAction'
        patch_body = {'status': new_status}
        if not completed:
            patch_body['completed'] = None
        service.tasks().patch(tasklist='@default', task=task_id, body=patch_body).execute()
        return True, f"Task status updated to {new_status}."
    except Exception as e:
        return False, f"Failed to update task: {e}"


