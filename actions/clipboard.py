"""
Offline Clipboard Actions using pyperclip.
Execution latency: ~10ms
"""

import pyperclip
from logger import profile, get_logger

logger = get_logger("Jarvis.Actions.Clipboard")

@profile
def get_clipboard_text() -> str:
    """Reads content from system clipboard."""
    try:
        text = pyperclip.paste().strip()
        if text:
            return f"Clipboard contains: {text[:100]}"
        return "Clipboard is currently empty."
    except Exception as e:
        logger.error(f"Error reading clipboard: {e}")
        return "Could not read clipboard."

@profile
def set_clipboard_text(text: str) -> str:
    """Copies text to system clipboard."""
    try:
        pyperclip.copy(text)
        return "Copied text to clipboard."
    except Exception as e:
        logger.error(f"Error setting clipboard: {e}")
        return "Could not copy text to clipboard."
