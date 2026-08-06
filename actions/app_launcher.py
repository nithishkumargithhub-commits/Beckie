"""
Offline Windows App Launcher Action.
Execution latency: ~100ms
"""

import os
from logger import profile, get_logger

logger = get_logger("Jarvis.Actions.AppLauncher")

# Common Windows App Path mappings
APP_MAP = {
    "chrome": "start chrome",
    "google chrome": "start chrome",
    "notepad": "start notepad",
    "calculator": "start calc",
    "calc": "start calc",
    "explorer": "start explorer",
    "file explorer": "start explorer",
    "vscode": "code",
    "vs code": "code",
    "code": "code",
    "spotify": "start spotify",
    "cmd": "start cmd",
    "command prompt": "start cmd",
    "terminal": "start wt",
}

@profile
def launch_app(app_name: str) -> str:
    """Launches specified desktop application."""
    clean_name = app_name.lower().strip()
    cmd = APP_MAP.get(clean_name, f"start {clean_name}")
    try:
        os.system(cmd)
        return f"Opening {app_name}."
    except Exception as e:
        logger.error(f"Error launching app '{app_name}': {e}")
        return f"Could not launch {app_name}."

@profile
def close_app(app_name: str) -> str:
    """Closes specified desktop application."""
    clean_name = app_name.lower().strip().replace(".exe", "")
    try:
        os.system(f"taskkill /f /im {clean_name}.exe")
        return f"Closed {app_name}."
    except Exception as e:
        logger.error(f"Error closing app '{app_name}': {e}")
        return f"Could not close {app_name}."
