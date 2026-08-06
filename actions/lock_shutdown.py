"""
Offline Workstation Lock, Shutdown, and Restart Actions.
Execution latency: ~100ms
"""

import os
from logger import profile, get_logger

logger = get_logger("Jarvis.Actions.LockShutdown")

@profile
def lock_workstation() -> str:
    """Locks Windows session."""
    try:
        os.system("rundll32.exe user32.dll,LockWorkStation")
        return "Workstation locked."
    except Exception as e:
        logger.error(f"Error locking workstation: {e}")
        return "Failed to lock workstation."

@profile
def shutdown_system(delay_sec: int = 10) -> str:
    """Schedules Windows shutdown."""
    try:
        os.system(f"shutdown /s /t {delay_sec}")
        return f"System will shutdown in {delay_sec} seconds."
    except Exception as e:
        logger.error(f"Error executing shutdown: {e}")
        return "Failed to initiate shutdown."

@profile
def restart_system(delay_sec: int = 10) -> str:
    """Schedules Windows restart."""
    try:
        os.system(f"shutdown /r /t {delay_sec}")
        return f"System will restart in {delay_sec} seconds."
    except Exception as e:
        logger.error(f"Error executing restart: {e}")
        return "Failed to initiate restart."
