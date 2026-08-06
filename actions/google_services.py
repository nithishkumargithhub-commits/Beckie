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

# Unified OAuth Scopes for Calendar, Tasks, and Gmail
ALL_SCOPES = [
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/tasks',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send'
]

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

    creds = None
    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, ALL_SCOPES)
            logger.info("Loaded credentials from token.json")
        except Exception as e:
            logger.error(f"Error reading token.json: {e}")

    try:
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Credentials expired. Refreshing OAuth token...")
                creds.refresh(Request())
            else:
                logger.info(f"Initializing OAuth login flow for Google {service_name}...")
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, ALL_SCOPES)
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
