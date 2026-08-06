"""
Offline Windows Control Action using pygetwindow.
Execution latency: ~50ms
"""

from logger import profile, get_logger

logger = get_logger("Jarvis.Actions.WindowControl")

@profile
def control_window(action: str, window_name: str = "") -> str:
    """Controls active window (minimize, maximize, restore, close)."""
    action = action.lower().strip()
    try:
        import pygetwindow as gw
        active = gw.getActiveWindow()
        if not active:
            return "No active window detected."

        if "minimize" in action or "hide" in action:
            active.minimize()
            return "Window minimized."
        elif "maximize" in action or "expand" in action:
            active.maximize()
            return "Window maximized."
        elif "restore" in action:
            active.restore()
            return "Window restored."
        elif "close" in action:
            active.close()
            return "Window closed."
        else:
            return "Window control action executed."

    except Exception as e:
        logger.error(f"Error controlling window: {e}")
        return "Could not perform window operation."
