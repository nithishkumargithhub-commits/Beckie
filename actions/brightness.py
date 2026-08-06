"""
Offline Display Brightness Action using screen-brightness-control.
Execution latency: ~50ms
"""

from logger import profile, get_logger

logger = get_logger("Jarvis.Actions.Brightness")

@profile
def set_brightness(level: int = 70) -> str:
    """Sets screen brightness level (0-100)."""
    level = max(0, min(100, level))
    try:
        import screen_brightness_control as sbc
        sbc.set_brightness(level)
        return f"Screen brightness set to {level} percent."
    except Exception as e:
        logger.error(f"Error setting brightness: {e}")
        return f"Could not adjust display brightness."
