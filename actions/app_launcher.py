"""
Offline Windows App Launcher Action.
Delegates to SafeFileOperations for whitelist verification, Tier 2 confirmation, and safe execution.
"""

from __future__ import annotations

import logging
from typing import Optional
from logger import profile, get_logger
from actions.file_ops import file_ops, SafeFileOperations

logger = get_logger("Jarvis.Actions.AppLauncher")


@profile
def launch_app(app_name: str) -> str:
    """Launches specified desktop application from approved whitelist."""
    success, msg = file_ops.launch_approved_app(app_name)
    return msg


@profile
def close_app(app_name: str) -> str:
    """Closes specified desktop application from approved whitelist."""
    clean_name = app_name.lower().strip().replace(".exe", "")
    from actions.file_ops import APPROVED_APPS
    if clean_name not in APPROVED_APPS:
        return f"Application '{app_name}' is not in the approved whitelist."
    try:
        import subprocess
        subprocess.run(["taskkill", "/f", "/im", f"{clean_name}.exe"], capture_output=True, shell=False)
        return f"Closed {app_name}."
    except Exception as e:
        logger.error(f"Error closing app '{app_name}': {e}")
        return f"Could not close {app_name}."
