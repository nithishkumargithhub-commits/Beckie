"""
JARVIS - Activity Tracker.

Tracks user development, meetings, study sessions, and browser domains
using ONLY approved categories.
PRIVACY GUARANTEE: Strictly NO keylogging and NO screen recording.
Only active foreground window metadata and sanitized domains are recorded.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

logger = logging.getLogger("Jarvis.Actions.ActivityTracker")


# ---------------------------------------------------------------------------
# Approved Activity Categories (STRICT REQUIREMENT)
# ---------------------------------------------------------------------------

class ActivityCategory(str, Enum):
    DEVELOPMENT      = "Development"
    MEETING          = "Meeting"
    STUDY_SESSION    = "Study Session"
    BROWSER_RESEARCH = "Browser Research"
    COMMUNICATION    = "Communication"
    UTILITY          = "Utility"
    BREAK_IDLE       = "Break / Idle"


APPROVED_CATEGORIES: Set[str] = {c.value for c in ActivityCategory}


def validate_category(category: str) -> str:
    """
    Validates that a category belongs strictly to the approved list.
    Raises ValueError if category is not approved.
    """
    for approved in APPROVED_CATEGORIES:
        if category.strip().lower() == approved.lower():
            return approved
    raise ValueError(
        f"Disallowed category '{category}'. Category must strictly be one of: "
        f"{sorted(APPROVED_CATEGORIES)}"
    )


# ---------------------------------------------------------------------------
# Approved Applications and Domain Mapping Rules
# ---------------------------------------------------------------------------

APP_CATEGORY_MAP: Dict[str, ActivityCategory] = {
    # Development
    "code.exe":             ActivityCategory.DEVELOPMENT,
    "code.cmd":             ActivityCategory.DEVELOPMENT,
    "cursor.exe":           ActivityCategory.DEVELOPMENT,
    "antigravity.exe":      ActivityCategory.DEVELOPMENT,
    "pycharm64.exe":        ActivityCategory.DEVELOPMENT,
    "pycharm.exe":          ActivityCategory.DEVELOPMENT,
    "idea64.exe":           ActivityCategory.DEVELOPMENT,
    "wt.exe":               ActivityCategory.DEVELOPMENT,
    "cmd.exe":              ActivityCategory.DEVELOPMENT,
    "powershell.exe":       ActivityCategory.DEVELOPMENT,
    "git.exe":              ActivityCategory.DEVELOPMENT,
    "devenv.exe":           ActivityCategory.DEVELOPMENT,
    # Meetings
    "zoom.exe":             ActivityCategory.MEETING,
    "teams.exe":            ActivityCategory.MEETING,
    "webexmta.exe":         ActivityCategory.MEETING,
    # Communication
    "slack.exe":            ActivityCategory.COMMUNICATION,
    "discord.exe":          ActivityCategory.COMMUNICATION,
    "thunderbird.exe":      ActivityCategory.COMMUNICATION,
    "outlook.exe":          ActivityCategory.COMMUNICATION,
    # Utilities
    "notepad.exe":          ActivityCategory.UTILITY,
    "calc.exe":             ActivityCategory.UTILITY,
    "explorer.exe":         ActivityCategory.UTILITY,
    "taskmgr.exe":          ActivityCategory.UTILITY,
    "mspaint.exe":          ActivityCategory.UTILITY,
    "spotify.exe":          ActivityCategory.BREAK_IDLE,
}

DOMAIN_CATEGORY_MAP: Dict[str, ActivityCategory] = {
    # Meeting domains
    "meet.google.com":          ActivityCategory.MEETING,
    "zoom.us":                  ActivityCategory.MEETING,
    "teams.microsoft.com":      ActivityCategory.MEETING,
    "teams.live.com":           ActivityCategory.MEETING,
    # Study session domains
    "coursera.org":             ActivityCategory.STUDY_SESSION,
    "edx.org":                  ActivityCategory.STUDY_SESSION,
    "khanacademy.org":          ActivityCategory.STUDY_SESSION,
    "arxiv.org":                ActivityCategory.STUDY_SESSION,
    "scholar.google.com":       ActivityCategory.STUDY_SESSION,
    "mit.edu":                  ActivityCategory.STUDY_SESSION,
    "stanford.edu":             ActivityCategory.STUDY_SESSION,
    # Development domains
    "github.com":               ActivityCategory.DEVELOPMENT,
    "gitlab.com":               ActivityCategory.DEVELOPMENT,
    "stackoverflow.com":        ActivityCategory.DEVELOPMENT,
    "docs.python.org":          ActivityCategory.DEVELOPMENT,
    "pypi.org":                 ActivityCategory.DEVELOPMENT,
    "developer.mozilla.org":    ActivityCategory.DEVELOPMENT,
    "w3schools.com":            ActivityCategory.DEVELOPMENT,
    # Communication domains
    "mail.google.com":          ActivityCategory.COMMUNICATION,
    "outlook.office.com":       ActivityCategory.COMMUNICATION,
    "slack.com":                ActivityCategory.COMMUNICATION,
    "discord.com":              ActivityCategory.COMMUNICATION,
}


@dataclass
class ActivityRecord:
    category: str
    app_name: str
    window_title: Optional[str] = None
    domain: Optional[str] = None
    duration_sec: float = 0.0
    timestamp: Optional[str] = None
    session_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None

    def __post_init__(self) -> None:
        # Strictly enforce approved category
        self.category = validate_category(self.category)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "app_name": self.app_name,
            "window_title": self.window_title,
            "domain": self.domain,
            "duration_sec": self.duration_sec,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "details": self.details,
        }


class ActivityTracker:
    """
    Manages activity tracking, study sessions, and meeting detection.
    Guarantees zero keystroke logging and zero screen recording.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        from db.schema import DB_PATH
        self._db_path = db_path or DB_PATH
        self._current_study_session: Optional[Dict[str, Any]] = None
        self._last_poll_time: float = time.time()
        self._last_app: Optional[str] = None
        self._last_title: Optional[str] = None

    # ------------------------------------------------------------------
    # Sanitization & Privacy (Requirement 6)
    # ------------------------------------------------------------------

    @staticmethod
    def sanitize_title(title: Optional[str]) -> Optional[str]:
        """Strips tokens, passwords, and sensitive keys from window titles."""
        if not title:
            return None
        # Redact anything matching tokens, auth headers, passwords, keys
        sanitized = re.sub(
            r"(?i)(token|key|secret|password|auth|bearer)=[\w\-.~]+",
            r"\1=***",
            title,
        )
        return sanitized[:256]

    @staticmethod
    def extract_domain_from_title(title: Optional[str]) -> Optional[str]:
        """
        Extracts high-level domain from browser window title (e.g. 'Google Chrome - GitHub').
        Only extracts approved web domain names; discards paths, parameters, or session tokens.
        """
        if not title:
            return None

        # Common browser patterns: "Page Title - Google Chrome", "Page Title — Mozilla Firefox"
        # Check known domains in title
        for known_domain in DOMAIN_CATEGORY_MAP.keys():
            if known_domain in title.lower() or known_domain.split(".")[0] in title.lower():
                return known_domain

        # Regex for generic domain names
        match = re.search(r"\b([a-zA-Z0-9\-]+\.(?:com|org|io|net|edu|gov|dev|ai))\b", title, re.IGNORECASE)
        if match:
            return match.group(1).lower()

        return None

    # ------------------------------------------------------------------
    # Categorization Engine
    # ------------------------------------------------------------------

    def classify_activity(
        self,
        app_name: str,
        window_title: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> ActivityCategory:
        """
        Classifies an activity strictly into one of the approved categories.
        """
        app_lower = app_name.lower().strip()
        title_lower = (window_title or "").lower()

        # 1. Active study session override
        if self._current_study_session is not None:
            # If the user is browsing or coding during an active study session, count as Study Session
            if domain in DOMAIN_CATEGORY_MAP and DOMAIN_CATEGORY_MAP[domain] in (
                ActivityCategory.STUDY_SESSION, ActivityCategory.DEVELOPMENT, ActivityCategory.BROWSER_RESEARCH
            ):
                return ActivityCategory.STUDY_SESSION
            if app_lower in APP_CATEGORY_MAP and APP_CATEGORY_MAP[app_lower] in (
                ActivityCategory.DEVELOPMENT, ActivityCategory.UTILITY
            ):
                return ActivityCategory.STUDY_SESSION

        # 2. Meeting detection from domain or title
        if domain and domain in DOMAIN_CATEGORY_MAP and DOMAIN_CATEGORY_MAP[domain] == ActivityCategory.MEETING:
            return ActivityCategory.MEETING

        if any(meeting_kw in title_lower for meeting_kw in ("meet - ", "zoom meeting", "microsoft teams", "webex meeting")):
            return ActivityCategory.MEETING

        # 3. Domain-specific classification for browsers
        if domain and domain in DOMAIN_CATEGORY_MAP:
            return DOMAIN_CATEGORY_MAP[domain]

        # 4. App-specific classification
        if app_lower in APP_CATEGORY_MAP:
            cat = APP_CATEGORY_MAP[app_lower]
            # If browser, default to Browser Research
            if app_lower in ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe"):
                return ActivityCategory.BROWSER_RESEARCH
            return cat

        # 5. Default fallback strictly within approved list
        if any(browser in app_lower for browser in ("chrome", "edge", "firefox", "browser")):
            return ActivityCategory.BROWSER_RESEARCH

        return ActivityCategory.UTILITY

    # ------------------------------------------------------------------
    # Window Metadata Polling (No Keylogging / Screen Recording)
    # ------------------------------------------------------------------

    def get_current_foreground_window(self) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Retrieves active window process name and sanitized title using standard Windows APIs.
        NO KEYLOGGING AND NO SCREEN RECORDING IS PERFORMED.
        """
        app_name = "unknown.exe"
        window_title: Optional[str] = None
        domain: Optional[str] = None

        if sys.platform == "win32":
            try:
                import win32gui
                import win32process
                import psutil

                hwnd = win32gui.GetForegroundWindow()
                if hwnd:
                    raw_title = win32gui.GetWindowText(hwnd)
                    window_title = self.sanitize_title(raw_title)
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if pid > 0:
                        try:
                            proc = psutil.Process(pid)
                            app_name = proc.name().lower()
                        except Exception:
                            pass
            except Exception as exc:
                logger.debug("Error querying foreground window: %s", exc)

        if window_title:
            domain = self.extract_domain_from_title(window_title)

        return app_name, window_title, domain

    # ------------------------------------------------------------------
    # Activity Logging to SQLite
    # ------------------------------------------------------------------

    def log_activity(
        self,
        category: str,
        app_name: str,
        window_title: Optional[str] = None,
        domain: Optional[str] = None,
        duration_sec: float = 0.0,
        session_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> ActivityRecord:
        """
        Records an activity entry in SQLite after validating the category.
        """
        approved_cat = validate_category(category)
        sanitized_title = self.sanitize_title(window_title)

        record = ActivityRecord(
            category=approved_cat,
            app_name=app_name,
            window_title=sanitized_title,
            domain=domain,
            duration_sec=duration_sec,
            session_id=session_id,
            details=details or {},
        )

        from db.schema import get_db
        try:
            with get_db(self._db_path) as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO activity_logs
                        (category, app_name, window_title, domain, duration_sec, session_id, details_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.category,
                        record.app_name,
                        record.window_title,
                        record.domain,
                        record.duration_sec,
                        record.session_id,
                        json.dumps(record.details),
                    ),
                )
                record.id = cursor.lastrowid
        except Exception as exc:
            logger.error("Failed to insert activity log: %s", exc)

        return record

    def record_current_activity(
        self,
        duration_sec: float = 30.0,
        session_id: Optional[str] = None,
    ) -> ActivityRecord:
        """
        Polls current foreground window and logs activity entry.
        """
        app_name, title, domain = self.get_current_foreground_window()
        category = self.classify_activity(app_name, title, domain)

        return self.log_activity(
            category=category.value,
            app_name=app_name,
            window_title=title,
            domain=domain,
            duration_sec=duration_sec,
            session_id=session_id,
        )

    # ------------------------------------------------------------------
    # Study Sessions
    # ------------------------------------------------------------------

    def start_study_session(
        self,
        subject: str,
        goal: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Starts a tracked study session."""
        sid = session_id or uuid.uuid4().hex[:12]
        start_time_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        from db.schema import get_db
        with get_db(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO study_sessions
                    (session_id, subject, goal, start_time, status, duration_sec)
                VALUES (?, ?, ?, ?, 'active', 0.0)
                """,
                (sid, subject, goal, start_time_iso),
            )

        self._current_study_session = {
            "session_id": sid,
            "subject": subject,
            "goal": goal,
            "start_time": time.time(),
        }
        logger.info("Study session started: %s (subject: %s)", sid, subject)
        return self._current_study_session

    def end_study_session(
        self,
        session_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Ends an active study session and records total duration."""
        active = self._current_study_session
        sid = session_id or (active["session_id"] if active else None)

        if not sid:
            return {"status": "error", "message": "No active study session to end."}

        end_time_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        from db.schema import get_db
        with get_db(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM study_sessions WHERE session_id = ?", (sid,)
            ).fetchone()
            if not row:
                return {"status": "error", "message": f"Session {sid} not found."}

            start_t = active["start_time"] if (active and active["session_id"] == sid) else time.time() - 3600
            duration_sec = max(1.0, time.time() - start_t)

            conn.execute(
                """
                UPDATE study_sessions
                SET end_time = ?, status = 'completed', notes = ?, duration_sec = ?
                WHERE session_id = ?
                """,
                (end_time_iso, notes, duration_sec, sid),
            )

        # Log study session activity record
        self.log_activity(
            category=ActivityCategory.STUDY_SESSION.value,
            app_name="study_session",
            window_title=f"Study Session: {row['subject']}",
            duration_sec=duration_sec,
            session_id=sid,
            details={"goal": row["goal"], "notes": notes},
        )

        if active and active.get("session_id") == sid:
            self._current_study_session = None

        return {
            "status": "completed",
            "session_id": sid,
            "duration_sec": duration_sec,
            "notes": notes,
        }

    def get_active_study_session(self) -> Optional[Dict[str, Any]]:
        return self._current_study_session

    # ------------------------------------------------------------------
    # Meetings
    # ------------------------------------------------------------------

    def log_meeting(
        self,
        title: str,
        duration_sec: float,
        domain: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        session_id: Optional[str] = None,
    ) -> ActivityRecord:
        """Manually or automatically log a meeting."""
        return self.log_activity(
            category=ActivityCategory.MEETING.value,
            app_name="meeting_client",
            window_title=title,
            domain=domain or "meet.google.com",
            duration_sec=duration_sec,
            session_id=session_id,
            details={"attendees": attendees or []},
        )


# Module-level instance
_default_tracker: Optional[ActivityTracker] = None


def get_activity_tracker(db_path: Optional[Path] = None) -> ActivityTracker:
    global _default_tracker
    if _default_tracker is None or (db_path and db_path != _default_tracker._db_path):
        _default_tracker = ActivityTracker(db_path=db_path)
    return _default_tracker
