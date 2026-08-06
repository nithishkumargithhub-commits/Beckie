"""
Offline Screenshot Action using PIL ImageGrab.
Execution latency: ~200ms
"""

import os
from datetime import datetime
from PIL import ImageGrab
from logger import profile, get_logger

logger = get_logger("Jarvis.Actions.Screenshot")

@profile
def capture_screenshot() -> str:
    """Captures desktop screen and saves it as a PNG image."""
    try:
        screenshots_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(screenshots_dir, f"screenshot_{timestamp}.png")
        
        screenshot = ImageGrab.grab()
        screenshot.save(filepath)
        logger.info(f"Screenshot saved to {filepath}")
        return f"Screenshot saved successfully."
    except Exception as e:
        logger.error(f"Error capturing screenshot: {e}")
        return "Could not capture screenshot."
