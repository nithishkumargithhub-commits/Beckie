import time
import datetime
import sqlite3
import threading
import logging
from typing import List, Callable, Optional

import config
import actions.database as database

logger = logging.getLogger("VoiceAssistant.ReminderDaemon")

class ReminderDaemon:
    """
    Background daemon thread that periodically checks for due reminders
    and triggers speech alerts and callbacks (e.g. WebSocket broadcasts).
    """
    def __init__(self, check_interval_seconds: int = 30):
        self.check_interval = check_interval_seconds
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.notification_callbacks: List[Callable[[dict], None]] = []

    def register_callback(self, callback: Callable[[dict], None]):
        """Registers a callback function (e.g. WebSocket broadcast) to call on reminder alert."""
        self.notification_callbacks.append(callback)

    def start(self):
        """Starts the background monitoring loop in a daemon thread."""
        if self.running:
            logger.warning("ReminderDaemon is already running.")
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True, name="ReminderDaemonThread")
        self.thread.start()
        logger.info("ReminderDaemon background thread started.")

    def stop(self):
        """Stops the background monitoring loop."""
        self.running = False
        logger.info("ReminderDaemon requested to stop.")

    def _run_loop(self):
        """Main loop checking for due reminders every interval."""
        while self.running:
            try:
                self.check_and_notify_due_reminders()
            except Exception as e:
                logger.error(f"Error in ReminderDaemon check loop: {e}")
            
            # Sleep in 1-second chunks to allow graceful thread exit
            for _ in range(self.check_interval):
                if not self.running:
                    break
                time.sleep(1)

    def check_and_notify_due_reminders(self):
        """
        Checks local database for pending reminders scheduled on or before current time.
        """
        conn = sqlite3.connect(database.DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        now_dt = datetime.datetime.now().astimezone()
        now_iso = now_dt.isoformat()

        due_reminders = []
        try:
            cursor.execute(
                "SELECT id, title, scheduled_time, status FROM reminders WHERE status = 'pending'"
            )
            rows = cursor.fetchall()

            for row in rows:
                r_dict = dict(row)
                s_time_str = r_dict.get("scheduled_time", "")
                try:
                    s_dt = datetime.datetime.fromisoformat(s_time_str)
                    if s_dt.tzinfo is None:
                        s_dt = s_dt.astimezone()
                    # Check if scheduled time is on or before current time
                    if s_dt <= now_dt:
                        due_reminders.append(r_dict)
                except Exception as ex:
                    logger.warning(f"Could not parse reminder timestamp '{s_time_str}': {ex}")

            # Notify and update database for due reminders
            for rem in due_reminders:
                rem_id = rem["id"]
                title = rem.get("title", "Untitled Reminder")

                logger.info(f"DUE REMINDER TRIGGERED: ID {rem_id} - '{title}'")

                # Mark as notified in database
                cursor.execute(
                    "UPDATE reminders SET status = 'notified' WHERE id = ?", (rem_id,)
                )
                conn.commit()

                # Dispatch notifications to registered callbacks (TTS & WebSockets)
                payload = {
                    "event": "reminder_due",
                    "id": rem_id,
                    "title": title,
                    "scheduled_time": rem.get("scheduled_time"),
                    "message": f"Reminder Alert: {title}"
                }

                for cb in self.notification_callbacks:
                    try:
                        cb(payload)
                    except Exception as cb_err:
                        logger.error(f"Error in reminder callback: {cb_err}")

        except Exception as e:
            logger.error(f"Failed to query due reminders: {e}")
        finally:
            conn.close()

# Global daemon singleton instance
reminder_daemon = ReminderDaemon(check_interval_seconds=30)
