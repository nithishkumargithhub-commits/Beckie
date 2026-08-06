"""
Offline Voice Notes Recording Action.
Execution latency: ~20ms
"""

import os
from datetime import datetime
from logger import profile, get_logger

logger = get_logger("Jarvis.Actions.Notes")

@profile
def append_voice_note(note_text: str) -> str:
    """Appends note text to voice_notes.txt with timestamp."""
    if not note_text or not note_text.strip():
        return "Note text was empty."
    try:
        notes_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "voice_notes.txt")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(notes_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {note_text.strip()}\n")
        return f"Note recorded: {note_text.strip()[:40]}"
    except Exception as e:
        logger.error(f"Error appending voice note: {e}")
        return "Could not record note."
