"""
Offline Time & Date Action.
Execution latency: ~10ms
"""

from datetime import datetime
from logger import profile, get_logger

logger = get_logger("Jarvis.Actions.TimeDate")

@profile
def get_current_time_date() -> str:
    """Returns current system time and date."""
    now = datetime.now()
    time_str = now.strftime("%I:%M %p")
    date_str = now.strftime("%A, %B %d, %Y")
    return f"It is currently {time_str} on {date_str}."
