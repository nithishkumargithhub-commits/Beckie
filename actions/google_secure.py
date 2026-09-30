"""
JARVIS – Gmail & Google Calendar OAuth integration (read-only scopes).

Design
------
* Uses ONLY read-only OAuth scopes – no accidental writes possible.
* Tokens are stored encrypted via core.token_store (SQLCipher + Fernet).
* Token refresh is handled transparently on every call.
* Calendar polling runs as a background daemon thread (daily by default).

Scopes
------
  Gmail    : https://www.googleapis.com/auth/gmail.readonly
  Calendar : https://www.googleapis.com/auth/calendar.readonly

Setup
-----
  1. Place your OAuth client JSON at <project_root>/credentials.json
     (Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client IDs)
  2. On first use, a browser window opens for consent.
  3. Subsequent calls are token-based (auto-refreshed, stored encrypted).
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import config
from core.token_store import (
    delete_token,
    load_token,
    save_token,
    token_needs_refresh,
)

logger = logging.getLogger("Jarvis.Actions.GoogleSecure")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CREDENTIALS_PATH = Path(config.BASE_DIR) / "credentials.json"

# Strictly read-only — no write scopes
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

_GMAIL_PROVIDER = "google_gmail"
_CALENDAR_PROVIDER = "google_calendar"
_ACCOUNT = "default"


# ---------------------------------------------------------------------------
# Shared OAuth helper
# ---------------------------------------------------------------------------

def _build_service(provider: str, scopes: List[str], service_name: str, version: str):
    """
    Build a Google API service, refreshing / re-authorising the token as needed.
    Tokens are persisted encrypted via core.token_store.
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            f"credentials.json not found at {CREDENTIALS_PATH}. "
            "Download from Google Cloud Console → APIs & Services → Credentials."
        )

    creds: Optional[Credentials] = None

    # Load from encrypted store
    stored = load_token(provider, _ACCOUNT)
    if stored:
        try:
            creds = Credentials.from_authorized_user_info(stored, scopes)
        except Exception as exc:
            logger.warning("Stored token invalid for %s: %s – re-authorising", provider, exc)
            delete_token(provider, _ACCOUNT)
            creds = None

    # Refresh or re-authorise
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired token for provider '%s'…", provider)
            creds.refresh(Request())
        else:
            logger.info("Starting OAuth consent flow for '%s'…", provider)
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), scopes)
            creds = flow.run_local_server(port=0)

        # Persist refreshed/new token
        token_dict = json.loads(creds.to_json())
        expires_at = (
            creds.expiry.isoformat() + "Z"
            if creds.expiry
            else None
        )
        save_token(provider, _ACCOUNT, token_dict, " ".join(scopes), expires_at)
        logger.info("Token saved for '%s'", provider)

    return build(service_name, version, credentials=creds)


# ---------------------------------------------------------------------------
# Gmail (read-only)
# ---------------------------------------------------------------------------

def check_unread_emails_secure(max_results: int = 5) -> Tuple[bool, str]:
    """
    Fetch unread Gmail messages (gmail.readonly scope).
    Returns (success, human-readable message).
    """
    try:
        service = _build_service(_GMAIL_PROVIDER, GMAIL_SCOPES, "gmail", "v1")
        response = (
            service.users()
            .messages()
            .list(userId="me", q="is:unread", maxResults=max_results)
            .execute()
        )
        messages = response.get("messages", [])

        if not messages:
            return True, "You have no unread emails in your Gmail inbox."

        summaries: List[str] = []
        for idx, msg in enumerate(messages, 1):
            data = (
                service.users()
                .messages()
                .get(userId="me", id=msg["id"], format="metadata",
                     metadataHeaders=["Subject", "From"])
                .execute()
            )
            headers = {
                h["name"].lower(): h["value"]
                for h in data.get("payload", {}).get("headers", [])
            }
            subject = headers.get("subject", "No Subject")
            sender = headers.get("from", "Unknown Sender")
            summaries.append(f"{idx}. From {sender}: '{subject}'")

        return True, "Unread emails:\n" + "\n".join(summaries)

    except FileNotFoundError as exc:
        return False, str(exc)
    except Exception as exc:
        msg = f"Gmail check failed: {exc}"
        logger.error(msg)
        return False, msg


def get_gmail_token_status() -> str:
    """Return a human-readable token status string for diagnostics."""
    needs = token_needs_refresh(_GMAIL_PROVIDER, _ACCOUNT)
    return "Token valid ✓" if not needs else "Token missing or near expiry – will re-auth on next call"


# ---------------------------------------------------------------------------
# Calendar (read-only) + daily polling daemon
# ---------------------------------------------------------------------------

def get_upcoming_events(max_results: int = 5) -> Tuple[bool, str]:
    """
    Fetch upcoming Calendar events (calendar.readonly scope).
    Returns (success, human-readable message).
    """
    try:
        service = _build_service(_CALENDAR_PROVIDER, CALENDAR_SCOPES, "calendar", "v3")
        now_iso = datetime.now(tz=timezone.utc).isoformat()
        result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now_iso,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = result.get("items", [])

        if not events:
            return True, "No upcoming events found in your calendar."

        summaries: List[str] = []
        for idx, event in enumerate(events, 1):
            summary = event.get("summary", "Untitled Event")
            start = event["start"].get("dateTime") or event["start"].get("date", "Unknown time")
            summaries.append(f"{idx}. {summary} at {start}")

        return True, "Upcoming events:\n" + "\n".join(summaries)

    except FileNotFoundError as exc:
        return False, str(exc)
    except Exception as exc:
        msg = f"Calendar fetch failed: {exc}"
        logger.error(msg)
        return False, msg


class CalendarReminderDaemon:
    """
    Background thread that polls Google Calendar daily and triggers Beckie's
    TTS to announce reminders for events starting within the next hour.
    """

    def __init__(
        self,
        speak_fn,
        poll_interval_seconds: int = 86400,  # 24 hours
        lookahead_minutes: int = 60,
    ) -> None:
        self._speak = speak_fn
        self._interval = poll_interval_seconds
        self._lookahead = lookahead_minutes
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="CalendarPoller")
        self._thread.start()
        logger.info("CalendarReminderDaemon started (poll every %ds)", self._interval)

    def stop(self) -> None:
        self._running = False

    def _loop(self) -> None:
        while self._running:
            self._check_and_announce()
            time.sleep(self._interval)

    def _check_and_announce(self) -> None:
        try:
            from datetime import timedelta

            service = _build_service(
                _CALENDAR_PROVIDER, CALENDAR_SCOPES, "calendar", "v3"
            )
            now = datetime.now(tz=timezone.utc)
            window_end = now + timedelta(minutes=self._lookahead)

            result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=now.isoformat(),
                    timeMax=window_end.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = result.get("items", [])
            for event in events:
                summary = event.get("summary", "an event")
                start_str = event["start"].get("dateTime") or event["start"].get("date", "")
                self._speak(f"Reminder: {summary} is coming up soon at {start_str}.")
                logger.info("Announced reminder for event: %s", summary)
        except Exception as exc:
            logger.error("CalendarReminderDaemon error: %s", exc)
